from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.engineering_os_contracts import (
    ActorType,
    DependencyMode,
    EngineeringTaskRecord,
    EngineeringTaskStatus,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.parallel_development_coordinator import (
    MergeQueueStatus,
    ParallelDevelopmentCoordinator,
    ScopeLeaseStatus,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore

NOW = datetime(2026, 9, 17, 10, 30, tzinfo=UTC)
REPO = "firasfanon/palwakf_workspace_manager"
BASE = "a" * 40
CANDIDATE = "b" * 40


def _task(
    task_id: str,
    scopes: tuple[str, ...],
    *,
    candidate: str | None = CANDIDATE,
) -> EngineeringTaskRecord:
    return EngineeringTaskRecord(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        title=f"Task {task_id}",
        description="Parallel development coordinator test task",
        repository=REPO,
        base_sha=BASE,
        integrated_head_at_creation=BASE,
        task_branch=f"task/{task_id.lower()}",
        latest_remote_task_sha=candidate,
        owner_id="owner-test",
        actor_id="agent-test",
        actor_type=ActorType.agent,
        provider_id=None,
        scope_patterns=list(scopes),
        depends_on=[],
        dependency_mode=DependencyMode.independent,
        risk_class="MEDIUM",
        mutation_class="source-write",
        required_capabilities=[],
        required_tests=[],
        status=EngineeringTaskStatus.wip_remote_checkpointed,
        wip_checkpoint_status="REMOTE_CHECKPOINTED" if candidate else "NOT_CHECKPOINTED",
        integration_status="READY" if candidate else "NOT_READY",
        evidence=[],
        created_at=NOW,
        updated_at=NOW,
    )


def _coordinator(store=None, heads=None):
    state_store = store or MemoryStateStore()
    current_heads = heads if heads is not None else {REPO: BASE}
    coordinator = ParallelDevelopmentCoordinator(
        state_store,
        integration_head_resolver=lambda repository: current_heads[repository],
        now=lambda: NOW,
    )
    return coordinator, current_heads


def test_disjoint_scopes_can_hold_parallel_active_leases() -> None:
    coordinator, _ = _coordinator()
    first = coordinator.acquire_scope_lease(
        _task("TASK_A", ("orchestrator/src/alpha/**",)), execution_host_id="HOST_A"
    )
    second = coordinator.acquire_scope_lease(
        _task("TASK_B", ("orchestrator/src/beta/**",)), execution_host_id="HOST_B"
    )
    assert first.status == ScopeLeaseStatus.active
    assert second.status == ScopeLeaseStatus.active
    assert len(coordinator.list_scope_leases()) == 2


def test_overlapping_scope_is_rejected_fail_closed() -> None:
    coordinator, _ = _coordinator()
    coordinator.acquire_scope_lease(
        _task("TASK_A", ("orchestrator/src/alpha/**",)), execution_host_id="HOST_A"
    )
    with pytest.raises(GovernanceError, match="SCOPE_LEASE_CONFLICT"):
        coordinator.acquire_scope_lease(
            _task("TASK_B", ("orchestrator/src/alpha/models/**",)),
            execution_host_id="HOST_B",
        )


def test_wildcard_parent_scope_conflicts_with_child_scope() -> None:
    coordinator, _ = _coordinator()
    coordinator.acquire_scope_lease(
        _task("TASK_A", ("orchestrator/src/**",)), execution_host_id="HOST_A"
    )
    with pytest.raises(GovernanceError, match="SCOPE_LEASE_CONFLICT"):
        coordinator.acquire_scope_lease(
            _task("TASK_B", ("orchestrator/src/beta/**",)),
            execution_host_id="HOST_B",
        )


def test_release_allows_reacquire_with_new_generation() -> None:
    coordinator, _ = _coordinator()
    task = _task("TASK_A", ("orchestrator/src/alpha/**",))
    first = coordinator.acquire_scope_lease(task, execution_host_id="HOST_A")
    released = coordinator.release_scope_lease(task.task_id)
    second = coordinator.acquire_scope_lease(task, execution_host_id="HOST_A")
    assert released.status == ScopeLeaseStatus.released
    assert first.lease_id != second.lease_id
    assert second.status == ScopeLeaseStatus.active


def test_enqueue_requires_remote_checkpoint() -> None:
    coordinator, _ = _coordinator()
    with pytest.raises(GovernanceError, match="MERGE_QUEUE_REMOTE_CHECKPOINT_REQUIRED"):
        coordinator.enqueue(_task("TASK_NO_REMOTE", ("orchestrator/src/x/**",), candidate=None))


def test_fifo_merge_queue_and_post_integration_readback() -> None:
    coordinator, heads = _coordinator()
    first = coordinator.enqueue(_task("TASK_A", ("orchestrator/src/alpha/**",)))
    second = coordinator.enqueue(_task("TASK_B", ("orchestrator/src/beta/**",)))
    with pytest.raises(GovernanceError, match="MERGE_QUEUE_NOT_AT_FRONT"):
        coordinator.require_ready_for_merge(second.entry_id)
    ready = coordinator.require_ready_for_merge(first.entry_id)
    assert ready.status == MergeQueueStatus.ready
    merged_head = "c" * 40
    heads[REPO] = merged_head
    integrated = coordinator.mark_integrated(
        first.entry_id,
        integrated_head=merged_head,
        authority_reference="AUTH-MERGE-1",
        evidence=("merge:evidence",),
    )
    assert integrated.status == MergeQueueStatus.integrated
    assert integrated.integrated_head == merged_head


def test_second_queue_entry_detects_latest_integration_head_drift() -> None:
    coordinator, heads = _coordinator()
    first = coordinator.enqueue(_task("TASK_A", ("orchestrator/src/alpha/**",)))
    second = coordinator.enqueue(_task("TASK_B", ("orchestrator/src/beta/**",)))
    ready = coordinator.require_ready_for_merge(first.entry_id)
    assert ready.status == MergeQueueStatus.ready
    merged_head = "c" * 40
    heads[REPO] = merged_head
    coordinator.mark_integrated(
        first.entry_id,
        integrated_head=merged_head,
        authority_reference="AUTH-MERGE-1",
        evidence=("merge:evidence",),
    )
    with pytest.raises(GovernanceError, match="MERGE_QUEUE_INTEGRATION_HEAD_DRIFT"):
        coordinator.require_ready_for_merge(second.entry_id)
    persisted = {item.entry_id: item for item in coordinator.list_merge_queue()}
    assert persisted[second.entry_id].status == MergeQueueStatus.reconciliation_required


def test_enqueue_marks_reconciliation_required_when_head_already_drifted() -> None:
    coordinator, heads = _coordinator()
    heads[REPO] = "d" * 40
    entry = coordinator.enqueue(_task("TASK_DRIFT", ("orchestrator/src/drift/**",)))
    assert entry.status == MergeQueueStatus.reconciliation_required


def test_invalid_integration_head_fails_closed() -> None:
    coordinator, heads = _coordinator()
    heads[REPO] = "not-a-sha"
    with pytest.raises(GovernanceError, match="MERGE_QUEUE_INTEGRATION_HEAD_INVALID"):
        coordinator.enqueue(_task("TASK_BAD_HEAD", ("orchestrator/src/x/**",)))


def test_post_integration_head_mismatch_is_rejected() -> None:
    coordinator, heads = _coordinator()
    entry = coordinator.enqueue(_task("TASK_A", ("orchestrator/src/alpha/**",)))
    coordinator.require_ready_for_merge(entry.entry_id)
    heads[REPO] = "c" * 40
    with pytest.raises(GovernanceError, match="MERGE_QUEUE_POST_INTEGRATION_HEAD_MISMATCH"):
        coordinator.mark_integrated(
            entry.entry_id,
            integrated_head="d" * 40,
            authority_reference="AUTH-MERGE-1",
            evidence=("merge:evidence",),
        )


def test_sqlite_restart_preserves_scope_leases_and_merge_queue(tmp_path) -> None:
    db = tmp_path / "parallel.sqlite3"
    first, _ = _coordinator(store=SQLiteStateStore(db))
    lease = first.acquire_scope_lease(
        _task("TASK_A", ("orchestrator/src/alpha/**",)), execution_host_id="HOST_A"
    )
    entry = first.enqueue(_task("TASK_B", ("orchestrator/src/beta/**",)))

    restarted, _ = _coordinator(store=SQLiteStateStore(db))
    leases = restarted.list_scope_leases()
    queue = restarted.list_merge_queue()
    assert leases == (lease,)
    assert queue == (entry,)
