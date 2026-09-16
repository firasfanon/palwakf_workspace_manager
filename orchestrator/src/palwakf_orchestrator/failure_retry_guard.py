from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

STATE_KEY = "pre_l5_failure_retry_guard_v1"


class RetryDisposition(StrEnum):
    allow_no_prior_failure = "ALLOW_NO_PRIOR_FAILURE"
    allow_state_changed = "ALLOW_STATE_CHANGED"
    allow_governed_override = "ALLOW_GOVERNED_OVERRIDE"
    block_same_failure_same_state = "BLOCK_SAME_FAILURE_SAME_STATE"


class KnownFailureFingerprintV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fingerprint_id: str = Field(min_length=1, max_length=200)
    lesson_id: str = Field(min_length=1, max_length=200)
    preventive_gate_id: str = Field(min_length=1, max_length=200)
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)
    applies_to_projects: tuple[str, ...] = ("*",)
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"

    @model_validator(mode="after")
    def validate_bindings(self) -> KnownFailureFingerprintV1:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("FAILURE_FINGERPRINT_EVIDENCE_REQUIRED")
        if any(not item.strip() for item in self.applies_to_projects):
            raise ValueError("FAILURE_FINGERPRINT_PROJECT_BINDING_REQUIRED")
        return self


class KnownFailureFingerprintRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_KNOWN_FAILURE_FINGERPRINT_REGISTRY_V1"] = (
        "PALWAKF_KNOWN_FAILURE_FINGERPRINT_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    imported_at: datetime
    records: tuple[KnownFailureFingerprintV1, ...] = Field(min_length=1)
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_registry(self) -> KnownFailureFingerprintRegistryV1:
        ids = [record.fingerprint_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("FAILURE_FINGERPRINT_REGISTRY_DUPLICATE_ID")
        if any(record.source_revision != self.source_revision for record in self.records):
            raise ValueError("FAILURE_FINGERPRINT_SOURCE_REVISION_MISMATCH")
        if any(record.authority_reference != self.authority_reference for record in self.records):
            raise ValueError("FAILURE_FINGERPRINT_AUTHORITY_MISMATCH")
        payload = {
            "registry_id": self.registry_id,
            "source_revision": self.source_revision,
            "authority_reference": self.authority_reference,
            "records": [record.model_dump(mode="json") for record in self.records],
            "canonical_promotion_allowed": False,
        }
        if self.registry_sha256 != _sha256(payload):
            raise ValueError("FAILURE_FINGERPRINT_REGISTRY_HASH_MISMATCH")
        return self

    def get(self, fingerprint_id: str) -> KnownFailureFingerprintV1:
        for record in self.records:
            if record.fingerprint_id == fingerprint_id:
                return record
        raise GovernanceError("KNOWN_FAILURE_FINGERPRINT_NOT_FOUND")


class FailureObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str = Field(min_length=1, max_length=200)
    fingerprint_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    execution_run_id: str | None = Field(default=None, max_length=200)
    state_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_evidence(self) -> FailureObservationV1:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("FAILURE_OBSERVATION_EVIDENCE_REQUIRED")
        return self


class RetryGuardDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint_id: str
    project_id: str
    task_id: str
    state_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: RetryDisposition
    allowed: bool
    prior_observation_id: str | None = None
    override_reference: str | None = None
    evaluated_at: datetime


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


def build_state_fingerprint(state: object) -> str:
    return _sha256(state)


def build_failure_registry_snapshot(
    *,
    source_revision: str,
    authority_reference: str,
    records: tuple[KnownFailureFingerprintV1, ...],
    imported_at: datetime | None = None,
) -> KnownFailureFingerprintRegistryV1:
    payload = {
        "registry_id": "PALWAKF_KNOWN_FAILURE_FINGERPRINT_REGISTRY_V1",
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "records": [record.model_dump(mode="json") for record in records],
        "canonical_promotion_allowed": False,
    }
    return KnownFailureFingerprintRegistryV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        imported_at=imported_at or datetime.now(UTC),
        records=records,
        registry_sha256=_sha256(payload),
    )


class FailureRetryGuardStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def _bucket(self) -> dict[str, object]:
        state = self._state_store.load()
        raw = state.get(STATE_KEY, {})
        return dict(raw) if isinstance(raw, dict) else {}

    def _save_bucket(self, bucket: dict[str, object]) -> None:
        state = self._state_store.load()
        state[STATE_KEY] = bucket
        self._state_store.save(state)

    def history(self) -> tuple[KnownFailureFingerprintRegistryV1, ...]:
        raw = self._bucket().get("registry_snapshots", [])
        if not isinstance(raw, list):
            return ()
        return tuple(KnownFailureFingerprintRegistryV1.model_validate(item) for item in raw)

    def current_registry(self) -> KnownFailureFingerprintRegistryV1:
        history = self.history()
        if not history:
            raise GovernanceError("KNOWN_FAILURE_REGISTRY_NOT_IMPORTED")
        return history[-1]

    def has_fingerprint(self, fingerprint_id: str, project_id: str) -> bool:
        history = self.history()
        if not history:
            return False
        for record in history[-1].records:
            if record.fingerprint_id != fingerprint_id:
                continue
            projects = set(record.applies_to_projects)
            return "*" in projects or project_id in projects
        return False

    def import_registry(
        self,
        *,
        source_revision: str,
        authority_reference: str,
        records: tuple[KnownFailureFingerprintV1, ...],
    ) -> KnownFailureFingerprintRegistryV1:
        snapshot = build_failure_registry_snapshot(
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
                raise GovernanceError("KNOWN_FAILURE_REGISTRY_REVISION_CONFLICT")
            return existing
        history.append(snapshot)
        bucket = self._bucket()
        bucket["source_of_truth"] = "WORKSPACE_DRIVE_SOVEREIGN"
        bucket["runtime_role"] = "GOVERNED_PROJECTION_AND_RECEIPT"
        bucket["canonical_promotion_allowed"] = False
        bucket["registry_snapshots"] = [item.model_dump(mode="json") for item in history]
        bucket.setdefault("observations", [])
        bucket.setdefault("retry_decisions", [])
        self._save_bucket(bucket)
        return snapshot

    def observations(self) -> tuple[FailureObservationV1, ...]:
        raw = self._bucket().get("observations", [])
        if not isinstance(raw, list):
            return ()
        return tuple(FailureObservationV1.model_validate(item) for item in raw)

    def retry_decisions(self) -> tuple[RetryGuardDecisionV1, ...]:
        raw = self._bucket().get("retry_decisions", [])
        if not isinstance(raw, list):
            return ()
        return tuple(RetryGuardDecisionV1.model_validate(item) for item in raw)

    def _fingerprint_for_project(
        self, fingerprint_id: str, project_id: str
    ) -> KnownFailureFingerprintV1:
        record = self.current_registry().get(fingerprint_id)
        projects = set(record.applies_to_projects)
        if "*" not in projects and project_id not in projects:
            raise GovernanceError("KNOWN_FAILURE_FINGERPRINT_PROJECT_MISMATCH")
        return record

    def record_failure(
        self,
        *,
        observation_id: str,
        fingerprint_id: str,
        project_id: str,
        task_id: str,
        state_fingerprint: str,
        evidence: tuple[str, ...],
        execution_run_id: str | None = None,
    ) -> FailureObservationV1:
        self._fingerprint_for_project(fingerprint_id, project_id)
        existing = {item.observation_id: item for item in self.observations()}
        current = existing.get(observation_id)
        if current is not None:
            replay = (
                current.fingerprint_id == fingerprint_id
                and current.project_id == project_id
                and current.task_id == task_id
                and current.execution_run_id == execution_run_id
                and current.state_fingerprint == state_fingerprint
                and current.evidence == evidence
            )
            if not replay:
                raise GovernanceError("FAILURE_OBSERVATION_ID_CONFLICT")
            return current

        observation = FailureObservationV1(
            observation_id=observation_id,
            fingerprint_id=fingerprint_id,
            project_id=project_id,
            task_id=task_id,
            execution_run_id=execution_run_id,
            state_fingerprint=state_fingerprint,
            observed_at=self._now(),
            evidence=evidence,
        )
        bucket = self._bucket()
        raw_observations = bucket.get("observations", [])
        if not isinstance(raw_observations, list):
            raise GovernanceError("FAILURE_OBSERVATION_STORE_CORRUPT")
        observations = list(raw_observations)
        observations.append(observation.model_dump(mode="json"))
        bucket["observations"] = observations
        self._save_bucket(bucket)
        return observation

    def _latest_relevant_observation(
        self,
        *,
        fingerprint_id: str,
        project_id: str,
    ) -> FailureObservationV1 | None:
        matches = [
            item
            for item in self.observations()
            if item.fingerprint_id == fingerprint_id and item.project_id == project_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: (item.observed_at, item.observation_id))

    def _persist_decision(
        self,
        decision: RetryGuardDecisionV1,
    ) -> RetryGuardDecisionV1:
        existing = {item.decision_id: item for item in self.retry_decisions()}
        current = existing.get(decision.decision_id)
        if current is not None:
            if current != decision:
                raise GovernanceError("RETRY_GUARD_DECISION_ID_CONFLICT")
            return current
        bucket = self._bucket()
        raw_decisions = bucket.get("retry_decisions", [])
        if not isinstance(raw_decisions, list):
            raise GovernanceError("RETRY_DECISION_STORE_CORRUPT")
        decisions = list(raw_decisions)
        decisions.append(decision.model_dump(mode="json"))
        bucket["retry_decisions"] = decisions
        self._save_bucket(bucket)
        return decision

    def evaluate_retry(
        self,
        *,
        fingerprint_id: str,
        project_id: str,
        task_id: str,
        state_fingerprint: str,
        override_reference: str | None = None,
        override_authority_reference: str | None = None,
    ) -> RetryGuardDecisionV1:
        self._fingerprint_for_project(fingerprint_id, project_id)
        prior = self._latest_relevant_observation(
            fingerprint_id=fingerprint_id,
            project_id=project_id,
        )
        if prior is None:
            disposition = RetryDisposition.allow_no_prior_failure
            allowed = True
        elif prior.state_fingerprint != state_fingerprint:
            disposition = RetryDisposition.allow_state_changed
            allowed = True
        elif override_reference is not None:
            registry = self.current_registry()
            if not override_reference.strip():
                raise GovernanceError("RETRY_OVERRIDE_REFERENCE_REQUIRED")
            if not override_authority_reference:
                raise GovernanceError("RETRY_OVERRIDE_AUTHORITY_REQUIRED")
            if override_authority_reference != registry.authority_reference:
                raise GovernanceError("RETRY_OVERRIDE_AUTHORITY_MISMATCH")
            disposition = RetryDisposition.allow_governed_override
            allowed = True
        else:
            disposition = RetryDisposition.block_same_failure_same_state
            allowed = False

        evaluated_at = self._now()
        payload = {
            "fingerprint_id": fingerprint_id,
            "project_id": project_id,
            "task_id": task_id,
            "state_fingerprint": state_fingerprint,
            "disposition": disposition.value,
            "allowed": allowed,
            "prior_observation_id": prior.observation_id if prior else None,
            "override_reference": override_reference,
            "evaluated_at": evaluated_at.isoformat(),
        }
        decision = RetryGuardDecisionV1(
            decision_id=_sha256(payload),
            fingerprint_id=fingerprint_id,
            project_id=project_id,
            task_id=task_id,
            state_fingerprint=state_fingerprint,
            disposition=disposition,
            allowed=allowed,
            prior_observation_id=prior.observation_id if prior else None,
            override_reference=override_reference,
            evaluated_at=evaluated_at,
        )
        return self._persist_decision(decision)

    def require_retry_allowed(
        self,
        *,
        fingerprint_id: str,
        project_id: str,
        task_id: str,
        state_fingerprint: str,
        override_reference: str | None = None,
        override_authority_reference: str | None = None,
    ) -> RetryGuardDecisionV1:
        decision = self.evaluate_retry(
            fingerprint_id=fingerprint_id,
            project_id=project_id,
            task_id=task_id,
            state_fingerprint=state_fingerprint,
            override_reference=override_reference,
            override_authority_reference=override_authority_reference,
        )
        if not decision.allowed:
            raise GovernanceError("BLIND_RETRY_BLOCKED_SAME_FAILURE_SAME_STATE")
        return decision
