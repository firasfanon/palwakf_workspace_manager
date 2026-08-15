from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.provider_contracts import RoleAuthority


class EngineeringTaskStatus(StrEnum):
    planned = "PLANNED"
    ready = "READY"
    in_progress = "IN_PROGRESS"
    wip_remote_checkpointed = "WIP_REMOTE_CHECKPOINTED"
    blocked_dependency = "BLOCKED_DEPENDENCY"
    ready_for_review = "READY_FOR_REVIEW"
    ready_for_integration = "READY_FOR_INTEGRATION"
    in_merge_queue = "IN_MERGE_QUEUE"
    reconciliation_required = "RECONCILIATION_REQUIRED"
    integrated = "INTEGRATED"
    failed = "FAILED"
    cancelled = "CANCELLED"
    superseded = "SUPERSEDED"


class DependencyMode(StrEnum):
    independent = "INDEPENDENT"
    wait_for_upstream = "WAIT_FOR_UPSTREAM"
    stacked = "STACKED"


class ActorType(StrEnum):
    human = "HUMAN"
    agent = "AGENT"
    llm = "LLM"


class ExtensionKind(StrEnum):
    skill = "SKILL"
    agent = "AGENT"
    tool = "TOOL"
    provider = "PROVIDER"


class ExtensionLifecycle(StrEnum):
    discovered = "DISCOVERED"
    quarantined = "QUARANTINED"
    approved = "APPROVED"
    installed = "INSTALLED"
    disabled = "DISABLED"


class ExtensionSourceKind(StrEnum):
    internal = "INTERNAL"
    github = "GITHUB"
    mcp = "MCP"
    local = "LOCAL"
    api = "API"


RiskClass = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
MutationClass = Literal["read-only", "source-write", "external-write"]


class CreateEngineeringTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    project_id: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=3, max_length=4000)
    repository: str = Field(min_length=3, max_length=240)
    base_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    task_branch: str = Field(pattern=r"^task/[A-Za-z0-9._/-]{3,180}$")
    owner_id: str = Field(min_length=2, max_length=160)
    actor_id: str = Field(min_length=2, max_length=160)
    actor_type: ActorType
    provider_id: str | None = Field(default=None, max_length=160)
    scope_patterns: list[str] = Field(min_length=1, max_length=64)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    dependency_mode: DependencyMode = DependencyMode.independent
    risk_class: RiskClass = "MEDIUM"
    mutation_class: MutationClass = "source-write"
    required_capabilities: list[str] = Field(default_factory=list, max_length=64)
    required_tests: list[str] = Field(default_factory=list, max_length=64)


class EngineeringTaskRecord(BaseModel):
    task_id: str
    project_id: str
    title: str
    description: str
    repository: str
    base_sha: str
    integrated_head_at_creation: str
    task_branch: str
    latest_remote_task_sha: str | None = None
    owner_id: str
    actor_id: str
    actor_type: ActorType
    provider_id: str | None = None
    scope_patterns: list[str]
    depends_on: list[str]
    dependency_mode: DependencyMode
    risk_class: RiskClass
    mutation_class: MutationClass
    required_capabilities: list[str]
    required_tests: list[str]
    status: EngineeringTaskStatus = EngineeringTaskStatus.planned
    wip_checkpoint_status: Literal["NOT_CHECKPOINTED", "REMOTE_CHECKPOINTED"] = "NOT_CHECKPOINTED"
    integration_status: Literal[
        "NOT_READY", "READY", "QUEUED", "INTEGRATED", "RECONCILIATION_REQUIRED"
    ] = "NOT_READY"
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RemoteCheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remote_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    evidence: list[str] = Field(default_factory=list, max_length=64)


class RegisterExtensionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extension_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    kind: ExtensionKind
    name: str = Field(min_length=2, max_length=200)
    version: str = Field(min_length=1, max_length=80)
    source_kind: ExtensionSourceKind
    source_reference: str = Field(min_length=2, max_length=2000)
    open_source: bool
    license: str | None = Field(default=None, max_length=160)
    capabilities: list[str] = Field(default_factory=list, max_length=128)
    declared_roles: list[str] = Field(default_factory=list, max_length=64)
    required_permissions: list[str] = Field(default_factory=list, max_length=64)
    allowed_projects: list[str] = Field(default_factory=list, max_length=64)
    risk_class: RiskClass = "MEDIUM"
    fork_strategy: Literal["PREFER_FORK", "UPSTREAM_ONLY", "INTERNAL_ONLY"] = "PREFER_FORK"


class ExtensionRecord(BaseModel):
    extension_id: str
    kind: ExtensionKind
    name: str
    version: str
    source_kind: ExtensionSourceKind
    source_reference: str
    open_source: bool
    license: str | None = None
    capabilities: list[str]
    declared_roles: list[str] = Field(default_factory=list)
    role_authorities: dict[str, RoleAuthority] = Field(default_factory=dict)
    required_permissions: list[str]
    allowed_projects: list[str]
    risk_class: RiskClass
    fork_strategy: str
    lifecycle: ExtensionLifecycle = ExtensionLifecycle.quarantined
    health_status: Literal["UNKNOWN", "HEALTHY", "DEGRADED", "BLOCKED"] = "UNKNOWN"
    created_at: datetime
    updated_at: datetime


class EngineeringOsSummary(BaseModel):
    generated_at: datetime
    remote_wip_authority: Literal["GITHUB_REMOTE_TASK_BRANCH"] = "GITHUB_REMOTE_TASK_BRANCH"
    local_worktree_authority: Literal[False] = False
    integrated_head_semantics: Literal["LATEST_INTEGRATED_ACCEPTED_HEAD"] = (
        "LATEST_INTEGRATED_ACCEPTED_HEAD"
    )
    parallel_tracks: list[str]
    tasks_by_status: dict[str, int]
    extensions_by_kind: dict[str, int]
    quarantined_extensions: int
    remote_checkpointed_tasks: int


def utc_now() -> datetime:
    return datetime.now(UTC)
