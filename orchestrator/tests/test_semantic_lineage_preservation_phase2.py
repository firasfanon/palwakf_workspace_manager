from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

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
    TaskEvent,
)
from palwakf_orchestrator.semantic_lineage_projection import (
    build_semantic_lineage_projection,
)

BASE_HEAD = "a" * 40
INTEGRATED_HEAD = "b" * 40
REMOTE_HEAD = "c" * 40
EXPECTED_HEAD = "d" * 40
BEFORE_HEAD = "e" * 40
AFTER_HEAD = "f" * 40
REPOSITORY = "firasfanon/palwakf_workspace_manager"

T0 = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 8, 16, 12, 1, tzinfo=UTC)
T2 = datetime(2026, 8, 16, 12, 2, tzinfo=UTC)
T3 = datetime(2026, 8, 16, 12, 3, tzinfo=UTC)
T4 = datetime(2026, 8, 16, 12, 4, tzinfo=UTC)


def engineering_record(**overrides: object) -> EngineeringTaskRecord:
    data: dict[str, object] = {
        "task_id": "WM-PHASE2-ENG-001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "title": "Semantic and lineage preservation",
        "description": "Preserve task intent independently from execution instructions.",
        "repository": REPOSITORY,
        "base_sha": BASE_HEAD,
        "integrated_head_at_creation": INTEGRATED_HEAD,
        "task_branch": "task/WM-PHASE2-ENG-001",
        "latest_remote_task_sha": REMOTE_HEAD,
        "owner_id": "firas",
        "actor_id": "firas",
        "actor_type": ActorType.human,
        "provider_id": "provider-phase2",
        "scope_patterns": ["orchestrator/**", "test/**"],
        "depends_on": ["WM-PHASE1-ENG-001"],
        "dependency_mode": DependencyMode.wait_for_upstream,
        "risk_class": "HIGH",
        "mutation_class": "source-write",
        "required_capabilities": ["source.control", "runtime.verification"],
        "required_tests": ["parity", "regression", "browser-uat"],
        "status": EngineeringTaskStatus.wip_remote_checkpointed,
        "wip_checkpoint_status": "REMOTE_CHECKPOINTED",
        "integration_status": "NOT_READY",
        "evidence": ["task-evidence-1", "task-evidence-2"],
        "created_at": T0,
        "updated_at": T4,
    }
    data.update(overrides)
    return EngineeringTaskRecord.model_validate(data)


def operator_record(**overrides: object) -> OperatorTaskRecord:
    events = [
        TaskEvent(
            event_type="TASK_AUTHORIZED",
            status=OperatorTaskStatus.pending,
            message="authorized",
            occurred_at=T1,
            correlation_id="corr-1",
            client_id="client-1",
        ),
        TaskEvent(
            event_type="TASK_STARTED",
            status=OperatorTaskStatus.running,
            message="started",
            occurred_at=T2,
            correlation_id="corr-2",
            client_id="client-1",
        ),
        TaskEvent(
            event_type="TASK_EXECUTION_COMPLETED",
            status=OperatorTaskStatus.pending_verification,
            message="completed",
            occurred_at=T3,
            correlation_id="corr-3",
            client_id="client-1",
        ),
    ]
    data: dict[str, object] = {
        "task_id": "WM_PHASE2_RUN_001",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "repository": REPOSITORY,
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": EXPECTED_HEAD,
        "authority_reference": "AUTHORITY://SEMANTIC_LINEAGE_PHASE2",
        "prompt": "Execute the bounded semantic lineage verification run.",
        "constraints": ["NO_UI", "NO_MIGRATION", "NO_AUTHORITY_WIDENING"],
        "approval_policy": "on-request",
        "sandbox": "workspace-write",
        "max_turns": 5,
        "timeout_seconds": 300,
        "idempotency_key": "semantic-lineage-phase2-run-001",
        "automatic_failure_code": None,
        "manual_fallback_selected": True,
        "requires_explicit_authorization": True,
        "authorized_at": T1,
        "authorized_by": "governance-user",
        "dispatch_mode": DispatchMode.user_relay_fallback,
        "status": OperatorTaskStatus.pending_verification,
        "created_at": T0,
        "updated_at": T4,
        "last_event": "TASK_EXECUTION_COMPLETED",
        "blocker": None,
        "thread_id": "thread-phase2",
        "execution_receipt": "execution-receipt-phase2",
        "before_head": BEFORE_HEAD,
        "after_head": AFTER_HEAD,
        "changed_files": ["orchestrator/src/a.py", "orchestrator/tests/test_a.py"],
        "tests": ["ruff", "mypy", "pytest", "flutter test"],
        "evidence": ["run-evidence-1", "run-evidence-2"],
        "verification_receipt": "verification-receipt-phase2",
        "client_id": "client-1",
        "correlation_id": "corr-3",
        "execution_host_id": "host-1",
        "tool_executor_id": "executor-1",
        "queued_at": T1,
        "started_at": T2,
        "completed_at": T3,
        "dispatch_latency_ms": 1000,
        "executor_duration_ms": 60000,
        "verification_duration_ms": 2000,
        "events": events,
    }
    data.update(overrides)
    return OperatorTaskRecord.model_validate(data)


def run_record(operator: OperatorTaskRecord | None = None, **overrides: object) -> SimpleNamespace:
    operator_task = operator or operator_record()
    data: dict[str, object] = {
        "execution_run_id": "WM_PHASE2_RUN_001",
        "legacy_operator_task_id": operator_task.task_id,
        "parent_engineering_task_id": "WM-PHASE2-ENG-001",
        "operator_task": operator_task,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_pt_fld_001_engineering_record_snapshot_is_complete_and_canonical() -> None:
    parent = engineering_record()
    projection = build_semantic_lineage_projection(parent, run_record())

    expected = parent.model_dump(mode="json")
    decoded = json.loads(projection.engineering_record.canonical_json)

    assert decoded == expected
    assert projection.engineering_record.record_type == "EngineeringTaskRecord"
    assert (
        projection.engineering_record.sha256
        == hashlib.sha256(projection.engineering_record.canonical_json.encode("utf-8")).hexdigest()
    )


def test_pt_fld_002_operator_record_snapshot_is_complete_and_canonical() -> None:
    operator = operator_record()
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(operator),
    )

    expected = operator.model_dump(mode="json")
    decoded = json.loads(projection.operator_record.canonical_json)

    assert decoded == expected
    assert projection.operator_record.record_type == "OperatorTaskRecord"
    assert (
        projection.operator_record.sha256
        == hashlib.sha256(projection.operator_record.canonical_json.encode("utf-8")).hexdigest()
    )


def test_pt_sem_001_all_head_roles_remain_distinct_and_exact() -> None:
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(),
    )

    assert projection.heads.task_base_sha == BASE_HEAD
    assert projection.heads.task_integrated_head_at_creation == INTEGRATED_HEAD
    assert projection.heads.task_latest_remote_task_sha == REMOTE_HEAD
    assert projection.heads.run_expected_head == EXPECTED_HEAD
    assert projection.heads.run_before_head == BEFORE_HEAD
    assert projection.heads.run_after_head == AFTER_HEAD
    assert (
        len(
            {
                projection.heads.task_base_sha,
                projection.heads.task_integrated_head_at_creation,
                projection.heads.task_latest_remote_task_sha,
                projection.heads.run_expected_head,
                projection.heads.run_before_head,
                projection.heads.run_after_head,
            }
        )
        == 6
    )


def test_pt_sem_002_goal_and_execution_fields_are_not_collapsed() -> None:
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(),
    )

    assert projection.semantics.task_description.startswith("Preserve task intent")
    assert projection.semantics.run_prompt.startswith("Execute the bounded")
    assert projection.semantics.task_description != projection.semantics.run_prompt
    assert projection.semantics.task_scope_patterns == ("orchestrator/**", "test/**")
    assert projection.semantics.run_constraints == (
        "NO_UI",
        "NO_MIGRATION",
        "NO_AUTHORITY_WIDENING",
    )
    assert projection.semantics.task_required_tests == (
        "parity",
        "regression",
        "browser-uat",
    )
    assert projection.semantics.run_actual_tests == (
        "ruff",
        "mypy",
        "pytest",
        "flutter test",
    )


def test_cpm_11_evidence_receipts_and_changed_files_preserve_lineage() -> None:
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(),
    )

    assert projection.evidence.task_evidence == ("task-evidence-1", "task-evidence-2")
    assert projection.evidence.run_evidence == ("run-evidence-1", "run-evidence-2")
    assert projection.evidence.changed_files == (
        "orchestrator/src/a.py",
        "orchestrator/tests/test_a.py",
    )
    assert projection.evidence.execution_receipt == "execution-receipt-phase2"
    assert projection.evidence.verification_receipt == "verification-receipt-phase2"


def test_pt_op_005_timing_lineage_is_preserved_exactly() -> None:
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(),
    )

    assert projection.timings.task_created_at == T0
    assert projection.timings.task_updated_at == T4
    assert projection.timings.run_created_at == T0
    assert projection.timings.run_updated_at == T4
    assert projection.timings.queued_at == T1
    assert projection.timings.started_at == T2
    assert projection.timings.completed_at == T3
    assert projection.timings.dispatch_latency_ms == 1000
    assert projection.timings.executor_duration_ms == 60000
    assert projection.timings.verification_duration_ms == 2000


def test_pt_hist_001_event_order_and_identity_are_preserved_exactly() -> None:
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(),
    )

    assert [event.event_type for event in projection.events] == [
        "TASK_AUTHORIZED",
        "TASK_STARTED",
        "TASK_EXECUTION_COMPLETED",
    ]
    assert [event.occurred_at for event in projection.events] == [T1, T2, T3]
    assert [event.correlation_id for event in projection.events] == [
        "corr-1",
        "corr-2",
        "corr-3",
    ]
    assert [event.client_id for event in projection.events] == [
        "client-1",
        "client-1",
        "client-1",
    ]


def test_projection_preserves_distinct_authority_fields_without_rewriting() -> None:
    projection = build_semantic_lineage_projection(
        engineering_record(),
        run_record(),
    )

    assert projection.authority.task_branch == "task/WM-PHASE2-ENG-001"
    assert projection.authority.run_branch == "agent/workspace-manager-foundation-v1"
    assert projection.authority.task_branch != projection.authority.run_branch
    assert projection.authority.task_mutation_class == "source-write"
    assert projection.authority.run_sandbox == "workspace-write"
    assert projection.authority.authority_reference == "AUTHORITY://SEMANTIC_LINEAGE_PHASE2"


def test_projection_fails_closed_on_cross_layer_identity_drift() -> None:
    parent = engineering_record()
    operator = operator_record()

    with pytest.raises(GovernanceError, match="SEMANTIC_LINEAGE_PARENT_ID_DRIFT"):
        build_semantic_lineage_projection(
            parent,
            run_record(operator, parent_engineering_task_id="WM-OTHER-PARENT"),
        )

    with pytest.raises(GovernanceError, match="SEMANTIC_LINEAGE_OPERATOR_IDENTITY_DRIFT"):
        build_semantic_lineage_projection(
            parent,
            run_record(operator, legacy_operator_task_id="WM_OTHER_RUN"),
        )

    with pytest.raises(GovernanceError, match="SEMANTIC_LINEAGE_PROJECT_DRIFT"):
        build_semantic_lineage_projection(
            parent,
            run_record(operator.model_copy(update={"project_id": "OTHER_PROJECT"})),
        )

    with pytest.raises(GovernanceError, match="SEMANTIC_LINEAGE_REPOSITORY_DRIFT"):
        build_semantic_lineage_projection(
            parent,
            run_record(operator.model_copy(update={"repository": "other/repository"})),
        )
