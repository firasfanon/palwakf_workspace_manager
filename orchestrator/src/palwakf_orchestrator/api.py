from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from palwakf_orchestrator.config import Settings, get_settings
from palwakf_orchestrator.contracts import DispatchRequest, DispatchResponse, HealthResponse
from palwakf_orchestrator.errors import GatewayError, GovernanceError
from palwakf_orchestrator.service import OrchestratorService


def create_app(
    settings: Settings | None = None,
    service: OrchestratorService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_service = service or OrchestratorService(resolved_settings)
    app = FastAPI(
        title="PalWakf Sovereign Orchestrator",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return resolved_service.health()

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
