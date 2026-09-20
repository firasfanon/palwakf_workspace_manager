from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.errors import GovernanceError


class SkillAdmissionStage(StrEnum):
    discovered = "DISCOVERED"
    source_verified = "SOURCE_VERIFIED"
    license_verified = "LICENSE_VERIFIED"
    security_reviewed = "SECURITY_REVIEWED"
    sandbox_only = "SANDBOX_ONLY"
    project_proven = "PROJECT_PROVEN"
    cross_project_candidate = "CROSS_PROJECT_CANDIDATE"
    canonical_approved = "CANONICAL_APPROVED"
    hold = "HOLD"
    rejected = "REJECTED"
    quarantined = "QUARANTINED"
    revoked = "REVOKED"


class SkillSourcePin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    path: str = Field(min_length=1, max_length=500)
    content_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    license: str = Field(min_length=1, max_length=160)
    provenance_verified: bool = False


class SkillCapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    filesystem: tuple[str, ...] = ()
    network: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    database: tuple[str, ...] = ()
    production: tuple[str, ...] = ()


class SkillAdmissionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$")
    name: str = Field(min_length=2, max_length=240)
    standard: Literal["AGENT_SKILLS"] = "AGENT_SKILLS"
    source: SkillSourcePin
    requested: SkillCapabilityRequest = Field(default_factory=SkillCapabilityRequest)
    security_findings: tuple[str, ...] = ()
    eval_refs: tuple[str, ...] = ()
    regression_refs: tuple[str, ...] = ()
    mind_review_ref: str | None = None
    workspace_decision_ref: str | None = None
    stage: SkillAdmissionStage = SkillAdmissionStage.quarantined
    external_execution_authority: Literal[False] = False
    auto_promotion: Literal[False] = False


class AuthorityLayer(BaseModel):
    actions: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    filesystem: tuple[str, ...] = ()
    network: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    database: tuple[str, ...] = ()
    production: tuple[str, ...] = ()


class EffectiveSkillAuthority(BaseModel):
    actions: tuple[str, ...]
    tools: tuple[str, ...]
    filesystem: tuple[str, ...]
    network: tuple[str, ...]
    secrets: tuple[str, ...]
    database: tuple[str, ...]
    production: tuple[str, ...]
    fail_closed: Literal[True] = True
    self_authorized: Literal[False] = False


def _intersection(
    requested: tuple[str, ...], layers: tuple[AuthorityLayer, ...], field: str
) -> tuple[str, ...]:
    if not layers:
        raise GovernanceError("AUTHORITY_LAYER_REQUIRED")
    allowed = set(requested)
    for layer in layers:
        allowed &= set(getattr(layer, field))
    return tuple(item for item in requested if item in allowed)


def effective_skill_authority(
    requested: SkillCapabilityRequest,
    *,
    project: AuthorityLayer,
    task: AuthorityLayer,
    agent: AuthorityLayer,
    provider: AuthorityLayer,
    tool: AuthorityLayer,
    environment: AuthorityLayer,
) -> EffectiveSkillAuthority:
    layers = (project, task, agent, provider, tool, environment)
    return EffectiveSkillAuthority(
        actions=_intersection(requested.actions, layers, "actions"),
        tools=_intersection(requested.tools, layers, "tools"),
        filesystem=_intersection(requested.filesystem, layers, "filesystem"),
        network=_intersection(requested.network, layers, "network"),
        secrets=_intersection(requested.secrets, layers, "secrets"),
        database=_intersection(requested.database, layers, "database"),
        production=_intersection(requested.production, layers, "production"),
    )


def assert_skill_loadable(candidate: SkillAdmissionCandidate) -> None:
    if candidate.stage not in {
        SkillAdmissionStage.project_proven,
        SkillAdmissionStage.cross_project_candidate,
        SkillAdmissionStage.canonical_approved,
    }:
        raise GovernanceError("EXTERNAL_SKILL_NOT_ADMITTED")
    if not candidate.source.provenance_verified:
        raise GovernanceError("EXTERNAL_SKILL_PROVENANCE_NOT_VERIFIED")
    if candidate.security_findings:
        raise GovernanceError("EXTERNAL_SKILL_SECURITY_FINDINGS_OPEN")
    if not candidate.eval_refs or not candidate.regression_refs:
        raise GovernanceError("EXTERNAL_SKILL_EVAL_REGRESSION_REQUIRED")
    if candidate.mind_review_ref is None or candidate.workspace_decision_ref is None:
        raise GovernanceError("EXTERNAL_SKILL_REVIEW_DECISION_REQUIRED")


class SkillAuthorityEvaluationRequest(BaseModel):
    requested: SkillCapabilityRequest
    project: AuthorityLayer
    task: AuthorityLayer
    agent: AuthorityLayer
    provider: AuthorityLayer
    tool: AuthorityLayer
    environment: AuthorityLayer

    def evaluate(self) -> EffectiveSkillAuthority:
        return effective_skill_authority(
            self.requested,
            project=self.project,
            task=self.task,
            agent=self.agent,
            provider=self.provider,
            tool=self.tool,
            environment=self.environment,
        )


class WorkspaceSkillDecisionType(StrEnum):
    bounded_pilot_candidate = "BOUNDED_PILOT_CANDIDATE"
    adaptation_required = "ADAPTATION_REQUIRED"
    hold = "HOLD"
    reject = "REJECT"


class WorkspaceSkillAdmissionDecision(BaseModel):
    skill_id: str
    decision: WorkspaceSkillDecisionType
    stage: SkillAdmissionStage
    reasons: tuple[str, ...]
    execution_authority_granted: Literal[False] = False
    canonical_promotion_granted: Literal[False] = False
    separate_execution_authorization_required: Literal[True] = True


def decide_external_skill(
    skill_id: str,
    *,
    mind_decision: str,
    sandbox_pass: bool,
    blocking_findings: tuple[str, ...] = (),
) -> WorkspaceSkillAdmissionDecision:
    reasons: list[str] = []
    if blocking_findings or not sandbox_pass:
        decision = WorkspaceSkillDecisionType.hold
        stage = SkillAdmissionStage.hold
        reasons.append("SANDBOX_OR_SECURITY_GATE_NOT_PASS")
    elif mind_decision == "REJECT":
        decision = WorkspaceSkillDecisionType.reject
        stage = SkillAdmissionStage.rejected
        reasons.append("MIND_REJECTED_CANDIDATE")
    elif mind_decision == "HOLD":
        decision = WorkspaceSkillDecisionType.hold
        stage = SkillAdmissionStage.hold
        reasons.append("MIND_REVIEW_REQUIRES_HOLD")
    elif mind_decision == "REQUIRE_ADAPTATION":
        decision = WorkspaceSkillDecisionType.adaptation_required
        stage = SkillAdmissionStage.hold
        reasons.append("PALWAKF_ADAPTER_REQUIRED_BEFORE_PILOT")
    elif mind_decision == "RECOMMEND_PROJECT_PROVEN":
        decision = WorkspaceSkillDecisionType.bounded_pilot_candidate
        stage = SkillAdmissionStage.sandbox_only
        reasons.append("ELIGIBLE_FOR_SEPARATELY_AUTHORIZED_BOUNDED_PILOT")
    else:
        decision = WorkspaceSkillDecisionType.hold
        stage = SkillAdmissionStage.hold
        reasons.append("UNKNOWN_MIND_DECISION_FAIL_CLOSED")

    return WorkspaceSkillAdmissionDecision(
        skill_id=skill_id,
        decision=decision,
        stage=stage,
        reasons=tuple(reasons),
    )
