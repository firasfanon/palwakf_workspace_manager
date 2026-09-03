from datetime import UTC, datetime

from palwakf_orchestrator.engineering_os_contracts import (
    ActorType,
    DependencyMode,
    EngineeringTaskRecord,
)
from palwakf_orchestrator.execution_run_contracts import ExecutionRunOperationalView
from palwakf_orchestrator.intersystem_contracts import build_workspace_authority_package
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord
from palwakf_orchestrator.state_rollup_policy import evaluate_state_rollup

BASE = "1807b450f17904d17cfbe418ded7d61ee5029b56"
WIP = "19b9c8e9d2c52b955dfb1fd273dfecaa4f8383e6"


def _view(capabilities: list[str]) -> ExecutionRunOperationalView:
    now = datetime.now(UTC)
    parent = EngineeringTaskRecord(
        task_id="FOUR_SYSTEM_READ_ONLY_INTEGRATION_PILOT_V1",
        project_id="PALWAKF_LOCAL_AGENTS",
        title="Provider learning authority test",
        description="Provider learning authority test",
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
        mutation_class="read-only",
        required_capabilities=capabilities,
        required_tests=["PROVIDER_LEARNING_GATE"],
        created_at=now,
        updated_at=now,
    )
    run = OperatorTaskRecord(
        task_id="PROVIDER_LEARNING_RUN_001",
        project_id=parent.project_id,
        repository=parent.repository,
        branch=parent.task_branch,
        expected_head=WIP,
        authority_reference="AUTHORITY:PROVIDER_LEARNING_GATE_V1",
        prompt="Observe local providers and derive learning candidates.",
        constraints=["NO_SOURCE_MUTATION", "NO_NETWORK_WRITE"],
        approval_policy="on-request",
        sandbox="read-only",
        max_turns=4,
        timeout_seconds=300,
        idempotency_key="provider-learning-001",
        requires_explicit_authorization=True,
        scope_patterns=parent.scope_patterns,
        created_at=now,
        updated_at=now,
        last_event="created",
    )
    return ExecutionRunOperationalView(
        execution_run_id=run.task_id,
        legacy_operator_task_id=run.task_id,
        parent_engineering_task_id=parent.task_id,
        parent_task=parent,
        operator_task=run,
        rollup=evaluate_state_rollup(parent, run),
    )


def test_local_provider_network_read_requires_explicit_capability():
    package = build_workspace_authority_package(_view(["READ_ONLY_DIAGNOSTIC"]))
    assert package.allow_network_read is False
    assert package.allow_network_write is False


def test_local_provider_network_read_is_enabled_by_governed_capability():
    package = build_workspace_authority_package(
        _view(
            [
                "READ_ONLY_DIAGNOSTIC",
                "LOCAL_PROVIDER_NETWORK_READ",
                "OLLAMA_PROVIDER_LEARNING",
                "HERMES_PROVIDER_LEARNING",
            ]
        )
    )
    assert package.allow_network_read is True
    assert package.allow_network_write is False
