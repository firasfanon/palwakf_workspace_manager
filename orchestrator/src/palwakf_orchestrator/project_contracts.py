from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectAdapterKind(StrEnum):
    github_repository = "github_repository"
    local_git = "local_git"


class ProjectStatus(StrEnum):
    registered = "registered"
    probed = "probed"
    drifted = "drifted"
    blocked = "blocked"


class ToolDisposition(StrEnum):
    selected = "selected"
    conditional = "conditional"
    excluded = "excluded"
    blocked = "blocked"


class EvidenceReference(BaseModel):
    kind: str
    reference: str
    observation: str


class ProjectToolDecision(BaseModel):
    adapter_id: str
    disposition: ToolDisposition
    reason: str
    evidence: list[str] = Field(default_factory=list)


class ProjectCapabilityProfile(BaseModel):
    profile_version: Literal["PROJECT_CAPABILITY_PROFILE_V1"] = (
        "PROJECT_CAPABILITY_PROFILE_V1"
    )
    project_id: str
    observed_head: str
    stack: list[str]
    selected_tools: list[ProjectToolDecision] = Field(default_factory=list)
    conditional_tools: list[ProjectToolDecision] = Field(default_factory=list)
    excluded_tools: list[ProjectToolDecision] = Field(default_factory=list)
    blocked_tools: list[ProjectToolDecision] = Field(default_factory=list)


class ProjectCommand(BaseModel):
    command: str
    purpose: str
    evidence: str
    executable_in_read_only_probe: Literal[False] = False


class CIWorkflowReality(BaseModel):
    provider: str
    name: str
    path: str | None = None
    status: str
    conclusion: str | None = None
    url: str | None = None
    observed_head: str | None = None


class DeploymentReality(BaseModel):
    provider: str
    status: str
    environment: str | None = None
    url: str | None = None
    evidence: str


class CandidateWorkItem(BaseModel):
    rank: int = Field(ge=1, le=20)
    candidate_id: str
    title: str
    rationale: str
    acceptance_test: str
    evidence: list[str] = Field(min_length=1)
    blocked: bool = False
    blocker: str | None = None


class FileTreeSummary(BaseModel):
    total_files: int = Field(ge=0)
    scanned_files: int = Field(ge=0)
    truncated: bool
    source_roots: list[str] = Field(default_factory=list)
    test_roots: list[str] = Field(default_factory=list)
    manifest_files: list[str] = Field(default_factory=list)
    workflow_files: list[str] = Field(default_factory=list)
    state_files: list[str] = Field(default_factory=list)
    secret_risk_file_names: list[str] = Field(default_factory=list)
    ignored_secret_policy_present: bool = False


class ExternalProjectRealityReport(BaseModel):
    report_version: Literal["EXTERNAL_PROJECT_REALITY_REPORT_V1"] = (
        "EXTERNAL_PROJECT_REALITY_REPORT_V1"
    )
    project_id: str
    repository_full_name: str
    adapter: ProjectAdapterKind
    visibility: str
    default_branch: str
    observed_branch: str
    observed_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    previous_observed_head: str | None = None
    drift_status: Literal["BASELINE_CREATED", "UNCHANGED", "HEAD_DRIFT"]
    ahead_by: int | None = None
    behind_by: int | None = None
    local_clean: bool | None = None
    stack: list[str]
    package_managers: list[str]
    toolchain_versions: dict[str, str]
    commands: list[ProjectCommand]
    ci: list[CIWorkflowReality]
    ci_status: str
    deployments: list[DeploymentReality]
    deployment_status: str
    tree: FileTreeSummary
    indicators: dict[str, bool]
    source_of_truth_references: list[EvidenceReference]
    capability_profile: ProjectCapabilityProfile
    candidate_work_items: list[CandidateWorkItem]
    blockers: list[str] = Field(default_factory=list)
    observed_at: datetime
    baseline_fingerprint: str = Field(pattern=r"^[0-9A-F]{64}$")
    external_mutation_performed: Literal[False] = False


class ExternalProjectRecord(BaseModel):
    project_id: str
    display_name: str
    repository_full_name: str
    adapter: ProjectAdapterKind
    local_repository_path: str | None = None
    default_branch: str | None = None
    observed_branch: str | None = None
    observed_head: str | None = None
    visibility: str | None = None
    stack: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    ci_providers: list[str] = Field(default_factory=list)
    deployment_providers: list[str] = Field(default_factory=list)
    authority_mode: Literal["READ_ONLY_ZERO_MUTATION"] = "READ_ONLY_ZERO_MUTATION"
    allowed_mutation_modes: list[str] = Field(default_factory=list)
    source_of_truth_references: list[str] = Field(default_factory=list)
    last_probe_at: datetime | None = None
    baseline_fingerprint: str | None = None
    status: ProjectStatus = ProjectStatus.registered
    blockers: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_full_name: str = Field(
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        max_length=200,
    )
    display_name: str = Field(min_length=1, max_length=200)
    adapter: ProjectAdapterKind = ProjectAdapterKind.github_repository
    local_repository_path: str | None = Field(default=None, max_length=1_000)
    expected_head: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{40}$",
    )
    authority_mode: Literal["READ_ONLY_ZERO_MUTATION"] = "READ_ONLY_ZERO_MUTATION"


class PrepareGovernedTaskEnvelopeResponse(BaseModel):
    project_id: str
    repository: str
    expected_head: str
    authority_mode: Literal["READ_ONLY_ZERO_MUTATION"]
    candidate_work_item: CandidateWorkItem
    prepared_only: Literal[True] = True
    dispatched: Literal[False] = False


class PrepareGovernedTaskEnvelopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=3, max_length=200)
