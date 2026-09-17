from datetime import timedelta

import pytest

from palwakf_orchestrator.contract_version_registry import (
    CompatibilityClass,
    ConsumedContractBindingV1,
    ContractLifecycle,
    ContractVersionRecordV1,
    build_contract_version_registry,
)
from palwakf_orchestrator.cross_project_impact_analysis import (
    ImpactClassification,
    ImpactRevalidationReceiptV1,
    analyze_cross_project_impact,
    require_project_clear_for_execution,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import (
    MaterialChangeEventType,
    build_material_change_event,
)
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_change_inbox import (
    ProjectChangeInboxStatus,
    ProjectChangeInboxStore,
)
from palwakf_orchestrator.typed_dependency_graph import (
    DependencyEdgeV1,
    DependencyKind,
    ProjectDependencyDeclarationV1,
    build_typed_dependency_graph,
)
from tests.test_material_change_event_registry import AUTH, NOW, REV, A, B, _acceptance

C = "PROJECT_C"


def _graph(*, transitive: bool = False):
    edges = [
        DependencyEdgeV1(
            edge_id="edge-ab",
            producer_project_id=A,
            consumer_project_id=B,
            kind=DependencyKind.api,
            contract_id="CONTRACT_AB",
            version="V1",
            authority_reference=AUTH,
            source_revision=REV,
            evidence=("edge-ab",),
        )
    ]
    if transitive:
        edges.append(
            DependencyEdgeV1(
                edge_id="edge-bc",
                producer_project_id=B,
                consumer_project_id=C,
                kind=DependencyKind.data,
                contract_id="CONTRACT_BC",
                version="V1",
                authority_reference=AUTH,
                source_revision=REV,
                evidence=("edge-bc",),
            )
        )
    declarations = (
        ProjectDependencyDeclarationV1(project_id=A, produced_edge_ids=("edge-ab",)),
        ProjectDependencyDeclarationV1(
            project_id=B,
            produced_edge_ids=(("edge-bc",) if transitive else ()),
            consumed_edge_ids=("edge-ab",),
        ),
        ProjectDependencyDeclarationV1(
            project_id=C,
            consumed_edge_ids=(("edge-bc",) if transitive else ()),
        ),
    )
    return build_typed_dependency_graph(
        source_revision=REV,
        authority_reference=AUTH,
        project_ids=(A, B, C),
        declarations=declarations,
        edges=tuple(edges),
        imported_at=NOW,
    )


def _contracts(graph):
    records = []
    bindings = []
    for edge in graph.edges:
        records.append(
            ContractVersionRecordV1(
                contract_id=edge.contract_id,
                version=edge.version,
                producer_project_id=edge.producer_project_id,
                lifecycle=ContractLifecycle.current,
                compatibility_with_predecessor=CompatibilityClass.initial,
                source_revision=REV,
                authority_reference=AUTH,
                evidence=(f"contract:{edge.contract_id}",),
            )
        )
        bindings.append(
            ConsumedContractBindingV1(
                edge_id=edge.edge_id,
                contract_id=edge.contract_id,
                version=edge.version,
                producer_project_id=edge.producer_project_id,
                consumer_project_id=edge.consumer_project_id,
            )
        )
    return build_contract_version_registry(
        graph=graph,
        source_revision=REV,
        authority_reference=AUTH,
        records=tuple(records),
        consumer_bindings=tuple(bindings),
        imported_at=NOW,
    )


def _event(event_type: MaterialChangeEventType, *, graph=None, event_id="impact-event"):
    graph = graph or _graph()
    kwargs = {}
    if event_type == MaterialChangeEventType.dependency_changed:
        kwargs["edge_id"] = "edge-ab"
    if event_type in {
        MaterialChangeEventType.contract_version_published,
        MaterialChangeEventType.contract_version_deprecated,
        MaterialChangeEventType.contract_version_retired,
    }:
        kwargs.update(contract_id="CONTRACT_AB", contract_version="V1")
    return build_material_change_event(
        event_id=event_id,
        event_type=event_type,
        acceptance=_acceptance(f"change-{event_id}"),
        project_id=A,
        affected_project_ids=(B,),
        graph=graph,
        contract_registry=_contracts(graph),
        source_revision=REV,
        evidence=("impact:event",),
        occurred_at=NOW,
        **kwargs,
    )


def test_dependency_change_requires_revalidation_and_leaves_unrelated_no_impact() -> None:
    graph = _graph()
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.dependency_changed, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    assert analysis.decision_for(B).classification == ImpactClassification.revalidation
    assert analysis.decision_for(C).classification == ImpactClassification.no_impact


def test_retired_contract_blocks_affected_project() -> None:
    graph = _graph()
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.contract_version_retired, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    assert analysis.decision_for(B).classification == ImpactClassification.blocking
    with pytest.raises(GovernanceError, match="IMPACT_ANALYSIS_PROJECT_BLOCKED"):
        require_project_clear_for_execution(analysis, project_id=B)


def test_deprecated_contract_is_deferred() -> None:
    graph = _graph()
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.contract_version_deprecated, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    assert analysis.decision_for(B).classification == ImpactClassification.deferred


def test_source_project_is_info() -> None:
    graph = _graph()
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.runtime_contract_changed, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    assert analysis.decision_for(A).classification == ImpactClassification.info


def test_transitive_downstream_project_receives_info_visibility() -> None:
    graph = _graph(transitive=True)
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.runtime_contract_changed, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    assert analysis.decision_for(B).classification == ImpactClassification.revalidation
    assert analysis.decision_for(C).classification == ImpactClassification.info


def test_inbox_deferred_overrides_direct_revalidation() -> None:
    graph = _graph()
    event = _event(MaterialChangeEventType.runtime_contract_changed, graph=graph)
    store = ProjectChangeInboxStore(MemoryStateStore(), now=lambda: NOW + timedelta(minutes=1))
    item = store.ingest_event(event)[0]
    store.transition(
        item.inbox_item_id,
        project_id=B,
        expected_status=ProjectChangeInboxStatus.open,
        new_status=ProjectChangeInboxStatus.deferred,
        lifecycle_evidence=("defer:evidence",),
    )
    analysis = analyze_cross_project_impact(
        event=event,
        graph=graph,
        contract_registry=_contracts(graph),
        inbox=store.snapshot(),
        generated_at=NOW,
    )
    assert analysis.decision_for(B).classification == ImpactClassification.deferred


def test_revalidation_gate_requires_matching_receipt() -> None:
    graph = _graph()
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.dependency_changed, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    with pytest.raises(GovernanceError, match="IMPACT_ANALYSIS_REVALIDATION_RECEIPT_REQUIRED"):
        require_project_clear_for_execution(analysis, project_id=B)
    receipt = ImpactRevalidationReceiptV1(
        event_id=analysis.event_id,
        project_id=B,
        authority_reference=analysis.authority_reference,
        evidence=("revalidated",),
    )
    result = require_project_clear_for_execution(
        analysis,
        project_id=B,
        revalidation_receipt=receipt,
    )
    assert result.classification == ImpactClassification.revalidation


def test_wrong_authority_receipt_fails_closed() -> None:
    graph = _graph()
    analysis = analyze_cross_project_impact(
        event=_event(MaterialChangeEventType.dependency_changed, graph=graph),
        graph=graph,
        contract_registry=_contracts(graph),
        generated_at=NOW,
    )
    bad = ImpactRevalidationReceiptV1(
        event_id=analysis.event_id,
        project_id=B,
        authority_reference="WRONG-AUTHORITY",
        evidence=("bad",),
    )
    with pytest.raises(GovernanceError, match="IMPACT_ANALYSIS_REVALIDATION_AUTHORITY_MISMATCH"):
        require_project_clear_for_execution(
            analysis,
            project_id=B,
            revalidation_receipt=bad,
        )


def test_snapshot_drift_fails_closed() -> None:
    graph = _graph()
    event = _event(MaterialChangeEventType.runtime_contract_changed, graph=graph)
    changed_graph = _graph(transitive=True)
    with pytest.raises(GovernanceError, match="IMPACT_ANALYSIS_GRAPH_SNAPSHOT_MISMATCH"):
        analyze_cross_project_impact(
            event=event,
            graph=changed_graph,
            contract_registry=_contracts(changed_graph),
            generated_at=NOW,
        )


def test_all_required_impact_classes_exist() -> None:
    assert {item.value for item in ImpactClassification} == {
        "BLOCKING",
        "REVALIDATION",
        "DEFERRED",
        "INFO",
        "NO_IMPACT",
    }
