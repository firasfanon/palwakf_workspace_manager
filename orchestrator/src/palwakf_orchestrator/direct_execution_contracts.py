from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DirectWorkspaceClass(StrEnum):
    palwakf_governed_project = "PALWAKF_GOVERNED_PROJECT"
    research = "RESEARCH"
    private_project = "PRIVATE_PROJECT"


class DirectExecutionStatus(StrEnum):
    completed = "COMPLETED"
    failed = "FAILED"


class DirectExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=3, max_length=200)
    item_class: DirectWorkspaceClass
    title: str = Field(min_length=1, max_length=300)
    prompt: str = Field(min_length=1, max_length=20_000)
    project_uid: str | None = Field(default=None, max_length=64)
    technical_id: str | None = Field(default=None, max_length=80)
    context_summary: str = Field(default="", max_length=4_000)


class DirectExecutionReceipt(BaseModel):
    session_id: str
    item_id: str
    item_class: DirectWorkspaceClass
    project_uid: str | None = None
    technical_id: str | None = None
    title: str
    route: str = "DIRECT"
    status: DirectExecutionStatus
    provider_id: str | None = None
    model: str
    prompt_sha256: str
    output: str = ""
    error_code: str | None = None
    palwakf_governance_used: bool = False
    engineering_task_used: bool = False
    operator_authorization_used: bool = False
    tool_plan_used: bool = False
    started_at: datetime
    completed_at: datetime
