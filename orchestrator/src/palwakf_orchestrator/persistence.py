from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Protocol, cast

from palwakf_orchestrator.errors import GovernanceError


@dataclass(frozen=True)
class SQLiteBackupReceiptV1:
    backup_path: str
    backup_sha256: str
    state_sha256: str
    size_bytes: int
    created_at: str
    duration_ms: int
    integrity_check: tuple[str, ...]


@dataclass(frozen=True)
class SQLiteRestoreReceiptV1:
    backup_path: str
    backup_sha256: str
    before_state_sha256: str
    restored_state_sha256: str
    restored_at: str
    duration_ms: int
    integrity_check: tuple[str, ...]


def _canonical_state_sha256(state: dict[str, Any]) -> str:
    canonical = json.dumps(
        state,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_integrity_check(path: Path) -> tuple[str, ...]:
    try:
        with sqlite3.connect(path, timeout=10) as connection:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        raise GovernanceError("SQLITE_INTEGRITY_CHECK_FAILED") from exc
    result = tuple(str(row[0]) for row in rows)
    if result != ("ok",):
        raise GovernanceError("SQLITE_INTEGRITY_CHECK_NOT_OK")
    return result


def _load_state_from_sqlite(path: Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(path, timeout=10) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT state_json FROM application_state WHERE singleton = 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise GovernanceError("SQLITE_BACKUP_STATE_READ_FAILED") from exc
    try:
        return json.loads(row["state_json"]) if row else {}
    except (json.JSONDecodeError, TypeError) as exc:
        raise GovernanceError("SQLITE_BACKUP_STATE_JSON_INVALID") from exc


class StateStore(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, state: dict[str, Any]) -> None: ...

    def acquire_repository_writer(
        self, repository: str, task_id: str, execution_host_id: str
    ) -> bool: ...

    def release_repository_writer(self, repository: str, task_id: str) -> None: ...

    def writer_for(self, repository: str) -> dict[str, str] | None: ...

    def is_healthy(self) -> bool: ...


class MemoryStateStore:
    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._writers: dict[str, dict[str, str]] = {}
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            return cast(dict[str, Any], json.loads(json.dumps(self._state)))

    def save(self, state: dict[str, Any]) -> None:
        with self._lock:
            self._state = json.loads(json.dumps(state))

    def acquire_repository_writer(
        self, repository: str, task_id: str, execution_host_id: str
    ) -> bool:
        with self._lock:
            current = self._writers.get(repository)
            if current and current["task_id"] != task_id:
                return False
            self._writers[repository] = {
                "task_id": task_id,
                "execution_host_id": execution_host_id,
            }
            return True

    def release_repository_writer(self, repository: str, task_id: str) -> None:
        with self._lock:
            current = self._writers.get(repository)
            if current and current["task_id"] == task_id:
                self._writers.pop(repository, None)

    def writer_for(self, repository: str) -> dict[str, str] | None:
        with self._lock:
            current = self._writers.get(repository)
            return dict(current) if current else None

    def is_healthy(self) -> bool:
        return True


class SQLiteStateStore:
    """Transactional local state. Task content never leaves the workspace here."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS application_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repository_writers (
                    repository TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    execution_host_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL
                );
                """
            )

    def load(self) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM application_state WHERE singleton = 1"
            ).fetchone()
            return json.loads(row["state_json"]) if row else {}

    def save(self, state: dict[str, Any]) -> None:
        canonical = json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO application_state(singleton, state_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (canonical, datetime.now(UTC).isoformat()),
            )
            connection.commit()

    def acquire_repository_writer(
        self, repository: str, task_id: str, execution_host_id: str
    ) -> bool:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT task_id FROM repository_writers WHERE repository = ?",
                (repository,),
            ).fetchone()
            if row and row["task_id"] != task_id:
                connection.rollback()
                return False
            connection.execute(
                """
                INSERT INTO repository_writers(
                    repository, task_id, execution_host_id, acquired_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(repository) DO UPDATE SET
                    task_id = excluded.task_id,
                    execution_host_id = excluded.execution_host_id,
                    acquired_at = excluded.acquired_at
                """,
                (repository, task_id, execution_host_id, datetime.now(UTC).isoformat()),
            )
            connection.commit()
            return True

    def release_repository_writer(self, repository: str, task_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM repository_writers WHERE repository = ? AND task_id = ?",
                (repository, task_id),
            )

    def writer_for(self, repository: str) -> dict[str, str] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT task_id, execution_host_id, acquired_at
                FROM repository_writers WHERE repository = ?
                """,
                (repository,),
            ).fetchone()
            return dict(row) if row else None

    def verify_integrity(self) -> tuple[str, ...]:
        with self._lock:
            return _sqlite_integrity_check(self.path)

    def create_backup(self, destination: Path) -> SQLiteBackupReceiptV1:
        target_path = destination.resolve()
        if target_path == self.path:
            raise GovernanceError("SQLITE_BACKUP_TARGET_MUST_DIFFER_FROM_SOURCE")
        if target_path.exists():
            raise GovernanceError("SQLITE_BACKUP_TARGET_ALREADY_EXISTS")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        started_ns = perf_counter_ns()
        with self._lock:
            state_sha256 = _canonical_state_sha256(self.load())
            try:
                with self._connect() as source, sqlite3.connect(target_path, timeout=10) as target:
                    source.backup(target)
                    target.commit()
            except sqlite3.Error as exc:
                target_path.unlink(missing_ok=True)
                raise GovernanceError("SQLITE_BACKUP_FAILED") from exc
            integrity = _sqlite_integrity_check(target_path)
            backup_state_sha256 = _canonical_state_sha256(_load_state_from_sqlite(target_path))
            if backup_state_sha256 != state_sha256:
                target_path.unlink(missing_ok=True)
                raise GovernanceError("SQLITE_BACKUP_STATE_HASH_MISMATCH")
        return SQLiteBackupReceiptV1(
            backup_path=str(target_path),
            backup_sha256=_file_sha256(target_path),
            state_sha256=state_sha256,
            size_bytes=target_path.stat().st_size,
            created_at=datetime.now(UTC).isoformat(),
            duration_ms=max(0, (perf_counter_ns() - started_ns) // 1_000_000),
            integrity_check=integrity,
        )

    def restore_backup(self, receipt: SQLiteBackupReceiptV1) -> SQLiteRestoreReceiptV1:
        backup_path = Path(receipt.backup_path).resolve()
        if backup_path == self.path:
            raise GovernanceError("SQLITE_RESTORE_SOURCE_MUST_DIFFER_FROM_TARGET")
        if not backup_path.is_file():
            raise GovernanceError("SQLITE_BACKUP_NOT_FOUND")
        if _file_sha256(backup_path) != receipt.backup_sha256:
            raise GovernanceError("SQLITE_BACKUP_SHA256_MISMATCH")
        backup_integrity = _sqlite_integrity_check(backup_path)
        backup_state_sha256 = _canonical_state_sha256(_load_state_from_sqlite(backup_path))
        if backup_state_sha256 != receipt.state_sha256:
            raise GovernanceError("SQLITE_BACKUP_STATE_HASH_MISMATCH")

        started_ns = perf_counter_ns()
        with self._lock:
            before_state_sha256 = _canonical_state_sha256(self.load())
            try:
                with sqlite3.connect(backup_path, timeout=10) as source, self._connect() as target:
                    source.backup(target)
                    target.commit()
            except sqlite3.Error as exc:
                raise GovernanceError("SQLITE_RESTORE_FAILED") from exc
            restored_state_sha256 = _canonical_state_sha256(self.load())
            if restored_state_sha256 != receipt.state_sha256:
                raise GovernanceError("SQLITE_RESTORE_STATE_HASH_MISMATCH")
            restored_integrity = _sqlite_integrity_check(self.path)

        if restored_integrity != backup_integrity:
            raise GovernanceError("SQLITE_RESTORE_INTEGRITY_MISMATCH")
        return SQLiteRestoreReceiptV1(
            backup_path=str(backup_path),
            backup_sha256=receipt.backup_sha256,
            before_state_sha256=before_state_sha256,
            restored_state_sha256=restored_state_sha256,
            restored_at=datetime.now(UTC).isoformat(),
            duration_ms=max(0, (perf_counter_ns() - started_ns) // 1_000_000),
            integrity_check=restored_integrity,
        )

    def is_healthy(self) -> bool:
        try:
            self.verify_integrity()
            return True
        except (sqlite3.Error, GovernanceError):
            return False
