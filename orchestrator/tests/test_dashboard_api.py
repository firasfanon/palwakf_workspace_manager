from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.mcp_server import create_mcp_server
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_contracts import ProjectAdapterKind
from palwakf_orchestrator.project_reality import GitHubRepositoryRealityAdapter
from palwakf_orchestrator.project_service import ExternalProjectService
from tests.test_project_reality import FakeGitHubReadClient
from tests.test_service import build_service

TOKEN = "dashboard-api-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def build_dashboard_app(tmp_path: Path):
    store = MemoryStateStore()
    project_service = ExternalProjectService(
        {
            ProjectAdapterKind.github_repository: GitHubRepositoryRealityAdapter(
                FakeGitHubReadClient()
            )
        },
        store,
    )
    app = create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=store,
        auth_registry=AuthRegistry.for_testing("dashboard-client", TOKEN),
        project_service=project_service,
    )
    return app


@pytest.mark.asyncio
async def test_dashboard_uses_authoritative_project_reality(tmp_path: Path) -> None:
    app = build_dashboard_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        intake = await client.post(
            "/v1/projects/intake",
            headers=AUTH,
            json={
                "repository_full_name": "firasfanon/Pal_Eyes",
                "display_name": "Pal Eyes",
                "adapter": "github_repository",
            },
        )
        project_id = intake.json()["project_id"]
        await client.post(f"/v1/projects/{project_id}/probe", headers=AUTH)
        response = await client.get("/v1/dashboard/summary", headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_total"] == 1
    assert body["projects"][0]["project_id"] == project_id
    assert body["projects"][0]["ci_status"] == "NOT_CONFIGURED"
    assert body["projects"][0]["deployment_status"] == "NOT_DISCOVERED"
    assert "EXTERNAL_PROJECT_REGISTRY" in body["provenance"]


@pytest.mark.asyncio
async def test_dashboard_evidence_is_bounded_and_never_exposes_absolute_paths(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "report.json").write_text(
        json.dumps(
            {
                "task_id": "SAFE_TASK",
                "status": "PASS",
                "observed_at": "2026-07-31T00:00:00Z",
                "private_path": "C:\\Users\\operator\\secret",
                "baseline_fingerprint": "A" * 64,
            }
        ),
        encoding="utf-8",
    )
    app = build_dashboard_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/evidence?limit=1", headers=AUTH)
        invalid = await client.get("/v1/evidence?limit=101", headers=AUTH)

    assert response.status_code == 200
    assert response.json()[0]["safe_reference"] == "evidence/report.json"
    assert "C:\\Users" not in response.text
    assert response.json()[0]["fingerprint"] == "A" * 64
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_dashboard_routes_require_read_scope(tmp_path: Path) -> None:
    app = build_dashboard_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        responses = [
            await client.get("/v1/dashboard/summary"),
            await client.get("/v1/dashboard/activity"),
            await client.get("/v1/alerts"),
            await client.get("/v1/evidence"),
        ]

    assert all(response.status_code == 401 for response in responses)


@pytest.mark.asyncio
async def test_dashboard_http_reads_have_mcp_contract_parity(tmp_path: Path) -> None:
    app = build_dashboard_app(tmp_path)
    registry = AuthRegistry.for_testing("dashboard-client", TOKEN)
    server = create_mcp_server(
        app.state.connected_service,
        registry,
        app.state.dashboard_service,
    )

    names = {tool.name for tool in await server.list_tools()}

    assert {
        "get_workspace_dashboard",
        "list_operational_alerts",
        "list_workspace_evidence",
        "list_workspace_activity",
    }.issubset(names)
