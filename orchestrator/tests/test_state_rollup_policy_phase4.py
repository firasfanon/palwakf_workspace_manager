from __future__ import annotations

from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.engineering_os_contracts import (
    ActorType,
    DependencyMode,
    EngineeringTaskRecord,
    EngineeringTaskStatus,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    DispatchMode,
    OperatorTaskRecord,
    OperatorTaskStatus,
)
from palwakf_orchestrator.state_rollup_policy import (
    RunStateSignal,
    authorize_explicit_rollup,
    evaluate_state_rollup,
    operator_state_policy_inventory,
)

REPOSITORY = "firasfanon/palwakf_workspace_manager"
HEAD_A = "a" * 40
HEAD_B = "b" * 40
NOW = datetime(2026, 8, 17, 1, 48, tzinfo=UTC)


def engineering_record(**overrides: object) -> EngineeringTaskRecord:
    data: dict[str, object] = {
        "task_id": "WM-PHASE4-ENG-001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "title": "Explicit state roll-up policy",
        "description": "Keep EngineeringTask and execution-run state machines separate.",
        "repository": REPOSITORY,
        "base_sha": HEAD_A,
        "integrated_head_at_creation": HEAD_A,
        "task_branch": "task/WM-STATE-SEMANTICS-ROLLUP-POLICY-PHASE4-V1",
        "latest_remote_task_sha": HEAD_B,
        "owner_id": "firas",
        "actor_id": "firas",
        "actor_type": ActorType.human,
        "provider_id": None,
        "scope_patterns": ["orchestrator/**"],
        "depends_on": [],
        "dependency_mode": DependencyMode.independent,
        "risk_class": "HIGH",
        "mutation_class": "source-write",
        "required_capabilities": ["state.policy"],
        "required_tests": ["parity", "regression"],
        "status": EngineeringTaskStatus.wip_remote_checkpointed,
        "wip_checkpoint_status": "REMOTE_CHECKPOINTED",
        "integration_status": "NOT_READY",
        "evidence": ["phase4-parent-evidence"],
        "created_at": NOW,
        "updated_at": NOW,
    }
    data.update(overrides)
    return EngineeringTaskRecord.model_validate(data)


def operator_record(
    status: OperatorTaskStatus,
    **overrides: object,
) -> OperatorTaskRecord:
    data: dict[str, object] = {
        "task_id": f"WM_PHASE4_RUN_{status.value.upper()}",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "repository": REPOSITORY,
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": HEAD_A,
        "authority_reference": "AUTHORITY://PHASE4_STATE_POLICY",
        "prompt": "Evaluate state policy without mutating the parent task.",
        "constraints": ["NO_AUTO_ROLLUP", "NO_UI", "NO_MIGRATION"],
        "approval_policy": "never",
        "sandbox": "read-only",
        "max_turns": 3,
        "timeout_seconds": 300,
        "idempotency_key": f"phase4-state-{status.value}",
        "automatic_failure_code": None,
        "manual_fallback_selected": False,
        "requires_explicit_authorization": False,
        "authorized_at": None,
        "authorized_by": None,
        "dispatch_mode": DispatchMode.automatic,
        "status": status,
        "created_at": NOW,
        "updated_at": NOW,
        "last_event": "PHASE4_FIXTURE",
        "blocker": None,
        "thread_id": None,
        "execution_receipt": None,
        "before_head": None,
        "after_head": None,
        "changed_files": [],
        "tests": [],
        "evidence": ["phase4-run-evidence"],
        "verification_receipt": None,
        "client_id": None,
        "correlation_id": None,
        "execution_host_id": None,
        "tool_executor_id": None,
        "queued_at": None,
        "started_at": None,
        "completed_at": None,
        "dispatch_latency_ms": None,
        "executor_duration_ms": None,
        "verification_duration_ms": None,
        "events": [],
    }
    data.update(overrides)
    return OperatorTaskRecord.model_validate(data)


def test_cpm09_policy_covers_every_operator_status_exactly() -> None:
    inventory = operator_state_policy_inventory()
    assert set(inventory) == set(OperatorTaskStatus)
    assert len(inventory) == len(OperatorTaskStatus)


def test_cpm09_pending_queued_running_never_auto_transition_parent() -> None:
    parent = engineering_record()
    for status in (
        OperatorTaskStatus.pending,
        OperatorTaskStatus.queued,
        OperatorTaskStatus.running,
    ):
        decision = evaluate_state_rollup(parent, operator_record(status))
        assert decision.automatic_parent_transition is False
        assert decision.allowed_explicit_parent_targets == ()


def test_cpm09_failed_and_timed_out_runs_do_not_fail_parent() -> None:
    parent = engineering_record()
    for status in (OperatorTaskStatus.failed, OperatorTaskStatus.timed_out):
        decision = evaluate_state_rollup(parent, operator_record(status))
        assert decision.signal == RunStateSignal.execution_failure
        assert decision.parent_status == EngineeringTaskStatus.wip_remote_checkpointed
        assert EngineeringTaskStatus.failed not in decision.allowed_explicit_parent_targets


def test_cpm09_cancelled_run_does_not_cancel_parent() -> None:
    parent = engineering_record()
    decision = evaluate_state_rollup(parent, operator_record(OperatorTaskStatus.cancelled))
    assert decision.signal == RunStateSignal.cancelled_run
    assert EngineeringTaskStatus.cancelled not in decision.allowed_explicit_parent_targets
    assert decision.parent_status == parent.status


def test_cpm09_pending_verification_is_not_review_ready() -> None:
    decision = evaluate_state_rollup(
        engineering_record(),
        operator_record(OperatorTaskStatus.pending_verification),
    )
    assert decision.signal == RunStateSignal.verification_required
    assert decision.allowed_explicit_parent_targets == ()


def test_cpm09_verified_run_allows_explicit_review_only() -> None:
    parent = engineering_record()
    run = operator_record(OperatorTaskStatus.verified)
    decision = evaluate_state_rollup(parent, run)
    assert decision.automatic_parent_transition is False
    assert decision.allowed_explicit_parent_targets == (EngineeringTaskStatus.ready_for_review,)
    authorization = authorize_explicit_rollup(
        parent,
        run,
        EngineeringTaskStatus.ready_for_review,
    )
    assert authorization.automatic is False
    assert authorization.requires_explicit_human_authorization is True


def test_cpm09_verified_run_cannot_directly_integrate_or_skip_review() -> None:
    parent = engineering_record()
    run = operator_record(OperatorTaskStatus.verified)
    with pytest.raises(GovernanceError, match="RUN_CANNOT_DIRECTLY_INTEGRATE_PARENT"):
        authorize_explicit_rollup(parent, run, EngineeringTaskStatus.integrated)
    with pytest.raises(
        GovernanceError,
        match="EXPLICIT_ROLLUP_TARGET_NOT_ALLOWED_FOR_RUN_STATE",
    ):
        authorize_explicit_rollup(
            parent,
            run,
            EngineeringTaskStatus.ready_for_integration,
        )


def test_cpm23_awaiting_approval_remains_nonproducing_compatibility_state() -> None:
    decision = evaluate_state_rollup(
        engineering_record(),
        operator_record(OperatorTaskStatus.awaiting_approval),
    )
    assert decision.reserved_run_state is True
    assert decision.signal == RunStateSignal.reserved_compatibility_state
    assert decision.allowed_explicit_parent_targets == ()
    assert "does not create a producer" in decision.reason


def test_cpm23_drifted_only_allows_explicit_reconciliation() -> None:
    parent = engineering_record()
    run = operator_record(OperatorTaskStatus.drifted)
    decision = evaluate_state_rollup(parent, run)
    assert decision.reserved_run_state is True
    assert decision.allowed_explicit_parent_targets == (
        EngineeringTaskStatus.reconciliation_required,
    )
    authorization = authorize_explicit_rollup(
        parent,
        run,
        EngineeringTaskStatus.reconciliation_required,
    )
    assert authorization.requires_explicit_human_authorization is True
    assert authorization.automatic is False


def test_cpm09_terminal_parent_states_cannot_be_reopened_by_run_policy() -> None:
    for parent_status in (
        EngineeringTaskStatus.integrated,
        EngineeringTaskStatus.cancelled,
        EngineeringTaskStatus.superseded,
    ):
        parent = engineering_record(status=parent_status)
        for run_status in (
            OperatorTaskStatus.verified,
            OperatorTaskStatus.drifted,
        ):
            decision = evaluate_state_rollup(parent, operator_record(run_status))
            assert decision.allowed_explicit_parent_targets == ()
            assert decision.automatic_parent_transition is False


def test_cpm09_policy_evaluation_is_read_only() -> None:
    parent = engineering_record()
    run = operator_record(
        OperatorTaskStatus.verified,
        verification_receipt="verify-phase4",
        after_head=HEAD_B,
    )
    parent_before = parent.model_dump(mode="json")
    run_before = run.model_dump(mode="json")
    _ = evaluate_state_rollup(parent, run)
    _ = authorize_explicit_rollup(
        parent,
        run,
        EngineeringTaskStatus.ready_for_review,
    )
    assert parent.model_dump(mode="json") == parent_before
    assert run.model_dump(mode="json") == run_before


def test_cpm09_cross_layer_project_and_repository_drift_fail_closed() -> None:
    parent = engineering_record()
    with pytest.raises(GovernanceError, match="STATE_ROLLUP_PROJECT_DRIFT"):
        evaluate_state_rollup(
            parent,
            operator_record(
                OperatorTaskStatus.verified,
                project_id="OTHER_PROJECT",
            ),
        )
    with pytest.raises(GovernanceError, match="STATE_ROLLUP_REPOSITORY_DRIFT"):
        evaluate_state_rollup(
            parent,
            operator_record(
                OperatorTaskStatus.verified,
                repository="other/repository",
            ),
        )
