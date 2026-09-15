from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from palwakf_orchestrator.errors import GovernanceError


class ProjectSystemRole(StrEnum):
    control_plane = "CONTROL_PLANE"
    knowledge_plane = "KNOWLEDGE_PLANE"
    execution_plane = "EXECUTION_PLANE"
    integration_orchestrator = "INTEGRATION_ORCHESTRATOR"


class ProjectSystemKind(StrEnum):
    repository_project = "REPOSITORY_PROJECT"
    logical_component = "LOGICAL_COMPONENT"


class ProjectTruthAuthorities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["REMOTE_GITHUB"] = "REMOTE_GITHUB"
    sovereign: Literal["WORKSPACE_DRIVE"] = "WORKSPACE_DRIVE"
    operational_runtime: Literal["OPERATIONAL_STATE_STORE"] = "OPERATIONAL_STATE_STORE"
    chat_history: Literal["NOT_SYSTEM_OF_RECORD"] = "NOT_SYSTEM_OF_RECORD"


class ProjectMutationAuthorityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_mutation_requires_task_authorization: Literal[True] = True
    main_merge_requires_explicit_authorization: Literal[True] = True
    baseline_promotion_requires_explicit_authorization: Literal[True] = True
    production_requires_explicit_authorization: Literal[True] = True
    shared_db_mutation_requires_explicit_authorization: Literal[True] = True
    authority_expansion_forbidden: Literal[True] = True


class ProjectContractManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal["PROJECT_CONTRACT_MANIFEST_V1"] = "PROJECT_CONTRACT_MANIFEST_V1"
    project_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    institutional_name: str = Field(min_length=3, max_length=240)
    system_role: ProjectSystemRole
    system_kind: ProjectSystemKind
    repository_full_name: str = Field(
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        max_length=200,
    )
    host_project_id: str | None = None
    separate_repository: bool
    implementation_placement: str = Field(min_length=3, max_length=240)
    current_state_document_id: str = Field(min_length=10, max_length=200)
    architecture_version: Literal["ENGINEERING_OS_SYSTEM_DESIGN_SPEC_V1"] = (
        "ENGINEERING_OS_SYSTEM_DESIGN_SPEC_V1"
    )
    truth_authorities: ProjectTruthAuthorities = Field(default_factory=ProjectTruthAuthorities)
    mutation_authority: ProjectMutationAuthorityPolicy = Field(
        default_factory=ProjectMutationAuthorityPolicy
    )


class ProjectContractManifestRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: Literal["PROJECT_CONTRACT_MANIFEST_REGISTRY_V1"] = (
        "PROJECT_CONTRACT_MANIFEST_REGISTRY_V1"
    )
    manifests: list[ProjectContractManifestV1] = Field(min_length=4, max_length=4)


_REQUIRED_SYSTEMS: dict[str, tuple[ProjectSystemRole, ProjectSystemKind, str]] = {
    "PALWAKF_WORKSPACE_MANAGER": (
        ProjectSystemRole.control_plane,
        ProjectSystemKind.repository_project,
        "firasfanon/palwakf_workspace_manager",
    ),
    "PALWAKF_MIND_ASSISTANT": (
        ProjectSystemRole.knowledge_plane,
        ProjectSystemKind.repository_project,
        "firasfanon/palwakf_mind_assistant",
    ),
    "PALWAKF_AGENTIC_AI": (
        ProjectSystemRole.execution_plane,
        ProjectSystemKind.repository_project,
        "firasfanon/palwakf_agenticAi_system",
    ),
    "PALWAKF_INTEGRATION_ORCHESTRATOR_ENGINEERING_OS": (
        ProjectSystemRole.integration_orchestrator,
        ProjectSystemKind.logical_component,
        "firasfanon/palwakf_workspace_manager",
    ),
}


class ProjectContractManifestService:
    def __init__(self, manifest_root: Path | None = None) -> None:
        self._manifest_root = manifest_root or (
            Path(__file__).resolve().parents[2] / "data" / "project_contract_manifests"
        )
        self._registry = self._load_registry()

    def registry(self) -> ProjectContractManifestRegistryV1:
        return self._registry

    def list_manifests(self) -> list[ProjectContractManifestV1]:
        return list(self._registry.manifests)

    def get_manifest(self, project_id: str) -> ProjectContractManifestV1:
        for manifest in self._registry.manifests:
            if manifest.project_id == project_id:
                return manifest
        raise GovernanceError("PROJECT_CONTRACT_MANIFEST_NOT_FOUND")

    def _load_registry(self) -> ProjectContractManifestRegistryV1:
        if not self._manifest_root.is_dir():
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_ROOT_MISSING")
        paths = sorted(self._manifest_root.glob("*.json"))
        if len(paths) != 4:
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_COUNT_MISMATCH")
        manifests: list[ProjectContractManifestV1] = []
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                manifests.append(ProjectContractManifestV1.model_validate(payload))
            except (OSError, json.JSONDecodeError, ValidationError) as exc:
                raise GovernanceError(f"PROJECT_CONTRACT_MANIFEST_INVALID:{path.name}") from exc
        registry = ProjectContractManifestRegistryV1(manifests=manifests)
        self._validate_registry(registry)
        return registry

    def _validate_registry(self, registry: ProjectContractManifestRegistryV1) -> None:
        by_id = {manifest.project_id: manifest for manifest in registry.manifests}
        if len(by_id) != len(registry.manifests):
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_DUPLICATE_PROJECT_ID")
        if set(by_id) != set(_REQUIRED_SYSTEMS):
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_REQUIRED_SYSTEM_SET_MISMATCH")
        roles = [manifest.system_role for manifest in registry.manifests]
        if len(set(roles)) != len(roles):
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_DUPLICATE_SYSTEM_ROLE")

        for project_id, expected in _REQUIRED_SYSTEMS.items():
            expected_role, expected_kind, expected_repo = expected
            manifest = by_id[project_id]
            if manifest.system_role != expected_role:
                raise GovernanceError("PROJECT_CONTRACT_MANIFEST_ROLE_MISMATCH")
            if manifest.system_kind != expected_kind:
                raise GovernanceError("PROJECT_CONTRACT_MANIFEST_KIND_MISMATCH")
            if manifest.repository_full_name != expected_repo:
                raise GovernanceError("PROJECT_CONTRACT_MANIFEST_REPOSITORY_MISMATCH")

        workspace = by_id["PALWAKF_WORKSPACE_MANAGER"]
        integration = by_id["PALWAKF_INTEGRATION_ORCHESTRATOR_ENGINEERING_OS"]
        for manifest in registry.manifests:
            if manifest.system_kind == ProjectSystemKind.repository_project:
                if not manifest.separate_repository or manifest.host_project_id is not None:
                    raise GovernanceError(
                        "PROJECT_CONTRACT_MANIFEST_REPOSITORY_PROJECT_PLACEMENT_INVALID"
                    )
                if manifest.implementation_placement != "SEPARATE_REPOSITORY":
                    raise GovernanceError(
                        "PROJECT_CONTRACT_MANIFEST_REPOSITORY_PROJECT_PLACEMENT_INVALID"
                    )

        if integration.separate_repository:
            raise GovernanceError(
                "PROJECT_CONTRACT_MANIFEST_INTEGRATION_SEPARATE_REPOSITORY_FORBIDDEN"
            )
        if integration.host_project_id != workspace.project_id:
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_INTEGRATION_HOST_MISMATCH")
        if integration.repository_full_name != workspace.repository_full_name:
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_INTEGRATION_REPOSITORY_MISMATCH")
        if integration.implementation_placement != "LOGICAL_COMPONENT_INSIDE_WORKSPACE_MANAGER_V1":
            raise GovernanceError("PROJECT_CONTRACT_MANIFEST_INTEGRATION_PLACEMENT_MISMATCH")
