from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import ServiceScope
from palwakf_orchestrator.persistence import MemoryStateStore
from tests.test_service import build_service

READ_TOKEN = "local-session-read-token"
READ_AUTH = {"Authorization": f"Bearer {READ_TOKEN}"}


def build_readonly_app(tmp_path: Path):
    return create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing(
            "local-session-read-client",
            READ_TOKEN,
            scopes=(ServiceScope.read,),
        ),
    )


@pytest.mark.asyncio
async def test_read_scope_can_issue_readonly_local_session(tmp_path: Path) -> None:
    app = build_readonly_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 43210)),
        base_url="http://127.0.0.1",
        follow_redirects=False,
    ) as client:
        issue = await client.post("/local/session/issue", headers=READ_AUTH)

        assert issue.status_code == 200
        launch_path = issue.json()["launch_path"]
        assert launch_path.startswith("/local/session/")

        redeem = await client.get(launch_path)

        assert redeem.status_code == 303
        assert redeem.headers["location"] == "/dashboard"
        cookie = redeem.headers["set-cookie"]
        assert "palwakf_local_session=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/" in cookie

        dashboard = await client.get("/v1/dashboard/summary")
        assert dashboard.status_code == 200

        mutation = await client.post("/v1/engineering-os/tasks", json={})
        assert mutation.status_code == 403
        assert mutation.json()["detail"] == "missing scope: tasks:dispatch"

        second_redeem = await client.get(launch_path)
        assert second_redeem.status_code == 401
        assert second_redeem.json()["detail"] == ("local launch session is invalid or expired")


@pytest.mark.asyncio
async def test_local_session_issue_rejects_invalid_bearer(tmp_path: Path) -> None:
    app = build_readonly_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 43211)),
        base_url="http://127.0.0.1",
    ) as client:
        response = await client.post(
            "/local/session/issue",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "valid bearer authentication is required"
