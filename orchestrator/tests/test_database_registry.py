from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from palwakf_orchestrator.database_catalog import APPROVED_APPLICATION_SCHEMAS
from palwakf_orchestrator.database_contracts import (
    SchemaCatalogSnapshot,
    SchemaColumnRecordWithObject,
    SchemaObjectKind,
    SchemaRelationRecord,
    SupabaseCliToolStatus,
)
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
    assert snapshot.reality_summary.rls_enabled_table_count == 290
    assert snapshot.reality_summary.primary_key_count == 391
    assert snapshot.reality_summary.foreign_key_count == 295
    assert snapshot.reality_summary.index_count == 1196
    assert snapshot.reality_summary.function_count == 717
    assert snapshot.reality_summary.policy_count == 318


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


def test_full_catalog_import_builds_exact_lookup_and_hash() -> None:
    registry = DatabaseRegistryService(
        MemoryStateStore(),
        cli_status=cli_status(),
    )
    catalog = SchemaCatalogSnapshot(
        database_target_id="PALWAKF_CANONICAL_SUPABASE",
        captured_at=datetime(2026, 8, 11, tzinfo=UTC),
        approved_schema_names=list(APPROVED_APPLICATION_SCHEMAS),
        relations=[
            SchemaRelationRecord(
                schema_name="core",
                object_name="projects",
                kind=SchemaObjectKind.table,
                owner_role="postgres",
                rls_enabled=True,
            )
        ],
        columns=[
            SchemaColumnRecordWithObject(
                schema_name="core",
                object_name="projects",
                name="id",
                data_type="uuid",
                nullable=False,
                ordinal=1,
            )
        ],
    )

    snapshot = registry.replace_catalog_snapshot(catalog)
    result = registry.lookup("core", "projects")

    assert snapshot.schema_status.value == "COMPLETE"
    assert snapshot.catalog is not None
    assert snapshot.schema_hash is not None
    assert result.status == "FOUND"
    assert result.object is not None
    assert result.object.columns[0].name == "id"


def test_full_catalog_import_fails_closed_on_boundary_drift() -> None:
    registry = DatabaseRegistryService(
        MemoryStateStore(),
        cli_status=cli_status(),
    )
    catalog = SchemaCatalogSnapshot(
        database_target_id="PALWAKF_CANONICAL_SUPABASE",
        captured_at=datetime(2026, 8, 11, tzinfo=UTC),
        approved_schema_names=list(APPROVED_APPLICATION_SCHEMAS),
        boundary_drift_schema_names=["unexpected_app_schema"],
    )

    with pytest.raises(ValueError, match="UNAPPROVED_SCHEMA_BOUNDARY_DRIFT"):
        registry.replace_catalog_snapshot(catalog)


def test_supabase_cli_remote_mutation_is_fail_closed(tmp_path: Path) -> None:
    adapter = SupabaseCliAdapter(tmp_path)

    with pytest.raises(
        PermissionError,
        match="SUPABASE_REMOTE_MUTATION_DENIED_BY_DEFAULT",
    ):
        adapter.remote_mutation("db", "push")
