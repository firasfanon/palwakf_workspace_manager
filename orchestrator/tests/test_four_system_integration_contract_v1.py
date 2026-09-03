from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.engineering_os_contracts import ActorType, DependencyMode, EngineeringTaskRecord
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_contracts import ExecutionRunOperationalView
from palwakf_orchestrator.intersystem_contracts import build_workspace_authority_package
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord
from palwakf_orchestrator.state_rollup_policy import evaluate_state_rollup

BASE = "1" * 40
WIP = "2" * 40


def _view(*, mutation_class="read-only", sandbox="read-only", expected_head=WIP):
    now = datetime.now(UTC)
    parent = EngineeringTaskRecord(
        task_id="FOUR_SYSTEM_READ_ONLY_INTEGRATION_PILOT_V1",
        project_id="PALWAKF_LOCAL_AGENTS",
        title="Four system read-only pilot",
        description="Governed self integration diagnostic",
        repository="firasfanon/palwakf_agenticAi_system",
        base_sha=BASE,
        integrated_head_at_creation=BASE,
        task_branch="task/FOUR_SYSTEM_READ_ONLY_INTEGRATION_PILOT_V1",
        latest_remote_task_sha=WIP,
        owner_id="workspace",
        actor_id="human",
        actor_type=ActorType.human,
        scope_patterns=["backend/**"],
        depends_on=[],
        dependency_mode=DependencyMode.independent,
        risk_class="LOW",
        mutation_class=mutation_class,
        required_capabilities=["READ_ONLY_DIAGNOSTIC"],
        required_tests=["AGENTIC_CONTRACT"],
        created_at=now,
        updated_at=now,
    )
    run = OperatorTaskRecord(
        task_id="FOUR_SYSTEM_PILOT_RUN_001",
        project_id=parent.project_id,
        repository=parent.repository,
        branch=parent.task_branch,
        expected_head=expected_head,
        authority_reference="AUTHORITY:FOUR_SYSTEM_READ_ONLY_INTEGRATION_PILOT_V1",
        prompt="Perform a governed read-only diagnostic.",
        constraints=["NO_MUTATION"],
        approval_policy="on-request",
        sandbox=sandbox,
        max_turns=4,
        timeout_seconds=300,
        idempotency_key="four-system-pilot-001",
        requires_explicit_authorization=True,
        scope_patterns=parent.scope_patterns,
        created_at=now,
        updated_at=now,
        last_event="created",
    )
    rollup = evaluate_state_rollup(parent, run)
    return ExecutionRunOperationalView(
        execution_run_id=run.task_id,
        legacy_operator_task_id=run.task_id,
        parent_engineering_task_id=parent.task_id,
        parent_task=parent,
        operator_task=run,
        rollup=rollup,
    )


def test_authority_package_preserves_base_and_remote_wip_head():
    package = build_workspace_authority_package(_view())
    assert package.base_sha == BASE
    assert package.expected_head == WIP
    assert package.read_only is True
    assert package.allow_network_write is False
    assert package.objective == "Perform a governed read-only diagnostic."
    assert package.constraints == ["NO_MUTATION"]


def test_authority_package_fails_closed_for_write_parent():
    with pytest.raises(GovernanceError, match="INTERSYSTEM_PILOT_REQUIRES_READ_ONLY_PARENT"):
        build_workspace_authority_package(_view(mutation_class="source-write"))


def test_authority_package_fails_closed_for_head_drift():
    with pytest.raises(GovernanceError, match="INTERSYSTEM_PILOT_EXPECTED_HEAD_DRIFT"):
        build_workspace_authority_package(_view(expected_head="3" * 40))
