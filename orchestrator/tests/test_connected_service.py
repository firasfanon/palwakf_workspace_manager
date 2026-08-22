from pathlib import Path

import pytest

from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import (
    ClientPrincipal,
    ConnectedDispatchRequest,
    ContinueTaskRequest,
    ServiceScope,
)
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.mcp_server import create_mcp_server
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskStatus,
    TaskCapabilityRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore
from tests.test_service import FULL_HEAD, build_service


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def task_request(task_id: str = "CONNECTED_SERVICE_TEST") -> CreateOperatorTaskRequest:
    return CreateOperatorTaskRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository="firasfanon/palwakf_workspace_manager",
        branch="agent/workspace-manager-foundation-v1",
        expected_head=FULL_HEAD,
        authority_reference="AUTHORITY://CONNECTED_SERVICE_V1",
        prompt="Inspect the governed workspace and return one read-only result.",
        constraints=["NO_PRODUCTION", "NO_DATABASE_WRITE"],
        sandbox="read-only",
        max_turns=1,
        timeout_seconds=60,
        idempotency_key=f"connected-{task_id.lower()}",
    )


def tool_plan(task_id: str = "CONNECTED_SERVICE_TEST") -> TaskCapabilityRequest:
    return TaskCapabilityRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        task_type="read-only-probe",
        mutation_class="read-only",
        environment="local",
        data_classification="internal",
        acceptance_requirements=["thread reference", "final response"],
    )


def principal() -> ClientPrincipal:
    return ClientPrincipal(
        client_id="connected-test",
        scopes=frozenset(ServiceScope),
    )


@pytest.mark.asyncio
async def test_bounded_dispatch_persists_host_and_replays_idempotently(
    tmp_path: Path,
) -> None:
    settings = Settings(
        workspace_root=tmp_path,
        execution_host_id="host-test",
        tool_executor_id="codex-test",
        queue_capacity=2,
        worker_count=1,
    )
    store = MemoryStateStore()
    operator = OperatorService(
        tmp_path,
        orchestrator=build_service(tmp_path),
        verifier=AcceptingVerifier(),
        automatic_agents_available=True,
        state_store=store,
    )
    connected = ConnectedApplicationService(
        settings,
        operator,
        store,
        authentication_configured=True,
    )
    command = ConnectedDispatchRequest(task=task_request(), tool_plan=tool_plan())

    await connected.start()
    first = await connected.dispatch(command, principal(), transport="http")
    await connected.wait_until_idle()
    completed = connected.status(first.task.task_id, principal(), transport="http")
    replay = await connected.dispatch(command, principal(), transport="mcp")
    await connected.stop()

    assert first.task.status == OperatorTaskStatus.queued
    assert completed.task.status == OperatorTaskStatus.pending_verification
    assert completed.task.thread_id == "thread-test"
    assert completed.task.execution_host_id == "host-test"
    assert completed.task.tool_executor_id == "codex-test"
    assert replay.task.execution_receipt == completed.task.execution_receipt


@pytest.mark.asyncio
async def test_cross_host_continue_is_rejected(tmp_path: Path) -> None:
    settings = Settings(
        workspace_root=tmp_path,
        execution_host_id="host-current",
        tool_executor_id="codex-current",
    )
    store = MemoryStateStore()
    operator = OperatorService(tmp_path, verifier=AcceptingVerifier(), state_store=store)
    task = operator.create_task(
        task_request().model_copy(update={"automatic_failure_code": "CHANNEL_UNAVAILABLE"})
    )
    operator.plan_tools(task.task_id, tool_plan())
    operator.fail_task(task.task_id, "CHANNEL_UNAVAILABLE")
    connected = ConnectedApplicationService(
        settings,
        operator,
        store,
        authentication_configured=True,
    )

    with pytest.raises(GovernanceError, match="cross-host"):
        await connected.continue_task(
            task.task_id,
            ContinueTaskRequest(
                execution_host_id="host-other",
                tool_executor_id="codex-current",
            ),
            principal(),
            transport="http",
        )


def test_sqlite_restart_restores_task_and_enforces_single_writer(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    first = OperatorService(tmp_path, verifier=AcceptingVerifier(), state_store=store)
    task = first.create_task(task_request())
    first.bind_client(
        task.task_id,
        client_id="client-a",
        correlation_id="corr-a",
        execution_host_id="host-a",
        tool_executor_id="codex-a",
    )

    restarted = OperatorService(tmp_path, verifier=AcceptingVerifier(), state_store=store)

    assert restarted.get_task(task.task_id).execution_host_id == "host-a"
    assert store.acquire_repository_writer(task.repository, task.task_id, "host-a")
    assert not store.acquire_repository_writer(task.repository, "OTHER_TASK", "host-b")
    store.release_repository_writer(task.repository, task.task_id)
    assert store.acquire_repository_writer(task.repository, "OTHER_TASK", "host-b")


@pytest.mark.asyncio
async def test_mcp_exposes_http_parity_tool_set_without_unscoped_tools(
    tmp_path: Path,
) -> None:
    settings = Settings(workspace_root=tmp_path)
    store = MemoryStateStore()
    operator = OperatorService(tmp_path, verifier=AcceptingVerifier(), state_store=store)
    connected = ConnectedApplicationService(
        settings,
        operator,
        store,
        authentication_configured=True,
    )
    registry = AuthRegistry.for_testing("mcp-client", "mcp-test-token")

    server = create_mcp_server(connected, registry)

    assert {tool.name for tool in await server.list_tools()} == {
        "dispatch_codex_task",
        "continue_codex_task",
        "get_codex_task_status",
        "cancel_codex_task",
        "verify_codex_result",
        "list_recent_tasks",
    }


def test_tool_health_never_invents_balance_or_expiry(tmp_path: Path) -> None:
    settings = Settings(workspace_root=tmp_path)
    store = MemoryStateStore()
    connected = ConnectedApplicationService(
        settings,
        OperatorService(tmp_path, verifier=AcceptingVerifier(), state_store=store),
        store,
        authentication_configured=True,
    )

    codex = connected.tool_health.get("codex")

    assert codex.authentication.value == "SET"
    assert codex.quota.value == "AVAILABLE"
    assert codex.balance.value is None
    assert codex.credit_expiry.value is None
    assert codex.balance.provenance == "NOT_EXPOSED_BY_PROVIDER"
