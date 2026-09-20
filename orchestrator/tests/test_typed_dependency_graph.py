from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_manifest_service import ProjectContractManifestService
from palwakf_orchestrator.typed_dependency_graph import (
    GRAPH_STATE_KEY,
    DependencyEdgeStatus,
    DependencyEdgeV1,
    DependencyKind,
    ProjectDependencyDeclarationV1,
    TypedDependencyGraphStore,
    build_graph_from_project_registry,
)

REV = "drive-revision-015"
AUTH = "PREL5-015-AUTHORITY"
NOW = datetime(2026, 9, 16, 19, 0, tzinfo=UTC)


def _registry():
    return ProjectContractManifestService().registry()


def _edges() -> tuple[DependencyEdgeV1, ...]:
    projects = sorted(item.project_id for item in _registry().manifests)
    producer = projects[0]
    edges: list[DependencyEdgeV1] = []
    for index, kind in enumerate(DependencyKind):
        consumer = projects[(index % (len(projects) - 1)) + 1]
        edges.append(
            DependencyEdgeV1(
                edge_id=f"edge-{kind.value.lower()}",
                producer_project_id=producer,
                consumer_project_id=consumer,
                kind=kind,
                contract_id=f"contract-{kind.value.lower()}",
                version="V1",
                status=DependencyEdgeStatus.active,
                authority_reference=AUTH,
                source_revision=REV,
                evidence=(f"evidence:{kind.value}",),
            )
        )
    return tuple(edges)


def _declarations(
    edges: tuple[DependencyEdgeV1, ...],
) -> tuple[ProjectDependencyDeclarationV1, ...]:
    projects = sorted(item.project_id for item in _registry().manifests)
    result: list[ProjectDependencyDeclarationV1] = []
    for project_id in projects:
        result.append(
            ProjectDependencyDeclarationV1(
                project_id=project_id,
                produced_edge_ids=tuple(
                    edge.edge_id for edge in edges if edge.producer_project_id == project_id
                ),
                consumed_edge_ids=tuple(
                    edge.edge_id for edge in edges if edge.consumer_project_id == project_id
                ),
            )
        )
    return tuple(result)


def _graph(edges: tuple[DependencyEdgeV1, ...] | None = None):
    selected = edges or _edges()
    return build_graph_from_project_registry(
        project_registry=_registry(),
        source_revision=REV,
        authority_reference=AUTH,
        declarations=_declarations(selected),
        edges=selected,
        imported_at=NOW,
    )


def test_all_seven_dependency_kinds_are_versioned_and_declared() -> None:
    graph = _graph()
    assert {edge.kind for edge in graph.edges} == set(DependencyKind)
    assert all(edge.version == "V1" for edge in graph.edges)
    assert graph.source_authority == "WORKSPACE_DRIVE_SOVEREIGN"
    assert graph.canonical_promotion_allowed is False


def test_graph_queries_preserve_project_direction() -> None:
    graph = _graph()
    producer = graph.edges[0].producer_project_id
    consumer = graph.edges[0].consumer_project_id
    assert graph.outgoing(producer)
    assert graph.incoming(consumer)
    with pytest.raises(GovernanceError, match="DEPENDENCY_GRAPH_PROJECT_NOT_FOUND"):
        graph.incoming("UNKNOWN_PROJECT")


def test_unknown_project_endpoint_is_rejected() -> None:
    edge = _edges()[0].model_copy(update={"consumer_project_id": "UNKNOWN_PROJECT"})
    with pytest.raises(ValidationError, match="DEPENDENCY_GRAPH_UNKNOWN_PROJECT_ENDPOINT"):
        build_graph_from_project_registry(
            project_registry=_registry(),
            source_revision=REV,
            authority_reference=AUTH,
            declarations=_declarations((edge,)),
            edges=(edge,),
            imported_at=NOW,
        )


def test_missing_producer_declaration_is_rejected() -> None:
    edge = _edges()[0]
    declarations = list(_declarations((edge,)))
    producer_index = next(
        i for i, item in enumerate(declarations) if item.project_id == edge.producer_project_id
    )
    declarations[producer_index] = declarations[producer_index].model_copy(
        update={"produced_edge_ids": ()}
    )
    with pytest.raises(ValidationError, match="DEPENDENCY_GRAPH_PRODUCER_DECLARATION_MISSING"):
        build_graph_from_project_registry(
            project_registry=_registry(),
            source_revision=REV,
            authority_reference=AUTH,
            declarations=tuple(declarations),
            edges=(edge,),
            imported_at=NOW,
        )


def test_missing_consumer_declaration_is_rejected() -> None:
    edge = _edges()[0]
    declarations = list(_declarations((edge,)))
    consumer_index = next(
        i for i, item in enumerate(declarations) if item.project_id == edge.consumer_project_id
    )
    declarations[consumer_index] = declarations[consumer_index].model_copy(
        update={"consumed_edge_ids": ()}
    )
    with pytest.raises(ValidationError, match="DEPENDENCY_GRAPH_CONSUMER_DECLARATION_MISSING"):
        build_graph_from_project_registry(
            project_registry=_registry(),
            source_revision=REV,
            authority_reference=AUTH,
            declarations=tuple(declarations),
            edges=(edge,),
            imported_at=NOW,
        )


def test_duplicate_active_edge_key_is_rejected() -> None:
    edge = _edges()[0]
    duplicate = edge.model_copy(update={"edge_id": "edge-duplicate"})
    edges = (edge, duplicate)
    with pytest.raises(ValidationError, match="DEPENDENCY_GRAPH_DUPLICATE_ACTIVE_EDGE"):
        build_graph_from_project_registry(
            project_registry=_registry(),
            source_revision=REV,
            authority_reference=AUTH,
            declarations=_declarations(edges),
            edges=edges,
            imported_at=NOW,
        )


def test_store_persists_and_replays_same_source_revision_idempotently() -> None:
    state = MemoryStateStore()
    store = TypedDependencyGraphStore(state, now=lambda: NOW)
    first = store.import_graph(
        project_registry=_registry(),
        source_revision=REV,
        authority_reference=AUTH,
        declarations=_declarations(_edges()),
        edges=_edges(),
    )
    second = store.import_graph(
        project_registry=_registry(),
        source_revision=REV,
        authority_reference=AUTH,
        declarations=_declarations(_edges()),
        edges=_edges(),
    )
    assert second.graph_sha256 == first.graph_sha256
    assert store.current().graph_sha256 == first.graph_sha256


def test_same_source_revision_with_changed_graph_is_rejected() -> None:
    state = MemoryStateStore()
    store = TypedDependencyGraphStore(state, now=lambda: NOW)
    edges = _edges()
    store.import_graph(
        project_registry=_registry(),
        source_revision=REV,
        authority_reference=AUTH,
        declarations=_declarations(edges),
        edges=edges,
    )
    changed = (edges[0].model_copy(update={"version": "V2"}),) + edges[1:]
    with pytest.raises(GovernanceError, match="DEPENDENCY_GRAPH_SOURCE_REVISION_CONFLICT"):
        store.import_graph(
            project_registry=_registry(),
            source_revision=REV,
            authority_reference=AUTH,
            declarations=_declarations(changed),
            edges=changed,
        )


def test_persisted_graph_hash_tampering_is_rejected() -> None:
    state = MemoryStateStore()
    store = TypedDependencyGraphStore(state, now=lambda: NOW)
    store.import_graph(
        project_registry=_registry(),
        source_revision=REV,
        authority_reference=AUTH,
        declarations=_declarations(_edges()),
        edges=_edges(),
    )
    raw = state.load()
    raw[GRAPH_STATE_KEY]["snapshots"][0]["graph_sha256"] = "0" * 64
    state.save(raw)
    with pytest.raises(GovernanceError, match="DEPENDENCY_GRAPH_HASH_MISMATCH"):
        store.current()
