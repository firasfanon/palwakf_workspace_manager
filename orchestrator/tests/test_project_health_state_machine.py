from __future__ import annotations

from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_contracts import ProjectIntakeRequest
from palwakf_orchestrator.project_health import (
    ProjectHealthState,
    ProjectHealthStateMachine,
    ProjectHealthTransitionRequest,
)
from palwakf_orchestrator.project_service import ExternalProjectService

NOW = datetime(2026, 9, 16, 1, 30, tzinfo=UTC)


def build_machine() -> tuple[ProjectHealthStateMachine, str]:
    store = MemoryStateStore()
    projects = ExternalProjectService({}, store, now=lambda: NOW)
    project = projects.intake(
        ProjectIntakeRequest(
            repository_full_name="firasfanon/palwakf_workspace_manager",
            display_name="Workspace Manager",
        )
    )
    return ProjectHealthStateMachine(projects, store, now=lambda: NOW), project.project_id


def transition(
    machine: ProjectHealthStateMachine,
    project_id: str,
    expected: ProjectHealthState,
    target: ProjectHealthState,
    *,
    authority: str | None,
) -> object:
    return machine.transition(
        project_id,
        ProjectHealthTransitionRequest(
            expected_state=expected,
            target_state=target,
            reason=f"transition {expected} to {target}",
            evidence=["EVIDENCE://PREL5-005/TEST"],
            authority_reference=authority,
        ),
    )


def test_initial_state_is_machine_readable_and_unassessed() -> None:
    machine, project_id = build_machine()

    record = machine.get(project_id)

    assert record.record_version == "PROJECT_HEALTH_STATE_V1"
    assert record.state == ProjectHealthState.unassessed
    assert record.sequence == 0
    assert record.transitions == []


def test_trust_raising_transition_requires_authority() -> None:
    machine, project_id = build_machine()

    with pytest.raises(GovernanceError, match="PROJECT_HEALTH_AUTHORITY_REQUIRED"):
        transition(
            machine,
            project_id,
            ProjectHealthState.unassessed,
            ProjectHealthState.reconciling,
            authority=None,
        )


def test_invalid_direct_transition_fails_closed() -> None:
    machine, project_id = build_machine()

    with pytest.raises(GovernanceError, match="PROJECT_HEALTH_TRANSITION_NOT_ALLOWED"):
        transition(
            machine,
            project_id,
            ProjectHealthState.unassessed,
            ProjectHealthState.healthy,
            authority="AUTHORITY://PREL5-005",
        )


def test_valid_reconciliation_to_healthy_persists_evidence_and_authority() -> None:
    machine, project_id = build_machine()

    reconciling = transition(
        machine,
        project_id,
        ProjectHealthState.unassessed,
        ProjectHealthState.reconciling,
        authority="AUTHORITY://PREL5-BATCH",
    )
    healthy = transition(
        machine,
        project_id,
        ProjectHealthState.reconciling,
        ProjectHealthState.healthy,
        authority="AUTHORITY://PREL5-BATCH",
    )

    assert reconciling.sequence == 1
    assert healthy.state == ProjectHealthState.healthy
    assert healthy.sequence == 2
    assert healthy.last_evidence == ["EVIDENCE://PREL5-005/TEST"]
    assert healthy.last_authority_reference == "AUTHORITY://PREL5-BATCH"
    assert [item.transition_id for item in healthy.transitions] == ["PH-0001", "PH-0002"]


def test_expected_state_prevents_stale_transition() -> None:
    machine, project_id = build_machine()
    transition(
        machine,
        project_id,
        ProjectHealthState.unassessed,
        ProjectHealthState.blocked,
        authority=None,
    )

    with pytest.raises(GovernanceError, match="PROJECT_HEALTH_EXPECTED_STATE_MISMATCH"):
        transition(
            machine,
            project_id,
            ProjectHealthState.unassessed,
            ProjectHealthState.reconciling,
            authority="AUTHORITY://STALE",
        )


def test_blocked_project_cannot_skip_reconciliation() -> None:
    machine, project_id = build_machine()
    blocked = transition(
        machine,
        project_id,
        ProjectHealthState.unassessed,
        ProjectHealthState.blocked,
        authority=None,
    )
    assert blocked.state == ProjectHealthState.blocked

    with pytest.raises(GovernanceError, match="PROJECT_HEALTH_TRANSITION_NOT_ALLOWED"):
        transition(
            machine,
            project_id,
            ProjectHealthState.blocked,
            ProjectHealthState.healthy,
            authority="AUTHORITY://PREL5-BATCH",
        )
