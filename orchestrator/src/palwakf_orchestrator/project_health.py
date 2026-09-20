from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore, StateStore
from palwakf_orchestrator.project_service import ExternalProjectService


class ProjectHealthState(StrEnum):
    unassessed = "UNASSESSED"
    reconciling = "RECONCILING"
    healthy = "HEALTHY"
    degraded = "DEGRADED"
    blocked = "BLOCKED"


class ProjectHealthTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state: ProjectHealthState
    target_state: ProjectHealthState
    reason: str = Field(min_length=3, max_length=500)
    evidence: list[str] = Field(min_length=1, max_length=32)
    authority_reference: str | None = Field(default=None, min_length=3, max_length=500)


class ProjectHealthTransition(BaseModel):
    transition_id: str
    sequence: int = Field(ge=1)
    from_state: ProjectHealthState
    to_state: ProjectHealthState
    reason: str
    evidence: list[str]
    authority_reference: str | None = None
    transitioned_at: datetime


class ProjectHealthRecord(BaseModel):
    record_version: Literal["PROJECT_HEALTH_STATE_V1"] = "PROJECT_HEALTH_STATE_V1"
    project_id: str
    state: ProjectHealthState = ProjectHealthState.unassessed
    sequence: int = Field(default=0, ge=0)
    last_reason: str | None = None
    last_evidence: list[str] = Field(default_factory=list)
    last_authority_reference: str | None = None
    updated_at: datetime | None = None
    transitions: list[ProjectHealthTransition] = Field(default_factory=list)


class ProjectHealthStateMachine:
    _AUTHORITY_REQUIRED = frozenset({ProjectHealthState.reconciling, ProjectHealthState.healthy})
    _ALLOWED: dict[ProjectHealthState, frozenset[ProjectHealthState]] = {
        ProjectHealthState.unassessed: frozenset(
            {ProjectHealthState.reconciling, ProjectHealthState.blocked}
        ),
        ProjectHealthState.reconciling: frozenset(
            {
                ProjectHealthState.healthy,
                ProjectHealthState.degraded,
                ProjectHealthState.blocked,
            }
        ),
        ProjectHealthState.healthy: frozenset(
            {
                ProjectHealthState.reconciling,
                ProjectHealthState.degraded,
                ProjectHealthState.blocked,
            }
        ),
        ProjectHealthState.degraded: frozenset(
            {ProjectHealthState.reconciling, ProjectHealthState.blocked}
        ),
        ProjectHealthState.blocked: frozenset({ProjectHealthState.reconciling}),
    }

    def __init__(
        self,
        projects: ExternalProjectService,
        state_store: StateStore | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._projects = projects
        self._state_store = state_store or MemoryStateStore()
        self._now = now or (lambda: datetime.now(UTC))

    def get(self, project_id: str) -> ProjectHealthRecord:
        self._projects.get_project(project_id)
        records = self._load()
        return records.get(project_id, ProjectHealthRecord(project_id=project_id))

    def transition(
        self,
        project_id: str,
        command: ProjectHealthTransitionRequest,
    ) -> ProjectHealthRecord:
        self._projects.get_project(project_id)
        records = self._load()
        current = records.get(project_id, ProjectHealthRecord(project_id=project_id))
        if current.state != command.expected_state:
            raise GovernanceError("PROJECT_HEALTH_EXPECTED_STATE_MISMATCH")
        if command.target_state not in self._ALLOWED[current.state]:
            raise GovernanceError("PROJECT_HEALTH_TRANSITION_NOT_ALLOWED")
        evidence = [item.strip() for item in command.evidence if item.strip()]
        if len(evidence) != len(command.evidence):
            raise GovernanceError("PROJECT_HEALTH_EVIDENCE_REQUIRED")
        if command.target_state in self._AUTHORITY_REQUIRED and not command.authority_reference:
            raise GovernanceError("PROJECT_HEALTH_AUTHORITY_REQUIRED")

        sequence = current.sequence + 1
        transitioned_at = self._now()
        transition = ProjectHealthTransition(
            transition_id=f"PH-{sequence:04d}",
            sequence=sequence,
            from_state=current.state,
            to_state=command.target_state,
            reason=command.reason,
            evidence=evidence,
            authority_reference=command.authority_reference,
            transitioned_at=transitioned_at,
        )
        updated = current.model_copy(
            update={
                "state": command.target_state,
                "sequence": sequence,
                "last_reason": command.reason,
                "last_evidence": evidence,
                "last_authority_reference": command.authority_reference,
                "updated_at": transitioned_at,
                "transitions": [*current.transitions, transition],
            }
        )
        records[project_id] = updated
        self._save(records)
        return updated

    def _load(self) -> dict[str, ProjectHealthRecord]:
        state = self._state_store.load()
        raw = state.get("project_health_state_machine", {})
        records = raw.get("records", {}) if isinstance(raw, dict) else {}
        return {key: ProjectHealthRecord.model_validate(value) for key, value in records.items()}

    def _save(self, records: dict[str, ProjectHealthRecord]) -> None:
        state = self._state_store.load()
        state["project_health_state_machine"] = {
            "registry_version": "PROJECT_HEALTH_STATE_REGISTRY_V1",
            "records": {key: value.model_dump(mode="json") for key, value in records.items()},
        }
        self._state_store.save(state)
