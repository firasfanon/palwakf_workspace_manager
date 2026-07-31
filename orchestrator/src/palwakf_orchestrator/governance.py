from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from palwakf_orchestrator.contracts import (
    DispatchPlan,
    DispatchRequest,
    RepositoryState,
)
from palwakf_orchestrator.errors import GovernanceError


class GitRunner(Protocol):
    def run(self, workspace: Path, *args: str) -> str: ...


class SubprocessGitRunner:
    def run(self, workspace: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(workspace), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise GovernanceError(f"git {' '.join(args)} failed: {detail}")
        return completed.stdout.strip()


class GovernanceGate:
    def __init__(self, workspace: Path, git: GitRunner | None = None) -> None:
        self._workspace = workspace.resolve()
        self._git = git or SubprocessGitRunner()

    def verify_repository(self, request: DispatchRequest) -> RepositoryState:
        if not self._workspace.is_dir():
            raise GovernanceError(f"workspace does not exist: {self._workspace}")

        branch = self._git.run(self._workspace, "branch", "--show-current")
        local_head = self._git.run(self._workspace, "rev-parse", "HEAD")
        status = self._git.run(self._workspace, "status", "--porcelain")
        remote_line = self._git.run(
            self._workspace,
            "ls-remote",
            "origin",
            f"refs/heads/{request.branch}",
        )
        remote_head = remote_line.split(maxsplit=1)[0] if remote_line else ""

        if branch != request.branch:
            raise GovernanceError(
                f"branch mismatch: expected {request.branch}, got {branch or '<detached>'}"
            )
        if not local_head.startswith(request.expected_head.lower()):
            raise GovernanceError(
                f"local HEAD drift: expected prefix {request.expected_head}, got {local_head}"
            )
        if remote_head != local_head:
            raise GovernanceError(
                f"remote HEAD drift: local {local_head}, remote {remote_head or '<missing>'}"
            )
        if status:
            raise GovernanceError("worktree is not clean")

        return RepositoryState(
            repository=request.repository,
            branch=branch,
            local_head=local_head,
            remote_head=remote_head,
            clean=True,
        )

    def verify_result_repository(
        self,
        request: DispatchRequest,
        before: RepositoryState,
    ) -> RepositoryState:
        after = self.verify_repository(
            request.model_copy(
                update={"expected_head": self._git.run(self._workspace, "rev-parse", "HEAD")}
            )
        )
        if request.boundaries.workspace_write:
            if after.local_head == before.local_head:
                raise GovernanceError("authorized workspace-write produced no commit")
        elif after.local_head != before.local_head:
            raise GovernanceError("read-only dispatch mutated repository HEAD")
        return after

    @staticmethod
    def verify_plan(
        plan: DispatchPlan,
        request: DispatchRequest | None = None,
    ) -> None:
        if request is None:
            if plan.requires_workspace_write:
                raise GovernanceError("dispatch plan requested forbidden workspace mutation")
            return
        if plan.requires_workspace_write != request.boundaries.workspace_write:
            raise GovernanceError("dispatch plan mutation class does not match task authority")
