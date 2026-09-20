from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_manifest_service import (
    ProjectContractManifestService,
    ProjectSystemKind,
    ProjectSystemRole,
)
from tests.test_service import build_service

TOKEN = "project-manifest-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
EXPECTED_PROJECTS = {
    "PALWAKF_WORKSPACE_MANAGER",
    "PALWAKF_MIND_ASSISTANT",
    "PALWAKF_AGENTIC_AI",
    "PALWAKF_INTEGRATION_ORCHESTRATOR_ENGINEERING_OS",
}


def _bundled_manifest_root() -> Path:
    import palwakf_orchestrator.project_manifest_service as manifest_module

    return (
        Path(manifest_module.__file__).resolve().parents[2] / "data" / "project_contract_manifests"
    )


def _copy_manifest_root(tmp_path: Path) -> Path:
    target = tmp_path / "project_contract_manifests"
    shutil.copytree(_bundled_manifest_root(), target)
    return target


def test_bundled_four_system_manifests_are_exact_and_fail_closed_by_design() -> None:
    registry = ProjectContractManifestService().registry()
    manifests = registry.manifests

    assert registry.registry_version == "PROJECT_CONTRACT_MANIFEST_REGISTRY_V1"
    assert {manifest.project_id for manifest in manifests} == EXPECTED_PROJECTS
    assert {manifest.system_role for manifest in manifests} == set(ProjectSystemRole)
    assert all(manifest.truth_authorities.code == "REMOTE_GITHUB" for manifest in manifests)
    assert all(manifest.truth_authorities.sovereign == "WORKSPACE_DRIVE" for manifest in manifests)
    assert all(
        manifest.truth_authorities.operational_runtime == "OPERATIONAL_STATE_STORE"
        for manifest in manifests
    )
    assert all(
        manifest.mutation_authority.source_mutation_requires_task_authorization
        for manifest in manifests
    )
    assert all(manifest.mutation_authority.authority_expansion_forbidden for manifest in manifests)

    integration = next(
        manifest
        for manifest in manifests
        if manifest.project_id == "PALWAKF_INTEGRATION_ORCHESTRATOR_ENGINEERING_OS"
    )
    assert integration.system_kind == ProjectSystemKind.logical_component
    assert integration.separate_repository is False
    assert integration.host_project_id == "PALWAKF_WORKSPACE_MANAGER"
    assert integration.repository_full_name == "firasfanon/palwakf_workspace_manager"


def test_manifest_with_unknown_field_is_rejected(tmp_path: Path) -> None:
    root = _copy_manifest_root(tmp_path)
    path = root / "PALWAKF_WORKSPACE_MANAGER.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["implicit_execution_authority"] = True
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(GovernanceError, match="PROJECT_CONTRACT_MANIFEST_INVALID"):
        ProjectContractManifestService(root)


def test_missing_required_manifest_fails_closed(tmp_path: Path) -> None:
    root = _copy_manifest_root(tmp_path)
    (root / "PALWAKF_MIND_ASSISTANT.json").unlink()

    with pytest.raises(
        GovernanceError,
        match="PROJECT_CONTRACT_MANIFEST_COUNT_MISMATCH",
    ):
        ProjectContractManifestService(root)


def test_integration_orchestrator_cannot_claim_separate_repository(tmp_path: Path) -> None:
    root = _copy_manifest_root(tmp_path)
    path = root / "PALWAKF_INTEGRATION_ORCHESTRATOR_ENGINEERING_OS.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["separate_repository"] = True
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(
        GovernanceError,
        match="PROJECT_CONTRACT_MANIFEST_INTEGRATION_SEPARATE_REPOSITORY_FORBIDDEN",
    ):
        ProjectContractManifestService(root)


@pytest.mark.asyncio
async def test_manifest_api_lists_and_gets_validated_contracts(tmp_path: Path) -> None:
    app = create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing("project-manifest-client", TOKEN),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        listing = await client.get("/v1/project-contract-manifests", headers=AUTH)
        workspace = await client.get(
            "/v1/project-contract-manifests/PALWAKF_WORKSPACE_MANAGER",
            headers=AUTH,
        )
        missing = await client.get(
            "/v1/project-contract-manifests/UNKNOWN_PROJECT",
            headers=AUTH,
        )

    assert listing.status_code == 200
    assert {item["project_id"] for item in listing.json()["manifests"]} == EXPECTED_PROJECTS
    assert workspace.status_code == 200
    assert workspace.json()["system_role"] == "CONTROL_PLANE"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "PROJECT_CONTRACT_MANIFEST_NOT_FOUND"
