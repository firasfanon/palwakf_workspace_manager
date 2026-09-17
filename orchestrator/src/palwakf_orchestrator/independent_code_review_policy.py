from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError


class MaterialCodeReviewReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=2, max_length=128)
    repository: str = Field(min_length=3, max_length=240)
    task_id: str = Field(min_length=3, max_length=128)
    subject_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    coding_agent_id: str = Field(min_length=3, max_length=200)
    final_review_agent_id: Literal["qa_security_reviewer_agentic_v1"] = (
        "qa_security_reviewer_agentic_v1"
    )
    coding_admission_reference: Literal["PREL5-024"] = "PREL5-024"
    review_admission_reference: Literal["PREL5-025"] = "PREL5-025"
    test_admission_reference: Literal["PREL5-026"] = "PREL5-026"
    review_capability: Literal["INDEPENDENT_QA_SECURITY_REVIEW"] = "INDEPENDENT_QA_SECURITY_REVIEW"
    test_capability: Literal["CONTROLLED_TEST_EXECUTION"] = "CONTROLLED_TEST_EXECUTION"
    review_passed: Literal[True] = True
    test_evidence_passed: Literal[True] = True
    evidence: tuple[str, ...] = Field(min_length=2, max_length=64)

    @model_validator(mode="after")
    def validate_independence_and_evidence(self) -> Self:
        if self.coding_agent_id == self.final_review_agent_id:
            raise ValueError("CODING_AGENT_MUST_DIFFER_FROM_FINAL_REVIEW_AGENT")
        if any(not item.strip() for item in self.evidence):
            raise ValueError("MATERIAL_CODE_REVIEW_EVIDENCE_REQUIRED")
        if not any("PREL5-024" in item for item in self.evidence):
            raise ValueError("PREL5_024_CODING_AGENT_EVIDENCE_REQUIRED")
        if not any("PREL5-025" in item for item in self.evidence):
            raise ValueError("PREL5_025_REVIEW_EVIDENCE_REQUIRED")
        if not any("PREL5-026" in item for item in self.evidence):
            raise ValueError("PREL5_026_TEST_EVIDENCE_REQUIRED")
        return self


def require_material_code_review(
    *,
    receipt: MaterialCodeReviewReceiptV1 | None,
    project_id: str,
    repository: str,
    task_id: str,
    subject_sha: str,
) -> MaterialCodeReviewReceiptV1:
    if receipt is None:
        raise GovernanceError("MATERIAL_CODE_INDEPENDENT_REVIEW_REQUIRED")
    if receipt.project_id != project_id:
        raise GovernanceError("MATERIAL_CODE_REVIEW_PROJECT_MISMATCH")
    if receipt.repository != repository:
        raise GovernanceError("MATERIAL_CODE_REVIEW_REPOSITORY_MISMATCH")
    if receipt.task_id != task_id:
        raise GovernanceError("MATERIAL_CODE_REVIEW_TASK_MISMATCH")
    if receipt.subject_sha != subject_sha.lower():
        raise GovernanceError("MATERIAL_CODE_REVIEW_STALE_HEAD")
    return receipt
