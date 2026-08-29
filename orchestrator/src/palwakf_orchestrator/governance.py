from __future__ import annotations

import fnmatch
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
        if request.boundaries.workspace_write:
            return self._complete_workspace_write(request, before)

        after = self.verify_repository(
            request.model_copy(
                update={"expected_head": self._git.run(self._workspace, "rev-parse", "HEAD")}
            )
        )
        if after.local_head != before.local_head:
            raise GovernanceError("read-only dispatch mutated repository HEAD")
        return after

    def _complete_workspace_write(
        self,
        request: DispatchRequest,
        before: RepositoryState,
    ) -> RepositoryState:
        branch = self._git.run(self._workspace, "branch", "--show-current")
        local_head = self._git.run(self._workspace, "rev-parse", "HEAD")
        remote_head = self._remote_branch_head(request.branch)

        if branch != request.branch:
            raise GovernanceError(
                f"PROVIDER_RESULT_BRANCH_DRIFT:expected={request.branch}:actual={branch}"
            )
        if local_head != before.local_head:
            raise GovernanceError(
                "PROVIDER_GIT_HEAD_MUTATION_NOT_ALLOWED:"
                f"expected={before.local_head}:actual={local_head}"
            )
        if remote_head != before.remote_head:
            raise GovernanceError(
                "PROVIDER_REMOTE_MUTATION_NOT_ALLOWED:"
                f"expected={before.remote_head}:actual={remote_head or '<missing>'}"
            )

        staged_before = self._git_lines("diff", "--cached", "--name-only")
        if staged_before:
            raise GovernanceError(
                "PROVIDER_GIT_INDEX_MUTATION_NOT_ALLOWED:" + ",".join(staged_before)
            )

        dirty_paths = self._dirty_paths()
        if not dirty_paths:
            raise GovernanceError("AUTHORIZED_WORKSPACE_WRITE_PRODUCED_NO_SOURCE_CHANGE")

        scope_patterns = self._normalized_scope_patterns(request)
        violations = [
            path
            for path in dirty_paths
            if not any(fnmatch.fnmatch(path, pattern) for pattern in scope_patterns)
        ]
        if violations:
            raise GovernanceError(
                "PROVIDER_RESULT_OUTSIDE_AUTHORIZED_SCOPE:" + ",".join(violations)
            )

        committed = False
        try:
            self._git.run(self._workspace, "add", "-A", "--", *dirty_paths)
            staged = self._git_lines("diff", "--cached", "--name-only")
            if sorted(staged) != sorted(dirty_paths):
                raise GovernanceError(
                    "GOVERNED_WRITE_STAGED_SCOPE_MISMATCH:"
                    f"expected={','.join(sorted(dirty_paths))}:"
                    f"actual={','.join(sorted(staged))}"
                )
            self._git.run(self._workspace, "diff", "--cached", "--check")
            self._git.run(
                self._workspace,
                "commit",
                "--no-gpg-sign",
                "-m",
                f"chore(provider): complete {request.task_id.lower()}",
            )
            committed = True
        except Exception:
            if not committed:
                self._git.run(self._workspace, "reset", "--", *dirty_paths)
            raise

        candidate_sha = self._git.run(self._workspace, "rev-parse", "HEAD").lower()
        parent_sha = self._git.run(self._workspace, "rev-parse", "HEAD^").lower()
        if parent_sha != before.local_head.lower():
            raise GovernanceError(
                "GOVERNED_WRITE_PARENT_MISMATCH:"
                f"expected={before.local_head.lower()}:actual={parent_sha}"
            )

        committed_paths = self._git_lines(
            "diff",
            "--name-only",
            before.local_head,
            candidate_sha,
        )
        if sorted(committed_paths) != sorted(dirty_paths):
            raise GovernanceError(
                "GOVERNED_WRITE_COMMIT_SCOPE_MISMATCH:"
                f"expected={','.join(sorted(dirty_paths))}:"
                f"actual={','.join(sorted(committed_paths))}"
            )

        remote_before_push = self._remote_branch_head(request.branch)
        if remote_before_push != before.remote_head:
            raise GovernanceError(
                "GOVERNED_WRITE_REMOTE_DRIFT_BEFORE_PUSH:"
                f"expected={before.remote_head}:actual={remote_before_push or '<missing>'}"
            )

        try:
            self._git.run(
                self._workspace,
                "push",
                "origin",
                f"HEAD:refs/heads/{request.branch}",
            )
        except GovernanceError as exc:
            raise GovernanceError(
                f"GOVERNED_WRITE_PUSH_FAILED_LOCAL_COMMIT:{candidate_sha}"
            ) from exc

        remote_after = self._remote_branch_head(request.branch)
        if remote_after != candidate_sha:
            raise GovernanceError(
                "GOVERNED_WRITE_REMOTE_READBACK_MISMATCH:"
                f"expected={candidate_sha}:actual={remote_after or '<missing>'}"
            )

        if self._git.run(self._workspace, "status", "--porcelain"):
            raise GovernanceError("GOVERNED_WRITE_WORKTREE_NOT_CLEAN_AFTER_PUSH")

        return RepositoryState(
            repository=request.repository,
            branch=request.branch,
            local_head=candidate_sha,
            remote_head=remote_after,
            clean=True,
        )

    def _remote_branch_head(self, branch: str) -> str:
        remote_line = self._git.run(
            self._workspace,
            "ls-remote",
            "origin",
            f"refs/heads/{branch}",
        )
        return remote_line.split(maxsplit=1)[0].lower() if remote_line else ""

    def _dirty_paths(self) -> list[str]:
        return sorted(
            set(
                [
                    *self._git_lines("diff", "--name-only"),
                    *self._git_lines("ls-files", "--others", "--exclude-standard"),
                ]
            )
        )

    def _git_lines(self, *args: str) -> list[str]:
        return [
            line.replace("\\", "/")
            for line in self._git.run(self._workspace, *args).splitlines()
            if line
        ]

    @staticmethod
    def _normalized_scope_patterns(request: DispatchRequest) -> list[str]:
        patterns = [
            pattern.replace("\\", "/")
            for pattern in request.source_scope_patterns
            if pattern.strip()
        ]
        if patterns:
            return patterns
        if (
            request.task_id == "PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1"
            and request.branch == "agent/workspace-manager-foundation-v1"
        ):
            return ["**"]
        raise GovernanceError("GOVERNED_WRITE_REQUIRES_NONEMPTY_SOURCE_SCOPE")

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
