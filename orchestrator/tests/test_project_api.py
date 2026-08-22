from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_contracts import ProjectAdapterKind
from palwakf_orchestrator.project_reality import GitHubRepositoryRealityAdapter
from palwakf_orchestrator.project_service import ExternalProjectService
from tests.test_project_reality import HEAD, FakeGitHubReadClient
from tests.test_service import build_service

TOKEN = "project-api-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_authenticated_project_api_intake_probe_and_prepare(
    tmp_path: Path,
) -> None:
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
        auth_registry=AuthRegistry.for_testing("project-client", TOKEN),
        project_service=project_service,
    )

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
                "authority_mode": "READ_ONLY_ZERO_MUTATION",
            },
        )
        project_id = intake.json()["project_id"]
        probe = await client.post(
            f"/v1/projects/{project_id}/probe",
            headers=AUTH,
        )
        candidates = await client.get(
            f"/v1/projects/{project_id}/candidate-work-items",
            headers=AUTH,
        )
        prepare = await client.post(
            f"/v1/projects/{project_id}/prepare-task",
            headers=AUTH,
            json={"candidate_id": candidates.json()[0]["candidate_id"]},
        )

    assert intake.status_code == 200
    assert probe.status_code == 200
    assert probe.json()["observed_head"] == HEAD
    assert probe.json()["external_mutation_performed"] is False
    assert candidates.status_code == 200
    assert prepare.status_code == 200
    assert prepare.json()["prepared_only"] is True
    assert prepare.json()["dispatched"] is False


@pytest.mark.asyncio
async def test_project_api_requires_authentication(tmp_path: Path) -> None:
    app = create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing("project-client", TOKEN),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/projects")

    assert response.status_code == 401
