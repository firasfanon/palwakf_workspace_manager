from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

REGISTRY_STATE_KEY = "pre_l5_decision_supersession_registry_v1"


class DecisionStatus(StrEnum):
    current = "CURRENT"
    superseded = "SUPERSEDED"
    revoked = "REVOKED"
    historical = "HISTORICAL"


class DecisionRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=200)
    conflict_key: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    effective_at: datetime
    status: DecisionStatus
    authority: str = Field(min_length=1, max_length=200)
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)
    applies_to_projects: tuple[str, ...] = ("*",)
    supersedes: tuple[str, ...] = ()
    instruction_ids: tuple[str, ...] = ()
    directive_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("DECISION_EVIDENCE_MUST_BE_NONEMPTY")
        if any(not item.strip() for item in self.applies_to_projects):
            raise ValueError("DECISION_PROJECT_BINDING_MUST_BE_NONEMPTY")
        if self.decision_id in self.supersedes:
            raise ValueError("DECISION_CANNOT_SUPERSEDE_ITSELF")
        if len(set(self.supersedes)) != len(self.supersedes):
            raise ValueError("DECISION_DUPLICATE_SUPERSESSION_TARGET")
        if len(set(self.instruction_ids)) != len(self.instruction_ids):
            raise ValueError("DECISION_DUPLICATE_INSTRUCTION_BINDING")
        return self


class DecisionSupersessionRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_DECISION_SUPERSESSION_REGISTRY_V1"] = (
        "PALWAKF_DECISION_SUPERSESSION_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    imported_at: datetime
    records: tuple[DecisionRecordV1, ...] = Field(min_length=1)
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        by_id = {record.decision_id: record for record in self.records}
        if len(by_id) != len(self.records):
            raise ValueError("DECISION_REGISTRY_DUPLICATE_DECISION_ID")
        if any(record.source_revision != self.source_revision for record in self.records):
            raise ValueError("DECISION_REGISTRY_SOURCE_REVISION_MISMATCH")
        if any(record.authority_reference != self.authority_reference for record in self.records):
            raise ValueError("DECISION_REGISTRY_AUTHORITY_REFERENCE_MISMATCH")

        self._validate_current_uniqueness()
        self._validate_supersession_edges(by_id)
        self._validate_superseded_coverage(by_id)
        self._validate_no_cycles(by_id)
        return self

    def _validate_current_uniqueness(self) -> None:
        current = [record for record in self.records if record.status == DecisionStatus.current]
        for index, left in enumerate(current):
            for right in current[index + 1 :]:
                if left.conflict_key != right.conflict_key:
                    continue
                left_projects = set(left.applies_to_projects)
                right_projects = set(right.applies_to_projects)
                overlaps = (
                    "*" in left_projects
                    or "*" in right_projects
                    or bool(left_projects.intersection(right_projects))
                )
                if overlaps:
                    raise ValueError("DECISION_REGISTRY_MULTIPLE_CURRENT_DECISIONS")

    def _validate_supersession_edges(self, by_id: dict[str, DecisionRecordV1]) -> None:
        for record in self.records:
            for target_id in record.supersedes:
                target = by_id.get(target_id)
                if target is None:
                    raise ValueError("DECISION_REGISTRY_UNKNOWN_SUPERSESSION_TARGET")
                if target.conflict_key != record.conflict_key:
                    raise ValueError("DECISION_REGISTRY_CROSS_KEY_SUPERSESSION")
                source_projects = set(record.applies_to_projects)
                target_projects = set(target.applies_to_projects)
                project_overlap = (
                    "*" in source_projects
                    or "*" in target_projects
                    or bool(source_projects.intersection(target_projects))
                )
                if not project_overlap:
                    raise ValueError("DECISION_REGISTRY_CROSS_PROJECT_SUPERSESSION")
                if target.status != DecisionStatus.superseded:
                    raise ValueError("DECISION_REGISTRY_TARGET_NOT_MARKED_SUPERSEDED")
                if target.effective_at >= record.effective_at:
                    raise ValueError("DECISION_REGISTRY_NON_FORWARD_SUPERSESSION")

    def _validate_superseded_coverage(self, by_id: dict[str, DecisionRecordV1]) -> None:
        referenced = {target for record in self.records for target in record.supersedes}
        for record in self.records:
            if record.status == DecisionStatus.superseded and record.decision_id not in referenced:
                raise ValueError("DECISION_REGISTRY_UNLINKED_SUPERSEDED_DECISION")
            if record.status == DecisionStatus.current and record.decision_id in referenced:
                raise ValueError("DECISION_REGISTRY_CURRENT_DECISION_IS_SUPERSEDED")

    def _validate_no_cycles(self, by_id: dict[str, DecisionRecordV1]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(decision_id: str) -> None:
            if decision_id in visiting:
                raise ValueError("DECISION_REGISTRY_SUPERSESSION_CYCLE")
            if decision_id in visited:
                return
            visiting.add(decision_id)
            for target in by_id[decision_id].supersedes:
                visit(target)
            visiting.remove(decision_id)
            visited.add(decision_id)

        for decision_id in by_id:
            visit(decision_id)

    def get(self, decision_id: str) -> DecisionRecordV1:
        for record in self.records:
            if record.decision_id == decision_id:
                return record
        raise GovernanceError("DECISION_NOT_FOUND")

    def current_for_project(self, project_id: str) -> tuple[DecisionRecordV1, ...]:
        current = [
            record
            for record in self.records
            if record.status == DecisionStatus.current
            and ("*" in record.applies_to_projects or project_id in record.applies_to_projects)
        ]
        return tuple(sorted(current, key=lambda item: (item.conflict_key, item.decision_id)))

    def bind_instruction(
        self,
        *,
        decision_id: str,
        project_id: str,
        instruction_id: str,
        conflict_key: str,
        version: str,
        directive_fingerprint: str,
    ) -> DecisionRecordV1:
        decision = self.get(decision_id)
        projects = set(decision.applies_to_projects)
        if "*" not in projects and project_id not in projects:
            raise GovernanceError("DECISION_PROJECT_BINDING_MISMATCH")
        if decision.status != DecisionStatus.current:
            raise GovernanceError("DECISION_NOT_CURRENT")
        if instruction_id not in decision.instruction_ids:
            raise GovernanceError("DECISION_INSTRUCTION_BINDING_MISMATCH")
        if decision.conflict_key != conflict_key:
            raise GovernanceError("DECISION_CONFLICT_KEY_MISMATCH")
        if decision.version != version:
            raise GovernanceError("DECISION_VERSION_MISMATCH")
        if decision.directive_fingerprint != directive_fingerprint:
            raise GovernanceError("DECISION_DIRECTIVE_FINGERPRINT_MISMATCH")
        return decision


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_decision_registry_snapshot(
    *,
    source_revision: str,
    authority_reference: str,
    records: tuple[DecisionRecordV1, ...],
    imported_at: datetime | None = None,
) -> DecisionSupersessionRegistryV1:
    payload = {
        "registry_id": "PALWAKF_DECISION_SUPERSESSION_REGISTRY_V1",
        "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "records": [record.model_dump(mode="json") for record in records],
        "canonical_promotion_allowed": False,
    }
    return DecisionSupersessionRegistryV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        imported_at=imported_at or datetime.now(UTC),
        records=records,
        registry_sha256=_sha256(payload),
    )


class DecisionSupersessionRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def current(self) -> DecisionSupersessionRegistryV1:
        history = self.history()
        if not history:
            raise GovernanceError("DECISION_REGISTRY_NOT_IMPORTED")
        return history[-1]

    def history(self) -> tuple[DecisionSupersessionRegistryV1, ...]:
        state = self._state_store.load()
        raw = state.get(REGISTRY_STATE_KEY, {})
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else []
        return tuple(DecisionSupersessionRegistryV1.model_validate(item) for item in snapshots)

    def import_snapshot(
        self,
        *,
        source_revision: str,
        authority_reference: str,
        records: tuple[DecisionRecordV1, ...],
    ) -> DecisionSupersessionRegistryV1:
        snapshot = build_decision_registry_snapshot(
            source_revision=source_revision,
            authority_reference=authority_reference,
            records=records,
            imported_at=self._now(),
        )
        history = list(self.history())
        for existing in history:
            if existing.source_revision != source_revision:
                continue
            if existing.registry_sha256 != snapshot.registry_sha256:
                raise GovernanceError("DECISION_REGISTRY_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(snapshot)
        state = self._state_store.load()
        state[REGISTRY_STATE_KEY] = {
            "registry_version": "PALWAKF_DECISION_SUPERSESSION_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_PROJECTION_ONLY",
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return snapshot
