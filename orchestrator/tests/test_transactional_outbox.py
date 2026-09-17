from datetime import timedelta

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import (
    MaterialChangeEventType,
    build_material_change_event,
)
from palwakf_orchestrator.transactional_outbox import (
    LightweightOutboxDispatcher,
    MemoryTransactionalOutboxStore,
    OutboxArchitectureContractV1,
    OutboxStatus,
    PostgresOutboxSqlV1,
    PostgresTransactionalOutboxWriterV1,
    build_cloud_event,
    build_outbox_message,
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


def _event(event_id: str = "event-outbox-1"):
    graph = _graph()
    return build_material_change_event(
        event_id=event_id,
        event_type=MaterialChangeEventType.dependency_changed,
        acceptance=_acceptance(f"change-{event_id}"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=_contracts(graph),
        source_revision=REV,
        evidence=("outbox:evidence",),
        edge_id="edge-1",
        occurred_at=NOW,
    )


def test_material_change_maps_to_cloudevents_1_0() -> None:
    event = _event()
    cloud_event = build_cloud_event(event)
    assert cloud_event.specversion == "1.0"
    assert cloud_event.id == event.event_id
    assert cloud_event.source.endswith(event.project_id)
    assert cloud_event.type == "org.palwakf.material-change.dependency-changed"
    assert cloud_event.subject.endswith(event.change_id)
    assert cloud_event.data["material_event_sha256"] == event.event_sha256


def test_architecture_contract_requires_no_kafka_or_shared_db_mutation() -> None:
    contract = OutboxArchitectureContractV1()
    assert contract.backend == "POSTGRESQL_TRANSACTIONAL_OUTBOX"
    assert contract.dispatcher == "LIGHTWEIGHT_POLLING"
    assert contract.event_format == "CLOUDEVENTS_1_0"
    assert contract.kafka_required is False
    assert contract.shared_db_mutation_performed is False


def test_outbox_enqueue_is_idempotent_by_material_event_hash() -> None:
    store = MemoryTransactionalOutboxStore()
    message = build_outbox_message(_event(), created_at=NOW)
    first = store.enqueue(message)
    second = store.enqueue(message)
    assert first == second
    assert first.idempotency_key == _event().event_sha256


def test_outbox_idempotency_conflict_fails_closed() -> None:
    store = MemoryTransactionalOutboxStore()
    first = build_outbox_message(_event("event-a"), created_at=NOW)
    store.enqueue(first)
    conflicting = build_outbox_message(_event("event-b"), created_at=NOW).model_copy(
        update={"idempotency_key": first.idempotency_key}
    )
    with pytest.raises(GovernanceError, match="OUTBOX_IDEMPOTENCY_CONFLICT"):
        store.enqueue(conflicting)


def test_successful_dispatch_marks_message_once() -> None:
    store = MemoryTransactionalOutboxStore()
    message = store.enqueue(build_outbox_message(_event(), created_at=NOW))
    delivered = []
    dispatcher = LightweightOutboxDispatcher(
        store,
        delivered.append,
        now=lambda: NOW,
    )
    result = dispatcher.dispatch_once(lock_token="dispatcher-1")
    assert result.dispatched == 1
    assert result.failed == 0
    assert store.get(message.outbox_id).status == OutboxStatus.dispatched
    assert len(delivered) == 1

    second = dispatcher.dispatch_once(lock_token="dispatcher-2")
    assert second.attempted == 0
    assert len(delivered) == 1


def test_failed_dispatch_is_retried_without_loss() -> None:
    store = MemoryTransactionalOutboxStore()
    message = store.enqueue(build_outbox_message(_event(), created_at=NOW))
    clock = [NOW]
    calls = [0]

    def transport(_cloud_event) -> None:
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("temporary transport failure")

    dispatcher = LightweightOutboxDispatcher(
        store,
        transport,
        now=lambda: clock[0],
        retry_delay=timedelta(seconds=30),
    )
    first = dispatcher.dispatch_once(lock_token="dispatcher-1")
    assert first.failed == 1
    pending = store.get(message.outbox_id)
    assert pending.status == OutboxStatus.pending
    assert pending.attempt_count == 1
    assert pending.last_error == "temporary transport failure"

    clock[0] = NOW + timedelta(seconds=29)
    assert dispatcher.dispatch_once(lock_token="dispatcher-2").attempted == 0
    clock[0] = NOW + timedelta(seconds=31)
    second = dispatcher.dispatch_once(lock_token="dispatcher-3")
    assert second.dispatched == 1
    final = store.get(message.outbox_id)
    assert final.status == OutboxStatus.dispatched
    assert final.attempt_count == 2


def test_lock_owner_mismatch_is_rejected() -> None:
    store = MemoryTransactionalOutboxStore()
    message = store.enqueue(build_outbox_message(_event(), created_at=NOW))
    claimed = store.claim_batch(limit=1, now=NOW, lock_token="owner-a")
    assert claimed[0].outbox_id == message.outbox_id
    with pytest.raises(GovernanceError, match="OUTBOX_LOCK_MISMATCH"):
        store.mark_dispatched(
            message.outbox_id,
            lock_token="owner-b",
            dispatched_at=NOW,
        )


def test_postgres_sql_contract_is_idempotent_and_skip_locked() -> None:
    sql = PostgresOutboxSqlV1(schema_name="workspace_manager")
    ddl = sql.create_table_sql()
    claim = sql.claim_sql()
    assert "idempotency_key text NOT NULL UNIQUE" in ddl
    assert "cloud_event jsonb NOT NULL" in ddl
    assert "ON CONFLICT (idempotency_key) DO NOTHING" in sql.insert_sql()
    assert "FOR UPDATE SKIP LOCKED" in claim
    assert '"workspace_manager"."event_outbox_v1"' in ddl


def test_postgres_schema_must_be_explicit_valid_identifier() -> None:
    with pytest.raises(ValueError, match="OUTBOX_SCHEMA_IDENTIFIER_INVALID"):
        PostgresOutboxSqlV1(schema_name="workspace-manager;drop")


class _FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query: str, params: tuple[object, ...]) -> object:
        self.calls.append((query, params))
        return object()


def test_postgres_writer_uses_caller_owned_transaction_without_commit() -> None:
    cursor = _FakeCursor()
    message = build_outbox_message(_event(), created_at=NOW)
    writer = PostgresTransactionalOutboxWriterV1(
        PostgresOutboxSqlV1(schema_name="workspace_manager")
    )
    writer.enqueue_in_transaction(cursor, message)
    assert len(cursor.calls) == 1
    query, params = cursor.calls[0]
    assert "INSERT INTO" in query
    assert "ON CONFLICT" in query
    assert params[0] == message.outbox_id
    assert params[1] == message.idempotency_key
    assert "commit" not in query.lower()
