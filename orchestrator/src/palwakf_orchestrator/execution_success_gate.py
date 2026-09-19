from __future__ import annotations

import fnmatch
import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.engineering_os_contracts import EngineeringTaskRecord
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.evidence_acceptance_engine import EvidenceKind
from palwakf_orchestrator.independent_code_review_policy import (
    MaterialCodeReviewReceiptV1,
    require_material_code_review,
)
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord, OperatorTaskStatus


class SemanticObjectiveReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=2, max_length=128)
    repository: str = Field(min_length=3, max_length=240)
    task_id: str = Field(min_length=3, max_length=128)
    subject_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    objective_reference: str = Field(min_length=3, max_length=1000)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)


class ExecutionSuccessReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    project_id: str
    repository: str
    task_id: str
    subject_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    semantic_objective_reference: str
    tests_reference: str
    scope_authority_reference: str
    independent_review_receipt_id: str
    evidence_readback_reference: str


def _scope_violations(parent: EngineeringTaskRecord, run: OperatorTaskRecord) -> list[str]:
    violations: list[str] = []
    for changed in run.changed_files:
        normalized = changed.replace("\\", "/").lstrip("./")
        if not any(fnmatch.fnmatch(normalized, pattern) for pattern in parent.scope_patterns):
            violations.append(normalized)
    return sorted(set(violations))


def _canonical_receipt_id(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "success-" + hashlib.sha256(encoded).hexdigest()[:24]


def require_five_part_execution_success(
    *,
    parent: EngineeringTaskRecord,
    run: OperatorTaskRecord,
    semantic_receipt: SemanticObjectiveReceiptV1 | None,
    material_review_receipt: MaterialCodeReviewReceiptV1 | None,
) -> ExecutionSuccessReceiptV1:
    if run.status != OperatorTaskStatus.verified:
        raise GovernanceError("EXECUTION_SUCCESS_REQUIRES_VERIFIED_RUN")
    subject_sha = (run.after_head or parent.latest_remote_task_sha or "").lower()
    if len(subject_sha) != 40:
        raise GovernanceError("EXECUTION_SUCCESS_SUBJECT_HEAD_REQUIRED")
    if semantic_receipt is None:
        raise GovernanceError("SEMANTIC_OBJECTIVE_EVIDENCE_REQUIRED")
    if (
        semantic_receipt.project_id != parent.project_id
        or semantic_receipt.repository != parent.repository
        or semantic_receipt.task_id != parent.task_id
        or semantic_receipt.subject_sha != subject_sha
    ):
        raise GovernanceError("SEMANTIC_OBJECTIVE_BINDING_MISMATCH")
    if not semantic_receipt.evidence:
        raise GovernanceError("SEMANTIC_OBJECTIVE_EVIDENCE_REQUIRED")

    decision = run.acceptance_decision
    if decision is None or not decision.accepted or decision.subject_head != subject_sha:
        raise GovernanceError("ACCEPTANCE_DECISION_REQUIRED")

    if EvidenceKind.tests not in decision.satisfied_kinds:
        raise GovernanceError("EXECUTION_SUCCESS_TESTS_REQUIRED")
    if EvidenceKind.readback not in decision.satisfied_kinds:
        raise GovernanceError("EXECUTION_SUCCESS_READBACK_REQUIRED")

    violations = _scope_violations(parent, run)
    if violations:
        raise GovernanceError("EXECUTION_SUCCESS_SCOPE_VIOLATION:" + ",".join(violations))
    if not run.authority_reference.strip():
        raise GovernanceError("EXECUTION_SUCCESS_AUTHORITY_REQUIRED")
    if run.requires_explicit_authorization and run.authorized_at is None:
        raise GovernanceError("EXECUTION_SUCCESS_EXPLICIT_AUTHORIZATION_REQUIRED")

    review = require_material_code_review(
        receipt=material_review_receipt,
        project_id=parent.project_id,
        repository=parent.repository,
        task_id=parent.task_id,
        subject_sha=subject_sha,
    )

    payload = {
        "project_id": parent.project_id,
        "repository": parent.repository,
        "task_id": parent.task_id,
        "subject_sha": subject_sha,
        "semantic": semantic_receipt.objective_reference,
        "tests": "TESTS",
        "scope_authority": run.authority_reference,
        "review": review.receipt_id,
        "readback": "READBACK",
    }
    return ExecutionSuccessReceiptV1(
        receipt_id=_canonical_receipt_id(payload),
        project_id=parent.project_id,
        repository=parent.repository,
        task_id=parent.task_id,
        subject_sha=subject_sha,
        semantic_objective_reference=semantic_receipt.objective_reference,
        tests_reference="TESTS",
        scope_authority_reference=run.authority_reference,
        independent_review_receipt_id=review.receipt_id,
        evidence_readback_reference="READBACK",
    )
