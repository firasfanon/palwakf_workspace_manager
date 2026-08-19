from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, get_args, get_origin

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from palwakf_orchestrator.api import _add_legacy_routes
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_capability_compatibility import (
    ADVANCED_CONTRACT_FIELD_INVENTORY,
    LEGACY_EXECUTION_API_CONTRACTS,
    build_execution_capability_compatibility_snapshot,
    current_advanced_contract_field_inventory,
)
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    ManualAcknowledgementRequest,
    ManualDispatchMarkRequest,
    ManualDispatchPackage,
    ManualResultRequest,
    OperatorTaskRecord,
    OperatorTaskStatus,
    PermissionStatus,
    TaskCapabilityRequest,
    ToolInvocationReceipt,
    ToolPlanResponse,
    ToolReconciliation,
    ToolSelectionDecision,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore

HEAD = "d" * 40
AFTER_HEAD = "e" * 40
TASK_ID = "PALWAKF_PHASE3_COMPATIBILITY_TEST"
PROJECT_ID = "PALWAKF_WORKSPACE_MANAGER"
REPOSITORY = "firasfanon/palwakf_workspace_manager"
NOW = datetime(2026, 8, 17, 1, 10, tzinfo=UTC)


class FakeVerifier:
    def __init__(self, accepted_heads: set[str] | None = None) -> None:
        self.accepted_heads = accepted_heads if accepted_heads is not None else {HEAD, AFTER_HEAD}

    def verify(self, branch: str, expected_head: str) -> str:
        if expected_head not in self.accepted_heads:
            raise GovernanceError("HEAD drift")
        return expected_head


def create_request(**overrides: object) -> CreateOperatorTaskRequest:
    data: dict[str, object] = {
        "task_id": TASK_ID,
        "project_id": PROJECT_ID,
        "repository": REPOSITORY,
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": HEAD,
        "authority_reference": "AUTHORITY://PHASE3_EXECUTION_COMPATIBILITY",
        "prompt": "Preserve the bounded execution capability and contract compatibility surface.",
        "constraints": ["NO_UI", "NO_MIGRATION", "NO_REMOTE_CONNECTIVITY"],
        "approval_policy": "never",
        "sandbox": "read-only",
        "max_turns": 4,
        "timeout_seconds": 300,
        "idempotency_key": "palwakf-phase3-compatibility-test",
        "automatic_failure_code": "AUTOMATIC_CHANNEL_UNAVAILABLE",
        "manual_fallback_selected": True,
        "requires_explicit_authorization": False,
    }
    data.update(overrides)
    return CreateOperatorTaskRequest.model_validate(data)


def tool_request(task_id: str = TASK_ID) -> TaskCapabilityRequest:
    return TaskCapabilityRequest(
        task_id=task_id,
        project_id=PROJECT_ID,
        required_capability_ids=[],
        optional_capability_ids=[],
        task_type="backend-repository",
        mutation_class="read-only",
        environment="local",
        data_classification="internal",
        acceptance_requirements=["tests", "evidence"],
    )


def manual_package(task_id: str = TASK_ID) -> ManualDispatchPackage:
    return ManualDispatchPackage(
        package_receipt="manual-phase3-compatibility",
        task_id=task_id,
        repository=REPOSITORY,
        branch="agent/workspace-manager-foundation-v1",
        expected_head=HEAD,
        authority_reference="AUTHORITY://PHASE3_EXECUTION_COMPATIBILITY",
        prompt="Preserve the bounded execution capability and contract compatibility surface.",
        constraints=["NO_UI", "NO_MIGRATION", "NO_REMOTE_CONNECTIVITY"],
        approval_policy="never",
        sandbox="read-only",
        timeout_seconds=300,
        max_turns=4,
        idempotency_key="palwakf-phase3-compatibility-test",
        canonical_envelope_sha256="a" * 64,
        automatic_failure_code="AUTOMATIC_CHANNEL_UNAVAILABLE",
        relay_provider_id="codex",
        generated_at=NOW,
        automatic_connectivity_acceptance=False,
    )


def manual_operator_record(tmp_path: Path) -> OperatorTaskRecord:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    return service.create_task(create_request())


def plan_response(task_id: str = TASK_ID) -> ToolPlanResponse:
    return ToolPlanResponse(
        task_id=task_id,
        project_id=PROJECT_ID,
        decisions=[
            ToolSelectionDecision(
                capability_id="repository.read",
                selected_adapter_id="github",
                fallback_adapter_id="local_git",
                selected_reason="Repository truth is authoritative on GitHub.",
                excluded_adapters_with_reason=[],
                permission_status=PermissionStatus.authorized,
                approval_required=False,
                invocation_order=1,
                evidence_contract=["REPOSITORY_HEAD"],
                decision_timestamp=NOW,
                registry_version="PHASE3_TEST",
                blocked=False,
                substituted=False,
            )
        ],
        dispatch_blocked=False,
        blockers=[],
    )


def invocation(task_id: str = TASK_ID) -> ToolInvocationReceipt:
    return ToolInvocationReceipt(
        invocation_id="inv-phase3-001",
        task_id=task_id,
        capability_id="repository.read",
        adapter_id="github",
        status="completed",
        evidence=["REPOSITORY_HEAD"],
        occurred_at=NOW,
        tool_call_id="tool-call-1",
        command_summary="Read repository head",
        output_excerpt="f840dcf",
        exit_code=0,
    )


def reconciliation(task_id: str = TASK_ID) -> ToolReconciliation:
    return ToolReconciliation(
        task_id=task_id,
        planned_adapter_ids=["github"],
        actual_adapter_ids=["github"],
        missing_adapter_ids=[],
        unexpected_adapter_ids=[],
        reconciled=True,
    )


def canonical(model: object) -> str:
    payload = cast(
        OperatorTaskRecord
        | ManualDispatchPackage
        | ToolPlanResponse
        | ToolInvocationReceipt
        | ToolReconciliation,
        model,
    )
    return json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def response_model_label(value: object) -> str:
    origin = get_origin(value)
    if origin is list:
        item = get_args(value)[0]
        return f"list[{item.__name__}]"
    if origin is dict:
        key, item = get_args(value)
        return f"dict[{key.__name__},{item.__name__}]"
    if isinstance(value, type):
        return value.__name__
    return str(value)


def test_cpm13_manual_dispatch_package_projection_is_exact(tmp_path: Path) -> None:
    task = manual_operator_record(tmp_path)
    package = manual_package()

    snapshot = build_execution_capability_compatibility_snapshot(
        task,
        manual_dispatch_package=package,
    )

    assert snapshot.manual_dispatch_package is not None
    assert snapshot.manual_dispatch_package.canonical_json == canonical(package)
    assert (
        snapshot.manual_dispatch_package.sha256
        == hashlib.sha256(canonical(package).encode("utf-8")).hexdigest()
    )


def test_cpm13_plan_invocation_and_reconciliation_projection_is_exact(tmp_path: Path) -> None:
    task = manual_operator_record(tmp_path)
    plan = plan_response()
    actual = invocation()
    result = reconciliation()

    snapshot = build_execution_capability_compatibility_snapshot(
        task,
        tool_plan=plan,
        tool_invocations=[actual],
        reconciliation=result,
    )

    assert snapshot.tool_plan is not None
    assert snapshot.tool_plan.canonical_json == canonical(plan)
    assert len(snapshot.tool_invocations) == 1
    assert snapshot.tool_invocations[0].canonical_json == canonical(actual)
    assert snapshot.reconciliation is not None
    assert snapshot.reconciliation.canonical_json == canonical(result)


def test_cpm13_projection_rejects_cross_task_artifact_drift(tmp_path: Path) -> None:
    task = manual_operator_record(tmp_path)

    with pytest.raises(
        GovernanceError,
        match="EXECUTION_CAPABILITY_MANUAL_PACKAGE_TASK_ID_DRIFT",
    ):
        build_execution_capability_compatibility_snapshot(
            task,
            manual_dispatch_package=manual_package("OTHER_TASK"),
        )

    with pytest.raises(
        GovernanceError,
        match="EXECUTION_CAPABILITY_INVOCATION_TASK_ID_DRIFT",
    ):
        build_execution_capability_compatibility_snapshot(
            task,
            tool_invocations=[invocation("OTHER_TASK")],
        )


def test_cpm13_projection_rejects_reconciliation_drift(tmp_path: Path) -> None:
    task = manual_operator_record(tmp_path)
    drifted = reconciliation().model_copy(
        update={
            "actual_adapter_ids": ["local_git"],
            "unexpected_adapter_ids": ["local_git"],
            "reconciled": False,
        }
    )

    with pytest.raises(
        GovernanceError,
        match="EXECUTION_CAPABILITY_RECONCILIATION_ACTUAL_DRIFT",
    ):
        build_execution_capability_compatibility_snapshot(
            task,
            tool_plan=plan_response(),
            tool_invocations=[invocation()],
            reconciliation=drifted,
        )


def test_cpm13_manual_relay_still_requires_independent_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    monkeypatch.setattr(
        service,
        "_changed_files",
        lambda before_head, after_head: ["orchestrator/src/example.py"],
    )
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
            thread_reference="phase3-thread-001",
        ),
    )
    imported = service.import_manual_result(
        task.task_id,
        ManualResultRequest(
            package_receipt=package.package_receipt,
            thread_reference="phase3-thread-001",
            before_head=HEAD,
            after_head=AFTER_HEAD,
            commit_sha=AFTER_HEAD,
            result_summary="Compatibility-preserving bounded result",
            changed_files=["orchestrator/src/example.py"],
            tests=["pytest:pass"],
            evidence=["evidence/phase3.json"],
        ),
    )

    assert imported.status == OperatorTaskStatus.pending_verification
    assert imported.verification_receipt is None

    verified = service.verify_task(
        task.task_id,
        VerificationRequest(
            verification_receipt="phase3-independent-verification",
            ci_status="success",
            verified_head=AFTER_HEAD,
        ),
    )
    assert verified.status == OperatorTaskStatus.verified


def test_cpm13_tool_plan_and_actual_reconciliation_remain_separate(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    task = service.create_task(create_request())
    plan = service.plan_tools(task.task_id, tool_request())

    assert plan.dispatch_blocked is False
    result = service.reconcile_tools(task.task_id)

    assert result.actual_adapter_ids == []
    assert result.reconciled is False
    assert result.missing_adapter_ids


def test_cpm13_persistence_roundtrip_preserves_manual_package_and_tool_plan(
    tmp_path: Path,
) -> None:
    store = MemoryStateStore()
    first = OperatorService(tmp_path, verifier=FakeVerifier(), state_store=store)
    task = first.create_task(create_request())
    package = first.generate_manual_package(task.task_id)
    plan = first.plan_tools(task.task_id, tool_request())

    restored = OperatorService(tmp_path, verifier=FakeVerifier(), state_store=store)

    assert restored.get_task(task.task_id) == first.get_task(task.task_id)
    assert restored.generate_manual_package(task.task_id) == package
    assert restored.tool_decisions(task.task_id) == plan


def test_cpm16_legacy_execution_routes_remain_present(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    app = FastAPI()
    connected = cast(ConnectedApplicationService, object())
    _add_legacy_routes(app, service, connected)

    actual = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method in {"GET", "POST"}
    }
    expected = {(item.method, item.path) for item in LEGACY_EXECUTION_API_CONTRACTS}

    assert actual == expected


def test_cpm16_legacy_execution_response_models_remain_compatible(tmp_path: Path) -> None:
    service = OperatorService(tmp_path, verifier=FakeVerifier())
    app = FastAPI()
    connected = cast(ConnectedApplicationService, object())
    _add_legacy_routes(app, service, connected)

    routes = {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method in {"GET", "POST"}
    }

    for contract in LEGACY_EXECUTION_API_CONTRACTS:
        route = routes[(contract.method, contract.path)]
        assert response_model_label(route.response_model) == contract.response_model


def test_cpm16_advanced_contract_field_inventories_are_locked() -> None:
    assert current_advanced_contract_field_inventory() == ADVANCED_CONTRACT_FIELD_INVENTORY
