from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Transport(StrEnum):
    sdk = "sdk"
    mcp = "mcp"


class SovereigntyBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_write: Literal[False] = False
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


class DispatchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    codex_prompt: str = Field(min_length=10, max_length=30_000)
    requires_workspace_write: bool = False


class PlanningResult(BaseModel):
    plan: DispatchPlan
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


class DispatchResponse(BaseModel):
    task_id: str
    status: Literal["completed"]
    transport: Transport
    execution_receipt: str
    idempotency_key: str
    idempotency_replayed: bool
    repository_state: RepositoryState
    plan_summary: str
    agents_response_id: str | None = None
    codex_thread_id: str | None = None
    final_response: str
    boundaries: SovereigntyBoundaries


class HealthResponse(BaseModel):
    service: Literal["palwakf-orchestrator"]
    version: Literal["0.1.0"]
    status: Literal["ready"]
    remote_deployment: Literal[False]
    boundaries: SovereigntyBoundaries
    transports: tuple[Transport, Transport]
