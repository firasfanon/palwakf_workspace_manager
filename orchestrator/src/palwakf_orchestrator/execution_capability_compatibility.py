from __future__ import annotations

import hashlib
import json
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    ManualAcknowledgementRequest,
    ManualDispatchMarkRequest,
    ManualDispatchPackage,
    ManualResultRequest,
    OperatorTaskRecord,
    ProjectCapabilityProfile,
    RuntimeCapabilities,
    TaskCapabilityRequest,
    ToolInvocationReceipt,
    ToolPlanResponse,
    ToolReconciliation,
    ToolSelectionDecision,
)


class CanonicalCapabilityArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_type: str
    canonical_json: str
    sha256: str


class ExecutionCapabilityCompatibilitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    operator_task: CanonicalCapabilityArtifact
    manual_dispatch_package: CanonicalCapabilityArtifact | None
    tool_plan: CanonicalCapabilityArtifact | None
    tool_invocations: tuple[CanonicalCapabilityArtifact, ...]
    reconciliation: CanonicalCapabilityArtifact | None


class LegacyExecutionApiContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: Literal["GET", "POST"]
    path: str
    response_model: str


LEGACY_EXECUTION_API_CONTRACTS: Final[tuple[LegacyExecutionApiContract, ...]] = (
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/capabilities",
        response_model="RuntimeCapabilities",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/capability-registry",
        response_model="dict[str,object]",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/projects/{project_id}/tool-profile",
        response_model="ProjectCapabilityProfile",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/tasks",
        response_model="list[OperatorTaskRecord]",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/tasks/{task_id}",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/dispatch",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/authorize",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/continue",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/cancel",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/verify",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/manual-package",
        response_model="ManualDispatchPackage",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/manual-dispatched",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/manual-ack",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/manual-result",
        response_model="OperatorTaskRecord",
    ),
    LegacyExecutionApiContract(
        method="POST",
        path="/v1/tasks/{task_id}/tool-plan",
        response_model="ToolPlanResponse",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/tasks/{task_id}/tool-decisions",
        response_model="ToolPlanResponse",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/tasks/{task_id}/tool-invocations",
        response_model="list[ToolInvocationReceipt]",
    ),
    LegacyExecutionApiContract(
        method="GET",
        path="/v1/tasks/{task_id}/tool-reconciliation",
        response_model="ToolReconciliation",
    ),
)


ADVANCED_CONTRACT_FIELD_INVENTORY: Final[dict[str, tuple[str, ...]]] = {
    "RuntimeCapabilities": (
        "version",
        "task_lifecycle",
        "manual_relay_fallback",
        "capability_routing",
        "tool_decision_trace",
        "planned_actual_reconciliation",
        "automatic_agents_available",
        "database_connected",
        "production_mutation",
        "secret_values_exposed",
    ),
    "ProjectCapabilityProfile": (
        "project_id",
        "project_type",
        "domain_tags",
        "stack",
        "required_capabilities",
        "conditional_capabilities",
        "prohibited_capabilities",
        "preferred_adapters",
        "fallback_adapters",
        "environment_boundaries",
        "approval_classes",
        "evidence_requirements",
        "profile_source",
        "profile_version",
    ),
    "ManualDispatchPackage": (
        "package_receipt",
        "task_id",
        "repository",
        "branch",
        "expected_head",
        "authority_reference",
        "prompt",
        "constraints",
        "approval_policy",
        "sandbox",
        "timeout_seconds",
        "max_turns",
        "idempotency_key",
        "canonical_envelope_sha256",
        "automatic_failure_code",
        "relay_provider_id",
        "generated_at",
        "automatic_connectivity_acceptance",
    ),
    "ManualDispatchMarkRequest": ("package_receipt",),
    "ManualAcknowledgementRequest": (
        "package_receipt",
        "thread_reference",
    ),
    "ManualResultRequest": (
        "package_receipt",
        "thread_reference",
        "before_head",
        "after_head",
        "commit_sha",
        "result_summary",
        "changed_files",
        "tests",
        "evidence",
    ),
    "TaskCapabilityRequest": (
        "task_id",
        "project_id",
        "required_capability_ids",
        "optional_capability_ids",
        "task_type",
        "mutation_class",
        "environment",
        "data_classification",
        "acceptance_requirements",
    ),
    "ToolSelectionDecision": (
        "capability_id",
        "selected_adapter_id",
        "fallback_adapter_id",
        "selected_reason",
        "excluded_adapters_with_reason",
        "permission_status",
        "approval_required",
        "invocation_order",
        "evidence_contract",
        "decision_timestamp",
        "registry_version",
        "blocked",
        "substituted",
    ),
    "ToolPlanResponse": (
        "task_id",
        "project_id",
        "decisions",
        "dispatch_blocked",
        "blockers",
    ),
    "ToolInvocationReceipt": (
        "invocation_id",
        "task_id",
        "capability_id",
        "adapter_id",
        "status",
        "evidence",
        "occurred_at",
        "tool_call_id",
        "command_summary",
        "output_excerpt",
        "exit_code",
    ),
    "ToolReconciliation": (
        "task_id",
        "planned_adapter_ids",
        "actual_adapter_ids",
        "missing_adapter_ids",
        "unexpected_adapter_ids",
        "reconciled",
    ),
}


_ADVANCED_CONTRACT_MODELS: Final[dict[str, type[BaseModel]]] = {
    "RuntimeCapabilities": RuntimeCapabilities,
    "ProjectCapabilityProfile": ProjectCapabilityProfile,
    "ManualDispatchPackage": ManualDispatchPackage,
    "ManualDispatchMarkRequest": ManualDispatchMarkRequest,
    "ManualAcknowledgementRequest": ManualAcknowledgementRequest,
    "ManualResultRequest": ManualResultRequest,
    "TaskCapabilityRequest": TaskCapabilityRequest,
    "ToolSelectionDecision": ToolSelectionDecision,
    "ToolPlanResponse": ToolPlanResponse,
    "ToolInvocationReceipt": ToolInvocationReceipt,
    "ToolReconciliation": ToolReconciliation,
}


def current_advanced_contract_field_inventory() -> dict[str, tuple[str, ...]]:
    return {name: tuple(model.model_fields) for name, model in _ADVANCED_CONTRACT_MODELS.items()}


def build_execution_capability_compatibility_snapshot(
    task: OperatorTaskRecord,
    *,
    manual_dispatch_package: ManualDispatchPackage | None = None,
    tool_plan: ToolPlanResponse | None = None,
    tool_invocations: list[ToolInvocationReceipt] | tuple[ToolInvocationReceipt, ...] = (),
    reconciliation: ToolReconciliation | None = None,
) -> ExecutionCapabilityCompatibilitySnapshot:
    _assert_task_identity(
        task.task_id, manual_dispatch_package, tool_plan, tool_invocations, reconciliation
    )
    _assert_reconciliation_consistency(tool_plan, tool_invocations, reconciliation)

    return ExecutionCapabilityCompatibilitySnapshot(
        task_id=task.task_id,
        operator_task=_canonical_artifact("OperatorTaskRecord", task),
        manual_dispatch_package=(
            _canonical_artifact("ManualDispatchPackage", manual_dispatch_package)
            if manual_dispatch_package is not None
            else None
        ),
        tool_plan=(
            _canonical_artifact("ToolPlanResponse", tool_plan) if tool_plan is not None else None
        ),
        tool_invocations=tuple(
            _canonical_artifact("ToolInvocationReceipt", invocation)
            for invocation in tool_invocations
        ),
        reconciliation=(
            _canonical_artifact("ToolReconciliation", reconciliation)
            if reconciliation is not None
            else None
        ),
    )


def _assert_task_identity(
    task_id: str,
    manual_dispatch_package: ManualDispatchPackage | None,
    tool_plan: ToolPlanResponse | None,
    tool_invocations: list[ToolInvocationReceipt] | tuple[ToolInvocationReceipt, ...],
    reconciliation: ToolReconciliation | None,
) -> None:
    artifacts = (
        ("MANUAL_PACKAGE", manual_dispatch_package),
        ("TOOL_PLAN", tool_plan),
        ("RECONCILIATION", reconciliation),
    )
    for label, artifact in artifacts:
        if artifact is not None and artifact.task_id != task_id:
            raise GovernanceError(f"EXECUTION_CAPABILITY_{label}_TASK_ID_DRIFT")

    if any(invocation.task_id != task_id for invocation in tool_invocations):
        raise GovernanceError("EXECUTION_CAPABILITY_INVOCATION_TASK_ID_DRIFT")


def _assert_reconciliation_consistency(
    tool_plan: ToolPlanResponse | None,
    tool_invocations: list[ToolInvocationReceipt] | tuple[ToolInvocationReceipt, ...],
    reconciliation: ToolReconciliation | None,
) -> None:
    if reconciliation is None:
        return
    if tool_plan is None:
        raise GovernanceError("EXECUTION_CAPABILITY_RECONCILIATION_WITHOUT_PLAN")

    planned = [
        decision.selected_adapter_id
        for decision in tool_plan.decisions
        if decision.selected_adapter_id
    ]
    actual = [
        invocation.adapter_id for invocation in tool_invocations if invocation.status == "completed"
    ]
    missing = [adapter for adapter in planned if adapter not in actual]
    unexpected = [adapter for adapter in actual if adapter not in planned]

    if reconciliation.planned_adapter_ids != planned:
        raise GovernanceError("EXECUTION_CAPABILITY_RECONCILIATION_PLANNED_DRIFT")
    if reconciliation.actual_adapter_ids != actual:
        raise GovernanceError("EXECUTION_CAPABILITY_RECONCILIATION_ACTUAL_DRIFT")
    if reconciliation.missing_adapter_ids != missing:
        raise GovernanceError("EXECUTION_CAPABILITY_RECONCILIATION_MISSING_DRIFT")
    if reconciliation.unexpected_adapter_ids != unexpected:
        raise GovernanceError("EXECUTION_CAPABILITY_RECONCILIATION_UNEXPECTED_DRIFT")
    if reconciliation.reconciled != (not missing and not unexpected):
        raise GovernanceError("EXECUTION_CAPABILITY_RECONCILIATION_STATUS_DRIFT")


def _canonical_artifact(
    artifact_type: str,
    artifact: BaseModel,
) -> CanonicalCapabilityArtifact:
    canonical_json = json.dumps(
        artifact.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return CanonicalCapabilityArtifact(
        artifact_type=artifact_type,
        canonical_json=canonical_json,
        sha256=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    )
