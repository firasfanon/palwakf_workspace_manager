from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    ManualAcknowledgementRequest,
    ManualDispatchMarkRequest,
    ManualResultRequest,
    OperatorTaskStatus,
    TaskCapabilityRequest,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService

HEAD = "d" * 40
AFTER_HEAD = "e" * 40


class FakeVerifier:
    def __init__(self, accepted_heads: set[str] | None = None) -> None:
        self.accepted_heads = accepted_heads if accepted_heads is not None else {HEAD, AFTER_HEAD}
        self.calls = 0

    def verify(self, branch: str, expected_head: str) -> str:
        self.calls += 1
        if expected_head not in self.accepted_heads:
            raise GovernanceError("HEAD drift")
        return expected_head


def create_request(**overrides) -> CreateOperatorTaskRequest:
    data = {
        "task_id": "PALWAKF_SELF_HOSTING_TEST",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "repository": "firasfanon/palwakf_workspace_manager",
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": HEAD,
        "authority_reference": "AUTHORITY://SELF_HOSTING_V1",
        "prompt": "Implement the bounded read-only governed product task.",
        "constraints": ["NO_PRODUCTION", "NO_DATABASE"],
        "approval_policy": "never",
        "sandbox": "workspace-write",
        "max_turns": 4,
        "timeout_seconds": 300,
        "idempotency_key": "palwakf-self-hosting-test",
        "automatic_failure_code": "OPENAI_API_PROJECT_INSUFFICIENT_QUOTA",
    }
    data.update(overrides)
    return CreateOperatorTaskRequest.model_validate(data)


def tool_request(task_id: str = "PALWAKF_SELF_HOSTING_TEST") -> TaskCapabilityRequest:
    return TaskCapabilityRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        required_capability_ids=[],
        optional_capability_ids=[],
        task_type="backend-repository",
        mutation_class="source-write",
        environment="local",
        data_classification="internal",
        acceptance_requirements=["tests", "evidence"],
    )


def test_automatic_failure_enables_idempotent_manual_package(tmp_path: Path) -> None:
    verifier = FakeVerifier()
    service = OperatorService(tmp_path, verifier=verifier)
    task = service.create_task(create_request())

    first = service.generate_manual_package(task.task_id)
    second = service.generate_manual_package(task.task_id)

    assert first == second
    assert first.package_receipt.startswith("manual-")
    assert first.automatic_connectivity_acceptance is False
    assert first.canonical_envelope_sha256 == second.canonical_envelope_sha256
    assert "OPENAI_API_KEY" not in first.model_dump_json()
    assert verifier.calls == 2


def test_secret_like_value_is_rejected_before_task_persistence(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())

    with pytest.raises(GovernanceError, match="secret-like"):
        service.create_task(
            create_request(
                constraints=[
                    "api_key=" + "dummy-" + "secret-like-value",
                ]
            )
        )


def test_head_drift_blocks_manual_package(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier(set()))
    task = service.create_task(create_request())

    with pytest.raises(GovernanceError, match="HEAD drift"):
        service.generate_manual_package(task.task_id)


def test_manual_result_remains_pending_until_independent_verification(
    tmp_path: Path,
) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(create_request())
    package = service.generate_manual_package(task.task_id)
    service.mark_manual_dispatched(
        task.task_id,
        ManualDispatchMarkRequest(package_receipt=package.package_receipt),
    )
    service.record_manual_ack(
        task.task_id,
        ManualAcknowledgementRequest(
            package_receipt=package.package_receipt,
            thread_reference="thread-live-001",
        ),
    )

    result = service.import_manual_result(
        task.task_id,
        ManualResultRequest(
            package_receipt=package.package_receipt,
            thread_reference="thread-live-001",
            before_head=HEAD,
            after_head=AFTER_HEAD,
            commit_sha=AFTER_HEAD,
            result_summary="Bounded change completed",
            changed_files=["orchestrator/api.py"],
            tests=["pytest:pass"],
            evidence=["evidence/checkpoint.json"],
        ),
    )

    assert result.status == OperatorTaskStatus.pending_verification
    assert result.verification_receipt is None
    verified = service.verify_task(
        task.task_id,
        VerificationRequest(
            verification_receipt="github-actions-run-001",
            ci_status="success",
            verified_head=AFTER_HEAD,
        ),
    )
    assert verified.status == OperatorTaskStatus.verified


def test_result_import_fails_closed_on_drift(tmp_path: Path) -> None:
    verifier = FakeVerifier({HEAD})
    service = OperatorService(tmp_path, verifier=verifier)
    task = service.create_task(create_request())
    package = service.generate_manual_package(task.task_id)
    service.mark_manual_dispatched(
        task.task_id,
        ManualDispatchMarkRequest(package_receipt=package.package_receipt),
    )
    service.record_manual_ack(
        task.task_id,
        ManualAcknowledgementRequest(
            package_receipt=package.package_receipt,
            thread_reference="thread-live-001",
        ),
    )

    with pytest.raises(GovernanceError, match="HEAD drift"):
        service.import_manual_result(
            task.task_id,
            ManualResultRequest(
                package_receipt=package.package_receipt,
                thread_reference="thread-live-001",
                before_head=HEAD,
                after_head=AFTER_HEAD,
                commit_sha=AFTER_HEAD,
                result_summary="Result",
                changed_files=[],
                tests=[],
                evidence=[],
            ),
        )


def test_cancel_is_idempotent(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(create_request())

    first = service.cancel_task(task.task_id)
    event_count = len(first.events)
    second = service.cancel_task(task.task_id)

    assert first.status == OperatorTaskStatus.cancelled
    assert second.status == OperatorTaskStatus.cancelled
    assert len(second.events) == event_count


@pytest.mark.asyncio
async def test_no_dispatch_occurs_before_tool_decisions_are_persisted(
    tmp_path: Path,
) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(create_request())

    with pytest.raises(GovernanceError, match="tool decisions"):
        await service.dispatch_task(task.task_id)

    service.plan_tools(task.task_id, tool_request())
    failed = await service.dispatch_task(task.task_id)
    assert failed.status == OperatorTaskStatus.failed
    assert failed.thread_id is None


def test_tool_plan_and_actual_reconciliation_are_separate(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(create_request())
    plan = service.plan_tools(task.task_id, tool_request())

    assert plan.dispatch_blocked is False
    reconciliation = service.reconcile_tools(task.task_id)
    assert reconciliation.reconciled is False
    assert reconciliation.actual_adapter_ids == []


@pytest.mark.asyncio
async def test_workspace_write_routes_to_governed_relay_instead_of_autonomous_codex(
    tmp_path: Path,
) -> None:
    service = OperatorService(
        tmp_path,
        verifier=FakeVerifier(),
        automatic_agents_available=True,
    )
    from palwakf_orchestrator.operator_contracts import TaskAuthorizationRequest

    task = service.create_task(
        create_request(
            task_id="PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1",
            automatic_failure_code=None,
            requires_explicit_authorization=True,
        )
    )
    service.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=HEAD,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="test-governance",
    )
    plan = service.plan_tools(task.task_id, tool_request(task.task_id))

    assert plan.dispatch_blocked is False
    assert any(
        decision.capability_id == "governed.patch_relay" and decision.selected_adapter_id == "codex"
        for decision in plan.decisions
    )

    result = await service.dispatch_task(task.task_id)

    assert result.status == OperatorTaskStatus.failed
    assert result.blocker == "AUTONOMOUS_DEVELOPMENT_SUSPENDED_BY_POLICY"
    package = service.generate_manual_package(task.task_id)
    assert package.relay_provider_id == "codex"
