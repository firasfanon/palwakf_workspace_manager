from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from palwakf_orchestrator.engineering_os_contracts import (
    ActorType,
    CreateEngineeringTaskRequest,
    DependencyMode,
    EngineeringTaskRecord,
    EngineeringTaskStatus,
    RemoteCheckpointRequest,
)
from palwakf_orchestrator.engineering_os_service import TASKS_KEY, EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskRecord,
    OperatorTaskStatus,
    TaskAuthorizationRequest,
    TaskEvent,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore

BASE_HEAD = "a" * 40
REMOTE_HEAD = "b" * 40
RESULT_HEAD = "c" * 40


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def engineering_request(**overrides: object) -> CreateEngineeringTaskRequest:
    data: dict[str, object] = {
        "task_id": "WM-PARITY-ENG-001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "title": "Capability preservation baseline",
        "description": "Preserve engineering task authority and lifecycle semantics.",
        "repository": "firasfanon/palwakf_workspace_manager",
        "base_sha": BASE_HEAD.upper(),
        "task_branch": "task/WM-PARITY-ENG-001",
        "owner_id": "firas",
        "actor_id": "firas",
        "actor_type": ActorType.human,
        "provider_id": None,
        "scope_patterns": ["lib/**", "orchestrator/**"],
        "depends_on": [],
        "dependency_mode": DependencyMode.independent,
        "risk_class": "HIGH",
        "mutation_class": "source-write",
        "required_capabilities": ["source.control", "runtime.verification"],
        "required_tests": ["targeted", "regression"],
    }
    data.update(overrides)
    return CreateEngineeringTaskRequest.model_validate(data)


def operator_request(**overrides: object) -> CreateOperatorTaskRequest:
    data: dict[str, object] = {
        "task_id": "WM_PARITY_OP_001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "repository": "firasfanon/palwakf_workspace_manager",
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": BASE_HEAD,
        "authority_reference": "AUTHORITY://CAPABILITY_PRESERVATION_V1",
        "prompt": "Execute the bounded parity preservation task without widening authority.",
        "constraints": ["NO_PRODUCTION", "NO_SECRET_ACCESS"],
        "approval_policy": "never",
        "sandbox": "read-only",
        "max_turns": 3,
        "timeout_seconds": 120,
        "idempotency_key": "capability-preservation-op-001",
    }
    data.update(overrides)
    return CreateOperatorTaskRequest.model_validate(data)


def engineering_record(
    *,
    task_id: str,
    status: EngineeringTaskStatus,
    base_sha: str = BASE_HEAD,
    remote_sha: str | None = REMOTE_HEAD,
) -> EngineeringTaskRecord:
    now = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
    return EngineeringTaskRecord(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        title=f"Parity {status.value}",
        description="Full engineering record round-trip fixture.",
        repository="firasfanon/palwakf_workspace_manager",
        base_sha=base_sha,
        integrated_head_at_creation=base_sha,
        task_branch=f"task/{task_id}",
        latest_remote_task_sha=remote_sha,
        owner_id="firas",
        actor_id="agent-a",
        actor_type=ActorType.agent,
        provider_id="provider-a",
        scope_patterns=["lib/**", "orchestrator/**"],
        depends_on=["WM-UPSTREAM-001"],
        dependency_mode=DependencyMode.stacked,
        risk_class="CRITICAL",
        mutation_class="source-write",
        required_capabilities=["source.control", "evidence.capture"],
        required_tests=["targeted", "regression", "browser-uat"],
        status=status,
        wip_checkpoint_status="REMOTE_CHECKPOINTED",
        integration_status="RECONCILIATION_REQUIRED",
        evidence=["evidence:one", "evidence:two"],
        created_at=now,
        updated_at=now,
    )


def operator_record(*, task_id: str, status: OperatorTaskStatus) -> OperatorTaskRecord:
    now = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
    event = TaskEvent(
        event_type="PARITY_FIXTURE",
        status=status,
        message="Preserve this event exactly.",
        occurred_at=now,
        correlation_id="corr-parity",
        client_id="client-parity",
    )
    return OperatorTaskRecord(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository="firasfanon/palwakf_workspace_manager",
        branch="agent/workspace-manager-foundation-v1",
        expected_head=REMOTE_HEAD,
        authority_reference="AUTHORITY://CAPABILITY_PRESERVATION_V1",
        prompt="Preserve the complete operator execution record during consolidation.",
        constraints=["NO_PRODUCTION", "NO_SECRET_ACCESS"],
        approval_policy="on-request",
        sandbox="workspace-write",
        max_turns=7,
        timeout_seconds=900,
        idempotency_key=f"parity-{task_id.lower()}",
        automatic_failure_code="CHANNEL_UNAVAILABLE",
        manual_fallback_selected=True,
        requires_explicit_authorization=True,
        authorized_at=now,
        authorized_by="governance-user",
        status=status,
        created_at=now,
        updated_at=now,
        last_event=event.event_type,
        blocker="PARITY_BLOCKER",
        thread_id="thread-parity",
        execution_receipt="receipt-parity",
        before_head=REMOTE_HEAD,
        after_head=RESULT_HEAD,
        changed_files=["orchestrator/a.py", "lib/b.dart"],
        tests=["pytest:pass", "flutter test:pass"],
        evidence=["evidence/run.json"],
        verification_receipt="verification-parity",
        client_id="client-parity",
        correlation_id="corr-parity",
        execution_host_id="host-parity",
        tool_executor_id="tool-parity",
        queued_at=now,
        started_at=now,
        completed_at=now,
        dispatch_latency_ms=11,
        executor_duration_ms=22,
        verification_duration_ms=33,
        events=[event],
    )


def _operator_state(records: list[OperatorTaskRecord]) -> dict[str, object]:
    return {
        "operator": {
            "tasks": {item.task_id: item.model_dump(mode="json") for item in records},
            "idempotency_tasks": {item.idempotency_key: item.task_id for item in records},
            "manual_packages": {},
            "tool_plans": {},
            "invocations": {},
        }
    }


def test_pt_fld_001_engineering_full_record_round_trip() -> None:
    store = MemoryStateStore()
    original = engineering_record(
        task_id="WM-PARITY-FLD-001",
        status=EngineeringTaskStatus.reconciliation_required,
    )
    store.save({TASKS_KEY: {original.task_id: original.model_dump(mode="json")}})

    restored = EngineeringOsService(store).get_task(original.task_id)

    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_pt_fld_002_operator_full_record_round_trip() -> None:
    store = MemoryStateStore()
    original = operator_record(task_id="WM_PARITY_FLD_002", status=OperatorTaskStatus.drifted)
    store.save(_operator_state([original]))

    restored = OperatorService(
        Path.cwd(),
        verifier=AcceptingVerifier(),
        state_store=store,
    ).get_task(original.task_id)

    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_pt_sem_001_task_base_sha_and_run_expected_head_remain_distinct() -> None:
    task = engineering_record(
        task_id="WM-PARITY-SEM-001",
        status=EngineeringTaskStatus.wip_remote_checkpointed,
        base_sha=BASE_HEAD,
        remote_sha=REMOTE_HEAD,
    )
    run = operator_record(task_id="WM_PARITY_SEM_001", status=OperatorTaskStatus.pending)

    assert task.base_sha == BASE_HEAD
    assert task.latest_remote_task_sha == REMOTE_HEAD
    assert run.expected_head == REMOTE_HEAD
    assert task.base_sha != run.expected_head


def test_pt_sem_002_task_goal_fields_do_not_collapse_into_run_execution_fields() -> None:
    task = engineering_record(
        task_id="WM-PARITY-SEM-002",
        status=EngineeringTaskStatus.ready,
    )
    run = operator_record(task_id="WM_PARITY_SEM_002", status=OperatorTaskStatus.pending)

    assert task.description != run.prompt
    assert task.scope_patterns != run.constraints
    assert task.required_tests != run.tests


def test_pt_eng_003_terminal_engineering_states_reject_remote_checkpoint() -> None:
    for index, status in enumerate(
        (
            EngineeringTaskStatus.integrated,
            EngineeringTaskStatus.cancelled,
            EngineeringTaskStatus.superseded,
        ),
        start=1,
    ):
        store = MemoryStateStore()
        record = engineering_record(task_id=f"WM-PARITY-TERM-{index}", status=status)
        store.save({TASKS_KEY: {record.task_id: record.model_dump(mode="json")}})
        service = EngineeringOsService(store)

        with pytest.raises(GovernanceError, match="TASK_STATE_REJECTS_WIP_CHECKPOINT"):
            service.checkpoint_task(
                record.task_id,
                RemoteCheckpointRequest(remote_sha=RESULT_HEAD, evidence=["guard"]),
            )


def test_pt_state_001_all_engineering_statuses_are_persistable_and_readable() -> None:
    store = MemoryStateStore()
    records = {
        f"WM-PARITY-ENG-STATE-{index}": engineering_record(
            task_id=f"WM-PARITY-ENG-STATE-{index}",
            status=status,
        )
        for index, status in enumerate(EngineeringTaskStatus)
    }
    store.save({TASKS_KEY: {key: value.model_dump(mode="json") for key, value in records.items()}})

    restored = EngineeringOsService(store).list_tasks()

    assert {item.status for item in restored} == set(EngineeringTaskStatus)


def test_pt_state_002_all_operator_statuses_are_persistable_and_readable() -> None:
    records = [
        operator_record(task_id=f"WM_PARITY_OP_STATE_{index}", status=status)
        for index, status in enumerate(OperatorTaskStatus)
    ]
    store = MemoryStateStore()
    store.save(_operator_state(records))

    restored = OperatorService(
        Path.cwd(),
        verifier=AcceptingVerifier(),
        state_store=store,
    ).list_tasks()

    assert {item.status for item in restored} == set(OperatorTaskStatus)


def test_pt_state_003_awaiting_approval_remains_continuable_to_pending() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    task = service.create_task(operator_request(task_id="WM_PARITY_AWAITING_APPROVAL"))
    task.status = OperatorTaskStatus.awaiting_approval
    event_count = len(task.events)

    continued = service.continue_task(task.task_id)

    assert continued.status == OperatorTaskStatus.pending
    assert continued.last_event == "TASK_CONTINUED"
    assert len(continued.events) == event_count + 1


def test_pt_state_004_drifted_remains_readable_without_synthetic_transition() -> None:
    record = operator_record(task_id="WM_PARITY_DRIFTED", status=OperatorTaskStatus.drifted)
    store = MemoryStateStore()
    store.save(_operator_state([record]))
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier(), state_store=store)

    observed = service.get_task(record.task_id)

    assert observed.status == OperatorTaskStatus.drifted
    assert observed.last_event == "PARITY_FIXTURE"
    with pytest.raises(GovernanceError, match="not in a continuable state"):
        service.continue_task(record.task_id)


def test_pt_eng_004_declared_unproduced_engineering_states_remain_distinct() -> None:
    reserved = {
        EngineeringTaskStatus.planned,
        EngineeringTaskStatus.in_progress,
        EngineeringTaskStatus.blocked_dependency,
        EngineeringTaskStatus.ready_for_review,
        EngineeringTaskStatus.ready_for_integration,
        EngineeringTaskStatus.in_merge_queue,
        EngineeringTaskStatus.reconciliation_required,
        EngineeringTaskStatus.integrated,
        EngineeringTaskStatus.failed,
        EngineeringTaskStatus.cancelled,
        EngineeringTaskStatus.superseded,
    }

    assert len(reserved) == 11
    assert reserved.issubset(set(EngineeringTaskStatus))
    assert EngineeringTaskStatus.ready not in reserved
    assert EngineeringTaskStatus.wip_remote_checkpointed not in reserved


def test_pt_op_003_authorization_is_bound_to_head_and_authority_reference() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    task = service.create_task(
        operator_request(
            task_id="WM_PARITY_AUTHORIZATION",
            requires_explicit_authorization=True,
        )
    )

    with pytest.raises(GovernanceError, match="HEAD"):
        service.authorize_task(
            task.task_id,
            TaskAuthorizationRequest(
                expected_head=REMOTE_HEAD,
                authority_reference=task.authority_reference,
                acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
            ),
            principal_id="tester",
        )
    with pytest.raises(GovernanceError, match="reference"):
        service.authorize_task(
            task.task_id,
            TaskAuthorizationRequest(
                expected_head=task.expected_head,
                authority_reference="AUTHORITY://DIFFERENT_REFERENCE",
                acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
            ),
            principal_id="tester",
        )

    first = service.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=task.expected_head,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="tester",
    )
    event_count = len(first.events)
    second = service.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=task.expected_head,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="tester",
    )

    assert first.authorized_by == "tester"
    assert first.authorized_at is not None
    assert len(second.events) == event_count


def test_pt_op_005_queue_and_start_preserve_timing_and_event_lineage() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    task = service.create_task(operator_request(task_id="WM_PARITY_TIMING"))

    queued = service.queue_task(task.task_id)
    started = service.start_task(task.task_id)

    assert queued.queued_at is not None
    assert started.started_at is not None
    assert started.dispatch_latency_ms is not None
    assert [event.event_type for event in started.events][-2:] == [
        "TASK_QUEUED",
        "TASK_EXECUTION_STARTED",
    ]


def test_pt_op_006_restart_recovery_preserves_failure_cause_and_history() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    task = service.create_task(operator_request(task_id="WM_PARITY_RECOVERY"))
    service.queue_task(task.task_id)
    service.start_task(task.task_id)

    recovered = service.recover_interrupted_tasks()
    restored = service.get_task(task.task_id)

    assert recovered == [task.task_id]
    assert restored.status == OperatorTaskStatus.failed
    assert restored.blocker == "SERVICE_RESTART_INTERRUPTED_EXECUTION"
    assert restored.last_event == "TASK_RECOVERED_AFTER_RESTART"


def test_pt_op_009_continue_remains_restricted_to_current_compatible_states() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    failed = service.create_task(operator_request(task_id="WM_PARITY_CONTINUE_FAILED"))
    service.fail_task(failed.task_id, "EXPECTED_FAILURE")
    assert service.continue_task(failed.task_id).status == OperatorTaskStatus.pending

    pending = service.create_task(
        operator_request(
            task_id="WM_PARITY_CONTINUE_PENDING",
            idempotency_key="capability-preservation-op-continue-pending",
        )
    )
    with pytest.raises(GovernanceError, match="not in a continuable state"):
        service.continue_task(pending.task_id)


def test_pt_op_011_verification_requires_exact_head_and_successful_ci() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    task = service.create_task(operator_request(task_id="WM_PARITY_VERIFY"))
    task.status = OperatorTaskStatus.pending_verification
    task.after_head = RESULT_HEAD

    with pytest.raises(GovernanceError, match="HEAD"):
        service.verify_task(
            task.task_id,
            VerificationRequest(
                verification_receipt="receipt-wrong-head",
                ci_status="success",
                verified_head=REMOTE_HEAD,
            ),
        )
    with pytest.raises(GovernanceError, match="CI"):
        service.verify_task(
            task.task_id,
            VerificationRequest(
                verification_receipt="receipt-pending-ci",
                ci_status="pending",
                verified_head=RESULT_HEAD,
            ),
        )

    verified = service.verify_task(
        task.task_id,
        VerificationRequest(
            verification_receipt="receipt-success",
            ci_status="success",
            verified_head=RESULT_HEAD,
        ),
    )
    assert verified.status == OperatorTaskStatus.verified
    assert verified.verification_receipt == "receipt-success"


def test_pt_hist_001_event_lineage_keeps_identity_and_order() -> None:
    service = OperatorService(Path.cwd(), verifier=AcceptingVerifier())
    task = service.create_task(
        operator_request(
            task_id="WM_PARITY_HISTORY",
            requires_explicit_authorization=True,
        )
    )
    service.bind_client(
        task.task_id,
        client_id="client-history",
        correlation_id="corr-history",
        execution_host_id="host-history",
        tool_executor_id="tool-history",
    )
    service.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=task.expected_head,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="tester",
    )
    service.queue_task(task.task_id)
    service.start_task(task.task_id)
    service.fail_task(task.task_id, "EXPECTED_FAILURE")

    restored = service.get_task(task.task_id)
    assert [event.event_type for event in restored.events] == [
        "TASK_CREATED",
        "TASK_AUTHORIZED",
        "TASK_QUEUED",
        "TASK_EXECUTION_STARTED",
        "TASK_EXECUTION_FAILED",
    ]
    assert all(event.correlation_id == "corr-history" for event in restored.events[1:])
    assert all(event.client_id == "client-history" for event in restored.events[1:])
