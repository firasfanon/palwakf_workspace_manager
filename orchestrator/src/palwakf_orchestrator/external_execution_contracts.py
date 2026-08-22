from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.file_apply_contracts import FileMutationSpec


class ExternalWorkspaceLifecycle(StrEnum):
    unprepared = "UNPREPARED"
    ready = "READY"
    dirty = "DIRTY"
    validated = "VALIDATED"
    checkpointed = "CHECKPOINTED"
    blocked = "BLOCKED"


class ExternalValidationCheck(StrEnum):
    git_diff_check = "GIT_DIFF_CHECK"
    flutter_pub_get = "FLUTTER_PUB_GET"
    flutter_analyze = "FLUTTER_ANALYZE"
    flutter_test = "FLUTTER_TEST"
    flutter_build_web = "FLUTTER_BUILD_WEB"
    ruff = "RUFF"
    mypy = "MYPY"
    pytest = "PYTEST"


class PrepareExternalWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recreate: bool = False


class ApplyExternalWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[FileMutationSpec] = Field(min_length=1, max_length=256)


class ValidateExternalWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[ExternalValidationCheck] = Field(default_factory=list, max_length=16)


class CheckpointExternalWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commit_message: str = Field(min_length=4, max_length=240)
    evidence: list[str] = Field(default_factory=list, max_length=64)


class ExternalValidationCommandResult(BaseModel):
    check: ExternalValidationCheck
    command_summary: str
    status: Literal["PASS", "FAIL"]
    exit_code: int | None = None
    duration_ms: int
    output_excerpt: str = ""


class ExternalValidationResult(BaseModel):
    checks: list[ExternalValidationCommandResult]
    all_passed: bool
    validated_paths: list[str]
    started_at: datetime
    completed_at: datetime


class ExternalExecutionWorkspaceStatus(BaseModel):
    execution_run_id: str
    parent_engineering_task_id: str
    project_id: str
    repository: str
    task_branch: str
    expected_head: str
    workspace_path: str | None = None
    lifecycle: ExternalWorkspaceLifecycle = ExternalWorkspaceLifecycle.unprepared
    prepared: bool = False
    authorized: bool = False
    current_head: str | None = None
    remote_head: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    validation: ExternalValidationResult | None = None
    checkpoint_sha: str | None = None
    last_error: str | None = None
    updated_at: datetime
