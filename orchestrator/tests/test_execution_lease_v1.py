from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_lease_v1 import (
    ExecutionLeaseRouteClaimV1,
    ExecutionLeaseV1,
    LeaseRevocationState,
    validate_execution_lease_claim_v1,
)

NOW = datetime(2026, 9, 27, 21, 0, tzinfo=UTC)


def lease(**updates) -> ExecutionLeaseV1:
    data = {
        "project_id": "PALWAKF_AGENTIC_AI_SYSTEM",
        "task_id": "MODEL-TOOL-AGENT-ROUTING-V1",
        "correlation_id": "routing-v1",
        "created_at": NOW,
        "provenance": ("handoff:MODEL_TOOL_AGENT_ROUTING_AND_EXECUTION_BINDING",),
        "lease_id": "lease-routing-v1",
        "granted_scope": "READ_ONLY_EXECUTION",
        "expires_at": NOW + timedelta(hours=1),
        "allowed_capabilities": (
            "agent.headless_api",
            "model.inference",
            "model.health",
            "provider.health",
        ),
        "allowed_tools": (),
        "write_authority": "NONE",
        "allowed_provider_ids": ("hermes-headless", "ollama"),
        "allowed_agent_ids": ("coordinator_agentic_v1",),
        "allowed_model_ids": ("qwen2.5:3b",),
        "exact_base": "40d28da2953b1aceed466388d217d6b88533becb",
        "branch": "task/AGENTIC-AUTONOMOUS-LOCAL-AI-MEGA-BATCH-V1",
        "allowed_paths": (),
        "forbidden_operations": (
            "production",
            "shared_db_mutation",
            "git_push",
        ),
        "approval_reference": "WORKSPACE://routing-v1",
    }
    data.update(updates)
    return ExecutionLeaseV1.model_validate(data)


def test_read_only_lease_accepts_exact_read_only_route_claim() -> None:
    item = lease()
    claim = ExecutionLeaseRouteClaimV1(
        project_id=item.project_id,
        task_id=item.task_id,
        correlation_id=item.correlation_id,
        agent_id="coordinator_agentic_v1",
        provider_ids=("hermes-headless", "ollama"),
        model_id="qwen2.5:3b",
        capability_ids=("agent.headless_api", "model.inference"),
    )

    validate_execution_lease_claim_v1(item, claim, now=NOW)


def test_read_only_lease_cannot_grant_write_authority_or_paths() -> None:
    with pytest.raises(ValidationError, match="READ_ONLY_LEASE_CANNOT_GRANT_WRITE"):
        lease(
            write_authority="BOUNDED_SOURCE_WRITE",
            allowed_paths=("backend/src/**",),
        )


def test_source_write_claim_is_rejected_by_read_only_lease() -> None:
    item = lease()
    claim = ExecutionLeaseRouteClaimV1(
        project_id=item.project_id,
        task_id=item.task_id,
        correlation_id=item.correlation_id,
        agent_id="coordinator_agentic_v1",
        provider_ids=("hermes-headless",),
        capability_ids=("agent.headless_api",),
        mutation_class="SOURCE_WRITE",
    )

    with pytest.raises(GovernanceError, match="LEASE_WRITE_AUTHORITY_REQUIRED"):
        validate_execution_lease_claim_v1(item, claim, now=NOW)


def test_revoked_or_expired_lease_fails_closed() -> None:
    revoked = lease(revocation_state=LeaseRevocationState.revoked)
    with pytest.raises(GovernanceError, match="EXECUTION_LEASE_REVOKED"):
        revoked.assert_active(now=NOW)

    expired = lease(
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(GovernanceError, match="EXECUTION_LEASE_EXPIRED"):
        expired.assert_active(now=NOW)


def test_unlisted_provider_model_tool_or_capability_fails_closed() -> None:
    item = lease(allowed_tools=("safe-tool",))
    base = {
        "project_id": item.project_id,
        "task_id": item.task_id,
        "correlation_id": item.correlation_id,
        "agent_id": "coordinator_agentic_v1",
        "provider_ids": ("hermes-headless",),
        "capability_ids": ("agent.headless_api",),
    }

    with pytest.raises(GovernanceError, match="LEASE_PROVIDER_NOT_ALLOWED"):
        validate_execution_lease_claim_v1(
            item,
            ExecutionLeaseRouteClaimV1.model_validate(
                {**base, "provider_ids": ("opencode",)}
            ),
            now=NOW,
        )

    with pytest.raises(GovernanceError, match="LEASE_MODEL_NOT_ALLOWED"):
        validate_execution_lease_claim_v1(
            item,
            ExecutionLeaseRouteClaimV1.model_validate(
                {**base, "model_id": "other-model"}
            ),
            now=NOW,
        )

    with pytest.raises(GovernanceError, match="LEASE_TOOL_NOT_ALLOWED"):
        validate_execution_lease_claim_v1(
            item,
            ExecutionLeaseRouteClaimV1.model_validate(
                {**base, "tool_ids": ("other-tool",)}
            ),
            now=NOW,
        )

    with pytest.raises(GovernanceError, match="LEASE_CAPABILITY_NOT_ALLOWED"):
        validate_execution_lease_claim_v1(
            item,
            ExecutionLeaseRouteClaimV1.model_validate(
                {**base, "capability_ids": ("browser.uat",)}
            ),
            now=NOW,
        )
