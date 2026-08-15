from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OperatorTaskStatus(StrEnum):
    pending = "pending"
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    failed = "failed"
    pending_verification = "pending_verification"
    verified = "verified"
    drifted = "drifted"
    timed_out = "timed_out"
    cancelled = "cancelled"


class DispatchMode(StrEnum):
    automatic = "automatic"
    user_relay_fallback = "user_relay_fallback"


class PermissionStatus(StrEnum):
    authorized = "authorized"
    approval_required = "approval_required"
    blocked = "blocked"
    untested = "untested"


class TaskEvent(BaseModel):
    event_type: str
    status: OperatorTaskStatus
    message: str
    occurred_at: datetime
    correlation_id: str | None = None
    client_id: str | None = None


class CreateOperatorTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    project_id: str = Field(min_length=2, max_length=128)
    repository: Literal["firasfanon/palwakf_workspace_manager"]
    branch: Literal["agent/workspace-manager-foundation-v1"]
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    authority_reference: str = Field(min_length=8, max_length=2_000)
    prompt: str = Field(min_length=10, max_length=20_000)
    constraints: list[str] = Field(min_length=1, max_length=32)
    approval_policy: Literal["never", "on-request"] = "never"
    sandbox: Literal["read-only", "workspace-write"] = "read-only"
    max_turns: int = Field(ge=1, le=20)
    timeout_seconds: int = Field(ge=30, le=3_600)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    automatic_failure_code: str | None = Field(default=None, max_length=256)
    manual_fallback_selected: bool = False
    requires_explicit_authorization: bool = False


class OperatorTaskRecord(BaseModel):
    task_id: str
    project_id: str
    repository: str
    branch: str
    expected_head: str
    authority_reference: str
    prompt: str
    constraints: list[str]
    approval_policy: str
    sandbox: str
    max_turns: int
    timeout_seconds: int
    idempotency_key: str
    automatic_failure_code: str | None = None
    manual_fallback_selected: bool = False
    requires_explicit_authorization: bool = False
    authorized_at: datetime | None = None
    authorized_by: str | None = None
    dispatch_mode: DispatchMode = DispatchMode.automatic
    status: OperatorTaskStatus = OperatorTaskStatus.pending
    created_at: datetime
    updated_at: datetime
    last_event: str
    blocker: str | None = None
    thread_id: str | None = None
    execution_receipt: str | None = None
    before_head: str | None = None
    after_head: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    verification_receipt: str | None = None
    client_id: str | None = None
    correlation_id: str | None = None
    execution_host_id: str | None = None
    tool_executor_id: str | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dispatch_latency_ms: int | None = None
    executor_duration_ms: int | None = None
    verification_duration_ms: int | None = None
    events: list[TaskEvent] = Field(default_factory=list)


class TaskAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    authority_reference: str = Field(min_length=8, max_length=2_000)
    acknowledgement: Literal["AUTHORIZE_GOVERNED_EXECUTION"]


class ManualDispatchPackage(BaseModel):
    package_receipt: str
    task_id: str
    repository: str
    branch: str
    expected_head: str
    authority_reference: str
    prompt: str
    constraints: list[str]
    approval_policy: str
    sandbox: str
    timeout_seconds: int
    max_turns: int
    idempotency_key: str
    canonical_envelope_sha256: str
    automatic_failure_code: str
    relay_provider_id: str = "codex"
    generated_at: datetime
    automatic_connectivity_acceptance: Literal[False] = False


class ManualDispatchMarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_receipt: str = Field(min_length=12, max_length=128)


class ManualAcknowledgementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_receipt: str = Field(min_length=12, max_length=128)
    thread_reference: str = Field(min_length=4, max_length=512)


class ManualResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_receipt: str = Field(min_length=12, max_length=128)
    thread_reference: str = Field(min_length=4, max_length=512)
    before_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    after_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    result_summary: str = Field(min_length=4, max_length=4_000)
    changed_files: list[str] = Field(max_length=256)
    tests: list[str] = Field(max_length=128)
    evidence: list[str] = Field(max_length=128)


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_receipt: str = Field(min_length=8, max_length=512)
    ci_status: Literal["success", "failed", "pending"]
    verified_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")


class RuntimeCapabilities(BaseModel):
    version: Literal["SELF_HOSTING_OPERATIONAL_LOOP_V1"]
    task_lifecycle: Literal[True] = True
    manual_relay_fallback: Literal[True] = True
    capability_routing: Literal[True] = True
    tool_decision_trace: Literal[True] = True
    planned_actual_reconciliation: Literal[True] = True
    automatic_agents_available: bool
    database_connected: Literal[False] = False
    production_mutation: Literal[False] = False
    secret_values_exposed: Literal[False] = False


class ProjectCapabilityProfile(BaseModel):
    project_id: str
    project_type: str
    domain_tags: list[str]
    stack: list[str]
    required_capabilities: list[str]
    conditional_capabilities: list[str]
    prohibited_capabilities: list[str]
    preferred_adapters: dict[str, list[str]]
    fallback_adapters: dict[str, list[str]]
    environment_boundaries: list[str]
    approval_classes: list[str]
    evidence_requirements: list[str]
    profile_source: str
    profile_version: str


class TaskCapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    project_id: str
    required_capability_ids: list[str] = Field(default_factory=list)
    optional_capability_ids: list[str] = Field(default_factory=list)
    task_type: str = Field(min_length=2, max_length=128)
    mutation_class: Literal["read-only", "source-write", "external-write"]
    environment: Literal["local", "preview", "production"]
    data_classification: Literal["public", "internal", "restricted"]
    acceptance_requirements: list[str] = Field(min_length=1)


class AdapterExclusion(BaseModel):
    adapter_id: str
    reason: str


class ToolSelectionDecision(BaseModel):
    capability_id: str
    selected_adapter_id: str | None
    fallback_adapter_id: str | None
    selected_reason: str
    excluded_adapters_with_reason: list[AdapterExclusion]
    permission_status: PermissionStatus
    approval_required: bool
    invocation_order: int
    evidence_contract: list[str]
    decision_timestamp: datetime
    registry_version: str
    blocked: bool
    substituted: bool


class ToolPlanResponse(BaseModel):
    task_id: str
    project_id: str
    decisions: list[ToolSelectionDecision]
    dispatch_blocked: bool
    blockers: list[str]


class ToolInvocationReceipt(BaseModel):
    invocation_id: str
    task_id: str
    capability_id: str
    adapter_id: str
    status: Literal["completed", "failed", "skipped"]
    evidence: list[str]
    occurred_at: datetime
    tool_call_id: str | None = None
    command_summary: str | None = None
    output_excerpt: str | None = None
    exit_code: int | None = None


class ToolReconciliation(BaseModel):
    task_id: str
    planned_adapter_ids: list[str]
    actual_adapter_ids: list[str]
    missing_adapter_ids: list[str]
    unexpected_adapter_ids: list[str]
    reconciled: bool
