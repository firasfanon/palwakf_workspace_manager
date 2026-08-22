from __future__ import annotations

from pathlib import Path

import pytest

from palwakf_orchestrator.engineering_os_contracts import (
    ActorType,
    CreateEngineeringTaskRequest,
    DependencyMode,
    EngineeringTaskStatus,
    RemoteCheckpointRequest,
)
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskStatus,
    TaskAuthorizationRequest,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore

BASE_HEAD = "a" * 40
REMOTE_HEAD = "b" * 40
RESULT_HEAD = "c" * 40
REPOSITORY = "firasfanon/palwakf_workspace_manager"


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def engineering_request(**overrides: object) -> CreateEngineeringTaskRequest:
    data: dict[str, object] = {
        "task_id": "WM-PHASE1-ENG-001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "title": "Lossless task consolidation phase one",
        "description": "Own one or more execution runs without collapsing task authority.",
        "repository": REPOSITORY,
        "base_sha": BASE_HEAD,
        "task_branch": "task/WM-PHASE1-ENG-001",
        "owner_id": "firas",
        "actor_id": "firas",
        "actor_type": ActorType.human,
        "provider_id": None,
        "scope_patterns": ["orchestrator/**"],
        "depends_on": [],
        "dependency_mode": DependencyMode.independent,
        "risk_class": "HIGH",
        "mutation_class": "source-write",
        "required_capabilities": ["source.control", "runtime.verification"],
        "required_tests": ["parity", "regression"],
    }
    data.update(overrides)
    return CreateEngineeringTaskRequest.model_validate(data)


def operator_request(**overrides: object) -> CreateOperatorTaskRequest:
    data: dict[str, object] = {
        "task_id": "WM_PHASE1_RUN_001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "repository": REPOSITORY,
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": BASE_HEAD,
        "authority_reference": "AUTHORITY://LOSSLESS_TASK_CONSOLIDATION_PHASE_1",
        "prompt": "Execute one bounded run beneath the authoritative engineering task.",
        "constraints": ["NO_AUTHORITY_WIDENING", "NO_PRODUCTION"],
        "approval_policy": "never",
        "sandbox": "read-only",
        "max_turns": 3,
        "timeout_seconds": 120,
        "idempotency_key": "lossless-phase1-run-001",
    }
    data.update(overrides)
    return CreateOperatorTaskRequest.model_validate(data)


def build_services() -> tuple[
    MemoryStateStore,
    EngineeringOsService,
    OperatorService,
    ExecutionRunAdapter,
]:
    store = MemoryStateStore()
    engineering = EngineeringOsService(store)
    operator = OperatorService(
        Path.cwd(),
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    adapter = ExecutionRunAdapter(engineering, operator, store)
    return store, engineering, operator, adapter


def test_pt_rel_001_one_engineering_task_owns_multiple_execution_runs() -> None:
    store, engineering, _, adapter = build_services()
    parent = engineering.create_task(engineering_request())

    first = adapter.create_run(parent.task_id, operator_request())
    second = adapter.create_run(
        parent.task_id,
        operator_request(
            task_id="WM_PHASE1_RUN_002",
            idempotency_key="lossless-phase1-run-002",
        ),
    )

    restored_operator = OperatorService(
        Path.cwd(),
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    restored_adapter = ExecutionRunAdapter(engineering, restored_operator, store)
    restored = restored_adapter.list_runs(parent.task_id)

    assert {item.execution_run_id for item in restored} == {
        first.execution_run_id,
        second.execution_run_id,
    }
    assert all(item.parent_engineering_task_id == parent.task_id for item in restored)
    assert first.execution_run_id == first.legacy_operator_task_id
    assert second.execution_run_id == second.legacy_operator_task_id


def test_pt_rel_002_task_authority_and_run_head_snapshots_remain_distinct() -> None:
    _, engineering, _, adapter = build_services()
    parent = engineering.create_task(engineering_request())
    first = adapter.create_run(parent.task_id, operator_request())

    checkpointed = engineering.checkpoint_task(
        parent.task_id,
        RemoteCheckpointRequest(remote_sha=REMOTE_HEAD, evidence=["checkpoint:phase1"]),
    )
    second = adapter.create_run(
        parent.task_id,
        operator_request(
            task_id="WM_PHASE1_RUN_002",
            expected_head=REMOTE_HEAD,
            idempotency_key="lossless-phase1-run-002",
        ),
    )

    assert checkpointed.base_sha == BASE_HEAD
    assert checkpointed.latest_remote_task_sha == REMOTE_HEAD
    assert first.operator_task.expected_head == BASE_HEAD
    assert second.operator_task.expected_head == REMOTE_HEAD
    assert first.operator_task.expected_head != checkpointed.latest_remote_task_sha


def test_pt_state_005_verified_execution_run_does_not_integrate_parent_task() -> None:
    _, engineering, operator, adapter = build_services()
    parent = engineering.create_task(engineering_request())
    run = adapter.create_run(parent.task_id, operator_request())

    operator_record = operator.get_task(run.legacy_operator_task_id)
    operator_record.status = OperatorTaskStatus.pending_verification
    operator_record.after_head = RESULT_HEAD
    verified = operator.verify_task(
        operator_record.task_id,
        VerificationRequest(
            verification_receipt="verification-phase1",
            ci_status="success",
            verified_head=RESULT_HEAD,
        ),
    )

    assert verified.status == OperatorTaskStatus.verified
    assert engineering.get_task(parent.task_id).status == EngineeringTaskStatus.ready


def test_pt_state_006_failed_execution_run_does_not_fail_parent_task() -> None:
    _, engineering, operator, adapter = build_services()
    parent = engineering.create_task(engineering_request())
    run = adapter.create_run(parent.task_id, operator_request())

    failed = operator.fail_task(run.legacy_operator_task_id, "EXPECTED_PHASE1_FAILURE")

    assert failed.status == OperatorTaskStatus.failed
    assert engineering.get_task(parent.task_id).status == EngineeringTaskStatus.ready


def test_pt_op_008_execution_run_adapter_preserves_operator_capabilities() -> None:
    _, engineering, operator, adapter = build_services()
    parent = engineering.create_task(engineering_request())
    request = operator_request(
        approval_policy="on-request",
        sandbox="workspace-write",
        manual_fallback_selected=True,
        requires_explicit_authorization=True,
    )

    run = adapter.create_run(parent.task_id, request)
    authorized = operator.authorize_task(
        run.legacy_operator_task_id,
        TaskAuthorizationRequest(
            expected_head=BASE_HEAD,
            authority_reference=request.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="governance-user",
    )
    bound = operator.bind_client(
        authorized.task_id,
        client_id="client-phase1",
        correlation_id="corr-phase1",
        execution_host_id="host-phase1",
        tool_executor_id="executor-phase1",
    )
    restored = adapter.get_run(run.execution_run_id)

    assert restored.operator_task.model_dump(mode="json") == bound.model_dump(mode="json")
    assert restored.parent_engineering_task_id == parent.task_id
    assert restored.legacy_operator_task_id == bound.task_id
    assert bound.manual_fallback_selected is True
    assert bound.requires_explicit_authorization is True
    assert bound.execution_host_id == "host-phase1"
    assert bound.tool_executor_id == "executor-phase1"


def test_pt_neg_001_execution_run_adapter_never_widens_parent_authority() -> None:
    _, engineering, operator, adapter = build_services()
    parent = engineering.create_task(engineering_request(mutation_class="read-only"))

    with pytest.raises(GovernanceError, match="EXECUTION_RUN_MUTATION_WIDENS_PARENT_AUTHORITY"):
        adapter.create_run(
            parent.task_id,
            operator_request(sandbox="workspace-write"),
        )

    with pytest.raises(GovernanceError, match="EXECUTION_RUN_HEAD_OUTSIDE_PARENT_AUTHORITY"):
        adapter.create_run(
            parent.task_id,
            operator_request(expected_head=REMOTE_HEAD),
        )

    standalone_request = operator_request(
        task_id="WM_PHASE1_STANDALONE",
        idempotency_key="lossless-phase1-standalone",
    )
    standalone = operator.create_task(standalone_request)
    assert standalone.status == OperatorTaskStatus.pending

    with pytest.raises(GovernanceError, match="EXISTING_OPERATOR_TASK_REQUIRES_SEPARATE_MIGRATION"):
        adapter.create_run(parent.task_id, standalone_request)
