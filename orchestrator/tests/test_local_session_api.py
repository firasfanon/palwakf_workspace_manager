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
        assert redeem.headers["location"] == "/#/dashboard"
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



@pytest.mark.asyncio
async def test_direct_dashboard_browser_request_fails_closed_with_human_entrypoint(
    tmp_path: Path,
) -> None:
    app = build_readonly_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 43212)),
        base_url="http://127.0.0.1",
    ) as client:
        response = await client.get(
            "/dashboard",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("text/html")
    assert "PALWAKF_LOCAL_AUTHENTICATED_ENTRYPOINT_REQUIRED" in response.text
    assert (
        "\u064a\u0644\u0632\u0645 \u0628\u062f\u0621 \u062c\u0644\u0633\u0629 "
        "\u0645\u062d\u0644\u064a\u0629 \u0622\u0645\u0646\u0629"
        in response.text
    )
    assert (
        "\u0647\u0630\u0647 \u0627\u0644\u0635\u0641\u062d\u0629 \u0645\u062d\u0645\u064a\u0629"
        in response.text
    )
    assert ".\\Start-PalWakfWorkspaceManager.ps1" in response.text
    assert '{"detail":"valid bearer authentication is required"}' not in response.text


@pytest.mark.asyncio
async def test_unauthenticated_dashboard_api_remains_json_bearer_challenge(
    tmp_path: Path,
) -> None:
    app = build_readonly_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 43213)),
        base_url="http://127.0.0.1",
    ) as client:
        response = await client.get("/v1/dashboard/summary")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "valid bearer authentication is required"

@pytest.mark.asyncio
async def test_local_ui_static_assets_bypass_auth_and_api_rate_budget(
    tmp_path: Path,
) -> None:
    build_root = tmp_path / "build" / "web"
    build_root.mkdir(parents=True)
    (build_root / "manifest.json").write_text(
        '{"name":"PalWakf Workspace Manager"}',
        encoding="utf-8",
    )
    (build_root / "main.dart.js").write_text(
        'console.log("palwakf");',
        encoding="utf-8",
    )
    (build_root / "NOTICES").write_text(
        "PalWakf local asset",
        encoding="utf-8",
    )

    app = create_app(
        Settings(workspace_root=tmp_path, requests_per_minute=1),
        build_service(tmp_path),
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing(
            "local-session-read-client",
            READ_TOKEN,
            scopes=(ServiceScope.read,),
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 43214)),
        base_url="http://127.0.0.1",
    ) as client:
        manifest = await client.get("/manifest.json")
        script = await client.get("/main.dart.js")
        notices = await client.get("/NOTICES")
        missing_favicon = await client.get("/favicon.ico")
        protected_openapi = await client.get("/openapi.json")

        assert manifest.status_code == 200
        assert manifest.json()["name"] == "PalWakf Workspace Manager"
        assert manifest.headers["cache-control"] == "no-store"
        assert manifest.headers["x-content-type-options"] == "nosniff"

        assert script.status_code == 200
        assert "palwakf" in script.text
        assert script.headers["cache-control"] == "no-store"
        assert script.headers["x-content-type-options"] == "nosniff"

        assert notices.status_code == 200
        assert notices.text == "PalWakf local asset"

        assert missing_favicon.status_code == 404

        assert protected_openapi.status_code == 401
        assert protected_openapi.headers["www-authenticate"] == "Bearer"

        first_api = await client.get("/v1/dashboard/summary", headers=READ_AUTH)
        assert first_api.status_code == 200

        second_api = await client.get("/v1/dashboard/summary", headers=READ_AUTH)
        assert second_api.status_code == 429
        assert second_api.json()["detail"] == "client rate limit exceeded"


@pytest.mark.asyncio
async def test_local_ui_html_entrypoint_stays_authenticated(tmp_path: Path) -> None:
    build_root = tmp_path / "build" / "web"
    build_root.mkdir(parents=True)
    (build_root / "index.html").write_text(
        "<!doctype html><title>PalWakf</title>",
        encoding="utf-8",
    )

    app = build_readonly_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 43215)),
        base_url="http://127.0.0.1",
    ) as client:
        response = await client.get(
            "/index.html",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
