from palwakf_orchestrator.four_system_l4 import (
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
        workspace_run_id=workspace_run_id,
        correlation_id="corr-1",
        request_sha256="a" * 64,
        result_sha256="b" * 64,
        agentic_result=result,
        resume_token="agentic-resume-1",
    )


def mind_envelope(workspace_run_id: str) -> L4MindReviewEnvelope:
    return L4MindReviewEnvelope(
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
