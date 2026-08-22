from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from palwakf_orchestrator.engineering_os_contracts import EngineeringTaskRecord
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord, TaskEvent


class ExecutionRunLike(Protocol):
    execution_run_id: str
    legacy_operator_task_id: str
    parent_engineering_task_id: str
    operator_task: OperatorTaskRecord


class CanonicalRecordSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: str
    canonical_json: str
    sha256: str


class AuthorityLineageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    repository: str
    task_branch: str
    run_branch: str
    task_mutation_class: str
    run_sandbox: str
    authority_reference: str


class HeadLineageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_base_sha: str
    task_integrated_head_at_creation: str
    task_latest_remote_task_sha: str | None
    run_expected_head: str
    run_before_head: str | None
    run_after_head: str | None


class GoalExecutionSemanticSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_description: str
    run_prompt: str
    task_scope_patterns: tuple[str, ...]
    run_constraints: tuple[str, ...]
    task_required_tests: tuple[str, ...]
    run_actual_tests: tuple[str, ...]


class EvidenceLineageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_evidence: tuple[str, ...]
    run_evidence: tuple[str, ...]
    changed_files: tuple[str, ...]
    execution_receipt: str | None
    verification_receipt: str | None


class TimingLineageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_created_at: datetime
    task_updated_at: datetime
    run_created_at: datetime
    run_updated_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    dispatch_latency_ms: int | None
    executor_duration_ms: int | None
    verification_duration_ms: int | None


class EventLineageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    status: str
    message: str
    occurred_at: datetime
    correlation_id: str | None
    client_id: str | None


class SemanticLineageProjection(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_engineering_task_id: str
    execution_run_id: str
    legacy_operator_task_id: str
    engineering_record: CanonicalRecordSnapshot
    operator_record: CanonicalRecordSnapshot
    authority: AuthorityLineageSnapshot
    heads: HeadLineageSnapshot
    semantics: GoalExecutionSemanticSnapshot
    evidence: EvidenceLineageSnapshot
    timings: TimingLineageSnapshot
    events: tuple[EventLineageSnapshot, ...]


def build_semantic_lineage_projection(
    parent: EngineeringTaskRecord,
    run: ExecutionRunLike,
) -> SemanticLineageProjection:
    operator = run.operator_task
    _assert_identity(parent, run, operator)

    return SemanticLineageProjection(
        parent_engineering_task_id=parent.task_id,
        execution_run_id=run.execution_run_id,
        legacy_operator_task_id=run.legacy_operator_task_id,
        engineering_record=_canonical_record_snapshot("EngineeringTaskRecord", parent),
        operator_record=_canonical_record_snapshot("OperatorTaskRecord", operator),
        authority=AuthorityLineageSnapshot(
            project_id=parent.project_id,
            repository=parent.repository,
            task_branch=parent.task_branch,
            run_branch=operator.branch,
            task_mutation_class=parent.mutation_class,
            run_sandbox=operator.sandbox,
            authority_reference=operator.authority_reference,
        ),
        heads=HeadLineageSnapshot(
            task_base_sha=parent.base_sha,
            task_integrated_head_at_creation=parent.integrated_head_at_creation,
            task_latest_remote_task_sha=parent.latest_remote_task_sha,
            run_expected_head=operator.expected_head,
            run_before_head=operator.before_head,
            run_after_head=operator.after_head,
        ),
        semantics=GoalExecutionSemanticSnapshot(
            task_description=parent.description,
            run_prompt=operator.prompt,
            task_scope_patterns=tuple(parent.scope_patterns),
            run_constraints=tuple(operator.constraints),
            task_required_tests=tuple(parent.required_tests),
            run_actual_tests=tuple(operator.tests),
        ),
        evidence=EvidenceLineageSnapshot(
            task_evidence=tuple(parent.evidence),
            run_evidence=tuple(operator.evidence),
            changed_files=tuple(operator.changed_files),
            execution_receipt=operator.execution_receipt,
            verification_receipt=operator.verification_receipt,
        ),
        timings=TimingLineageSnapshot(
            task_created_at=parent.created_at,
            task_updated_at=parent.updated_at,
            run_created_at=operator.created_at,
            run_updated_at=operator.updated_at,
            queued_at=operator.queued_at,
            started_at=operator.started_at,
            completed_at=operator.completed_at,
            dispatch_latency_ms=operator.dispatch_latency_ms,
            executor_duration_ms=operator.executor_duration_ms,
            verification_duration_ms=operator.verification_duration_ms,
        ),
        events=tuple(_event_snapshot(event) for event in operator.events),
    )


def _assert_identity(
    parent: EngineeringTaskRecord,
    run: ExecutionRunLike,
    operator: OperatorTaskRecord,
) -> None:
    if run.parent_engineering_task_id != parent.task_id:
        raise GovernanceError("SEMANTIC_LINEAGE_PARENT_ID_DRIFT")
    if operator.task_id != run.legacy_operator_task_id:
        raise GovernanceError("SEMANTIC_LINEAGE_OPERATOR_IDENTITY_DRIFT")
    if operator.project_id != parent.project_id:
        raise GovernanceError("SEMANTIC_LINEAGE_PROJECT_DRIFT")
    if operator.repository != parent.repository:
        raise GovernanceError("SEMANTIC_LINEAGE_REPOSITORY_DRIFT")


def _canonical_record_snapshot(
    record_type: str,
    record: BaseModel,
) -> CanonicalRecordSnapshot:
    canonical_json = json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return CanonicalRecordSnapshot(
        record_type=record_type,
        canonical_json=canonical_json,
        sha256=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    )


def _event_snapshot(event: TaskEvent) -> EventLineageSnapshot:
    return EventLineageSnapshot(
        event_type=event.event_type,
        status=event.status.value,
        message=event.message,
        occurred_at=event.occurred_at,
        correlation_id=event.correlation_id,
        client_id=event.client_id,
    )
