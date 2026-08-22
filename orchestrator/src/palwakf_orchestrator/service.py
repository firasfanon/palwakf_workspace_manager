from __future__ import annotations

import asyncio
from uuid import uuid4

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import (
    DispatchRequest,
    DispatchResponse,
    HealthResponse,
    SovereigntyBoundaries,
    Transport,
)
from palwakf_orchestrator.gateways import CodexMcpGateway, CodexSdkGateway, ExecutorGateway
from palwakf_orchestrator.governance import GovernanceGate
from palwakf_orchestrator.planner import AgentsPlanner, Planner


class OrchestratorService:
    def __init__(
        self,
        settings: Settings,
        *,
        gate: GovernanceGate | None = None,
        planner: Planner | None = None,
        gateways: dict[Transport, ExecutorGateway] | None = None,
    ) -> None:
        self._settings = settings
        self._gate = gate or GovernanceGate(settings.workspace_root)
        self._planner = planner or AgentsPlanner(settings)
        self._gateways = gateways or {
            Transport.sdk: CodexSdkGateway(settings),
            Transport.mcp: CodexMcpGateway(settings),
        }
        self._execution_lock = asyncio.Lock()
        self._executions: dict[str, asyncio.Task[DispatchResponse]] = {}

    def health(self) -> HealthResponse:
        return HealthResponse(
            service="palwakf-orchestrator",
            version="0.1.0",
            status="ready",
            remote_deployment=False,
            boundaries=SovereigntyBoundaries(),
            transports=(Transport.sdk, Transport.mcp),
        )

    async def dispatch(self, request: DispatchRequest) -> DispatchResponse:
        async with self._execution_lock:
            execution = self._executions.get(request.idempotency_key)
            replayed = execution is not None
            if execution is None:
                execution = asyncio.create_task(self._execute(request))
                self._executions[request.idempotency_key] = execution

        try:
            response = await execution
        except Exception:
            async with self._execution_lock:
                if self._executions.get(request.idempotency_key) is execution:
                    del self._executions[request.idempotency_key]
            raise

        return response.model_copy(update={"idempotency_replayed": replayed})

    async def _execute(self, request: DispatchRequest) -> DispatchResponse:
        repository_state = self._gate.verify_repository(request)
        planning = await self._planner.plan(request, repository_state)
        gateway = self._gateways[request.transport]
        if request.boundaries.workspace_write:
            self._gate.verify_plan(planning.plan, request)
            gateway_result = await gateway.run(
                planning.plan.effective_executor_prompt,
                self._settings.workspace_root,
                workspace_write=True,
            )
            result_repository_state = self._gate.verify_result_repository(
                request,
                repository_state,
            )
        else:
            self._gate.verify_plan(planning.plan)
            gateway_result = await gateway.run(
                planning.plan.effective_executor_prompt,
                self._settings.workspace_root,
            )
            verifier = getattr(self._gate, "verify_result_repository", None)
            result_repository_state = (
                verifier(request, repository_state) if callable(verifier) else repository_state
            )
        return DispatchResponse(
            task_id=request.task_id,
            status="completed",
            transport=request.transport,
            execution_receipt=f"pwk-{uuid4()}",
            idempotency_key=request.idempotency_key,
            idempotency_replayed=False,
            repository_state=repository_state,
            result_repository_state=result_repository_state,
            plan_summary=planning.plan.summary,
            reasoning_provider_id=planning.reasoning_provider_id,
            reasoning_response_id=planning.reasoning_response_id,
            executor_id=gateway.executor_id,
            executor_thread_id=gateway_result.thread_id,
            agents_response_id=planning.agents_response_id,
            codex_thread_id=gateway_result.thread_id,
            final_response=gateway_result.final_response,
            tool_outputs=gateway_result.tool_outputs,
            boundaries=request.boundaries,
        )
