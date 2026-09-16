from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from palwakf_orchestrator.contract_version_registry import (
    CompatibilityClass,
    ConsumedContractBindingV1,
    ContractLifecycle,
    ContractVersionRecordV1,
    build_contract_version_registry,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import (
    REGISTRY_STATE_KEY,
    AcceptedMaterialChangeV1,
    MaterialChangeEventRegistryStore,
    MaterialChangeEventType,
    build_material_change_event,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore
from palwakf_orchestrator.typed_dependency_graph import (
    DependencyEdgeV1,
    DependencyKind,
    ProjectDependencyDeclarationV1,
    build_typed_dependency_graph,
)

REV = "drive-revision-017"
AUTH = "PREL5-017-AUTHORITY"
NOW = datetime(2026, 9, 16, 21, 0, tzinfo=UTC)
A = "PROJECT_A"
B = "PROJECT_B"


def _graph(version: str = "V1"):
    edge = DependencyEdgeV1(
        edge_id="edge-1",
        producer_project_id=A,
        consumer_project_id=B,
        kind=DependencyKind.api,
        contract_id="CONTRACT_A",
        version=version,
        authority_reference=AUTH,
        source_revision=REV,
        evidence=("graph-evidence",),
    )
    declarations = (
        ProjectDependencyDeclarationV1(project_id=A, produced_edge_ids=(edge.edge_id,)),
        ProjectDependencyDeclarationV1(project_id=B, consumed_edge_ids=(edge.edge_id,)),
    )
    return build_typed_dependency_graph(
        source_revision=REV,
        authority_reference=AUTH,
        project_ids=(A, B),
        declarations=declarations,
        edges=(edge,),
        imported_at=NOW,
    )


def _contracts(graph=None):
    graph = graph or _graph()
    version = graph.edges[0].version
    record = ContractVersionRecordV1(
        contract_id="CONTRACT_A",
        version=version,
        producer_project_id=A,
        lifecycle=ContractLifecycle.current,
        compatibility_with_predecessor=CompatibilityClass.initial,
        source_revision=REV,
        authority_reference=AUTH,
        evidence=("contract-evidence",),
    )
    binding = ConsumedContractBindingV1(
        edge_id="edge-1",
        contract_id="CONTRACT_A",
        version=version,
        producer_project_id=A,
        consumer_project_id=B,
    )
    return build_contract_version_registry(
        graph=graph,
        source_revision=REV,
        authority_reference=AUTH,
        records=(record,),
        consumer_bindings=(binding,),
        imported_at=NOW,
    )


def _acceptance(change_id: str = "change-1") -> AcceptedMaterialChangeV1:
    return AcceptedMaterialChangeV1(
        change_id=change_id,
        authority_reference=AUTH,
        accepted_at=NOW,
        evidence=("acceptance:evidence",),
    )


def test_accepted_dependency_change_emits_typed_authoritative_event() -> None:
    graph = _graph()
    event = build_material_change_event(
        event_id="event-1",
        event_type=MaterialChangeEventType.dependency_changed,
        acceptance=_acceptance(),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=_contracts(graph),
        source_revision=REV,
        evidence=("change:evidence",),
        edge_id="edge-1",
        occurred_at=NOW,
    )
    assert event.change_id == "change-1"
    assert event.dependency_graph_sha256 == graph.graph_sha256
    assert "acceptance:evidence" in event.evidence
    assert event.event_sha256


def test_contract_material_event_requires_exact_contract_reference() -> None:
    graph = _graph()
    event = build_material_change_event(
        event_id="event-contract",
        event_type=MaterialChangeEventType.contract_version_published,
        acceptance=_acceptance("change-contract"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=_contracts(graph),
        source_revision=REV,
        evidence=(),
        contract_id="CONTRACT_A",
        contract_version="V1",
        occurred_at=NOW,
    )
    assert event.contract_id == "CONTRACT_A"
    assert event.contract_version == "V1"


def test_dependency_event_rejects_unknown_edge() -> None:
    graph = _graph()
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_UNKNOWN_DEPENDENCY_EDGE"):
        build_material_change_event(
            event_id="event-bad-edge",
            event_type=MaterialChangeEventType.dependency_changed,
            acceptance=_acceptance("change-bad-edge"),
            project_id=A,
            affected_project_ids=(B,),
            graph=graph,
            contract_registry=_contracts(graph),
            source_revision=REV,
            evidence=(),
            edge_id="missing-edge",
            occurred_at=NOW,
        )


def test_dependency_event_rejects_wrong_producer() -> None:
    graph = _graph()
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_DEPENDENCY_PRODUCER_MISMATCH"):
        build_material_change_event(
            event_id="event-wrong-producer",
            event_type=MaterialChangeEventType.dependency_changed,
            acceptance=_acceptance("change-wrong-producer"),
            project_id=B,
            affected_project_ids=(A,),
            graph=graph,
            contract_registry=_contracts(graph),
            source_revision=REV,
            evidence=(),
            edge_id="edge-1",
            occurred_at=NOW,
        )


def test_stale_contract_registry_graph_binding_is_rejected() -> None:
    graph_v1 = _graph("V1")
    graph_v2 = _graph("V2")
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_STALE_CONTRACT_REGISTRY_GRAPH"):
        build_material_change_event(
            event_id="event-stale",
            event_type=MaterialChangeEventType.runtime_contract_changed,
            acceptance=_acceptance("change-stale"),
            project_id=A,
            affected_project_ids=(B,),
            graph=graph_v2,
            contract_registry=_contracts(graph_v1),
            source_revision=REV,
            evidence=(),
            occurred_at=NOW,
        )


def test_event_cannot_precede_acceptance() -> None:
    graph = _graph()
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_EVENT_BEFORE_ACCEPTANCE"):
        build_material_change_event(
            event_id="event-before",
            event_type=MaterialChangeEventType.runtime_contract_changed,
            acceptance=_acceptance("change-before"),
            project_id=A,
            affected_project_ids=(B,),
            graph=graph,
            contract_registry=_contracts(graph),
            source_revision=REV,
            evidence=(),
            occurred_at=NOW - timedelta(seconds=1),
        )


def test_project_leakage_is_rejected() -> None:
    graph = _graph()
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_PROJECT_BINDING_MISMATCH"):
        build_material_change_event(
            event_id="event-leak",
            event_type=MaterialChangeEventType.runtime_contract_changed,
            acceptance=_acceptance("change-leak"),
            project_id=A,
            affected_project_ids=("PROJECT_UNKNOWN",),
            graph=graph,
            contract_registry=_contracts(graph),
            source_revision=REV,
            evidence=(),
            occurred_at=NOW,
        )


def test_dependency_event_requires_consumer_in_affected_projects() -> None:
    graph = _graph()
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_DEPENDENCY_CONSUMER_NOT_AFFECTED"):
        build_material_change_event(
            event_id="event-missing-consumer",
            event_type=MaterialChangeEventType.dependency_changed,
            acceptance=_acceptance("change-missing-consumer"),
            project_id=A,
            affected_project_ids=(A,),
            graph=graph,
            contract_registry=_contracts(graph),
            source_revision=REV,
            evidence=(),
            edge_id="edge-1",
            occurred_at=NOW,
        )


def test_sqlite_restart_persists_material_change_event(tmp_path) -> None:
    graph = _graph()
    contracts = _contracts(graph)
    path = tmp_path / "state.db"
    store = MaterialChangeEventRegistryStore(SQLiteStateStore(path), now=lambda: NOW)
    created = store.register_accepted_change(
        event_id="event-persist",
        event_type=MaterialChangeEventType.runtime_contract_changed,
        acceptance=_acceptance("change-persist"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=contracts,
        source_revision=REV,
        evidence=("persist-evidence",),
    )
    restarted = MaterialChangeEventRegistryStore(SQLiteStateStore(path), now=lambda: NOW)
    assert restarted.registry().get(created.event_id).event_sha256 == created.event_sha256


def test_idempotent_replay_returns_existing_event() -> None:
    graph = _graph()
    contracts = _contracts(graph)
    store = MaterialChangeEventRegistryStore(MemoryStateStore(), now=lambda: NOW)
    kwargs = dict(
        event_id="event-replay",
        event_type=MaterialChangeEventType.runtime_contract_changed,
        acceptance=_acceptance("change-replay"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=contracts,
        source_revision=REV,
        evidence=("replay-evidence",),
    )
    first = store.register_accepted_change(**kwargs)
    second = store.register_accepted_change(**kwargs)
    assert second.event_sha256 == first.event_sha256
    assert len(store.registry().events) == 1


def test_idempotency_conflict_is_rejected() -> None:
    graph = _graph()
    contracts = _contracts(graph)
    store = MaterialChangeEventRegistryStore(MemoryStateStore(), now=lambda: NOW)
    store.register_accepted_change(
        event_id="event-conflict",
        event_type=MaterialChangeEventType.runtime_contract_changed,
        acceptance=_acceptance("change-conflict"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=contracts,
        source_revision=REV,
        evidence=("first-evidence",),
    )
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_EVENT_IDEMPOTENCY_CONFLICT"):
        store.register_accepted_change(
            event_id="event-conflict",
            event_type=MaterialChangeEventType.runtime_contract_changed,
            acceptance=_acceptance("change-conflict"),
            project_id=A,
            affected_project_ids=(B,),
            graph=graph,
            contract_registry=contracts,
            source_revision=REV,
            evidence=("different-evidence",),
        )


def test_persisted_event_hash_tampering_is_rejected() -> None:
    graph = _graph()
    contracts = _contracts(graph)
    state_store = MemoryStateStore()
    store = MaterialChangeEventRegistryStore(state_store, now=lambda: NOW)
    store.register_accepted_change(
        event_id="event-tamper",
        event_type=MaterialChangeEventType.runtime_contract_changed,
        acceptance=_acceptance("change-tamper"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=contracts,
        source_revision=REV,
        evidence=("tamper-evidence",),
    )
    state = state_store.load()
    state[REGISTRY_STATE_KEY]["events"][0]["event_sha256"] = "0" * 64
    state_store.save(state)
    with pytest.raises(GovernanceError, match="MATERIAL_CHANGE_EVENT_HASH_MISMATCH"):
        store.registry()
