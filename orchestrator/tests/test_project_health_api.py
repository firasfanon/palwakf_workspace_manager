from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.persistence import MemoryStateStore
from tests.test_service import build_service

TOKEN = "project-health-api-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_project_health_api_enforces_authority_and_exposes_state(tmp_path: Path) -> None:
    store = MemoryStateStore()
    app = create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=store,
        auth_registry=AuthRegistry.for_testing("project-health-client", TOKEN),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        intake = await client.post(
            "/v1/projects/intake",
            headers=AUTH,
            json={
                "repository_full_name": "firasfanon/palwakf_workspace_manager",
                "display_name": "Workspace Manager",
                "adapter": "github_repository",
                "authority_mode": "READ_ONLY_ZERO_MUTATION",
            },
        )
        project_id = intake.json()["project_id"]
        initial = await client.get(f"/v1/projects/{project_id}/health", headers=AUTH)
        denied = await client.post(
            f"/v1/projects/{project_id}/health/transition",
            headers=AUTH,
            json={
                "expected_state": "UNASSESSED",
                "target_state": "RECONCILING",
                "reason": "start governed reconciliation",
                "evidence": ["EVIDENCE://PREL5-005/API"],
            },
        )
        allowed = await client.post(
            f"/v1/projects/{project_id}/health/transition",
            headers=AUTH,
            json={
                "expected_state": "UNASSESSED",
                "target_state": "RECONCILING",
                "reason": "start governed reconciliation",
                "evidence": ["EVIDENCE://PREL5-005/API"],
                "authority_reference": "AUTHORITY://PREL5-BATCH",
            },
        )

    assert intake.status_code == 200
    assert initial.status_code == 200
    assert initial.json()["state"] == "UNASSESSED"
    assert denied.status_code == 409
    assert denied.json()["detail"] == "PROJECT_HEALTH_AUTHORITY_REQUIRED"
    assert allowed.status_code == 200
    assert allowed.json()["state"] == "RECONCILING"
    assert allowed.json()["sequence"] == 1
    assert allowed.json()["transitions"][0]["evidence"] == ["EVIDENCE://PREL5-005/API"]
