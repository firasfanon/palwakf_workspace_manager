from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast


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

    def is_healthy(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
