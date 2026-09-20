from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import (
    MaterialChangeEventRegistryV1,
    MaterialChangeEventType,
    MaterialChangeEventV1,
)
from palwakf_orchestrator.persistence import StateStore

INBOX_STATE_KEY = "pre_l5_project_change_inbox_v1"


class ProjectChangeInboxStatus(StrEnum):
    open = "OPEN"
    acknowledged = "ACKNOWLEDGED"
    revalidation_required = "REVALIDATION_REQUIRED"
    deferred = "DEFERRED"
    resolved = "RESOLVED"


_UNRESOLVED_STATUSES = {
    ProjectChangeInboxStatus.open,
    ProjectChangeInboxStatus.acknowledged,
    ProjectChangeInboxStatus.revalidation_required,
    ProjectChangeInboxStatus.deferred,
}


class ProjectChangeInboxItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    inbox_item_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str = Field(min_length=3, max_length=128)
    event_id: str = Field(min_length=1, max_length=200)
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    change_id: str = Field(min_length=1, max_length=200)
    source_project_id: str = Field(min_length=3, max_length=128)
    event_type: MaterialChangeEventType
    status: ProjectChangeInboxStatus = ProjectChangeInboxStatus.open
    authority_reference: str = Field(min_length=1, max_length=500)
    source_revision: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)
    dependency_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    updated_at: datetime
    resolution_reference: str | None = Field(default=None, max_length=500)
    lifecycle_evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_item(self) -> Self:
        if self.project_id == self.source_project_id:
            raise ValueError("PROJECT_CHANGE_INBOX_SOURCE_PROJECT_CANNOT_RECEIVE_INBOUND_ITEM")
        if any(not item.strip() for item in self.evidence):
            raise ValueError("PROJECT_CHANGE_INBOX_EVENT_EVIDENCE_REQUIRED")
        if any(not item.strip() for item in self.lifecycle_evidence):
            raise ValueError("PROJECT_CHANGE_INBOX_LIFECYCLE_EVIDENCE_REQUIRED")
        if self.status == ProjectChangeInboxStatus.resolved and not self.resolution_reference:
            raise ValueError("PROJECT_CHANGE_INBOX_RESOLUTION_REFERENCE_REQUIRED")
        return self


class ProjectChangeInboxSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: Literal["PALWAKF_PROJECT_CHANGE_INBOX_V1"] = "PALWAKF_PROJECT_CHANGE_INBOX_V1"
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    runtime_role: Literal["GOVERNED_DURABLE_CHANGE_PROJECTION"] = (
        "GOVERNED_DURABLE_CHANGE_PROJECTION"
    )
    items: tuple[ProjectChangeInboxItemV1, ...] = ()
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        ids = [item.inbox_item_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("PROJECT_CHANGE_INBOX_DUPLICATE_ITEM_ID")
        event_project = [(item.event_id, item.project_id) for item in self.items]
        if len(set(event_project)) != len(event_project):
            raise ValueError("PROJECT_CHANGE_INBOX_DUPLICATE_EVENT_PROJECT")
        return self

    def unresolved_for_project(self, project_id: str) -> tuple[ProjectChangeInboxItemV1, ...]:
        return tuple(
            item
            for item in self.items
            if item.project_id == project_id and item.status in _UNRESOLVED_STATUSES
        )

    def all_for_project(self, project_id: str) -> tuple[ProjectChangeInboxItemV1, ...]:
        return tuple(item for item in self.items if item.project_id == project_id)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _item_id(project_id: str, event_id: str) -> str:
    return hashlib.sha256(f"{project_id}:{event_id}".encode()).hexdigest()


def _build_item(event: MaterialChangeEventV1, project_id: str) -> ProjectChangeInboxItemV1:
    return ProjectChangeInboxItemV1(
        inbox_item_id=_item_id(project_id, event.event_id),
        project_id=project_id,
        event_id=event.event_id,
        event_sha256=event.event_sha256,
        change_id=event.change_id,
        source_project_id=event.project_id,
        event_type=event.event_type,
        authority_reference=event.authority_reference,
        source_revision=event.source_revision,
        evidence=event.evidence,
        dependency_graph_sha256=event.dependency_graph_sha256,
        contract_registry_sha256=event.contract_registry_sha256,
        created_at=event.occurred_at,
        updated_at=event.occurred_at,
    )


_ALLOWED_TRANSITIONS: dict[ProjectChangeInboxStatus, set[ProjectChangeInboxStatus]] = {
    ProjectChangeInboxStatus.open: {
        ProjectChangeInboxStatus.acknowledged,
        ProjectChangeInboxStatus.revalidation_required,
        ProjectChangeInboxStatus.deferred,
        ProjectChangeInboxStatus.resolved,
    },
    ProjectChangeInboxStatus.acknowledged: {
        ProjectChangeInboxStatus.revalidation_required,
        ProjectChangeInboxStatus.deferred,
        ProjectChangeInboxStatus.resolved,
    },
    ProjectChangeInboxStatus.revalidation_required: {
        ProjectChangeInboxStatus.deferred,
        ProjectChangeInboxStatus.resolved,
    },
    ProjectChangeInboxStatus.deferred: {
        ProjectChangeInboxStatus.acknowledged,
        ProjectChangeInboxStatus.revalidation_required,
        ProjectChangeInboxStatus.resolved,
    },
    ProjectChangeInboxStatus.resolved: set(),
}


class ProjectChangeInboxStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def snapshot(self) -> ProjectChangeInboxSnapshotV1:
        state = self._state_store.load()
        raw = state.get(INBOX_STATE_KEY, {})
        items_raw = raw.get("items", []) if isinstance(raw, dict) else []
        if isinstance(raw, dict) and items_raw:
            expected = raw.get("items_sha256")
            if expected != _sha256(items_raw):
                raise GovernanceError("PROJECT_CHANGE_INBOX_HASH_MISMATCH")
        items = tuple(ProjectChangeInboxItemV1.model_validate(item) for item in items_raw)
        return ProjectChangeInboxSnapshotV1(items=items)

    def sync_registry(
        self,
        registry: MaterialChangeEventRegistryV1,
    ) -> ProjectChangeInboxSnapshotV1:
        for event in registry.events:
            self.ingest_event(event)
        return self.snapshot()

    def ingest_event(self, event: MaterialChangeEventV1) -> tuple[ProjectChangeInboxItemV1, ...]:
        current = list(self.snapshot().items)
        created: list[ProjectChangeInboxItemV1] = []
        by_key = {(item.event_id, item.project_id): item for item in current}
        for project_id in event.affected_project_ids:
            if project_id == event.project_id:
                continue
            key = (event.event_id, project_id)
            existing = by_key.get(key)
            if existing is not None:
                if existing.event_sha256 != event.event_sha256:
                    raise GovernanceError("PROJECT_CHANGE_INBOX_EVENT_REPLAY_CONFLICT")
                created.append(existing)
                continue
            item = _build_item(event, project_id)
            current.append(item)
            by_key[key] = item
            created.append(item)
        self._persist(tuple(current))
        return tuple(created)

    def transition(
        self,
        inbox_item_id: str,
        *,
        project_id: str,
        expected_status: ProjectChangeInboxStatus,
        new_status: ProjectChangeInboxStatus,
        lifecycle_evidence: tuple[str, ...],
        resolution_reference: str | None = None,
    ) -> ProjectChangeInboxItemV1:
        snapshot = self.snapshot()
        current = next(
            (item for item in snapshot.items if item.inbox_item_id == inbox_item_id), None
        )
        if current is None:
            raise GovernanceError("PROJECT_CHANGE_INBOX_ITEM_NOT_FOUND")
        if current.project_id != project_id:
            raise GovernanceError("PROJECT_CHANGE_INBOX_PROJECT_MISMATCH")
        if current.status != expected_status:
            raise GovernanceError("PROJECT_CHANGE_INBOX_STALE_STATUS")
        if new_status not in _ALLOWED_TRANSITIONS[current.status]:
            raise GovernanceError("PROJECT_CHANGE_INBOX_INVALID_TRANSITION")
        if not lifecycle_evidence or any(not item.strip() for item in lifecycle_evidence):
            raise GovernanceError("PROJECT_CHANGE_INBOX_LIFECYCLE_EVIDENCE_REQUIRED")
        if new_status == ProjectChangeInboxStatus.resolved and not resolution_reference:
            raise GovernanceError("PROJECT_CHANGE_INBOX_RESOLUTION_REFERENCE_REQUIRED")

        updated = current.model_copy(
            update={
                "status": new_status,
                "updated_at": self._now(),
                "resolution_reference": resolution_reference,
                "lifecycle_evidence": tuple(
                    dict.fromkeys((*current.lifecycle_evidence, *lifecycle_evidence))
                ),
            }
        )
        items = tuple(
            updated if item.inbox_item_id == inbox_item_id else item for item in snapshot.items
        )
        self._persist(items)
        return updated

    def unresolved_for_project(self, project_id: str) -> tuple[ProjectChangeInboxItemV1, ...]:
        return self.snapshot().unresolved_for_project(project_id)

    def resume_visibility(self, project_id: str) -> tuple[ProjectChangeInboxItemV1, ...]:
        return self.unresolved_for_project(project_id)

    def get(self, inbox_item_id: str, *, project_id: str) -> ProjectChangeInboxItemV1:
        for item in self.snapshot().items:
            if item.inbox_item_id != inbox_item_id:
                continue
            if item.project_id != project_id:
                raise GovernanceError("PROJECT_CHANGE_INBOX_PROJECT_MISMATCH")
            return item
        raise GovernanceError("PROJECT_CHANGE_INBOX_ITEM_NOT_FOUND")

    def _persist(self, items: tuple[ProjectChangeInboxItemV1, ...]) -> None:
        state = self._state_store.load()
        payload = [item.model_dump(mode="json") for item in items]
        state[INBOX_STATE_KEY] = {
            "registry_version": "PALWAKF_PROJECT_CHANGE_INBOX_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_DURABLE_CHANGE_PROJECTION",
            "canonical_promotion_allowed": False,
            "items_sha256": _sha256(payload),
            "items": payload,
        }
        self._state_store.save(state)
