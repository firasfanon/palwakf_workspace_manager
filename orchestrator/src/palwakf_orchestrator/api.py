from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
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
    SessionAuthorizationContext,
    ToolHealthAlert,
    ToolOperationalHealth,
    ToolProbeRequest,
    VerifyCommand,
)
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.dashboard_contracts import (
    DashboardSummary,
    EvidenceIndexItem,
    OperationalAlertSummary,
    RecentActivityItem,
)
from palwakf_orchestrator.dashboard_service import DashboardAggregationService
from palwakf_orchestrator.direct_execution_contracts import (
    DirectExecutionReceipt,
    DirectExecutionRequest,
)
from palwakf_orchestrator.direct_execution_service import (
    DirectExecutionError,
    DirectExecutionService,
    OpenAIAgentsDirectTextExecutor,
)
from palwakf_orchestrator.engineering_os_contracts import (
    CreateEngineeringTaskRequest,
    EngineeringOsSummary,
    EngineeringTaskRecord,
    ExtensionRecord,
    RegisterExtensionRequest,
    RemoteCheckpointRequest,
)
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.execution_run_contracts import (
    CreateExecutionRunRequest,
    EngineeringTaskExecutionContext,
    ExecutionRunOperationalView,
)
from palwakf_orchestrator.external_execution_contracts import (
    ApplyExternalWorkspaceRequest,
    CheckpointExternalWorkspaceRequest,
    ExternalExecutionWorkspaceStatus,
    PrepareExternalWorkspaceRequest,
    ValidateExternalWorkspaceRequest,
)
from palwakf_orchestrator.external_execution_workspace import (
    ExternalExecutionWorkspaceService,
)
from palwakf_orchestrator.four_system_l4 import mount_four_system_l4
from palwakf_orchestrator.intersystem_contracts import (
    WorkspaceAuthorityPackageV1,
    build_workspace_authority_package,
)
from palwakf_orchestrator.local_product import LocalProductService, ManagedWorkspaceStatus
from palwakf_orchestrator.local_session import LOCAL_SESSION_COOKIE, LocalSessionManager
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
    TaskAuthorizationRequest,
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
    CreateProjectEngineeringTaskRequest,
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
    local_session_manager: LocalSessionManager | None = None,
    local_product_service: LocalProductService | None = None,
    engineering_os_service: EngineeringOsService | None = None,
    external_execution_service: ExternalExecutionWorkspaceService | None = None,
    direct_execution_service: DirectExecutionService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.assert_safe_binding()
    resolved_service = service or OrchestratorService(resolved_settings)
    resolved_store = state_store or SQLiteStateStore(resolved_settings.resolved_state_db_path)
    engineering_os = engineering_os_service or EngineeringOsService(resolved_store)
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
    execution_runs = ExecutionRunAdapter(engineering_os, resolved_operator, resolved_store)
    direct_executor = (
        OpenAIAgentsDirectTextExecutor(resolved_settings.openai_model)
        if os.environ.get("OPENAI_API_KEY")
        else None
    )
    direct_execution = direct_execution_service or DirectExecutionService(
        resolved_store,
        model=resolved_settings.openai_model,
        executor=direct_executor,
    )
    external_execution = external_execution_service or ExternalExecutionWorkspaceService(
        engineering_os,
        execution_runs,
        resolved_operator,
        resolved_store,
        workspace_root=resolved_settings.workspace_root,
        execution_host_id=resolved_settings.execution_host_id,
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
    local_sessions = local_session_manager or LocalSessionManager()
    local_product = local_product_service
    if local_product is None and (resolved_settings.workspace_root / ".git").is_dir():
        local_product = LocalProductService(
            resolved_settings.workspace_root,
            resolved_settings.repository,
            resolved_settings.governed_branch,
            resolved_settings.pull_request_number,
            resolved_operator,
            resolved_store,
        )
    dashboard = DashboardAggregationService(
        resolved_operator,
        resolved_projects,
        connected,
        resolved_store,
        resolved_settings.workspace_root,
        stale_seconds=resolved_settings.stale_project_seconds,
        local_product=local_product,
        engineering_os=engineering_os,
    )
    limiter = BoundedRateLimiter(resolved_settings.requests_per_minute)
    mcp_http_app = create_mcp_server(
        connected,
        resolved_auth,
        dashboard,
        engineering_os=engineering_os,
        execution_runs=execution_runs,
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
    app.state.dashboard_service = dashboard
    app.state.local_product_service = local_product
    app.state.engineering_os_service = engineering_os
    app.state.execution_run_adapter = execution_runs
    app.state.external_execution_workspace_service = external_execution
    app.state.direct_execution_service = direct_execution
    mount_four_system_l4(
        app,
        state_store=resolved_store,
        execution_runs=execution_runs,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=True,
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
        if request.method == "GET" and request.url.path.startswith("/local/session/"):
            return await call_next(request)
        scope = _scope_for(request)
        try:
            principal = local_sessions.require(request, scope)
            if principal is None:
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

    @app.get("/v1/auth/context", response_model=SessionAuthorizationContext)
    async def authorization_context(request: Request) -> SessionAuthorizationContext:
        principal = request.state.principal
        scopes = sorted(principal.scopes, key=lambda scope: scope.value)
        mutation_scopes = {
            ServiceScope.dispatch,
            ServiceScope.continue_task,
            ServiceScope.cancel,
            ServiceScope.verify,
            ServiceScope.probe,
        }
        return SessionAuthorizationContext(
            client_id=principal.client_id,
            scopes=scopes,
            read_only=not any(scope in principal.scopes for scope in mutation_scopes),
            can_dispatch=ServiceScope.dispatch in principal.scopes,
            can_continue=ServiceScope.continue_task in principal.scopes,
            can_cancel=ServiceScope.cancel in principal.scopes,
            can_verify=ServiceScope.verify in principal.scopes,
            can_probe_tools=ServiceScope.probe in principal.scopes,
        )

    @app.post("/local/session/issue")
    async def issue_local_session(request: Request) -> dict[str, str]:
        nonce = local_sessions.issue_launch(request.state.principal)
        return {"launch_path": f"/local/session/{nonce}"}

    @app.get("/local/session/{nonce}", include_in_schema=False)
    async def redeem_local_session(nonce: str, request: Request) -> Response:
        session_id = local_sessions.redeem_launch(nonce, request)
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(
            LOCAL_SESSION_COOKIE,
            session_id,
            max_age=28_800,
            httponly=True,
            secure=False,
            samesite="strict",
            path="/",
        )
        return response

    @app.post("/v1/local-product/bootstrap", response_model=ManagedWorkspaceStatus)
    async def bootstrap_local_product() -> ManagedWorkspaceStatus:
        if local_product is None:
            raise HTTPException(status_code=503, detail="local repository is unavailable")
        return local_product.register(refresh_remote=True)

    @app.get("/v1/local-product/status", response_model=ManagedWorkspaceStatus)
    async def local_product_status() -> ManagedWorkspaceStatus:
        if local_product is None:
            raise HTTPException(status_code=503, detail="local repository is unavailable")
        return local_product.status()

    @app.post("/v1/local-product/proof-task", response_model=OperatorTaskRecord)
    async def create_local_proof_task() -> OperatorTaskRecord:
        if local_product is None:
            raise HTTPException(status_code=503, detail="local repository is unavailable")
        try:
            return local_product.create_proof_task()
        except GovernanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/metrics", response_model=OperationalMetrics)
    async def metrics() -> OperationalMetrics:
        return connected.metrics()

    @app.get("/v1/queue", response_model=QueueSnapshot)
    async def queue() -> QueueSnapshot:
        return connected.queue_snapshot()

    @app.get("/v1/dashboard/summary", response_model=DashboardSummary)
    async def dashboard_summary() -> DashboardSummary:
        return dashboard.summary()

    @app.get("/v1/dashboard/activity", response_model=list[RecentActivityItem])
    async def dashboard_activity(
        limit: int = Query(default=30, ge=1, le=100),
    ) -> list[RecentActivityItem]:
        return dashboard.activity(limit)

    @app.get("/v1/alerts", response_model=list[OperationalAlertSummary])
    async def operational_alerts() -> list[OperationalAlertSummary]:
        return dashboard.alerts()

    @app.get("/v1/evidence", response_model=list[EvidenceIndexItem])
    async def evidence_index(
        limit: int = Query(default=50, ge=1, le=100),
    ) -> list[EvidenceIndexItem]:
        return dashboard.evidence(limit)

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

    _add_engineering_os_routes(app, engineering_os)
    _add_execution_run_routes(app, execution_runs, external_execution)
    _add_direct_execution_routes(app, direct_execution)
    _add_legacy_routes(app, resolved_operator, connected)
    _add_project_routes(app, resolved_projects, engineering_os)
    app.mount("/mcp", mcp_http_app, name="mcp")

    @app.get("/{ui_path:path}", include_in_schema=False)
    async def local_flutter_ui(ui_path: str) -> Response:
        build_root = (resolved_settings.workspace_root / "build" / "web").resolve()
        candidate = (build_root / ui_path).resolve()
        if ui_path and candidate.is_file() and build_root in candidate.parents:
            return FileResponse(candidate)
        index = build_root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="local Flutter build is not available")

    return app


def _scope_for(request: Request) -> ServiceScope:
    path = request.url.path
    if path == "/local/session/issue":
        return ServiceScope.read
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


def _add_engineering_os_routes(
    app: FastAPI,
    engineering_os: EngineeringOsService,
) -> None:
    def engineering_error(exc: GovernanceError) -> HTTPException:
        status = 404 if str(exc) == "ENGINEERING_TASK_NOT_FOUND" else 409
        return HTTPException(status_code=status, detail=str(exc))

    @app.get("/v1/engineering-os/summary", response_model=EngineeringOsSummary)
    async def engineering_os_summary() -> EngineeringOsSummary:
        return engineering_os.summary()

    @app.get(
        "/v1/engineering-os/tasks",
        response_model=list[EngineeringTaskRecord],
    )
    async def engineering_os_tasks() -> list[EngineeringTaskRecord]:
        return engineering_os.list_tasks()

    @app.post(
        "/v1/engineering-os/tasks",
        response_model=EngineeringTaskRecord,
    )
    async def create_engineering_os_task(
        command: CreateEngineeringTaskRequest,
    ) -> EngineeringTaskRecord:
        try:
            return engineering_os.create_task(command)
        except GovernanceError as exc:
            raise engineering_error(exc) from exc

    @app.post(
        "/v1/engineering-os/tasks/{task_id}/checkpoint",
        response_model=EngineeringTaskRecord,
    )
    async def checkpoint_engineering_os_task(
        task_id: str,
        command: RemoteCheckpointRequest,
    ) -> EngineeringTaskRecord:
        try:
            return engineering_os.checkpoint_task(task_id, command)
        except GovernanceError as exc:
            raise engineering_error(exc) from exc

    @app.get("/v1/extensions", response_model=list[ExtensionRecord])
    async def list_extensions() -> list[ExtensionRecord]:
        return engineering_os.list_extensions()

    @app.post("/v1/extensions", response_model=ExtensionRecord)
    async def register_extension(
        command: RegisterExtensionRequest,
    ) -> ExtensionRecord:
        try:
            return engineering_os.register_extension(command)
        except GovernanceError as exc:
            raise engineering_error(exc) from exc


def _add_execution_run_routes(
    app: FastAPI,
    execution_runs: ExecutionRunAdapter,
    external_execution: ExternalExecutionWorkspaceService | None = None,
) -> None:
    def execution_error(exc: GovernanceError) -> HTTPException:
        missing = str(exc) in {"ENGINEERING_TASK_NOT_FOUND", "EXECUTION_RUN_NOT_FOUND"}
        return HTTPException(status_code=404 if missing else 409, detail=str(exc))

    @app.get(
        "/v1/execution-runs/{execution_run_id}/intersystem/authority-package",
        response_model=WorkspaceAuthorityPackageV1,
    )
    async def intersystem_authority_package(
        execution_run_id: str,
    ) -> WorkspaceAuthorityPackageV1:
        try:
            view = execution_runs.get_operational_view(execution_run_id)
            return build_workspace_authority_package(view)
        except GovernanceError as exc:
            raise execution_error(exc) from exc

    @app.get(
        "/v1/engineering-os/tasks/{task_id}/execution-context",
        response_model=EngineeringTaskExecutionContext,
    )
    async def engineering_task_execution_context(
        task_id: str,
    ) -> EngineeringTaskExecutionContext:
        try:
            return execution_runs.execution_context(task_id)
        except GovernanceError as exc:
            raise execution_error(exc) from exc

    @app.post(
        "/v1/engineering-os/tasks/{task_id}/runs",
        response_model=ExecutionRunOperationalView,
    )
    async def create_engineering_execution_run(
        task_id: str,
        command: CreateExecutionRunRequest,
    ) -> ExecutionRunOperationalView:
        try:
            return execution_runs.create_governed_run(task_id, command)
        except GovernanceError as exc:
            raise execution_error(exc) from exc

    @app.get(
        "/v1/execution-runs/{execution_run_id}",
        response_model=ExecutionRunOperationalView,
    )
    async def execution_run_status(
        execution_run_id: str,
    ) -> ExecutionRunOperationalView:
        try:
            return execution_runs.get_operational_view(execution_run_id)
        except GovernanceError as exc:
            raise execution_error(exc) from exc

    if external_execution is not None:

        @app.get(
            "/v1/execution-runs/{execution_run_id}/workspace",
            response_model=ExternalExecutionWorkspaceStatus,
        )
        async def external_workspace_status(
            execution_run_id: str,
        ) -> ExternalExecutionWorkspaceStatus:
            try:
                return external_execution.status(execution_run_id)
            except GovernanceError as exc:
                raise execution_error(exc) from exc

        @app.post(
            "/v1/execution-runs/{execution_run_id}/workspace/prepare",
            response_model=ExternalExecutionWorkspaceStatus,
        )
        async def prepare_external_workspace(
            execution_run_id: str,
            command: PrepareExternalWorkspaceRequest,
        ) -> ExternalExecutionWorkspaceStatus:
            try:
                return external_execution.prepare(execution_run_id, command)
            except GovernanceError as exc:
                raise execution_error(exc) from exc

        @app.post(
            "/v1/execution-runs/{execution_run_id}/workspace/apply",
            response_model=ExternalExecutionWorkspaceStatus,
        )
        async def apply_external_workspace(
            execution_run_id: str,
            command: ApplyExternalWorkspaceRequest,
        ) -> ExternalExecutionWorkspaceStatus:
            try:
                return external_execution.apply(execution_run_id, command)
            except GovernanceError as exc:
                raise execution_error(exc) from exc

        @app.post(
            "/v1/execution-runs/{execution_run_id}/workspace/validate",
            response_model=ExternalExecutionWorkspaceStatus,
        )
        async def validate_external_workspace(
            execution_run_id: str,
            command: ValidateExternalWorkspaceRequest,
        ) -> ExternalExecutionWorkspaceStatus:
            try:
                return external_execution.validate(execution_run_id, command)
            except GovernanceError as exc:
                raise execution_error(exc) from exc

        @app.post(
            "/v1/execution-runs/{execution_run_id}/workspace/checkpoint",
            response_model=ExternalExecutionWorkspaceStatus,
        )
        async def checkpoint_external_workspace(
            execution_run_id: str,
            command: CheckpointExternalWorkspaceRequest,
        ) -> ExternalExecutionWorkspaceStatus:
            try:
                return external_execution.checkpoint(execution_run_id, command)
            except GovernanceError as exc:
                raise execution_error(exc) from exc


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

    @app.post("/v1/tasks/{task_id}/authorize", response_model=OperatorTaskRecord)
    async def authorize_task(
        task_id: str,
        command: TaskAuthorizationRequest,
        request: Request,
    ) -> OperatorTaskRecord:
        try:
            return operator.authorize_task(
                task_id,
                command,
                principal_id=request.state.principal.client_id,
            )
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
        try:
            return operator.tool_decisions(task_id)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.get(
        "/v1/tasks/{task_id}/tool-invocations",
        response_model=list[ToolInvocationReceipt],
    )
    async def tool_invocations(task_id: str) -> list[ToolInvocationReceipt]:
        try:
            return operator.tool_invocations(task_id)
        except GovernanceError as exc:
            raise conflict(exc) from exc

    @app.get(
        "/v1/tasks/{task_id}/tool-reconciliation",
        response_model=ToolReconciliation,
    )
    async def tool_reconciliation(task_id: str) -> ToolReconciliation:
        try:
            return operator.reconcile_tools(task_id)
        except GovernanceError as exc:
            raise conflict(exc) from exc


def _add_project_routes(
    app: FastAPI,
    projects: ExternalProjectService,
    engineering_os: EngineeringOsService,
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

    @app.post(
        "/v1/projects/{project_id}/candidate-work-items/{candidate_id}/engineering-task",
        response_model=EngineeringTaskRecord,
    )
    async def create_external_project_engineering_task(
        project_id: str,
        candidate_id: str,
        command: CreateProjectEngineeringTaskRequest,
    ) -> EngineeringTaskRecord:
        try:
            prepared = projects.prepare_engineering_task_request(
                project_id,
                candidate_id,
                command,
            )
            return engineering_os.create_task(prepared)
        except GovernanceError as exc:
            raise project_error(exc) from exc

def _add_direct_execution_routes(
    app: FastAPI,
    direct_execution: DirectExecutionService,
) -> None:
    @app.post(
        "/v1/direct-execution/sessions",
        response_model=DirectExecutionReceipt,
    )
    async def execute_direct_workspace_item(
        command: DirectExecutionRequest,
    ) -> DirectExecutionReceipt:
        try:
            return await direct_execution.execute(command)
        except DirectExecutionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/v1/direct-execution/sessions/{session_id}",
        response_model=DirectExecutionReceipt,
    )
    async def direct_execution_status(session_id: str) -> DirectExecutionReceipt:
        try:
            return direct_execution.get(session_id)
        except DirectExecutionError as exc:
            status = 404 if str(exc) == "DIRECT_EXECUTION_SESSION_NOT_FOUND" else 409
            raise HTTPException(status_code=status, detail=str(exc)) from exc
