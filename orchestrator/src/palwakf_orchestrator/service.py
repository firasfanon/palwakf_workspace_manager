from __future__ import annotations

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import (
    DispatchRequest,
    DispatchResponse,
    HealthResponse,
    SovereigntyBoundaries,
    Transport,
)
from palwakf_orchestrator.gateways import CodexGateway, CodexMcpGateway, CodexSdkGateway
from palwakf_orchestrator.governance import GovernanceGate
from palwakf_orchestrator.planner import AgentsPlanner, Planner


class OrchestratorService:
    def __init__(
        self,
        settings: Settings,
        *,
        gate: GovernanceGate | None = None,
        planner: Planner | None = None,
        gateways: dict[Transport, CodexGateway] | None = None,
    ) -> None:
        self._settings = settings
        self._gate = gate or GovernanceGate(settings.workspace_root)
        self._planner = planner or AgentsPlanner(settings)
        self._gateways = gateways or {
            Transport.sdk: CodexSdkGateway(settings),
            Transport.mcp: CodexMcpGateway(settings),
        }

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
        repository_state = self._gate.verify_repository(request)
        plan = await self._planner.plan(request, repository_state)
        self._gate.verify_plan(plan)
        gateway_result = await self._gateways[request.transport].run(
            plan.codex_prompt,
            self._settings.workspace_root,
        )
        return DispatchResponse(
            task_id=request.task_id,
            status="completed",
            transport=request.transport,
            repository_state=repository_state,
            plan_summary=plan.summary,
            codex_thread_id=gateway_result.thread_id,
            final_response=gateway_result.final_response,
            boundaries=request.boundaries,
        )
