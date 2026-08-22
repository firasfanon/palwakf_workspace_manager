from fastapi import FastAPI
from fastapi.testclient import TestClient

from palwakf_orchestrator.api import _add_engineering_os_routes
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.persistence import MemoryStateStore


def client() -> TestClient:
    app = FastAPI()
    _add_engineering_os_routes(app, EngineeringOsService(MemoryStateStore()))
    return TestClient(app)


def test_engineering_os_routes_create_task_and_extension() -> None:
    api = client()
    task = api.post(
        "/v1/engineering-os/tasks",
        json={
            "task_id": "WM-API-101",
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "title": "API task",
            "description": "Remote-first API task",
            "repository": "firasfanon/palwakf_workspace_manager",
            "base_sha": "a" * 40,
            "task_branch": "task/WM-API-101",
            "owner_id": "firas",
            "actor_id": "firas",
            "actor_type": "HUMAN",
            "scope_patterns": ["lib/**"],
            "depends_on": [],
            "dependency_mode": "INDEPENDENT",
            "risk_class": "MEDIUM",
            "mutation_class": "source-write",
            "required_capabilities": ["source.control"],
            "required_tests": ["targeted"],
        },
    )
    assert task.status_code == 200
    assert task.json()["status"] == "READY"

    extension = api.post(
        "/v1/extensions",
        json={
            "extension_id": "tool.example",
            "kind": "TOOL",
            "name": "Example Tool",
            "version": "0.1.0",
            "source_kind": "GITHUB",
            "source_reference": "example/tool",
            "open_source": True,
            "license": "MIT",
            "capabilities": ["source.read"],
            "declared_roles": ["governed_patch_relay"],
            "required_permissions": ["read"],
            "allowed_projects": ["PALWAKF_WORKSPACE_MANAGER"],
            "risk_class": "LOW",
            "fork_strategy": "PREFER_FORK",
        },
    )
    assert extension.status_code == 200
    assert extension.json()["lifecycle"] == "QUARANTINED"
    assert extension.json()["declared_roles"] == ["governed_patch_relay"]
    assert extension.json()["role_authorities"] == {"governed_patch_relay": "NOT_AUTHORIZED"}

    summary = api.get("/v1/engineering-os/summary")
    assert summary.status_code == 200
    assert summary.json()["tasks_by_status"]["READY"] == 1
    assert summary.json()["extensions_by_kind"]["TOOL"] == 1
