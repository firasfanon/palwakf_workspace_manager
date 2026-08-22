from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.local_product import (
    SELF_HOSTED_PROOF_IDEMPOTENCY_KEY,
    SELF_HOSTED_PROOF_TASK_ID,
    LocalProductService,
)
from palwakf_orchestrator.operator_contracts import OperatorTaskStatus, TaskAuthorizationRequest
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore
from tests.test_service import build_service

TOKEN = "local-product-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeGitHub:
    def __init__(self, head: str) -> None:
        self.head = head

    def get_json(self, path: str) -> dict[str, Any]:
        if path.startswith("pulls/"):
            return {"state": "open", "head": {"sha": self.head}}
        if path.startswith("actions/runs"):
            return {
                "workflow_runs": [
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://github.com/example/actions/runs/1",
                    }
                ]
            }
        if path.startswith("commits/"):
            return {
                "statuses": [
                    {
                        "context": "Vercel",
                        "state": "success",
                        "target_url": "https://example.vercel.app",
                    }
                ]
            }
        raise AssertionError(f"unexpected GitHub path: {path}")


class SuccessfulCiVerifier:
    def status(self, head: str) -> tuple[str, str]:
        return "success", "github-actions-run-123"


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str]:
    workspace = tmp_path / "workspace"
    remote = tmp_path / "remote.git"
    workspace.mkdir()
    _git(workspace, "init")
    _git(workspace, "config", "user.name", "PalWakf Test")
    _git(workspace, "config", "user.email", "test@example.invalid")
    _git(workspace, "checkout", "-b", "agent/workspace-manager-foundation-v1")
    (workspace / "README.md").write_text("test\n", encoding="utf-8")
    _git(workspace, "add", "README.md")
    _git(workspace, "commit", "-m", "test")
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    _git(workspace, "remote", "add", "origin", str(remote))
    _git(workspace, "push", "-u", "origin", "agent/workspace-manager-foundation-v1")
    return workspace, _git(workspace, "rev-parse", "HEAD")


def test_self_registration_and_proof_authorization_are_persisted(tmp_path: Path) -> None:
    workspace, head = _repository(tmp_path)
    store = MemoryStateStore()
    operator = OperatorService(workspace, state_store=store)
    product = LocalProductService(
        workspace,
        "firasfanon/palwakf_workspace_manager",
        "agent/workspace-manager-foundation-v1",
        1,
        operator,
        store,
        github=FakeGitHub(head),
    )

    status = product.register()
    task = product.create_proof_task()
    replay = product.create_proof_task()
    authorized = operator.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=head,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="local-ui",
    )

    assert status.registered
    assert status.local_head == status.remote_head == status.pull_request_head == head
    assert status.ci_status == "SUCCESS"
    assert task.task_id == SELF_HOSTED_PROOF_TASK_ID
    assert task.idempotency_key == SELF_HOSTED_PROOF_IDEMPOTENCY_KEY
    assert replay.created_at == task.created_at
    assert authorized.authorized_at is not None
    assert authorized.authorized_by == "local-ui"
    assert store.load()["managed_workspace"]["repository"] == status.repository


@pytest.mark.asyncio
async def test_exact_self_hosted_head_is_verified_by_github_ci(tmp_path: Path) -> None:
    workspace, head = _repository(tmp_path)
    store = MemoryStateStore()
    operator = OperatorService(workspace, state_store=store)
    product = LocalProductService(
        workspace,
        "firasfanon/palwakf_workspace_manager",
        "agent/workspace-manager-foundation-v1",
        1,
        operator,
        store,
        github=FakeGitHub(head),
    )
    task = product.create_proof_task()
    operator.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=head,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="local-ui",
    )
    task.status = OperatorTaskStatus.pending_verification
    task.after_head = head
    connected = ConnectedApplicationService(
        Settings(workspace_root=workspace),
        operator,
        store,
        authentication_configured=True,
        ci_verifier=SuccessfulCiVerifier(),  # type: ignore[arg-type]
    )

    await connected._verify_self_hosted_ci(task)

    verified = operator.get_task(task.task_id)
    assert verified.status == OperatorTaskStatus.verified
    assert verified.verification_receipt == "github-actions-run-123"


@pytest.mark.asyncio
async def test_local_session_is_one_time_and_cookie_authenticates(tmp_path: Path) -> None:
    app = create_app(
        Settings(workspace_root=tmp_path),
        build_service(tmp_path),
        state_store=MemoryStateStore(),
        auth_registry=AuthRegistry.for_testing("local-ui", TOKEN),
    )
    transport = ASGITransport(app=app, client=("127.0.0.1", 43123))
    async with AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
        follow_redirects=False,
    ) as client:
        issued = await client.post("/local/session/issue", headers=AUTH)
        launch_path = issued.json()["launch_path"]
        redeemed = await client.get(launch_path)
        capabilities = await client.get("/v1/capabilities")
        replay = await client.get(launch_path)

    assert issued.status_code == 200
    assert redeemed.status_code == 303
    assert "palwakf_local_session=" in redeemed.headers["set-cookie"]
    assert "HttpOnly" in redeemed.headers["set-cookie"]
    assert capabilities.status_code == 200
    assert replay.status_code == 401


def test_root_launchers_do_not_embed_runtime_credentials() -> None:
    repository = Path(__file__).resolve().parents[2]
    start = (repository / "Start-PalWakfWorkspaceManager.ps1").read_text(encoding="utf-8")
    stop = (repository / "Stop-PalWakfWorkspaceManager.ps1").read_text(encoding="utf-8")

    assert "ORCHESTRATOR_SESSION_TOKEN" not in start
    assert "OPENAI_API_KEY=" not in start
    assert "local/session/issue" in start
    assert "protected_local_token" in start
    assert "Stop-Process" in stop
