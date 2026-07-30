from __future__ import annotations

import asyncio
import json
import secrets
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import ConnectedDispatchRequest
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.contracts import (
    DispatchRequest,
    DispatchResponse,
    RepositoryState,
    SovereigntyBoundaries,
    Transport,
)
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    TaskCapabilityRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore

HEAD = "94c50e0400ee4f843270f7f505119f2a72c78841"


class FakeVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


class FakeExecutor:
    async def dispatch(self, request: DispatchRequest) -> DispatchResponse:
        if request.task_id.endswith("_CANCEL"):
            await asyncio.sleep(2)
        return DispatchResponse(
            task_id=request.task_id,
            status="completed",
            transport=Transport.sdk,
            execution_receipt=f"fake-{request.idempotency_key}",
            idempotency_key=request.idempotency_key,
            idempotency_replayed=False,
            repository_state=RepositoryState(
                repository=request.repository,
                branch=request.branch,
                local_head=HEAD,
                remote_head=HEAD,
                clean=True,
            ),
            plan_summary="Deterministic fake executor acceptance",
            agents_response_id="fake-agents-response",
            codex_thread_id=f"fake-thread-{request.task_id.lower()}",
            final_response="FAKE_EXECUTOR_COMPLETED",
            boundaries=SovereigntyBoundaries(),
        )


def task(task_id: str) -> CreateOperatorTaskRequest:
    return CreateOperatorTaskRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository="firasfanon/palwakf_workspace_manager",
        branch="agent/workspace-manager-foundation-v1",
        expected_head=HEAD,
        authority_reference="AUTHORITY://CONNECTED_SERVICE_SMOKE",
        prompt="Run the deterministic fake executor transport acceptance.",
        constraints=["NO_PRODUCTION", "NO_DATABASE_WRITE"],
        sandbox="read-only",
        max_turns=1,
        timeout_seconds=30,
        idempotency_key=f"connected-smoke-{task_id.lower()}",
    )


def plan(task_id: str) -> TaskCapabilityRequest:
    return TaskCapabilityRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        task_type="transport-smoke",
        mutation_class="read-only",
        environment="local",
        data_classification="internal",
        acceptance_requirements=["receipt", "status", "thread"],
    )


def command(task_id: str) -> dict[str, Any]:
    return ConnectedDispatchRequest(
        task=task(task_id),
        tool_plan=plan(task_id),
    ).model_dump(mode="json")


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def payload(result: Any) -> Any:
    if result.isError:
        raise RuntimeError(result.content[0].text)
    if result.structuredContent is not None:
        value = result.structuredContent
        return value.get("result", value)
    return json.loads(result.content[0].text)


async def wait_for_status(
    session: ClientSession,
    task_id: str,
    accepted: set[str],
) -> dict[str, Any]:
    for _ in range(50):
        result = payload(
            await session.call_tool(
                "get_codex_task_status",
                {"task_id": task_id},
            )
        )
        if result["task"]["status"] in accepted:
            return result
        await asyncio.sleep(0.05)
    raise TimeoutError(f"status timeout for {task_id}")


async def run() -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    registry = AuthRegistry.for_testing("smoke-client", token)
    port = free_port()
    with TemporaryDirectory(prefix="palwakf-connected-smoke-") as temporary:
        settings = Settings(
            workspace_root=Path(temporary),
            execution_host_id="smoke-host",
            tool_executor_id="fake-codex-executor",
            port=port,
            queue_capacity=4,
            worker_count=1,
        )
        store = MemoryStateStore()
        executor = FakeExecutor()
        operator = OperatorService(
            Path(temporary),
            orchestrator=executor,  # type: ignore[arg-type]
            verifier=FakeVerifier(),
            automatic_agents_available=True,
            state_store=store,
        )
        connected = ConnectedApplicationService(
            settings,
            operator,
            store,
            authentication_configured=True,
        )
        app = create_app(
            settings,
            executor,  # type: ignore[arg-type]
            operator,
            state_store=store,
            auth_registry=registry,
            connected_service=connected,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="error",
            )
        )
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            if server_task.done():
                await server_task
            await asyncio.sleep(0.02)

        headers = {"Authorization": f"Bearer {token}"}
        base_url = f"http://127.0.0.1:{port}"
        try:
            async with httpx.AsyncClient(headers=headers, timeout=10) as client:
                ready = await client.get(f"{base_url}/ready")
                async with httpx.AsyncClient(timeout=10) as plain_client:
                    unauthenticated = await plain_client.get(f"{base_url}/health")
                async with streamable_http_client(
                    f"{base_url}/mcp/",
                    http_client=client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()

                        dispatched = payload(
                            await session.call_tool(
                                "dispatch_codex_task",
                                {"request": command("CONNECTED_SMOKE_DISPATCH")},
                            )
                        )
                        completed = await wait_for_status(
                            session,
                            "CONNECTED_SMOKE_DISPATCH",
                            {"pending_verification"},
                        )
                        verified = payload(
                            await session.call_tool(
                                "verify_codex_result",
                                {
                                    "task_id": "CONNECTED_SMOKE_DISPATCH",
                                    "command": {
                                        "request": {
                                            "verification_receipt": "smoke-ci-success",
                                            "ci_status": "success",
                                            "verified_head": HEAD,
                                        },
                                        "execution_host_id": "smoke-host",
                                        "tool_executor_id": "fake-codex-executor",
                                    },
                                },
                            )
                        )

                        continued_task = operator.create_task(task("CONNECTED_SMOKE_CONTINUE"))
                        operator.plan_tools(continued_task.task_id, plan(continued_task.task_id))
                        operator.fail_task(continued_task.task_id, "FAKE_RETRYABLE_FAILURE")
                        continued = payload(
                            await session.call_tool(
                                "continue_codex_task",
                                {
                                    "task_id": continued_task.task_id,
                                    "command": {
                                        "execution_host_id": "smoke-host",
                                        "tool_executor_id": "fake-codex-executor",
                                    },
                                },
                            )
                        )
                        continued_final = await wait_for_status(
                            session,
                            continued_task.task_id,
                            {"pending_verification"},
                        )

                        payload(
                            await session.call_tool(
                                "dispatch_codex_task",
                                {"request": command("CONNECTED_SMOKE_CANCEL")},
                            )
                        )
                        cancelled = payload(
                            await session.call_tool(
                                "cancel_codex_task",
                                {"task_id": "CONNECTED_SMOKE_CANCEL"},
                            )
                        )
                        recent = payload(
                            await session.call_tool("list_recent_tasks", {"limit": 10})
                        )
        finally:
            server.should_exit = True
            await server_task

    return {
        "status": "PASS",
        "http_ready": ready.status_code,
        "unauthenticated_health": unauthenticated.status_code,
        "mcp_dispatch": dispatched["task"]["status"],
        "mcp_status": completed["task"]["status"],
        "mcp_verify": verified["task"]["status"],
        "mcp_continue": continued["task"]["status"],
        "mcp_continue_final": continued_final["task"]["status"],
        "mcp_cancel": cancelled["task"]["status"],
        "mcp_recent_count": len(recent),
        "execution_host_id": completed["task"]["execution_host_id"],
        "tool_executor_id": completed["task"]["tool_executor_id"],
        "secret_printed": False,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), sort_keys=True))
