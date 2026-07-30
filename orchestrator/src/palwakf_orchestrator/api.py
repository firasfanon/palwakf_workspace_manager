from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from palwakf_orchestrator.config import Settings, get_settings
from palwakf_orchestrator.contracts import DispatchRequest, DispatchResponse, HealthResponse
from palwakf_orchestrator.errors import GatewayError, GovernanceError
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
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
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.service import OrchestratorService


def create_app(
    settings: Settings | None = None,
    service: OrchestratorService | None = None,
    operator_service: OperatorService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_service = service or OrchestratorService(resolved_settings)
    resolved_operator = operator_service or OperatorService(
        resolved_settings.workspace_root,
        orchestrator=resolved_service,
    )
    app = FastAPI(
        title="PalWakf Sovereign Orchestrator",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return resolved_service.health()

    @app.get("/v1/capabilities", response_model=RuntimeCapabilities)
    async def capabilities() -> RuntimeCapabilities:
        return resolved_operator.capabilities()

    @app.get("/v1/capability-registry")
    async def capability_registry() -> dict[str, object]:
        return resolved_operator.registry_snapshot()

    @app.get("/v1/projects/{project_id}/tool-profile")
    async def project_tool_profile(project_id: str) -> ProjectCapabilityProfile:
        try:
            return resolved_operator.project_profile(project_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/tasks", response_model=OperatorTaskRecord)
    async def create_task(request: CreateOperatorTaskRequest) -> OperatorTaskRecord:
        try:
            return resolved_operator.create_task(request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/tasks", response_model=list[OperatorTaskRecord])
    async def list_tasks() -> list[OperatorTaskRecord]:
        return resolved_operator.list_tasks()

    @app.get("/v1/tasks/{task_id}", response_model=OperatorTaskRecord)
    async def task_status(task_id: str) -> OperatorTaskRecord:
        try:
            return resolved_operator.get_task(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/dispatch", response_model=OperatorTaskRecord)
    async def dispatch_task(task_id: str) -> OperatorTaskRecord:
        try:
            return await resolved_operator.dispatch_task(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/continue", response_model=OperatorTaskRecord)
    async def continue_task(task_id: str) -> OperatorTaskRecord:
        try:
            return resolved_operator.continue_task(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/cancel", response_model=OperatorTaskRecord)
    async def cancel_task(task_id: str) -> OperatorTaskRecord:
        try:
            return resolved_operator.cancel_task(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/verify", response_model=OperatorTaskRecord)
    async def verify_task(
        task_id: str,
        request: VerificationRequest,
    ) -> OperatorTaskRecord:
        try:
            return resolved_operator.verify_task(task_id, request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/v1/tasks/{task_id}/manual-package",
        response_model=ManualDispatchPackage,
    )
    async def manual_package(task_id: str) -> ManualDispatchPackage:
        try:
            return resolved_operator.generate_manual_package(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/v1/tasks/{task_id}/manual-dispatched",
        response_model=OperatorTaskRecord,
    )
    async def manual_dispatched(
        task_id: str,
        request: ManualDispatchMarkRequest,
    ) -> OperatorTaskRecord:
        try:
            return resolved_operator.mark_manual_dispatched(task_id, request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/manual-ack", response_model=OperatorTaskRecord)
    async def manual_ack(
        task_id: str,
        request: ManualAcknowledgementRequest,
    ) -> OperatorTaskRecord:
        try:
            return resolved_operator.record_manual_ack(task_id, request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/manual-result", response_model=OperatorTaskRecord)
    async def manual_result(
        task_id: str,
        request: ManualResultRequest,
    ) -> OperatorTaskRecord:
        try:
            return resolved_operator.import_manual_result(task_id, request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/tool-plan", response_model=ToolPlanResponse)
    async def tool_plan(
        task_id: str,
        request: TaskCapabilityRequest,
    ) -> ToolPlanResponse:
        try:
            return resolved_operator.plan_tools(task_id, request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/tasks/{task_id}/tool-decisions", response_model=ToolPlanResponse)
    async def tool_decisions(task_id: str) -> ToolPlanResponse:
        try:
            return resolved_operator.tool_decisions(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/v1/tasks/{task_id}/tool-invocations",
        response_model=list[ToolInvocationReceipt],
    )
    async def tool_invocations(task_id: str) -> list[ToolInvocationReceipt]:
        try:
            return resolved_operator.tool_invocations(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/v1/tasks/{task_id}/tool-reconciliation",
        response_model=ToolReconciliation,
    )
    async def tool_reconciliation(task_id: str) -> ToolReconciliation:
        try:
            return resolved_operator.reconcile_tools(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/dispatch", response_model=DispatchResponse)
    async def dispatch(
        dispatch_request: DispatchRequest,
        http_request: Request,
    ) -> DispatchResponse:
        host = http_request.url.hostname or ""
        if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            raise HTTPException(status_code=403, detail="V1 dispatch is local-only")
        try:
            return await resolved_service.dispatch(dispatch_request)
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except GatewayError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app
