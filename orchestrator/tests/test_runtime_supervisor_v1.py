from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.environment_runtime_registry import (
    CertifiedRuntimeBaselineV1,
    RuntimeFingerprintV1,
    build_environment_runtime_snapshot,
    project_runtime_components,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.runtime_supervisor_v1 import (
    ProviderRuntimeProjectionV1,
    RuntimeComponentLifecycle,
    RuntimeComponentObservationV1,
    RuntimeComponentSpecV1,
    RuntimeSupervisorAction,
    RuntimeSupervisorActionRequestV1,
    RuntimeSupervisorV1,
    transition_runtime_component,
)

NOW = datetime(2026, 9, 27, 18, 50, tzinfo=UTC)


def runtime_snapshot():
    baseline = CertifiedRuntimeBaselineV1(
        baseline_id="runtime-v1",
        source_revision="drive-runtime-v1",
        authority_reference="DRIVE://runtime/v1",
        required_components={
            "meshcentral": "1.0",
            "meshagent": "1.0",
            "palwakf_remote_mcp": "1.0",
            "secure_tunnel": "1.0",
        },
        evidence=("runtime-baseline",),
    )
    current = RuntimeFingerprintV1(
        fingerprint_id="runtime-current",
        device_id="DESKTOP-S5A0JSB",
        os_build="26100",
        arch="AMD64",
        powershell_edition="Desktop",
        powershell_version="5.1",
        components=dict(baseline.required_components),
        captured_at=NOW,
        evidence=("runtime-readback",),
    )
    return build_environment_runtime_snapshot(
        source_revision="drive-runtime-v1",
        authority_reference="DRIVE://runtime/v1",
        baseline=baseline,
        current=current,
        imported_at=NOW,
    )


def specs() -> tuple[RuntimeComponentSpecV1, ...]:
    return (
        RuntimeComponentSpecV1(
            component_id="meshcentral",
            critical=True,
            expected_version="1.0",
            allowed_actions=(
                RuntimeSupervisorAction.probe,
                RuntimeSupervisorAction.start,
                RuntimeSupervisorAction.stop,
            ),
            bounded_command_ids={
                RuntimeSupervisorAction.probe: "runtime.meshcentral.probe",
                RuntimeSupervisorAction.start: "runtime.meshcentral.start",
                RuntimeSupervisorAction.stop: "runtime.meshcentral.stop",
            },
        ),
        RuntimeComponentSpecV1(
            component_id="meshagent",
            dependencies=("meshcentral",),
            critical=True,
            expected_version="1.0",
            allowed_actions=(
                RuntimeSupervisorAction.probe,
                RuntimeSupervisorAction.start,
                RuntimeSupervisorAction.stop,
                RuntimeSupervisorAction.restart,
                RuntimeSupervisorAction.recover,
                RuntimeSupervisorAction.resume,
            ),
            bounded_command_ids={
                RuntimeSupervisorAction.probe: "runtime.meshagent.probe",
                RuntimeSupervisorAction.start: "runtime.meshagent.start",
                RuntimeSupervisorAction.stop: "runtime.meshagent.stop",
                RuntimeSupervisorAction.restart: "runtime.meshagent.restart",
                RuntimeSupervisorAction.recover: "runtime.meshagent.recover",
                RuntimeSupervisorAction.resume: "runtime.meshagent.resume",
            },
        ),
    )


def observation(
    component_id: str,
    state: RuntimeComponentLifecycle,
    *,
    version: str = "1.0",
) -> RuntimeComponentObservationV1:
    return RuntimeComponentObservationV1(
        component_id=component_id,
        lifecycle_state=state,
        version=version,
        process_present=state == RuntimeComponentLifecycle.healthy,
        observed_at=NOW,
        evidence=(f"{component_id}:readback",),
    )


def test_environment_registry_projects_versioned_runtime_components() -> None:
    projected = project_runtime_components(runtime_snapshot())
    by_id = {item.component_id: item for item in projected}

    assert by_id["meshcentral"].version == "1.0"
    assert by_id["meshcentral"].source_revision == "drive-runtime-v1"
    assert len(by_id["meshcentral"].runtime_fingerprint_sha256) == 64


def test_dependency_order_is_topological_and_deterministic() -> None:
    supervisor = RuntimeSupervisorV1(specs())
    assert supervisor.dependency_order == ("meshcentral", "meshagent")


def test_missing_critical_observation_fails_runtime_health_closed() -> None:
    supervisor = RuntimeSupervisorV1(specs())
    result = supervisor.reconcile(
        runtime_snapshot(),
        [observation("meshcentral", RuntimeComponentLifecycle.healthy)],
        observed_at=NOW,
    )

    assert result.overall_health == "UNAVAILABLE"
    by_id = {item.component_id: item for item in result.components}
    assert by_id["meshagent"].lifecycle_state == RuntimeComponentLifecycle.unavailable


def test_version_drift_demotes_healthy_observation_to_degraded() -> None:
    supervisor = RuntimeSupervisorV1(specs())
    result = supervisor.reconcile(
        runtime_snapshot(),
        [
            observation("meshcentral", RuntimeComponentLifecycle.healthy),
            observation(
                "meshagent",
                RuntimeComponentLifecycle.healthy,
                version="2.0",
            ),
        ],
        observed_at=NOW,
    )

    by_id = {item.component_id: item for item in result.components}
    assert by_id["meshagent"].lifecycle_state == RuntimeComponentLifecycle.degraded
    assert result.overall_health == "DEGRADED"


def test_mutating_action_requires_explicit_authorization() -> None:
    supervisor = RuntimeSupervisorV1(specs())
    request = RuntimeSupervisorActionRequestV1(
        request_id="runtime-action-1",
        correlation_id="corr-1",
        component_id="meshagent",
        action=RuntimeSupervisorAction.restart,
        authority_reference="AUTHORITY://runtime/restart",
    )

    plan = supervisor.plan_action(
        request,
        [
            observation("meshcentral", RuntimeComponentLifecycle.healthy),
            observation("meshagent", RuntimeComponentLifecycle.healthy),
        ],
    )

    assert plan.allowed is False
    assert "EXPLICIT_AUTHORIZATION_REQUIRED" in plan.blockers
    assert plan.execution_channel == "PALWAKF_SECURE_MCP_BOUNDED_POWERSHELL"


def test_authorized_restart_requires_healthy_dependency_and_exact_binding() -> None:
    supervisor = RuntimeSupervisorV1(specs())
    request = RuntimeSupervisorActionRequestV1(
        request_id="runtime-action-2",
        correlation_id="corr-2",
        component_id="meshagent",
        action=RuntimeSupervisorAction.restart,
        authority_reference="AUTHORITY://runtime/restart",
        explicit_authorization=True,
    )

    plan = supervisor.plan_action(
        request,
        [
            observation("meshcentral", RuntimeComponentLifecycle.healthy),
            observation("meshagent", RuntimeComponentLifecycle.degraded),
        ],
    )

    assert plan.allowed is True
    assert plan.bounded_command_id == "runtime.meshagent.restart"
    assert plan.dependency_order == ("meshcentral", "meshagent")
    assert plan.no_authority_expansion is True


def test_stop_is_blocked_while_dependent_component_is_active() -> None:
    supervisor = RuntimeSupervisorV1(specs())
    request = RuntimeSupervisorActionRequestV1(
        request_id="runtime-action-3",
        correlation_id="corr-3",
        component_id="meshcentral",
        action=RuntimeSupervisorAction.stop,
        authority_reference="AUTHORITY://runtime/stop",
        explicit_authorization=True,
    )

    plan = supervisor.plan_action(
        request,
        [
            observation("meshcentral", RuntimeComponentLifecycle.healthy),
            observation("meshagent", RuntimeComponentLifecycle.healthy),
        ],
    )

    assert plan.allowed is False
    assert "DEPENDENT_ACTIVE:meshagent" in plan.blockers


def test_quarantined_component_requires_explicit_readmission_for_transition() -> None:
    with pytest.raises(
        GovernanceError,
        match="RUNTIME_COMPONENT_READMISSION_AUTHORIZATION_REQUIRED",
    ):
        transition_runtime_component(
            RuntimeComponentLifecycle.quarantined,
            RuntimeComponentLifecycle.probed,
        )

    assert (
        transition_runtime_component(
            RuntimeComponentLifecycle.quarantined,
            RuntimeComponentLifecycle.probed,
            readmission_authorized=True,
        )
        == RuntimeComponentLifecycle.probed
    )


def test_provider_projection_accepts_agentic_admitted_healthy_shape() -> None:
    projection = ProviderRuntimeProjectionV1(
        project_id="PALWAKF_AGENTIC_AI_SYSTEM",
        task_id="RUNTIME-PROVIDER-V1",
        correlation_id="corr-provider",
        created_at=NOW,
        provenance=("agentic-provider-runtime",),
        provider_id="opencode",
        lifecycle="ADMITTED",
        health="HEALTHY",
        capabilities=("engineering.analysis",),
        route_eligible=True,
    )

    assert projection.producer == "Agentic"
    assert projection.authority_scope == "NO_SOVEREIGN_AUTHORITY"


def test_provider_projection_rejects_unadmitted_route_eligibility() -> None:
    with pytest.raises(
        ValidationError,
        match="ROUTE_ELIGIBLE_PROVIDER_MUST_BE_ADMITTED_AND_HEALTHY",
    ):
        ProviderRuntimeProjectionV1(
            project_id="PALWAKF_AGENTIC_AI_SYSTEM",
            task_id="RUNTIME-PROVIDER-V1",
            correlation_id="corr-provider",
            created_at=NOW,
            provenance=("agentic-provider-runtime",),
            provider_id="opencode",
            lifecycle="PROBED",
            health="HEALTHY",
            capabilities=("engineering.analysis",),
            route_eligible=True,
        )
