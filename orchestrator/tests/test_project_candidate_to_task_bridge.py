from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_contracts import ProjectAdapterKind, ProjectIntakeRequest
from palwakf_orchestrator.project_reality import GitHubRepositoryRealityAdapter
from palwakf_orchestrator.project_service import ExternalProjectService
from tests.test_project_reality import HEAD, FakeGitHubReadClient
from tests.test_service import build_service

TOKEN = "project-candidate-task-bridge-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_candidate_becomes_real_engineering_task_with_server_derived_authority(
    tmp_path: Path,
) -> None:
    store = MemoryStateStore()
    projects = ExternalProjectService(
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
        auth_registry=AuthRegistry.for_testing("project-bridge-client", TOKEN),
        project_service=projects,
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
        candidate = probe.json()["candidate_work_items"][0]
        task_id = "PAL_EYES_CANDIDATE_OPERATIONAL_TASK"

        created = await client.post(
            (
                f"/v1/projects/{project_id}/candidate-work-items/"
                f"{candidate['candidate_id']}/engineering-task"
            ),
            headers=AUTH,
            json={
                "task_id": task_id,
                "owner_id": "firas",
                "actor_id": "firas",
                "actor_type": "HUMAN",
                "scope_patterns": ["lib/**", "test/**"],
                "risk_class": "MEDIUM",
                "mutation_class": "source-write",
            },
        )
        tasks = await client.get("/v1/engineering-os/tasks", headers=AUTH)

        rejected_override = await client.post(
            (
                f"/v1/projects/{project_id}/candidate-work-items/"
                f"{candidate['candidate_id']}/engineering-task"
            ),
            headers=AUTH,
            json={
                "task_id": "PAL_EYES_AUTHORITY_OVERRIDE_REJECTED",
                "owner_id": "firas",
                "actor_id": "firas",
                "actor_type": "HUMAN",
                "scope_patterns": ["lib/**"],
                "repository": "attacker/override",
            },
        )

    assert intake.status_code == 200
    assert probe.status_code == 200
    assert created.status_code == 200
    payload = created.json()
    assert payload["project_id"] == project_id
    assert payload["repository"] == "firasfanon/Pal_Eyes"
    assert payload["base_sha"] == HEAD
    assert payload["task_branch"] == f"task/{task_id}"
    assert payload["title"] == candidate["title"]
    assert payload["status"] == "READY"
    assert payload["scope_patterns"] == ["lib/**", "test/**"]
    assert "Acceptance:" in payload["description"]
    assert any(item["task_id"] == task_id for item in tasks.json())
    assert rejected_override.status_code == 422


@pytest.mark.asyncio
async def test_blocked_candidate_cannot_become_engineering_task(tmp_path: Path) -> None:
    store = MemoryStateStore()
    projects = ExternalProjectService(
        {
            ProjectAdapterKind.github_repository: GitHubRepositoryRealityAdapter(
                FakeGitHubReadClient()
            )
        },
        store,
    )
    record = projects.intake(
        ProjectIntakeRequest(
            repository_full_name="firasfanon/Pal_Eyes",
            display_name="Pal Eyes",
        )
    )
    report = await projects.probe(record.project_id)
    blocked = report.model_copy(
        update={
            "candidate_work_items": [
                report.candidate_work_items[0].model_copy(
                    update={"blocked": True, "blocker": "TEST_BLOCKER"}
                )
            ]
        }
    )
    state = store.load()
    state["external_projects"]["reports"][record.project_id] = blocked.model_dump(mode="json")
    store.save(state)

    app = create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=store,
        auth_registry=AuthRegistry.for_testing("project-bridge-client", TOKEN),
        project_service=projects,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            (
                f"/v1/projects/{record.project_id}/candidate-work-items/"
                f"{blocked.candidate_work_items[0].candidate_id}/engineering-task"
            ),
            headers=AUTH,
            json={
                "task_id": "PAL_EYES_BLOCKED_CANDIDATE",
                "owner_id": "firas",
                "actor_id": "firas",
                "actor_type": "HUMAN",
                "scope_patterns": ["lib/**"],
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "PROJECT_CANDIDATE_BLOCKED"
