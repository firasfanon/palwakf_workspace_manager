from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from palwakf_orchestrator.contracts import DispatchRequest
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.gateways import (
    CODEX_WRITE_DEVELOPER_INSTRUCTIONS,
    CODEX_WRITE_RESULT_SCHEMA,
)
from palwakf_orchestrator.governance import GovernanceGate
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    TaskAuthorizationRequest,
    TaskCapabilityRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.provider_contracts import ProviderMode

REPOSITORY = "firasfanon/palwakf_workspace_manager"
BRANCH = "task/WM-CONTROL-PLANE-MEGA-BATCH-V1"
TASK_ID = "WM_PROVIDER_WRITE_COMPLETION_RUNTIME_TEST"
AUTHORIZED_FILE = "orchestrator/src/palwakf_orchestrator/example_runtime_fix.py"


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


def initialized_repository(tmp_path: Path) -> tuple[Path, str]:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    git(tmp_path, "init", "--bare", str(remote))
    git(tmp_path, "init", "--initial-branch", BRANCH, str(repo))
    git(repo, "config", "user.email", "workspace-runtime-test@example.invalid")
    git(repo, "config", "user.name", "Workspace Runtime Test")
    target = repo / AUTHORIZED_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    git(repo, "add", "--", AUTHORIZED_FILE)
    git(repo, "commit", "-m", "seed")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", BRANCH)
    return repo, git(repo, "rev-parse", "HEAD")


def write_request(head: str, *, scope: list[str] | None = None) -> DispatchRequest:
    return DispatchRequest.model_validate(
        {
            "task_id": TASK_ID,
            "prompt": "Apply one bounded provider runtime test change inside the authorized scope.",
            "repository": REPOSITORY,
            "branch": BRANCH,
            "expected_head": head,
            "idempotency_key": "provider-write-completion-runtime-test",
            "executor_provider_id": "codex",
            "provider_mode": "bounded_bug_fix",
            "source_scope_patterns": scope or ["orchestrator/src/palwakf_orchestrator/**"],
            "boundaries": {"workspace_write": True},
        }
    )


def test_governance_gate_commits_pushes_and_reads_back_exact_provider_worktree(
    tmp_path: Path,
) -> None:
    repo, head = initialized_repository(tmp_path)
    request = write_request(head)
    gate = GovernanceGate(repo)
    before = gate.verify_repository(request)

    target = repo / AUTHORIZED_FILE
    target.write_text("VALUE = 2\n", encoding="utf-8")

    after = gate.verify_result_repository(request, before)

    assert after.local_head != head
    assert after.local_head == after.remote_head
    assert git(repo, "rev-parse", "HEAD^") == head
    assert git(repo, "diff", "--name-only", head, after.local_head) == AUTHORIZED_FILE
    assert git(repo, "status", "--porcelain") == ""
    remote = git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}")
    assert remote.split(maxsplit=1)[0] == after.local_head


def test_governance_gate_rejects_provider_change_outside_authorized_scope(
    tmp_path: Path,
) -> None:
    repo, head = initialized_repository(tmp_path)
    request = write_request(head, scope=[AUTHORIZED_FILE])
    gate = GovernanceGate(repo)
    before = gate.verify_repository(request)

    (repo / "README.md").write_text("outside scope\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="PROVIDER_RESULT_OUTSIDE_AUTHORIZED_SCOPE"):
        gate.verify_result_repository(request, before)

    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}").startswith(head)


def test_governance_gate_rejects_provider_git_commit_before_workspace_completion(
    tmp_path: Path,
) -> None:
    repo, head = initialized_repository(tmp_path)
    request = write_request(head)
    gate = GovernanceGate(repo)
    before = gate.verify_repository(request)

    target = repo / AUTHORIZED_FILE
    target.write_text("VALUE = 3\n", encoding="utf-8")
    git(repo, "add", "--", AUTHORIZED_FILE)
    git(repo, "commit", "-m", "provider must not commit")

    with pytest.raises(GovernanceError, match="PROVIDER_GIT_HEAD_MUTATION_NOT_ALLOWED"):
        gate.verify_result_repository(request, before)

    remote = git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}")
    assert remote.split(maxsplit=1)[0] == head


def test_codex_write_gateway_hands_off_git_completion_to_workspace() -> None:
    instructions = CODEX_WRITE_DEVELOPER_INSTRUCTIONS.lower()
    properties = CODEX_WRITE_RESULT_SCHEMA["properties"]
    required = CODEX_WRITE_RESULT_SCHEMA["required"]

    assert "do not stage files, commit, push" in instructions
    assert "sovereign workspace completion gate" in instructions
    assert "after_head" not in properties
    assert "commit_sha" not in properties
    assert "after_head" not in required
    assert "commit_sha" not in required


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        assert branch == BRANCH
        return expected_head


class CapturingOrchestrator:
    def __init__(self) -> None:
        self.request: DispatchRequest | None = None

    async def dispatch(self, request: DispatchRequest) -> SimpleNamespace:
        self.request = request
        return SimpleNamespace(
            executor_thread_id="codex-provider-write-test-thread",
            execution_receipt="codex-provider-write-test-receipt",
            repository_state=SimpleNamespace(local_head=request.expected_head),
            result_repository_state=SimpleNamespace(local_head=request.expected_head),
            tool_outputs=[],
            executor_id="codex",
        )


class ScopeRelayOperatorService(OperatorService):
    def _changed_files(self, before_head: str, after_head: str) -> list[str]:
        return []


@pytest.mark.asyncio
async def test_operator_dispatch_propagates_authorized_scope_to_dispatch_contract(
    tmp_path: Path,
) -> None:
    orchestrator = CapturingOrchestrator()
    scope = ["orchestrator/src/palwakf_orchestrator/gateways.py"]
    head = "a" * 40
    service = ScopeRelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        orchestrator=orchestrator,  # type: ignore[arg-type]
        automatic_agents_available=True,
    )
    service.create_task(
        CreateOperatorTaskRequest(
            task_id=TASK_ID,
            project_id="PALWAKF_WORKSPACE_MANAGER",
            repository=REPOSITORY,
            branch=BRANCH,
            expected_head=head,
            authority_reference="AUTHORITY://PROVIDER/WRITE_COMPLETION",
            prompt="Apply one bounded provider runtime source change and return the handoff.",
            constraints=[
                "NO_SCOPE_EXPANSION",
                "NO_PRODUCTION",
                "NO_DATABASE_MUTATION",
                "PROVIDER_CERTIFICATION_TRIAL",
            ],
            approval_policy="on-request",
            sandbox="workspace-write",
            max_turns=4,
            timeout_seconds=300,
            idempotency_key="provider.write.completion.operator",
            requires_explicit_authorization=True,
            scope_patterns=scope,
            relay_provider_id="codex",
            provider_mode=ProviderMode.bounded_bug_fix,
        ),
        allow_task_branch=True,
    )
    service.authorize_task(
        TASK_ID,
        TaskAuthorizationRequest(
            expected_head=head,
            authority_reference="AUTHORITY://PROVIDER/WRITE_COMPLETION",
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="workspace-runtime-test",
    )
    service.plan_tools(
        TASK_ID,
        TaskCapabilityRequest(
            task_id=TASK_ID,
            project_id="PALWAKF_WORKSPACE_MANAGER",
            required_capability_ids=[],
            optional_capability_ids=[],
            task_type="engineering-provider-runtime",
            mutation_class="source-write",
            environment="local",
            data_classification="internal",
            acceptance_requirements=["tests", "evidence"],
        ),
    )

    await service.dispatch_task(TASK_ID)

    assert orchestrator.request is not None
    assert orchestrator.request.source_scope_patterns == scope
