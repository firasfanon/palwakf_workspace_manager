from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.evidence_acceptance_engine import AcceptanceDecisionV1
from palwakf_orchestrator.failure_retry_guard import FailureRetryGuardStore
from palwakf_orchestrator.persistence import StateStore

STATE_KEY = "pre_l5_incident_failure_learning_v1"


class IncidentStatus(StrEnum):
    open = "OPEN"
    root_cause_classified = "ROOT_CAUSE_CLASSIFIED"
    learning_bound = "LEARNING_BOUND"
    prevention_verified = "PREVENTION_VERIFIED"
    closed = "CLOSED"


class IncidentRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    incident_id: str = Field(min_length=3, max_length=200)
    observation_id: str = Field(min_length=1, max_length=200)
    fingerprint_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    failure_state_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: IncidentStatus
    opened_at: datetime
    root_cause_code: str | None = Field(default=None, max_length=300)
    lesson_id: str | None = Field(default=None, max_length=200)
    preventive_gate_id: str | None = Field(default=None, max_length=200)
    acceptance_decision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence: tuple[str, ...] = Field(min_length=1, max_length=128)
    closed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_state(self) -> IncidentRecordV1:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("INCIDENT_EVIDENCE_REQUIRED")
        if self.status in {
            IncidentStatus.root_cause_classified,
            IncidentStatus.learning_bound,
            IncidentStatus.prevention_verified,
            IncidentStatus.closed,
        } and not self.root_cause_code:
            raise ValueError("INCIDENT_ROOT_CAUSE_REQUIRED")
        if self.status in {
            IncidentStatus.learning_bound,
            IncidentStatus.prevention_verified,
            IncidentStatus.closed,
        } and (not self.lesson_id or not self.preventive_gate_id):
            raise ValueError("INCIDENT_LEARNING_BINDING_REQUIRED")
        if (
            self.status in {IncidentStatus.prevention_verified, IncidentStatus.closed}
            and not self.acceptance_decision_id
        ):
            raise ValueError("INCIDENT_PREVENTION_ACCEPTANCE_REQUIRED")
        if self.status == IncidentStatus.closed and self.closed_at is None:
            raise ValueError("INCIDENT_CLOSED_AT_REQUIRED")
        return self


class LearningCandidateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    incident_id: str
    project_id: str
    fingerprint_id: str
    lesson_id: str
    preventive_gate_id: str
    evidence: tuple[str, ...] = Field(min_length=1, max_length=128)
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    canonical_promotion_allowed: Literal[False] = False


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _merge_evidence(existing: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    merged = tuple(dict.fromkeys((*existing, *additions)))
    if any(not item.strip() for item in merged):
        raise GovernanceError("INCIDENT_EVIDENCE_REQUIRED")
    return merged


class IncidentFailureLearningStore:
    def __init__(
        self,
        state_store: StateStore,
        failure_store: FailureRetryGuardStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._failure_store = failure_store
        self._now = now or (lambda: datetime.now(UTC))

    def _bucket(self) -> dict[str, object]:
        state = self._state_store.load()
        raw = state.get(STATE_KEY, {})
        return dict(raw) if isinstance(raw, dict) else {}

    def _save_bucket(self, bucket: dict[str, object]) -> None:
        state = self._state_store.load()
        state[STATE_KEY] = bucket
        self._state_store.save(state)
    def incidents(self) -> tuple[IncidentRecordV1, ...]:
        raw = self._bucket().get("incidents", [])
        if not isinstance(raw, list):
            raise GovernanceError("INCIDENT_STORE_CORRUPT")
        return tuple(IncidentRecordV1.model_validate(item) for item in raw)

    def learning_candidates(self) -> tuple[LearningCandidateV1, ...]:
        raw = self._bucket().get("learning_candidates", [])
        if not isinstance(raw, list):
            raise GovernanceError("LEARNING_CANDIDATE_STORE_CORRUPT")
        return tuple(LearningCandidateV1.model_validate(item) for item in raw)

    def get(self, incident_id: str) -> IncidentRecordV1:
        for incident in self.incidents():
            if incident.incident_id == incident_id:
                return incident
        raise GovernanceError("INCIDENT_NOT_FOUND")

    def _replace(self, updated: IncidentRecordV1) -> IncidentRecordV1:
        items = list(self.incidents())
        replaced = False
        for index, current in enumerate(items):
            if current.incident_id == updated.incident_id:
                items[index] = updated
                replaced = True
                break
        if not replaced:
            raise GovernanceError("INCIDENT_NOT_FOUND")
        bucket = self._bucket()
        bucket["source_of_truth"] = "WORKSPACE_DRIVE_SOVEREIGN"
        bucket["runtime_role"] = "GOVERNED_LIFECYCLE_AND_LEARNING_CANDIDATE_RECEIPT"
        bucket["canonical_promotion_allowed"] = False
        bucket["incidents"] = [item.model_dump(mode="json") for item in items]
        bucket.setdefault("learning_candidates", [])
        self._save_bucket(bucket)
        return updated

    def open_incident(
        self,
        *,
        incident_id: str,
        observation_id: str,
        evidence: tuple[str, ...],
    ) -> IncidentRecordV1:
        observations = {item.observation_id: item for item in self._failure_store.observations()}
        observation = observations.get(observation_id)
        if observation is None:
            raise GovernanceError("INCIDENT_FAILURE_OBSERVATION_NOT_FOUND")
        existing = {item.incident_id: item for item in self.incidents()}
        current = existing.get(incident_id)
        merged_evidence = _merge_evidence((), evidence)
        if current is not None:
            if (
                current.observation_id == observation_id
                and current.fingerprint_id == observation.fingerprint_id
                and current.project_id == observation.project_id
                and current.task_id == observation.task_id
                and current.failure_state_fingerprint == observation.state_fingerprint
            ):
                return current
            raise GovernanceError("INCIDENT_ID_CONFLICT")
        incident = IncidentRecordV1(
            incident_id=incident_id,
            observation_id=observation.observation_id,
            fingerprint_id=observation.fingerprint_id,
            project_id=observation.project_id,
            task_id=observation.task_id,
            failure_state_fingerprint=observation.state_fingerprint,
            status=IncidentStatus.open,
            opened_at=self._now(),
            evidence=merged_evidence,
        )
        bucket = self._bucket()
        items = list(self.incidents())
        items.append(incident)
        bucket["source_of_truth"] = "WORKSPACE_DRIVE_SOVEREIGN"
        bucket["runtime_role"] = "GOVERNED_LIFECYCLE_AND_LEARNING_CANDIDATE_RECEIPT"
        bucket["canonical_promotion_allowed"] = False
        bucket["incidents"] = [item.model_dump(mode="json") for item in items]
        bucket.setdefault("learning_candidates", [])
        self._save_bucket(bucket)
        return incident

    def classify_root_cause(
        self,
        incident_id: str,
        *,
        root_cause_code: str,
        evidence: tuple[str, ...],
    ) -> IncidentRecordV1:
        incident = self.get(incident_id)
        if incident.status == IncidentStatus.closed:
            raise GovernanceError("INCIDENT_ALREADY_CLOSED")
        root_cause = root_cause_code.strip()
        if not root_cause:
            raise GovernanceError("INCIDENT_ROOT_CAUSE_REQUIRED")
        updated = incident.model_copy(
            update={
                "status": IncidentStatus.root_cause_classified,
                "root_cause_code": root_cause,
                "evidence": _merge_evidence(incident.evidence, evidence),
            }
        )
        return self._replace(updated)

    def bind_learning(
        self,
        incident_id: str,
        *,
        evidence: tuple[str, ...],
    ) -> IncidentRecordV1:
        incident = self.get(incident_id)
        if incident.status != IncidentStatus.root_cause_classified:
            raise GovernanceError("INCIDENT_ROOT_CAUSE_REQUIRED_BEFORE_LEARNING")
        fingerprint = self._failure_store.current_registry().get(incident.fingerprint_id)
        projects = set(fingerprint.applies_to_projects)
        if "*" not in projects and incident.project_id not in projects:
            raise GovernanceError("INCIDENT_FAILURE_FINGERPRINT_PROJECT_MISMATCH")
        updated = incident.model_copy(
            update={
                "status": IncidentStatus.learning_bound,
                "lesson_id": fingerprint.lesson_id,
                "preventive_gate_id": fingerprint.preventive_gate_id,
                "evidence": _merge_evidence(incident.evidence, evidence),
            }
        )
        return self._replace(updated)

    def verify_prevention(
        self,
        incident_id: str,
        *,
        acceptance_decision: AcceptanceDecisionV1,
        evidence: tuple[str, ...],
    ) -> IncidentRecordV1:
        incident = self.get(incident_id)
        if incident.status != IncidentStatus.learning_bound:
            raise GovernanceError("INCIDENT_LEARNING_REQUIRED_BEFORE_PREVENTION")
        if not acceptance_decision.accepted:
            raise GovernanceError("INCIDENT_PREVENTION_ACCEPTANCE_REQUIRED")
        if acceptance_decision.missing_kinds or acceptance_decision.failed_kinds:
            raise GovernanceError("INCIDENT_PREVENTION_ACCEPTANCE_INCOMPLETE")
        decision_id = _sha256(acceptance_decision.model_dump(mode="json"))
        updated = incident.model_copy(
            update={
                "status": IncidentStatus.prevention_verified,
                "acceptance_decision_id": decision_id,
                "evidence": _merge_evidence(
                    incident.evidence,
                    (*evidence, f"acceptance-decision:{decision_id}"),
                ),
            }
        )
        return self._replace(updated)

    def close_incident(
        self,
        incident_id: str,
        *,
        evidence: tuple[str, ...],
    ) -> tuple[IncidentRecordV1, LearningCandidateV1]:
        incident = self.get(incident_id)
        if incident.status != IncidentStatus.prevention_verified:
            raise GovernanceError("INCIDENT_PREVENTION_REQUIRED_BEFORE_CLOSE")
        closed = incident.model_copy(
            update={
                "status": IncidentStatus.closed,
                "closed_at": self._now(),
                "evidence": _merge_evidence(incident.evidence, evidence),
            }
        )
        self._replace(closed)
        candidate = self._learning_candidate(closed)
        bucket = self._bucket()
        existing = list(self.learning_candidates())
        by_incident = {item.incident_id: item for item in existing}
        current = by_incident.get(closed.incident_id)
        if current is not None:
            if current == candidate:
                return closed, current
            raise GovernanceError("LEARNING_CANDIDATE_INCIDENT_CONFLICT")
        existing.append(candidate)
        bucket["learning_candidates"] = [item.model_dump(mode="json") for item in existing]
        self._save_bucket(bucket)
        return closed, candidate

    def _learning_candidate(self, incident: IncidentRecordV1) -> LearningCandidateV1:
        if not incident.lesson_id or not incident.preventive_gate_id:
            raise GovernanceError("INCIDENT_LEARNING_BINDING_REQUIRED")
        payload = {
            "incident_id": incident.incident_id,
            "project_id": incident.project_id,
            "fingerprint_id": incident.fingerprint_id,
            "lesson_id": incident.lesson_id,
            "preventive_gate_id": incident.preventive_gate_id,
            "evidence": incident.evidence,
            "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
            "canonical_promotion_allowed": False,
        }
        return LearningCandidateV1(
            candidate_id=_sha256(payload),
            incident_id=incident.incident_id,
            project_id=incident.project_id,
            fingerprint_id=incident.fingerprint_id,
            lesson_id=incident.lesson_id,
            preventive_gate_id=incident.preventive_gate_id,
            evidence=incident.evidence,
        )
