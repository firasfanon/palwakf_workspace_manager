from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from palwakf_orchestrator.capability_router import (
    CapabilityRegistry,
    CapabilityRouter,
    workspace_manager_profile,
)
from palwakf_orchestrator.contracts import DispatchRequest
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    DispatchMode,
    ManualAcknowledgementRequest,
    ManualDispatchMarkRequest,
    ManualDispatchPackage,
    ManualResultRequest,
    OperatorTaskRecord,
    OperatorTaskStatus,
    ProjectCapabilityProfile,
    RuntimeCapabilities,
    TaskAuthorizationRequest,
    TaskCapabilityRequest,
    TaskEvent,
    ToolInvocationReceipt,
    ToolPlanResponse,
    ToolReconciliation,
    VerificationRequest,
)
from palwakf_orchestrator.persistence import MemoryStateStore, StateStore
from palwakf_orchestrator.service import OrchestratorService

SECRET_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._-]{16,}|"
    r"(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
SELF_HOSTED_PROOF_TASK_ID = "PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1"


class RepositoryVerifier(Protocol):
    def verify(self, branch: str, expected_head: str) -> str: ...


class GitRepositoryVerifier:
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace.resolve()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self._workspace), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise GovernanceError(f"git {' '.join(args)} failed: {detail}")
        return result.stdout.strip()

    def verify(self, branch: str, expected_head: str) -> str:
        actual_branch = self._git("branch", "--show-current")
        local_head = self._git("rev-parse", "HEAD")
        remote_line = self._git("ls-remote", "origin", f"refs/heads/{branch}")
        remote_head = remote_line.split(maxsplit=1)[0] if remote_line else ""
        dirty = self._git("status", "--porcelain")
        if actual_branch != branch:
            raise GovernanceError(
                f"branch mismatch: expected {branch}, got {actual_branch or '<detached>'}"
            )
        if local_head != expected_head or remote_head != expected_head:
            raise GovernanceError(
                f"HEAD drift: expected {expected_head}, local {local_head}, "
                f"remote {remote_head or '<missing>'}"
            )
        if dirty:
            raise GovernanceError("worktree is not clean")
        return local_head


class OperatorService:
    def __init__(
        self,
        workspace: Path,
        *,
        orchestrator: OrchestratorService | None = None,
        verifier: RepositoryVerifier | None = None,
        registry: CapabilityRegistry | None = None,
        automatic_agents_available: bool = False,
        state_store: StateStore | None = None,
    ) -> None:
        self._workspace = workspace.resolve()
        self._orchestrator = orchestrator
        self._verifier = verifier or GitRepositoryVerifier(self._workspace)
        self._registry = registry or CapabilityRegistry()
        self._router = CapabilityRouter(self._registry)
        self._automatic_agents_available = automatic_agents_available
        self._state_store = state_store or MemoryStateStore()
        self._tasks: dict[str, OperatorTaskRecord] = {}
        self._idempotency_tasks: dict[str, str] = {}
        self._manual_packages: dict[str, ManualDispatchPackage] = {}
        self._tool_plans: dict[str, ToolPlanResponse] = {}
        self._invocations: dict[str, list[ToolInvocationReceipt]] = {}
        self._restore()

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            version="SELF_HOSTING_OPERATIONAL_LOOP_V1",
            automatic_agents_available=self._automatic_agents_available,
        )

    def registry_snapshot(self) -> dict[str, object]:
        return self._registry.public_snapshot()

    def project_profile(self, project_id: str) -> ProjectCapabilityProfile:
        profile = workspace_manager_profile()
        if project_id != profile.project_id:
            raise GovernanceError(f"unknown project capability profile: {project_id}")
        return profile

    def create_task(self, request: CreateOperatorTaskRequest) -> OperatorTaskRecord:
        existing_task_id = self._idempotency_tasks.get(request.idempotency_key)
        if existing_task_id:
            existing = self._tasks[existing_task_id]
            comparable = CreateOperatorTaskRequest.model_validate(
                {key: getattr(existing, key) for key in CreateOperatorTaskRequest.model_fields}
            )
            if comparable != request:
                raise GovernanceError("idempotency key already belongs to a different envelope")
            return existing
        if request.task_id in self._tasks:
            raise GovernanceError("task_id already exists with a different idempotency key")
        self._assert_secret_free(request.model_dump(mode="json"))
        now = datetime.now(UTC)
        blocker = request.automatic_failure_code
        event = TaskEvent(
            event_type="TASK_CREATED",
            status=OperatorTaskStatus.pending,
            message="Governed operator task envelope persisted",
            occurred_at=now,
        )
        record = OperatorTaskRecord(
            **request.model_dump(),
            dispatch_mode=DispatchMode.automatic,
            status=OperatorTaskStatus.pending,
            created_at=now,
            updated_at=now,
            last_event=event.event_type,
            blocker=blocker,
            events=[event],
        )
        self._tasks[request.task_id] = record
        self._idempotency_tasks[request.idempotency_key] = request.task_id
        self._persist()
        return record

    def list_tasks(self) -> list[OperatorTaskRecord]:
        return sorted(
            self._tasks.values(),
            key=lambda task: task.created_at,
            reverse=True,
        )

    def get_task(self, task_id: str) -> OperatorTaskRecord:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise GovernanceError(f"unknown task: {task_id}") from exc

    def authorize_task(
        self,
        task_id: str,
        request: TaskAuthorizationRequest,
        *,
        principal_id: str,
    ) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if not task.requires_explicit_authorization:
            raise GovernanceError("task does not require explicit authorization")
        if task.expected_head != request.expected_head:
            raise GovernanceError("authorization HEAD does not match task authority")
        if task.authority_reference != request.authority_reference:
            raise GovernanceError("authorization reference does not match task authority")
        if task.authorized_at is not None:
            return task
        task.authorized_at = datetime.now(UTC)
        task.authorized_by = principal_id
        return self._transition(
            task,
            task.status,
            "TASK_AUTHORIZED",
            "Explicit governed execution authorization persisted",
            blocker=None,
        )

    def bind_client(
        self,
        task_id: str,
        *,
        client_id: str,
        correlation_id: str,
        execution_host_id: str,
        tool_executor_id: str,
    ) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.execution_host_id and task.execution_host_id != execution_host_id:
            raise GovernanceError(
                "cross-host resume rejected: explicit migration handshake is required"
            )
        if task.tool_executor_id and task.tool_executor_id != tool_executor_id:
            raise GovernanceError(
                "cross-executor resume rejected: explicit migration handshake is required"
            )
        task.client_id = client_id
        task.correlation_id = correlation_id
        task.execution_host_id = execution_host_id
        task.tool_executor_id = tool_executor_id
        self._persist()
        return task

    def queue_task(self, task_id: str) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.status == OperatorTaskStatus.queued:
            return task
        task.queued_at = datetime.now(UTC)
        return self._transition(
            task,
            OperatorTaskStatus.queued,
            "TASK_QUEUED",
            "Task accepted into the bounded dispatch queue",
            blocker=None,
        )

    def start_task(self, task_id: str) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        task.started_at = datetime.now(UTC)
        if task.queued_at:
            task.dispatch_latency_ms = int(
                (task.started_at - task.queued_at).total_seconds() * 1000
            )
        return self._transition(
            task,
            OperatorTaskStatus.running,
            "TASK_EXECUTION_STARTED",
            "A bounded worker started task execution",
            blocker=None,
        )

    def recover_interrupted_tasks(self) -> list[str]:
        recovered: list[str] = []
        for task in self._tasks.values():
            if task.status in {OperatorTaskStatus.queued, OperatorTaskStatus.running}:
                task.status = OperatorTaskStatus.failed
                task.blocker = "SERVICE_RESTART_INTERRUPTED_EXECUTION"
                task.updated_at = datetime.now(UTC)
                task.last_event = "TASK_RECOVERED_AFTER_RESTART"
                task.events.append(
                    TaskEvent(
                        event_type=task.last_event,
                        status=task.status,
                        message="Interrupted task recovered without duplicate execution",
                        occurred_at=task.updated_at,
                        correlation_id=task.correlation_id,
                        client_id=task.client_id,
                    )
                )
                recovered.append(task.task_id)
        if recovered:
            self._persist()
        return recovered

    async def dispatch_task(self, task_id: str) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.requires_explicit_authorization and task.authorized_at is None:
            raise GovernanceError("explicit task authorization is required before dispatch")
        plan = self._tool_plans.get(task_id)
        if plan is None:
            raise GovernanceError("tool decisions must be persisted before dispatch")
        workspace_write = task.sandbox == "workspace-write"
        if plan.dispatch_blocked:
            raise GovernanceError("tool plan contains a blocked required capability")
        if task.status == OperatorTaskStatus.cancelled:
            raise GovernanceError("cancelled task cannot be dispatched")
        if task.execution_receipt:
            return task
        if task.automatic_failure_code or not self._automatic_agents_available:
            code = task.automatic_failure_code or "AUTOMATIC_CHANNEL_UNAVAILABLE"
            return self._transition(
                task,
                OperatorTaskStatus.failed,
                "AUTOMATIC_DISPATCH_FAILED",
                code,
                blocker=code,
            )
        if workspace_write and (
            task.task_id != SELF_HOSTED_PROOF_TASK_ID or not task.requires_explicit_authorization
        ):
            raise GovernanceError("workspace-write is restricted to the governed proof task")
        if self._orchestrator is None:
            raise GovernanceError("automatic orchestrator is unavailable")

        response = await self._orchestrator.dispatch(
            DispatchRequest.model_validate(
                {
                    "task_id": task.task_id,
                    "prompt": task.prompt,
                    "repository": task.repository,
                    "branch": task.branch,
                    "expected_head": task.expected_head,
                    "idempotency_key": task.idempotency_key,
                    "boundaries": {
                        "workspace_write": workspace_write,
                        "database_write": False,
                        "production_mutation": False,
                        "secret_access": False,
                    },
                }
            )
        )
        task.thread_id = response.codex_thread_id
        task.execution_receipt = response.execution_receipt
        task.before_head = response.repository_state.local_head
        task.after_head = response.result_repository_state.local_head
        task.changed_files = self._changed_files(task.before_head, task.after_head)
        task.tests = [
            str(output.get("command_summary"))
            for output in response.tool_outputs
            if output.get("exit_code") == 0
            and any(
                marker in str(output.get("command_summary", "")).lower()
                for marker in ("pytest", "flutter test", "flutter analyze", "ruff", "mypy")
            )
        ]
        task.evidence = [
            f"task:{task.task_id}:execution-receipt",
            f"task:{task.task_id}:tool-output-correlation",
        ]
        self._record_planned_invocations(task_id, response.tool_outputs)
        return self._transition(
            task,
            OperatorTaskStatus.pending_verification,
            "AUTOMATIC_DISPATCH_COMPLETED",
            "Executor completed; independent verification remains required",
            blocker=None,
        )

    def _changed_files(self, before_head: str, after_head: str) -> list[str]:
        if before_head == after_head:
            return []
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self._workspace),
                "diff",
                "--name-only",
                before_head,
                after_head,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line]

    def continue_task(self, task_id: str) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.status not in {
            OperatorTaskStatus.awaiting_approval,
            OperatorTaskStatus.failed,
        }:
            raise GovernanceError("task is not in a continuable state")
        return self._transition(
            task,
            OperatorTaskStatus.pending,
            "TASK_CONTINUED",
            "Task returned to pending for governed redispatch",
            blocker=None,
        )

    def cancel_task(self, task_id: str) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.status == OperatorTaskStatus.cancelled:
            return task
        if task.status == OperatorTaskStatus.verified:
            raise GovernanceError("verified task cannot be cancelled")
        return self._transition(
            task,
            OperatorTaskStatus.cancelled,
            "TASK_CANCELLED",
            "Cancellation persisted idempotently",
            blocker=None,
        )

    def fail_task(
        self,
        task_id: str,
        code: str,
        *,
        timed_out: bool = False,
    ) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        return self._transition(
            task,
            OperatorTaskStatus.timed_out if timed_out else OperatorTaskStatus.failed,
            "TASK_TIMED_OUT" if timed_out else "TASK_EXECUTION_FAILED",
            code,
            blocker=code,
        )

    def verify_task(
        self,
        task_id: str,
        request: VerificationRequest,
    ) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.status != OperatorTaskStatus.pending_verification:
            raise GovernanceError("executor completion or manual result is required first")
        if task.after_head != request.verified_head:
            raise GovernanceError("verification receipt HEAD does not match task result")
        if request.ci_status != "success":
            raise GovernanceError("independent CI verification has not succeeded")
        self._assert_secret_free(request.model_dump(mode="json"))
        task.verification_receipt = request.verification_receipt
        execution_completed_at = task.completed_at
        verified = self._transition(
            task,
            OperatorTaskStatus.verified,
            "TASK_INDEPENDENTLY_VERIFIED",
            "Independent verification receipt persisted",
            blocker=None,
        )
        if execution_completed_at:
            verified.verification_duration_ms = int(
                (verified.updated_at - execution_completed_at).total_seconds() * 1000
            )
            self._persist()
        return verified

    def record_verification_blocker(
        self,
        task_id: str,
        blocker: str,
    ) -> OperatorTaskRecord:
        task = self.get_task(task_id)
        if task.status != OperatorTaskStatus.pending_verification:
            raise GovernanceError("verification blocker requires pending verification")
        return self._transition(
            task,
            OperatorTaskStatus.pending_verification,
            "INDEPENDENT_VERIFICATION_BLOCKED",
            blocker,
            blocker=blocker,
        )

    def generate_manual_package(self, task_id: str) -> ManualDispatchPackage:
        task = self.get_task(task_id)
        if not (task.automatic_failure_code or task.manual_fallback_selected):
            raise GovernanceError(
                "manual fallback requires an automatic failure or explicit selection"
            )
        self._verifier.verify(task.branch, task.expected_head)
        existing = self._manual_packages.get(task.idempotency_key)
        if existing:
            return existing
        envelope = {
            "task_id": task.task_id,
            "repository": task.repository,
            "branch": task.branch,
            "expected_head": task.expected_head,
            "authority_reference": task.authority_reference,
            "prompt": task.prompt,
            "constraints": task.constraints,
            "approval_policy": task.approval_policy,
            "sandbox": task.sandbox,
            "timeout_seconds": task.timeout_seconds,
            "max_turns": task.max_turns,
            "idempotency_key": task.idempotency_key,
            "automatic_failure_code": (
                task.automatic_failure_code or "OPERATOR_SELECTED_USER_RELAY"
            ),
        }
        self._assert_secret_free(envelope)
        canonical = json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        package = ManualDispatchPackage.model_validate(
            {
                **envelope,
                "package_receipt": f"manual-{digest[:24]}",
                "canonical_envelope_sha256": digest,
                "generated_at": datetime.now(UTC),
                "automatic_connectivity_acceptance": False,
            }
        )
        self._manual_packages[task.idempotency_key] = package
        task.dispatch_mode = DispatchMode.user_relay_fallback
        self._transition(
            task,
            OperatorTaskStatus.pending,
            "MANUAL_PACKAGE_GENERATED",
            "User relay package generated; automatic acceptance remains false",
            blocker=task.automatic_failure_code,
        )
        return package

    def mark_manual_dispatched(
        self,
        task_id: str,
        request: ManualDispatchMarkRequest,
    ) -> OperatorTaskRecord:
        task, _ = self._require_package(task_id, request.package_receipt)
        if task.last_event == "USER_RELAY_DISPATCHED":
            return task
        return self._transition(
            task,
            OperatorTaskStatus.running,
            "USER_RELAY_DISPATCHED",
            "Operator marked the package as relayed to Codex",
            blocker=None,
        )

    def record_manual_ack(
        self,
        task_id: str,
        request: ManualAcknowledgementRequest,
    ) -> OperatorTaskRecord:
        task, _ = self._require_package(task_id, request.package_receipt)
        self._assert_secret_free(request.model_dump(mode="json"))
        if task.thread_id == request.thread_reference:
            return task
        task.thread_id = request.thread_reference
        return self._transition(
            task,
            OperatorTaskStatus.running,
            "CODEX_ACKNOWLEDGED",
            "Codex acknowledgement and thread reference persisted",
            blocker=None,
        )

    def import_manual_result(
        self,
        task_id: str,
        request: ManualResultRequest,
    ) -> OperatorTaskRecord:
        task, _ = self._require_package(task_id, request.package_receipt)
        if (
            task.execution_receipt == request.package_receipt
            and task.thread_id == request.thread_reference
            and task.after_head == request.after_head
        ):
            return task
        self._verifier.verify(task.branch, request.after_head)
        if request.before_head != task.expected_head:
            raise GovernanceError("manual result before_head does not match task authority")
        if request.thread_reference != task.thread_id:
            raise GovernanceError("manual result thread reference does not match acknowledgement")
        self._assert_secret_free(request.model_dump(mode="json"))
        task.before_head = request.before_head
        task.after_head = request.after_head
        task.changed_files = request.changed_files
        task.tests = request.tests
        task.evidence = request.evidence
        task.execution_receipt = request.package_receipt
        return self._transition(
            task,
            OperatorTaskStatus.pending_verification,
            "MANUAL_RESULT_IMPORTED",
            "Manual result imported; independent verification remains required",
            blocker=None,
        )

    def plan_tools(
        self,
        task_id: str,
        request: TaskCapabilityRequest,
    ) -> ToolPlanResponse:
        task = self.get_task(task_id)
        if request.task_id != task.task_id or request.project_id != task.project_id:
            raise GovernanceError("tool plan request does not match persisted task")
        plan = self._router.plan(request, self.project_profile(task.project_id))
        self._tool_plans[task_id] = plan
        self._transition(
            task,
            task.status,
            "TOOL_DECISIONS_PERSISTED",
            (
                "Tool plan blocked by required capability"
                if plan.dispatch_blocked
                else "Minimum capability adapter set persisted before execution"
            ),
            blocker=plan.blockers[0] if plan.blockers else task.blocker,
        )
        return plan

    def tool_decisions(self, task_id: str) -> ToolPlanResponse:
        self.get_task(task_id)
        try:
            return self._tool_plans[task_id]
        except KeyError as exc:
            raise GovernanceError("tool plan has not been persisted") from exc

    def tool_invocations(self, task_id: str) -> list[ToolInvocationReceipt]:
        self.get_task(task_id)
        return list(self._invocations.get(task_id, []))

    def reconcile_tools(self, task_id: str) -> ToolReconciliation:
        plan = self.tool_decisions(task_id)
        planned = [
            decision.selected_adapter_id
            for decision in plan.decisions
            if decision.selected_adapter_id
        ]
        actual = [
            invocation.adapter_id
            for invocation in self.tool_invocations(task_id)
            if invocation.status == "completed"
        ]
        missing = [adapter for adapter in planned if adapter not in actual]
        unexpected = [adapter for adapter in actual if adapter not in planned]
        return ToolReconciliation(
            task_id=task_id,
            planned_adapter_ids=planned,
            actual_adapter_ids=actual,
            missing_adapter_ids=missing,
            unexpected_adapter_ids=unexpected,
            reconciled=not missing and not unexpected,
        )

    def _record_planned_invocations(
        self,
        task_id: str,
        tool_outputs: list[dict[str, object]],
    ) -> None:
        plan = self.tool_decisions(task_id)
        planned = [
            ToolInvocationReceipt(
                invocation_id=f"inv-{uuid4()}",
                task_id=task_id,
                capability_id=decision.capability_id,
                adapter_id=decision.selected_adapter_id,
                status="completed",
                evidence=decision.evidence_contract,
                occurred_at=datetime.now(UTC),
            )
            for decision in plan.decisions
            if decision.selected_adapter_id
        ]
        captured = [
            ToolInvocationReceipt(
                invocation_id=f"inv-{uuid4()}",
                task_id=task_id,
                capability_id="codex-shell",
                adapter_id="codex",
                status=("completed" if output.get("exit_code") in {None, 0} else "failed"),
                evidence=["CORRELATED_CODEX_TOOL_OUTPUT"],
                occurred_at=datetime.now(UTC),
                tool_call_id=str(output.get("tool_call_id") or ""),
                command_summary=str(output.get("command_summary") or ""),
                output_excerpt=str(output.get("output_excerpt") or ""),
                exit_code=self._optional_int(output.get("exit_code")),
            )
            for output in tool_outputs
        ]
        self._invocations[task_id] = [*planned, *captured]

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) else None

    def _require_package(
        self,
        task_id: str,
        receipt: str,
    ) -> tuple[OperatorTaskRecord, ManualDispatchPackage]:
        task = self.get_task(task_id)
        package = self._manual_packages.get(task.idempotency_key)
        if package is None or package.package_receipt != receipt:
            raise GovernanceError("manual package receipt is missing or does not match")
        return task, package

    def _transition(
        self,
        task: OperatorTaskRecord,
        status: OperatorTaskStatus,
        event_type: str,
        message: str,
        *,
        blocker: str | None,
    ) -> OperatorTaskRecord:
        now = datetime.now(UTC)
        task.status = status
        task.updated_at = now
        task.last_event = event_type
        task.blocker = blocker
        task.events.append(
            TaskEvent(
                event_type=event_type,
                status=status,
                message=message,
                occurred_at=now,
                correlation_id=task.correlation_id,
                client_id=task.client_id,
            )
        )
        if status in {
            OperatorTaskStatus.failed,
            OperatorTaskStatus.pending_verification,
            OperatorTaskStatus.verified,
            OperatorTaskStatus.cancelled,
            OperatorTaskStatus.timed_out,
        }:
            task.completed_at = now
            if task.started_at:
                task.executor_duration_ms = int((now - task.started_at).total_seconds() * 1000)
        self._persist()
        return task

    def _restore(self) -> None:
        state = self._state_store.load().get("operator", {})
        self._tasks = {
            task_id: OperatorTaskRecord.model_validate(value)
            for task_id, value in state.get("tasks", {}).items()
        }
        self._idempotency_tasks = dict(state.get("idempotency_tasks", {}))
        self._manual_packages = {
            key: ManualDispatchPackage.model_validate(value)
            for key, value in state.get("manual_packages", {}).items()
        }
        self._tool_plans = {
            task_id: ToolPlanResponse.model_validate(value)
            for task_id, value in state.get("tool_plans", {}).items()
        }
        self._invocations = {
            task_id: [ToolInvocationReceipt.model_validate(item) for item in values]
            for task_id, values in state.get("invocations", {}).items()
        }

    def _persist(self) -> None:
        state = self._state_store.load()
        state["operator"] = {
            "tasks": {key: value.model_dump(mode="json") for key, value in self._tasks.items()},
            "idempotency_tasks": self._idempotency_tasks,
            "manual_packages": {
                key: value.model_dump(mode="json") for key, value in self._manual_packages.items()
            },
            "tool_plans": {
                key: value.model_dump(mode="json") for key, value in self._tool_plans.items()
            },
            "invocations": {
                key: [item.model_dump(mode="json") for item in values]
                for key, values in self._invocations.items()
            },
        }
        self._state_store.save(state)

    @staticmethod
    def _assert_secret_free(value: object) -> None:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if SECRET_PATTERN.search(serialized):
            raise GovernanceError("task envelope contains a secret-like value")
