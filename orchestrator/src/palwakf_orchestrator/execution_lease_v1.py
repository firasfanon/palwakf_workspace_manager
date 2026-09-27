from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError


class LeaseRevocationState(StrEnum):
    active = "ACTIVE"
    revoked = "REVOKED"


class LeaseWriteAuthority(StrEnum):
    none = "NONE"
    bounded_source_write = "BOUNDED_SOURCE_WRITE"


class ExecutionLeaseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    compatibility_version: Literal["1"] = "1"
    contract_type: Literal["ExecutionLease"] = "ExecutionLease"
    project_id: str = Field(min_length=2, max_length=160)
    task_id: str = Field(min_length=2, max_length=160)
    correlation_id: str = Field(min_length=2, max_length=160)
    authority_scope: Literal["WORKSPACE_GOVERNED_EXECUTION"] = (
        "WORKSPACE_GOVERNED_EXECUTION"
    )
    producer: Literal["Workspace"] = "Workspace"
    created_at: datetime
    provenance: tuple[str, ...] = Field(min_length=1, max_length=64)

    lease_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
    granted_scope: Literal["READ_ONLY_EXECUTION", "BOUNDED_SOURCE_WRITE"]
    expires_at: datetime
    allowed_capabilities: tuple[str, ...] = Field(min_length=1, max_length=64)
    allowed_tools: tuple[str, ...] = Field(default=(), max_length=64)
    write_authority: LeaseWriteAuthority
    revocation_state: LeaseRevocationState = LeaseRevocationState.active

    allowed_provider_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    allowed_agent_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    allowed_model_ids: tuple[str, ...] = Field(default=(), max_length=64)
    exact_base: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    branch: str = Field(pattern=r"^task/[A-Za-z0-9._/-]{3,180}$")
    allowed_paths: tuple[str, ...] = Field(default=(), max_length=128)
    forbidden_operations: tuple[str, ...] = Field(default=(), max_length=128)
    approval_reference: str = Field(min_length=8, max_length=2_000)

    @model_validator(mode="after")
    def validate_authority(self) -> ExecutionLeaseV1:
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("LEASE_TIMESTAMPS_MUST_BE_TIMEZONE_AWARE")
        if self.expires_at <= self.created_at:
            raise ValueError("LEASE_EXPIRY_MUST_FOLLOW_CREATION")
        if (self.expires_at - self.created_at).total_seconds() > 7200:
            raise ValueError("LEASE_DURATION_EXCEEDS_TWO_HOURS")

        collections = (
            self.allowed_capabilities,
            self.allowed_tools,
            self.allowed_provider_ids,
            self.allowed_agent_ids,
            self.allowed_model_ids,
            self.allowed_paths,
            self.forbidden_operations,
            self.provenance,
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("LEASE_COLLECTIONS_MUST_NOT_CONTAIN_DUPLICATES")
        if any(not value.strip() for values in collections for value in values):
            raise ValueError("LEASE_COLLECTION_VALUES_MUST_BE_NONEMPTY")

        if self.granted_scope == "READ_ONLY_EXECUTION":
            if self.write_authority != LeaseWriteAuthority.none:
                raise ValueError("READ_ONLY_LEASE_CANNOT_GRANT_WRITE_AUTHORITY")
            if self.allowed_paths:
                raise ValueError("READ_ONLY_LEASE_CANNOT_GRANT_WRITE_PATHS")
        else:
            if self.write_authority != LeaseWriteAuthority.bounded_source_write:
                raise ValueError("BOUNDED_WRITE_SCOPE_REQUIRES_WRITE_AUTHORITY")
            if not self.allowed_paths:
                raise ValueError("BOUNDED_WRITE_SCOPE_REQUIRES_ALLOWED_PATHS")

        if any(
            token in capability.lower()
            for capability in self.allowed_capabilities
            for token in ("production", "shared_db", "shared-db")
        ):
            raise ValueError("LEASE_CANNOT_GRANT_PRODUCTION_OR_SHARED_DB_CAPABILITY")

        return self

    def assert_active(self, *, now: datetime | None = None) -> None:
        observed = now or datetime.now(UTC)
        if observed.tzinfo is None:
            raise GovernanceError("LEASE_CHECK_TIME_MUST_BE_TIMEZONE_AWARE")
        if self.revocation_state != LeaseRevocationState.active:
            raise GovernanceError("EXECUTION_LEASE_REVOKED")
        if observed >= self.expires_at:
            raise GovernanceError("EXECUTION_LEASE_EXPIRED")


class ExecutionLeaseRouteClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    task_id: str
    correlation_id: str
    agent_id: str
    provider_ids: tuple[str, ...]
    model_id: str | None = None
    tool_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    mutation_class: Literal["READ_ONLY", "SOURCE_WRITE"] = "READ_ONLY"


def validate_execution_lease_claim_v1(
    lease: ExecutionLeaseV1,
    claim: ExecutionLeaseRouteClaimV1,
    *,
    now: datetime | None = None,
) -> None:
    lease.assert_active(now=now)

    if claim.project_id != lease.project_id:
        raise GovernanceError("LEASE_PROJECT_MISMATCH")
    if claim.task_id != lease.task_id:
        raise GovernanceError("LEASE_TASK_MISMATCH")
    if claim.correlation_id != lease.correlation_id:
        raise GovernanceError("LEASE_CORRELATION_MISMATCH")
    if claim.agent_id not in lease.allowed_agent_ids:
        raise GovernanceError("LEASE_AGENT_NOT_ALLOWED")
    if any(provider not in lease.allowed_provider_ids for provider in claim.provider_ids):
        raise GovernanceError("LEASE_PROVIDER_NOT_ALLOWED")
    if claim.model_id is not None and claim.model_id not in lease.allowed_model_ids:
        raise GovernanceError("LEASE_MODEL_NOT_ALLOWED")
    if any(tool not in lease.allowed_tools for tool in claim.tool_ids):
        raise GovernanceError("LEASE_TOOL_NOT_ALLOWED")
    if any(
        capability not in lease.allowed_capabilities
        for capability in claim.capability_ids
    ):
        raise GovernanceError("LEASE_CAPABILITY_NOT_ALLOWED")
    if (
        claim.mutation_class == "SOURCE_WRITE"
        and lease.write_authority != LeaseWriteAuthority.bounded_source_write
    ):
        raise GovernanceError("LEASE_WRITE_AUTHORITY_REQUIRED")
