import pytest
from pydantic import ValidationError

from palwakf_orchestrator.four_system_l4 import (
    CONTRACT_ID,
    FourSystemL4OperationalService,
    L4AgenticResultEnvelope,
    L4DecisionRequest,
    L4MindReviewEnvelope,
    L4SovereignAck,
)
from palwakf_orchestrator.intersystem_contracts import WorkspaceAuthorityPackageV1
from palwakf_orchestrator.persistence import MemoryStateStore

HEAD = "2" * 40
BASE = "1" * 40


def package() -> WorkspaceAuthorityPackageV1:
    return WorkspaceAuthorityPackageV1(
        state_package_id="workspace-state-run-1",
        execution_run_id="run-1",
        project_id="PALWAKF_LOCAL_AGENTS",
        task_id="task-1",
        repository="firasfanon/palwakf_agenticAi_system",
        task_branch="task/example",
        base_sha=BASE,
        expected_head=HEAD,
        authority_reference="AUTH:test",
        objective="Perform governed read-only diagnostic.",
        constraints=["NO_MUTATION"],
        timeout_seconds=120,
        scope_patterns=["backend/**"],
        required_capabilities=["READ_ONLY_DIAGNOSTIC"],
        required_tests=["L4"],
    )


def agentic_envelope(workspace_run_id: str) -> L4AgenticResultEnvelope:
    result = {
        "execution": {
            "run_id": "agentic-run-1",
            "project_id": "PALWAKF_LOCAL_AGENTS",
            "task_id": "task-1",
            "state_package_id": "workspace-state-run-1",
            "before_head": HEAD,
            "changed_files": [],
            "final_result": "PASS",
        },
        "experience": {"experience_id": "exp-1"},
        "evaluation": {"evaluation_id": "eval-1", "run_id": "agentic-run-1", "passed": True},
        "learning_bundle": {
            "project_id": "PALWAKF_LOCAL_AGENTS",
            "task_id": "task-1",
            "run_id": "agentic-run-1",
            "source_sha": HEAD,
            "candidates": [],
        },
        "institutional_knowledge_promoted": False,
        "external_review_required": True,
    }
    return L4AgenticResultEnvelope(
        contract_id=CONTRACT_ID,
        workspace_run_id=workspace_run_id,
        correlation_id="corr-1",
        request_sha256="a" * 64,
        result_sha256="b" * 64,
        agentic_result=result,
        resume_token="agentic-resume-1",
    )


def mind_envelope(workspace_run_id: str) -> L4MindReviewEnvelope:
    return L4MindReviewEnvelope(
        contract_id=CONTRACT_ID,
        workspace_run_id=workspace_run_id,
        correlation_id="corr-1",
        request_sha256="c" * 64,
        result_sha256="d" * 64,
        resume_token="mind-resume-1",
        review_result={
            "review_id": "mind-review-1",
            "project_id": "PALWAKF_LOCAL_AGENTS",
            "task_id": "task-1",
            "run_id": "agentic-run-1",
            "candidate_reviews": [],
            "conflict_count": 0,
            "conflict_refs": [],
            "context_authority_status": "CURRENT",
            "promotion_recommendation": "HUMAN_WORKSPACE_REVIEW_REQUIRED",
            "canonical_write_allowed": False,
            "mutation_mode": "READ_ONLY",
        },
    )


def test_l4_roundtrip_persists_and_resumes():
    store = MemoryStateStore()
    service = FourSystemL4OperationalService(store)

    opened = service.open_authority_run(package=package(), correlation_id="corr-1")
    assert opened.stage == "OPENED"
    assert len(opened.checkpoints) == 1

    after_agentic = service.record_agentic(
        opened.workspace_run_id,
        agentic_envelope(opened.workspace_run_id),
    )
    assert after_agentic.stage == "AGENTIC_COMPLETED"

    after_mind = service.record_mind(
        opened.workspace_run_id,
        mind_envelope(opened.workspace_run_id),
    )
    assert after_mind.stage == "MIND_REVIEW_COMPLETED"

    sovereign = service.sovereign_envelope(opened.workspace_run_id)
    assert sovereign["canonical_knowledge_promoted"] is False
    assert len(sovereign["envelope_sha256"]) == 64

    after_ack = service.acknowledge_sovereign(
        opened.workspace_run_id,
        L4SovereignAck(
            drive_document_id="drive-doc-1",
            drive_revision_id="rev-1",
            envelope_sha256=sovereign["envelope_sha256"],
        ),
    )
    assert after_ack.stage == "SOVEREIGN_CHECKPOINT_ACKNOWLEDGED"

    accepted = service.decide(
        opened.workspace_run_id,
        L4DecisionRequest(decision="ACCEPTED", reason="All L4 gates passed."),
    )
    assert accepted.stage == "ACCEPTED"
    assert accepted.decision == "ACCEPTED"

    resumed = FourSystemL4OperationalService(store).get(opened.workspace_run_id)
    assert resumed.stage == "ACCEPTED"
    assert len(resumed.checkpoints) == 5
    assert len({item.chain_sha256 for item in resumed.checkpoints}) == 5


def test_accept_requires_sovereign_checkpoint():
    store = MemoryStateStore()
    service = FourSystemL4OperationalService(store)
    opened = service.open_authority_run(package=package(), correlation_id="corr-1")
    service.record_agentic(opened.workspace_run_id, agentic_envelope(opened.workspace_run_id))
    service.record_mind(opened.workspace_run_id, mind_envelope(opened.workspace_run_id))

    try:
        service.decide(
            opened.workspace_run_id,
            L4DecisionRequest(decision="ACCEPTED", reason="Too early."),
        )
    except Exception as error:
        assert "FOUR_SYSTEM_L4_SOVEREIGN_CHECKPOINT_REQUIRED" in str(error)
    else:
        raise AssertionError("acceptance must fail closed without sovereign checkpoint")


def test_l4_inbound_wire_contract_id_is_required_and_exact():
    agentic = agentic_envelope("l4-wire-agentic").model_dump(mode="json")
    mind = mind_envelope("l4-wire-mind").model_dump(mode="json")
    assert agentic["contract_id"] == CONTRACT_ID
    assert mind["contract_id"] == CONTRACT_ID
    assert L4AgenticResultEnvelope.model_validate(agentic).contract_id == CONTRACT_ID
    assert L4MindReviewEnvelope.model_validate(mind).contract_id == CONTRACT_ID
    missing_agentic = dict(agentic)
    missing_agentic.pop("contract_id")
    missing_mind = dict(mind)
    missing_mind.pop("contract_id")
    with pytest.raises(ValidationError):
        L4AgenticResultEnvelope.model_validate(missing_agentic)
    with pytest.raises(ValidationError):
        L4MindReviewEnvelope.model_validate(missing_mind)
    with pytest.raises(ValidationError):
        L4AgenticResultEnvelope.model_validate({**agentic, "contract_id": "PALWAKF_WRONG_CONTRACT"})
    with pytest.raises(ValidationError):
        L4MindReviewEnvelope.model_validate({**mind, "contract_id": "PALWAKF_WRONG_CONTRACT"})


def test_l4_agentic_wire_payload_with_contract_id_reaches_service():
    store = MemoryStateStore()
    service = FourSystemL4OperationalService(store)
    opened = service.open_authority_run(package=package(), correlation_id="corr-1")
    payload = agentic_envelope(opened.workspace_run_id).model_dump(mode="json")
    recorded = service.record_agentic(opened.workspace_run_id, L4AgenticResultEnvelope.model_validate(payload))
    assert recorded.stage == "AGENTIC_COMPLETED"
    assert recorded.agentic_envelope["contract_id"] == CONTRACT_ID


def test_l4_mind_wire_payload_with_contract_id_reaches_service():
    store = MemoryStateStore()
    service = FourSystemL4OperationalService(store)
    opened = service.open_authority_run(package=package(), correlation_id="corr-1")
    service.record_agentic(opened.workspace_run_id, agentic_envelope(opened.workspace_run_id))
    payload = mind_envelope(opened.workspace_run_id).model_dump(mode="json")
    recorded = service.record_mind(opened.workspace_run_id, L4MindReviewEnvelope.model_validate(payload))
    assert recorded.stage == "MIND_REVIEW_COMPLETED"
    assert recorded.mind_envelope["contract_id"] == CONTRACT_ID

def test_sovereign_ack_identical_replay_survives_lifecycle_progression():
    store = MemoryStateStore()
    service = FourSystemL4OperationalService(store)
    opened = service.open_authority_run(package=package(), correlation_id="corr-1")
    service.record_agentic(
        opened.workspace_run_id,
        agentic_envelope(opened.workspace_run_id),
    )
    service.record_mind(
        opened.workspace_run_id,
        mind_envelope(opened.workspace_run_id),
    )

    sovereign = service.sovereign_envelope(opened.workspace_run_id)
    ack = L4SovereignAck(
        drive_document_id="drive-doc-1",
        drive_revision_id="rev-1",
        envelope_sha256=sovereign["envelope_sha256"],
    )

    after_ack = service.acknowledge_sovereign(opened.workspace_run_id, ack)
    assert after_ack.stage == "SOVEREIGN_CHECKPOINT_ACKNOWLEDGED"
    assert len(after_ack.checkpoints) == 4

    replay_after_ack = service.acknowledge_sovereign(opened.workspace_run_id, ack)
    assert replay_after_ack.stage == "SOVEREIGN_CHECKPOINT_ACKNOWLEDGED"
    assert len(replay_after_ack.checkpoints) == 4

    decision = L4DecisionRequest(
        decision="ACCEPTED",
        reason="All L4 gates passed.",
    )
    accepted = service.decide(opened.workspace_run_id, decision)
    assert accepted.stage == "ACCEPTED"
    assert len(accepted.checkpoints) == 5

    replay_after_accept = service.acknowledge_sovereign(
        opened.workspace_run_id,
        ack,
    )
    assert replay_after_accept.stage == "ACCEPTED"
    assert replay_after_accept.decision == "ACCEPTED"
    assert len(replay_after_accept.checkpoints) == 5

    decision_replay = service.decide(opened.workspace_run_id, decision)
    assert decision_replay.stage == "ACCEPTED"
    assert len(decision_replay.checkpoints) == 5


def test_sovereign_ack_conflicting_replay_fails_closed_without_new_checkpoint():
    store = MemoryStateStore()
    service = FourSystemL4OperationalService(store)
    opened = service.open_authority_run(package=package(), correlation_id="corr-1")
    service.record_agentic(
        opened.workspace_run_id,
        agentic_envelope(opened.workspace_run_id),
    )
    service.record_mind(
        opened.workspace_run_id,
        mind_envelope(opened.workspace_run_id),
    )

    sovereign = service.sovereign_envelope(opened.workspace_run_id)
    ack = L4SovereignAck(
        drive_document_id="drive-doc-1",
        drive_revision_id="rev-1",
        envelope_sha256=sovereign["envelope_sha256"],
    )
    service.acknowledge_sovereign(opened.workspace_run_id, ack)

    conflicting = L4SovereignAck(
        drive_document_id="drive-doc-1",
        drive_revision_id="rev-conflict",
        envelope_sha256=sovereign["envelope_sha256"],
    )

    with pytest.raises(Exception) as exc:
        service.acknowledge_sovereign(opened.workspace_run_id, conflicting)

    assert "FOUR_SYSTEM_L4_SOVEREIGN_ACK_REPLAY_CONFLICT" in str(exc.value)
    persisted = service.get(opened.workspace_run_id)
    assert persisted.stage == "SOVEREIGN_CHECKPOINT_ACKNOWLEDGED"
    assert len(persisted.checkpoints) == 4

