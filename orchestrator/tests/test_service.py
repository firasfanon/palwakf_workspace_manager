from pathlib import Path

from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import (
    DispatchPlan,
    DispatchRequest,
    GatewayResult,
    RepositoryState,
    Transport,
)
from palwakf_orchestrator.service import OrchestratorService
from tests.test_contracts import valid_request

FULL_HEAD = "a312d498bf89c509ae04a6c2eaa476de0a7c39bc"


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
    async def plan(
        self,
        request: DispatchRequest,
        repository_state: RepositoryState,
    ) -> DispatchPlan:
        return DispatchPlan(
            summary="Read-only inspection",
            codex_prompt=f"Inspect without writes: {request.prompt}",
            requires_workspace_write=False,
        )


class FakeGateway:
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


async def test_dispatch_uses_planner_and_selected_gateway(tmp_path: Path) -> None:
    request = DispatchRequest.model_validate(valid_request())

    response = await build_service(tmp_path).dispatch(request)

    assert response.status == "completed"
    assert response.codex_thread_id == "thread-test"
    assert response.boundaries.production_mutation is False


async def test_health_endpoint_is_local_read_only_contract(tmp_path: Path) -> None:
    app = create_app(Settings(workspace_root=tmp_path), build_service(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["remote_deployment"] is False
    assert response.json()["boundaries"]["workspace_write"] is False


async def test_dispatch_endpoint_rejects_remote_host(tmp_path: Path) -> None:
    app = create_app(Settings(workspace_root=tmp_path), build_service(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://orchestrator.example",
    ) as client:
        response = await client.post("/v1/dispatch", json=valid_request())

    assert response.status_code == 403
    assert response.json()["detail"] == "V1 dispatch is local-only"
