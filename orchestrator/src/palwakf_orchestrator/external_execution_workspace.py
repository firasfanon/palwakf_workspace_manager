from __future__ import annotations

import fnmatch
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from palwakf_orchestrator.engineering_os_contracts import (
    EngineeringTaskRecord,
    RemoteCheckpointRequest,
)
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.external_execution_contracts import (
    ApplyExternalWorkspaceRequest,
    CheckpointExternalWorkspaceRequest,
    ExternalExecutionWorkspaceStatus,
    ExternalValidationCheck,
    ExternalValidationCommandResult,
    ExternalValidationResult,
    ExternalWorkspaceLifecycle,
    PrepareExternalWorkspaceRequest,
    ValidateExternalWorkspaceRequest,
)
from palwakf_orchestrator.file_apply_contracts import GovernedFileApplyRequest
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord, OperatorTaskStatus
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.transactional_file_apply import GovernedTransactionalFileApply

EXTERNAL_EXECUTION_WORKSPACES_KEY = "external_execution_workspaces_v1"
WORKSPACE_MANAGER_REPOSITORY = "firasfanon/palwakf_workspace_manager"
_REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})/[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})$"
)

RemoteUrlResolver = Callable[[str], str]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ExternalExecutionWorkspaceService:
    """Governed execution workspaces for repositories outside Workspace Manager."""

    def __init__(
        self,
        engineering_tasks: EngineeringOsService,
        execution_runs: ExecutionRunAdapter,
        operator_tasks: OperatorService,
        state_store: StateStore,
        *,
        workspace_root: Path,
        execution_host_id: str,
        remote_url_resolver: RemoteUrlResolver | None = None,
        git_executable: str = "git",
    ) -> None:
        self.engineering_tasks = engineering_tasks
        self.execution_runs = execution_runs
        self.operator_tasks = operator_tasks
        self.state_store = state_store
        self.workspace_root = (
            workspace_root.resolve() / ".palwakf" / "external_execution_workspaces"
        )
        self.execution_host_id = execution_host_id
        self.remote_url_resolver = remote_url_resolver or self._github_remote_url
        self.git_executable = git_executable

    def status(self, execution_run_id: str) -> ExternalExecutionWorkspaceStatus:
        parent, operator = self._authority(
            execution_run_id,
            require_authorized=False,
            allow_completed=True,
        )
        stored = self._load_status(execution_run_id)
        if stored is None:
            return self._base_status(execution_run_id, parent, operator)

        workspace = self._workspace_path(execution_run_id)
        updates: dict[str, object] = {
            "authorized": operator.authorized_at is not None,
            "updated_at": _utc_now(),
        }
        if workspace.is_dir() and (workspace / ".git").is_dir():
            try:
                updates["workspace_path"] = str(workspace)
                updates["prepared"] = True
                updates["current_head"] = self._git_scalar(workspace, "rev-parse", "HEAD").lower()
                if stored.lifecycle != ExternalWorkspaceLifecycle.checkpointed:
                    updates["changed_files"] = self._dirty_paths(workspace)
            except GovernanceError:
                pass
        updated = stored.model_copy(update=updates)
        self._save_status(updated)
        return updated

    def prepare(
        self,
        execution_run_id: str,
        request: PrepareExternalWorkspaceRequest,
    ) -> ExternalExecutionWorkspaceStatus:
        parent, operator = self._authority(execution_run_id, require_authorized=True)
        workspace = self._workspace_path(execution_run_id)
        expected = operator.expected_head.lower()
        remote_head: str | None = None

        if request.recreate and workspace.exists():
            self._remove_workspace(workspace)

        if workspace.exists():
            self._assert_existing_workspace(workspace, operator)
            dirty = self._dirty_paths(workspace)
            if dirty:
                raise GovernanceError("EXTERNAL_WORKSPACE_DIRTY_RECREATE_REQUIRED")
            status = self._base_status(execution_run_id, parent, operator).model_copy(
                update={
                    "workspace_path": str(workspace),
                    "lifecycle": ExternalWorkspaceLifecycle.ready,
                    "prepared": True,
                    "authorized": True,
                    "current_head": self._git_scalar(workspace, "rev-parse", "HEAD").lower(),
                    "remote_head": self._remote_branch_head(workspace, operator.branch),
                    "changed_files": [],
                    "last_error": None,
                    "updated_at": _utc_now(),
                }
            )
            self._save_status(status)
            return status

        workspace.parent.mkdir(parents=True, exist_ok=True)
        remote_url = self.remote_url_resolver(parent.repository)
        try:
            self._run(
                [
                    self.git_executable,
                    "clone",
                    "--no-checkout",
                    "--origin",
                    "origin",
                    remote_url,
                    str(workspace),
                ],
                timeout_seconds=max(120, min(operator.timeout_seconds, 900)),
            )
            self._assert_origin(workspace, remote_url)
            self._git(workspace, "cat-file", "-e", f"{expected}^{{commit}}")
            remote_head = self._remote_branch_head(workspace, operator.branch)
            if remote_head is not None and remote_head.lower() != expected:
                raise GovernanceError(
                    "EXTERNAL_REMOTE_TASK_BRANCH_DRIFT:"
                    f"expected={expected} actual={remote_head.lower()}"
                )
            self._git(workspace, "checkout", "-B", operator.branch, expected)
            self._assert_workspace_binding(workspace, operator, allow_dirty=False)
        except Exception as exc:
            if workspace.exists():
                self._remove_workspace(workspace)
            self._save_blocked(execution_run_id, parent, operator, workspace, exc)
            if isinstance(exc, GovernanceError):
                raise
            raise GovernanceError(f"EXTERNAL_WORKSPACE_PREPARE_FAILED:{exc}") from exc

        status = self._base_status(execution_run_id, parent, operator).model_copy(
            update={
                "workspace_path": str(workspace),
                "lifecycle": ExternalWorkspaceLifecycle.ready,
                "prepared": True,
                "authorized": True,
                "current_head": expected,
                "remote_head": remote_head.lower() if remote_head else None,
                "changed_files": [],
                "validation": None,
                "checkpoint_sha": None,
                "last_error": None,
                "updated_at": _utc_now(),
            }
        )
        self._save_status(status)
        return status

    def apply(
        self,
        execution_run_id: str,
        request: ApplyExternalWorkspaceRequest,
    ) -> ExternalExecutionWorkspaceStatus:
        parent, operator = self._authority(execution_run_id, require_authorized=True)
        self._require_source_write(parent, operator)
        workspace = self._require_prepared_workspace(execution_run_id, operator)
        current_dirty = self._dirty_paths(workspace)
        requested_paths = sorted({self._normalize_path(item.path) for item in request.files})
        missing_dirty = sorted(set(current_dirty) - set(requested_paths))
        if missing_dirty:
            raise GovernanceError(
                "EXTERNAL_APPLY_MANIFEST_MUST_INCLUDE_CURRENT_DIRTY_PATHS:"
                + ",".join(missing_dirty)
            )
        self._assert_scope(operator, requested_paths)
        self._assert_workspace_binding(workspace, operator, allow_dirty=True)

        engine = GovernedTransactionalFileApply(
            workspace,
            self.state_store,
            execution_host_id=self.execution_host_id,
        )
        engine.apply(
            GovernedFileApplyRequest(
                task_id=operator.task_id,
                repository=operator.repository,
                expected_branch=operator.branch,
                expected_head=operator.expected_head,
                files=request.files,
            )
        )
        changed = self._dirty_paths(workspace)
        self._assert_scope(operator, changed)
        status = self._base_status(execution_run_id, parent, operator).model_copy(
            update={
                "workspace_path": str(workspace),
                "lifecycle": ExternalWorkspaceLifecycle.dirty,
                "prepared": True,
                "authorized": True,
                "current_head": self._git_scalar(workspace, "rev-parse", "HEAD").lower(),
                "remote_head": self._remote_branch_head(workspace, operator.branch),
                "changed_files": changed,
                "validation": None,
                "checkpoint_sha": None,
                "last_error": None,
                "updated_at": _utc_now(),
            }
        )
        self._save_status(status)
        return status

    def validate(
        self,
        execution_run_id: str,
        request: ValidateExternalWorkspaceRequest,
    ) -> ExternalExecutionWorkspaceStatus:
        parent, operator = self._authority(execution_run_id, require_authorized=True)
        workspace = self._require_prepared_workspace(execution_run_id, operator)
        self._assert_workspace_binding(workspace, operator, allow_dirty=True)
        changed = self._dirty_paths(workspace)
        self._assert_scope(operator, changed)
        checks = list(dict.fromkeys(list(request.checks) or self._default_checks(workspace)))

        before_snapshot = self._dirty_snapshot(workspace)
        started = _utc_now()
        results: list[ExternalValidationCommandResult] = []
        for check in checks:
            result = self._run_validation_check(
                workspace,
                check,
                timeout_seconds=max(60, min(operator.timeout_seconds, 3600)),
            )
            results.append(result)
            if result.status == "FAIL":
                break

        mutation_guard_error = self._restore_validation_side_effects(
            workspace,
            before_snapshot,
        )
        if mutation_guard_error is not None:
            results.append(
                ExternalValidationCommandResult(
                    check=ExternalValidationCheck.git_diff_check,
                    command_summary="VALIDATION_SOURCE_MUTATION_GUARD",
                    status="FAIL",
                    exit_code=None,
                    duration_ms=0,
                    output_excerpt=mutation_guard_error,
                )
            )

        changed_after = self._dirty_paths(workspace)
        self._assert_scope(operator, changed_after)
        completed = _utc_now()
        all_passed = bool(results) and all(item.status == "PASS" for item in results)
        validation = ExternalValidationResult(
            checks=results,
            all_passed=all_passed,
            validated_paths=changed_after,
            started_at=started,
            completed_at=completed,
        )
        status = self._base_status(execution_run_id, parent, operator).model_copy(
            update={
                "workspace_path": str(workspace),
                "lifecycle": (
                    ExternalWorkspaceLifecycle.validated
                    if all_passed
                    else ExternalWorkspaceLifecycle.blocked
                ),
                "prepared": True,
                "authorized": True,
                "current_head": self._git_scalar(workspace, "rev-parse", "HEAD").lower(),
                "remote_head": self._remote_branch_head(workspace, operator.branch),
                "changed_files": changed_after,
                "validation": validation,
                "checkpoint_sha": None,
                "last_error": None if all_passed else "EXTERNAL_VALIDATION_FAILED",
                "updated_at": _utc_now(),
            }
        )
        self._save_status(status)
        return status

    def checkpoint(
        self,
        execution_run_id: str,
        request: CheckpointExternalWorkspaceRequest,
    ) -> ExternalExecutionWorkspaceStatus:
        parent, operator = self._authority(
            execution_run_id,
            require_authorized=True,
            allow_completed=True,
        )
        self._require_source_write(parent, operator)
        workspace = self._require_prepared_workspace(execution_run_id, operator)
        stored = self._load_status(execution_run_id)
        if stored is None or stored.validation is None or not stored.validation.all_passed:
            raise GovernanceError("EXTERNAL_CHECKPOINT_REQUIRES_SUCCESSFUL_VALIDATION")
        if (
            stored.lifecycle == ExternalWorkspaceLifecycle.checkpointed
            and stored.checkpoint_sha is not None
        ):
            current = self._git_scalar(workspace, "rev-parse", "HEAD").lower()
            remote = self._remote_branch_head(workspace, operator.branch)
            if current == stored.checkpoint_sha and remote == stored.checkpoint_sha:
                return self.status(execution_run_id)

        expected = operator.expected_head.lower()
        current_head = self._git_scalar(workspace, "rev-parse", "HEAD").lower()
        dirty = self._dirty_paths(workspace)

        if current_head == expected:
            if sorted(dirty) != sorted(stored.validation.validated_paths):
                raise GovernanceError("EXTERNAL_WORKSPACE_CHANGED_AFTER_VALIDATION")
            if not dirty:
                raise GovernanceError("EXTERNAL_CHECKPOINT_REQUIRES_SOURCE_CHANGE")
            self._assert_scope(operator, dirty)
        else:
            if dirty:
                raise GovernanceError("EXTERNAL_CHECKPOINT_LOCAL_HEAD_AND_DIRTY_DRIFT")
            parent_sha = self._git_scalar(workspace, "rev-parse", "HEAD^").lower()
            committed = self._changed_files(workspace, expected, current_head)
            if parent_sha != expected or sorted(committed) != sorted(
                stored.validation.validated_paths
            ):
                raise GovernanceError("EXTERNAL_CHECKPOINT_LOCAL_COMMIT_DRIFT")

        if not self.state_store.acquire_repository_writer(
            operator.repository,
            operator.task_id,
            self.execution_host_id,
        ):
            raise GovernanceError(f"REPOSITORY_WRITER_BUSY:{operator.repository}")

        try:
            remote_before = self._remote_branch_head(workspace, operator.branch)
            if current_head == expected:
                if remote_before is not None and remote_before.lower() != expected:
                    raise GovernanceError(
                        "EXTERNAL_REMOTE_TASK_BRANCH_DRIFT:"
                        f"expected={expected} actual={remote_before.lower()}"
                    )
                self._git(workspace, "add", "--", *dirty)
                staged = self._git_lines(workspace, "diff", "--cached", "--name-only")
                if sorted(staged) != sorted(dirty):
                    raise GovernanceError("EXTERNAL_CHECKPOINT_STAGED_SCOPE_MISMATCH")
                self._git(workspace, "diff", "--cached", "--check")
                self._git(
                    workspace,
                    "commit",
                    "--no-gpg-sign",
                    "-m",
                    request.commit_message,
                )
                candidate_sha = self._git_scalar(workspace, "rev-parse", "HEAD").lower()
                commit_parent = self._git_scalar(workspace, "rev-parse", "HEAD^").lower()
                if commit_parent != expected:
                    raise GovernanceError("EXTERNAL_CHECKPOINT_PARENT_MISMATCH")
                committed = self._changed_files(workspace, expected, candidate_sha)
                if sorted(committed) != sorted(dirty):
                    raise GovernanceError("EXTERNAL_CHECKPOINT_COMMIT_SCOPE_MISMATCH")
            else:
                candidate_sha = current_head
                committed = self._changed_files(workspace, expected, candidate_sha)
                if remote_before is not None and remote_before.lower() not in {
                    expected,
                    candidate_sha,
                }:
                    raise GovernanceError(
                        "EXTERNAL_REMOTE_TASK_BRANCH_DRIFT:"
                        f"expected={expected}|{candidate_sha} actual={remote_before.lower()}"
                    )

            if remote_before is None or remote_before.lower() != candidate_sha:
                self._git(
                    workspace,
                    "push",
                    "origin",
                    f"HEAD:refs/heads/{operator.branch}",
                    timeout_seconds=max(120, min(operator.timeout_seconds, 900)),
                )
            remote_after = self._remote_branch_head(workspace, operator.branch)
            if remote_after is None or remote_after.lower() != candidate_sha:
                raise GovernanceError(
                    "EXTERNAL_CHECKPOINT_REMOTE_READBACK_MISMATCH:"
                    f"expected={candidate_sha} actual={remote_after or '<missing>'}"
                )

            validation_summaries = [
                f"{item.check.value}:{item.status}" for item in stored.validation.checks
            ]
            evidence = [
                f"external-workspace:{execution_run_id}",
                f"remote-sha:{candidate_sha}",
                "non-force-push:PASS",
                "remote-readback:PASS",
                *request.evidence,
            ]
            receipt = f"external-workspace:{execution_run_id}:{candidate_sha}"
            self.operator_tasks.record_external_execution_result(
                operator.task_id,
                before_head=expected,
                after_head=candidate_sha,
                changed_files=committed,
                tests=validation_summaries,
                evidence=evidence,
                execution_receipt=receipt,
            )
            self.engineering_tasks.checkpoint_task(
                parent.task_id,
                RemoteCheckpointRequest(remote_sha=candidate_sha, evidence=evidence),
            )
            if self._dirty_paths(workspace):
                raise GovernanceError("EXTERNAL_CHECKPOINT_WORKTREE_NOT_CLEAN")

            status = self._base_status(execution_run_id, parent, operator).model_copy(
                update={
                    "workspace_path": str(workspace),
                    "lifecycle": ExternalWorkspaceLifecycle.checkpointed,
                    "prepared": True,
                    "authorized": True,
                    "current_head": candidate_sha,
                    "remote_head": candidate_sha,
                    "changed_files": committed,
                    "validation": stored.validation,
                    "checkpoint_sha": candidate_sha,
                    "last_error": None,
                    "updated_at": _utc_now(),
                }
            )
            self._save_status(status)
            return status
        except Exception as exc:
            self._save_blocked(execution_run_id, parent, operator, workspace, exc)
            if isinstance(exc, GovernanceError):
                raise
            raise GovernanceError(f"EXTERNAL_CHECKPOINT_FAILED:{exc}") from exc
        finally:
            self.state_store.release_repository_writer(operator.repository, operator.task_id)

    def _authority(
        self,
        execution_run_id: str,
        *,
        require_authorized: bool,
        allow_completed: bool = False,
    ) -> tuple[EngineeringTaskRecord, OperatorTaskRecord]:
        view = self.execution_runs.get_operational_view(execution_run_id)
        parent = view.parent_task
        operator = view.operator_task
        if parent.repository == WORKSPACE_MANAGER_REPOSITORY:
            raise GovernanceError("EXTERNAL_EXECUTION_REQUIRES_EXTERNAL_REPOSITORY")
        if not _REPOSITORY_PATTERN.fullmatch(parent.repository):
            raise GovernanceError("EXTERNAL_EXECUTION_REPOSITORY_IDENTITY_INVALID")
        if operator.repository != parent.repository or operator.branch != parent.task_branch:
            raise GovernanceError("EXTERNAL_EXECUTION_AUTHORITY_DRIFT")
        if require_authorized and operator.authorized_at is None:
            raise GovernanceError("EXTERNAL_EXECUTION_REQUIRES_EXPLICIT_AUTHORIZATION")
        authority_head = (parent.latest_remote_task_sha or parent.base_sha).lower()
        if authority_head != operator.expected_head.lower():
            completed = (
                allow_completed
                and operator.after_head is not None
                and operator.after_head.lower() == authority_head
                and operator.status
                in {OperatorTaskStatus.pending_verification, OperatorTaskStatus.verified}
            )
            if not completed:
                raise GovernanceError(
                    "EXTERNAL_EXECUTION_RUN_AUTHORITY_STALE:"
                    f"run={operator.expected_head.lower()} parent={authority_head}"
                )
        return parent, operator

    @staticmethod
    def _require_source_write(
        parent: EngineeringTaskRecord,
        operator: OperatorTaskRecord,
    ) -> None:
        if parent.mutation_class != "source-write" or operator.sandbox != "workspace-write":
            raise GovernanceError("EXTERNAL_EXECUTION_SOURCE_WRITE_NOT_AUTHORIZED")

    def _require_prepared_workspace(
        self,
        execution_run_id: str,
        operator: OperatorTaskRecord,
    ) -> Path:
        workspace = self._workspace_path(execution_run_id)
        if not workspace.is_dir() or not (workspace / ".git").is_dir():
            raise GovernanceError("EXTERNAL_WORKSPACE_NOT_PREPARED")
        self._assert_existing_workspace(workspace, operator)
        return workspace

    def _assert_existing_workspace(
        self,
        workspace: Path,
        operator: OperatorTaskRecord,
    ) -> None:
        self._assert_origin(workspace, self.remote_url_resolver(operator.repository))
        branch = self._git_scalar(workspace, "branch", "--show-current")
        if branch != operator.branch:
            raise GovernanceError(
                f"EXTERNAL_WORKSPACE_BRANCH_DRIFT:expected={operator.branch} actual={branch}"
            )
        head = self._git_scalar(workspace, "rev-parse", "HEAD").lower()
        expected = operator.expected_head.lower()
        if head != expected:
            try:
                parent = self._git_scalar(workspace, "rev-parse", "HEAD^").lower()
            except GovernanceError:
                parent = ""
            if parent != expected:
                raise GovernanceError(
                    f"EXTERNAL_WORKSPACE_HEAD_DRIFT:expected={expected} actual={head}"
                )

    def _assert_workspace_binding(
        self,
        workspace: Path,
        operator: OperatorTaskRecord,
        *,
        allow_dirty: bool,
    ) -> None:
        self._assert_existing_workspace(workspace, operator)
        if not allow_dirty and self._dirty_paths(workspace):
            raise GovernanceError("EXTERNAL_WORKSPACE_NOT_CLEAN")

    def _assert_scope(
        self,
        operator: OperatorTaskRecord,
        paths: Sequence[str],
    ) -> None:
        patterns = [value.replace("\\", "/") for value in operator.scope_patterns]
        if not patterns:
            if paths:
                raise GovernanceError("EXTERNAL_EXECUTION_REQUIRES_EXPLICIT_SOURCE_SCOPE")
            return
        violations: list[str] = []
        for path in paths:
            normalized = self._normalize_path(path)
            if not any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns):
                violations.append(normalized)
        if violations:
            raise GovernanceError(
                "EXECUTION_RESULT_OUTSIDE_AUTHORIZED_SCOPE:" + ",".join(sorted(violations))
            )

    def _default_checks(self, workspace: Path) -> list[ExternalValidationCheck]:
        checks = [ExternalValidationCheck.git_diff_check]
        if (workspace / "pubspec.yaml").is_file():
            checks.extend(
                [
                    ExternalValidationCheck.flutter_pub_get,
                    ExternalValidationCheck.flutter_analyze,
                    ExternalValidationCheck.flutter_test,
                    ExternalValidationCheck.flutter_build_web,
                ]
            )
        if (workspace / "pyproject.toml").is_file():
            checks.extend(
                [
                    ExternalValidationCheck.ruff,
                    ExternalValidationCheck.mypy,
                    ExternalValidationCheck.pytest,
                ]
            )
        return checks

    def _run_validation_check(
        self,
        workspace: Path,
        check: ExternalValidationCheck,
        *,
        timeout_seconds: int,
    ) -> ExternalValidationCommandResult:
        command = self._validation_command(workspace, check)
        if command is None:
            return ExternalValidationCommandResult(
                check=check,
                command_summary=check.value,
                status="FAIL",
                exit_code=None,
                duration_ms=0,
                output_excerpt=f"VALIDATION_TOOL_NOT_FOUND:{check.value}",
            )
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            output = "\n".join(
                value for value in (result.stdout.strip(), result.stderr.strip()) if value
            )
            return ExternalValidationCommandResult(
                check=check,
                command_summary=" ".join(command),
                status="PASS" if result.returncode == 0 else "FAIL",
                exit_code=result.returncode,
                duration_ms=duration_ms,
                output_excerpt=output[-6000:],
            )
        except subprocess.TimeoutExpired as exc:
            return ExternalValidationCommandResult(
                check=check,
                command_summary=" ".join(command),
                status="FAIL",
                exit_code=None,
                duration_ms=int((time.monotonic() - started) * 1000),
                output_excerpt=f"VALIDATION_COMMAND_TIMEOUT:{exc.timeout}",
            )
        except OSError as exc:
            return ExternalValidationCommandResult(
                check=check,
                command_summary=" ".join(command),
                status="FAIL",
                exit_code=None,
                duration_ms=int((time.monotonic() - started) * 1000),
                output_excerpt=f"VALIDATION_COMMAND_START_FAILED:{exc}",
            )

    def _validation_command(
        self,
        workspace: Path,
        check: ExternalValidationCheck,
    ) -> list[str] | None:
        if check == ExternalValidationCheck.git_diff_check:
            return [self.git_executable, "diff", "--check"]
        if check in {
            ExternalValidationCheck.flutter_pub_get,
            ExternalValidationCheck.flutter_analyze,
            ExternalValidationCheck.flutter_test,
            ExternalValidationCheck.flutter_build_web,
        }:
            flutter = shutil.which("flutter.bat") or shutil.which("flutter")
            if flutter is None:
                return None
            if check == ExternalValidationCheck.flutter_pub_get:
                return [flutter, "pub", "get"]
            if check == ExternalValidationCheck.flutter_analyze:
                return [flutter, "analyze", "--no-pub"]
            if check == ExternalValidationCheck.flutter_test:
                return [flutter, "test", "--no-pub"]
            return [flutter, "build", "web", "--release", "--no-pub"]

        python = self._python_for(workspace)
        if check == ExternalValidationCheck.ruff:
            return [python, "-m", "ruff", "check", "."]
        if check == ExternalValidationCheck.mypy:
            return [python, "-m", "mypy", "."]
        if check == ExternalValidationCheck.pytest:
            return [python, "-m", "pytest"]
        return None

    @staticmethod
    def _python_for(workspace: Path) -> str:
        candidates = [
            workspace / ".venv" / "Scripts" / "python.exe",
            workspace / ".venv" / "bin" / "python",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return sys.executable

    def _dirty_snapshot(self, workspace: Path) -> dict[str, bytes | None]:
        snapshot: dict[str, bytes | None] = {}
        for path in self._dirty_paths(workspace):
            target = self._resolve_workspace_path(workspace, path)
            snapshot[path] = target.read_bytes() if target.is_file() else None
        return snapshot

    def _restore_validation_side_effects(
        self,
        workspace: Path,
        before: dict[str, bytes | None],
    ) -> str | None:
        try:
            after = set(self._dirty_paths(workspace))
            before_paths = set(before)
            for path, payload in before.items():
                target = self._resolve_workspace_path(workspace, path)
                if payload is None:
                    if target.exists():
                        self._remove_target(target)
                elif not target.is_file() or target.read_bytes() != payload:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)

            for path in sorted(after - before_paths):
                target = self._resolve_workspace_path(workspace, path)
                tracked = self._run(
                    [
                        self.git_executable,
                        "-C",
                        str(workspace),
                        "ls-files",
                        "--error-unmatch",
                        "--",
                        path,
                    ],
                    timeout_seconds=30,
                    allow_failure=True,
                )
                if tracked.returncode == 0:
                    self._git(workspace, "restore", "--", path)
                elif target.exists():
                    self._remove_target(target)

            final_paths = set(self._dirty_paths(workspace))
            if final_paths != before_paths:
                return (
                    "VALIDATION_SOURCE_MUTATION_RESTORE_MISMATCH:"
                    f"before={sorted(before_paths)} after={sorted(final_paths)}"
                )
            for path, payload in before.items():
                target = self._resolve_workspace_path(workspace, path)
                if payload is None:
                    if target.exists():
                        return f"VALIDATION_SOURCE_MUTATION_RESTORE_FAILED:{path}"
                elif not target.is_file() or target.read_bytes() != payload:
                    return f"VALIDATION_SOURCE_MUTATION_RESTORE_FAILED:{path}"
            return None
        except Exception as exc:
            return f"VALIDATION_SOURCE_MUTATION_GUARD_FAILED:{exc}"

    @staticmethod
    def _remove_target(target: Path) -> None:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    def _base_status(
        self,
        execution_run_id: str,
        parent: EngineeringTaskRecord,
        operator: OperatorTaskRecord,
    ) -> ExternalExecutionWorkspaceStatus:
        return ExternalExecutionWorkspaceStatus(
            execution_run_id=execution_run_id,
            parent_engineering_task_id=parent.task_id,
            project_id=parent.project_id,
            repository=operator.repository,
            task_branch=operator.branch,
            expected_head=operator.expected_head.lower(),
            authorized=operator.authorized_at is not None,
            updated_at=_utc_now(),
        )

    def _save_blocked(
        self,
        execution_run_id: str,
        parent: EngineeringTaskRecord,
        operator: OperatorTaskRecord,
        workspace: Path,
        exc: Exception,
    ) -> None:
        current_head: str | None = None
        changed: list[str] = []
        if workspace.is_dir() and (workspace / ".git").is_dir():
            try:
                current_head = self._git_scalar(workspace, "rev-parse", "HEAD").lower()
                changed = self._dirty_paths(workspace)
            except GovernanceError:
                pass
        previous = self._load_status(execution_run_id)
        status = self._base_status(execution_run_id, parent, operator).model_copy(
            update={
                "workspace_path": str(workspace) if workspace.exists() else None,
                "lifecycle": ExternalWorkspaceLifecycle.blocked,
                "prepared": workspace.is_dir() and (workspace / ".git").is_dir(),
                "current_head": current_head,
                "remote_head": previous.remote_head if previous else None,
                "changed_files": changed,
                "validation": previous.validation if previous else None,
                "checkpoint_sha": previous.checkpoint_sha if previous else None,
                "last_error": str(exc),
                "updated_at": _utc_now(),
            }
        )
        self._save_status(status)

    def _load_status(
        self,
        execution_run_id: str,
    ) -> ExternalExecutionWorkspaceStatus | None:
        raw = self.state_store.load().get(EXTERNAL_EXECUTION_WORKSPACES_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("EXTERNAL_EXECUTION_WORKSPACE_STATE_INVALID")
        value = raw.get(execution_run_id)
        return ExternalExecutionWorkspaceStatus.model_validate(value) if value else None

    def _save_status(self, status: ExternalExecutionWorkspaceStatus) -> None:
        state = self.state_store.load()
        raw = state.get(EXTERNAL_EXECUTION_WORKSPACES_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("EXTERNAL_EXECUTION_WORKSPACE_STATE_INVALID")
        records = dict(raw)
        records[status.execution_run_id] = status.model_dump(mode="json")
        state[EXTERNAL_EXECUTION_WORKSPACES_KEY] = records
        self.state_store.save(state)

    def _workspace_path(self, execution_run_id: str) -> Path:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,127}", execution_run_id):
            raise GovernanceError("EXTERNAL_EXECUTION_RUN_ID_INVALID")
        return self.workspace_root / execution_run_id.lower()

    def _remove_workspace(self, workspace: Path) -> None:
        root = self.workspace_root.resolve()
        resolved = workspace.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise GovernanceError("EXTERNAL_WORKSPACE_PATH_ESCAPE") from exc

        def retry_readonly_remove(
            function: Callable[..., object],
            path: str,
            exc_info: tuple[type[BaseException], BaseException, object],
        ) -> None:
            error = exc_info[1]
            if not isinstance(error, PermissionError):
                raise error
            candidate = Path(path)
            if candidate.is_symlink():
                raise error
            try:
                candidate.resolve().relative_to(root)
            except ValueError:
                raise error from None
            os.chmod(path, stat.S_IWRITE)
            function(path)

        shutil.rmtree(resolved, onerror=retry_readonly_remove)

    @staticmethod
    def _github_remote_url(repository: str) -> str:
        if not _REPOSITORY_PATTERN.fullmatch(repository):
            raise GovernanceError("EXTERNAL_EXECUTION_REPOSITORY_IDENTITY_INVALID")
        return f"https://github.com/{repository}.git"

    def _assert_origin(self, workspace: Path, expected_url: str) -> None:
        actual = self._git_scalar(workspace, "remote", "get-url", "origin")
        if self._normalize_remote(actual) != self._normalize_remote(expected_url):
            raise GovernanceError(
                f"EXTERNAL_WORKSPACE_ORIGIN_DRIFT:expected={expected_url} actual={actual}"
            )

    @staticmethod
    def _normalize_remote(value: str) -> str:
        return value.rstrip("/").removesuffix(".git").replace("\\", "/").lower()

    def _remote_branch_head(self, workspace: Path, branch: str) -> str | None:
        output = self._git_scalar(
            workspace,
            "ls-remote",
            "--heads",
            "origin",
            f"refs/heads/{branch}",
        )
        if not output:
            return None
        return output.split(maxsplit=1)[0].lower()

    def _changed_files(self, workspace: Path, before: str, after: str) -> list[str]:
        return self._git_lines(workspace, "diff", "--name-only", before, after)

    def _dirty_paths(self, workspace: Path) -> list[str]:
        output = self._git_scalar(
            workspace,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        if not output:
            return []
        paths: list[str] = []
        for line in output.splitlines():
            if len(line) < 4 or line[2] != " ":
                raise GovernanceError(f"MALFORMED_GIT_STATUS_LINE:{line}")
            value = line[3:]
            if " -> " in value:
                value = value.split(" -> ", 1)[1]
            paths.append(self._normalize_path(value.strip('"')))
        return sorted(dict.fromkeys(paths))

    @staticmethod
    def _normalize_path(value: str) -> str:
        candidate = value.replace("\\", "/")
        parts = PurePosixPath(candidate).parts
        if (
            not parts
            or candidate.startswith("/")
            or re.match(r"^[A-Za-z]:/", candidate)
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise GovernanceError(f"INVALID_EXTERNAL_WORKSPACE_PATH:{value}")
        return PurePosixPath(*parts).as_posix()

    def _resolve_workspace_path(self, workspace: Path, relative_path: str) -> Path:
        normalized = self._normalize_path(relative_path)
        candidate = workspace.joinpath(*PurePosixPath(normalized).parts)
        parent = candidate.parent.resolve()
        try:
            parent.relative_to(workspace.resolve())
        except ValueError as exc:
            raise GovernanceError(f"EXTERNAL_WORKSPACE_PATH_ESCAPE:{relative_path}") from exc
        return parent / candidate.name

    def _git(
        self,
        workspace: Path,
        *args: str,
        timeout_seconds: int = 120,
    ) -> str:
        result = self._run(
            [self.git_executable, "-C", str(workspace), *args],
            timeout_seconds=timeout_seconds,
        )
        return result.stdout.strip()

    def _git_scalar(self, workspace: Path, *args: str) -> str:
        return self._git(workspace, *args).strip()

    def _git_lines(self, workspace: Path, *args: str) -> list[str]:
        output = self._git(workspace, *args)
        return [line.strip() for line in output.splitlines() if line.strip()]

    @staticmethod
    def _run(
        command: list[str],
        *,
        timeout_seconds: int,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GovernanceError(f"EXTERNAL_PROCESS_FAILED:{command[0]}:{exc}") from exc
        if result.returncode != 0 and not allow_failure:
            detail = (result.stderr or result.stdout).strip()
            raise GovernanceError(
                f"EXTERNAL_PROCESS_NONZERO:{command[0]}:EXIT={result.returncode}:{detail}"
            )
        return result
