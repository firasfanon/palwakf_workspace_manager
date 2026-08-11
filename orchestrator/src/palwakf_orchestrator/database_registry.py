from __future__ import annotations

from datetime import UTC, datetime

from palwakf_orchestrator.database_contracts import (
    DatabaseRegistrySnapshot,
    DatabaseTargetRecord,
    DatabaseTargetStatus,
    SchemaLookupResult,
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
        state = self._state_store.load()
        state["database_registry"] = updated.model_dump(mode="json")
        self._state_store.save(state)
        return updated

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
                application_schema_count=35,
                table_count=407,
                view_count=248,
                approximate_column_count=9948,
            ),
            cli=self._cli_status,
        )
        state["database_registry"] = snapshot.model_dump(mode="json")
        self._state_store.save(state)
