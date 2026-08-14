from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import ServiceScope
from palwakf_orchestrator.dashboard_service import DashboardAggregationService
from palwakf_orchestrator.local_product import LocalProductService
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore
from tests.test_service import build_service

READ_TOKEN = "semantic-read-token"
FULL_TOKEN = "semantic-full-token"
READ_AUTH = {"Authorization": f"Bearer {READ_TOKEN}"}
FULL_AUTH = {"Authorization": f"Bearer {FULL_TOKEN}"}


def build_app(tmp_path: Path):
    credentials = [
        {
            "client_id": "semantic-read-client",
            "token_sha256": hashlib.sha256(READ_TOKEN.encode()).hexdigest(),
            "scopes": [ServiceScope.read.value],
        },
        {
            "client_id": "semantic-full-client",
            "token_sha256": hashlib.sha256(FULL_TOKEN.encode()).hexdigest(),
            "scopes": [scope.value for scope in ServiceScope],
        },
    ]
    store = MemoryStateStore()
    return create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=store,
        auth_registry=AuthRegistry.from_json(json.dumps(credentials)),
    )


@pytest.mark.asyncio
async def test_auth_context_exposes_effective_scopes_without_secret(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        read = await client.get("/v1/auth/context", headers=READ_AUTH)
        full = await client.get("/v1/auth/context", headers=FULL_AUTH)

    assert read.status_code == 200
    assert read.json() == {
        "client_id": "semantic-read-client",
        "scopes": ["tasks:read"],
        "read_only": True,
        "can_dispatch": False,
        "can_continue": False,
        "can_cancel": False,
        "can_verify": False,
        "can_probe_tools": False,
    }
    assert full.status_code == 200
    assert full.json()["read_only"] is False
    assert full.json()["can_dispatch"] is True
    assert full.json()["can_probe_tools"] is True
    assert READ_TOKEN not in read.text
    assert FULL_TOKEN not in full.text


@pytest.mark.asyncio
async def test_dashboard_includes_engineering_os_task_truth(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    payload = {
        "task_id": "WM-SEMANTIC-UAT-1",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "title": "Semantic integrity witness",
        "description": "Engineering OS task must appear in dashboard truth.",
        "repository": "firasfanon/palwakf_workspace_manager",
        "base_sha": "a" * 40,
        "task_branch": "task/WM-SEMANTIC-UAT-1",
        "owner_id": "firas",
        "actor_id": "firas",
        "actor_type": "HUMAN",
        "scope_patterns": ["lib/**"],
        "depends_on": [],
        "dependency_mode": "INDEPENDENT",
        "risk_class": "LOW",
        "mutation_class": "read-only",
        "required_capabilities": [],
        "required_tests": ["semantic-integrity"],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/v1/engineering-os/tasks",
            headers=FULL_AUTH,
            json=payload,
        )
        dashboard = await client.get("/v1/dashboard/summary", headers=READ_AUTH)

    assert created.status_code == 200
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["tasks"]["total"] == 1
    assert body["tasks"]["active_task_ids"] == ["WM-SEMANTIC-UAT-1"]
    assert body["tasks"]["provenance"] == ("UNIFIED_OPERATOR_AND_ENGINEERING_OS_TASK_STORES")
    assert "ENGINEERING_OS_TASK_STORE" in body["provenance"]
    assert body["checkpoints"][0]["task_id"] == "WM-SEMANTIC-UAT-1"


def test_codex_installation_is_not_reported_as_execution_authority() -> None:
    state = LocalProductService._codex_state()

    assert state.status == "SUSPENDED_BY_POLICY"
    assert state.authorized is False
    assert state.policy == "GLOBAL_GOVERNANCE_2026-08-08"


def test_checkout_branch_truth_is_separate_from_governed_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStateStore()
    operator = OperatorService(tmp_path, state_store=store)
    product = LocalProductService(
        tmp_path,
        "firasfanon/palwakf_workspace_manager",
        "agent/workspace-manager-foundation-v1",
        1,
        operator,
        store,
    )
    checkout_sha = "b" * 40
    governed_sha = "f" * 40

    def fake_git(*args: str) -> str:
        if args == ("branch", "--show-current"):
            return "task/current-semantic-hotfix"
        if args == ("rev-parse", "HEAD"):
            return checkout_sha
        if args == ("status", "--porcelain"):
            return ""
        if args == (
            "ls-remote",
            "origin",
            "refs/heads/task/current-semantic-hotfix",
        ):
            return f"{checkout_sha}\trefs/heads/task/current-semantic-hotfix"
        if args == (
            "ls-remote",
            "origin",
            "refs/heads/agent/workspace-manager-foundation-v1",
        ):
            return f"{governed_sha}\trefs/heads/agent/workspace-manager-foundation-v1"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(product, "_git", fake_git)

    status = product.register(refresh_remote=False)

    assert status.branch == "task/current-semantic-hotfix"
    assert status.checkout_branch == "task/current-semantic-hotfix"
    assert status.checkout_head == checkout_sha
    assert status.remote_head == checkout_sha
    assert status.governed_branch == "agent/workspace-manager-foundation-v1"
    assert status.governed_remote_head == governed_sha


def test_operational_alert_human_text_is_arabic_first() -> None:
    message, action = DashboardAggregationService._localized_tool_alert(
        "AUTHENTICATION_UNVERIFIED",
        "github",
    )

    assert "لا توجد أدلة" in message
    assert "فحصًا موثقًا" in action
    assert "AUTHENTICATION_UNVERIFIED" not in message
