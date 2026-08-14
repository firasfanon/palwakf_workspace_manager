from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from palwakf_orchestrator.local_product import ManagedWorkspaceStatus


class FreshnessState(StrEnum):
    fresh = "FRESH"
    stale = "STALE"
    unknown = "UNKNOWN"


class PortfolioProjectSummary(BaseModel):
    project_id: str
    display_name: str
    repository_full_name: str
    status: str
    readiness: str
    attention_required: bool
    observed_branch: str | None
    observed_head: str | None
    last_probe_at: datetime | None
    freshness: FreshnessState
    stack: list[str]
    package_managers: list[str]
    ci_status: str
    deployment_status: str
    drift_status: str
    blockers: list[str]
    tool_gap_count: int
    top_candidate_id: str | None
    top_candidate_title: str | None
    task_count: int
    active_writer: bool
    evidence_count: int
    provenance: Literal["EXTERNAL_PROJECT_REGISTRY", "LOCAL_MANAGED_WORKSPACE"] = (
        "EXTERNAL_PROJECT_REGISTRY"
    )


class TaskStatusSummary(BaseModel):
    total: int
    pending: int
    queued: int
    running: int
    awaiting_approval: int
    failed: int
    pending_verification: int
    verified: int
    drifted: int
    timed_out: int
    cancelled: int
    stale: int
    active_task_ids: list[str]
    latest_verified_task_id: str | None
    latest_verified_at: datetime | None
    provenance: Literal[
        "OPERATOR_TASK_STORE",
        "UNIFIED_OPERATOR_AND_ENGINEERING_OS_TASK_STORES",
    ] = "OPERATOR_TASK_STORE"


class ToolHealthSummary(BaseModel):
    total: int
    healthy: int
    degraded: int
    blocked: int
    stale: int
    unknown: int
    required_attention: int
    provenance: Literal["TOOL_HEALTH_STORE"] = "TOOL_HEALTH_STORE"


class OperationalAlertSummary(BaseModel):
    alert_id: str
    severity: Literal["info", "warning", "critical"]
    source_kind: Literal["tool", "project", "task", "connection"]
    source_id: str
    code: str
    message: str
    required_action: str
    observed_at: datetime
    freshness: FreshnessState
    evidence_reference: str | None = None


class RecentActivityItem(BaseModel):
    activity_id: str
    kind: Literal["task_event", "project_probe", "audit"]
    subject_id: str
    title: str
    detail: str
    occurred_at: datetime
    status: str
    provenance: str


class ResumeCheckpointSummary(BaseModel):
    checkpoint_id: str
    task_id: str
    status: str
    updated_at: datetime
    next_action: str
    evidence_reference: str | None = None


class ConnectionReadinessSummary(BaseModel):
    mode: str
    ready: bool
    authentication_configured: bool
    store_healthy: bool
    workers_started: bool
    local_secure: bool
    public_unauthenticated_endpoint: Literal[False] = False
    chatgpt_live_state: Literal["PENDING_NOT_ACTIVATED"] = "PENDING_NOT_ACTIVATED"
    execution_host_compatibility: Literal["CURRENT_RUNTIME_BOUND"] = "CURRENT_RUNTIME_BOUND"
    tool_executor_compatibility: Literal["CURRENT_RUNTIME_BOUND"] = "CURRENT_RUNTIME_BOUND"
    last_successful_codex_execution_at: datetime | None


class EvidenceIndexItem(BaseModel):
    evidence_id: str
    association_kind: Literal["task", "project", "workspace"]
    association_id: str | None
    evidence_type: str
    observed_at: datetime | None
    fingerprint: str | None
    safe_reference: str
    status: str
    provenance: Literal["REPOSITORY_EVIDENCE", "TASK_STORE"]


class DashboardAction(BaseModel):
    action_id: str
    label: str
    route: str
    enabled: bool
    disabled_reason: str | None = None
    authority: str


class DashboardSummary(BaseModel):
    generated_at: datetime
    freshness: FreshnessState
    portfolio_total: int
    portfolio_ready: int
    portfolio_attention_required: int
    active_repository_writers: int
    human_action_required: int
    tasks: TaskStatusSummary
    tools: ToolHealthSummary
    alert_count: int
    critical_alert_count: int
    projects: list[PortfolioProjectSummary]
    connection: ConnectionReadinessSummary
    checkpoints: list[ResumeCheckpointSummary]
    actions: list[DashboardAction]
    managed_workspace: ManagedWorkspaceStatus | None = None
    provenance: list[str] = Field(
        default_factory=lambda: [
            "OPERATOR_TASK_STORE",
            "EXTERNAL_PROJECT_REGISTRY",
            "TOOL_HEALTH_STORE",
            "CONNECTED_SERVICE_READINESS",
        ]
    )
