from __future__ import annotations

import fnmatch
import hashlib
import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.execution_lease_v1 import ExecutionLeaseV1, LeaseWriteAuthority


REMOTE_CAPABILITY_IDS: tuple[str, ...] = (
    "mesh_device_info",
    "mesh_hostname",
    "file_read",
    "temp_write",
    "temp_delete",
    "bounded_powershell",
    "process_port_readback",
    "git_readback",
    "playwright_screenshot_uat",
    "audit_readback",
)

REMOTE_TOOL_BY_CAPABILITY: dict[str, str] = {
    capability: f"palwakf-remote-mcp.{capability}" for capability in REMOTE_CAPABILITY_IDS
}


class RemoteActionClassV1(StrEnum):
    read_only = "READ_ONLY"
    bounded_temp_mutation = "BOUNDED_TEMP_MUTATION"
    bounded_command = "BOUNDED_COMMAND"
    browser_uat = "BROWSER_UAT"


_ACTION_CLASS_BY_CAPABILITY: dict[str, RemoteActionClassV1] = {
    "mesh_device_info": RemoteActionClassV1.read_only,
    "mesh_hostname": RemoteActionClassV1.read_only,
    "file_read": RemoteActionClassV1.read_only,
    "temp_write": RemoteActionClassV1.bounded_temp_mutation,
    "temp_delete": RemoteActionClassV1.bounded_temp_mutation,
    "bounded_powershell": RemoteActionClassV1.bounded_command,
    "process_port_readback": RemoteActionClassV1.read_only,
    "git_readback": RemoteActionClassV1.read_only,
    "playwright_screenshot_uat": RemoteActionClassV1.browser_uat,
    "audit_readback": RemoteActionClassV1.read_only,
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _relative_path(value: str) -> str | None:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    if path.parts and ":" in path.parts[0]:
        return None
    return path.as_posix()


class RemoteExecutionTransportProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: Literal["palwakf-remote-mcp"] = "palwakf-remote-mcp"
    provider_kind: Literal["EXECUTION_TRANSPORT"] = "EXECUTION_TRANSPORT"
    authority_scope: Literal["NO_SOVEREIGN_AUTHORITY"] = "NO_SOVEREIGN_AUTHORITY"
    lifecycle: Literal["ADMITTED"]
    health: Literal["HEALTHY"]
    admitted_capabilities: tuple[str, ...] = Field(min_length=1, max_length=10)
    route_eligible: Literal[True] = True
    transport_only: Literal[True] = True
    arbitrary_shell_exposed: Literal[False] = False
    bounded_source_write_admitted: Literal[False] = False

    @model_validator(mode="after")
    def validate_capabilities(self) -> "RemoteExecutionTransportProjectionV1":
        if len(set(self.admitted_capabilities)) != len(self.admitted_capabilities):
            raise ValueError("REMOTE_TRANSPORT_CAPABILITIES_MUST_BE_UNIQUE")
        unknown = set(self.admitted_capabilities) - set(REMOTE_CAPABILITY_IDS)
        if unknown:
            raise ValueError(f"REMOTE_TRANSPORT_CAPABILITY_UNKNOWN:{sorted(unknown)}")
        return self


class WorkspaceRemoteExecutionScopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
    lease_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
    owner: Literal["Workspace"] = "Workspace"
    allowed_path_patterns: tuple[str, ...] = Field(default=(), max_length=64)
    allowed_bounded_operation_ids: tuple[str, ...] = Field(default=(), max_length=64)
    bounded_mutations_temp_only: Literal[True] = True
    authority_expansion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_scope(self) -> "WorkspaceRemoteExecutionScopeV1":
        collections = (self.allowed_path_patterns, self.allowed_bounded_operation_ids)
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("REMOTE_SCOPE_COLLECTIONS_MUST_BE_UNIQUE")
        for pattern in self.allowed_path_patterns:
            normalized = pattern.replace("\\", "/").strip()
            if not normalized or normalized.startswith("/"):
                raise ValueError("REMOTE_SCOPE_PATH_PATTERN_INVALID")
            parts = PurePosixPath(normalized).parts
            if ".." in parts or (parts and ":" in parts[0]):
                raise ValueError("REMOTE_SCOPE_PATH_PATTERN_INVALID")
        return self


class AutonomousExecutionRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    task_id: str
    correlation_id: str
    branch: str
    current_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    agent_id: str
    capability_id: str
    tool_id: str
    requested_relative_paths: tuple[str, ...] = Field(default=(), max_length=128)
    bounded_operation_id: str | None = Field(default=None, max_length=160)
    raw_shell: None = None
    source_write_requested: Literal[False] = False
    manual_terminal_requested: Literal[False] = False


class AutonomousExecutionBindingReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["ALLOW", "DENY"]
    blockers: tuple[str, ...]
    provider_id: Literal["palwakf-remote-mcp"] = "palwakf-remote-mcp"
    capability_id: str
    tool_id: str
    action_class: RemoteActionClassV1
    lease_id: str
    scope_id: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_owner: Literal["Workspace"] = "Workspace"
    execution_router: Literal["Agentic"] = "Agentic"
    transport_only: Literal[True] = True
    arbitrary_shell_exposed: Literal[False] = False
    source_write_authorized: Literal[False] = False
    manual_terminal_fallback: Literal[False] = False
    no_authority_expansion: Literal[True] = True


def evaluate_autonomous_execution_binding_v1(
    *,
    request: AutonomousExecutionRequestV1,
    lease: ExecutionLeaseV1,
    scope: WorkspaceRemoteExecutionScopeV1,
    transport: RemoteExecutionTransportProjectionV1,
    now=None,
) -> AutonomousExecutionBindingReceiptV1:
    blockers: list[str] = []
    try:
        lease.assert_active(now=now)
    except Exception as exc:
        blockers.append(str(exc))

    if request.project_id != lease.project_id:
        blockers.append("LEASE_PROJECT_MISMATCH")
    if request.task_id != lease.task_id:
        blockers.append("LEASE_TASK_MISMATCH")
    if request.correlation_id != lease.correlation_id:
        blockers.append("LEASE_CORRELATION_MISMATCH")
    if request.branch != lease.branch:
        blockers.append("LEASE_BRANCH_MISMATCH")
    if request.current_head.lower() != lease.exact_base.lower():
        blockers.append("LEASE_EXACT_BASE_MISMATCH")
    if request.agent_id not in lease.allowed_agent_ids:
        blockers.append("LEASE_AGENT_NOT_ALLOWED")
    if "palwakf-remote-mcp" not in lease.allowed_provider_ids:
        blockers.append("LEASE_REMOTE_TRANSPORT_PROVIDER_NOT_ALLOWED")

    expected_tool = REMOTE_TOOL_BY_CAPABILITY.get(request.capability_id)
    if expected_tool is None:
        blockers.append("REMOTE_CAPABILITY_UNKNOWN")
        action_class = RemoteActionClassV1.read_only
    else:
        action_class = _ACTION_CLASS_BY_CAPABILITY[request.capability_id]
        if request.tool_id != expected_tool:
            blockers.append("REMOTE_TOOL_CAPABILITY_MISMATCH")

    if request.capability_id not in lease.allowed_capabilities:
        blockers.append("LEASE_REMOTE_CAPABILITY_NOT_ALLOWED")
    if request.tool_id not in lease.allowed_tools:
        blockers.append("LEASE_REMOTE_TOOL_NOT_ALLOWED")
    if request.capability_id not in transport.admitted_capabilities:
        blockers.append("REMOTE_CAPABILITY_NOT_ADMITTED")
    if lease.write_authority != LeaseWriteAuthority.none:
        blockers.append("P2_SOURCE_WRITE_AUTHORITY_FORBIDDEN")
    if lease.granted_scope != "READ_ONLY_EXECUTION":
        blockers.append("P2_LEASE_SCOPE_MUST_REMAIN_READ_ONLY_EXECUTION")
    if scope.lease_id != lease.lease_id:
        blockers.append("REMOTE_SCOPE_LEASE_MISMATCH")

    path_capabilities = {"file_read", "temp_write", "temp_delete"}
    if request.capability_id in path_capabilities:
        if not request.requested_relative_paths:
            blockers.append("REMOTE_PATH_REQUIRED")
        for raw in request.requested_relative_paths:
            normalized = _relative_path(raw)
            if normalized is None:
                blockers.append("REMOTE_PATH_INVALID")
                continue
            if not any(
                fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/"))
                for pattern in scope.allowed_path_patterns
            ):
                blockers.append("REMOTE_PATH_OUT_OF_WORKSPACE_SCOPE")
    elif request.requested_relative_paths:
        blockers.append("REMOTE_PATHS_NOT_ALLOWED_FOR_CAPABILITY")

    if request.capability_id == "bounded_powershell":
        if not request.bounded_operation_id:
            blockers.append("BOUNDED_OPERATION_ID_REQUIRED")
        elif request.bounded_operation_id not in scope.allowed_bounded_operation_ids:
            blockers.append("BOUNDED_OPERATION_NOT_IN_WORKSPACE_SCOPE")
    elif request.bounded_operation_id is not None:
        blockers.append("BOUNDED_OPERATION_ONLY_VALID_FOR_BOUNDED_POWERSHELL")

    unique = tuple(dict.fromkeys(blockers))
    return AutonomousExecutionBindingReceiptV1(
        decision="ALLOW" if not unique else "DENY",
        blockers=unique,
        capability_id=request.capability_id,
        tool_id=request.tool_id,
        action_class=action_class,
        lease_id=lease.lease_id,
        scope_id=scope.scope_id,
        request_sha256=_sha256(request.model_dump(mode="json")),
    )


class AutonomousExecutionEvidenceEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    contract_type: Literal["EvidenceEnvelope"] = "EvidenceEnvelope"
    producer: Literal["Workspace"] = "Workspace"
    provider_id: Literal["palwakf-remote-mcp"] = "palwakf-remote-mcp"
    lease_id: str
    scope_id: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    capability_id: str
    tool_id: str
    execution_status: Literal["PASS", "FAIL"]
    audit_reference: str = Field(min_length=1, max_length=1000)
    runtime_evidence: tuple[str, ...] = Field(min_length=1, max_length=64)
    manual_terminal_used: bool = False
    authority_violations: Literal[0] = 0
    no_authority_expansion: Literal[True] = True
