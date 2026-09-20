from __future__ import annotations

import fnmatch
import hashlib
import json
import ntpath
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RdcActionClass(StrEnum):
    filesystem_read = "filesystem.read"
    terminal_read = "terminal.read"
    git_read = "git.read"
    gh_read = "gh.read"
    filesystem_write = "filesystem.write"
    terminal_mutating = "terminal.mutating"
    git_write = "git.write"
    gh_write = "gh.write"
    ollama_local = "ollama.local"
    hermes_local = "hermes.local"


MUTATING_RDC_ACTIONS = frozenset(
    {
        RdcActionClass.filesystem_write,
        RdcActionClass.terminal_mutating,
        RdcActionClass.git_write,
        RdcActionClass.gh_write,
    }
)


class RdcPreflightDecision(StrEnum):
    allow = "ALLOW"
    deny = "DENY"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class RdcToolConfigSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    app_version: str = Field(min_length=1, max_length=100)
    default_shell: str = Field(min_length=1, max_length=500)
    allowed_directories: tuple[str, ...] = ()
    blocked_commands: tuple[str, ...] = ()
    telemetry_enabled: bool

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.model_dump(mode="json"))


class RdcRuntimeIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    device_id: str = Field(min_length=8, max_length=200)
    device_name: str = Field(min_length=1, max_length=200)
    device_status: Literal["online", "offline"]
    local_user: str = Field(min_length=1, max_length=200)
    user_profile: str = Field(min_length=1, max_length=500)
    tool_config: RdcToolConfigSnapshotV1


class RdcExecutionChannelContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: Literal["PALWAKF_RDC_EXECUTION_CHANNEL_V1"] = "PALWAKF_RDC_EXECUTION_CHANNEL_V1"
    channel_id: Literal["remote-desktop-commander"] = "remote-desktop-commander"
    source_authority: Literal["MPCE-20260914-010"] = "MPCE-20260914-010"
    expected_device_id: str = Field(min_length=8, max_length=200)
    expected_device_name: str = Field(min_length=1, max_length=200)
    expected_local_user: str = Field(min_length=1, max_length=200)
    expected_tool_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_actions: tuple[RdcActionClass, ...] = Field(min_length=1)
    authority_expansion_allowed: Literal[False] = False


class RdcTaskBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    project_id: str = Field(min_length=2, max_length=128)
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
    local_repository_path: str = Field(min_length=3, max_length=1000)
    branch: str = Field(pattern=r"^task/[A-Za-z0-9._/-]{3,180}$")
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    authority_reference: str = Field(min_length=8, max_length=2000)
    mutation_class: Literal["read-only", "source-write"]
    scope_patterns: tuple[str, ...] = Field(min_length=1, max_length=64)
    require_clean_worktree: bool = True


class RdcRepositoryRealityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=2, max_length=128)
    repository: str
    local_repository_path: str
    branch: str
    local_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    remote_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    origin: str = Field(min_length=1, max_length=1000)
    worktree_clean: bool


class RdcPreflightRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract: RdcExecutionChannelContractV1
    runtime: RdcRuntimeIdentityV1
    binding: RdcTaskBindingV1
    reality: RdcRepositoryRealityV1
    requested_action: RdcActionClass
    requested_paths: tuple[str, ...] = Field(min_length=1, max_length=256)


class RdcPreflightReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: RdcPreflightDecision
    channel_id: Literal["remote-desktop-commander"]
    task_id: str
    project_id: str
    blockers: tuple[str, ...]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_scope_enforced: Literal[True] = True
    tool_scope_broader_than_task_scope: bool
    authority_expansion_allowed: Literal[False] = False


def _same_windows_path(left: str, right: str) -> bool:
    return ntpath.normcase(ntpath.normpath(left)) == ntpath.normcase(ntpath.normpath(right))


def _windows_path_within(child: str, parent: str) -> bool:
    try:
        child_norm = ntpath.normcase(ntpath.abspath(child))
        parent_norm = ntpath.normcase(ntpath.abspath(parent))
        return ntpath.commonpath([child_norm, parent_norm]) == parent_norm
    except ValueError:
        return False


def _normalized_relative_path(value: str) -> str | None:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    if path.parts and ":" in path.parts[0]:
        return None
    return path.as_posix()


def _scope_pattern_valid(pattern: str) -> bool:
    normalized = pattern.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return False
    parts = PurePosixPath(normalized).parts
    return ".." not in parts and not (parts and ":" in parts[0])


def _path_matches_scope(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern.replace("\\", "/")) for pattern in patterns)


def evaluate_rdc_preflight(request: RdcPreflightRequestV1) -> RdcPreflightReceiptV1:
    contract = request.contract
    runtime = request.runtime
    binding = request.binding
    reality = request.reality
    blockers: list[str] = []

    if runtime.device_status != "online":
        blockers.append("RDC_DEVICE_NOT_ONLINE")
    if runtime.device_id != contract.expected_device_id:
        blockers.append("RDC_DEVICE_ID_MISMATCH")
    if runtime.device_name != contract.expected_device_name:
        blockers.append("RDC_DEVICE_NAME_MISMATCH")
    if runtime.local_user != contract.expected_local_user:
        blockers.append("RDC_LOCAL_USER_MISMATCH")
    if runtime.tool_config.fingerprint_sha256 != contract.expected_tool_config_sha256:
        blockers.append("RDC_TOOL_CONFIG_MISMATCH")

    if reality.project_id != binding.project_id:
        blockers.append("RDC_PROJECT_SCOPE_MISMATCH")
    if reality.repository != binding.repository:
        blockers.append("RDC_TARGET_REPOSITORY_MISMATCH")
    if not _same_windows_path(
        reality.local_repository_path,
        binding.local_repository_path,
    ):
        blockers.append("RDC_LOCAL_REPOSITORY_PATH_MISMATCH")
    if reality.branch != binding.branch:
        blockers.append("RDC_TASK_BRANCH_MISMATCH")
    if reality.local_head.lower() != binding.expected_head.lower():
        blockers.append("RDC_LOCAL_HEAD_MISMATCH")
    if reality.remote_head.lower() != binding.expected_head.lower():
        blockers.append("RDC_REMOTE_HEAD_MISMATCH")
    if binding.require_clean_worktree and not reality.worktree_clean:
        blockers.append("RDC_WORKTREE_NOT_CLEAN")

    if request.requested_action not in contract.allowed_actions:
        blockers.append("RDC_ACTION_NOT_ALLOWED")
    if binding.mutation_class == "read-only" and request.requested_action in MUTATING_RDC_ACTIONS:
        blockers.append("RDC_MUTATION_EXCEEDS_TASK_AUTHORITY")

    if any(not _scope_pattern_valid(pattern) for pattern in binding.scope_patterns):
        blockers.append("RDC_INVALID_TASK_SCOPE_PATTERN")

    normalized_paths: list[str] = []
    for raw_path in request.requested_paths:
        normalized = _normalized_relative_path(raw_path)
        if normalized is None:
            blockers.append("RDC_REQUESTED_PATH_ESCAPES_REPOSITORY")
            continue
        normalized_paths.append(normalized)
        if not _path_matches_scope(normalized, binding.scope_patterns):
            blockers.append("RDC_REQUESTED_PATH_OUT_OF_SCOPE")

    configured_roots = runtime.tool_config.allowed_directories
    if configured_roots and not any(
        _windows_path_within(binding.local_repository_path, root) for root in configured_roots
    ):
        blockers.append("RDC_TOOL_CONFIG_EXCLUDES_TARGET_REPOSITORY")
    broad_tool_scope = not configured_roots
    unique_blockers = tuple(dict.fromkeys(blockers))
    decision = RdcPreflightDecision.allow if not unique_blockers else RdcPreflightDecision.deny
    request_sha256 = _sha256(request.model_dump(mode="json"))

    return RdcPreflightReceiptV1(
        decision=decision,
        channel_id=contract.channel_id,
        task_id=binding.task_id,
        project_id=binding.project_id,
        blockers=unique_blockers,
        request_sha256=request_sha256,
        tool_config_sha256=runtime.tool_config.fingerprint_sha256,
        tool_scope_broader_than_task_scope=broad_tool_scope,
    )
