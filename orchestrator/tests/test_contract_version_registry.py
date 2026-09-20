from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.contract_version_registry import (
    REGISTRY_STATE_KEY,
    CompatibilityClass,
    ConsumedContractBindingV1,
    ContractLifecycle,
    ContractVersionRecordV1,
    ContractVersionRegistryStore,
    build_contract_version_registry,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.typed_dependency_graph import (
    DependencyEdgeV1,
    DependencyKind,
    ProjectDependencyDeclarationV1,
    build_typed_dependency_graph,
)

REV = "drive-revision-016"
AUTH = "PREL5-016-AUTHORITY"
NOW = datetime(2026, 9, 16, 20, 0, tzinfo=UTC)
PRODUCER = "PROJECT_A"
CONSUMER = "PROJECT_B"
CONTRACT = "TEST_CONTRACT"


def _graph(version: str = "V1"):
    edge = DependencyEdgeV1(
        edge_id="edge-contract",
        producer_project_id=PRODUCER,
        consumer_project_id=CONSUMER,
        kind=DependencyKind.api,
        contract_id=CONTRACT,
        version=version,
        authority_reference=AUTH,
        source_revision=REV,
        evidence=("graph-evidence",),
    )
    declarations = (
        ProjectDependencyDeclarationV1(
            project_id=PRODUCER,
            produced_edge_ids=(edge.edge_id,),
        ),
        ProjectDependencyDeclarationV1(
            project_id=CONSUMER,
            consumed_edge_ids=(edge.edge_id,),
        ),
    )
    return build_typed_dependency_graph(
        source_revision=REV,
        authority_reference=AUTH,
        project_ids=(PRODUCER, CONSUMER),
        declarations=declarations,
        edges=(edge,),
        imported_at=NOW,
    )


def _record(
    version: str,
    *,
    lifecycle: ContractLifecycle = ContractLifecycle.current,
    predecessor: str | None = None,
    compatibility: CompatibilityClass = CompatibilityClass.initial,
    superseded_by: str | None = None,
) -> ContractVersionRecordV1:
    return ContractVersionRecordV1(
        contract_id=CONTRACT,
        version=version,
        producer_project_id=PRODUCER,
        lifecycle=lifecycle,
        predecessor_version=predecessor,
        compatibility_with_predecessor=compatibility,
        superseded_by_version=superseded_by,
        source_revision=REV,
        authority_reference=AUTH,
        evidence=(f"contract:{version}",),
    )


def _binding(version: str = "V1") -> ConsumedContractBindingV1:
    return ConsumedContractBindingV1(
        edge_id="edge-contract",
        contract_id=CONTRACT,
        version=version,
        producer_project_id=PRODUCER,
        consumer_project_id=CONSUMER,
    )


def test_initial_current_contract_is_consumable() -> None:
    registry = build_contract_version_registry(
        graph=_graph(),
        source_revision=REV,
        authority_reference=AUTH,
        records=(_record("V1"),),
        consumer_bindings=(_binding(),),
        imported_at=NOW,
    )
    record = registry.require_consumable("edge-contract")
    assert record.version == "V1"
    assert registry.requires_revalidation("edge-contract") is False
    assert registry.source_authority == "WORKSPACE_DRIVE_SOVEREIGN"
    assert registry.canonical_promotion_allowed is False


def test_breaking_successor_requires_revalidation() -> None:
    records = (
        _record(
            "V1",
            lifecycle=ContractLifecycle.deprecated,
            superseded_by="V2",
        ),
        _record(
            "V2",
            predecessor="V1",
            compatibility=CompatibilityClass.breaking,
        ),
    )
    registry = build_contract_version_registry(
        graph=_graph("V2"),
        source_revision=REV,
        authority_reference=AUTH,
        records=records,
        consumer_bindings=(_binding("V2"),),
        imported_at=NOW,
    )
    assert registry.requires_revalidation("edge-contract") is True


def test_backward_compatible_successor_does_not_require_revalidation() -> None:
    records = (
        _record(
            "V1",
            lifecycle=ContractLifecycle.deprecated,
            superseded_by="V2",
        ),
        _record(
            "V2",
            predecessor="V1",
            compatibility=CompatibilityClass.backward_compatible,
        ),
    )
    registry = build_contract_version_registry(
        graph=_graph("V2"),
        source_revision=REV,
        authority_reference=AUTH,
        records=records,
        consumer_bindings=(_binding("V2"),),
        imported_at=NOW,
    )
    assert registry.requires_revalidation("edge-contract") is False


def test_retired_contract_cannot_back_active_dependency_edge() -> None:
    retired = _record(
        "V1",
        lifecycle=ContractLifecycle.retired,
        superseded_by="V2",
    )
    successor = _record(
        "V2",
        predecessor="V1",
        compatibility=CompatibilityClass.backward_compatible,
    )
    with pytest.raises(GovernanceError, match="CONTRACT_VERSION_ACTIVE_EDGE_RETIRED"):
        build_contract_version_registry(
            graph=_graph("V1"),
            source_revision=REV,
            authority_reference=AUTH,
            records=(retired, successor),
            consumer_bindings=(_binding("V1"),),
            imported_at=NOW,
        )


def test_consumer_binding_must_match_dependency_edge() -> None:
    bad_binding = _binding().model_copy(update={"consumer_project_id": "PROJECT_C"})
    with pytest.raises(GovernanceError, match="CONTRACT_VERSION_BINDING_EDGE_MISMATCH"):
        build_contract_version_registry(
            graph=_graph(),
            source_revision=REV,
            authority_reference=AUTH,
            records=(_record("V1"),),
            consumer_bindings=(bad_binding,),
            imported_at=NOW,
        )


def test_unknown_predecessor_is_rejected() -> None:
    orphan = _record(
        "V2",
        predecessor="V1",
        compatibility=CompatibilityClass.backward_compatible,
    )
    with pytest.raises(ValidationError, match="CONTRACT_VERSION_UNKNOWN_PREDECESSOR"):
        build_contract_version_registry(
            graph=_graph("V2"),
            source_revision=REV,
            authority_reference=AUTH,
            records=(orphan,),
            consumer_bindings=(_binding("V2"),),
            imported_at=NOW,
        )


def test_multiple_current_versions_are_rejected() -> None:
    current_v1 = _record("V1")
    current_v2 = _record(
        "V2",
        predecessor="V1",
        compatibility=CompatibilityClass.backward_compatible,
    )
    with pytest.raises(ValidationError, match="CONTRACT_VERSION_MULTIPLE_CURRENT_VERSIONS"):
        build_contract_version_registry(
            graph=_graph("V2"),
            source_revision=REV,
            authority_reference=AUTH,
            records=(current_v1, current_v2),
            consumer_bindings=(_binding("V2"),),
            imported_at=NOW,
        )


def test_store_persists_and_replays_same_revision_idempotently() -> None:
    state = MemoryStateStore()
    store = ContractVersionRegistryStore(state, now=lambda: NOW)
    records = (_record("V1"),)
    bindings = (_binding(),)
    first = store.import_registry(
        graph=_graph(),
        source_revision=REV,
        authority_reference=AUTH,
        records=records,
        consumer_bindings=bindings,
    )
    second = store.import_registry(
        graph=_graph(),
        source_revision=REV,
        authority_reference=AUTH,
        records=records,
        consumer_bindings=bindings,
    )
    assert second.registry_sha256 == first.registry_sha256
    assert store.current().registry_sha256 == first.registry_sha256


def test_same_source_revision_with_changed_registry_is_rejected() -> None:
    state = MemoryStateStore()
    store = ContractVersionRegistryStore(state, now=lambda: NOW)
    store.import_registry(
        graph=_graph(),
        source_revision=REV,
        authority_reference=AUTH,
        records=(_record("V1"),),
        consumer_bindings=(_binding(),),
    )
    changed_record = _record("V1").model_copy(update={"evidence": ("changed-evidence",)})
    with pytest.raises(GovernanceError, match="CONTRACT_VERSION_SOURCE_REVISION_CONFLICT"):
        store.import_registry(
            graph=_graph(),
            source_revision=REV,
            authority_reference=AUTH,
            records=(changed_record,),
            consumer_bindings=(_binding(),),
        )


def test_persisted_registry_hash_tampering_is_rejected() -> None:
    state = MemoryStateStore()
    store = ContractVersionRegistryStore(state, now=lambda: NOW)
    store.import_registry(
        graph=_graph(),
        source_revision=REV,
        authority_reference=AUTH,
        records=(_record("V1"),),
        consumer_bindings=(_binding(),),
    )
    raw = state.load()
    raw[REGISTRY_STATE_KEY]["snapshots"][0]["registry_sha256"] = "0" * 64
    state.save(raw)
    with pytest.raises(GovernanceError, match="CONTRACT_VERSION_REGISTRY_HASH_MISMATCH"):
        store.current()
