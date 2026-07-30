from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from palwakf_orchestrator.auth import AuthRegistry, BoundedRateLimiter, JwtAuthConfig
from palwakf_orchestrator.config import Settings, get_settings
from palwakf_orchestrator.connected_contracts import (
    ConnectedDispatchRequest,
    ConnectedTaskReceipt,
    ContinueTaskRequest,
    OperationalMetrics,
    QueueSnapshot,
    ServiceReadiness,
    ServiceScope,
    ToolHealthAlert,
    ToolOperationalHealth,
    ToolProbeRequest,
    VerifyCommand,
)
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.mcp_server import create_mcp_server
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
from palwakf_orchestrator.persistence import SQLiteStateStore, StateStore
from palwakf_orchestrator.project_contracts import (
    CandidateWorkItem,
    ExternalProjectRealityReport,
    ExternalProjectRecord,
    PrepareGovernedTaskEnvelopeRequest,
    PrepareGovernedTaskEnvelopeResponse,
    ProjectAdapterKind,
    ProjectIntakeRequest,
)
from palwakf_orchestrator.project_reality import (
    GitHubRepositoryRealityAdapter,
    HttpxGitHubReadClient,
    LocalGitRealityAdapter,
)
from palwakf_orchestrator.project_service import ExternalProjectService
from palwakf_orchestrator.service import OrchestratorService


def create_app(
    settings: Settings | None = None,
    service: OrchestratorService | None = None,
    operator_service: OperatorService | None = None,
    *,
    state_store: StateStore | None = None,
    auth_registry: AuthRegistry | None = None,
    connected_service: ConnectedApplicationService | None = None,
    project_service: ExternalProjectService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.assert_safe_binding()
    resolved_service = service or OrchestratorService(resolved_settings)
    resolved_store = state_store or SQLiteStateStore(resolved_settings.resolved_state_db_path)
    jwt_config = (
        JwtAuthConfig(
            issuer=resolved_settings.oauth_authorization_server,
            audience=resolved_settings.oauth_audience,
            jwks_url=resolved_settings.oauth_jwks_url,
        )
        if resolved_settings.oauth_authorization_server
        and resolved_settings.oauth_audience
        and resolved_settings.oauth_jwks_url
        else None
    )
    resolved_auth = auth_registry or AuthRegistry.from_json(
        resolved_settings.auth_clients_json,
        jwt_config=jwt_config,
    )
    resolved_operator = operator_service or OperatorService(
        resolved_settings.workspace_root,
        orchestrator=resolved_service,
        automatic_agents_available=bool(os.environ.get("OPENAI_API_KEY")),
        state_store=resolved_store,
    )
    connected = connected_service or ConnectedApplicationService(
        resolved_settings,
        resolved_operator,
        resolved_store,
        authentication_configured=resolved_auth.configured,
    )
    resolved_projects = project_service or ExternalProjectService(
        {
            ProjectAdapterKind.github_repository: GitHubRepositoryRealityAdapter(
                HttpxGitHubReadClient(os.environ.get("GITHUB_TOKEN"))
            ),
            ProjectAdapterKind.local_git: LocalGitRealityAdapter(
                resolved_settings.local_project_allowlist
            ),
        },
        resolved_store,
    )
    limiter = BoundedRateLimiter(resolved_settings.requests_per_minute)
    mcp_http_app = create_mcp_server(
        connected,
        resolved_auth,
    ).streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await connected.start()
        try:
            async with mcp_http_app.router.lifespan_context(mcp_http_app):
                yield
        finally:
            await connected.stop()

    app = FastAPI(
        title="PalWakf Connected Sovereign Orchestrator",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.connected_service = connected
    app.state.project_service = resolved_projects
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type", "X-Correlation-ID"],
    )

    @app.middleware("http")
    async def authenticate(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path.startswith("/mcp"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        scope = _scope_for(request)
        try:
            principal = resolved_auth.require(request, scope)
            limiter.require(principal.client_id)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
        request.state.principal = principal
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health", response_model=ServiceReadiness)
    async def health() -> ServiceReadiness:
        return connected.readiness()

    @app.get("/ready", response_model=ServiceReadiness)
    async def ready() -> ServiceReadiness:
        readiness = connected.readiness()
        if not readiness.ready:
            raise HTTPException(status_code=503, detail=readiness.model_dump(mode="json"))
        return readiness

    @app.get("/v1/metrics", response_model=OperationalMetrics)
    async def metrics() -> OperationalMetrics:
        return connected.metrics()

    @app.get("/v1/queue", response_model=QueueSnapshot)
    async def queue() -> QueueSnapshot:
        return connected.queue_snapshot()

    @app.post("/v1/connected/tasks/dispatch", response_model=ConnectedTaskReceipt)
    async def connected_dispatch(
        command: ConnectedDispatchRequest,
        request: Request,
    ) -> ConnectedTaskReceipt:
        try:
            return await connected.dispatch(
                command,
                request.state.principal,
                transport="http",
                correlation_id=request.headers.get("X-Correlation-ID"),
            )
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/v1/connected/tasks/{task_id}/continue",
        response_model=ConnectedTaskReceipt,
    )
    async def connected_continue(
        task_id: str,
        command: ContinueTaskRequest,
        request: Request,
    ) -> ConnectedTaskReceipt:
        try:
            return await connected.continue_task(
                task_id, command, request.state.principal, transport="http"
            )
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/v1/connected/tasks/{task_id}/status",
        response_model=ConnectedTaskReceipt,
    )
    async def connected_status(task_id: str, request: Request) -> ConnectedTaskReceipt:
        try:
            return connected.status(task_id, request.state.principal, transport="http")
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/v1/connected/tasks/{task_id}/cancel",
        response_model=ConnectedTaskReceipt,
    )
    async def connected_cancel(task_id: str, request: Request) -> ConnectedTaskReceipt:
        try:
            return connected.cancel(task_id, request.state.principal, transport="http")
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/v1/connected/tasks/{task_id}/verify",
        response_model=ConnectedTaskReceipt,
    )
    async def connected_verify(
        task_id: str,
        command: VerifyCommand,
        request: Request,
    ) -> ConnectedTaskReceipt:
        try:
            return connected.verify(task_id, command, request.state.principal, transport="http")
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/tools/health", response_model=list[ToolOperationalHealth])
    async def tools_health() -> list[ToolOperationalHealth]:
        return connected.tool_health.list_health()

    @app.get(
        "/v1/tools/{adapter_id}/health",
        response_model=ToolOperationalHealth,
    )
    async def tool_health(adapter_id: str) -> ToolOperationalHealth:
        try:
            return connected.tool_health.get(adapter_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/v1/tools/alerts", response_model=list[ToolHealthAlert])
    async def tool_alerts() -> list[ToolHealthAlert]:
        return connected.tool_health.alerts()

    @app.post(
        "/v1/tools/{adapter_id}/probe",
        response_model=ToolOperationalHealth,
    )
    async def probe_tool(
        adapter_id: str,
        _: ToolProbeRequest,
    ) -> ToolOperationalHealth:
        try:
            return connected.tool_health.probe(adapter_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    _add_legacy_routes(app, resolved_operator, connected)
    _add_project_routes(app, resolved_projects)
    app.mount("/mcp", mcp_http_app, name="mcp")
    return app


def _scope_for(request: Request) -> ServiceScope:
    path = request.url.path
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return ServiceScope.read
    if path.endswith("/continue"):
        return ServiceScope.continue_task
    if path.endswith("/cancel"):
        return ServiceScope.cancel
    if path.endswith("/verify"):
        return ServiceScope.verify
    if path.endswith("/probe"):
        return ServiceScope.probe
    return ServiceScope.dispatch


def _add_legacy_routes(
    app: FastAPI,
    operator: OperatorService,
    connected: ConnectedApplicationService,
) -> None:
    def conflict(exc: GovernanceError) -> HTTPException:
        return HTTPException(status_code=409, detail=str(exc))

    @app.get("/v1/capabilities", response_model=RuntimeCapabilities)
    async def capabilities() -> RuntimeCapabilities:
        return operator.capabilities()

    @app.get("/v1/capability-registry")
    async def capability_registry() -> dict[str, object]:
        return operator.registry_snapshot()

    @app.get("/v1/projects/{project_id}/tool-profile")
    async def project_tool_profile(project_id: str) -> ProjectCapabilityProfile:
        try:
            return operator.project_profile(project_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/tasks", response_model=OperatorTaskRecord)
    async def create_task(command: CreateOperatorTaskRequest) -> OperatorTaskRecord:
        try:
            return operator.create_task(command)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.get("/v1/tasks", response_model=list[OperatorTaskRecord])
    async def list_tasks() -> list[OperatorTaskRecord]:
        return operator.list_tasks()

    @app.get("/v1/tasks/{task_id}", response_model=OperatorTaskRecord)
    async def task_status(task_id: str) -> OperatorTaskRecord:
        try:
            return operator.get_task(task_id)
        except GovernanceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/tasks/{task_id}/dispatch", response_model=OperatorTaskRecord)
    async def dispatch_task(task_id: str, request: Request) -> OperatorTaskRecord:
        try:
            receipt = await connected.dispatch_existing(
                task_id,
                request.state.principal,
                transport="http",
                correlation_id=request.headers.get("X-Correlation-ID"),
            )
            return receipt.task
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/continue", response_model=OperatorTaskRecord)
    async def continue_task(task_id: str, request: Request) -> OperatorTaskRecord:
        try:
            receipt = await connected.continue_task(
                task_id,
                ContinueTaskRequest(
                    execution_host_id=connected.settings.execution_host_id,
                    tool_executor_id=connected.settings.tool_executor_id,
                ),
                request.state.principal,
                transport="http",
            )
            return receipt.task
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/cancel", response_model=OperatorTaskRecord)
    async def cancel_task(task_id: str, request: Request) -> OperatorTaskRecord:
        try:
            return connected.cancel(
                task_id,
                request.state.principal,
                transport="http",
            ).task
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/verify", response_model=OperatorTaskRecord)
    async def verify_task(
        task_id: str,
        command: VerificationRequest,
        request: Request,
    ) -> OperatorTaskRecord:
        try:
            return connected.verify(
                task_id,
                VerifyCommand(
                    request=command,
                    execution_host_id=connected.settings.execution_host_id,
                    tool_executor_id=connected.settings.tool_executor_id,
                ),
                request.state.principal,
                transport="http",
            ).task
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/manual-package", response_model=ManualDispatchPackage)
    async def manual_package(task_id: str) -> ManualDispatchPackage:
        try:
            return operator.generate_manual_package(task_id)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/manual-dispatched", response_model=OperatorTaskRecord)
    async def manual_dispatched(
        task_id: str, command: ManualDispatchMarkRequest
    ) -> OperatorTaskRecord:
        try:
            return operator.mark_manual_dispatched(task_id, command)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/manual-ack", response_model=OperatorTaskRecord)
    async def manual_ack(task_id: str, command: ManualAcknowledgementRequest) -> OperatorTaskRecord:
        try:
            return operator.record_manual_ack(task_id, command)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/manual-result", response_model=OperatorTaskRecord)
    async def manual_result(task_id: str, command: ManualResultRequest) -> OperatorTaskRecord:
        try:
            return operator.import_manual_result(task_id, command)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.post("/v1/tasks/{task_id}/tool-plan", response_model=ToolPlanResponse)
    async def tool_plan(task_id: str, command: TaskCapabilityRequest) -> ToolPlanResponse:
        try:
            return operator.plan_tools(task_id, command)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.get("/v1/tasks/{task_id}/tool-decisions", response_model=ToolPlanResponse)
    async def tool_decisions(task_id: str) -> ToolPlanResponse:
        return operator.tool_decisions(task_id)

    @app.get(
        "/v1/tasks/{task_id}/tool-invocations",
        response_model=list[ToolInvocationReceipt],
    )
    async def tool_invocations(task_id: str) -> list[ToolInvocationReceipt]:
        return operator.tool_invocations(task_id)

    @app.get(
        "/v1/tasks/{task_id}/tool-reconciliation",
        response_model=ToolReconciliation,
    )
    async def tool_reconciliation(task_id: str) -> ToolReconciliation:
        return operator.reconcile_tools(task_id)


def _add_project_routes(
    app: FastAPI,
    projects: ExternalProjectService,
) -> None:
    def project_error(exc: GovernanceError) -> HTTPException:
        status = (
            404
            if str(exc)
            in {
                "PROJECT_NOT_REGISTERED",
                "PROJECT_REALITY_NOT_PROBED",
                "PROJECT_REPOSITORY_NOT_FOUND",
                "PROJECT_CANDIDATE_NOT_FOUND",
            }
            else 409
        )
        return HTTPException(status_code=status, detail=str(exc))

    @app.post("/v1/projects/intake", response_model=ExternalProjectRecord)
    async def project_intake(command: ProjectIntakeRequest) -> ExternalProjectRecord:
        try:
            return projects.intake(command)
        except GovernanceError as exc:
            raise project_error(exc) from exc

    @app.get("/v1/projects", response_model=list[ExternalProjectRecord])
    async def list_external_projects() -> list[ExternalProjectRecord]:
        return projects.list_projects()

    @app.get("/v1/projects/{project_id}", response_model=ExternalProjectRecord)
    async def get_external_project(project_id: str) -> ExternalProjectRecord:
        try:
            return projects.get_project(project_id)
        except GovernanceError as exc:
            raise project_error(exc) from exc

    @app.post(
        "/v1/projects/{project_id}/probe",
        response_model=ExternalProjectRealityReport,
    )
    async def probe_external_project(
        project_id: str,
    ) -> ExternalProjectRealityReport:
        try:
            return await projects.probe(project_id)
        except GovernanceError as exc:
            raise project_error(exc) from exc

    @app.get(
        "/v1/projects/{project_id}/reality",
        response_model=ExternalProjectRealityReport,
    )
    async def external_project_reality(
        project_id: str,
    ) -> ExternalProjectRealityReport:
        try:
            return projects.reality(project_id)
        except GovernanceError as exc:
            raise project_error(exc) from exc

    @app.get(
        "/v1/projects/{project_id}/candidate-work-items",
        response_model=list[CandidateWorkItem],
    )
    async def external_project_candidates(
        project_id: str,
    ) -> list[CandidateWorkItem]:
        try:
            return projects.candidate_work_items(project_id)
        except GovernanceError as exc:
            raise project_error(exc) from exc

    @app.post(
        "/v1/projects/{project_id}/prepare-task",
        response_model=PrepareGovernedTaskEnvelopeResponse,
    )
    async def prepare_external_project_task(
        project_id: str,
        command: PrepareGovernedTaskEnvelopeRequest,
    ) -> PrepareGovernedTaskEnvelopeResponse:
        try:
            return projects.prepare_task_envelope(project_id, command.candidate_id)
        except GovernanceError as exc:
            raise project_error(exc) from exc
