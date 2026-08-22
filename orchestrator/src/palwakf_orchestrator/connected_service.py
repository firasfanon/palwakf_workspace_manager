from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from datetime import UTC, datetime
from statistics import median
from typing import Literal
from uuid import uuid4

import httpx

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import (
    AuditEvent,
    ClientPrincipal,
    ConnectedDispatchRequest,
    ConnectedTaskReceipt,
    ContinueTaskRequest,
    OperationalMetrics,
    QueueSnapshot,
    ServiceReadiness,
    VerifyCommand,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    OperatorTaskRecord,
    OperatorTaskStatus,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.safe_logging import redact
from palwakf_orchestrator.tool_health import ToolHealthService

TransportName = Literal["http", "mcp"]
SELF_HOSTED_PROOF_TASK_ID = "PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1"


class GitHubCiVerifier:
    def __init__(self, repository: str, token: str | None = None) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "PalWakf-Workspace-Manager",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=f"https://api.github.com/repos/{repository}",
            headers=headers,
            timeout=15,
        )

    def status(self, head: str) -> tuple[str, str | None]:
        response = self._client.get("/actions/runs", params={"head_sha": head, "per_page": 5})
        response.raise_for_status()
        payload = response.json()
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list) or not runs:
            return "pending", None
        run = runs[0]
        if not isinstance(run, dict):
            return "pending", None
        status = str(run.get("status") or "pending").lower()
        conclusion = str(run.get("conclusion") or "").lower()
        run_id = run.get("id")
        receipt = f"github-actions-run-{run_id}" if run_id else None
        if status != "completed":
            return "pending", receipt
        return ("success" if conclusion == "success" else "failed"), receipt


class ConnectedApplicationService:
    def __init__(
        self,
        settings: Settings,
        operator: OperatorService,
        store: StateStore,
        *,
        authentication_configured: bool,
        tool_health: ToolHealthService | None = None,
        ci_verifier: GitHubCiVerifier | None = None,
    ) -> None:
        self.settings = settings
        self.operator = operator
        self.store = store
        self.tool_health = tool_health or ToolHealthService(store)
        self.authentication_configured = authentication_configured
        self._queue: asyncio.Queue[str] = asyncio.Queue(settings.queue_capacity)
        self._workers: list[asyncio.Task[None]] = []
        self._active: dict[str, asyncio.Task[OperatorTaskRecord]] = {}
        self._repository_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._audit = self._restore_audit()
        self._ci_verifier = ci_verifier or GitHubCiVerifier(
            settings.repository,
            os.environ.get("GITHUB_TOKEN"),
        )

    async def start(self) -> None:
        if self._workers:
            return
        for task_id in self.operator.recover_interrupted_tasks():
            task = self.operator.get_task(task_id)
            self.store.release_repository_writer(task.repository, task.task_id)
        self._workers = [
            asyncio.create_task(self._worker(index), name=f"palwakf-worker-{index}")
            for index in range(self.settings.worker_count)
        ]

    async def stop(self) -> None:
        for execution in list(self._active.values()):
            execution.cancel()
        if self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def wait_until_idle(self) -> None:
        await self._queue.join()

    def readiness(self) -> ServiceReadiness:
        return ServiceReadiness(
            service="palwakf-connected-orchestrator",
            version="1.0.0",
            ready=(
                self.authentication_configured and self.store.is_healthy() and bool(self._workers)
            ),
            mode=self.settings.service_mode,
            authentication_configured=self.authentication_configured,
            store_healthy=self.store.is_healthy(),
            workers_started=bool(self._workers),
        )

    async def dispatch(
        self,
        request: ConnectedDispatchRequest,
        principal: ClientPrincipal,
        *,
        transport: TransportName,
        correlation_id: str | None = None,
    ) -> ConnectedTaskReceipt:
        correlation = correlation_id or f"corr-{uuid4()}"
        if request.task.task_id != request.tool_plan.task_id:
            raise GovernanceError("task and tool plan identifiers do not match")
        task = self.operator.create_task(request.task)
        self.operator.bind_client(
            task.task_id,
            client_id=principal.client_id,
            correlation_id=correlation,
            execution_host_id=self.settings.execution_host_id,
            tool_executor_id=self.settings.tool_executor_id,
        )
        try:
            self.operator.tool_decisions(task.task_id)
        except GovernanceError:
            self.operator.plan_tools(task.task_id, request.tool_plan)
        if task.execution_receipt or task.status in {
            OperatorTaskStatus.queued,
            OperatorTaskStatus.running,
        }:
            self._record_audit(correlation, principal, "dispatch", "idempotent_replay", task)
            return self._receipt(task, correlation, principal, transport)
        if self._queue.full():
            self._record_audit(correlation, principal, "dispatch", "queue_full", task)
            raise GovernanceError("bounded dispatch queue is full")
        task = self.operator.queue_task(task.task_id)
        self._queue.put_nowait(task.task_id)
        self._record_audit(correlation, principal, "dispatch", "queued", task)
        return self._receipt(task, correlation, principal, transport)

    async def dispatch_existing(
        self,
        task_id: str,
        principal: ClientPrincipal,
        *,
        transport: TransportName,
        correlation_id: str | None = None,
    ) -> ConnectedTaskReceipt:
        correlation = correlation_id or f"corr-{uuid4()}"
        task = self.operator.get_task(task_id)
        self.operator.tool_decisions(task_id)
        task = self.operator.bind_client(
            task_id,
            client_id=principal.client_id,
            correlation_id=correlation,
            execution_host_id=self.settings.execution_host_id,
            tool_executor_id=self.settings.tool_executor_id,
        )
        if task.execution_receipt or task.status in {
            OperatorTaskStatus.queued,
            OperatorTaskStatus.running,
        }:
            return self._receipt(task, correlation, principal, transport)
        if self._queue.full():
            raise GovernanceError("bounded dispatch queue is full")
        task = self.operator.queue_task(task_id)
        self._queue.put_nowait(task_id)
        self._record_audit(correlation, principal, "dispatch", "queued", task)
        return self._receipt(task, correlation, principal, transport)

    async def continue_task(
        self,
        task_id: str,
        command: ContinueTaskRequest,
        principal: ClientPrincipal,
        *,
        transport: TransportName,
    ) -> ConnectedTaskReceipt:
        correlation = f"corr-{uuid4()}"
        self._assert_host(command.execution_host_id, command.tool_executor_id)
        task = self.operator.bind_client(
            task_id,
            client_id=principal.client_id,
            correlation_id=correlation,
            execution_host_id=command.execution_host_id,
            tool_executor_id=command.tool_executor_id,
        )
        task = self.operator.continue_task(task.task_id)
        if self._queue.full():
            raise GovernanceError("bounded dispatch queue is full")
        task = self.operator.queue_task(task.task_id)
        self._queue.put_nowait(task.task_id)
        self._record_audit(correlation, principal, "continue", "queued", task)
        return self._receipt(task, correlation, principal, transport)

    def status(
        self, task_id: str, principal: ClientPrincipal, *, transport: TransportName
    ) -> ConnectedTaskReceipt:
        task = self.operator.get_task(task_id)
        correlation = f"corr-{uuid4()}"
        self._record_audit(correlation, principal, "status", "returned", task)
        return self._receipt(task, correlation, principal, transport)

    def list_recent(self, limit: int = 50) -> list[OperatorTaskRecord]:
        return self.operator.list_tasks()[: min(max(limit, 1), 100)]

    def cancel(
        self, task_id: str, principal: ClientPrincipal, *, transport: TransportName
    ) -> ConnectedTaskReceipt:
        correlation = f"corr-{uuid4()}"
        execution = self._active.get(task_id)
        if execution:
            execution.cancel()
        task = self.operator.cancel_task(task_id)
        self._record_audit(correlation, principal, "cancel", "cancelled", task)
        return self._receipt(task, correlation, principal, transport)

    def verify(
        self,
        task_id: str,
        command: VerifyCommand,
        principal: ClientPrincipal,
        *,
        transport: TransportName,
    ) -> ConnectedTaskReceipt:
        correlation = f"corr-{uuid4()}"
        self._assert_host(command.execution_host_id, command.tool_executor_id)
        self.operator.bind_client(
            task_id,
            client_id=principal.client_id,
            correlation_id=correlation,
            execution_host_id=command.execution_host_id,
            tool_executor_id=command.tool_executor_id,
        )
        task = self.operator.verify_task(task_id, command.request)
        self._record_audit(correlation, principal, "verify", "verified", task)
        return self._receipt(task, correlation, principal, transport)

    def queue_snapshot(self) -> QueueSnapshot:
        running = len(self._active)
        return QueueSnapshot(
            capacity=self.settings.queue_capacity,
            worker_count=self.settings.worker_count,
            queued=self._queue.qsize(),
            running=running,
            available_slots=max(self.settings.queue_capacity - self._queue.qsize(), 0),
            active_repository_writers=sum(
                1
                for task in self._active
                if self.operator.get_task(task).sandbox == "workspace-write"
            ),
        )

    def metrics(self) -> OperationalMetrics:
        tasks = self.operator.list_tasks()

        def duration(field: str) -> int | None:
            values = [getattr(task, field) for task in tasks if getattr(task, field) is not None]
            return int(median(values)) if values else None

        return OperationalMetrics(
            queued=sum(task.status == OperatorTaskStatus.queued for task in tasks),
            running=sum(task.status == OperatorTaskStatus.running for task in tasks),
            completed=sum(
                task.status
                in {
                    OperatorTaskStatus.pending_verification,
                    OperatorTaskStatus.verified,
                }
                for task in tasks
            ),
            failed=sum(
                task.status in {OperatorTaskStatus.failed, OperatorTaskStatus.timed_out}
                for task in tasks
            ),
            cancelled=sum(task.status == OperatorTaskStatus.cancelled for task in tasks),
            dispatch_latency_ms=duration("dispatch_latency_ms"),
            executor_duration_ms=duration("executor_duration_ms"),
            verification_duration_ms=duration("verification_duration_ms"),
            last_successful_executor_execution_at=max(
                (
                    task.completed_at
                    for task in tasks
                    if task.execution_receipt and task.completed_at is not None
                ),
                default=None,
            ),
            last_successful_codex_execution_at=max(
                (
                    task.completed_at
                    for task in tasks
                    if task.execution_receipt and task.completed_at is not None
                ),
                default=None,
            ),
            store_healthy=self.store.is_healthy(),
        )

    async def _worker(self, index: int) -> None:
        while True:
            task_id = await self._queue.get()
            try:
                task = self.operator.get_task(task_id)
                if task.status == OperatorTaskStatus.cancelled:
                    continue
                repository_lock = self._repository_locks[task.repository]
                async with repository_lock:
                    await self._execute(task)
            finally:
                self._queue.task_done()

    async def _execute(self, task: OperatorTaskRecord) -> None:
        writer_acquired = False
        if task.sandbox == "workspace-write":
            writer_acquired = self.store.acquire_repository_writer(
                task.repository,
                task.task_id,
                self.settings.execution_host_id,
            )
            if not writer_acquired:
                self.operator.fail_task(task.task_id, "REPOSITORY_WRITER_BUSY")
                return
        try:
            self.operator.start_task(task.task_id)
            execution = asyncio.create_task(self.operator.dispatch_task(task.task_id))
            self._active[task.task_id] = execution
            try:
                completed = await asyncio.wait_for(execution, timeout=task.timeout_seconds)
                if (
                    completed.task_id == SELF_HOSTED_PROOF_TASK_ID
                    and completed.status == OperatorTaskStatus.pending_verification
                    and completed.after_head
                ):
                    await self._verify_self_hosted_ci(completed)
            except TimeoutError:
                self.operator.fail_task(task.task_id, "EXECUTION_TIMEOUT", timed_out=True)
            except asyncio.CancelledError:
                if self.operator.get_task(task.task_id).status != OperatorTaskStatus.cancelled:
                    self.operator.cancel_task(task.task_id)
        except Exception as exc:
            self.operator.fail_task(
                task.task_id,
                f"EXECUTION_FAILED:{type(exc).__name__}:{redact(exc)[:400]}",
            )
        finally:
            self._active.pop(task.task_id, None)
            if writer_acquired:
                self.store.release_repository_writer(task.repository, task.task_id)

    async def _verify_self_hosted_ci(self, task: OperatorTaskRecord) -> None:
        assert task.after_head is not None
        deadline = asyncio.get_running_loop().time() + self.settings.self_hosted_ci_timeout_seconds
        last_receipt: str | None = None
        while asyncio.get_running_loop().time() < deadline:
            try:
                status, receipt = await asyncio.to_thread(
                    self._ci_verifier.status,
                    task.after_head,
                )
            except httpx.HTTPError as exc:
                self.operator.record_verification_blocker(
                    task.task_id,
                    f"GITHUB_CI_READ_FAILED:{type(exc).__name__}",
                )
                return
            last_receipt = receipt or last_receipt
            if status == "success" and last_receipt:
                self.operator.verify_task(
                    task.task_id,
                    VerificationRequest(
                        verification_receipt=last_receipt,
                        ci_status="success",
                        verified_head=task.after_head,
                    ),
                )
                return
            if status == "failed":
                self.operator.record_verification_blocker(
                    task.task_id,
                    f"GITHUB_CI_FAILED:{last_receipt or 'UNKNOWN_RUN'}",
                )
                return
            await asyncio.sleep(10)
        self.operator.record_verification_blocker(
            task.task_id,
            f"GITHUB_CI_TIMEOUT:{last_receipt or 'NO_RUN_DISCOVERED'}",
        )

    def _assert_host(self, execution_host_id: str, tool_executor_id: str) -> None:
        if (
            execution_host_id != self.settings.execution_host_id
            or tool_executor_id != self.settings.tool_executor_id
        ):
            raise GovernanceError(
                "incompatible cross-host resume rejected; migration handshake required"
            )

    @staticmethod
    def _receipt(
        task: OperatorTaskRecord,
        correlation_id: str,
        principal: ClientPrincipal,
        transport: TransportName,
    ) -> ConnectedTaskReceipt:
        return ConnectedTaskReceipt(
            task=task.model_copy(deep=True),
            correlation_id=correlation_id,
            client_id=principal.client_id,
            transport=transport,
        )

    def _restore_audit(self) -> list[AuditEvent]:
        return [AuditEvent.model_validate(value) for value in self.store.load().get("audit", [])]

    def _record_audit(
        self,
        correlation_id: str,
        principal: ClientPrincipal,
        action: str,
        outcome: str,
        task: OperatorTaskRecord,
    ) -> None:
        self._audit.append(
            AuditEvent(
                occurred_at=datetime.now(UTC),
                correlation_id=correlation_id,
                client_id=principal.client_id,
                action=action,
                outcome=outcome,
                task_id=task.task_id,
                metadata={
                    "execution_host_id": task.execution_host_id,
                    "tool_executor_id": task.tool_executor_id,
                },
            )
        )
        state = self.store.load()
        state["audit"] = [item.model_dump(mode="json") for item in self._audit[-10_000:]]
        self.store.save(state)
