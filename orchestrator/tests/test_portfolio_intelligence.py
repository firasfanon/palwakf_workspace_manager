from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.portfolio_intelligence import PortfolioIntelligenceService
from palwakf_orchestrator.portfolio_intelligence_contracts import DependencyView
from palwakf_orchestrator.project_contracts import ProjectAdapterKind
from palwakf_orchestrator.project_reality import GitHubRepositoryRealityAdapter
from palwakf_orchestrator.project_service import ExternalProjectService
from tests.test_project_reality import FakeGitHubReadClient
from tests.test_service import build_service

TOKEN = "portfolio-intelligence-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def build_portfolio_app(tmp_path: Path):
    store = MemoryStateStore()
    projects = ExternalProjectService(
        {
            ProjectAdapterKind.github_repository: GitHubRepositoryRealityAdapter(
                FakeGitHubReadClient()
            )
        },
        store,
    )
    return create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=store,
        auth_registry=AuthRegistry.for_testing("portfolio-client", TOKEN),
        project_service=projects,
    )


async def _register_project(client: AsyncClient) -> str:
    intake = await client.post(
        "/v1/projects/intake",
        headers=AUTH,
        json={
            "repository_full_name": "firasfanon/Pal_Eyes",
            "display_name": "Pal Eyes",
            "adapter": "github_repository",
        },
    )
    assert intake.status_code == 200
    project_id = intake.json()["project_id"]
    probe = await client.post(f"/v1/projects/{project_id}/probe", headers=AUTH)
    assert probe.status_code == 200
    return str(project_id)
@pytest.mark.asyncio
async def test_portfolio_overview_is_read_only_truth_projection(tmp_path: Path) -> None:
    app = build_portfolio_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        project_id = await _register_project(client)
        response = await client.get("/v1/portfolio/overview", headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "PALWAKF_PORTFOLIO_INTELLIGENCE_V1"
    assert body["projects"][0]["project_id"] == project_id
    assert body["projects"][0]["scope_progress_percent"] is None
    assert (
        body["projects"][0]["scope_progress_basis"]
        == "UNAVAILABLE_NO_CANONICAL_SCOPE_PROFILE_IN_RUNTIME"
    )
    assert body["projects"][0]["forecast"]["p50"] is None
    assert body["projects"][0]["forecast"]["p80"] is None
    assert (
        body["projects"][0]["forecast"]["basis"]
        == "NO_FABRICATED_ETA_WITHOUT_HISTORICAL_CYCLE_TIME"
    )
    assert "UNKNOWN_IS_NOT_FALSE" in body["authority_notes"]
    assert "NO_SECOND_SOVEREIGN_STATE_STORE" in body["provenance"]


@pytest.mark.asyncio
async def test_portfolio_source_failure_semantics_do_not_fabricate_drive_state(
    tmp_path: Path,
) -> None:
    app = build_portfolio_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await _register_project(client)
        response = await client.get("/v1/portfolio/overview", headers=AUTH)

    sources = {item["source_id"]: item for item in response.json()["source_health"]}
    drive = sources["WORKSPACE_DRIVE_SOVEREIGN"]
    assert drive["state"] == "UNKNOWN"
    assert drive["freshness"] == "NO_LIVE_RUNTIME_ADAPTER"
    assert "لا تُفسر هذه الحالة كغياب" in drive["detail_ar"]


@pytest.mark.asyncio
async def test_portfolio_dependency_absence_is_explicit_unavailable(
    tmp_path: Path,
) -> None:
    app = build_portfolio_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/portfolio/critical-path", headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["project_ids"] == []
    assert "لا يتم اختلاق" in body["reason_ar"]
@pytest.mark.asyncio
async def test_portfolio_routes_require_authenticated_read_scope(tmp_path: Path) -> None:
    app = build_portfolio_app(tmp_path)
    routes = [
        "/v1/portfolio/overview",
        "/v1/portfolio/recommendations",
        "/v1/portfolio/critical-path",
        "/v1/portfolio/forecast",
        "/v1/portfolio/capabilities",
        "/v1/portfolio/skills",
        "/v1/portfolio/tools",
        "/v1/portfolio/agents",
        "/v1/portfolio/providers",
        "/v1/portfolio/dependencies",
        "/v1/portfolio/blockers",
        "/v1/portfolio/decisions",
        "/v1/portfolio/history",
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        responses = [await client.get(route) for route in routes]

    assert all(response.status_code == 401 for response in responses)


def test_dependency_path_is_deterministic_and_cycle_fails_closed() -> None:
    edges = [
        DependencyView(
            edge_id="e1",
            producer_project_id="WORKSPACE",
            consumer_project_id="MIND",
            kind="API",
            contract_id="c1",
            version="1",
            status="ACTIVE",
            evidence=["evidence-1"],
        ),
        DependencyView(
            edge_id="e2",
            producer_project_id="MIND",
            consumer_project_id="AGENTIC",
            kind="KNOWLEDGE",
            contract_id="c2",
            version="1",
            status="ACTIVE",
            evidence=["evidence-2"],
        ),
    ]
    path, blocker, cycle = PortfolioIntelligenceService._longest_dependency_path(
        ("WORKSPACE", "MIND", "AGENTIC"),
        edges,
    )
    assert path == ["WORKSPACE", "MIND", "AGENTIC"]
    assert blocker == "WORKSPACE"
    assert cycle is False

    cycle_edges = [
        *edges,
        DependencyView(
            edge_id="e3",
            producer_project_id="AGENTIC",
            consumer_project_id="WORKSPACE",
            kind="RUNTIME",
            contract_id="c3",
            version="1",
            status="ACTIVE",
            evidence=["evidence-3"],
        ),
    ]
    path, _, cycle = PortfolioIntelligenceService._longest_dependency_path(
        ("WORKSPACE", "MIND", "AGENTIC"),
        cycle_edges,
    )
    assert path == []
    assert cycle is True
@pytest.mark.asyncio
async def test_portfolio_recommendations_never_grant_authority(tmp_path: Path) -> None:
    app = build_portfolio_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await _register_project(client)
        response = await client.get("/v1/portfolio/recommendations", headers=AUTH)

    assert response.status_code == 200
    for item in response.json():
        assert item["authority"] == "ADVISORY_ONLY"
        assert item["status"] == "PROPOSED"
