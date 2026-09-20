from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.engineering_os_contracts import EngineeringTaskRecord
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

SCOPE_LEASE_STATE_KEY = "pre_l5_scope_leases_v1"
MERGE_QUEUE_STATE_KEY = "pre_l5_merge_queue_v1"
IntegrationHeadResolver = Callable[[str], str]
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class ScopeLeaseStatus(StrEnum):
    active = "ACTIVE"
    released = "RELEASED"


class MergeQueueStatus(StrEnum):
    queued = "QUEUED"
    ready = "READY"
    reconciliation_required = "RECONCILIATION_REQUIRED"
    integrated = "INTEGRATED"


class ScopeLeaseRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lease_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=3, max_length=128)
    project_id: str = Field(min_length=2, max_length=128)
    repository: str = Field(min_length=3, max_length=240)
    scope_patterns: tuple[str, ...] = Field(min_length=1, max_length=64)
    execution_host_id: str = Field(min_length=3, max_length=128)
    status: ScopeLeaseStatus = ScopeLeaseStatus.active
    acquired_at: datetime
    released_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if any(not item.strip() for item in self.scope_patterns):
            raise ValueError("SCOPE_LEASE_EMPTY_PATTERN")
        if len(set(self.scope_patterns)) != len(self.scope_patterns):
            raise ValueError("SCOPE_LEASE_DUPLICATE_PATTERN")
        if self.status == ScopeLeaseStatus.released and self.released_at is None:
            raise ValueError("SCOPE_LEASE_RELEASE_TIMESTAMP_REQUIRED")
        return self


class MergeQueueEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=3, max_length=128)
    project_id: str = Field(min_length=2, max_length=128)
    repository: str = Field(min_length=3, max_length=240)
    task_branch: str = Field(min_length=3, max_length=200)
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    expected_integration_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    scope_patterns: tuple[str, ...] = Field(min_length=1, max_length=64)
    status: MergeQueueStatus = MergeQueueStatus.queued
    enqueued_at: datetime
    updated_at: datetime
    integrated_head: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_integrated_state(self) -> Self:
        if self.status == MergeQueueStatus.integrated and self.integrated_head is None:
            raise ValueError("MERGE_QUEUE_INTEGRATED_HEAD_REQUIRED")
        return self


def _normalized_pattern(pattern: str) -> str:
    return pattern.replace("\\", "/").strip().lstrip("./")


def _static_prefix(pattern: str) -> str:
    normalized = _normalized_pattern(pattern)
    positions = [normalized.find(token) for token in ("*", "?", "[")]
    positions = [value for value in positions if value >= 0]
    if positions:
        normalized = normalized[: min(positions)]
    return normalized.rstrip("/")


def _prefix_overlaps(left: str, right: str) -> bool:
    if not left or not right:
        return True
    if left == right:
        return True
    return left.startswith(right + "/") or right.startswith(left + "/")


def scopes_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return any(_prefix_overlaps(_static_prefix(a), _static_prefix(b)) for a in left for b in right)


def _normalized_sha(value: str, error: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise GovernanceError(error)
    return value.lower()


class ParallelDevelopmentCoordinator:
    def __init__(
        self,
        state_store: StateStore,
        *,
        integration_head_resolver: IntegrationHeadResolver,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._integration_head_resolver = integration_head_resolver
        self._now = now or (lambda: datetime.now(UTC))

    def list_scope_leases(self) -> tuple[ScopeLeaseRecordV1, ...]:
        state = self._state_store.load()
        raw = state.get(SCOPE_LEASE_STATE_KEY, {})
        values = raw.get("leases", []) if isinstance(raw, dict) else []
        return tuple(ScopeLeaseRecordV1.model_validate(item) for item in values)

    def list_merge_queue(self) -> tuple[MergeQueueEntryV1, ...]:
        state = self._state_store.load()
        raw = state.get(MERGE_QUEUE_STATE_KEY, {})
        values = raw.get("entries", []) if isinstance(raw, dict) else []
        entries = (MergeQueueEntryV1.model_validate(item) for item in values)
        return tuple(sorted(entries, key=lambda item: (item.enqueued_at, item.entry_id)))

    def acquire_scope_lease(
        self,
        task: EngineeringTaskRecord,
        *,
        execution_host_id: str,
    ) -> ScopeLeaseRecordV1:
        scopes = tuple(task.scope_patterns)
        active = [
            item for item in self.list_scope_leases() if item.status == ScopeLeaseStatus.active
        ]
        for existing in active:
            if existing.task_id == task.task_id:
                if (
                    existing.repository == task.repository
                    and existing.scope_patterns == scopes
                    and existing.execution_host_id == execution_host_id
                ):
                    return existing
                raise GovernanceError("SCOPE_LEASE_TASK_BINDING_CONFLICT")
            if existing.repository == task.repository and scopes_overlap(
                existing.scope_patterns, scopes
            ):
                raise GovernanceError("SCOPE_LEASE_CONFLICT")

        generation = 1 + sum(1 for item in self.list_scope_leases() if item.task_id == task.task_id)
        lease = ScopeLeaseRecordV1(
            lease_id=f"scope-lease:{task.task_id}:{generation}",
            task_id=task.task_id,
            project_id=task.project_id,
            repository=task.repository,
            scope_patterns=scopes,
            execution_host_id=execution_host_id,
            acquired_at=self._now(),
        )
        self._save_scope_lease(lease)
        return lease

    def release_scope_lease(self, task_id: str) -> ScopeLeaseRecordV1:
        leases = list(self.list_scope_leases())
        for index, item in enumerate(leases):
            if item.task_id != task_id or item.status != ScopeLeaseStatus.active:
                continue
            released = item.model_copy(
                update={
                    "status": ScopeLeaseStatus.released,
                    "released_at": self._now(),
                }
            )
            leases[index] = released
            self._persist_scope_leases(tuple(leases))
            return released
        raise GovernanceError("SCOPE_LEASE_ACTIVE_NOT_FOUND")

    def enqueue(self, task: EngineeringTaskRecord) -> MergeQueueEntryV1:
        if task.latest_remote_task_sha is None:
            raise GovernanceError("MERGE_QUEUE_REMOTE_CHECKPOINT_REQUIRED")
        current_head = _normalized_sha(
            self._integration_head_resolver(task.repository),
            "MERGE_QUEUE_INTEGRATION_HEAD_INVALID",
        )
        expected_head = task.integrated_head_at_creation.lower()
        status = (
            MergeQueueStatus.queued
            if current_head == expected_head
            else MergeQueueStatus.reconciliation_required
        )
        now = self._now()
        entry = MergeQueueEntryV1(
            entry_id=f"merge-queue:{task.task_id}",
            task_id=task.task_id,
            project_id=task.project_id,
            repository=task.repository,
            task_branch=task.task_branch,
            candidate_sha=task.latest_remote_task_sha.lower(),
            expected_integration_head=expected_head,
            scope_patterns=tuple(task.scope_patterns),
            status=status,
            enqueued_at=now,
            updated_at=now,
            evidence=(f"integration-head-observed:{current_head}",),
        )
        entries = list(self.list_merge_queue())
        for existing in entries:
            if existing.task_id != task.task_id:
                continue
            if existing == entry:
                return existing
            if existing.status != MergeQueueStatus.integrated:
                raise GovernanceError("MERGE_QUEUE_TASK_ALREADY_ENQUEUED")
        entries.append(entry)
        self._persist_merge_queue(tuple(entries))
        return entry

    def require_ready_for_merge(self, entry_id: str) -> MergeQueueEntryV1:
        entries = list(self.list_merge_queue())
        index, entry = self._find_queue_entry(entries, entry_id)
        current_head = _normalized_sha(
            self._integration_head_resolver(entry.repository),
            "MERGE_QUEUE_INTEGRATION_HEAD_INVALID",
        )
        if entry.status == MergeQueueStatus.integrated:
            raise GovernanceError("MERGE_QUEUE_ENTRY_ALREADY_INTEGRATED")
        if current_head != entry.expected_integration_head:
            updated = entry.model_copy(
                update={
                    "status": MergeQueueStatus.reconciliation_required,
                    "updated_at": self._now(),
                    "evidence": (*entry.evidence, f"integration-head-drift:{current_head}"),
                }
            )
            entries[index] = updated
            self._persist_merge_queue(tuple(entries))
            raise GovernanceError("MERGE_QUEUE_INTEGRATION_HEAD_DRIFT")

        for earlier in entries[:index]:
            if (
                earlier.repository == entry.repository
                and earlier.status != MergeQueueStatus.integrated
            ):
                raise GovernanceError("MERGE_QUEUE_NOT_AT_FRONT")
        ready = entry.model_copy(
            update={
                "status": MergeQueueStatus.ready,
                "updated_at": self._now(),
                "evidence": (*entry.evidence, f"integration-head-revalidated:{current_head}"),
            }
        )
        entries[index] = ready
        self._persist_merge_queue(tuple(entries))
        return ready

    def mark_integrated(
        self,
        entry_id: str,
        *,
        integrated_head: str,
        authority_reference: str,
        evidence: tuple[str, ...],
    ) -> MergeQueueEntryV1:
        if not authority_reference.strip():
            raise GovernanceError("MERGE_QUEUE_AUTHORITY_REFERENCE_REQUIRED")
        if not evidence or any(not item.strip() for item in evidence):
            raise GovernanceError("MERGE_QUEUE_INTEGRATION_EVIDENCE_REQUIRED")
        entries = list(self.list_merge_queue())
        index, entry = self._find_queue_entry(entries, entry_id)
        if entry.status != MergeQueueStatus.ready:
            raise GovernanceError("MERGE_QUEUE_ENTRY_NOT_READY")
        normalized_integrated_head = _normalized_sha(
            integrated_head, "MERGE_QUEUE_INTEGRATED_HEAD_INVALID"
        )
        observed_head = _normalized_sha(
            self._integration_head_resolver(entry.repository),
            "MERGE_QUEUE_INTEGRATION_HEAD_INVALID",
        )
        if observed_head != normalized_integrated_head:
            raise GovernanceError("MERGE_QUEUE_POST_INTEGRATION_HEAD_MISMATCH")
        integrated = entry.model_copy(
            update={
                "status": MergeQueueStatus.integrated,
                "integrated_head": normalized_integrated_head,
                "updated_at": self._now(),
                "evidence": (*entry.evidence, f"authority:{authority_reference}", *evidence),
            }
        )
        entries[index] = integrated
        self._persist_merge_queue(tuple(entries))
        return integrated

    @staticmethod
    def _find_queue_entry(
        entries: list[MergeQueueEntryV1],
        entry_id: str,
    ) -> tuple[int, MergeQueueEntryV1]:
        for index, item in enumerate(entries):
            if item.entry_id == entry_id:
                return index, item
        raise GovernanceError("MERGE_QUEUE_ENTRY_NOT_FOUND")

    def _save_scope_lease(self, lease: ScopeLeaseRecordV1) -> None:
        leases = list(self.list_scope_leases())
        leases.append(lease)
        self._persist_scope_leases(tuple(leases))

    def _persist_scope_leases(self, leases: tuple[ScopeLeaseRecordV1, ...]) -> None:
        state = self._state_store.load()
        state[SCOPE_LEASE_STATE_KEY] = {
            "version": "PALWAKF_SCOPE_LEASE_REGISTRY_V1",
            "leases": [item.model_dump(mode="json") for item in leases],
        }
        self._state_store.save(state)

    def _persist_merge_queue(self, entries: tuple[MergeQueueEntryV1, ...]) -> None:
        state = self._state_store.load()
        state[MERGE_QUEUE_STATE_KEY] = {
            "version": "PALWAKF_MERGE_QUEUE_V1",
            "entries": [item.model_dump(mode="json") for item in entries],
        }
        self._state_store.save(state)
