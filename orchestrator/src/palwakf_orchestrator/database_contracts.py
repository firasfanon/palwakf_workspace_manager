from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DatabaseTargetStatus(StrEnum):
    active_healthy = "ACTIVE_HEALTHY"
    degraded = "DEGRADED"
    unreachable = "UNREACHABLE"
    unknown = "UNKNOWN"


class SchemaRegistryStatus(StrEnum):
    summary_only = "SUMMARY_ONLY"
    complete = "COMPLETE"
    stale = "STALE"
    refresh_required = "REFRESH_REQUIRED"


class SchemaObjectKind(StrEnum):
    table = "TABLE"
    partitioned_table = "PARTITIONED_TABLE"
    view = "VIEW"
    materialized_view = "MATERIALIZED_VIEW"
    function = "FUNCTION"
    rpc = "RPC"


class DatabaseTargetRecord(BaseModel):
    target_id: str
    provider: Literal["supabase"] = "supabase"
    project_ref: str
    project_name: str
    region: str
    status: DatabaseTargetStatus
    canonical: bool = True
    remote_mutation_allowed: Literal[False] = False
    last_verified_at: datetime | None = None


class SchemaRealitySummary(BaseModel):
    snapshot_version: Literal["DATABASE_REALITY_BASELINE_R1"] = "DATABASE_REALITY_BASELINE_R1"
    application_schema_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    view_count: int = Field(ge=0)
    approximate_column_count: int = Field(ge=0)
    source: Literal["SUPABASE_READ_ONLY_CATALOG_QUERY"] = "SUPABASE_READ_ONLY_CATALOG_QUERY"
    excludes_internal_service_schemas: bool = True


class SchemaColumnRecord(BaseModel):
    name: str
    data_type: str
    nullable: bool
    ordinal: int = Field(ge=1)


class SchemaObjectRecord(BaseModel):
    schema_name: str
    object_name: str
    kind: SchemaObjectKind
    columns: list[SchemaColumnRecord] = Field(default_factory=list)
    owner_project_id: str | None = None
    consumer_project_ids: list[str] = Field(default_factory=list)
    compatibility_version: str | None = None


class SchemaLookupResult(BaseModel):
    status: Literal["FOUND", "METADATA_REFRESH_REQUIRED"]
    schema_name: str
    object_name: str
    object: SchemaObjectRecord | None = None
    guessed_name_used: Literal[False] = False


class SupabaseCliToolStatus(BaseModel):
    provider_id: Literal["supabase_cli"] = "supabase_cli"
    installation_model: Literal["PROJECT_SCOPED_PINNED_DEV_DEPENDENCY"] = (
        "PROJECT_SCOPED_PINNED_DEV_DEPENDENCY"
    )
    available: bool
    version: str | None = None
    invocation: Literal["PROJECT_LOCAL_BINARY"] = "PROJECT_LOCAL_BINARY"
    remote_mutation_allowed: Literal[False] = False
    allowed_capabilities: list[str] = Field(
        default_factory=lambda: [
            "VERSION",
            "HELP",
            "LOCAL_METADATA_PREPARATION",
        ]
    )


class DatabaseRegistrySnapshot(BaseModel):
    registry_version: Literal["DATABASE_SCHEMA_REGISTRY_R2_FOUNDATION"] = (
        "DATABASE_SCHEMA_REGISTRY_R2_FOUNDATION"
    )
    target: DatabaseTargetRecord
    schema_status: SchemaRegistryStatus
    reality_summary: SchemaRealitySummary
    objects: list[SchemaObjectRecord] = Field(default_factory=list)
    cli: SupabaseCliToolStatus
    last_schema_refresh_at: datetime | None = None
    schema_hash: str | None = None
