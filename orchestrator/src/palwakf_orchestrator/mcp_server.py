from __future__ import annotations

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.connected_contracts import (
    ClientPrincipal,
    ConnectedDispatchRequest,
    ContinueTaskRequest,
    ServiceScope,
    VerifyCommand,
)
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.dashboard_service import DashboardAggregationService


class RegistryTokenVerifier:
    def __init__(self, registry: AuthRegistry) -> None:
        self._registry = registry

    async def verify_token(self, token: str) -> AccessToken | None:
        principal = self._registry.authenticate(token)
        if principal is None:
            return None
        return AccessToken(
            token="verified",
            client_id=principal.client_id,
            scopes=[scope.value for scope in principal.scopes],
        )


def _principal(required: ServiceScope) -> ClientPrincipal:
    access = get_access_token()
    if access is None:
        raise PermissionError("authenticated MCP client is required")
    principal = ClientPrincipal(
        client_id=access.client_id,
        scopes=frozenset(ServiceScope(scope) for scope in access.scopes),
    )
    principal.require(required)
    return principal


def create_mcp_server(
    application: ConnectedApplicationService,
    auth_registry: AuthRegistry,
    dashboard: DashboardAggregationService | None = None,
) -> FastMCP:
    settings = application.settings
    issuer_url = settings.oauth_authorization_server or "http://localhost:8421"
    resource_url = settings.public_base_url or "http://localhost:8421/mcp"
    server = FastMCP(
        name="PalWakf Workspace Manager",
        instructions=(
            "Authenticated governed task dispatch. Mutations require explicit scoped authority."
        ),
        token_verifier=RegistryTokenVerifier(auth_registry),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer_url),
            resource_server_url=AnyHttpUrl(resource_url),
            # Tool handlers enforce distinct read/write scopes.
            required_scopes=[],
        ),
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(description="Dispatch one governed Codex task using the bounded queue.")
    async def dispatch_codex_task(
        request: ConnectedDispatchRequest,
    ) -> dict[str, object]:
        result = await application.dispatch(
            request,
            _principal(ServiceScope.dispatch),
            transport="mcp",
        )
        return result.model_dump(mode="json")

    @server.tool(description="Continue the same compatible persisted Codex task.")
    async def continue_codex_task(
        task_id: str,
        command: ContinueTaskRequest,
    ) -> dict[str, object]:
        result = await application.continue_task(
            task_id,
            command,
            _principal(ServiceScope.continue_task),
            transport="mcp",
        )
        return result.model_dump(mode="json")

    @server.tool(description="Read the persisted status of a governed Codex task.")
    def get_codex_task_status(task_id: str) -> dict[str, object]:
        result = application.status(
            task_id,
            _principal(ServiceScope.read),
            transport="mcp",
        )
        return result.model_dump(mode="json")

    @server.tool(description="Cancel a queued or running governed Codex task.")
    def cancel_codex_task(task_id: str) -> dict[str, object]:
        result = application.cancel(
            task_id,
            _principal(ServiceScope.cancel),
            transport="mcp",
        )
        return result.model_dump(mode="json")

    @server.tool(description="Persist independent verification for a completed task.")
    def verify_codex_result(
        task_id: str,
        command: VerifyCommand,
    ) -> dict[str, object]:
        result = application.verify(
            task_id,
            command,
            _principal(ServiceScope.verify),
            transport="mcp",
        )
        return result.model_dump(mode="json")

    @server.tool(description="List recent governed tasks without exposing credentials.")
    def list_recent_tasks(limit: int = 50) -> list[dict[str, object]]:
        _principal(ServiceScope.read)
        return [task.model_dump(mode="json") for task in application.list_recent(limit)]

    if dashboard is not None:

        @server.tool(description="Read the authoritative workspace dashboard summary.")
        def get_workspace_dashboard() -> dict[str, object]:
            _principal(ServiceScope.read)
            return dashboard.summary().model_dump(mode="json")

        @server.tool(description="List bounded operational alerts.")
        def list_operational_alerts() -> list[dict[str, object]]:
            _principal(ServiceScope.read)
            return [item.model_dump(mode="json") for item in dashboard.alerts()]

        @server.tool(description="List bounded safe evidence references.")
        def list_workspace_evidence(limit: int = 50) -> list[dict[str, object]]:
            _principal(ServiceScope.read)
            bounded = min(max(limit, 1), 100)
            return [
                item.model_dump(mode="json") for item in dashboard.evidence(bounded)
            ]

        @server.tool(description="List bounded recent workspace activity.")
        def list_workspace_activity(limit: int = 30) -> list[dict[str, object]]:
            _principal(ServiceScope.read)
            bounded = min(max(limit, 1), 100)
            return [
                item.model_dump(mode="json") for item in dashboard.activity(bounded)
            ]

    return server
