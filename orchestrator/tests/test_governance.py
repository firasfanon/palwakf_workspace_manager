from pathlib import Path

import pytest

from palwakf_orchestrator.contracts import DispatchPlan, DispatchRequest
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.governance import GovernanceGate
from tests.test_contracts import valid_request

FULL_HEAD = "a312d498bf89c509ae04a6c2eaa476de0a7c39bc"


class FakeGit:
    def __init__(self, *, remote_head: str = FULL_HEAD, status: str = "") -> None:
        self.remote_head = remote_head
        self.status = status

    def run(self, workspace: Path, *args: str) -> str:
        if args == ("branch", "--show-current"):
            return "agent/workspace-manager-foundation-v1"
        if args == ("rev-parse", "HEAD"):
            return FULL_HEAD
        if args == ("status", "--porcelain"):
            return self.status
        if args[:2] == ("ls-remote", "origin"):
            return f"{self.remote_head}\t{args[2]}"
        raise AssertionError(args)


def test_repository_gate_accepts_exact_governed_state(tmp_path: Path) -> None:
    request = DispatchRequest.model_validate(valid_request())
    state = GovernanceGate(tmp_path, FakeGit()).verify_repository(request)

    assert state.clean is True
    assert state.local_head == FULL_HEAD
    assert state.remote_head == FULL_HEAD


def test_repository_gate_rejects_remote_drift(tmp_path: Path) -> None:
    request = DispatchRequest.model_validate(valid_request())
    gate = GovernanceGate(tmp_path, FakeGit(remote_head="b" * 40))

    with pytest.raises(GovernanceError, match="remote HEAD drift"):
        gate.verify_repository(request)


def test_repository_gate_rejects_dirty_worktree(tmp_path: Path) -> None:
    request = DispatchRequest.model_validate(valid_request())
    gate = GovernanceGate(tmp_path, FakeGit(status=" M README.md"))

    with pytest.raises(GovernanceError, match="not clean"):
        gate.verify_repository(request)


def test_plan_gate_rejects_workspace_write() -> None:
    plan = DispatchPlan(
        summary="Attempt mutation",
        codex_prompt="Change a tracked source file in the repository.",
        requires_workspace_write=True,
    )

    with pytest.raises(GovernanceError, match="forbidden workspace mutation"):
        GovernanceGate.verify_plan(plan)
