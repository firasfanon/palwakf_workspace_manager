from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from palwakf_orchestrator.contracts import DispatchRequest
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.governance import GitHubRealityGate, GovernanceGate

REPOSITORY = "firasfanon/palwakf_workspace_manager"
BRANCH = "task/PREL5-012-GITHUB-REALITY-TEST"
TASK_ID = "PREL5_012_GITHUB_REALITY_RUNTIME_TEST"
TARGET = "orchestrator/src/palwakf_orchestrator/github_reality_probe.py"


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
    git(repo, "config", "user.email", "prel5-012@example.invalid")
    git(repo, "config", "user.name", "PREL5 012 Test")
    target = repo / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    git(repo, "add", "--", TARGET)
    git(repo, "commit", "-m", "seed")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", BRANCH)
    return repo, git(repo, "rev-parse", "HEAD")


def write_request(head: str) -> DispatchRequest:
    return DispatchRequest.model_validate(
        {
            "task_id": TASK_ID,
            "prompt": "Apply one bounded GitHub reality test change inside the authorized scope.",
            "repository": REPOSITORY,
            "branch": BRANCH,
            "expected_head": head,
            "idempotency_key": "prel5-012-github-reality-runtime-test",
            "executor_provider_id": "codex",
            "provider_mode": "bounded_bug_fix",
            "source_scope_patterns": [TARGET],
            "boundaries": {"workspace_write": True},
        }
    )


class NoPullClient:
    def get_json(self, path: str) -> Any:
        assert path.startswith("pulls?state=open&head=")
        return []


class PullSequenceClient:
    def __init__(self, heads: list[str | None]) -> None:
        self._heads = heads
        self.calls = 0

    def get_json(self, path: str) -> Any:
        assert path.startswith("pulls?state=open&head=")
        index = min(self.calls, len(self._heads) - 1)
        self.calls += 1
        head = self._heads[index]
        if head is None:
            return []
        return [{"number": 7, "state": "open", "head": {"sha": head, "ref": BRANCH}}]


class RemoteHeadPullClient:
    def __init__(self, repo: Path) -> None:
        self._repo = repo

    def get_json(self, path: str) -> Any:
        assert path.startswith("pulls?state=open&head=")
        remote = git(self._repo, "ls-remote", "origin", f"refs/heads/{BRANCH}")
        head = remote.split(maxsplit=1)[0]
        return [{"number": 8, "state": "open", "head": {"sha": head, "ref": BRANCH}}]


def test_reality_gate_accepts_no_open_pr_and_verifies_fetched_remote_object(
    tmp_path: Path,
) -> None:
    repo, head = initialized_repository(tmp_path)
    snapshot = GitHubRealityGate(repo, REPOSITORY, NoPullClient()).verify(
        branch=BRANCH,
        expected_local_head=head,
    )

    assert snapshot.local_head == snapshot.remote_head == head
    assert snapshot.pull_request_number is None
    assert snapshot.pull_request_head is None
    assert snapshot.pull_request_state == "NONE"
    assert snapshot.remote_commit_object_verified is True
    assert git(repo, "rev-parse", "FETCH_HEAD") == head


def test_reality_gate_rejects_open_pr_head_drift(tmp_path: Path) -> None:
    repo, head = initialized_repository(tmp_path)
    gate = GitHubRealityGate(repo, REPOSITORY, PullSequenceClient(["b" * 40]))

    with pytest.raises(GovernanceError, match="GITHUB_REALITY_PR_HEAD_MISMATCH"):
        gate.verify(branch=BRANCH, expected_local_head=head)


def test_governed_write_accepts_matching_pr_reality_across_push(tmp_path: Path) -> None:
    repo, head = initialized_repository(tmp_path)
    reality = GitHubRealityGate(repo, REPOSITORY, RemoteHeadPullClient(repo))
    gate = GovernanceGate(repo, github_reality=reality)
    request = write_request(head)
    before = gate.verify_repository(request)
    (repo / TARGET).write_text("VALUE = 2\n", encoding="utf-8")

    after = gate.verify_result_repository(request, before)

    assert after.local_head == after.remote_head
    assert after.local_head != head
    assert git(repo, "status", "--porcelain") == ""
    remote = git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}")
    assert remote.split(maxsplit=1)[0] == after.local_head


def test_pre_push_pr_drift_blocks_remote_push(tmp_path: Path) -> None:
    repo, head = initialized_repository(tmp_path)
    client = PullSequenceClient([head, head, "c" * 40])
    reality = GitHubRealityGate(repo, REPOSITORY, client)
    gate = GovernanceGate(repo, github_reality=reality)
    request = write_request(head)
    before = gate.verify_repository(request)
    (repo / TARGET).write_text("VALUE = 3\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="GITHUB_REALITY_PR_HEAD_MISMATCH"):
        gate.verify_result_repository(request, before)

    remote = git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}")
    assert remote.split(maxsplit=1)[0] == head
    assert git(repo, "rev-parse", "HEAD") != head


def test_post_push_stale_pr_readback_is_detected(tmp_path: Path) -> None:
    repo, head = initialized_repository(tmp_path)
    client = PullSequenceClient([head, head, head, head])
    reality = GitHubRealityGate(repo, REPOSITORY, client)
    gate = GovernanceGate(repo, github_reality=reality)
    request = write_request(head)
    before = gate.verify_repository(request)
    (repo / TARGET).write_text("VALUE = 4\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="GITHUB_REALITY_PR_HEAD_MISMATCH"):
        gate.verify_result_repository(request, before)

    remote = git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}")
    remote_head = remote.split(maxsplit=1)[0]
    assert remote_head != head
    assert git(repo, "rev-parse", "HEAD") == remote_head
