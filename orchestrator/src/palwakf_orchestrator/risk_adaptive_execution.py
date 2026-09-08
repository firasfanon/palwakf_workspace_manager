from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.errors import GovernanceError


class RiskLevel(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class PilotAction(StrEnum):
    RESUME = "RESUME"
    READ_ONLY_L4_GATE = "READ_ONLY_L4_GATE"
    BOUNDED_TASK_BRANCH_WRITE = "BOUNDED_TASK_BRANCH_WRITE"
    COMMIT_PUSH_PR = "COMMIT_PUSH_PR"
    MAIN_BASELINE_PRODUCTION_DB = "MAIN_BASELINE_PRODUCTION_DB"


class MethodPilotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: PilotAction
    observed_head: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{40}$")


class MethodPilotDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method_id: Literal["PALWAKF_RISK_ADAPTIVE_FIRST_METHOD_PILOT_V1"] = (
        "PALWAKF_RISK_ADAPTIVE_FIRST_METHOD_PILOT_V1"
    )
    risk_level: RiskLevel
    ready: bool
    automatic_execution_allowed: bool
    human_authorization_required: bool
    targeted_revalidation_required: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    visible_message: str
    bootstrap_basis: Literal["EXISTING_GOVERNED_L4_AUTHORITY_PACKAGE"] = (
        "EXISTING_GOVERNED_L4_AUTHORITY_PACKAGE"
    )


class RiskAdaptiveExecutionPilot:
    def classify(self, action: PilotAction) -> RiskLevel:
        if action in {PilotAction.RESUME, PilotAction.READ_ONLY_L4_GATE}:
            return RiskLevel.R0
        if action == PilotAction.BOUNDED_TASK_BRANCH_WRITE:
            return RiskLevel.R1
        if action == PilotAction.COMMIT_PUSH_PR:
            return RiskLevel.R2
        return RiskLevel.R3

    def decide(self, record, request: MethodPilotRequest) -> MethodPilotDecision:
        risk = self.classify(request.action)
        package = record.authority_package
        blockers: list[str] = []
        revalidate: list[str] = []

        if not package.authority_reference:
            blockers.append("AUTHORITY_REFERENCE_MISSING")
        if not package.project_id or not package.task_id or not package.repository:
            blockers.append("GOVERNED_IDENTITY_INCOMPLETE")

        if risk in {RiskLevel.R1, RiskLevel.R2, RiskLevel.R3}:
            revalidate.extend(("EXPECTED_HEAD", "TASK_BRANCH", "AUTHORIZED_SCOPE"))
            if request.observed_head is None:
                blockers.append("FRESH_HEAD_OBSERVATION_REQUIRED")
            elif request.observed_head.lower() != package.expected_head.lower():
                blockers.append("EXPECTED_HEAD_DRIFT")

        if risk == RiskLevel.R3:
            return MethodPilotDecision(
                risk_level=risk,
                ready=False,
                automatic_execution_allowed=False,
                human_authorization_required=True,
                targeted_revalidation_required=tuple(revalidate),
                blockers=tuple(blockers or ["EXPLICIT_HIGH_IMPACT_AUTHORIZATION_REQUIRED"]),
                visible_message="يتطلب هذا الإجراء تفويضًا بشريًا صريحًا عالي الأثر.",
            )

        if blockers:
            return MethodPilotDecision(
                risk_level=risk,
                ready=False,
                automatic_execution_allowed=False,
                human_authorization_required=False,
                targeted_revalidation_required=tuple(revalidate),
                blockers=tuple(blockers),
                visible_message=f"BLOCKED: {blockers[0]}",
            )

        return MethodPilotDecision(
            risk_level=risk,
            ready=True,
            automatic_execution_allowed=True,
            human_authorization_required=False,
            targeted_revalidation_required=tuple(revalidate),
            blockers=(),
            visible_message="READY",
        )

    def require_ready(self, record, request: MethodPilotRequest) -> MethodPilotDecision:
        decision = self.decide(record, request)
        if not decision.ready:
            raise GovernanceError(f"METHOD_PILOT_BLOCKED:{decision.blockers[0]}")
        return decision
