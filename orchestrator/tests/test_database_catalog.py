from __future__ import annotations

from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.database_catalog import (
    APPROVED_APPLICATION_SCHEMAS,
    NON_APPLICATION_SCHEMAS,
    build_boundary_drift_sql,
    build_catalog_sql,
    compute_schema_catalog_hash,
    validate_catalog_boundary,
)
from palwakf_orchestrator.database_contracts import (
    SchemaCatalogSnapshot,
    SchemaColumnRecordWithObject,
    SchemaObjectKind,
    SchemaRelationRecord,
)


def sample_catalog() -> SchemaCatalogSnapshot:
    return SchemaCatalogSnapshot(
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


def test_approved_application_schema_boundary_is_exact_and_stable() -> None:
    assert len(APPROVED_APPLICATION_SCHEMAS) == 35
    assert "pgbouncer" not in APPROVED_APPLICATION_SCHEMAS
    assert "supabase_migrations" not in APPROVED_APPLICATION_SCHEMAS
    assert "topology" not in APPROVED_APPLICATION_SCHEMAS
    assert {"pgbouncer", "supabase_migrations", "topology"} <= NON_APPLICATION_SCHEMAS


def test_catalog_sql_is_read_only_catalog_introspection() -> None:
    sql = build_catalog_sql().upper()
    assert sql.startswith("WITH APPROVED")
    for forbidden in (
        " INSERT ",
        " UPDATE ",
        " DELETE ",
        " ALTER ",
        " DROP ",
        " CREATE ",
        " TRUNCATE ",
        " GRANT ",
        " REVOKE ",
    ):
        assert forbidden not in f" {sql} "
    assert "PG_CATALOG" not in sql
    assert "PG_CLASS" in sql
    assert "PG_CONSTRAINT" in sql
    assert "PG_POLICY" in sql
    assert "INFORMATION_SCHEMA.VIEW_TABLE_USAGE" in sql


def test_boundary_drift_sql_is_read_only() -> None:
    sql = build_boundary_drift_sql().upper()
    assert sql.startswith("SELECT ")
    assert "PGBOUNCER" in sql
    assert "SUPABASE_MIGRATIONS" in sql
    assert "TOPOLOGY" in sql


def test_catalog_hash_ignores_capture_time_but_not_structure() -> None:
    first = sample_catalog()
    second = first.model_copy(update={"captured_at": datetime(2026, 8, 12, tzinfo=UTC)})
    assert compute_schema_catalog_hash(first) == compute_schema_catalog_hash(second)

    changed = first.model_copy(
        update={"columns": [first.columns[0].model_copy(update={"data_type": "text"})]}
    )
    assert compute_schema_catalog_hash(first) != compute_schema_catalog_hash(changed)


def test_catalog_boundary_fails_closed_on_unapproved_schema() -> None:
    catalog = sample_catalog().model_copy(
        update={"boundary_drift_schema_names": ["new_unapproved_schema"]}
    )
    with pytest.raises(ValueError, match="UNAPPROVED_SCHEMA_BOUNDARY_DRIFT"):
        validate_catalog_boundary(catalog)
