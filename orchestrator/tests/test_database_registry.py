from __future__ import annotations

from pathlib import Path

import pytest

from palwakf_orchestrator.database_contracts import SupabaseCliToolStatus
from palwakf_orchestrator.database_registry import (
    CANONICAL_SUPABASE_TARGET_REF,
    DatabaseRegistryService,
)
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.supabase_cli import SupabaseCliAdapter


def cli_status() -> SupabaseCliToolStatus:
    return SupabaseCliToolStatus(available=True, version="test-version")


def test_canonical_database_target_is_seeded_without_remote_mutation() -> None:
    registry = DatabaseRegistryService(
        MemoryStateStore(),
        cli_status=cli_status(),
    )

    snapshot = registry.snapshot()

    assert snapshot.target.project_ref == CANONICAL_SUPABASE_TARGET_REF
    assert snapshot.target.status.value == "ACTIVE_HEALTHY"
    assert snapshot.target.remote_mutation_allowed is False
    assert snapshot.schema_status.value == "SUMMARY_ONLY"
    assert snapshot.reality_summary.application_schema_count == 35
    assert snapshot.reality_summary.table_count == 407
    assert snapshot.reality_summary.view_count == 248
    assert snapshot.reality_summary.approximate_column_count == 9948


def test_unknown_schema_object_never_guesses_a_name() -> None:
    registry = DatabaseRegistryService(
        MemoryStateStore(),
        cli_status=cli_status(),
    )

    result = registry.lookup("core", "imagined_table_name")

    assert result.status == "METADATA_REFRESH_REQUIRED"
    assert result.guessed_name_used is False
    assert result.object is None


def test_database_registry_lookup_does_not_damage_workspace_state() -> None:
    store = MemoryStateStore()
    registry = DatabaseRegistryService(store, cli_status=cli_status())

    assert registry.lookup("offline_project", "missing").status == "METADATA_REFRESH_REQUIRED"
    assert store.is_healthy() is True


def test_supabase_cli_remote_mutation_is_fail_closed(tmp_path: Path) -> None:
    adapter = SupabaseCliAdapter(tmp_path)

    with pytest.raises(
        PermissionError,
        match="SUPABASE_REMOTE_MUTATION_DENIED_BY_DEFAULT",
    ):
        adapter.remote_mutation("db", "push")
