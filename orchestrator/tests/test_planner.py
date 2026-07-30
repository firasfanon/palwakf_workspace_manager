from pathlib import Path

import pytest

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import DispatchRequest, RepositoryState
from palwakf_orchestrator.errors import GatewayError
from palwakf_orchestrator.planner import AgentsPlanner
from tests.test_contracts import valid_request

FULL_HEAD = "a312d498bf89c509ae04a6c2eaa476de0a7c39bc"


async def test_planner_fails_closed_without_runtime_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = DispatchRequest.model_validate(valid_request())
    state = RepositoryState(
        repository=request.repository,
        branch=request.branch,
        local_head=FULL_HEAD,
        remote_head=FULL_HEAD,
        clean=True,
    )

    with pytest.raises(GatewayError, match="unavailable"):
        await AgentsPlanner(Settings(workspace_root=tmp_path)).plan(request, state)
