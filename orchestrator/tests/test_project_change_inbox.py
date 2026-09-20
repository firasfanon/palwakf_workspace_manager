from datetime import timedelta

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import (
    MaterialChangeEventRegistryV1,
    MaterialChangeEventType,
    build_material_change_event,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore
from palwakf_orchestrator.project_change_inbox import (
    INBOX_STATE_KEY,
    ProjectChangeInboxStatus,
    ProjectChangeInboxStore,
)
from tests.test_material_change_event_registry import (
    NOW,
    REV,
    A,
    B,
    _acceptance,
    _contracts,
    _graph,
)


def _event(*, event_id: str = "event-inbox-1", affected=(B,)):
    graph = _graph()
    return build_material_change_event(
        event_id=event_id,
        event_type=MaterialChangeEventType.dependency_changed,
        acceptance=_acceptance(f"change-{event_id}"),
        project_id=A,
        affected_project_ids=affected,
        graph=graph,
        contract_registry=_contracts(graph),
        source_revision=REV,
        evidence=("inbox:event",),
        edge_id="edge-1",
        occurred_at=NOW,
    )


def test_inbound_event_creates_unresolved_item_for_affected_project_only() -> None:
    store = ProjectChangeInboxStore(MemoryStateStore())
    items = store.ingest_event(_event())
    assert len(items) == 1
    item = items[0]
    assert item.project_id == B
    assert item.source_project_id == A
    assert item.status == ProjectChangeInboxStatus.open
    assert store.unresolved_for_project(B) == (item,)
    assert store.unresolved_for_project(A) == ()


def test_sync_registry_is_idempotent_and_resume_visible() -> None:
    store = ProjectChangeInboxStore(MemoryStateStore())
    registry = MaterialChangeEventRegistryV1(events=(_event(),))
    first = store.sync_registry(registry)
    second = store.sync_registry(registry)
    assert len(first.items) == 1
    assert second.items == first.items
    assert store.resume_visibility(B) == first.items


def test_project_isolation_rejects_cross_project_get() -> None:
    store = ProjectChangeInboxStore(MemoryStateStore())
    item = store.ingest_event(_event())[0]
    with pytest.raises(GovernanceError, match="PROJECT_CHANGE_INBOX_PROJECT_MISMATCH"):
        store.get(item.inbox_item_id, project_id=A)


def test_lifecycle_progresses_and_resolved_item_leaves_unresolved_view() -> None:
    clock = iter((NOW + timedelta(minutes=1), NOW + timedelta(minutes=2)))
    store = ProjectChangeInboxStore(MemoryStateStore(), now=lambda: next(clock))
    item = store.ingest_event(_event())[0]
    acknowledged = store.transition(
        item.inbox_item_id,
        project_id=B,
        expected_status=ProjectChangeInboxStatus.open,
        new_status=ProjectChangeInboxStatus.acknowledged,
        lifecycle_evidence=("ack:evidence",),
    )
    resolved = store.transition(
        item.inbox_item_id,
        project_id=B,
        expected_status=ProjectChangeInboxStatus.acknowledged,
        new_status=ProjectChangeInboxStatus.resolved,
        lifecycle_evidence=("resolution:evidence",),
        resolution_reference="decision:resolved-1",
    )
    assert acknowledged.status == ProjectChangeInboxStatus.acknowledged
    assert resolved.status == ProjectChangeInboxStatus.resolved
    assert store.unresolved_for_project(B) == ()
    assert store.get(item.inbox_item_id, project_id=B).resolution_reference == "decision:resolved-1"


def test_stale_status_and_terminal_reopen_fail_closed() -> None:
    store = ProjectChangeInboxStore(MemoryStateStore(), now=lambda: NOW + timedelta(minutes=1))
    item = store.ingest_event(_event())[0]
    with pytest.raises(GovernanceError, match="PROJECT_CHANGE_INBOX_STALE_STATUS"):
        store.transition(
            item.inbox_item_id,
            project_id=B,
            expected_status=ProjectChangeInboxStatus.acknowledged,
            new_status=ProjectChangeInboxStatus.resolved,
            lifecycle_evidence=("bad",),
            resolution_reference="decision:x",
        )
    resolved = store.transition(
        item.inbox_item_id,
        project_id=B,
        expected_status=ProjectChangeInboxStatus.open,
        new_status=ProjectChangeInboxStatus.resolved,
        lifecycle_evidence=("done",),
        resolution_reference="decision:done",
    )
    assert resolved.status == ProjectChangeInboxStatus.resolved
    with pytest.raises(GovernanceError, match="PROJECT_CHANGE_INBOX_INVALID_TRANSITION"):
        store.transition(
            item.inbox_item_id,
            project_id=B,
            expected_status=ProjectChangeInboxStatus.resolved,
            new_status=ProjectChangeInboxStatus.acknowledged,
            lifecycle_evidence=("reopen",),
        )


def test_resolution_requires_reference_and_lifecycle_evidence() -> None:
    store = ProjectChangeInboxStore(MemoryStateStore())
    item = store.ingest_event(_event())[0]
    with pytest.raises(GovernanceError, match="LIFECYCLE_EVIDENCE_REQUIRED"):
        store.transition(
            item.inbox_item_id,
            project_id=B,
            expected_status=ProjectChangeInboxStatus.open,
            new_status=ProjectChangeInboxStatus.acknowledged,
            lifecycle_evidence=(),
        )
    with pytest.raises(GovernanceError, match="RESOLUTION_REFERENCE_REQUIRED"):
        store.transition(
            item.inbox_item_id,
            project_id=B,
            expected_status=ProjectChangeInboxStatus.open,
            new_status=ProjectChangeInboxStatus.resolved,
            lifecycle_evidence=("done",),
        )


def test_sqlite_restart_preserves_unresolved_resume_visibility(tmp_path) -> None:
    db = tmp_path / "state.sqlite3"
    first = ProjectChangeInboxStore(SQLiteStateStore(db))
    item = first.ingest_event(_event())[0]
    restarted = ProjectChangeInboxStore(SQLiteStateStore(db))
    assert restarted.resume_visibility(B) == (item,)


def test_source_project_is_not_duplicated_as_inbound_recipient() -> None:
    store = ProjectChangeInboxStore(MemoryStateStore())
    items = store.ingest_event(_event(affected=(A, B)))
    assert len(items) == 1
    assert items[0].project_id == B


def test_persisted_inbox_hash_tampering_is_rejected() -> None:
    state_store = MemoryStateStore()
    store = ProjectChangeInboxStore(state_store)
    store.ingest_event(_event())
    state = state_store.load()
    state[INBOX_STATE_KEY]["items"][0]["change_id"] = "tampered"
    state_store.save(state)
    with pytest.raises(GovernanceError, match="PROJECT_CHANGE_INBOX_HASH_MISMATCH"):
        store.snapshot()
