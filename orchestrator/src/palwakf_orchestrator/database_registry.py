from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from palwakf_orchestrator.database_catalog import (
    APPROVED_APPLICATION_SCHEMAS,
    compute_schema_catalog_hash,
    validate_catalog_boundary,
)
from palwakf_orchestrator.database_contracts import (
    DatabaseRegistrySnapshot,
    DatabaseTargetRecord,
    DatabaseTargetStatus,
    SchemaCatalogSnapshot,
    SchemaColumnRecord,
    SchemaColumnRecordWithObject,
    SchemaLookupResult,
    SchemaObjectKind,
    SchemaObjectRecord,
    SchemaRealitySummary,
    SchemaRegistryStatus,
    SupabaseCliToolStatus,
)
from palwakf_orchestrator.persistence import StateStore

CANONICAL_SUPABASE_TARGET_REF = "lyeryfsrhrxuepuqepgi"
CANONICAL_SUPABASE_TARGET_NAME = "waqf Project fit@1975Ff"
CANONICAL_SUPABASE_REGION = "eu-central-1"


class DatabaseRegistryService:
    """Persistent database metadata registry; never a remote mutation surface."""

    def __init__(
        self,
        state_store: StateStore,
        *,
        cli_status: SupabaseCliToolStatus,
    ) -> None:
        self._state_store = state_store
        self._cli_status = cli_status
        self._ensure_seed()

    def snapshot(self) -> DatabaseRegistrySnapshot:
        state = self._state_store.load()
        raw = state.get("database_registry")
        if not isinstance(raw, dict):
            self._ensure_seed()
            state = self._state_store.load()
            raw = state.get("database_registry")
        return DatabaseRegistrySnapshot.model_validate(raw)

    def target(self) -> DatabaseTargetRecord:
        return self.snapshot().target

    def lookup(self, schema_name: str, object_name: str) -> SchemaLookupResult:
        snapshot = self.snapshot()
        for item in snapshot.objects:
            if item.schema_name == schema_name and item.object_name == object_name:
                return SchemaLookupResult(
                    status="FOUND",
                    schema_name=schema_name,
                    object_name=object_name,
                    object=item,
                )
        return SchemaLookupResult(
            status="METADATA_REFRESH_REQUIRED",
            schema_name=schema_name,
            object_name=object_name,
        )

    def replace_schema_snapshot(
        self,
        *,
        objects: list[SchemaObjectRecord],
        schema_hash: str,
        captured_at: datetime,
    ) -> DatabaseRegistrySnapshot:
        current = self.snapshot()
        updated = current.model_copy(
            update={
                "schema_status": SchemaRegistryStatus.complete,
                "objects": objects,
                "last_schema_refresh_at": captured_at,
                "schema_hash": schema_hash,
            }
        )
        self._persist(updated)
        return updated

    def replace_catalog_snapshot(
        self,
        catalog: SchemaCatalogSnapshot,
    ) -> DatabaseRegistrySnapshot:
        validate_catalog_boundary(catalog)
        if catalog.database_target_id != "PALWAKF_CANONICAL_SUPABASE":
            raise ValueError(
                "DATABASE_TARGET_MISMATCH:"
                f"expected=PALWAKF_CANONICAL_SUPABASE actual={catalog.database_target_id}"
            )

        relations = {(item.schema_name, item.object_name): item for item in catalog.relations}
        columns_by_object: dict[tuple[str, str], list[SchemaColumnRecordWithObject]] = defaultdict(
            list
        )
        for column in catalog.columns:
            columns_by_object[(column.schema_name, column.object_name)].append(column)

        objects: list[SchemaObjectRecord] = []
        for key in sorted(relations):
            relation = relations[key]
            columns = sorted(columns_by_object.get(key, []), key=lambda item: item.ordinal)
            objects.append(
                SchemaObjectRecord(
                    schema_name=relation.schema_name,
                    object_name=relation.object_name,
                    kind=relation.kind,
                    columns=[
                        SchemaColumnRecord(
                            name=column.name,
                            data_type=column.data_type,
                            nullable=column.nullable,
                            ordinal=column.ordinal,
                            default_expression=column.default_expression,
                            generated=column.generated,
                            identity=column.identity,
                        )
                        for column in columns
                    ],
                )
            )

        table_kinds = {SchemaObjectKind.table, SchemaObjectKind.partitioned_table}
        table_count = sum(item.kind in table_kinds for item in catalog.relations)
        view_count = sum(item.kind == SchemaObjectKind.view for item in catalog.relations)
        materialized_view_count = sum(
            item.kind == SchemaObjectKind.materialized_view for item in catalog.relations
        )
        rls_enabled_table_count = sum(
            item.kind in table_kinds and item.rls_enabled for item in catalog.relations
        )

        primary_key_count = sum(item.kind.value == "PRIMARY_KEY" for item in catalog.constraints)
        foreign_key_count = sum(item.kind.value == "FOREIGN_KEY" for item in catalog.constraints)
        unique_constraint_count = sum(item.kind.value == "UNIQUE" for item in catalog.constraints)

        summary = SchemaRealitySummary(
            application_schema_count=len(catalog.approved_schema_names),
            table_count=table_count,
            view_count=view_count,
            materialized_view_count=materialized_view_count,
            approximate_column_count=len(catalog.columns),
            rls_enabled_table_count=rls_enabled_table_count,
            primary_key_count=primary_key_count,
            foreign_key_count=foreign_key_count,
            unique_constraint_count=unique_constraint_count,
            index_count=len(catalog.indexes),
            function_count=len(catalog.functions),
            trigger_count=len(catalog.triggers),
            policy_count=len(catalog.policies),
            enum_type_count=len(catalog.enums),
        )

        current = self.snapshot()
        schema_hash = compute_schema_catalog_hash(catalog)
        updated = current.model_copy(
            update={
                "schema_status": SchemaRegistryStatus.complete,
                "reality_summary": summary,
                "objects": objects,
                "last_schema_refresh_at": catalog.captured_at,
                "schema_hash": schema_hash,
                "catalog": catalog,
            }
        )
        self._persist(updated)
        return updated

    def _persist(self, snapshot: DatabaseRegistrySnapshot) -> None:
        state = self._state_store.load()
        state["database_registry"] = snapshot.model_dump(mode="json")
        self._state_store.save(state)

    def _ensure_seed(self) -> None:
        state = self._state_store.load()
        if isinstance(state.get("database_registry"), dict):
            return

        now = datetime.now(UTC)
        snapshot = DatabaseRegistrySnapshot(
            target=DatabaseTargetRecord(
                target_id="PALWAKF_CANONICAL_SUPABASE",
                project_ref=CANONICAL_SUPABASE_TARGET_REF,
                project_name=CANONICAL_SUPABASE_TARGET_NAME,
                region=CANONICAL_SUPABASE_REGION,
                status=DatabaseTargetStatus.active_healthy,
                last_verified_at=now,
            ),
            schema_status=SchemaRegistryStatus.summary_only,
            reality_summary=SchemaRealitySummary(
                application_schema_count=len(APPROVED_APPLICATION_SCHEMAS),
                table_count=407,
                view_count=248,
                approximate_column_count=9948,
                rls_enabled_table_count=290,
                primary_key_count=391,
                foreign_key_count=295,
                unique_constraint_count=130,
                index_count=1196,
                function_count=717,
                trigger_count=87,
                policy_count=318,
                enum_type_count=17,
            ),
            cli=self._cli_status,
        )
        state["database_registry"] = snapshot.model_dump(mode="json")
        self._state_store.save(state)
