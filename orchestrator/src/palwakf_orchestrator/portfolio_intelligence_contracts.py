from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class TruthState(StrEnum):
    verified = "VERIFIED"
    degraded = "DEGRADED"
    unknown = "UNKNOWN"


class SourceHealthState(StrEnum):
    healthy = "HEALTHY"
    degraded = "DEGRADED"
    unavailable = "UNAVAILABLE"
    unknown = "UNKNOWN"


class SourceHealthItem(BaseModel):
    source_id: str
    label_ar: str
    state: SourceHealthState
    freshness: str
    detail_ar: str
    authority: str
    observed_at: datetime | None = None


class ScoreFactor(BaseModel):
    factor: str
    value: int = Field(ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    explanation_ar: str


class ProjectForecast(BaseModel):
    project_id: str
    status: Literal["AVAILABLE", "CONDITIONAL", "UNAVAILABLE"]
    p50: str | None = None
    p80: str | None = None
    confidence: float = Field(ge=0, le=1)
    conditions_ar: list[str] = Field(default_factory=list)
    basis: str


class ProjectIntelligence(BaseModel):
    project_id: str
    display_name: str
    repository_full_name: str
    truth_state: TruthState
    current_status: str
    readiness: str
    maturity_state: str
    scope_progress_percent: float | None = Field(default=None, ge=0, le=100)
    scope_progress_basis: str
    priority_score: int = Field(ge=0, le=100)
    priority_factors: list[ScoreFactor]
    next_action_ar: str
    blockers: list[str]
    observed_branch: str | None = None
    observed_head: str | None = None
    ci_status: str
    deployment_status: str
    drift_status: str
    evidence_count: int
    task_count: int
    tool_gap_count: int
    last_verified_at: datetime | None = None
    forecast: ProjectForecast
    evidence_refs: list[str] = Field(default_factory=list)


class PortfolioKpi(BaseModel):
    kpi_id: str
    label_ar: str
    value: str
    status: str
    confidence: float = Field(ge=0, le=1)
    explanation_ar: str
    evidence_refs: list[str] = Field(default_factory=list)


class DependencyView(BaseModel):
    edge_id: str
    producer_project_id: str
    consumer_project_id: str
    kind: str
    contract_id: str
    version: str
    status: str
    evidence: list[str]


class CriticalPathView(BaseModel):
    status: Literal["AVAILABLE", "UNAVAILABLE"]
    project_ids: list[str]
    most_blocking_project_id: str | None = None
    reason_ar: str
    evidence_refs: list[str] = Field(default_factory=list)


class PortfolioRecommendation(BaseModel):
    recommendation_id: str
    type: str
    subject_id: str
    reason_ar: str
    evidence_refs: list[str]
    affected_projects: list[str]
    unlock_count: int = Field(ge=0)
    risk_if_deferred_ar: str
    estimated_effort: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    confidence: float = Field(ge=0, le=1)
    status: Literal["PROPOSED"] = "PROPOSED"
    authority: Literal["ADVISORY_ONLY"] = "ADVISORY_ONLY"


class RegistryEntity(BaseModel):
    entity_id: str
    name_ar: str
    category: str
    lifecycle: str
    status: str
    description_ar: str
    owner: str
    evidence_refs: list[str] = Field(default_factory=list)
    deferred_reason_ar: str | None = None
    reopen_trigger_ar: str | None = None


class PortfolioRisk(BaseModel):
    risk_id: str
    severity: str
    subject_id: str
    summary_ar: str
    required_action_ar: str
    evidence_ref: str | None = None


class PortfolioDecision(BaseModel):
    decision_id: str
    kind: str
    project_id: str | None = None
    summary_ar: str
    requires_human_action: bool
    status: str
    authority_reference: str | None = None


class ChangeItem(BaseModel):
    change_id: str
    subject_id: str
    title: str
    detail: str
    occurred_at: datetime
    status: str
    provenance: str


class PortfolioCommandCenterSnapshot(BaseModel):
    schema_version: Literal["PALWAKF_PORTFOLIO_INTELLIGENCE_V1"] = (
        "PALWAKF_PORTFOLIO_INTELLIGENCE_V1"
    )
    generated_at: datetime
    snapshot_id: str
    truth_state: TruthState
    truth_confidence: int = Field(ge=0, le=100)
    truth_explanation_ar: list[str]
    source_health: list[SourceHealthItem]
    kpis: list[PortfolioKpi]
    projects: list[ProjectIntelligence]
    recommendations: list[PortfolioRecommendation]
    dependencies: list[DependencyView]
    critical_path: CriticalPathView
    forecasts: list[ProjectForecast]
    capabilities: list[RegistryEntity]
    skills: list[RegistryEntity]
    tools: list[RegistryEntity]
    agents: list[RegistryEntity]
    providers: list[RegistryEntity]
    risks: list[PortfolioRisk]
    decisions: list[PortfolioDecision]
    recent_changes: list[ChangeItem]
    evidence_refs: list[str]
    authority_notes: list[str] = Field(
        default_factory=lambda: [
            "RECOMMENDATIONS_DO_NOT_AUTHORIZE_EXECUTION",
            "CAPABILITY_IS_NOT_AUTHORITY",
            "UNKNOWN_IS_NOT_FALSE",
            "SOURCE_FAILURE_DOES_NOT_ERASE_LAST_VERIFIED_STATE",
        ]
    )
    provenance: list[str]
