from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.autonomous_execution_channel_v1 import (
    REMOTE_CAPABILITY_IDS,
    REMOTE_TOOL_BY_CAPABILITY,
    AutonomousExecutionEvidenceEnvelopeV1,
    AutonomousExecutionRequestV1,
    RemoteExecutionTransportProjectionV1,
    WorkspaceRemoteExecutionScopeV1,
    evaluate_autonomous_execution_binding_v1,
)
from palwakf_orchestrator.execution_lease_v1 import ExecutionLeaseV1


HEAD = "c208a5e8b6de47f91d578b9b91f69c27d191edea"
BRANCH = "task/WORKSPACE-AUTONOMOUS-LOCAL-AI-MEGA-BATCH-V1"


def lease(
    capability: str = "mesh_hostname",
    *,
    tool: str | None = None,
    write: bool = False,
) -> ExecutionLeaseV1:
    now = datetime.now(UTC)
    tool_id = tool or REMOTE_TOOL_BY_CAPABILITY[capability]
    data = {
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "task_id": "AUTONOMOUS-EXECUTION-CHANNEL-BINDING-V1",
        "correlation_id": "autonomous-execution-channel-binding-v1",
        "created_at": now,
        "provenance": ("test",),
        "lease_id": "lease-autonomous-channel-binding-v1",
        "granted_scope": "READ_ONLY_EXECUTION",
        "expires_at": now + timedelta(minutes=20),
        "allowed_capabilities": (capability,),
        "allowed_tools": (tool_id,),
        "write_authority": "NONE",
        "revocation_state": "ACTIVE",
        "allowed_provider_ids": ("palwakf-remote-mcp",),
        "allowed_agent_ids": ("coordinator_agentic_v1",),
        "allowed_model_ids": (),
        "exact_base": HEAD,
        "branch": BRANCH,
        "allowed_paths": (),
        "forbidden_operations": (
            "source_write",
            "main_merge",
            "baseline_promotion",
            "production",
            "shared_db_mutation",
            "arbitrary_shell",
        ),
        "approval_reference": "AUTH://AUTONOMOUS_EXECUTION_CHANNEL_BINDING_V1",
    }
    if write:
        data.update(
            {
                "granted_scope": "BOUNDED_SOURCE_WRITE",
                "write_authority": "BOUNDED_SOURCE_WRITE",
                "allowed_paths": ("orchestrator/src/**",),
            }
        )
    return ExecutionLeaseV1.model_validate(data)


def transport() -> RemoteExecutionTransportProjectionV1:
    return RemoteExecutionTransportProjectionV1(
        lifecycle="ADMITTED",
        health="HEALTHY",
        admitted_capabilities=REMOTE_CAPABILITY_IDS,
    )


def scope(
    active_lease: ExecutionLeaseV1,
    *,
    paths: tuple[str, ...] = (),
    operations: tuple[str, ...] = (),
) -> WorkspaceRemoteExecutionScopeV1:
    return WorkspaceRemoteExecutionScopeV1(
        scope_id="scope-autonomous-channel-binding-v1",
        lease_id=active_lease.lease_id,
        allowed_path_patterns=paths,
        allowed_bounded_operation_ids=operations,
    )


def request(
    capability: str = "mesh_hostname",
    *,
    paths: tuple[str, ...] = (),
    operation: str | None = None,
) -> AutonomousExecutionRequestV1:
    return AutonomousExecutionRequestV1(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        task_id="AUTONOMOUS-EXECUTION-CHANNEL-BINDING-V1",
        correlation_id="autonomous-execution-channel-binding-v1",
        branch=BRANCH,
        current_head=HEAD,
        agent_id="coordinator_agentic_v1",
        capability_id=capability,
        tool_id=REMOTE_TOOL_BY_CAPABILITY[capability],
        requested_relative_paths=paths,
        bounded_operation_id=operation,
    )


def test_exact_ten_capabilities_are_preserved() -> None:
    assert len(REMOTE_CAPABILITY_IDS) == 10
    assert set(REMOTE_CAPABILITY_IDS) == {
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
    }


def test_read_only_remote_binding_allows_exact_lease_route() -> None:
    active = lease()
    receipt = evaluate_autonomous_execution_binding_v1(
        request=request(),
        lease=active,
        scope=scope(active),
        transport=transport(),
    )
    assert receipt.decision == "ALLOW"
    assert receipt.blockers == ()
    assert receipt.provider_id == "palwakf-remote-mcp"
    assert receipt.authority_owner == "Workspace"
    assert receipt.execution_router == "Agentic"
    assert receipt.source_write_authorized is False
    assert receipt.arbitrary_shell_exposed is False
    assert receipt.manual_terminal_fallback is False


def test_raw_shell_and_manual_terminal_are_not_representable() -> None:
    base = request().model_dump()
    with pytest.raises(ValidationError):
        AutonomousExecutionRequestV1.model_validate({**base, "raw_shell": "whoami"})
    with pytest.raises(ValidationError):
        AutonomousExecutionRequestV1.model_validate(
            {**base, "manual_terminal_requested": True}
        )


def test_bounded_powershell_requires_workspace_operation_id() -> None:
    active = lease("bounded_powershell")
    denied = evaluate_autonomous_execution_binding_v1(
        request=request("bounded_powershell", operation="OPERATION-NOT-ADMITTED"),
        lease=active,
        scope=scope(active, operations=("GIT-READBACK",)),
        transport=transport(),
    )
    assert denied.decision == "DENY"
    assert "BOUNDED_OPERATION_NOT_IN_WORKSPACE_SCOPE" in denied.blockers

    allowed = evaluate_autonomous_execution_binding_v1(
        request=request("bounded_powershell", operation="GIT-READBACK"),
        lease=active,
        scope=scope(active, operations=("GIT-READBACK",)),
        transport=transport(),
    )
    assert allowed.decision == "ALLOW"


def test_temp_write_is_path_scoped_and_not_source_write() -> None:
    active = lease("temp_write")
    allowed = evaluate_autonomous_execution_binding_v1(
        request=request("temp_write", paths=("tmp/p2/probe.txt",)),
        lease=active,
        scope=scope(active, paths=("tmp/p2/**",)),
        transport=transport(),
    )
    assert allowed.decision == "ALLOW"
    assert allowed.action_class == "BOUNDED_TEMP_MUTATION"

    denied = evaluate_autonomous_execution_binding_v1(
        request=request("temp_write", paths=("backend/source.py",)),
        lease=active,
        scope=scope(active, paths=("tmp/p2/**",)),
        transport=transport(),
    )
    assert denied.decision == "DENY"
    assert "REMOTE_PATH_OUT_OF_WORKSPACE_SCOPE" in denied.blockers


def test_source_write_lease_is_rejected_by_p2_channel() -> None:
    active = lease(write=True)
    receipt = evaluate_autonomous_execution_binding_v1(
        request=request(),
        lease=active,
        scope=scope(active),
        transport=transport(),
    )
    assert receipt.decision == "DENY"
    assert "P2_SOURCE_WRITE_AUTHORITY_FORBIDDEN" in receipt.blockers
    assert "P2_LEASE_SCOPE_MUST_REMAIN_READ_ONLY_EXECUTION" in receipt.blockers


def test_wrong_tool_fails_closed() -> None:
    active = lease()
    bad_request = request().model_copy(
        update={"tool_id": "palwakf-remote-mcp.git_readback"}
    )
    receipt = evaluate_autonomous_execution_binding_v1(
        request=bad_request,
        lease=active,
        scope=scope(active),
        transport=transport(),
    )
    assert receipt.decision == "DENY"
    assert "REMOTE_TOOL_CAPABILITY_MISMATCH" in receipt.blockers
    assert "LEASE_REMOTE_TOOL_NOT_ALLOWED" in receipt.blockers


def test_evidence_envelope_cannot_record_authority_violation() -> None:
    with pytest.raises(ValidationError):
        AutonomousExecutionEvidenceEnvelopeV1(
            lease_id="lease-autonomous-channel-binding-v1",
            scope_id="scope-autonomous-channel-binding-v1",
            request_sha256="0" * 64,
            capability_id="mesh_hostname",
            tool_id="palwakf-remote-mcp.mesh_hostname",
            execution_status="PASS",
            audit_reference="audit://p2",
            runtime_evidence=("evidence://runtime",),
            authority_violations=1,
        )
