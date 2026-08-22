from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FilePreimageMode(StrEnum):
    absent = "ABSENT"
    exact_canonical_sha256 = "EXACT_CANONICAL_SHA256"


class FileApplyClassification(StrEnum):
    clean_preimage = "CLEAN_PREIMAGE"
    already_postimage = "ALREADY_POSTIMAGE"
    partial_postimage = "PARTIAL_POSTIMAGE"
    foreign_drift = "FOREIGN_DRIFT"


class FileApplyJournalStatus(StrEnum):
    planned = "PLANNED"
    prepared = "PREPARED"
    started = "STARTED"
    applied = "APPLIED"
    verified = "VERIFIED"
    blocked = "BLOCKED"
    rolled_back = "ROLLED_BACK"
    failed = "FAILED"


class FileMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=512)
    preimage_mode: FilePreimageMode
    expected_preimage_canonical_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    postimage_text: str

    @model_validator(mode="after")
    def validate_preimage_contract(self) -> FileMutationSpec:
        if self.preimage_mode == FilePreimageMode.exact_canonical_sha256:
            if self.expected_preimage_canonical_sha256 is None:
                raise ValueError(
                    "EXACT_CANONICAL_SHA256 requires expected_preimage_canonical_sha256"
                )
        elif self.expected_preimage_canonical_sha256 is not None:
            raise ValueError("ABSENT preimage must not provide a preimage sha256")
        return self


class GovernedFileApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    repository: str = Field(min_length=3, max_length=256)
    expected_branch: str = Field(min_length=1, max_length=256)
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    files: list[FileMutationSpec] = Field(min_length=1, max_length=256)


class FileApplyManifestItem(BaseModel):
    path: str
    preimage_mode: FilePreimageMode
    expected_preimage_canonical_sha256: str | None
    postimage_sha256: str
    encoding: Literal["UTF-8_NO_BOM"] = "UTF-8_NO_BOM"
    eol: Literal["LF"] = "LF"
    eof_newline: Literal["EXACTLY_ONE"] = "EXACTLY_ONE"


class FileApplyPlanItem(BaseModel):
    path: str
    classification: FileApplyClassification
    existed_before: bool
    actual_raw_sha256: str | None = None
    actual_canonical_sha256: str | None = None
    expected_preimage_canonical_sha256: str | None = None
    postimage_sha256: str
    blocker: str | None = None


class FileApplyPlan(BaseModel):
    run_id: str
    task_id: str
    repository: str
    expected_branch: str
    expected_head: str
    manifest_sha256: str
    items: list[FileApplyPlanItem]
    blocked: bool
    blockers: list[str]


class FileApplyJournalRecord(BaseModel):
    run_id: str
    task_id: str
    repository: str
    expected_branch: str
    expected_head: str
    manifest_sha256: str
    status: FileApplyJournalStatus
    classifications: dict[str, FileApplyClassification]
    changed_paths: list[str] = Field(default_factory=list)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class FileApplyResult(BaseModel):
    run_id: str
    task_id: str
    repository: str
    manifest_sha256: str
    status: Literal["VERIFIED", "NOOP_VERIFIED"]
    changed_paths: list[str]
    classifications: dict[str, FileApplyClassification]
    rollback_performed: Literal[False] = False
