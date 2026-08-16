from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from palwakf_orchestrator.engineering_os_contracts import (
    EngineeringTaskRecord,
    EngineeringTaskStatus,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    OperatorTaskRecord,
    OperatorTaskStatus,
)


class RunStateSignal(StrEnum):
    pending = "PENDING"
    active_execution = "ACTIVE_EXECUTION"
    verification_required = "VERIFICATION_REQUIRED"
    verified_run_available = "VERIFIED_RUN_AVAILABLE"
    execution_failure = "EXECUTION_FAILURE"
    cancelled_run = "CANCELLED_RUN"
    reserved_compatibility_state = "RESERVED_COMPATIBILITY_STATE"


class StateRollupDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_task_id: str
    operator_task_id: str
    parent_status: EngineeringTaskStatus
    run_status: OperatorTaskStatus
    signal: RunStateSignal
    automatic_parent_transition: bool = False
    allowed_explicit_parent_targets: tuple[EngineeringTaskStatus, ...]
    reserved_run_state: bool
    reason: str


class ExplicitRollupAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_task_id: str
    operator_task_id: str
    current_parent_status: EngineeringTaskStatus
    run_status: OperatorTaskStatus
    requested_parent_status: EngineeringTaskStatus
    automatic: bool = False
    requires_explicit_human_authorization: bool = True
    reason: str


_TERMINAL_PARENT_STATUSES = frozenset(
    {
        EngineeringTaskStatus.integrated,
        EngineeringTaskStatus.cancelled,
        EngineeringTaskStatus.superseded,
    }
)

_RESERVED_OPERATOR_STATUSES = frozenset(
    {
        OperatorTaskStatus.awaiting_approval,
        OperatorTaskStatus.drifted,
    }
)

_RUN_STATE_POLICY: dict[
    OperatorTaskStatus,
    tuple[RunStateSignal, tuple[EngineeringTaskStatus, ...], str],
] = {
    OperatorTaskStatus.pending: (
        RunStateSignal.pending,
        (),
        "Pending execution does not alter the parent EngineeringTask state.",
    ),
    OperatorTaskStatus.queued: (
        RunStateSignal.active_execution,
        (),
        "Queued execution is a run-local condition and does not alter the parent state.",
    ),
    OperatorTaskStatus.running: (
        RunStateSignal.active_execution,
        (),
        "Running execution is a run-local condition and does not alter the parent state.",
    ),
    OperatorTaskStatus.awaiting_approval: (
        RunStateSignal.reserved_compatibility_state,
        (),
        (
            "awaiting_approval is preserved as a compatibility state; "
            "Phase4 does not create a producer."
        ),
    ),
    OperatorTaskStatus.failed: (
        RunStateSignal.execution_failure,
        (),
        "A failed execution run does not fail the parent EngineeringTask.",
    ),
    OperatorTaskStatus.pending_verification: (
        RunStateSignal.verification_required,
        (),
        (
            "Executor completion is not parent review readiness until "
            "independent verification succeeds."
        ),
    ),
    OperatorTaskStatus.verified: (
        RunStateSignal.verified_run_available,
        (EngineeringTaskStatus.ready_for_review,),
        (
            "A verified run may support an explicit human decision to mark "
            "the parent ready for review only."
        ),
    ),
    OperatorTaskStatus.drifted: (
        RunStateSignal.reserved_compatibility_state,
        (EngineeringTaskStatus.reconciliation_required,),
        (
            "drifted is preserved as a compatibility state; if encountered, "
            "only an explicit reconciliation decision is eligible."
        ),
    ),
    OperatorTaskStatus.timed_out: (
        RunStateSignal.execution_failure,
        (),
        "A timed-out execution run does not fail the parent EngineeringTask.",
    ),
    OperatorTaskStatus.cancelled: (
        RunStateSignal.cancelled_run,
        (),
        "Cancelling an execution run does not cancel the parent EngineeringTask.",
    ),
}


def operator_state_policy_inventory() -> dict[
    OperatorTaskStatus,
    tuple[RunStateSignal, tuple[EngineeringTaskStatus, ...], str],
]:
    return dict(_RUN_STATE_POLICY)


def evaluate_state_rollup(
    parent: EngineeringTaskRecord,
    run: OperatorTaskRecord,
) -> StateRollupDecision:
    _assert_same_project_and_repository(parent, run)

    signal, explicit_targets, reason = _RUN_STATE_POLICY[run.status]
    if parent.status in _TERMINAL_PARENT_STATUSES:
        explicit_targets = ()
        reason = (
            f"Parent state {parent.status.value} is terminal for this policy; "
            "an execution run cannot reopen or rewrite it."
        )

    return StateRollupDecision(
        parent_task_id=parent.task_id,
        operator_task_id=run.task_id,
        parent_status=parent.status,
        run_status=run.status,
        signal=signal,
        automatic_parent_transition=False,
        allowed_explicit_parent_targets=explicit_targets,
        reserved_run_state=run.status in _RESERVED_OPERATOR_STATUSES,
        reason=reason,
    )


def authorize_explicit_rollup(
    parent: EngineeringTaskRecord,
    run: OperatorTaskRecord,
    requested_parent_status: EngineeringTaskStatus,
) -> ExplicitRollupAuthorization:
    decision = evaluate_state_rollup(parent, run)

    if requested_parent_status == EngineeringTaskStatus.integrated:
        raise GovernanceError("RUN_CANNOT_DIRECTLY_INTEGRATE_PARENT")

    if requested_parent_status not in decision.allowed_explicit_parent_targets:
        raise GovernanceError("EXPLICIT_ROLLUP_TARGET_NOT_ALLOWED_FOR_RUN_STATE")

    return ExplicitRollupAuthorization(
        parent_task_id=parent.task_id,
        operator_task_id=run.task_id,
        current_parent_status=parent.status,
        run_status=run.status,
        requested_parent_status=requested_parent_status,
        automatic=False,
        requires_explicit_human_authorization=True,
        reason=(
            "Policy eligibility only; caller must persist a separately authorized "
            "EngineeringTask transition through an owning workflow."
        ),
    )


def _assert_same_project_and_repository(
    parent: EngineeringTaskRecord,
    run: OperatorTaskRecord,
) -> None:
    if parent.project_id != run.project_id:
        raise GovernanceError("STATE_ROLLUP_PROJECT_DRIFT")
    if parent.repository != run.repository:
        raise GovernanceError("STATE_ROLLUP_REPOSITORY_DRIFT")
