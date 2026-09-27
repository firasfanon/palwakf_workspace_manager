from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.runtime_provider_binding_v1 import (
    bind_provider_projection_v1,
    validate_runtime_provider_binding_set_v1,
)
from palwakf_orchestrator.runtime_supervisor_v1 import (
    ProviderRuntimeProjectionV1,
    RuntimeComponentLifecycle,
)

NOW = datetime(2026, 9, 27, 20, 0, tzinfo=UTC)


def projection(
    provider_id: str,
    *,
    lifecycle: str = "PROBED",
    health: str = "HEALTHY",
    admitted: tuple[str, ...] = (),
    route_eligible: bool = False,
    bounded_write: bool = False,
) -> ProviderRuntimeProjectionV1:
    kinds = {
        "hermes-headless": "GENERAL_AGENT",
        "opencode": "ENGINEERING",
        "playwright": "BROWSER_UAT",
    }
    rw = {
        "hermes-headless": "BOUNDED_WRITE_CAPABLE",
        "opencode": "BOUNDED_WRITE_CAPABLE",
        "playwright": "BROWSER_UAT",
    }
    caps = {
        "hermes-headless": (
            "agent.headless_api",
            "agent.read_only_execution",
            "engineering.analysis",
            "provider.health",
        ),
        "opencode": (
            "engineering.analysis",
            "engineering.edit",
            "engineering.test",
            "provider.health",
        ),
        "playwright": (
            "browser.uat",
            "browser.navigation",
            "browser.screenshot",
            "provider.health",
        ),
    }
    return ProviderRuntimeProjectionV1(
        project_id="PALWAKF_AGENTIC_AI_SYSTEM",
        task_id="RUNTIME-BINDING-V1",
        correlation_id=f"corr-{provider_id}",
        created_at=NOW,
        provenance=(f"{provider_id}:runtime-evidence",),
        provider_id=provider_id,
        provider_kind=kinds[provider_id],
        version="test-version",
        endpoint=None,
        lifecycle=lifecycle,
        health=health,
        capabilities=caps[provider_id],
        admitted_capabilities=admitted,
        read_write_class=rw[provider_id],
        bounded_write_admitted=bounded_write,
        admission_evidence=("hermes-admission",) if provider_id == "hermes-headless" else (),
        route_eligible=route_eligible,
    )


def test_hermes_headless_binding_maps_to_workspace_runtime_component() -> None:
    receipt = bind_provider_projection_v1(
        projection(
            "hermes-headless",
            lifecycle="ADMITTED",
            admitted=("agent.headless_api", "provider.health"),
            route_eligible=True,
        )
    )

    assert receipt.component_id == "hermes_headless"
    assert receipt.observation.lifecycle_state == RuntimeComponentLifecycle.healthy
    assert receipt.bounded_write_admitted is False


def test_hermes_broad_or_write_admission_fails_closed() -> None:
    with pytest.raises(GovernanceError, match="ADMISSION_SCOPE_MISMATCH"):
        bind_provider_projection_v1(
            projection(
                "hermes-headless",
                lifecycle="ADMITTED",
                admitted=("agent.headless_api", "engineering.analysis", "provider.health"),
                route_eligible=True,
            )
        )

    with pytest.raises(GovernanceError, match="HERMES_BOUNDED_WRITE_FORBIDDEN"):
        bind_provider_projection_v1(
            projection(
                "hermes-headless",
                lifecycle="ADMITTED",
                admitted=("agent.headless_api", "provider.health"),
                route_eligible=True,
                bounded_write=True,
            )
        )


def test_opencode_and_playwright_remain_probe_bindings_only() -> None:
    opencode = bind_provider_projection_v1(projection("opencode"))
    playwright = bind_provider_projection_v1(projection("playwright"))

    assert opencode.observation.lifecycle_state == RuntimeComponentLifecycle.probed
    assert playwright.observation.lifecycle_state == RuntimeComponentLifecycle.probed
    assert opencode.route_eligible is False
    assert playwright.route_eligible is False


def test_current_workstream_binding_set_is_exact() -> None:
    receipts = validate_runtime_provider_binding_set_v1(
        (
            projection(
                "hermes-headless",
                lifecycle="ADMITTED",
                admitted=("agent.headless_api", "provider.health"),
                route_eligible=True,
            ),
            projection("opencode"),
            projection("playwright"),
        )
    )

    assert {item.provider_id for item in receipts} == {
        "hermes-headless",
        "opencode",
        "playwright",
    }


def test_missing_provider_binding_fails_closed() -> None:
    with pytest.raises(GovernanceError, match="RUNTIME_PROVIDER_BINDING_SET_MISMATCH"):
        validate_runtime_provider_binding_set_v1(
            (
                projection(
                    "hermes-headless",
                    lifecycle="ADMITTED",
                    admitted=("agent.headless_api", "provider.health"),
                    route_eligible=True,
                ),
                projection("opencode"),
            )
        )
