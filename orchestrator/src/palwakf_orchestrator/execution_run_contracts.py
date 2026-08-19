from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.engineering_os_contracts import EngineeringTaskRecord
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord
from palwakf_orchestrator.state_rollup_policy import StateRollupDecision


class CreateExecutionRunRequest(BaseModel):
    """Operator input only. Parent task authority is derived server-side."""

    model_config = ConfigDict(extra="forbid")

    execution_run_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    authority_reference: str = Field(min_length=8, max_length=2_000)
    prompt: str = Field(min_length=10, max_length=20_000)
    constraints: list[str] = Field(min_length=1, max_length=31)
    sandbox: Literal["read-only", "workspace-write"] | None = None
    max_turns: int = Field(default=6, ge=1, le=20)
    timeout_seconds: int = Field(default=1_800, ge=30, le=3_600)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    relay_provider_id: str = Field(
        default="chatgpt",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$",
    )
    requires_explicit_authorization: Literal[True] = True


class ExecutionRunOperationalView(BaseModel):
    execution_run_id: str
    legacy_operator_task_id: str
    parent_engineering_task_id: str
    parent_task: EngineeringTaskRecord
    operator_task: OperatorTaskRecord
    rollup: StateRollupDecision


class EngineeringTaskExecutionContext(BaseModel):
    parent_task: EngineeringTaskRecord
    runs: list[ExecutionRunOperationalView]
