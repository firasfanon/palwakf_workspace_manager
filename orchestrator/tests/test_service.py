from pathlib import Path

from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import ServiceScope
from palwakf_orchestrator.contracts import (
    DispatchPlan,
    DispatchRequest,
    GatewayResult,
    PlanningResult,
    RepositoryState,
    Transport,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.service import OrchestratorService
from tests.test_contracts import valid_request

FULL_HEAD = "a312d498bf89c509ae04a6c2eaa476de0a7c39bc"
TOKEN = "test-service-token"
AUTHORIZATION = {"Authorization": f"Bearer {TOKEN}"}


class FakeGate:
    def verify_repository(self, request: DispatchRequest) -> RepositoryState:
        return RepositoryState(
            repository=request.repository,
            branch=request.branch,
            local_head=FULL_HEAD,
            remote_head=FULL_HEAD,
            clean=True,
        )

    def verify_plan(self, plan: DispatchPlan) -> None:
        assert plan.requires_workspace_write is False


class FakePlanner:
    calls = 0

    async def plan(
        self,
        request: DispatchRequest,
        repository_state: RepositoryState,
    ) -> PlanningResult:
        self.calls += 1
        return PlanningResult(
            plan=DispatchPlan(
                summary="Read-only inspection",
                executor_prompt=f"Inspect without writes: {request.prompt}",
                requires_workspace_write=False,
            ),
            reasoning_provider_id="fake-reasoning-provider",
            reasoning_response_id="resp-test",
            agents_response_id="resp-test",
        )


class FakeGateway:
    executor_id = "fake-executor"

    async def run(self, prompt: str, workspace: Path) -> GatewayResult:
        assert prompt.startswith("Inspect without writes:")
        return GatewayResult(
            transport=Transport.sdk,
            thread_id="thread-test",
            status="completed",
            final_response="PalWakf Workspace Manager",
        )


def build_service(tmp_path: Path) -> OrchestratorService:
    settings = Settings(workspace_root=tmp_path)
    return OrchestratorService(
        settings,
        gate=FakeGate(),
        planner=FakePlanner(),
        gateways={
            Transport.sdk: FakeGateway(),
            Transport.mcp: FakeGateway(),
        },
    )


def build_app(
    tmp_path: Path,
    *,
    operator: OperatorService | None = None,
    scopes: tuple[ServiceScope, ...] = tuple(ServiceScope),
):
    return create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        operator,
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing("test-client", TOKEN, scopes),
    )


async def test_dispatch_uses_planner_and_selected_gateway(tmp_path: Path) -> None:
    request = DispatchRequest.model_validate(valid_request())

    response = await build_service(tmp_path).dispatch(request)

    assert response.status == "completed"
    assert response.reasoning_provider_id == "fake-reasoning-provider"
    assert response.reasoning_response_id == "resp-test"
    assert response.agents_response_id == "resp-test"
    assert response.executor_id == "fake-executor"
    assert response.executor_thread_id == "thread-test"
    assert response.codex_thread_id == "thread-test"
    assert response.boundaries.production_mutation is False


async def test_duplicate_idempotency_reuses_execution(tmp_path: Path) -> None:
    request = DispatchRequest.model_validate(valid_request())
    planner = FakePlanner()
    settings = Settings(workspace_root=tmp_path)
    service = OrchestratorService(
        settings,
        gate=FakeGate(),
        planner=planner,
        gateways={Transport.sdk: FakeGateway(), Transport.mcp: FakeGateway()},
    )

    first = await service.dispatch(request)
    second = await service.dispatch(request)

    assert planner.calls == 1
    assert first.execution_receipt == second.execution_receipt
    assert first.codex_thread_id == second.codex_thread_id
    assert first.idempotency_replayed is False
    assert second.idempotency_replayed is True


async def test_health_endpoint_is_local_read_only_contract(tmp_path: Path) -> None:
    app = build_app(tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        unauthorized = await client.get("/health")
        response = await client.get("/health", headers=AUTHORIZATION)

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["public_unauthenticated_endpoint"] is False
    assert response.json()["authentication_configured"] is True


async def test_dispatch_endpoint_rejects_unauthenticated_client(tmp_path: Path) -> None:
    app = build_app(tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://orchestrator.example",
    ) as client:
        response = await client.post("/v1/connected/tasks/dispatch", json={})

    assert response.status_code == 401
    assert response.json()["detail"] == "valid bearer authentication is required"


async def test_capabilities_endpoint_contains_flags_not_environment_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-secret-value")
    settings = Settings(workspace_root=tmp_path)
    operator = OperatorService(tmp_path, automatic_agents_available=False)
    app = create_app(
        settings,
        build_service(tmp_path),
        operator,
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing("test-client", TOKEN),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/capabilities", headers=AUTHORIZATION)

    assert response.status_code == 200
    payload = response.json()
    assert payload["manual_relay_fallback"] is True
    assert payload["automatic_agents_available"] is False
    assert payload["database_connected"] is False
    assert "dummy-secret-value" not in response.text
    assert "OPENAI_API_KEY" not in response.text


async def test_cors_allows_loopback_flutter_client_only(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        local = await client.options(
            "/v1/capabilities",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        remote = await client.options(
            "/v1/capabilities",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert local.headers["access-control-allow-origin"] == "http://localhost:8080"
    assert "access-control-allow-origin" not in remote.headers


async def test_read_scope_cannot_dispatch(tmp_path: Path) -> None:
    app = build_app(tmp_path, scopes=(ServiceScope.read,))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/v1/connected/tasks/dispatch",
            json={},
            headers=AUTHORIZATION,
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "missing scope: tasks:dispatch"
