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


class SchemaConstraintKind(StrEnum):
    primary_key = "PRIMARY_KEY"
    foreign_key = "FOREIGN_KEY"
    unique = "UNIQUE"
    check = "CHECK"
    exclusion = "EXCLUSION"


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
    materialized_view_count: int = Field(default=0, ge=0)
    rls_enabled_table_count: int = Field(default=0, ge=0)
    primary_key_count: int = Field(default=0, ge=0)
    foreign_key_count: int = Field(default=0, ge=0)
    unique_constraint_count: int = Field(default=0, ge=0)
    index_count: int = Field(default=0, ge=0)
    function_count: int = Field(default=0, ge=0)
    trigger_count: int = Field(default=0, ge=0)
    policy_count: int = Field(default=0, ge=0)
    enum_type_count: int = Field(default=0, ge=0)


class SchemaColumnRecord(BaseModel):
    name: str
    data_type: str
    nullable: bool
    ordinal: int = Field(ge=1)
    default_expression: str | None = None
    generated: str | None = None
    identity: str | None = None


class SchemaObjectRecord(BaseModel):
    schema_name: str
    object_name: str
    kind: SchemaObjectKind
    columns: list[SchemaColumnRecord] = Field(default_factory=list)
    owner_project_id: str | None = None
    consumer_project_ids: list[str] = Field(default_factory=list)
    compatibility_version: str | None = None


class SchemaRelationRecord(BaseModel):
    schema_name: str
    object_name: str
    kind: SchemaObjectKind
    owner_role: str
    rls_enabled: bool = False
    rls_forced: bool = False
    definition: str | None = None


class SchemaConstraintRecord(BaseModel):
    schema_name: str
    object_name: str
    constraint_name: str
    kind: SchemaConstraintKind
    columns: list[str] = Field(default_factory=list)
    referenced_schema_name: str | None = None
    referenced_object_name: str | None = None
    referenced_columns: list[str] = Field(default_factory=list)
    definition: str


class SchemaIndexRecord(BaseModel):
    schema_name: str
    object_name: str
    index_name: str
    unique: bool
    primary: bool
    valid: bool
    definition: str


class SchemaFunctionRecord(BaseModel):
    schema_name: str
    function_name: str
    identity_arguments: str
    result_type: str
    language: str
    security_definer: bool
    volatility: str
    parallel_safety: str


class SchemaTriggerRecord(BaseModel):
    schema_name: str
    object_name: str
    trigger_name: str
    enabled: str
    definition: str


class SchemaPolicyRecord(BaseModel):
    schema_name: str
    object_name: str
    policy_name: str
    command: str
    permissive: bool
    roles: list[str] = Field(default_factory=list)
    using_expression: str | None = None
    check_expression: str | None = None


class SchemaEnumRecord(BaseModel):
    schema_name: str
    enum_name: str
    values: list[str] = Field(default_factory=list)


class SchemaGrantRecord(BaseModel):
    object_kind: Literal["TABLE_OR_VIEW", "ROUTINE"]
    schema_name: str
    object_name: str
    grantee: str
    privileges: list[str] = Field(default_factory=list)


class SchemaDependencyRecord(BaseModel):
    source_schema_name: str
    source_object_name: str
    target_schema_name: str
    target_object_name: str
    dependency_type: Literal["VIEW_USES_RELATION"] = "VIEW_USES_RELATION"


class SchemaColumnRecordWithObject(SchemaColumnRecord):
    schema_name: str
    object_name: str


class SchemaCatalogSnapshot(BaseModel):
    catalog_version: Literal["PALWAKF_SCHEMA_CATALOG_R2"] = "PALWAKF_SCHEMA_CATALOG_R2"
    database_target_id: str
    captured_at: datetime
    approved_schema_names: list[str]
    boundary_drift_schema_names: list[str] = Field(default_factory=list)
    relations: list[SchemaRelationRecord] = Field(default_factory=list)
    columns: list[SchemaColumnRecordWithObject] = Field(default_factory=list)
    constraints: list[SchemaConstraintRecord] = Field(default_factory=list)
    indexes: list[SchemaIndexRecord] = Field(default_factory=list)
    functions: list[SchemaFunctionRecord] = Field(default_factory=list)
    triggers: list[SchemaTriggerRecord] = Field(default_factory=list)
    policies: list[SchemaPolicyRecord] = Field(default_factory=list)
    enums: list[SchemaEnumRecord] = Field(default_factory=list)
    grants: list[SchemaGrantRecord] = Field(default_factory=list)
    dependencies: list[SchemaDependencyRecord] = Field(default_factory=list)


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
    catalog: SchemaCatalogSnapshot | None = None
