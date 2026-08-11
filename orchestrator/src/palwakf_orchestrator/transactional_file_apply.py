from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.file_apply_contracts import (
    FileApplyClassification,
    FileApplyJournalRecord,
    FileApplyJournalStatus,
    FileApplyManifestItem,
    FileApplyPlan,
    FileApplyPlanItem,
    FileApplyResult,
    FileMutationSpec,
    FilePreimageMode,
    GovernedFileApplyRequest,
)
from palwakf_orchestrator.persistence import StateStore

ForwardWriter = Callable[[Path, bytes], None]


def canonical_text_bytes(text: str) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.rstrip("\n") + "\n"
    return normalized.encode("utf-8")


def canonical_existing_bytes(raw: bytes) -> bytes:
    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GovernanceError("NON_UTF8_TARGET") from exc
    return canonical_text_bytes(text)


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalized_repo_path(value: str) -> str:
    candidate = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", candidate) or candidate.startswith("/"):
        raise GovernanceError(f"ABSOLUTE_TARGET_PATH_FORBIDDEN:{value}")
    parts = PurePosixPath(candidate).parts
    if not parts or any(part in {".", ".."} for part in parts):
        raise GovernanceError(f"INVALID_TARGET_PATH:{value}")
    return PurePosixPath(*parts).as_posix()


class GovernedTransactionalFileApply:
    """Transactional, idempotent UTF-8/LF source mutation engine.

    The service never commits, pushes, contacts a remote provider, or executes
    arbitrary shell commands. Git subprocesses are read-only repository gates.
    """

    def __init__(
        self,
        repo_root: Path,
        state_store: StateStore,
        *,
        execution_host_id: str,
        forward_writer: ForwardWriter | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.state_store = state_store
        self.execution_host_id = execution_host_id
        self._forward_writer = forward_writer or self._atomic_write
        if not (self.repo_root / ".git").exists():
            raise GovernanceError(f"REPOSITORY_NOT_FOUND:{self.repo_root}")

    def plan(self, request: GovernedFileApplyRequest) -> FileApplyPlan:
        specs = self._normalized_specs(request.files)
        self._assert_git_binding(request, {spec.path for spec in specs})
        manifest_items = [self._manifest_item(spec) for spec in specs]
        manifest_sha256 = self._manifest_sha256(request, manifest_items)
        run_id = f"{request.task_id}-{manifest_sha256[:16]}"
        items = [self._classify(spec) for spec in specs]
        blockers = [item.blocker for item in items if item.blocker]
        plan = FileApplyPlan(
            run_id=run_id,
            task_id=request.task_id,
            repository=request.repository,
            expected_branch=request.expected_branch,
            expected_head=request.expected_head.lower(),
            manifest_sha256=manifest_sha256,
            items=items,
            blocked=bool(blockers),
            blockers=[blocker for blocker in blockers if blocker is not None],
        )
        self._persist_plan(plan)
        return plan

    def apply(self, request: GovernedFileApplyRequest) -> FileApplyResult:
        plan = self.plan(request)
        if plan.blocked:
            self._update_journal(
                plan,
                FileApplyJournalStatus.blocked,
                last_error=";".join(plan.blockers),
            )
            raise GovernanceError("FILE_APPLY_BLOCKED:" + ";".join(plan.blockers))

        if not self.state_store.acquire_repository_writer(
            request.repository,
            request.task_id,
            self.execution_host_id,
        ):
            raise GovernanceError(f"REPOSITORY_WRITER_BUSY:{request.repository}")

        try:
            # Re-plan under the writer lock to close the local race window.
            plan = self.plan(request)
            if plan.blocked:
                self._update_journal(
                    plan,
                    FileApplyJournalStatus.blocked,
                    last_error=";".join(plan.blockers),
                )
                raise GovernanceError("FILE_APPLY_BLOCKED:" + ";".join(plan.blockers))

            classifications = {item.path: item.classification for item in plan.items}
            if all(
                item.classification == FileApplyClassification.already_postimage
                for item in plan.items
            ):
                self._update_journal(plan, FileApplyJournalStatus.verified)
                return FileApplyResult(
                    run_id=plan.run_id,
                    task_id=plan.task_id,
                    repository=plan.repository,
                    manifest_sha256=plan.manifest_sha256,
                    status="NOOP_VERIFIED",
                    changed_paths=[],
                    classifications=classifications,
                )

            specs = self._normalized_specs(request.files)
            spec_map = {spec.path: spec for spec in specs}
            changed_paths = [
                item.path
                for item in plan.items
                if item.classification
                in {
                    FileApplyClassification.clean_preimage,
                    FileApplyClassification.partial_postimage,
                }
            ]

            with tempfile.TemporaryDirectory(prefix="palwakf-file-apply-") as temp_name:
                temp_root = Path(temp_name)
                staged = self._stage_postimages(temp_root, specs)
                preimages = self._capture_preimages(temp_root, changed_paths)
                self._update_journal(plan, FileApplyJournalStatus.prepared)
                self._update_journal(plan, FileApplyJournalStatus.started)

                mutated: list[str] = []
                try:
                    for path in changed_paths:
                        target = self._resolve_target(path)
                        self._forward_writer(target, staged[path].read_bytes())
                        mutated.append(path)
                        self._assert_exact_postimage(target, spec_map[path])

                    self._update_journal(
                        plan,
                        FileApplyJournalStatus.applied,
                        changed_paths=changed_paths,
                    )
                    for spec in specs:
                        self._assert_exact_postimage(self._resolve_target(spec.path), spec)
                except Exception as exc:
                    try:
                        self._rollback(mutated, preimages)
                    except Exception as rollback_exc:
                        self._update_journal(
                            plan,
                            FileApplyJournalStatus.failed,
                            changed_paths=mutated,
                            last_error=f"ROLLBACK_FAILED:{rollback_exc}",
                        )
                        raise GovernanceError(
                            f"FILE_APPLY_FAILED_AND_ROLLBACK_FAILED:{rollback_exc}"
                        ) from rollback_exc

                    self._update_journal(
                        plan,
                        FileApplyJournalStatus.rolled_back,
                        changed_paths=mutated,
                        last_error=str(exc),
                    )
                    raise GovernanceError(f"FILE_APPLY_FAILED_ROLLED_BACK:{exc}") from exc

            self._update_journal(
                plan,
                FileApplyJournalStatus.verified,
                changed_paths=changed_paths,
            )
            return FileApplyResult(
                run_id=plan.run_id,
                task_id=plan.task_id,
                repository=plan.repository,
                manifest_sha256=plan.manifest_sha256,
                status="VERIFIED",
                changed_paths=changed_paths,
                classifications=classifications,
            )
        finally:
            self.state_store.release_repository_writer(request.repository, request.task_id)

    def journal(self, run_id: str) -> FileApplyJournalRecord | None:
        raw = self.state_store.load().get("governed_file_apply_journal", {}).get(run_id)
        return FileApplyJournalRecord.model_validate(raw) if raw else None

    def _normalized_specs(self, specs: list[FileMutationSpec]) -> list[FileMutationSpec]:
        normalized: list[FileMutationSpec] = []
        seen: set[str] = set()
        for spec in specs:
            path = normalized_repo_path(spec.path)
            if path in seen:
                raise GovernanceError(f"DUPLICATE_TARGET_PATH:{path}")
            seen.add(path)
            normalized.append(spec.model_copy(update={"path": path}))
        return sorted(normalized, key=lambda item: item.path)

    def _manifest_item(self, spec: FileMutationSpec) -> FileApplyManifestItem:
        return FileApplyManifestItem(
            path=spec.path,
            preimage_mode=spec.preimage_mode,
            expected_preimage_canonical_sha256=(
                spec.expected_preimage_canonical_sha256.lower()
                if spec.expected_preimage_canonical_sha256
                else None
            ),
            postimage_sha256=sha256_hex(canonical_text_bytes(spec.postimage_text)),
        )

    def _manifest_sha256(
        self,
        request: GovernedFileApplyRequest,
        items: list[FileApplyManifestItem],
    ) -> str:
        payload = {
            "skill": "GOVERNED_TRANSACTIONAL_FILE_APPLY_V1",
            "repository": request.repository,
            "expected_branch": request.expected_branch,
            "expected_head": request.expected_head.lower(),
            "items": [item.model_dump(mode="json") for item in items],
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return sha256_hex(canonical)

    def _classify(self, spec: FileMutationSpec) -> FileApplyPlanItem:
        target = self._resolve_target(spec.path)
        postimage_sha = sha256_hex(canonical_text_bytes(spec.postimage_text))
        if not target.exists():
            if spec.preimage_mode == FilePreimageMode.absent:
                return FileApplyPlanItem(
                    path=spec.path,
                    classification=FileApplyClassification.clean_preimage,
                    existed_before=False,
                    expected_preimage_canonical_sha256=None,
                    postimage_sha256=postimage_sha,
                )
            return FileApplyPlanItem(
                path=spec.path,
                classification=FileApplyClassification.foreign_drift,
                existed_before=False,
                expected_preimage_canonical_sha256=spec.expected_preimage_canonical_sha256,
                postimage_sha256=postimage_sha,
                blocker=f"EXPECTED_PREIMAGE_MISSING:{spec.path}",
            )

        if target.is_symlink():
            return FileApplyPlanItem(
                path=spec.path,
                classification=FileApplyClassification.foreign_drift,
                existed_before=True,
                expected_preimage_canonical_sha256=spec.expected_preimage_canonical_sha256,
                postimage_sha256=postimage_sha,
                blocker=f"SYMLINK_TARGET_FORBIDDEN:{spec.path}",
            )
        if not target.is_file():
            return FileApplyPlanItem(
                path=spec.path,
                classification=FileApplyClassification.foreign_drift,
                existed_before=True,
                expected_preimage_canonical_sha256=spec.expected_preimage_canonical_sha256,
                postimage_sha256=postimage_sha,
                blocker=f"TARGET_NOT_REGULAR_FILE:{spec.path}",
            )

        raw = target.read_bytes()
        raw_sha = sha256_hex(raw)
        try:
            canonical = canonical_existing_bytes(raw)
        except GovernanceError:
            return FileApplyPlanItem(
                path=spec.path,
                classification=FileApplyClassification.foreign_drift,
                existed_before=True,
                actual_raw_sha256=raw_sha,
                expected_preimage_canonical_sha256=spec.expected_preimage_canonical_sha256,
                postimage_sha256=postimage_sha,
                blocker=f"NON_UTF8_TARGET:{spec.path}",
            )
        canonical_sha = sha256_hex(canonical)

        if raw_sha == postimage_sha:
            classification = FileApplyClassification.already_postimage
            blocker = None
        elif canonical_sha == postimage_sha:
            classification = FileApplyClassification.partial_postimage
            blocker = None
        elif (
            spec.preimage_mode == FilePreimageMode.exact_canonical_sha256
            and spec.expected_preimage_canonical_sha256 is not None
            and canonical_sha == spec.expected_preimage_canonical_sha256.lower()
        ):
            classification = FileApplyClassification.clean_preimage
            blocker = None
        else:
            classification = FileApplyClassification.foreign_drift
            blocker = f"FOREIGN_DRIFT:{spec.path}"

        return FileApplyPlanItem(
            path=spec.path,
            classification=classification,
            existed_before=True,
            actual_raw_sha256=raw_sha,
            actual_canonical_sha256=canonical_sha,
            expected_preimage_canonical_sha256=(
                spec.expected_preimage_canonical_sha256.lower()
                if spec.expected_preimage_canonical_sha256
                else None
            ),
            postimage_sha256=postimage_sha,
            blocker=blocker,
        )

    def _resolve_target(self, relative_path: str) -> Path:
        normalized = normalized_repo_path(relative_path)
        relative = PurePosixPath(normalized)
        candidate = self.repo_root.joinpath(*relative.parts)
        if candidate.exists() and candidate.is_symlink():
            return candidate
        parent = candidate.parent.resolve()
        try:
            parent.relative_to(self.repo_root)
        except ValueError as exc:
            raise GovernanceError(f"TARGET_ESCAPES_REPOSITORY:{relative_path}") from exc
        return parent / candidate.name

    def _assert_git_binding(
        self,
        request: GovernedFileApplyRequest,
        target_paths: set[str],
    ) -> None:
        branch = self._git_scalar("branch", "--show-current")
        if branch != request.expected_branch:
            raise GovernanceError(
                f"BRANCH_MISMATCH:expected={request.expected_branch} actual={branch}"
            )
        head = self._git_scalar("rev-parse", "HEAD").lower()
        if head != request.expected_head.lower():
            raise GovernanceError(
                f"HEAD_MISMATCH:expected={request.expected_head.lower()} actual={head}"
            )
        dirty = self._git_dirty_paths()
        unrelated = sorted(dirty - target_paths)
        if unrelated:
            raise GovernanceError("UNRELATED_WORKTREE_DRIFT:" + ",".join(unrelated))

    def _git_scalar(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise GovernanceError(
                f"GIT_READ_FAILED:{' '.join(args)}:EXIT={result.returncode}:{detail}"
            )
        return result.stdout.strip()

    def _git_dirty_paths(self) -> set[str]:
        output = self._git_scalar("status", "--porcelain=v1", "--untracked-files=all")
        paths: set[str] = set()
        if not output:
            return paths
        for line in output.splitlines():
            value = line[3:]
            if " -> " in value:
                value = value.split(" -> ", 1)[1]
            paths.add(normalized_repo_path(value.strip('"')))
        return paths

    def _stage_postimages(
        self,
        temp_root: Path,
        specs: list[FileMutationSpec],
    ) -> dict[str, Path]:
        staged: dict[str, Path] = {}
        stage_root = temp_root / "postimages"
        stage_root.mkdir(parents=True, exist_ok=True)
        for index, spec in enumerate(specs):
            payload = canonical_text_bytes(spec.postimage_text)
            expected = sha256_hex(payload)
            path = stage_root / f"{index:04d}.bin"
            path.write_bytes(payload)
            if sha256_hex(path.read_bytes()) != expected:
                raise GovernanceError(f"STAGED_POSTIMAGE_HASH_MISMATCH:{spec.path}")
            staged[spec.path] = path
        return staged

    def _capture_preimages(
        self,
        temp_root: Path,
        changed_paths: list[str],
    ) -> dict[str, dict[str, Any]]:
        backup_root = temp_root / "preimages"
        backup_root.mkdir(parents=True, exist_ok=True)
        captured: dict[str, dict[str, Any]] = {}
        for index, path in enumerate(changed_paths):
            target = self._resolve_target(path)
            if not target.exists():
                captured[path] = {"existed": False, "backup": None, "mode": None}
                continue
            backup = backup_root / f"{index:04d}.bin"
            raw = target.read_bytes()
            backup.write_bytes(raw)
            captured[path] = {
                "existed": True,
                "backup": backup,
                "mode": stat.S_IMODE(target.stat().st_mode),
                "raw_sha256": sha256_hex(raw),
            }
        return captured

    def _assert_exact_postimage(self, target: Path, spec: FileMutationSpec) -> None:
        if not target.exists() or not target.is_file() or target.is_symlink():
            raise GovernanceError(f"POSTIMAGE_TARGET_INVALID:{spec.path}")
        actual = sha256_hex(target.read_bytes())
        expected = sha256_hex(canonical_text_bytes(spec.postimage_text))
        if actual != expected:
            raise GovernanceError(
                f"POSTIMAGE_HASH_MISMATCH:{spec.path}:expected={expected}:actual={actual}"
            )

    def _rollback(
        self,
        mutated_paths: list[str],
        preimages: dict[str, dict[str, Any]],
    ) -> None:
        for path in reversed(mutated_paths):
            target = self._resolve_target(path)
            snapshot = preimages[path]
            if snapshot["existed"]:
                backup = snapshot["backup"]
                assert isinstance(backup, Path)
                self._atomic_write(target, backup.read_bytes(), mode=snapshot["mode"])
                restored = sha256_hex(target.read_bytes())
                if restored != snapshot["raw_sha256"]:
                    raise GovernanceError(f"ROLLBACK_HASH_MISMATCH:{path}")
            else:
                if target.exists():
                    target.unlink()
                self._remove_empty_parents(target.parent)

    def _atomic_write(self, target: Path, payload: bytes, mode: int | None = None) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        effective_mode = mode
        if effective_mode is None and target.exists() and target.is_file():
            effective_mode = stat.S_IMODE(target.stat().st_mode)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.palwakf-",
            dir=str(target.parent),
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if effective_mode is not None:
                os.chmod(temp_path, effective_mode)
            os.replace(temp_path, target)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _remove_empty_parents(self, start: Path) -> None:
        current = start
        while current != self.repo_root:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def _persist_plan(self, plan: FileApplyPlan) -> None:
        now = datetime.now(UTC)
        existing = self.journal(plan.run_id)
        record = FileApplyJournalRecord(
            run_id=plan.run_id,
            task_id=plan.task_id,
            repository=plan.repository,
            expected_branch=plan.expected_branch,
            expected_head=plan.expected_head,
            manifest_sha256=plan.manifest_sha256,
            status=FileApplyJournalStatus.planned,
            classifications={item.path: item.classification for item in plan.items},
            changed_paths=existing.changed_paths if existing else [],
            last_error=None,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._persist_journal(record)

    def _update_journal(
        self,
        plan: FileApplyPlan,
        status: FileApplyJournalStatus,
        *,
        changed_paths: list[str] | None = None,
        last_error: str | None = None,
    ) -> None:
        existing = self.journal(plan.run_id)
        now = datetime.now(UTC)
        record = FileApplyJournalRecord(
            run_id=plan.run_id,
            task_id=plan.task_id,
            repository=plan.repository,
            expected_branch=plan.expected_branch,
            expected_head=plan.expected_head,
            manifest_sha256=plan.manifest_sha256,
            status=status,
            classifications={item.path: item.classification for item in plan.items},
            changed_paths=changed_paths or (existing.changed_paths if existing else []),
            last_error=last_error,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._persist_journal(record)

    def _persist_journal(self, record: FileApplyJournalRecord) -> None:
        state = self.state_store.load()
        journal = state.setdefault("governed_file_apply_journal", {})
        journal[record.run_id] = record.model_dump(mode="json")
        self.state_store.save(state)
