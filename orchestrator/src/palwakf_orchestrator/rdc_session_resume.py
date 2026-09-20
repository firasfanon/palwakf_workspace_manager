from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    OperatorTaskRecord,
    ToolPlanResponse,
    ToolSelectionDecision,
)
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.rdc_execution_channel import (
    RdcActionClass,
    RdcPreflightDecision,
    RdcPreflightReceiptV1,
    RdcPreflightRequestV1,
    evaluate_rdc_preflight,
)

RDC_CAPABILITY_ID = "governed.local_execution_channel"
RDC_ADAPTER_ID: Literal["remote-desktop-commander"] = "remote-desktop-commander"
_STATE_KEY = "rdc_session_resume_workflow_v1"
_REQUIRED_BOOT_RULES = frozenset({"TODO-BOOT-014", "TODO-BOOT-015", "TODO-BOOT-016"})


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _merge_evidence(current: tuple[str, ...], added: tuple[str, ...]) -> tuple[str, ...]:
    values = [*current, *added]
    if any(not value.strip() for value in values):
        raise GovernanceError("RDC_SESSION_EMPTY_EVIDENCE")
    return tuple(dict.fromkeys(values))


class RdcSessionLifecycle(StrEnum):
    active = "ACTIVE"
    interrupted = "INTERRUPTED"
    resumed = "RESUMED"
    completed = "COMPLETED"


class RdcSessionBootstrapProofV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=2, max_length=128)
    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    current_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    todo_boot_rule_ids: tuple[str, ...] = Field(min_length=3, max_length=32)
    latest_handoff_loaded: Literal[True] = True
    fresh_git_readback: Literal[True] = True
    fresh_drive_readback: Literal[True] = True
    live_rdc_readback: Literal[True] = True

    @model_validator(mode="after")
    def require_execution_channel_bootstrap(self) -> Self:
        if not _REQUIRED_BOOT_RULES.issubset(set(self.todo_boot_rule_ids)):
            raise ValueError("RDC_SESSION_REQUIRED_BOOTSTRAP_RULES_MISSING")
        return self


class RdcSessionActionReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=3, max_length=160)
    action_class: RdcActionClass
    requested_paths: tuple[str, ...] = Field(min_length=1, max_length=256)
    preflight_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: tuple[str, ...] = Field(min_length=1, max_length=128)
    completed_at: datetime


class RdcSessionResumeRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: Literal["PALWAKF_RDC_SESSION_RESUME_WORKFLOW_V1"] = (
        "PALWAKF_RDC_SESSION_RESUME_WORKFLOW_V1"
    )
    task_id: str
    project_id: str
    repository: str
    branch: str
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    authority_reference: str
    selected_channel: Literal["remote-desktop-commander"] = RDC_ADAPTER_ID
    bootstrap_proof_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    last_preflight_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: RdcSessionLifecycle
    checkpoint_sequence: int = Field(ge=0)
    actions: tuple[RdcSessionActionReceiptV1, ...] = ()
    evidence: tuple[str, ...] = Field(min_length=1, max_length=256)
    manual_user_relay_required: bool = False
    manual_relay_exception_reference: str | None = None
    manual_relay_exception_blockers: tuple[str, ...] = ()
    manual_relay_is_default: Literal[False] = False
    authority_expansion_allowed: Literal[False] = False
    main_merge_authorized: Literal[False] = False
    baseline_promotion_authorized: Literal[False] = False
    production_authorized: Literal[False] = False
    database_mutation_authorized: Literal[False] = False
    created_at: datetime
    updated_at: datetime


def _rdc_decision(plan: ToolPlanResponse) -> ToolSelectionDecision | None:
    return next(
        (decision for decision in plan.decisions if decision.capability_id == RDC_CAPABILITY_ID),
        None,
    )


class RdcSessionResumeStore:
    def __init__(self, state_store: StateStore) -> None:
        self._state_store = state_store
        self._records: dict[str, RdcSessionResumeRecordV1] = {}
        self._restore()

    def get(self, task_id: str) -> RdcSessionResumeRecordV1:
        try:
            return self._records[task_id]
        except KeyError as exc:
            raise GovernanceError("RDC_SESSION_NOT_FOUND") from exc

    def _validate_context(
        self,
        *,
        task: OperatorTaskRecord,
        plan: ToolPlanResponse,
        bootstrap: RdcSessionBootstrapProofV1,
        request: RdcPreflightRequestV1,
    ) -> RdcPreflightReceiptV1:
        binding = request.binding
        blockers: list[str] = []

        if bootstrap.project_id != task.project_id:
            blockers.append("RDC_SESSION_BOOTSTRAP_PROJECT_MISMATCH")
        if bootstrap.task_id != task.task_id:
            blockers.append("RDC_SESSION_BOOTSTRAP_TASK_MISMATCH")
        if bootstrap.current_head.lower() != task.expected_head.lower():
            blockers.append("RDC_SESSION_BOOTSTRAP_HEAD_MISMATCH")
        if plan.task_id != task.task_id or plan.project_id != task.project_id:
            blockers.append("RDC_SESSION_TOOL_PLAN_IDENTITY_MISMATCH")

        decision = _rdc_decision(plan)
        if decision is None:
            blockers.append("RDC_SESSION_LOCAL_CHANNEL_NOT_PLANNED")
        elif decision.selected_adapter_id != RDC_ADAPTER_ID or decision.blocked:
            blockers.append("RDC_SESSION_RDC_NOT_SELECTED")
        elif decision.approval_required and task.authorized_at is None:
            blockers.append("RDC_SESSION_RDC_APPROVAL_NOT_SATISFIED")

        checks = (
            (binding.task_id, task.task_id, "RDC_SESSION_TASK_BINDING_MISMATCH"),
            (binding.project_id, task.project_id, "RDC_SESSION_PROJECT_BINDING_MISMATCH"),
            (binding.repository, task.repository, "RDC_SESSION_REPOSITORY_BINDING_MISMATCH"),
            (binding.branch, task.branch, "RDC_SESSION_BRANCH_BINDING_MISMATCH"),
            (
                binding.authority_reference,
                task.authority_reference,
                "RDC_SESSION_AUTHORITY_REFERENCE_MISMATCH",
            ),
        )
        for actual, expected, blocker in checks:
            if actual != expected:
                blockers.append(blocker)
        if binding.expected_head.lower() != task.expected_head.lower():
            blockers.append("RDC_SESSION_HEAD_BINDING_MISMATCH")

        if binding.mutation_class == "source-write":
            if task.sandbox != "workspace-write":
                blockers.append("RDC_SESSION_SOURCE_WRITE_SANDBOX_MISMATCH")
            if not task.requires_explicit_authorization or task.authorized_at is None:
                blockers.append("RDC_SESSION_SOURCE_WRITE_AUTHORIZATION_MISSING")
            if not task.scope_patterns:
                blockers.append("RDC_SESSION_SOURCE_WRITE_SCOPE_REQUIRED")
            if tuple(task.scope_patterns) != binding.scope_patterns:
                blockers.append("RDC_SESSION_SOURCE_WRITE_SCOPE_MISMATCH")

        receipt = evaluate_rdc_preflight(request)
        if receipt.decision is not RdcPreflightDecision.allow:
            blockers.append("RDC_SESSION_PREFLIGHT_DENIED")
            blockers.extend(receipt.blockers)

        if blockers:
            raise GovernanceError("|".join(dict.fromkeys(blockers)))
        return receipt

    def start(
        self,
        *,
        task: OperatorTaskRecord,
        plan: ToolPlanResponse,
        bootstrap: RdcSessionBootstrapProofV1,
        request: RdcPreflightRequestV1,
        evidence: tuple[str, ...],
    ) -> RdcSessionResumeRecordV1:
        receipt = self._validate_context(task=task, plan=plan, bootstrap=bootstrap, request=request)
        existing = self._records.get(task.task_id)
        if existing is not None:
            self._require_same_identity(existing, task)
            return existing

        now = datetime.now(UTC)
        record = RdcSessionResumeRecordV1(
            task_id=task.task_id,
            project_id=task.project_id,
            repository=task.repository,
            branch=task.branch,
            expected_head=task.expected_head,
            authority_reference=task.authority_reference,
            bootstrap_proof_sha256=_sha256(bootstrap.model_dump(mode="json")),
            last_preflight_request_sha256=receipt.request_sha256,
            tool_config_sha256=receipt.tool_config_sha256,
            lifecycle=RdcSessionLifecycle.active,
            checkpoint_sequence=0,
            evidence=_merge_evidence((), evidence),
            created_at=now,
            updated_at=now,
        )
        self._records[task.task_id] = record
        self._persist()
        return record

    def record_action(
        self,
        task_id: str,
        *,
        action_id: str,
        request: RdcPreflightRequestV1,
        evidence: tuple[str, ...],
    ) -> RdcSessionResumeRecordV1:
        record = self.get(task_id)
        if record.lifecycle not in {
            RdcSessionLifecycle.active,
            RdcSessionLifecycle.resumed,
        }:
            raise GovernanceError("RDC_SESSION_ACTION_REQUIRES_ACTIVE_SESSION")
        self._require_request_identity(record, request)
        receipt = evaluate_rdc_preflight(request)
        if receipt.decision is not RdcPreflightDecision.allow:
            raise GovernanceError(
                "RDC_SESSION_ACTION_PREFLIGHT_DENIED:" + ",".join(receipt.blockers)
            )
        action = RdcSessionActionReceiptV1(
            action_id=action_id,
            action_class=request.requested_action,
            requested_paths=request.requested_paths,
            preflight_request_sha256=receipt.request_sha256,
            evidence=_merge_evidence((), evidence),
            completed_at=datetime.now(UTC),
        )
        previous = next((item for item in record.actions if item.action_id == action_id), None)
        if previous is not None:
            comparable_previous = previous.model_dump(exclude={"completed_at"})
            comparable_action = action.model_dump(exclude={"completed_at"})
            if comparable_previous != comparable_action:
                raise GovernanceError("RDC_SESSION_ACTION_ID_REUSE_MISMATCH")
            return record

        now = datetime.now(UTC)
        updated = record.model_copy(
            update={
                "actions": (*record.actions, action),
                "last_preflight_request_sha256": receipt.request_sha256,
                "tool_config_sha256": receipt.tool_config_sha256,
                "checkpoint_sequence": record.checkpoint_sequence + 1,
                "evidence": _merge_evidence(record.evidence, evidence),
                "updated_at": now,
            }
        )
        self._records[task_id] = updated
        self._persist()
        return updated

    def interrupt(
        self,
        task_id: str,
        *,
        evidence: tuple[str, ...],
    ) -> RdcSessionResumeRecordV1:
        record = self.get(task_id)
        if record.lifecycle == RdcSessionLifecycle.interrupted:
            return record
        if record.lifecycle not in {
            RdcSessionLifecycle.active,
            RdcSessionLifecycle.resumed,
        }:
            raise GovernanceError("RDC_SESSION_CANNOT_INTERRUPT")
        updated = record.model_copy(
            update={
                "lifecycle": RdcSessionLifecycle.interrupted,
                "checkpoint_sequence": record.checkpoint_sequence + 1,
                "evidence": _merge_evidence(record.evidence, evidence),
                "updated_at": datetime.now(UTC),
            }
        )
        self._records[task_id] = updated
        self._persist()
        return updated

    def resume(
        self,
        *,
        task: OperatorTaskRecord,
        plan: ToolPlanResponse,
        bootstrap: RdcSessionBootstrapProofV1,
        request: RdcPreflightRequestV1,
        evidence: tuple[str, ...],
    ) -> RdcSessionResumeRecordV1:
        record = self.get(task.task_id)
        if record.lifecycle != RdcSessionLifecycle.interrupted:
            raise GovernanceError("RDC_SESSION_RESUME_REQUIRES_INTERRUPTED_STATE")
        self._require_same_identity(record, task)
        receipt = self._validate_context(task=task, plan=plan, bootstrap=bootstrap, request=request)
        updated = record.model_copy(
            update={
                "lifecycle": RdcSessionLifecycle.resumed,
                "bootstrap_proof_sha256": _sha256(bootstrap.model_dump(mode="json")),
                "last_preflight_request_sha256": receipt.request_sha256,
                "tool_config_sha256": receipt.tool_config_sha256,
                "checkpoint_sequence": record.checkpoint_sequence + 1,
                "evidence": _merge_evidence(record.evidence, evidence),
                "updated_at": datetime.now(UTC),
            }
        )
        self._records[task.task_id] = updated
        self._persist()
        return updated

    def record_manual_relay_exception(
        self,
        task_id: str,
        *,
        exception_reference: str,
        rdc_blockers: tuple[str, ...],
        evidence: tuple[str, ...],
    ) -> RdcSessionResumeRecordV1:
        record = self.get(task_id)
        if record.lifecycle != RdcSessionLifecycle.interrupted:
            raise GovernanceError("RDC_MANUAL_RELAY_EXCEPTION_REQUIRES_INTERRUPTION")
        if len(exception_reference.strip()) < 8:
            raise GovernanceError("RDC_MANUAL_RELAY_EXCEPTION_REFERENCE_REQUIRED")
        if not rdc_blockers or any(not item.strip() for item in rdc_blockers):
            raise GovernanceError("RDC_MANUAL_RELAY_EXCEPTION_BLOCKERS_REQUIRED")
        updated = record.model_copy(
            update={
                "manual_user_relay_required": True,
                "manual_relay_exception_reference": exception_reference,
                "manual_relay_exception_blockers": tuple(dict.fromkeys(rdc_blockers)),
                "checkpoint_sequence": record.checkpoint_sequence + 1,
                "evidence": _merge_evidence(record.evidence, evidence),
                "updated_at": datetime.now(UTC),
            }
        )
        self._records[task_id] = updated
        self._persist()
        return updated

    def complete(
        self,
        task_id: str,
        *,
        evidence: tuple[str, ...],
    ) -> RdcSessionResumeRecordV1:
        record = self.get(task_id)
        if record.lifecycle not in {
            RdcSessionLifecycle.active,
            RdcSessionLifecycle.resumed,
        }:
            raise GovernanceError("RDC_SESSION_COMPLETION_REQUIRES_ACTIVE_SESSION")
        updated = record.model_copy(
            update={
                "lifecycle": RdcSessionLifecycle.completed,
                "checkpoint_sequence": record.checkpoint_sequence + 1,
                "evidence": _merge_evidence(record.evidence, evidence),
                "updated_at": datetime.now(UTC),
            }
        )
        self._records[task_id] = updated
        self._persist()
        return updated

    @staticmethod
    def _require_same_identity(
        record: RdcSessionResumeRecordV1,
        task: OperatorTaskRecord,
    ) -> None:
        values = (
            (record.task_id, task.task_id),
            (record.project_id, task.project_id),
            (record.repository, task.repository),
            (record.branch, task.branch),
            (record.expected_head.lower(), task.expected_head.lower()),
            (record.authority_reference, task.authority_reference),
        )
        if any(left != right for left, right in values):
            raise GovernanceError("RDC_SESSION_PERSISTED_IDENTITY_DRIFT")

    @staticmethod
    def _require_request_identity(
        record: RdcSessionResumeRecordV1,
        request: RdcPreflightRequestV1,
    ) -> None:
        binding = request.binding
        values = (
            (record.task_id, binding.task_id),
            (record.project_id, binding.project_id),
            (record.repository, binding.repository),
            (record.branch, binding.branch),
            (record.expected_head.lower(), binding.expected_head.lower()),
            (record.authority_reference, binding.authority_reference),
        )
        if any(left != right for left, right in values):
            raise GovernanceError("RDC_SESSION_ACTION_BINDING_DRIFT")

    def _restore(self) -> None:
        state = self._state_store.load().get(_STATE_KEY, {})
        self._records = {
            task_id: RdcSessionResumeRecordV1.model_validate(value)
            for task_id, value in state.get("records", {}).items()
        }

    def _persist(self) -> None:
        state = self._state_store.load()
        state[_STATE_KEY] = {
            "records": {
                task_id: record.model_dump(mode="json") for task_id, record in self._records.items()
            }
        }
        self._state_store.save(state)
