from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import MaterialChangeEventV1

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class OutboxStatus(StrEnum):
    pending = "PENDING"
    in_flight = "IN_FLIGHT"
    dispatched = "DISPATCHED"


class OutboxArchitectureContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: Literal["POSTGRESQL_TRANSACTIONAL_OUTBOX"] = "POSTGRESQL_TRANSACTIONAL_OUTBOX"
    dispatcher: Literal["LIGHTWEIGHT_POLLING"] = "LIGHTWEIGHT_POLLING"
    event_format: Literal["CLOUDEVENTS_1_0"] = "CLOUDEVENTS_1_0"
    kafka_required: Literal[False] = False
    shared_db_mutation_performed: Literal[False] = False


class CloudEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    specversion: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    type: str = Field(min_length=1, max_length=300)
    subject: str = Field(min_length=1, max_length=500)
    time: datetime
    datacontenttype: Literal["application/json"] = "application/json"
    data: dict[str, Any]


class OutboxMessageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    cloud_event: CloudEventV1
    status: OutboxStatus = OutboxStatus.pending
    attempt_count: int = Field(default=0, ge=0)
    available_at: datetime
    created_at: datetime
    lock_token: str | None = Field(default=None, max_length=200)
    locked_at: datetime | None = None
    last_error: str | None = Field(default=None, max_length=1000)
    dispatched_at: datetime | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.status == OutboxStatus.in_flight and not self.lock_token:
            raise ValueError("OUTBOX_IN_FLIGHT_LOCK_REQUIRED")
        if self.status == OutboxStatus.dispatched and self.dispatched_at is None:
            raise ValueError("OUTBOX_DISPATCH_TIMESTAMP_REQUIRED")
        if self.status != OutboxStatus.in_flight and self.lock_token is not None:
            raise ValueError("OUTBOX_LOCK_ONLY_ALLOWED_IN_FLIGHT")
        return self


class DispatchBatchResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempted: int = Field(ge=0)
    dispatched: int = Field(ge=0)
    failed: int = Field(ge=0)
    outbox_ids: tuple[str, ...] = ()


class OutboxStore(Protocol):
    def enqueue(self, message: OutboxMessageV1) -> OutboxMessageV1: ...
    def claim_batch(
        self,
        *,
        limit: int,
        now: datetime,
        lock_token: str,
    ) -> tuple[OutboxMessageV1, ...]: ...

    def mark_dispatched(
        self,
        outbox_id: str,
        *,
        lock_token: str,
        dispatched_at: datetime,
    ) -> OutboxMessageV1: ...

    def release_for_retry(
        self,
        outbox_id: str,
        *,
        lock_token: str,
        error: str,
        available_at: datetime,
    ) -> OutboxMessageV1: ...

    def get(self, outbox_id: str) -> OutboxMessageV1: ...


class MemoryTransactionalOutboxStore:
    def __init__(self) -> None:
        self._messages: dict[str, OutboxMessageV1] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.RLock()

    def enqueue(self, message: OutboxMessageV1) -> OutboxMessageV1:
        with self._lock:
            existing_id = self._idempotency.get(message.idempotency_key)
            if existing_id is not None:
                existing = self._messages[existing_id]
                if existing.cloud_event != message.cloud_event:
                    raise GovernanceError("OUTBOX_IDEMPOTENCY_CONFLICT")
                return existing
            if message.outbox_id in self._messages:
                raise GovernanceError("OUTBOX_ID_CONFLICT")
            self._messages[message.outbox_id] = message
            self._idempotency[message.idempotency_key] = message.outbox_id
            return message

    def claim_batch(
        self,
        *,
        limit: int,
        now: datetime,
        lock_token: str,
    ) -> tuple[OutboxMessageV1, ...]:
        if limit < 1:
            raise GovernanceError("OUTBOX_CLAIM_LIMIT_INVALID")
        if not lock_token.strip():
            raise GovernanceError("OUTBOX_LOCK_TOKEN_REQUIRED")
        with self._lock:
            eligible = sorted(
                (
                    item
                    for item in self._messages.values()
                    if item.status == OutboxStatus.pending and item.available_at <= now
                ),
                key=lambda item: (item.created_at, item.outbox_id),
            )[:limit]
            claimed: list[OutboxMessageV1] = []
            for item in eligible:
                updated = item.model_copy(
                    update={
                        "status": OutboxStatus.in_flight,
                        "attempt_count": item.attempt_count + 1,
                        "lock_token": lock_token,
                        "locked_at": now,
                        "last_error": None,
                    }
                )
                self._messages[item.outbox_id] = updated
                claimed.append(updated)
            return tuple(claimed)

    def mark_dispatched(
        self,
        outbox_id: str,
        *,
        lock_token: str,
        dispatched_at: datetime,
    ) -> OutboxMessageV1:
        with self._lock:
            current = self.get(outbox_id)
            self._assert_lock(current, lock_token)
            updated = current.model_copy(
                update={
                    "status": OutboxStatus.dispatched,
                    "lock_token": None,
                    "locked_at": None,
                    "dispatched_at": dispatched_at,
                }
            )
            self._messages[outbox_id] = updated
            return updated

    def release_for_retry(
        self,
        outbox_id: str,
        *,
        lock_token: str,
        error: str,
        available_at: datetime,
    ) -> OutboxMessageV1:
        if not error.strip():
            raise GovernanceError("OUTBOX_RETRY_ERROR_REQUIRED")
        with self._lock:
            current = self.get(outbox_id)
            self._assert_lock(current, lock_token)
            updated = current.model_copy(
                update={
                    "status": OutboxStatus.pending,
                    "lock_token": None,
                    "locked_at": None,
                    "available_at": available_at,
                    "last_error": error[:1000],
                }
            )
            self._messages[outbox_id] = updated
            return updated

    def get(self, outbox_id: str) -> OutboxMessageV1:
        try:
            return self._messages[outbox_id]
        except KeyError as exc:
            raise GovernanceError("OUTBOX_MESSAGE_NOT_FOUND") from exc

    @staticmethod
    def _assert_lock(message: OutboxMessageV1, lock_token: str) -> None:
        if message.status != OutboxStatus.in_flight or message.lock_token != lock_token:
            raise GovernanceError("OUTBOX_LOCK_MISMATCH")


def build_cloud_event(event: MaterialChangeEventV1) -> CloudEventV1:
    event_type = event.event_type.value.lower().replace("_", "-")
    return CloudEventV1(
        id=event.event_id,
        source=f"urn:palwakf:workspace-manager:project:{event.project_id}",
        type=f"org.palwakf.material-change.{event_type}",
        subject=f"projects/{event.project_id}/changes/{event.change_id}",
        time=event.occurred_at,
        data={
            **event.model_dump(mode="json"),
            "material_event_sha256": event.event_sha256,
        },
    )


def build_outbox_message(
    event: MaterialChangeEventV1,
    *,
    created_at: datetime | None = None,
) -> OutboxMessageV1:
    created = created_at or datetime.now(UTC)
    return OutboxMessageV1(
        outbox_id=f"material-change:{event.event_id}",
        idempotency_key=event.event_sha256,
        cloud_event=build_cloud_event(event),
        available_at=created,
        created_at=created,
    )


class CursorLike(Protocol):
    def execute(self, query: str, params: tuple[object, ...]) -> object: ...


class PostgresOutboxSqlV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str
    table_name: str = "event_outbox_v1"

    @model_validator(mode="after")
    def validate_identifiers(self) -> Self:
        if not _IDENTIFIER_RE.fullmatch(self.schema_name):
            raise ValueError("OUTBOX_SCHEMA_IDENTIFIER_INVALID")
        if not _IDENTIFIER_RE.fullmatch(self.table_name):
            raise ValueError("OUTBOX_TABLE_IDENTIFIER_INVALID")
        return self

    @property
    def qualified_table(self) -> str:
        return f'"{self.schema_name}"."{self.table_name}"'

    def create_table_sql(self) -> str:
        table = self.qualified_table
        return f"""
CREATE TABLE IF NOT EXISTS {table} (
    outbox_id text PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE,
    cloud_event jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('PENDING','IN_FLIGHT','DISPATCHED')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    lock_token text,
    locked_at timestamptz,
    last_error text,
    dispatched_at timestamptz
);
""".strip()

    def insert_sql(self) -> str:
        table = self.qualified_table
        return f"""
INSERT INTO {table} (
    outbox_id, idempotency_key, cloud_event, status,
    attempt_count, available_at, created_at
) VALUES (%s, %s, %s::jsonb, 'PENDING', 0, %s, %s)
ON CONFLICT (idempotency_key) DO NOTHING
""".strip()

    def claim_sql(self) -> str:
        table = self.qualified_table
        return f"""
WITH next_batch AS (
    SELECT outbox_id
    FROM {table}
    WHERE status = 'PENDING' AND available_at <= %s
    ORDER BY created_at, outbox_id
    FOR UPDATE SKIP LOCKED
    LIMIT %s
)
UPDATE {table} AS o
SET status = 'IN_FLIGHT',
    attempt_count = o.attempt_count + 1,
    lock_token = %s,
    locked_at = %s,
    last_error = NULL
FROM next_batch AS n
WHERE o.outbox_id = n.outbox_id
RETURNING o.*
""".strip()

    def dispatched_sql(self) -> str:
        table = self.qualified_table
        return f"""
UPDATE {table}
SET status='DISPATCHED', lock_token=NULL, locked_at=NULL, dispatched_at=%s
WHERE outbox_id=%s AND status='IN_FLIGHT' AND lock_token=%s
""".strip()

    def retry_sql(self) -> str:
        table = self.qualified_table
        return f"""
UPDATE {table}
SET status='PENDING', lock_token=NULL, locked_at=NULL,
    last_error=%s, available_at=%s
WHERE outbox_id=%s AND status='IN_FLIGHT' AND lock_token=%s
""".strip()


class PostgresTransactionalOutboxWriterV1:
    """Uses a caller-owned DB transaction; never commits or opens a connection."""

    def __init__(self, sql: PostgresOutboxSqlV1) -> None:
        self._sql = sql

    def enqueue_in_transaction(
        self,
        cursor: CursorLike,
        message: OutboxMessageV1,
    ) -> None:
        payload = json.dumps(
            message.cloud_event.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        cursor.execute(
            self._sql.insert_sql(),
            (
                message.outbox_id,
                message.idempotency_key,
                payload,
                message.available_at,
                message.created_at,
            ),
        )


CloudEventTransport = Callable[[CloudEventV1], None]


class LightweightOutboxDispatcher:
    def __init__(
        self,
        store: OutboxStore,
        transport: CloudEventTransport,
        *,
        now: Callable[[], datetime] | None = None,
        retry_delay: timedelta = timedelta(seconds=30),
    ) -> None:
        if retry_delay.total_seconds() < 0:
            raise ValueError("OUTBOX_RETRY_DELAY_INVALID")
        self._store = store
        self._transport = transport
        self._now = now or (lambda: datetime.now(UTC))
        self._retry_delay = retry_delay

    def dispatch_once(
        self,
        *,
        limit: int = 50,
        lock_token: str,
    ) -> DispatchBatchResultV1:
        now = self._now()
        claimed = self._store.claim_batch(limit=limit, now=now, lock_token=lock_token)
        dispatched = 0
        failed = 0
        ids: list[str] = []
        for message in claimed:
            ids.append(message.outbox_id)
            try:
                self._transport(message.cloud_event)
            except Exception as exc:
                failed += 1
                detail = str(exc).strip() or type(exc).__name__
                self._store.release_for_retry(
                    message.outbox_id,
                    lock_token=lock_token,
                    error=detail,
                    available_at=now + self._retry_delay,
                )
            else:
                dispatched += 1
                self._store.mark_dispatched(
                    message.outbox_id,
                    lock_token=lock_token,
                    dispatched_at=now,
                )
        return DispatchBatchResultV1(
            attempted=len(claimed),
            dispatched=dispatched,
            failed=failed,
            outbox_ids=tuple(ids),
        )
