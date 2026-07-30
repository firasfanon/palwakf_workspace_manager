from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from agents import Agent, ModelSettings, RunConfig, Runner
from openai.types.shared import Reasoning

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import DispatchPlan, DispatchRequest, RepositoryState
from palwakf_orchestrator.errors import GatewayError


class Planner(Protocol):
    async def plan(
        self,
        request: DispatchRequest,
        repository_state: RepositoryState,
    ) -> DispatchPlan: ...


class AgentsPlanner:
    def __init__(self, settings: Settings, prompt_path: Path | None = None) -> None:
        self._settings = settings
        self._prompt_path = prompt_path or (
            Path(__file__).resolve().parents[2] / "docs" / "prompt.md"
        )

    async def plan(
        self,
        request: DispatchRequest,
        repository_state: RepositoryState,
    ) -> DispatchPlan:
        if not os.environ.get("OPENAI_API_KEY"):
            raise GatewayError("OPENAI_API_KEY is unavailable to the orchestrator runtime")
        instructions = self._prompt_path.read_text(encoding="utf-8")
        agent = Agent(
            name="PalWakf Sovereign Dispatch Planner",
            instructions=instructions,
            model=self._settings.openai_model,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort="low"),
                verbosity="low",
                store=False,
            ),
            output_type=DispatchPlan,
        )
        envelope = {
            "task": request.model_dump(mode="json"),
            "repository_state": repository_state.model_dump(mode="json"),
        }
        result = await Runner.run(
            agent,
            json.dumps(envelope, ensure_ascii=False, sort_keys=True),
            max_turns=self._settings.agent_max_turns,
            run_config=RunConfig(
                workflow_name="PalWakf Sovereign Dispatch V1",
                trace_include_sensitive_data=False,
            ),
        )
        if isinstance(result.final_output, DispatchPlan):
            return result.final_output
        return DispatchPlan.model_validate(result.final_output)
