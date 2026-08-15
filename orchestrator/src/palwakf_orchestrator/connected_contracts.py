from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskRecord,
    TaskCapabilityRequest,
    VerificationRequest,
)
from palwakf_orchestrator.provider_contracts import RoleAuthority


class ServiceMode(StrEnum):
    local_secure = "LOCAL_SECURE_MODE"
    remote_or_tunnel = "REMOTE_OR_TUNNEL_MODE"


class ServiceScope(StrEnum):
    read = "tasks:read"
    dispatch = "tasks:dispatch"
    continue_task = "tasks:continue"
    cancel = "tasks:cancel"
    verify = "tasks:verify"
    probe = "tools:probe"


class ClientPrincipal(BaseModel):
    client_id: str = Field(min_length=2, max_length=128)
    scopes: frozenset[ServiceScope]

    def require(self, scope: ServiceScope) -> None:
        if scope not in self.scopes:
            raise PermissionError(f"missing required scope: {scope.value}")


class SessionAuthorizationContext(BaseModel):
    client_id: str
    scopes: list[ServiceScope]
    read_only: bool
    can_dispatch: bool
    can_continue: bool
    can_cancel: bool
    can_verify: bool
    can_probe_tools: bool


class ConnectedDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: CreateOperatorTaskRequest
    tool_plan: TaskCapabilityRequest


class ContinueTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_host_id: str = Field(min_length=3, max_length=128)
    tool_executor_id: str = Field(min_length=3, max_length=128)


class ThreadBinding(BaseModel):
    thread_id: str
    task_id: str
    execution_host_id: str
    tool_executor_id: str
    bound_at: datetime


class QueueSnapshot(BaseModel):
    capacity: int
    worker_count: int
    queued: int
    running: int
    available_slots: int
    active_repository_writers: int


class ServiceReadiness(BaseModel):
    service: Literal["palwakf-connected-orchestrator"]
    version: Literal["1.0.0"]
    ready: bool
    mode: ServiceMode
    authentication_configured: bool
    store_healthy: bool
    workers_started: bool
    public_unauthenticated_endpoint: Literal[False] = False


class OperationalMetrics(BaseModel):
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    dispatch_latency_ms: int | None
    executor_duration_ms: int | None
    verification_duration_ms: int | None
    last_successful_executor_execution_at: datetime | None = None
    last_successful_codex_execution_at: datetime | None = None
    store_healthy: bool


class ValueProvenance(StrEnum):
    verified_provider_api = "VERIFIED_PROVIDER_API"
    verified_runtime_probe = "VERIFIED_RUNTIME_PROBE"
    verified_platform_ui = "VERIFIED_PLATFORM_UI"
    user_reported = "USER_REPORTED"
    estimated_from_usage = "ESTIMATED_FROM_USAGE"
    not_exposed_by_provider = "NOT_EXPOSED_BY_PROVIDER"
    not_applicable = "NOT_APPLICABLE"
    stale = "STALE"


class HealthFact(BaseModel):
    value: str | int | float | bool | None
    provenance: ValueProvenance
    observed_at: datetime | None = None
    unit: str | None = None
    note: str | None = None


class ToolOperationalHealth(BaseModel):
    adapter_id: str
    display_name: str
    required: bool
    connection: HealthFact
    authentication: HealthFact
    permission: HealthFact
    entitlement: HealthFact
    quota: HealthFact
    usage: HealthFact
    cost: HealthFact
    balance: HealthFact
    credit_expiry: HealthFact
    renewal: HealthFact
    rate_limit: HealthFact
    freshness: HealthFact
    operator_actions: list[str]
    evidence: list[str]
    role_authorities: dict[str, RoleAuthority] = Field(default_factory=dict)
    secret_values_exposed: Literal[False] = False


class ToolHealthAlertSeverity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"


class ToolHealthAlert(BaseModel):
    alert_id: str
    adapter_id: str
    severity: ToolHealthAlertSeverity
    code: str
    message: str
    operator_action: str
    observed_at: datetime


class ToolProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_evidence: list[str] = Field(default_factory=list, max_length=16)


class ConnectedTaskReceipt(BaseModel):
    task: OperatorTaskRecord
    correlation_id: str
    client_id: str
    transport: Literal["http", "mcp"]


class VerifyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: VerificationRequest
    execution_host_id: str = Field(min_length=3, max_length=128)
    tool_executor_id: str = Field(min_length=3, max_length=128)


class AuditEvent(BaseModel):
    occurred_at: datetime
    correlation_id: str
    client_id: str
    action: str
    outcome: str
    task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
