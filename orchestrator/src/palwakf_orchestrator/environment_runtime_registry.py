from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

REGISTRY_STATE_KEY = "pre_l5_environment_runtime_registry_v1"


class RuntimeCertificationState(StrEnum):
    exact_certified = "EXACT_CERTIFIED"
    revalidation_required = "DRIFTED_REVALIDATION_REQUIRED"
    revalidated_equivalent = "REVALIDATED_EQUIVALENT"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class RuntimeFingerprintV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fingerprint_id: str = Field(min_length=1, max_length=200)
    device_id: str = Field(min_length=1, max_length=200)
    os_build: str = Field(min_length=1, max_length=100)
    arch: str = Field(min_length=1, max_length=100)
    powershell_edition: str = Field(min_length=1, max_length=100)
    powershell_version: str = Field(min_length=1, max_length=100)
    components: dict[str, str] = Field(min_length=1)
    captured_at: datetime
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_nonempty(self) -> Self:
        if any(not key.strip() or not value.strip() for key, value in self.components.items()):
            raise ValueError("RUNTIME_COMPONENT_IDENTITY_MUST_BE_NONEMPTY")
        if any(not item.strip() for item in self.evidence):
            raise ValueError("RUNTIME_FINGERPRINT_EVIDENCE_MUST_BE_NONEMPTY")
        return self

    @property
    def fingerprint_sha256(self) -> str:
        payload = self.model_dump(mode="json", exclude={"captured_at", "evidence"})
        return _sha256(payload)


class CertifiedRuntimeBaselineV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_id: str = Field(min_length=1, max_length=200)
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    expected_device_id: str | None = Field(default=None, max_length=200)
    required_components: dict[str, str] = Field(min_length=1)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_baseline(self) -> Self:
        if any(
            not key.strip() or not value.strip() for key, value in self.required_components.items()
        ):
            raise ValueError("RUNTIME_BASELINE_COMPONENT_MUST_BE_NONEMPTY")
        if any(not item.strip() for item in self.evidence):
            raise ValueError("RUNTIME_BASELINE_EVIDENCE_MUST_BE_NONEMPTY")
        return self


class RuntimeRevalidationReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1, max_length=200)
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    baseline_id: str = Field(min_length=1, max_length=200)
    current_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    equivalent: Literal[True] = True
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)


class RuntimeReconciliationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_id: str
    current_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: RuntimeCertificationState
    mismatches: tuple[str, ...]
    revalidation_receipt_id: str | None = None
    certified_l4_equivalent: bool
    reconciled_at: datetime


def reconcile_runtime_environment(
    baseline: CertifiedRuntimeBaselineV1,
    current: RuntimeFingerprintV1,
    *,
    receipt: RuntimeRevalidationReceiptV1 | None = None,
    reconciled_at: datetime | None = None,
) -> RuntimeReconciliationV1:
    mismatches: list[str] = []
    if baseline.expected_device_id and current.device_id != baseline.expected_device_id:
        mismatches.append(
            f"device_id:expected={baseline.expected_device_id}:actual={current.device_id}"
        )
    for component, expected in sorted(baseline.required_components.items()):
        actual = current.components.get(component)
        if actual != expected:
            mismatches.append(f"{component}:expected={expected}:actual={actual or '<missing>'}")

    if not mismatches:
        status = RuntimeCertificationState.exact_certified
        equivalent = True
        receipt_id = None
    elif receipt is None:
        status = RuntimeCertificationState.revalidation_required
        equivalent = False
        receipt_id = None
    else:
        if receipt.baseline_id != baseline.baseline_id:
            raise GovernanceError("RUNTIME_REVALIDATION_BASELINE_MISMATCH")
        if receipt.current_fingerprint_sha256 != current.fingerprint_sha256:
            raise GovernanceError("RUNTIME_REVALIDATION_FINGERPRINT_MISMATCH")
        if any(not item.strip() for item in receipt.evidence):
            raise GovernanceError("RUNTIME_REVALIDATION_EVIDENCE_REQUIRED")
        status = RuntimeCertificationState.revalidated_equivalent
        equivalent = True
        receipt_id = receipt.receipt_id

    return RuntimeReconciliationV1(
        baseline_id=baseline.baseline_id,
        current_fingerprint_sha256=current.fingerprint_sha256,
        status=status,
        mismatches=tuple(mismatches),
        revalidation_receipt_id=receipt_id,
        certified_l4_equivalent=equivalent,
        reconciled_at=reconciled_at or datetime.now(UTC),
    )


def require_certified_l4_equivalent(reconciliation: RuntimeReconciliationV1) -> None:
    if not reconciliation.certified_l4_equivalent:
        raise GovernanceError("RUNTIME_NOT_CERTIFIED_L4_EQUIVALENT")


class EnvironmentRuntimeRegistrySnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_ENVIRONMENT_RUNTIME_REGISTRY_V1"] = (
        "PALWAKF_ENVIRONMENT_RUNTIME_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    baseline: CertifiedRuntimeBaselineV1
    current: RuntimeFingerprintV1
    reconciliation: RuntimeReconciliationV1
    imported_at: datetime
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False


def build_environment_runtime_snapshot(
    *,
    source_revision: str,
    authority_reference: str,
    baseline: CertifiedRuntimeBaselineV1,
    current: RuntimeFingerprintV1,
    receipt: RuntimeRevalidationReceiptV1 | None = None,
    imported_at: datetime | None = None,
) -> EnvironmentRuntimeRegistrySnapshotV1:
    reconciliation = reconcile_runtime_environment(baseline, current, receipt=receipt)
    payload = {
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "baseline": baseline.model_dump(mode="json"),
        "current": current.model_dump(mode="json"),
        "reconciliation": reconciliation.model_dump(mode="json"),
    }
    return EnvironmentRuntimeRegistrySnapshotV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        baseline=baseline,
        current=current,
        reconciliation=reconciliation,
        imported_at=imported_at or datetime.now(UTC),
        registry_sha256=_sha256(payload),
    )


class EnvironmentRuntimeRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def history(self) -> tuple[EnvironmentRuntimeRegistrySnapshotV1, ...]:
        state = self._state_store.load()
        raw = state.get(REGISTRY_STATE_KEY, {})
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else []
        return tuple(
            EnvironmentRuntimeRegistrySnapshotV1.model_validate(item) for item in snapshots
        )

    def current(self) -> EnvironmentRuntimeRegistrySnapshotV1:
        history = self.history()
        if not history:
            raise GovernanceError("ENVIRONMENT_RUNTIME_REGISTRY_NOT_IMPORTED")
        return history[-1]

    def import_snapshot(
        self,
        *,
        source_revision: str,
        authority_reference: str,
        baseline: CertifiedRuntimeBaselineV1,
        current: RuntimeFingerprintV1,
        receipt: RuntimeRevalidationReceiptV1 | None = None,
    ) -> EnvironmentRuntimeRegistrySnapshotV1:
        snapshot = build_environment_runtime_snapshot(
            source_revision=source_revision,
            authority_reference=authority_reference,
            baseline=baseline,
            current=current,
            receipt=receipt,
            imported_at=self._now(),
        )
        history = list(self.history())
        for existing in history:
            if existing.source_revision != source_revision:
                continue
            if existing.registry_sha256 != snapshot.registry_sha256:
                raise GovernanceError("ENVIRONMENT_RUNTIME_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(snapshot)
        state = self._state_store.load()
        state[REGISTRY_STATE_KEY] = {
            "registry_version": "PALWAKF_ENVIRONMENT_RUNTIME_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_PROJECTION_ONLY",
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return snapshot
