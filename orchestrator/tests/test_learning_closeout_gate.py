from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.learning_closeout_gate import (
    KnowledgeDeltaV1,
    LearningCloseoutReceiptV1,
    LearningDisposition,
    build_learning_closeout_receipt,
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
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def request(task_id: str = "PREL5_037_LEARNING_TEST") -> CreateOperatorTaskRequest:
    return CreateOperatorTaskRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository="firasfanon/palwakf_workspace_manager",
        branch="agent/workspace-manager-foundation-v1",
        expected_head=HEAD,
        authority_reference="AUTHORITY://PREL5/037",
        prompt="Verify mandatory learning closeout on material task completion.",
        constraints=["NO_PRODUCTION", "NO_DATABASE_MUTATION"],
        sandbox="workspace-write",
        max_turns=2,
        timeout_seconds=120,
        idempotency_key=f"prel5-037-{task_id.lower()}",
    )


def pending_material_service(
    tmp_path: Path,
    *,
    task_id: str = "PREL5_037_LEARNING_TEST",
) -> tuple[OperatorService, object]:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(request(task_id))
    task.status = OperatorTaskStatus.pending_verification
    task.after_head = AFTER
    task.changed_files = ["orchestrator/example.py"]
    return service, task


def no_learning_receipt(task_id: str, head: str = AFTER):
    return build_learning_closeout_receipt(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        task_id=task_id,
        subject_head=head,
        disposition=LearningDisposition.no_new_durable_learning,
        rationale="Review found no new durable knowledge beyond existing governed records.",
        evidence=("learning-review:complete",),
    )


def knowledge_delta(task_id: str) -> KnowledgeDeltaV1:
    return KnowledgeDeltaV1(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        task_id=task_id,
        subject_head=AFTER,
        summary="Captured a new durable learning from the material task.",
        claim_keys=("learning/material-closeout",),
        evidence=("evidence:task-review",),
    )


def verify_request(*, task_id: str, receipt=None) -> VerificationRequest:
    return VerificationRequest(
        verification_receipt="ci-prel5-037-pass",
        ci_status="success",
        verified_head=AFTER,
        learning_closeout_receipt=receipt,
    )


def test_material_task_cannot_close_without_learning_receipt(tmp_path: Path) -> None:
    service, task = pending_material_service(tmp_path)

    with pytest.raises(GovernanceError, match="MATERIAL_TASK_LEARNING_CLOSEOUT_REQUIRED"):
        service.verify_task(task.task_id, verify_request(task_id=task.task_id))

    assert service.get_task(task.task_id).status == OperatorTaskStatus.pending_verification



def test_no_new_durable_learning_receipt_allows_material_closeout(tmp_path: Path) -> None:
    service, task = pending_material_service(tmp_path)
    receipt = no_learning_receipt(task.task_id)

    verified = service.verify_task(
        task.task_id,
        verify_request(task_id=task.task_id, receipt=receipt),
    )

    assert verified.status == OperatorTaskStatus.verified
    assert verified.learning_closeout_receipt == receipt
    assert receipt.disposition == LearningDisposition.no_new_durable_learning


def test_knowledge_delta_receipt_allows_material_closeout(tmp_path: Path) -> None:
    service, task = pending_material_service(tmp_path, task_id="PREL5_037_DELTA_TEST")
    delta = knowledge_delta(task.task_id)
    receipt = build_learning_closeout_receipt(
        project_id=task.project_id,
        task_id=task.task_id,
        subject_head=AFTER,
        disposition=LearningDisposition.knowledge_delta,
        knowledge_delta=delta,
        evidence=("learning-delta:captured",),
    )

    verified = service.verify_task(
        task.task_id,
        verify_request(task_id=task.task_id, receipt=receipt),
    )

    assert verified.status == OperatorTaskStatus.verified
    assert verified.learning_closeout_receipt is not None
    assert verified.learning_closeout_receipt.knowledge_delta == delta
    assert verified.learning_closeout_receipt.canonical_promotion_allowed is False


def test_stale_head_learning_receipt_fails_closed(tmp_path: Path) -> None:
    service, task = pending_material_service(tmp_path)
    receipt = no_learning_receipt(task.task_id, STALE)

    with pytest.raises(GovernanceError, match="LEARNING_CLOSEOUT_HEAD_MISMATCH"):
        service.verify_task(
            task.task_id,
            verify_request(task_id=task.task_id, receipt=receipt),
        )


def test_receipt_hash_tamper_is_rejected() -> None:
    receipt = no_learning_receipt("PREL5_037_HASH_TEST")
    raw = receipt.model_dump(mode="json")
    raw["receipt_id"] = "0" * 64

    with pytest.raises(ValueError, match="LEARNING_CLOSEOUT_RECEIPT_HASH_MISMATCH"):
        LearningCloseoutReceiptV1.model_validate(raw)


def test_nonmaterial_task_does_not_require_learning_closeout(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(request("PREL5_037_NONMATERIAL"))
    task.status = OperatorTaskStatus.pending_verification
    task.after_head = AFTER
    task.changed_files = []

    verified = service.verify_task(
        task.task_id,
        VerificationRequest(
            verification_receipt="ci-prel5-037-nonmaterial",
            ci_status="success",
            verified_head=AFTER,
        ),
    )

    assert verified.status == OperatorTaskStatus.verified
    assert verified.learning_closeout_receipt is None
