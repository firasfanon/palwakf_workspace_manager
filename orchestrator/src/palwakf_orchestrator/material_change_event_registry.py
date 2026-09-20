from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.contract_version_registry import ContractVersionRegistryV1
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.typed_dependency_graph import TypedDependencyGraphV1

REGISTRY_STATE_KEY = "pre_l5_material_change_event_registry_v1"


class MaterialChangeEventType(StrEnum):
    dependency_changed = "DEPENDENCY_CHANGED"
    contract_version_published = "CONTRACT_VERSION_PUBLISHED"
    contract_version_deprecated = "CONTRACT_VERSION_DEPRECATED"
    contract_version_retired = "CONTRACT_VERSION_RETIRED"
    project_boundary_changed = "PROJECT_BOUNDARY_CHANGED"
    runtime_contract_changed = "RUNTIME_CONTRACT_CHANGED"


class AcceptedMaterialChangeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1, max_length=200)
    acceptance_status: Literal["ACCEPTED"] = "ACCEPTED"
    authority_reference: str = Field(min_length=1, max_length=500)
    accepted_at: datetime
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("MATERIAL_CHANGE_ACCEPTANCE_EVIDENCE_REQUIRED")
        return self


class MaterialChangeEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1, max_length=200)
    event_type: MaterialChangeEventType
    change_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=3, max_length=128)
    affected_project_ids: tuple[str, ...] = Field(min_length=1)
    occurred_at: datetime
    authority_reference: str = Field(min_length=1, max_length=500)
    source_revision: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)
    dependency_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edge_id: str | None = Field(default=None, max_length=200)
    contract_id: str | None = Field(default=None, max_length=200)
    contract_version: str | None = Field(default=None, max_length=100)
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("MATERIAL_CHANGE_EVENT_EVIDENCE_REQUIRED")
        if len(set(self.affected_project_ids)) != len(self.affected_project_ids):
            raise ValueError("MATERIAL_CHANGE_EVENT_DUPLICATE_AFFECTED_PROJECT")
        if self.event_type == MaterialChangeEventType.dependency_changed and not self.edge_id:
            raise ValueError("MATERIAL_CHANGE_DEPENDENCY_EDGE_REQUIRED")
        contract_types = {
            MaterialChangeEventType.contract_version_published,
            MaterialChangeEventType.contract_version_deprecated,
            MaterialChangeEventType.contract_version_retired,
        }
        if self.event_type in contract_types and (
            not self.contract_id or not self.contract_version
        ):
            raise ValueError("MATERIAL_CHANGE_CONTRACT_REFERENCE_REQUIRED")
        return self


class MaterialChangeEventRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_MATERIAL_CHANGE_EVENT_REGISTRY_V1"] = (
        "PALWAKF_MATERIAL_CHANGE_EVENT_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    runtime_role: Literal["GOVERNED_APPEND_ONLY_EVENT_PROJECTION"] = (
        "GOVERNED_APPEND_ONLY_EVENT_PROJECTION"
    )
    events: tuple[MaterialChangeEventV1, ...] = ()
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        event_ids = [event.event_id for event in self.events]
        change_ids = [event.change_id for event in self.events]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("MATERIAL_CHANGE_DUPLICATE_EVENT_ID")
        if len(set(change_ids)) != len(change_ids):
            raise ValueError("MATERIAL_CHANGE_DUPLICATE_CHANGE_ID")
        return self

    def get(self, event_id: str) -> MaterialChangeEventV1:
        for event in self.events:
            if event.event_id == event_id:
                return event
        raise GovernanceError("MATERIAL_CHANGE_EVENT_NOT_FOUND")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _event_payload(event: MaterialChangeEventV1 | dict[str, object]) -> dict[str, object]:
    if isinstance(event, MaterialChangeEventV1):
        payload = event.model_dump(mode="json")
    else:
        payload = dict(event)
    payload.pop("event_sha256", None)
    return payload


def build_material_change_event(
    *,
    event_id: str,
    event_type: MaterialChangeEventType,
    acceptance: AcceptedMaterialChangeV1,
    project_id: str,
    affected_project_ids: tuple[str, ...],
    graph: TypedDependencyGraphV1,
    contract_registry: ContractVersionRegistryV1,
    source_revision: str,
    evidence: tuple[str, ...],
    edge_id: str | None = None,
    contract_id: str | None = None,
    contract_version: str | None = None,
    occurred_at: datetime | None = None,
) -> MaterialChangeEventV1:
    projects = set(graph.project_ids)
    if project_id not in projects or any(item not in projects for item in affected_project_ids):
        raise GovernanceError("MATERIAL_CHANGE_PROJECT_BINDING_MISMATCH")
    if contract_registry.dependency_graph_sha256 != graph.graph_sha256:
        raise GovernanceError("MATERIAL_CHANGE_STALE_CONTRACT_REGISTRY_GRAPH")
    if edge_id is not None and edge_id not in {edge.edge_id for edge in graph.edges}:
        raise GovernanceError("MATERIAL_CHANGE_UNKNOWN_DEPENDENCY_EDGE")
    if contract_id is not None and contract_version is not None:
        contract_registry.get_record(project_id, contract_id, contract_version)
    if event_type == MaterialChangeEventType.dependency_changed:
        edge = next(edge for edge in graph.edges if edge.edge_id == edge_id)
        if project_id != edge.producer_project_id:
            raise GovernanceError("MATERIAL_CHANGE_DEPENDENCY_PRODUCER_MISMATCH")
        if edge.consumer_project_id not in affected_project_ids:
            raise GovernanceError("MATERIAL_CHANGE_DEPENDENCY_CONSUMER_NOT_AFFECTED")

    event_time = occurred_at or datetime.now(UTC)
    if event_time < acceptance.accepted_at:
        raise GovernanceError("MATERIAL_CHANGE_EVENT_BEFORE_ACCEPTANCE")
    combined_evidence = tuple(dict.fromkeys((*acceptance.evidence, *evidence)))
    payload: dict[str, object] = {
        "event_id": event_id,
        "event_type": event_type.value,
        "change_id": acceptance.change_id,
        "project_id": project_id,
        "affected_project_ids": affected_project_ids,
        "occurred_at": event_time.isoformat().replace("+00:00", "Z"),
        "authority_reference": acceptance.authority_reference,
        "source_revision": source_revision,
        "evidence": combined_evidence,
        "dependency_graph_sha256": graph.graph_sha256,
        "contract_registry_sha256": contract_registry.registry_sha256,
        "edge_id": edge_id,
        "contract_id": contract_id,
        "contract_version": contract_version,
    }
    return MaterialChangeEventV1.model_validate({**payload, "event_sha256": _sha256(payload)})


class MaterialChangeEventRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def registry(self) -> MaterialChangeEventRegistryV1:
        state = self._state_store.load()
        raw = state.get(REGISTRY_STATE_KEY, {})
        events_raw = raw.get("events", []) if isinstance(raw, dict) else []
        events: list[MaterialChangeEventV1] = []
        for item in events_raw:
            event = MaterialChangeEventV1.model_validate(item)
            if event.event_sha256 != _sha256(_event_payload(event)):
                raise GovernanceError("MATERIAL_CHANGE_EVENT_HASH_MISMATCH")
            events.append(event)
        return MaterialChangeEventRegistryV1(events=tuple(events))

    def register_accepted_change(
        self,
        *,
        event_id: str,
        event_type: MaterialChangeEventType,
        acceptance: AcceptedMaterialChangeV1,
        project_id: str,
        affected_project_ids: tuple[str, ...],
        graph: TypedDependencyGraphV1,
        contract_registry: ContractVersionRegistryV1,
        source_revision: str,
        evidence: tuple[str, ...] = (),
        edge_id: str | None = None,
        contract_id: str | None = None,
        contract_version: str | None = None,
    ) -> MaterialChangeEventV1:
        event = build_material_change_event(
            event_id=event_id,
            event_type=event_type,
            acceptance=acceptance,
            project_id=project_id,
            affected_project_ids=affected_project_ids,
            graph=graph,
            contract_registry=contract_registry,
            source_revision=source_revision,
            evidence=evidence,
            edge_id=edge_id,
            contract_id=contract_id,
            contract_version=contract_version,
            occurred_at=self._now(),
        )
        registry = self.registry()
        for existing in registry.events:
            if existing.event_id == event.event_id or existing.change_id == event.change_id:
                if existing.event_sha256 != event.event_sha256:
                    raise GovernanceError("MATERIAL_CHANGE_EVENT_IDEMPOTENCY_CONFLICT")
                return existing

        updated = MaterialChangeEventRegistryV1(events=(*registry.events, event))
        state = self._state_store.load()
        state[REGISTRY_STATE_KEY] = {
            "registry_version": "PALWAKF_MATERIAL_CHANGE_EVENT_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_APPEND_ONLY_EVENT_PROJECTION",
            "canonical_promotion_allowed": False,
            "events": [item.model_dump(mode="json") for item in updated.events],
        }
        self._state_store.save(state)
        return event
