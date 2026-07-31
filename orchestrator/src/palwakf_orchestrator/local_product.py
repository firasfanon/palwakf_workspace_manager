from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskRecord,
    OperatorTaskStatus,
    TaskCapabilityRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import StateStore

SELF_HOSTED_PROOF_TASK_ID = "PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1"
SELF_HOSTED_PROOF_IDEMPOTENCY_KEY = "palwakf-self-hosted-last-execution-card-v1"


class CapabilityState(BaseModel):
    status: str
    blocker: str | None = None
    last_success_at: datetime | None = None


class ManagedWorkspaceStatus(BaseModel):
    registered: bool
    repository: str
    branch: str
    pull_request_number: int
    local_head: str | None
    remote_head: str | None
    pull_request_head: str | None
    worktree_clean: bool | None
    pull_request_state: str
    ci_status: str
    ci_run_url: str | None
    preview_status: str
    preview_url: str | None
    active_writer_task_id: str | None
    current_task_id: str | None
    latest_verified_task_id: str | None
    latest_checkpoint: str | None
    github: CapabilityState
    agents_sdk: CapabilityState
    codex: CapabilityState
    authentication: CapabilityState
    orchestrator: CapabilityState
    refreshed_at: datetime
    provenance: list[str]


class GitHubReadClient(Protocol):
    def get_json(self, path: str) -> dict[str, Any]: ...


class HttpxGitHubStatusClient:
    def __init__(self, repository: str, token: str | None = None) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "PalWakf-Workspace-Manager",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._repository = repository
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers=headers,
            timeout=15,
            follow_redirects=False,
        )

    def get_json(self, path: str) -> dict[str, Any]:
        response = self._client.get(f"/repos/{self._repository}/{path.lstrip('/')}")
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("GitHub returned a non-object response")
        return value


class LocalProductService:
    def __init__(
        self,
        workspace: Path,
        repository: str,
        branch: str,
        pull_request_number: int,
        operator: OperatorService,
        store: StateStore,
        *,
        github: GitHubReadClient | None = None,
    ) -> None:
        self._workspace = workspace.resolve()
        self._repository = repository
        self._branch = branch
        self._pull_request_number = pull_request_number
        self._operator = operator
        self._store = store
        self._github = github or HttpxGitHubStatusClient(
            repository,
            os.environ.get("GITHUB_TOKEN"),
        )

    def register(self, *, refresh_remote: bool = True) -> ManagedWorkspaceStatus:
        local_head = self._git("rev-parse", "HEAD")
        remote_head = self._remote_head()
        clean = not bool(self._git("status", "--porcelain"))
        pr_head: str | None = None
        pr_state = "UNKNOWN"
        ci_status = "UNKNOWN"
        ci_run_url: str | None = None
        preview_status = "UNKNOWN"
        preview_url: str | None = None
        github_state = CapabilityState(status="UNKNOWN", blocker="GITHUB_NOT_REFRESHED")

        if refresh_remote:
            try:
                pull = self._github.get_json(f"pulls/{self._pull_request_number}")
                pr_head = self._nested_text(pull, "head", "sha")
                pr_state = str(pull.get("state") or "UNKNOWN").upper()
                runs = self._github.get_json(
                    f"actions/runs?branch={self._branch.replace('/', '%2F')}&per_page=1"
                )
                workflow_runs = runs.get("workflow_runs")
                if isinstance(workflow_runs, list) and workflow_runs:
                    run = workflow_runs[0]
                    if isinstance(run, dict):
                        run_status = str(run.get("status") or "UNKNOWN").upper()
                        conclusion = str(run.get("conclusion") or "").upper()
                        ci_status = (
                            conclusion if run_status == "COMPLETED" and conclusion else run_status
                        )
                        ci_run_url = self._safe_https(run.get("html_url"))
                commit_status = self._github.get_json(f"commits/{local_head}/status")
                statuses = commit_status.get("statuses")
                if isinstance(statuses, list):
                    for item in statuses:
                        if not isinstance(item, dict) or item.get("context") != "Vercel":
                            continue
                        preview_status = str(item.get("state") or "UNKNOWN").upper()
                        preview_url = self._safe_https(item.get("target_url"))
                        break
                github_state = CapabilityState(
                    status="CONNECTED",
                    last_success_at=datetime.now(UTC),
                )
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                github_state = CapabilityState(
                    status="BLOCKED",
                    blocker=f"GITHUB_READ_FAILED:{type(exc).__name__}",
                )

        tasks = self._operator.list_tasks()
        active = next(
            (
                task
                for task in tasks
                if task.status
                in {
                    OperatorTaskStatus.queued,
                    OperatorTaskStatus.running,
                    OperatorTaskStatus.awaiting_approval,
                    OperatorTaskStatus.pending_verification,
                }
            ),
            None,
        )
        latest_verified = next(
            (task for task in tasks if task.status == OperatorTaskStatus.verified),
            None,
        )
        writer = self._store.writer_for(self._repository)
        now = datetime.now(UTC)
        status = ManagedWorkspaceStatus(
            registered=True,
            repository=self._repository,
            branch=self._branch,
            pull_request_number=self._pull_request_number,
            local_head=local_head,
            remote_head=remote_head,
            pull_request_head=pr_head,
            worktree_clean=clean,
            pull_request_state=pr_state,
            ci_status=ci_status,
            ci_run_url=ci_run_url,
            preview_status=preview_status,
            preview_url=preview_url,
            active_writer_task_id=writer["task_id"] if writer else None,
            current_task_id=active.task_id if active else None,
            latest_verified_task_id=latest_verified.task_id if latest_verified else None,
            latest_checkpoint=active.last_event
            if active
            else (latest_verified.last_event if latest_verified else None),
            github=github_state,
            agents_sdk=self._module_state("agents"),
            codex=self._module_state("openai_codex"),
            authentication=CapabilityState(status="VERIFIED"),
            orchestrator=CapabilityState(status="CONNECTED"),
            refreshed_at=now,
            provenance=[
                "LOCAL_GIT",
                "GIT_REMOTE",
                "GITHUB_API",
                "OPERATOR_TASK_STORE",
                "REPOSITORY_WRITER_STORE",
            ],
        )
        state = self._store.load()
        state["managed_workspace"] = status.model_dump(mode="json")
        self._store.save(state)
        return status

    def status(self) -> ManagedWorkspaceStatus:
        persisted = self._store.load().get("managed_workspace")
        if isinstance(persisted, dict):
            current = self.register(refresh_remote=False)
            merged = current.model_copy(
                update={
                    "pull_request_head": persisted.get("pull_request_head"),
                    "pull_request_state": persisted.get("pull_request_state", "UNKNOWN"),
                    "ci_status": persisted.get("ci_status", "UNKNOWN"),
                    "ci_run_url": persisted.get("ci_run_url"),
                    "preview_status": persisted.get("preview_status", "UNKNOWN"),
                    "preview_url": persisted.get("preview_url"),
                    "github": CapabilityState.model_validate(
                        persisted.get("github", {"status": "UNKNOWN"})
                    ),
                }
            )
            state = self._store.load()
            state["managed_workspace"] = merged.model_dump(mode="json")
            self._store.save(state)
            return merged
        return self.register(refresh_remote=False)

    def create_proof_task(self) -> OperatorTaskRecord:
        status = self.register(refresh_remote=True)
        if (
            not status.worktree_clean
            or not status.local_head
            or status.local_head != status.remote_head
            or status.local_head != status.pull_request_head
        ):
            raise GovernanceError("proof task requires clean matching local, remote, and PR HEAD")
        task = self._operator.create_task(
            CreateOperatorTaskRequest(
                task_id=SELF_HOSTED_PROOF_TASK_ID,
                project_id="PALWAKF_WORKSPACE_MANAGER",
                repository="firasfanon/palwakf_workspace_manager",
                branch="agent/workspace-manager-foundation-v1",
                expected_head=status.local_head,
                authority_reference=(
                    "GOOGLE_DOC://PALWAKF_WORKSPACE_MANAGER_LOCAL_FIRST_"
                    "SELF_HOSTING_PRODUCT_COMPLETION_V1"
                ),
                prompt=self._proof_prompt(status.local_head),
                constraints=[
                    "ONLY_WORKSPACE_MANAGER_REPOSITORY",
                    "NO_EXTERNAL_PROJECT_ACCESS",
                    "NO_DATABASE_OR_SUPABASE",
                    "NO_PRODUCTION_PROMOTION",
                    "NO_SECRET_ACCESS",
                    "ONE_FOCUSED_COMMIT",
                    "PUSH_EXISTING_BRANCH_AND_PR_ONLY",
                ],
                sandbox="workspace-write",
                max_turns=12,
                timeout_seconds=1_800,
                idempotency_key=SELF_HOSTED_PROOF_IDEMPOTENCY_KEY,
                requires_explicit_authorization=True,
            )
        )
        try:
            self._operator.tool_decisions(task.task_id)
        except GovernanceError:
            self._operator.plan_tools(
                task.task_id,
                TaskCapabilityRequest(
                    task_id=task.task_id,
                    project_id=task.project_id,
                    task_type="self-hosted-dashboard-product-change",
                    mutation_class="source-write",
                    environment="local",
                    data_classification="internal",
                    acceptance_requirements=[
                        "persisted task-store card",
                        "correlated shell outputs",
                        "single commit and push",
                        "backend and Flutter tests",
                    ],
                ),
            )
        return task

    def _remote_head(self) -> str | None:
        value = self._git("ls-remote", "origin", f"refs/heads/{self._branch}")
        return value.split(maxsplit=1)[0] if value else None

    @staticmethod
    def _proof_prompt(expected_head: str) -> str:
        return f"""
Execute only task {SELF_HOSTED_PROOF_TASK_ID} in the current repository.
Authority HEAD is {expected_head}. Do not inspect any external project.

Add a real Arabic RTL Dashboard card titled "آخر تنفيذ ذاتي". Its values must
come only from the persisted Operator task store and must include task_id,
final status, abbreviated before/after HEAD, safe abbreviated execution receipt
and thread/session reference, completion time, verification state, navigation
to /tasks, and a safe evidence route. Before a completed self-hosted execution
exists, render a truthful empty state. Do not add fixtures or constants that
pretend an execution completed.

Add focused deterministic backend and Flutter tests. Run ruff format/check,
mypy, pytest, dart format, flutter analyze, and flutter test as applicable.
Do not access secrets, environment values, Supabase, databases, deployments,
production, or external repositories. Commit exactly once with:
feat: add persisted last self-hosted execution card
Push only agent/workspace-manager-foundation-v1 to origin. Do not merge.
Wait for every shell command output and return the required structured result.
""".strip()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self._workspace), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise GovernanceError(f"git {' '.join(args)} failed: {detail}")
        return result.stdout.strip()

    @staticmethod
    def _nested_text(value: dict[str, Any], outer: str, inner: str) -> str | None:
        nested = value.get(outer)
        if isinstance(nested, dict):
            result = nested.get(inner)
            return str(result) if result else None
        return None

    @staticmethod
    def _safe_https(value: object) -> str | None:
        text = str(value) if value else ""
        return text if text.startswith("https://") else None

    @staticmethod
    def _module_state(module: str) -> CapabilityState:
        try:
            __import__(module)
        except ImportError:
            return CapabilityState(status="BLOCKED", blocker=f"{module.upper()}_NOT_INSTALLED")
        return CapabilityState(status="AVAILABLE")
