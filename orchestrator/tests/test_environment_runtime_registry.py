from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.environment_runtime_registry import (
    CertifiedRuntimeBaselineV1,
    EnvironmentRuntimeRegistryStore,
    RuntimeCertificationState,
    RuntimeFingerprintV1,
    RuntimeRevalidationReceiptV1,
    reconcile_runtime_environment,
    require_certified_l4_equivalent,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore

NOW = datetime(2026, 9, 16, 16, 30, tzinfo=UTC)
BASE_COMPONENTS = {
    "powershell": "5.1.26100.9278",
    "git": "2.51.2.windows.1",
    "ollama": "0.34.0",
    "hermes": "0.21.3",
    "hermes_source": "14efb460",
}


def baseline() -> CertifiedRuntimeBaselineV1:
    return CertifiedRuntimeBaselineV1(
        baseline_id="PALWAKF_L4_RUNTIME_BASELINE_V1",
        source_revision="drive-baseline-r1",
        authority_reference="DRIVE://L4/runtime-baseline",
        expected_device_id="FIRAS-PC",
        required_components=BASE_COMPONENTS,
        evidence=("L4_PROVIDER_BENCHMARK",),
    )


def fingerprint(**updates: str) -> RuntimeFingerprintV1:
    components = dict(BASE_COMPONENTS)
    components.update({key: value for key, value in updates.items() if key in components})
    return RuntimeFingerprintV1(
        fingerprint_id="runtime-1",
        device_id=updates.get("device_id", "FIRAS-PC"),
        os_build="26200",
        arch="AMD64",
        powershell_edition="Desktop",
        powershell_version=components["powershell"],
        components=components,
        captured_at=NOW,
        evidence=("fresh-local-readback",),
    )


def test_exact_runtime_is_certified() -> None:
    result = reconcile_runtime_environment(baseline(), fingerprint(), reconciled_at=NOW)
    assert result.status == RuntimeCertificationState.exact_certified
    assert result.certified_l4_equivalent is True
    assert result.mismatches == ()
    require_certified_l4_equivalent(result)


def test_component_drift_fails_closed_until_revalidated() -> None:
    current = fingerprint(ollama="0.34.1")
    result = reconcile_runtime_environment(baseline(), current, reconciled_at=NOW)
    assert result.status == RuntimeCertificationState.revalidation_required
    assert result.certified_l4_equivalent is False
    assert result.mismatches == ("ollama:expected=0.34.0:actual=0.34.1",)
    with pytest.raises(GovernanceError, match="RUNTIME_NOT_CERTIFIED_L4_EQUIVALENT"):
        require_certified_l4_equivalent(result)


def test_device_drift_is_explicit() -> None:
    result = reconcile_runtime_environment(
        baseline(), fingerprint(device_id="DESKTOP-S5A0JSB"), reconciled_at=NOW
    )
    assert result.status == RuntimeCertificationState.revalidation_required
    assert result.mismatches[0].startswith("device_id:expected=FIRAS-PC")


def test_sovereign_revalidation_receipt_can_mark_drift_equivalent() -> None:
    current = fingerprint(ollama="0.34.1")
    receipt = RuntimeRevalidationReceiptV1(
        receipt_id="revalidation-1",
        source_revision="drive-revalidation-r2",
        authority_reference="DRIVE://L4/runtime-revalidation",
        baseline_id=baseline().baseline_id,
        current_fingerprint_sha256=current.fingerprint_sha256,
        evidence=("bounded-runtime-revalidation",),
    )
    result = reconcile_runtime_environment(baseline(), current, receipt=receipt, reconciled_at=NOW)
    assert result.status == RuntimeCertificationState.revalidated_equivalent
    assert result.certified_l4_equivalent is True
    assert result.revalidation_receipt_id == "revalidation-1"


def test_revalidation_receipt_must_bind_current_fingerprint() -> None:
    current = fingerprint(ollama="0.34.1")
    receipt = RuntimeRevalidationReceiptV1(
        receipt_id="revalidation-bad",
        source_revision="drive-revalidation-r2",
        authority_reference="DRIVE://L4/runtime-revalidation",
        baseline_id=baseline().baseline_id,
        current_fingerprint_sha256="a" * 64,
        evidence=("bounded-runtime-revalidation",),
    )
    with pytest.raises(GovernanceError, match="RUNTIME_REVALIDATION_FINGERPRINT_MISMATCH"):
        reconcile_runtime_environment(baseline(), current, receipt=receipt)


def test_registry_persists_and_restores_current_snapshot() -> None:
    state = MemoryStateStore()
    store = EnvironmentRuntimeRegistryStore(state, now=lambda: NOW)
    saved = store.import_snapshot(
        source_revision="drive-runtime-r3",
        authority_reference="DRIVE://PREL5-014",
        baseline=baseline(),
        current=fingerprint(ollama="0.34.1"),
    )
    restarted = EnvironmentRuntimeRegistryStore(state, now=lambda: NOW)
    restored = restarted.current()
    assert restored.registry_sha256 == saved.registry_sha256
    assert restored.reconciliation.status == RuntimeCertificationState.revalidation_required
    assert restored.canonical_promotion_allowed is False
    assert restored.source_authority == "WORKSPACE_DRIVE_SOVEREIGN"


def test_same_source_revision_with_changed_runtime_fails_closed() -> None:
    state = MemoryStateStore()
    store = EnvironmentRuntimeRegistryStore(state, now=lambda: NOW)
    store.import_snapshot(
        source_revision="drive-runtime-r3",
        authority_reference="DRIVE://PREL5-014",
        baseline=baseline(),
        current=fingerprint(ollama="0.34.1"),
    )
    with pytest.raises(GovernanceError, match="ENVIRONMENT_RUNTIME_SOURCE_REVISION_CONFLICT"):
        store.import_snapshot(
            source_revision="drive-runtime-r3",
            authority_reference="DRIVE://PREL5-014",
            baseline=baseline(),
            current=fingerprint(ollama="0.34.2"),
        )
