from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_contracts import ExecutionRunOperationalView


class WorkspaceAuthorityPackageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["PALWAKF_INTERSYSTEM_CONTRACT_V1"] = "PALWAKF_INTERSYSTEM_CONTRACT_V1"
    state_package_id: str
    execution_run_id: str
    project_id: str
    task_id: str
    repository: str
    task_branch: str
    base_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    authority_reference: str
    objective: str
    constraints: list[str]
    timeout_seconds: int
    scope_patterns: list[str]
    read_only: Literal[True] = True
    allow_network_read: bool = False
    allow_network_write: Literal[False] = False
    required_capabilities: list[str]
    required_tests: list[str]
    requested_provider_id: Literal["PALWAKF_NATIVE_AGENT"] = "PALWAKF_NATIVE_AGENT"
    requested_model_provider: Literal["none", "ollama"] = "none"


def build_workspace_authority_package(
    view: ExecutionRunOperationalView,
) -> WorkspaceAuthorityPackageV1:
    parent = view.parent_task
    run = view.operator_task

    if parent.mutation_class != "read-only":
        raise GovernanceError("INTERSYSTEM_PILOT_REQUIRES_READ_ONLY_PARENT")
    if run.sandbox != "read-only":
        raise GovernanceError("INTERSYSTEM_PILOT_REQUIRES_READ_ONLY_RUN")
    if not run.requires_explicit_authorization:
        raise GovernanceError("INTERSYSTEM_PILOT_EXPLICIT_AUTHORIZATION_REQUIRED")
    authority_head = parent.latest_remote_task_sha or parent.base_sha
    if run.expected_head.lower() != authority_head.lower():
        raise GovernanceError("INTERSYSTEM_PILOT_EXPECTED_HEAD_DRIFT")
    if run.project_id != parent.project_id or run.repository != parent.repository:
        raise GovernanceError("INTERSYSTEM_PILOT_SCOPE_DRIFT")

    return WorkspaceAuthorityPackageV1(
        state_package_id=f"workspace-state-{view.execution_run_id}",
        execution_run_id=view.execution_run_id,
        project_id=parent.project_id,
        task_id=parent.task_id,
        repository=parent.repository,
        task_branch=parent.task_branch,
        base_sha=parent.base_sha,
        expected_head=run.expected_head,
        authority_reference=run.authority_reference,
        objective=run.prompt,
        constraints=list(run.constraints),
        timeout_seconds=run.timeout_seconds,
        scope_patterns=list(parent.scope_patterns),
        allow_network_read=("LOCAL_PROVIDER_NETWORK_READ" in parent.required_capabilities),
        required_capabilities=list(parent.required_capabilities),
        required_tests=list(parent.required_tests),
    )
