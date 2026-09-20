from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import SQLiteStateStore


def _store(tmp_path: Path) -> SQLiteStateStore:
    return SQLiteStateStore(tmp_path / "state.sqlite3")


def test_backup_restore_round_trip_preserves_state_and_writer(tmp_path: Path) -> None:
    store = _store(tmp_path)
    original = {"project": "PALWAKF_WORKSPACE_MANAGER", "sequence": 1, "nested": {"ok": True}}
    store.save(original)
    assert store.acquire_repository_writer(
        "firasfanon/palwakf_workspace_manager",
        "L5-002",
        "DESKTOP-S5A0JSB",
    )

    backup = store.create_backup(tmp_path / "backup.sqlite3")
    assert backup.integrity_check == ("ok",)
    assert backup.size_bytes > 0
    assert len(backup.backup_sha256) == 64
    assert len(backup.state_sha256) == 64

    store.save({"project": "PALWAKF_WORKSPACE_MANAGER", "sequence": 2})
    store.release_repository_writer("firasfanon/palwakf_workspace_manager", "L5-002")
    assert store.load()["sequence"] == 2
    assert store.writer_for("firasfanon/palwakf_workspace_manager") is None

    restored = store.restore_backup(backup)
    assert restored.integrity_check == ("ok",)
    assert restored.restored_state_sha256 == backup.state_sha256

    restarted = SQLiteStateStore(store.path)
    assert restarted.load() == original
    writer = restarted.writer_for("firasfanon/palwakf_workspace_manager")
    assert writer is not None
    assert writer["task_id"] == "L5-002"
    assert writer["execution_host_id"] == "DESKTOP-S5A0JSB"
    assert restarted.is_healthy() is True


def test_corrupted_backup_fails_closed_before_target_mutation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save({"sequence": 1})
    backup = store.create_backup(tmp_path / "backup.sqlite3")
    store.save({"sequence": 2})

    with Path(backup.backup_path).open("ab") as handle:
        handle.write(b"tamper")

    with pytest.raises(GovernanceError, match="SQLITE_BACKUP_SHA256_MISMATCH"):
        store.restore_backup(backup)

    assert store.load() == {"sequence": 2}


def test_receipt_state_hash_mismatch_fails_before_restore(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save({"sequence": 1})
    backup = store.create_backup(tmp_path / "backup.sqlite3")
    store.save({"sequence": 2})

    forged = replace(backup, state_sha256="0" * 64)
    with pytest.raises(GovernanceError, match="SQLITE_BACKUP_STATE_HASH_MISMATCH"):
        store.restore_backup(forged)

    assert store.load() == {"sequence": 2}


def test_backup_destination_must_be_new_and_distinct(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save({"sequence": 1})

    with pytest.raises(
        GovernanceError,
        match="SQLITE_BACKUP_TARGET_MUST_DIFFER_FROM_SOURCE",
    ):
        store.create_backup(store.path)

    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"occupied")
    with pytest.raises(
        GovernanceError,
        match="SQLITE_BACKUP_TARGET_ALREADY_EXISTS",
    ):
        store.create_backup(existing)


def test_restore_requires_existing_distinct_backup(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save({"sequence": 1})
    backup = store.create_backup(tmp_path / "backup.sqlite3")

    missing = replace(backup, backup_path=str(tmp_path / "missing.sqlite3"))
    with pytest.raises(GovernanceError, match="SQLITE_BACKUP_NOT_FOUND"):
        store.restore_backup(missing)

    self_source = replace(backup, backup_path=str(store.path))
    with pytest.raises(
        GovernanceError,
        match="SQLITE_RESTORE_SOURCE_MUST_DIFFER_FROM_TARGET",
    ):
        store.restore_backup(self_source)


def test_integrity_check_is_explicit_and_healthy(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save({"sequence": 1})

    assert store.verify_integrity() == ("ok",)
    assert store.is_healthy() is True
