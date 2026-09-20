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

GRAPH_STATE_KEY = "pre_l5_typed_dependency_graph_v1"


class DependencyKind(StrEnum):
    api = "API"
    data = "DATA"
    schema = "SCHEMA"
    identity = "IDENTITY"
    permissions = "PERMISSIONS"
    knowledge = "KNOWLEDGE"
    runtime = "RUNTIME"


class DependencyEdgeStatus(StrEnum):
    active = "ACTIVE"
    superseded = "SUPERSEDED"
    retired = "RETIRED"


class DependencyEdgeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str = Field(min_length=1, max_length=200)
    producer_project_id: str = Field(min_length=3, max_length=128)
    consumer_project_id: str = Field(min_length=3, max_length=128)
    kind: DependencyKind
    contract_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    status: DependencyEdgeStatus = DependencyEdgeStatus.active
    authority_reference: str = Field(min_length=1, max_length=500)
    source_revision: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_edge(self) -> Self:
        if self.producer_project_id == self.consumer_project_id:
            raise ValueError("DEPENDENCY_EDGE_SELF_REFERENCE_FORBIDDEN")
        if any(not item.strip() for item in self.evidence):
            raise ValueError("DEPENDENCY_EDGE_EVIDENCE_REQUIRED")
        return self


class ProjectDependencyDeclarationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=3, max_length=128)
    produced_edge_ids: tuple[str, ...] = ()
    consumed_edge_ids: tuple[str, ...] = ()


class TypedDependencyGraphV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: Literal["PALWAKF_TYPED_DEPENDENCY_GRAPH_V1"] = "PALWAKF_TYPED_DEPENDENCY_GRAPH_V1"
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    project_ids: tuple[str, ...] = Field(min_length=1)
    declarations: tuple[ProjectDependencyDeclarationV1, ...] = Field(min_length=1)
    edges: tuple[DependencyEdgeV1, ...] = Field(min_length=1)
    imported_at: datetime
    graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        self._validate_projects_and_edges()
        self._validate_declarations()
        self._validate_active_edge_keys()
        return self

    def _validate_projects_and_edges(self) -> None:
        projects = set(self.project_ids)
        if len(projects) != len(self.project_ids):
            raise ValueError("DEPENDENCY_GRAPH_DUPLICATE_PROJECT_ID")
        if len({edge.edge_id for edge in self.edges}) != len(self.edges):
            raise ValueError("DEPENDENCY_GRAPH_DUPLICATE_EDGE_ID")
        for edge in self.edges:
            if edge.producer_project_id not in projects or edge.consumer_project_id not in projects:
                raise ValueError("DEPENDENCY_GRAPH_UNKNOWN_PROJECT_ENDPOINT")
            if edge.source_revision != self.source_revision:
                raise ValueError("DEPENDENCY_GRAPH_SOURCE_REVISION_MISMATCH")
            if edge.authority_reference != self.authority_reference:
                raise ValueError("DEPENDENCY_GRAPH_AUTHORITY_REFERENCE_MISMATCH")

    def _validate_declarations(self) -> None:
        by_project = {item.project_id: item for item in self.declarations}
        if set(by_project) != set(self.project_ids):
            raise ValueError("DEPENDENCY_GRAPH_PROJECT_DECLARATION_SET_MISMATCH")
        edge_ids = {edge.edge_id for edge in self.edges}
        for declaration in self.declarations:
            produced = set(declaration.produced_edge_ids)
            consumed = set(declaration.consumed_edge_ids)
            if not produced.issubset(edge_ids) or not consumed.issubset(edge_ids):
                raise ValueError("DEPENDENCY_GRAPH_DECLARATION_UNKNOWN_EDGE")
        for edge in self.edges:
            producer = by_project[edge.producer_project_id]
            consumer = by_project[edge.consumer_project_id]
            if edge.edge_id not in producer.produced_edge_ids:
                raise ValueError("DEPENDENCY_GRAPH_PRODUCER_DECLARATION_MISSING")
            if edge.edge_id not in consumer.consumed_edge_ids:
                raise ValueError("DEPENDENCY_GRAPH_CONSUMER_DECLARATION_MISSING")

    def _validate_active_edge_keys(self) -> None:
        seen: set[tuple[str, str, DependencyKind, str, str]] = set()
        for edge in self.edges:
            if edge.status != DependencyEdgeStatus.active:
                continue
            key = (
                edge.producer_project_id,
                edge.consumer_project_id,
                edge.kind,
                edge.contract_id,
                edge.version,
            )
            if key in seen:
                raise ValueError("DEPENDENCY_GRAPH_DUPLICATE_ACTIVE_EDGE")
            seen.add(key)

    def outgoing(self, project_id: str) -> tuple[DependencyEdgeV1, ...]:
        self._require_project(project_id)
        return tuple(edge for edge in self.edges if edge.producer_project_id == project_id)

    def incoming(self, project_id: str) -> tuple[DependencyEdgeV1, ...]:
        self._require_project(project_id)
        return tuple(edge for edge in self.edges if edge.consumer_project_id == project_id)

    def _require_project(self, project_id: str) -> None:
        if project_id not in self.project_ids:
            raise GovernanceError("DEPENDENCY_GRAPH_PROJECT_NOT_FOUND")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_typed_dependency_graph(
    *,
    source_revision: str,
    authority_reference: str,
    project_ids: tuple[str, ...],
    declarations: tuple[ProjectDependencyDeclarationV1, ...],
    edges: tuple[DependencyEdgeV1, ...],
    imported_at: datetime | None = None,
) -> TypedDependencyGraphV1:
    payload = {
        "graph_id": "PALWAKF_TYPED_DEPENDENCY_GRAPH_V1",
        "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "project_ids": project_ids,
        "declarations": [item.model_dump(mode="json") for item in declarations],
        "edges": [item.model_dump(mode="json") for item in edges],
        "canonical_promotion_allowed": False,
    }
    return TypedDependencyGraphV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        project_ids=project_ids,
        declarations=declarations,
        edges=edges,
        imported_at=imported_at or datetime.now(UTC),
        graph_sha256=_sha256(payload),
    )


def build_graph_from_project_registry(
    *,
    project_registry: object,
    source_revision: str,
    authority_reference: str,
    declarations: tuple[ProjectDependencyDeclarationV1, ...],
    edges: tuple[DependencyEdgeV1, ...],
    imported_at: datetime | None = None,
) -> TypedDependencyGraphV1:
    manifests = getattr(project_registry, "manifests", None)
    if not isinstance(manifests, list) or not manifests:
        raise GovernanceError("DEPENDENCY_GRAPH_PROJECT_REGISTRY_INVALID")
    project_ids = tuple(sorted(str(item.project_id) for item in manifests))
    return build_typed_dependency_graph(
        source_revision=source_revision,
        authority_reference=authority_reference,
        project_ids=project_ids,
        declarations=declarations,
        edges=edges,
        imported_at=imported_at,
    )


def _expected_graph_sha256(graph: TypedDependencyGraphV1) -> str:
    payload = {
        "graph_id": graph.graph_id,
        "source_authority": graph.source_authority,
        "source_revision": graph.source_revision,
        "authority_reference": graph.authority_reference,
        "project_ids": graph.project_ids,
        "declarations": [item.model_dump(mode="json") for item in graph.declarations],
        "edges": [item.model_dump(mode="json") for item in graph.edges],
        "canonical_promotion_allowed": graph.canonical_promotion_allowed,
    }
    return _sha256(payload)


class TypedDependencyGraphStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def current(self) -> TypedDependencyGraphV1:
        history = self.history()
        if not history:
            raise GovernanceError("DEPENDENCY_GRAPH_NOT_IMPORTED")
        return history[-1]

    def history(self) -> tuple[TypedDependencyGraphV1, ...]:
        state = self._state_store.load()
        raw = state.get(GRAPH_STATE_KEY, {})
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else []
        parsed: list[TypedDependencyGraphV1] = []
        for item in snapshots:
            graph = TypedDependencyGraphV1.model_validate(item)
            if graph.graph_sha256 != _expected_graph_sha256(graph):
                raise GovernanceError("DEPENDENCY_GRAPH_HASH_MISMATCH")
            parsed.append(graph)
        return tuple(parsed)

    def import_graph(
        self,
        *,
        project_registry: object,
        source_revision: str,
        authority_reference: str,
        declarations: tuple[ProjectDependencyDeclarationV1, ...],
        edges: tuple[DependencyEdgeV1, ...],
    ) -> TypedDependencyGraphV1:
        graph = build_graph_from_project_registry(
            project_registry=project_registry,
            source_revision=source_revision,
            authority_reference=authority_reference,
            declarations=declarations,
            edges=edges,
            imported_at=self._now(),
        )
        history = list(self.history())
        for existing in history:
            if existing.source_revision != source_revision:
                continue
            if existing.graph_sha256 != graph.graph_sha256:
                raise GovernanceError("DEPENDENCY_GRAPH_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(graph)
        state = self._state_store.load()
        state[GRAPH_STATE_KEY] = {
            "registry_version": "PALWAKF_TYPED_DEPENDENCY_GRAPH_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_PROJECTION_ONLY",
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return graph
