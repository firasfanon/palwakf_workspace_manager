from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.runtime_supervisor_v1 import (
    ProviderRuntimeProjectionV1,
    RuntimeComponentLifecycle,
    RuntimeComponentObservationV1,
)

_PROVIDER_COMPONENT: Final[dict[str, str]] = {
    "hermes-headless": "hermes_headless",
    "opencode": "opencode",
    "playwright": "playwright",
}

_HERMES_HEADLESS_ADMITTED_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {"agent.headless_api", "provider.health"}
)


class RuntimeProviderBindingReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    component_id: str
    lifecycle: str
    health: str
    admitted_capabilities: tuple[str, ...]
    route_eligible: bool
    bounded_write_admitted: bool
    observation: RuntimeComponentObservationV1
    binding_mode: Literal["AGENTIC_PROVIDER_DESCRIPTOR_TO_WORKSPACE_RUNTIME"] = (
        "AGENTIC_PROVIDER_DESCRIPTOR_TO_WORKSPACE_RUNTIME"
    )
    no_authority_expansion: Literal[True] = True


def _runtime_state(projection: ProviderRuntimeProjectionV1) -> RuntimeComponentLifecycle:
    if projection.health == "QUARANTINED":
        return RuntimeComponentLifecycle.quarantined
    if projection.health == "UNAVAILABLE":
        return RuntimeComponentLifecycle.unavailable
    if projection.health == "DEGRADED":
        return RuntimeComponentLifecycle.degraded
    if projection.lifecycle == "DISCOVERED":
        return RuntimeComponentLifecycle.discovered
    if projection.lifecycle == "PROBED":
        return RuntimeComponentLifecycle.probed
    return RuntimeComponentLifecycle.healthy


def bind_provider_projection_v1(
    projection: ProviderRuntimeProjectionV1,
) -> RuntimeProviderBindingReceiptV1:
    component_id = _PROVIDER_COMPONENT.get(projection.provider_id)
    if component_id is None:
        raise GovernanceError(f"UNSUPPORTED_RUNTIME_PROVIDER_BINDING:{projection.provider_id}")

    admitted = frozenset(projection.admitted_capabilities)

    if projection.provider_id == "hermes-headless":
        if projection.lifecycle != "ADMITTED" or projection.health != "HEALTHY":
            raise GovernanceError("HERMES_HEADLESS_MUST_BE_ADMITTED_AND_HEALTHY")
        if admitted != _HERMES_HEADLESS_ADMITTED_CAPABILITIES:
            raise GovernanceError("HERMES_HEADLESS_ADMISSION_SCOPE_MISMATCH")
        if projection.bounded_write_admitted:
            raise GovernanceError("HERMES_BOUNDED_WRITE_FORBIDDEN_IN_CURRENT_SCOPE")
        if not projection.route_eligible:
            raise GovernanceError("HERMES_HEADLESS_ADMISSION_MUST_BE_ROUTE_ELIGIBLE")
    else:
        if projection.lifecycle != "PROBED" or projection.health != "HEALTHY":
            raise GovernanceError(
                f"{projection.provider_id.upper()}_BINDING_MUST_REMAIN_PROBED_HEALTHY"
            )
        if projection.admitted_capabilities:
            raise GovernanceError(
                f"{projection.provider_id.upper()}_MUST_NOT_HAVE_ADMITTED_CAPABILITIES"
            )
        if projection.route_eligible:
            raise GovernanceError(
                f"{projection.provider_id.upper()}_MUST_NOT_BE_ROUTE_ELIGIBLE_YET"
            )
        if projection.bounded_write_admitted:
            raise GovernanceError(
                f"{projection.provider_id.upper()}_BOUNDED_WRITE_NOT_ADMITTED"
            )

    observation = RuntimeComponentObservationV1(
        component_id=component_id,
        lifecycle_state=_runtime_state(projection),
        version=projection.version,
        observed_at=projection.created_at,
        evidence=tuple(
            dict.fromkeys(
                (
                    *projection.provenance,
                    *projection.admission_evidence,
                    f"provider-binding:{projection.provider_id}",
                )
            )
        ),
    )
    return RuntimeProviderBindingReceiptV1(
        provider_id=projection.provider_id,
        component_id=component_id,
        lifecycle=projection.lifecycle,
        health=projection.health,
        admitted_capabilities=projection.admitted_capabilities,
        route_eligible=projection.route_eligible,
        bounded_write_admitted=projection.bounded_write_admitted,
        observation=observation,
    )


def validate_runtime_provider_binding_set_v1(
    projections: tuple[ProviderRuntimeProjectionV1, ...],
) -> tuple[RuntimeProviderBindingReceiptV1, ...]:
    by_id = {item.provider_id: item for item in projections}
    if len(by_id) != len(projections):
        raise GovernanceError("DUPLICATE_PROVIDER_RUNTIME_PROJECTION")
    if set(by_id) != set(_PROVIDER_COMPONENT):
        missing = sorted(set(_PROVIDER_COMPONENT) - set(by_id))
        extra = sorted(set(by_id) - set(_PROVIDER_COMPONENT))
        raise GovernanceError(f"RUNTIME_PROVIDER_BINDING_SET_MISMATCH:{missing}:{extra}")
    return tuple(bind_provider_projection_v1(by_id[key]) for key in sorted(by_id))
