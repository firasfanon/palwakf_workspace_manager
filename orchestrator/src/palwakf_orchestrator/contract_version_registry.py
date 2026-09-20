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
from palwakf_orchestrator.typed_dependency_graph import (
    DependencyEdgeStatus,
    TypedDependencyGraphV1,
)

REGISTRY_STATE_KEY = "pre_l5_contract_version_registry_v1"


class ContractLifecycle(StrEnum):
    current = "CURRENT"
    deprecated = "DEPRECATED"
    retired = "RETIRED"


class CompatibilityClass(StrEnum):
    initial = "INITIAL"
    backward_compatible = "BACKWARD_COMPATIBLE"
    breaking = "BREAKING"


class ContractVersionRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    producer_project_id: str = Field(min_length=3, max_length=128)
    lifecycle: ContractLifecycle
    predecessor_version: str | None = Field(default=None, max_length=100)
    compatibility_with_predecessor: CompatibilityClass
    superseded_by_version: str | None = Field(default=None, max_length=100)
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("CONTRACT_VERSION_EVIDENCE_REQUIRED")
        if self.predecessor_version is None:
            if self.compatibility_with_predecessor != CompatibilityClass.initial:
                raise ValueError("CONTRACT_VERSION_INITIAL_COMPATIBILITY_REQUIRED")
        elif self.compatibility_with_predecessor == CompatibilityClass.initial:
            raise ValueError("CONTRACT_VERSION_PREDECESSOR_COMPATIBILITY_REQUIRED")
        if self.lifecycle != ContractLifecycle.current and not self.superseded_by_version:
            raise ValueError("CONTRACT_VERSION_SUPERSEDED_BY_REQUIRED")
        return self


class ConsumedContractBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str = Field(min_length=1, max_length=200)
    contract_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    producer_project_id: str = Field(min_length=3, max_length=128)
    consumer_project_id: str = Field(min_length=3, max_length=128)


class ContractVersionRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_CONTRACT_VERSION_REGISTRY_V1"] = (
        "PALWAKF_CONTRACT_VERSION_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)
    dependency_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[ContractVersionRecordV1, ...] = Field(min_length=1)
    consumer_bindings: tuple[ConsumedContractBindingV1, ...] = ()
    imported_at: datetime
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        by_key = {
            (item.producer_project_id, item.contract_id, item.version): item
            for item in self.records
        }
        if len(by_key) != len(self.records):
            raise ValueError("CONTRACT_VERSION_DUPLICATE_RECORD")
        if any(item.source_revision != self.source_revision for item in self.records):
            raise ValueError("CONTRACT_VERSION_SOURCE_REVISION_MISMATCH")
        if any(item.authority_reference != self.authority_reference for item in self.records):
            raise ValueError("CONTRACT_VERSION_AUTHORITY_REFERENCE_MISMATCH")
        self._validate_current_uniqueness()
        self._validate_version_lineage(by_key)
        if len({item.edge_id for item in self.consumer_bindings}) != len(self.consumer_bindings):
            raise ValueError("CONTRACT_VERSION_DUPLICATE_CONSUMER_BINDING")
        return self

    def _validate_current_uniqueness(self) -> None:
        current_keys: set[tuple[str, str]] = set()
        for record in self.records:
            if record.lifecycle != ContractLifecycle.current:
                continue
            key = (record.producer_project_id, record.contract_id)
            if key in current_keys:
                raise ValueError("CONTRACT_VERSION_MULTIPLE_CURRENT_VERSIONS")
            current_keys.add(key)

    def _validate_version_lineage(
        self,
        by_key: dict[tuple[str, str, str], ContractVersionRecordV1],
    ) -> None:
        for record in self.records:
            base = (record.producer_project_id, record.contract_id)
            if record.predecessor_version is not None:
                predecessor_key = (*base, record.predecessor_version)
                if predecessor_key not in by_key:
                    raise ValueError("CONTRACT_VERSION_UNKNOWN_PREDECESSOR")
                if record.predecessor_version == record.version:
                    raise ValueError("CONTRACT_VERSION_SELF_PREDECESSOR")
            if record.superseded_by_version is not None:
                successor_key = (*base, record.superseded_by_version)
                successor = by_key.get(successor_key)
                if successor is None:
                    raise ValueError("CONTRACT_VERSION_UNKNOWN_SUCCESSOR")
                if successor.version == record.version:
                    raise ValueError("CONTRACT_VERSION_SELF_SUCCESSOR")

    def get_record(
        self,
        producer_project_id: str,
        contract_id: str,
        version: str,
    ) -> ContractVersionRecordV1:
        for record in self.records:
            if (
                record.producer_project_id == producer_project_id
                and record.contract_id == contract_id
                and record.version == version
            ):
                return record
        raise GovernanceError("CONTRACT_VERSION_NOT_FOUND")

    def binding_for_edge(self, edge_id: str) -> ConsumedContractBindingV1:
        for binding in self.consumer_bindings:
            if binding.edge_id == edge_id:
                return binding
        raise GovernanceError("CONTRACT_VERSION_EDGE_BINDING_NOT_FOUND")

    def require_consumable(self, edge_id: str) -> ContractVersionRecordV1:
        binding = self.binding_for_edge(edge_id)
        record = self.get_record(
            binding.producer_project_id,
            binding.contract_id,
            binding.version,
        )
        if record.lifecycle == ContractLifecycle.retired:
            raise GovernanceError("CONTRACT_VERSION_RETIRED_NOT_CONSUMABLE")
        return record

    def requires_revalidation(self, edge_id: str) -> bool:
        record = self.require_consumable(edge_id)
        return record.compatibility_with_predecessor == CompatibilityClass.breaking


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _registry_payload(
    *,
    source_revision: str,
    authority_reference: str,
    dependency_graph_sha256: str,
    records: tuple[ContractVersionRecordV1, ...],
    consumer_bindings: tuple[ConsumedContractBindingV1, ...],
) -> dict[str, object]:
    return {
        "registry_id": "PALWAKF_CONTRACT_VERSION_REGISTRY_V1",
        "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "dependency_graph_sha256": dependency_graph_sha256,
        "records": [item.model_dump(mode="json") for item in records],
        "consumer_bindings": [item.model_dump(mode="json") for item in consumer_bindings],
        "canonical_promotion_allowed": False,
    }


def build_contract_version_registry(
    *,
    graph: TypedDependencyGraphV1,
    source_revision: str,
    authority_reference: str,
    records: tuple[ContractVersionRecordV1, ...],
    consumer_bindings: tuple[ConsumedContractBindingV1, ...],
    imported_at: datetime | None = None,
) -> ContractVersionRegistryV1:
    payload = _registry_payload(
        source_revision=source_revision,
        authority_reference=authority_reference,
        dependency_graph_sha256=graph.graph_sha256,
        records=records,
        consumer_bindings=consumer_bindings,
    )
    registry = ContractVersionRegistryV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        dependency_graph_sha256=graph.graph_sha256,
        records=records,
        consumer_bindings=consumer_bindings,
        imported_at=imported_at or datetime.now(UTC),
        registry_sha256=_sha256(payload),
    )
    _validate_registry_against_graph(registry, graph)
    return registry


def _validate_registry_against_graph(
    registry: ContractVersionRegistryV1,
    graph: TypedDependencyGraphV1,
) -> None:
    if registry.dependency_graph_sha256 != graph.graph_sha256:
        raise GovernanceError("CONTRACT_VERSION_GRAPH_SHA_MISMATCH")
    project_ids = set(graph.project_ids)
    if any(record.producer_project_id not in project_ids for record in registry.records):
        raise GovernanceError("CONTRACT_VERSION_UNKNOWN_PRODUCER_PROJECT")

    edges = {edge.edge_id: edge for edge in graph.edges}
    bindings = {binding.edge_id: binding for binding in registry.consumer_bindings}
    for edge_id, binding in bindings.items():
        edge = edges.get(edge_id)
        if edge is None:
            raise GovernanceError("CONTRACT_VERSION_BINDING_UNKNOWN_EDGE")
        if (
            binding.contract_id != edge.contract_id
            or binding.version != edge.version
            or binding.producer_project_id != edge.producer_project_id
            or binding.consumer_project_id != edge.consumer_project_id
        ):
            raise GovernanceError("CONTRACT_VERSION_BINDING_EDGE_MISMATCH")
        registry.get_record(binding.producer_project_id, binding.contract_id, binding.version)

    for edge in graph.edges:
        if edge.status != DependencyEdgeStatus.active:
            continue
        active_binding = bindings.get(edge.edge_id)
        if active_binding is None:
            raise GovernanceError("CONTRACT_VERSION_ACTIVE_EDGE_BINDING_REQUIRED")
        record = registry.get_record(edge.producer_project_id, edge.contract_id, edge.version)
        if record.lifecycle == ContractLifecycle.retired:
            raise GovernanceError("CONTRACT_VERSION_ACTIVE_EDGE_RETIRED")


def _expected_registry_sha256(registry: ContractVersionRegistryV1) -> str:
    return _sha256(
        _registry_payload(
            source_revision=registry.source_revision,
            authority_reference=registry.authority_reference,
            dependency_graph_sha256=registry.dependency_graph_sha256,
            records=registry.records,
            consumer_bindings=registry.consumer_bindings,
        )
    )


class ContractVersionRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def current(self) -> ContractVersionRegistryV1:
        history = self.history()
        if not history:
            raise GovernanceError("CONTRACT_VERSION_REGISTRY_NOT_IMPORTED")
        return history[-1]

    def history(self) -> tuple[ContractVersionRegistryV1, ...]:
        state = self._state_store.load()
        raw = state.get(REGISTRY_STATE_KEY, {})
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else []
        parsed: list[ContractVersionRegistryV1] = []
        for item in snapshots:
            registry = ContractVersionRegistryV1.model_validate(item)
            if registry.registry_sha256 != _expected_registry_sha256(registry):
                raise GovernanceError("CONTRACT_VERSION_REGISTRY_HASH_MISMATCH")
            parsed.append(registry)
        return tuple(parsed)

    def import_registry(
        self,
        *,
        graph: TypedDependencyGraphV1,
        source_revision: str,
        authority_reference: str,
        records: tuple[ContractVersionRecordV1, ...],
        consumer_bindings: tuple[ConsumedContractBindingV1, ...],
    ) -> ContractVersionRegistryV1:
        registry = build_contract_version_registry(
            graph=graph,
            source_revision=source_revision,
            authority_reference=authority_reference,
            records=records,
            consumer_bindings=consumer_bindings,
            imported_at=self._now(),
        )
        history = list(self.history())
        for existing in history:
            if existing.source_revision != source_revision:
                continue
            if existing.registry_sha256 != registry.registry_sha256:
                raise GovernanceError("CONTRACT_VERSION_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(registry)
        state = self._state_store.load()
        state[REGISTRY_STATE_KEY] = {
            "registry_version": "PALWAKF_CONTRACT_VERSION_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_PROJECTION_ONLY",
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return registry
