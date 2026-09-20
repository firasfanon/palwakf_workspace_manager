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

REGISTRY_STATE_KEY = "pre_l5_lifecycle_decision_registry_v1"


class LifecycleStage(StrEnum):
    integration_acceptance = "INTEGRATION_ACCEPTANCE"
    main_merge = "MAIN_MERGE"
    baseline_promotion = "BASELINE_PROMOTION"
    deployment_acceptance = "DEPLOYMENT_ACCEPTANCE"
    production_acceptance = "PRODUCTION_ACCEPTANCE"


class LifecycleDisposition(StrEnum):
    approved = "APPROVED"
    rejected = "REJECTED"
    revoked = "REVOKED"


class LifecycleRecordStatus(StrEnum):
    current = "CURRENT"
    historical = "HISTORICAL"


class LifecycleDecisionRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=3, max_length=128)
    stage: LifecycleStage
    subject_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    disposition: LifecycleDisposition
    status: LifecycleRecordStatus = LifecycleRecordStatus.current
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    decided_at: datetime
    decided_by: str = Field(min_length=1, max_length=200)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("LIFECYCLE_DECISION_EVIDENCE_REQUIRED")
        return self


class LifecycleDecisionRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_LIFECYCLE_DECISION_REGISTRY_V1"] = (
        "PALWAKF_LIFECYCLE_DECISION_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    imported_at: datetime
    records: tuple[LifecycleDecisionRecordV1, ...] = Field(min_length=1)
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        if len({item.decision_id for item in self.records}) != len(self.records):
            raise ValueError("LIFECYCLE_DECISION_DUPLICATE_ID")
        if any(item.source_revision != self.source_revision for item in self.records):
            raise ValueError("LIFECYCLE_DECISION_SOURCE_REVISION_MISMATCH")
        if any(item.authority_reference != self.authority_reference for item in self.records):
            raise ValueError("LIFECYCLE_DECISION_AUTHORITY_REFERENCE_MISMATCH")
        self._validate_current_uniqueness()
        return self

    def _validate_current_uniqueness(self) -> None:
        seen: set[tuple[str, LifecycleStage, str]] = set()
        for item in self.records:
            if item.status != LifecycleRecordStatus.current:
                continue
            key = (item.project_id, item.stage, item.subject_sha)
            if key in seen:
                raise ValueError("LIFECYCLE_DECISION_MULTIPLE_CURRENT")
            seen.add(key)

    def current_for(
        self,
        *,
        project_id: str,
        stage: LifecycleStage,
        subject_sha: str,
    ) -> LifecycleDecisionRecordV1:
        for item in self.records:
            if (
                item.project_id == project_id
                and item.stage == stage
                and item.subject_sha == subject_sha.lower()
                and item.status == LifecycleRecordStatus.current
            ):
                return item
        raise GovernanceError("LIFECYCLE_DECISION_MISSING")

    def require_approved(
        self,
        *,
        project_id: str,
        stage: LifecycleStage,
        subject_sha: str,
    ) -> LifecycleDecisionRecordV1:
        decision = self.current_for(
            project_id=project_id,
            stage=stage,
            subject_sha=subject_sha,
        )
        if decision.disposition != LifecycleDisposition.approved:
            raise GovernanceError("LIFECYCLE_DECISION_NOT_APPROVED")
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


def _registry_payload(
    *,
    source_revision: str,
    authority_reference: str,
    records: tuple[LifecycleDecisionRecordV1, ...],
) -> dict[str, object]:
    return {
        "registry_id": "PALWAKF_LIFECYCLE_DECISION_REGISTRY_V1",
        "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "records": [item.model_dump(mode="json") for item in records],
        "canonical_promotion_allowed": False,
    }


def build_lifecycle_decision_registry(
    *,
    source_revision: str,
    authority_reference: str,
    records: tuple[LifecycleDecisionRecordV1, ...],
    imported_at: datetime | None = None,
) -> LifecycleDecisionRegistryV1:
    payload = _registry_payload(
        source_revision=source_revision,
        authority_reference=authority_reference,
        records=records,
    )
    return LifecycleDecisionRegistryV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        imported_at=imported_at or datetime.now(UTC),
        records=records,
        registry_sha256=_sha256(payload),
    )


def _expected_registry_sha256(registry: LifecycleDecisionRegistryV1) -> str:
    return _sha256(
        _registry_payload(
            source_revision=registry.source_revision,
            authority_reference=registry.authority_reference,
            records=registry.records,
        )
    )


def _validate_registry_integrity(registry: LifecycleDecisionRegistryV1) -> None:
    if registry.registry_sha256 != _expected_registry_sha256(registry):
        raise GovernanceError("LIFECYCLE_DECISION_REGISTRY_HASH_MISMATCH")


class LifecycleDecisionRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def history(self) -> tuple[LifecycleDecisionRegistryV1, ...]:
        state = self._state_store.load()
        raw = state.get(REGISTRY_STATE_KEY, {})
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else []
        result = tuple(LifecycleDecisionRegistryV1.model_validate(item) for item in snapshots)
        for item in result:
            _validate_registry_integrity(item)
        return result

    def current(self) -> LifecycleDecisionRegistryV1:
        history = self.history()
        if not history:
            raise GovernanceError("LIFECYCLE_DECISION_REGISTRY_NOT_IMPORTED")
        return history[-1]

    def import_snapshot(
        self,
        *,
        source_revision: str,
        authority_reference: str,
        records: tuple[LifecycleDecisionRecordV1, ...],
    ) -> LifecycleDecisionRegistryV1:
        snapshot = build_lifecycle_decision_registry(
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
                raise GovernanceError("LIFECYCLE_DECISION_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(snapshot)
        state = self._state_store.load()
        state[REGISTRY_STATE_KEY] = {
            "registry_version": "PALWAKF_LIFECYCLE_DECISION_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_PROJECTION_ONLY",
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return snapshot
