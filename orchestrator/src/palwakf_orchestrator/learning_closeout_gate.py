from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError


class LearningDisposition(StrEnum):
    knowledge_delta = "KNOWLEDGE_DELTA"
    no_new_durable_learning = "NO_NEW_DURABLE_LEARNING"


class KnowledgeDeltaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    subject_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    summary: str = Field(min_length=3, max_length=4000)
    claim_keys: tuple[str, ...] = Field(min_length=1, max_length=64)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=128)
    canonical_promotion_allowed: Literal[False] = False


class LearningCloseoutReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    subject_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    disposition: LearningDisposition
    knowledge_delta: KnowledgeDeltaV1 | None = None
    rationale: str | None = Field(default=None, max_length=4000)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=128)
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.disposition == LearningDisposition.knowledge_delta:
            if self.knowledge_delta is None:
                raise ValueError("LEARNING_CLOSEOUT_KNOWLEDGE_DELTA_REQUIRED")
            if (
                self.knowledge_delta.project_id != self.project_id
                or self.knowledge_delta.task_id != self.task_id
                or self.knowledge_delta.subject_head != self.subject_head
            ):
                raise ValueError("LEARNING_CLOSEOUT_KNOWLEDGE_DELTA_BINDING_MISMATCH")
        else:
            if self.knowledge_delta is not None:
                raise ValueError("LEARNING_CLOSEOUT_UNEXPECTED_KNOWLEDGE_DELTA")
            if not (self.rationale or "").strip():
                raise ValueError("LEARNING_CLOSEOUT_NO_LEARNING_RATIONALE_REQUIRED")
        if self.receipt_id != _sha256(_receipt_payload(
            project_id=self.project_id,
            task_id=self.task_id,
            subject_head=self.subject_head,
            disposition=self.disposition,
            knowledge_delta=self.knowledge_delta,
            rationale=self.rationale,
            evidence=self.evidence,
        )):
            raise ValueError("LEARNING_CLOSEOUT_RECEIPT_HASH_MISMATCH")
        return self


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _receipt_payload(
    *,
    project_id: str,
    task_id: str,
    subject_head: str,
    disposition: LearningDisposition,
    knowledge_delta: KnowledgeDeltaV1 | None,
    rationale: str | None,
    evidence: tuple[str, ...],
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "task_id": task_id,
        "subject_head": subject_head,
        "disposition": disposition.value,
        "knowledge_delta": (
            knowledge_delta.model_dump(mode="json") if knowledge_delta is not None else None
        ),
        "rationale": rationale,
        "evidence": evidence,
        "canonical_promotion_allowed": False,
    }


def build_learning_closeout_receipt(
    *,
    project_id: str,
    task_id: str,
    subject_head: str,
    disposition: LearningDisposition,
    evidence: tuple[str, ...],
    knowledge_delta: KnowledgeDeltaV1 | None = None,
    rationale: str | None = None,
) -> LearningCloseoutReceiptV1:
    payload = _receipt_payload(
        project_id=project_id,
        task_id=task_id,
        subject_head=subject_head,
        disposition=disposition,
        knowledge_delta=knowledge_delta,
        rationale=rationale,
        evidence=evidence,
    )
    return LearningCloseoutReceiptV1(
        receipt_id=_sha256(payload),
        project_id=project_id,
        task_id=task_id,
        subject_head=subject_head,
        disposition=disposition,
        knowledge_delta=knowledge_delta,
        rationale=rationale,
        evidence=evidence,
    )


def require_material_learning_closeout(
    receipt: LearningCloseoutReceiptV1 | None,
    *,
    project_id: str,
    task_id: str,
    subject_head: str,
) -> LearningCloseoutReceiptV1:
    if receipt is None:
        raise GovernanceError("MATERIAL_TASK_LEARNING_CLOSEOUT_REQUIRED")
    if receipt.project_id != project_id:
        raise GovernanceError("LEARNING_CLOSEOUT_PROJECT_MISMATCH")
    if receipt.task_id != task_id:
        raise GovernanceError("LEARNING_CLOSEOUT_TASK_MISMATCH")
    if receipt.subject_head != subject_head.lower():
        raise GovernanceError("LEARNING_CLOSEOUT_HEAD_MISMATCH")
    return receipt
