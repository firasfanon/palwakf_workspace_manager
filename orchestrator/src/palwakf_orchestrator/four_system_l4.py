from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.intersystem_contracts import (
    WorkspaceAuthorityPackageV1,
    build_workspace_authority_package,
)
from palwakf_orchestrator.persistence import StateStore

STATE_KEY = "four_system_l4_operational_runs_v1"
CONTRACT_ID = "PALWAKF_FOUR_SYSTEM_L4_OPERATIONAL_CONTRACT_V1"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class L4Checkpoint(BaseModel):
    seq: int
    stage: str
    created_at: str
    payload_sha256: str
    chain_sha256: str


class L4OpenRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_run_id: str = Field(min_length=1, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=160)
    requested_provider_id: Literal["PALWAKF_NATIVE_AGENT"] = "PALWAKF_NATIVE_AGENT"
    requested_model_provider: Literal["none"] = "none"


class L4AgenticResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_run_id: str
    correlation_id: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    agentic_result: dict[str, Any]
    resume_token: str


class L4MindReviewEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_run_id: str
    correlation_id: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_result: dict[str, Any]
    resume_token: str


class L4SovereignAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drive_document_id: str = Field(min_length=1, max_length=256)
    drive_revision_id: str = Field(min_length=1, max_length=512)
    envelope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class L4DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["ACCEPTED", "REWORK_REQUIRED", "REJECTED"]
    reason: str = Field(min_length=1, max_length=1000)


class L4OperationalRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: Literal["PALWAKF_FOUR_SYSTEM_L4_OPERATIONAL_CONTRACT_V1"] = CONTRACT_ID
    workspace_run_id: str
    correlation_id: str
    execution_run_id: str
    stage: str
    authority_package: WorkspaceAuthorityPackageV1
    authority_sha256: str
    agentic_envelope: dict[str, Any] | None = None
    mind_envelope: dict[str, Any] | None = None
    sovereign_ack: dict[str, Any] | None = None
    decision: str | None = None
    decision_reason: str | None = None
    checkpoints: tuple[L4Checkpoint, ...] = ()
    created_at: str
    updated_at: str


class FourSystemL4OperationalService:
    def __init__(self, state_store: StateStore) -> None:
        self._state_store = state_store

    def _load_all(self) -> dict[str, L4OperationalRunRecord]:
        raw = self._state_store.load().get(STATE_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("FOUR_SYSTEM_L4_STATE_INVALID")
        return {
            str(key): L4OperationalRunRecord.model_validate(value)
            for key, value in raw.items()
        }

    def _save(self, record: L4OperationalRunRecord) -> L4OperationalRunRecord:
        state = self._state_store.load()
        raw = state.get(STATE_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("FOUR_SYSTEM_L4_STATE_INVALID")
        updated = dict(raw)
        updated[record.workspace_run_id] = record.model_dump(mode="json")
        state[STATE_KEY] = updated
        self._state_store.save(state)
        return record

    def _checkpoint(
        self,
        record: L4OperationalRunRecord,
        *,
        stage: str,
        payload: Any,
    ) -> L4OperationalRunRecord:
        seq = len(record.checkpoints) + 1
        payload_sha = _sha(payload)
        previous = record.checkpoints[-1].chain_sha256 if record.checkpoints else "0" * 64
        chain_sha = hashlib.sha256(
            f"{previous}:{seq}:{stage}:{payload_sha}".encode("utf-8")
        ).hexdigest()
        checkpoint = L4Checkpoint(
            seq=seq,
            stage=stage,
            created_at=_now(),
            payload_sha256=payload_sha,
            chain_sha256=chain_sha,
        )
        return record.model_copy(
            update={
                "stage": stage,
                "checkpoints": (*record.checkpoints, checkpoint),
                "updated_at": _now(),
            }
        )

    def open_authority_run(
        self,
        *,
        package: WorkspaceAuthorityPackageV1,
        correlation_id: str,
    ) -> L4OperationalRunRecord:
        workspace_run_id = f"l4-{package.execution_run_id}"
        authority_sha = _sha(package.model_dump(mode="json"))
        existing = self._load_all().get(workspace_run_id)
        if existing is not None:
            if (
                existing.correlation_id != correlation_id
                or existing.authority_sha256 != authority_sha
            ):
                raise GovernanceError("FOUR_SYSTEM_L4_OPEN_IDEMPOTENCY_CONFLICT")
            return existing

        record = L4OperationalRunRecord(
            workspace_run_id=workspace_run_id,
            correlation_id=correlation_id,
            execution_run_id=package.execution_run_id,
            stage="OPENED",
            authority_package=package,
            authority_sha256=authority_sha,
            created_at=_now(),
            updated_at=_now(),
        )
        record = self._checkpoint(
            record,
            stage="OPENED",
            payload={
                "workspace_run_id": workspace_run_id,
                "correlation_id": correlation_id,
                "authority_sha256": authority_sha,
            },
        )
        return self._save(record)

    def get(self, workspace_run_id: str) -> L4OperationalRunRecord:
        record = self._load_all().get(workspace_run_id)
        if record is None:
            raise GovernanceError("FOUR_SYSTEM_L4_RUN_NOT_FOUND")
        return record

    def record_agentic(
        self,
        workspace_run_id: str,
        envelope: L4AgenticResultEnvelope,
    ) -> L4OperationalRunRecord:
        record = self.get(workspace_run_id)
        if envelope.workspace_run_id != record.workspace_run_id:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_RUN_ID_MISMATCH")
        if envelope.correlation_id != record.correlation_id:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_CORRELATION_MISMATCH")

        existing = record.agentic_envelope
        incoming = envelope.model_dump(mode="json")
        if existing is not None:
            if _sha(existing) != _sha(incoming):
                raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_REPLAY_CONFLICT")
            return record

        result = envelope.agentic_result
        execution = result.get("execution") or {}
        evaluation = result.get("evaluation") or {}
        learning_bundle = result.get("learning_bundle") or {}
        package = record.authority_package

        if execution.get("project_id") != package.project_id:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_PROJECT_MISMATCH")
        if execution.get("task_id") != package.task_id:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_TASK_MISMATCH")
        if execution.get("state_package_id") != package.state_package_id:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_STATE_PACKAGE_MISMATCH")
        if execution.get("before_head", "").lower() != package.expected_head.lower():
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_HEAD_MISMATCH")
        if execution.get("changed_files") not in ([], ()):
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_MUTATION_OBSERVED")
        if result.get("institutional_knowledge_promoted") is not False:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_AUTO_PROMOTION_DENIED")
        if result.get("external_review_required") is not True:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_EXTERNAL_REVIEW_REQUIRED")
        if learning_bundle.get("project_id") != package.project_id:
            raise GovernanceError("FOUR_SYSTEM_L4_LEARNING_PROJECT_MISMATCH")
        if learning_bundle.get("task_id") != package.task_id:
            raise GovernanceError("FOUR_SYSTEM_L4_LEARNING_TASK_MISMATCH")
        if learning_bundle.get("source_sha", "").lower() != package.expected_head.lower():
            raise GovernanceError("FOUR_SYSTEM_L4_LEARNING_SOURCE_MISMATCH")
        if evaluation.get("run_id") != execution.get("run_id"):
            raise GovernanceError("FOUR_SYSTEM_L4_EVALUATION_RUN_MISMATCH")

        record = record.model_copy(update={"agentic_envelope": incoming, "updated_at": _now()})
        record = self._checkpoint(
            record,
            stage="AGENTIC_COMPLETED",
            payload={
                "result_sha256": envelope.result_sha256,
                "run_id": execution.get("run_id"),
                "final_result": execution.get("final_result"),
                "evaluation_passed": evaluation.get("passed"),
            },
        )
        return self._save(record)

    def record_mind(
        self,
        workspace_run_id: str,
        envelope: L4MindReviewEnvelope,
    ) -> L4OperationalRunRecord:
        record = self.get(workspace_run_id)
        if record.agentic_envelope is None:
            raise GovernanceError("FOUR_SYSTEM_L4_AGENTIC_RESULT_REQUIRED")
        if envelope.workspace_run_id != record.workspace_run_id:
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_RUN_ID_MISMATCH")
        if envelope.correlation_id != record.correlation_id:
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_CORRELATION_MISMATCH")

        existing = record.mind_envelope
        incoming = envelope.model_dump(mode="json")
        if existing is not None:
            if _sha(existing) != _sha(incoming):
                raise GovernanceError("FOUR_SYSTEM_L4_MIND_REPLAY_CONFLICT")
            return record

        review = envelope.review_result
        agentic_result = record.agentic_envelope["agentic_result"]
        bundle = agentic_result["learning_bundle"]

        if review.get("project_id") != record.authority_package.project_id:
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_PROJECT_MISMATCH")
        if review.get("task_id") != record.authority_package.task_id:
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_TASK_MISMATCH")
        if review.get("run_id") != bundle.get("run_id"):
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_SOURCE_RUN_MISMATCH")
        if review.get("canonical_write_allowed") is not False:
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_CANONICAL_WRITE_DENIED")
        if review.get("mutation_mode") != "READ_ONLY":
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_MUTATION_MODE_DENIED")

        record = record.model_copy(update={"mind_envelope": incoming, "updated_at": _now()})
        record = self._checkpoint(
            record,
            stage="MIND_REVIEW_COMPLETED",
            payload={
                "result_sha256": envelope.result_sha256,
                "review_id": review.get("review_id"),
                "conflict_count": review.get("conflict_count"),
            },
        )
        return self._save(record)

    def sovereign_envelope(self, workspace_run_id: str) -> dict[str, Any]:
        record = self.get(workspace_run_id)
        if record.mind_envelope is None:
            raise GovernanceError("FOUR_SYSTEM_L4_MIND_REVIEW_REQUIRED")
        latest = record.checkpoints[-1]
        payload = {
            "contract_id": CONTRACT_ID,
            "workspace_run_id": record.workspace_run_id,
            "correlation_id": record.correlation_id,
            "stage": record.stage,
            "checkpoint_chain_sha256": latest.chain_sha256,
            "authority_sha256": record.authority_sha256,
            "agentic_result_sha256": record.agentic_envelope["result_sha256"],
            "mind_review_sha256": record.mind_envelope["result_sha256"],
            "canonical_knowledge_promoted": False,
            "production_approved": False,
        }
        return {**payload, "envelope_sha256": _sha(payload)}

    def acknowledge_sovereign(
        self,
        workspace_run_id: str,
        ack: L4SovereignAck,
    ) -> L4OperationalRunRecord:
        record = self.get(workspace_run_id)
        expected = self.sovereign_envelope(workspace_run_id)
        if ack.envelope_sha256 != expected["envelope_sha256"]:
            raise GovernanceError("FOUR_SYSTEM_L4_SOVEREIGN_ENVELOPE_HASH_MISMATCH")

        incoming = ack.model_dump(mode="json")
        if record.sovereign_ack is not None:
            if _sha(record.sovereign_ack) != _sha(incoming):
                raise GovernanceError("FOUR_SYSTEM_L4_SOVEREIGN_ACK_REPLAY_CONFLICT")
            return record

        record = record.model_copy(update={"sovereign_ack": incoming, "updated_at": _now()})
        record = self._checkpoint(
            record,
            stage="SOVEREIGN_CHECKPOINT_ACKNOWLEDGED",
            payload=incoming,
        )
        return self._save(record)

    def decide(
        self,
        workspace_run_id: str,
        request: L4DecisionRequest,
    ) -> L4OperationalRunRecord:
        record = self.get(workspace_run_id)
        if record.sovereign_ack is None:
            raise GovernanceError("FOUR_SYSTEM_L4_SOVEREIGN_CHECKPOINT_REQUIRED")
        if record.decision is not None:
            if record.decision != request.decision or record.decision_reason != request.reason:
                raise GovernanceError("FOUR_SYSTEM_L4_DECISION_REPLAY_CONFLICT")
            return record

        agentic_result = record.agentic_envelope["agentic_result"]
        execution = agentic_result["execution"]
        evaluation = agentic_result["evaluation"]

        if request.decision == "ACCEPTED":
            if execution.get("final_result") != "PASS":
                raise GovernanceError("FOUR_SYSTEM_L4_ACCEPT_REQUIRES_EXECUTION_PASS")
            if evaluation.get("passed") is not True:
                raise GovernanceError("FOUR_SYSTEM_L4_ACCEPT_REQUIRES_EVALUATION_PASS")

        record = record.model_copy(
            update={
                "decision": request.decision,
                "decision_reason": request.reason,
                "updated_at": _now(),
            }
        )
        record = self._checkpoint(
            record,
            stage=request.decision,
            payload={"decision": request.decision, "reason": request.reason},
        )
        return self._save(record)


def mount_four_system_l4(
    app: FastAPI,
    *,
    state_store: StateStore,
    execution_runs: ExecutionRunAdapter,
) -> None:
    service = FourSystemL4OperationalService(state_store)
    app.state.four_system_l4_service = service

    def _guard(callable_obj):
        try:
            return callable_obj()
        except GovernanceError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": str(error), "fail_closed": True},
            ) from error

    @app.post("/api/v1/four-system/l4/runs", response_model=L4OperationalRunRecord)
    def open_run(request: L4OpenRunRequest) -> L4OperationalRunRecord:
        def action():
            view = execution_runs.get_operational_view(request.execution_run_id)
            package = build_workspace_authority_package(view)
            if request.requested_provider_id != "PALWAKF_NATIVE_AGENT":
                raise GovernanceError("HERMES_OPERATIONAL_ADMISSION_CLOSED")
            package = package.model_copy(
                update={
                    "requested_provider_id": request.requested_provider_id,
                    "requested_model_provider": request.requested_model_provider,
                }
            )
            return service.open_authority_run(
                package=package,
                correlation_id=request.correlation_id,
            )

        return _guard(action)

    @app.get(
        "/api/v1/four-system/l4/runs/{workspace_run_id}",
        response_model=L4OperationalRunRecord,
    )
    def get_run(workspace_run_id: str) -> L4OperationalRunRecord:
        return _guard(lambda: service.get(workspace_run_id))

    @app.get(
        "/api/v1/four-system/l4/runs/{workspace_run_id}/resume",
        response_model=L4OperationalRunRecord,
    )
    def resume_run(workspace_run_id: str) -> L4OperationalRunRecord:
        return _guard(lambda: service.get(workspace_run_id))

    @app.post(
        "/api/v1/four-system/l4/runs/{workspace_run_id}/agentic-result",
        response_model=L4OperationalRunRecord,
    )
    def agentic_result(
        workspace_run_id: str,
        envelope: L4AgenticResultEnvelope,
    ) -> L4OperationalRunRecord:
        return _guard(lambda: service.record_agentic(workspace_run_id, envelope))

    @app.post(
        "/api/v1/four-system/l4/runs/{workspace_run_id}/mind-review",
        response_model=L4OperationalRunRecord,
    )
    def mind_review(
        workspace_run_id: str,
        envelope: L4MindReviewEnvelope,
    ) -> L4OperationalRunRecord:
        return _guard(lambda: service.record_mind(workspace_run_id, envelope))

    @app.get("/api/v1/four-system/l4/runs/{workspace_run_id}/sovereign-envelope")
    def sovereign_envelope(workspace_run_id: str) -> dict[str, Any]:
        return _guard(lambda: service.sovereign_envelope(workspace_run_id))

    @app.post(
        "/api/v1/four-system/l4/runs/{workspace_run_id}/sovereign-ack",
        response_model=L4OperationalRunRecord,
    )
    def sovereign_ack(
        workspace_run_id: str,
        ack: L4SovereignAck,
    ) -> L4OperationalRunRecord:
        return _guard(lambda: service.acknowledge_sovereign(workspace_run_id, ack))

    @app.post(
        "/api/v1/four-system/l4/runs/{workspace_run_id}/decision",
        response_model=L4OperationalRunRecord,
    )
    def decision(
        workspace_run_id: str,
        request: L4DecisionRequest,
    ) -> L4OperationalRunRecord:
        return _guard(lambda: service.decide(workspace_run_id, request))
