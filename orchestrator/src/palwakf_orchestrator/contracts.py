from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Transport(StrEnum):
    sdk = "sdk"
    mcp = "mcp"


class SovereigntyBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_write: bool = False
    database_write: Literal[False] = False
    production_mutation: Literal[False] = False
    secret_access: Literal[False] = False


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    prompt: str = Field(min_length=10, max_length=20_000)
    repository: Literal["firasfanon/palwakf_workspace_manager"]
    branch: Literal["agent/workspace-manager-foundation-v1"]
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{7,40}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    transport: Transport = Transport.sdk
    boundaries: SovereigntyBoundaries = Field(default_factory=SovereigntyBoundaries)

    @model_validator(mode="after")
    def restrict_workspace_write(self) -> DispatchRequest:
        if (
            self.boundaries.workspace_write
            and self.task_id != "PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1"
        ):
            raise ValueError("workspace_write is restricted to the governed proof task")
        return self


class DispatchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    executor_prompt: str | None = Field(default=None, min_length=10, max_length=30_000)
    codex_prompt: str | None = Field(default=None, min_length=10, max_length=30_000)
    requires_workspace_write: bool = False

    @model_validator(mode="after")
    def normalize_executor_prompt(self) -> DispatchPlan:
        if self.executor_prompt is None and self.codex_prompt is None:
            raise ValueError("executor_prompt is required")
        if self.executor_prompt is None:
            self.executor_prompt = self.codex_prompt
        if self.codex_prompt is None:
            self.codex_prompt = self.executor_prompt
        return self

    @property
    def effective_executor_prompt(self) -> str:
        assert self.executor_prompt is not None
        return self.executor_prompt


class PlanningResult(BaseModel):
    plan: DispatchPlan
    reasoning_provider_id: str = "openai-agents"
    reasoning_response_id: str | None = None
    agents_response_id: str | None = None


class RepositoryState(BaseModel):
    repository: str
    branch: str
    local_head: str
    remote_head: str
    clean: bool


class GatewayResult(BaseModel):
    transport: Transport
    thread_id: str | None = None
    status: str
    final_response: str
    tool_outputs: list[dict[str, object]] = Field(default_factory=list)


class DispatchResponse(BaseModel):
    task_id: str
    status: Literal["completed"]
    transport: Transport
    execution_receipt: str
    idempotency_key: str
    idempotency_replayed: bool
    repository_state: RepositoryState
    result_repository_state: RepositoryState
    plan_summary: str
    reasoning_provider_id: str = "openai-agents"
    reasoning_response_id: str | None = None
    executor_id: str = "codex"
    executor_thread_id: str | None = None
    agents_response_id: str | None = None
    codex_thread_id: str | None = None
    final_response: str
    tool_outputs: list[dict[str, object]] = Field(default_factory=list)
    boundaries: SovereigntyBoundaries


class HealthResponse(BaseModel):
    service: Literal["palwakf-orchestrator"]
    version: Literal["0.1.0"]
    status: Literal["ready"]
    remote_deployment: Literal[False]
    boundaries: SovereigntyBoundaries
    transports: tuple[Transport, Transport]
