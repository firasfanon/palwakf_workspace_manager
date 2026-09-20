from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.evidence_acceptance_engine import (
    AcceptanceEvidenceV1,
    EvidenceKind,
    EvidenceStatus,
    evaluate_acceptance,
)
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskStatus,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService

HEAD = "a" * 40
AFTER = "b" * 40
STALE = "c" * 40


class FakeVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def verify(self, branch: str, expected_head: str) -> str:
        self.calls.append((branch, expected_head))
        if expected_head != AFTER:
            raise GovernanceError("HEAD drift")
        return expected_head


def request() -> CreateOperatorTaskRequest:
    return CreateOperatorTaskRequest.model_validate(
        {
            "task_id": "PREL5_034_ACCEPTANCE_TEST",
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "repository": "firasfanon/palwakf_workspace_manager",
            "branch": "agent/workspace-manager-foundation-v1",
            "expected_head": HEAD,
            "authority_reference": "AUTHORITY://PREL5/034",
            "prompt": "Verify deterministic evidence-to-acceptance mapping.",
            "constraints": ["NO_PRODUCTION", "NO_DATABASE_MUTATION"],
            "approval_policy": "never",
            "sandbox": "read-only",
            "max_turns": 2,
            "timeout_seconds": 120,
            "idempotency_key": "prel5-034-acceptance-test",
            "acceptance_requirements": ["TESTS", "CI", "UAT", "READBACK"],
        }
    )


def pending_service(tmp_path: Path) -> tuple[OperatorService, FakeVerifier]:
    verifier = FakeVerifier()
    service = OperatorService(tmp_path, verifier=verifier)
    task = service.create_task(request())
    task.status = OperatorTaskStatus.pending_verification
    task.after_head = AFTER
    task.tests = ["pytest tests/test_example.py"]
    return service, verifier


def uat(head: str, status: EvidenceStatus) -> AcceptanceEvidenceV1:
    return AcceptanceEvidenceV1(
        kind=EvidenceKind.uat,
        status=status,
        reference=f"uat-receipt:{status.value.lower()}",
        subject_head=head,
    )


def verify_request(*, uat_evidence: AcceptanceEvidenceV1 | None = None) -> VerificationRequest:
    return VerificationRequest(
        verification_receipt="github-actions-prel5-034",
        ci_status="success",
        verified_head=AFTER,
        uat_evidence=uat_evidence,
    )


def test_engine_rejects_empty_requirements() -> None:
    with pytest.raises(ValueError, match="ACCEPTANCE_REQUIREMENTS_EMPTY"):
        evaluate_acceptance(subject_head=AFTER, required_kinds=(), evidence=())


def test_engine_ignores_stale_head_evidence() -> None:
    decision = evaluate_acceptance(
        subject_head=AFTER,
        required_kinds=(EvidenceKind.uat,),
        evidence=(uat(STALE, EvidenceStatus.passed),),
    )
    assert decision.accepted is False
    assert decision.missing_kinds == (EvidenceKind.uat,)


def test_missing_uat_blocks_verification(tmp_path: Path) -> None:
    service, verifier = pending_service(tmp_path)
    with pytest.raises(GovernanceError, match="MISSING=UAT"):
        service.verify_task("PREL5_034_ACCEPTANCE_TEST", verify_request())
    task = service.get_task("PREL5_034_ACCEPTANCE_TEST")
    assert task.status == OperatorTaskStatus.pending_verification
    assert task.acceptance_decision is not None
    assert task.acceptance_decision.accepted is False
    assert verifier.calls == [("agent/workspace-manager-foundation-v1", AFTER)]


def test_failed_uat_blocks_verification(tmp_path: Path) -> None:
    service, _ = pending_service(tmp_path)
    with pytest.raises(GovernanceError, match="FAILED=UAT"):
        service.verify_task(
            "PREL5_034_ACCEPTANCE_TEST",
            verify_request(uat_evidence=uat(AFTER, EvidenceStatus.failed)),
        )


def test_stale_head_uat_is_treated_as_missing(tmp_path: Path) -> None:
    service, _ = pending_service(tmp_path)
    with pytest.raises(GovernanceError, match="MISSING=UAT"):
        service.verify_task(
            "PREL5_034_ACCEPTANCE_TEST",
            verify_request(uat_evidence=uat(STALE, EvidenceStatus.passed)),
        )


def test_missing_test_evidence_blocks_when_required(tmp_path: Path) -> None:
    service, _ = pending_service(tmp_path)
    service.get_task("PREL5_034_ACCEPTANCE_TEST").tests = []
    with pytest.raises(GovernanceError, match="MISSING=TESTS"):
        service.verify_task(
            "PREL5_034_ACCEPTANCE_TEST",
            verify_request(uat_evidence=uat(AFTER, EvidenceStatus.passed)),
        )


def test_failed_ci_maps_to_failed_acceptance(tmp_path: Path) -> None:
    service, _ = pending_service(tmp_path)
    request_value = verify_request(uat_evidence=uat(AFTER, EvidenceStatus.passed))
    request_value.ci_status = "failed"
    with pytest.raises(GovernanceError, match="FAILED=CI"):
        service.verify_task("PREL5_034_ACCEPTANCE_TEST", request_value)


def test_stale_verified_head_fails_before_acceptance(tmp_path: Path) -> None:
    service, verifier = pending_service(tmp_path)
    request_value = verify_request(uat_evidence=uat(AFTER, EvidenceStatus.passed))
    request_value.verified_head = STALE
    with pytest.raises(GovernanceError, match="verification receipt HEAD"):
        service.verify_task("PREL5_034_ACCEPTANCE_TEST", request_value)
    assert verifier.calls == []


def test_acceptance_requirements_persist_on_task_record(tmp_path: Path) -> None:
    service, _ = pending_service(tmp_path)
    task = service.get_task("PREL5_034_ACCEPTANCE_TEST")
    assert task.acceptance_requirements == [
        EvidenceKind.tests,
        EvidenceKind.ci,
        EvidenceKind.uat,
        EvidenceKind.readback,
    ]


def test_complete_evidence_set_verifies_task(tmp_path: Path) -> None:
    service, verifier = pending_service(tmp_path)
    result = service.verify_task(
        "PREL5_034_ACCEPTANCE_TEST",
        verify_request(uat_evidence=uat(AFTER, EvidenceStatus.passed)),
    )
    assert result.status == OperatorTaskStatus.verified
    assert result.acceptance_decision is not None
    assert result.acceptance_decision.accepted is True
    assert result.acceptance_decision.missing_kinds == ()
    assert result.acceptance_decision.failed_kinds == ()
    assert verifier.calls == [("agent/workspace-manager-foundation-v1", AFTER)]
