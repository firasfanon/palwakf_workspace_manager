from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from palwakf_orchestrator.api import _add_execution_run_routes
from palwakf_orchestrator.engineering_os_contracts import CreateEngineeringTaskRequest
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.execution_run_contracts import CreateExecutionRunRequest
from palwakf_orchestrator.external_execution_contracts import (
    ApplyExternalWorkspaceRequest,
    CheckpointExternalWorkspaceRequest,
    ExternalValidationCheck,
    PrepareExternalWorkspaceRequest,
    ValidateExternalWorkspaceRequest,
)
from palwakf_orchestrator.external_execution_workspace import (
    ExternalExecutionWorkspaceService,
)
from palwakf_orchestrator.operator_contracts import TaskAuthorizationRequest
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore

BASE_REPOSITORY = "firasfanon/example-external-project"
PARENT_ID = "WM-EXTERNAL-RUNTIME-TEST"
RUN_ID = "WM_EXTERNAL_RUNTIME_RUN_001"
TASK_BRANCH = "task/WM-EXTERNAL-RUNTIME-TEST"


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _seed_remote(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "runtime@example.invalid")
    _git(source, "config", "user.name", "Runtime Test")
    (source / "lib").mkdir()
    (source / "lib" / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(source, "add", "lib/seed.txt")
    _git(source, "commit", "-m", "seed")
    base = _git(source, "rev-parse", "HEAD").lower()

    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    _git(source, "remote", "add", "origin", str(remote))
    _git(source, "push", "origin", "HEAD:refs/heads/main")
    return remote, base


def _parent_request(base: str) -> CreateEngineeringTaskRequest:
    return CreateEngineeringTaskRequest.model_validate(
        {
            "task_id": PARENT_ID,
            "project_id": "EXTERNAL_PROJECT",
            "title": "External runtime vertical slice",
            "description": "Execute a bounded source change in an isolated external repository.",
            "repository": BASE_REPOSITORY,
            "base_sha": base,
            "task_branch": TASK_BRANCH,
            "owner_id": "firas",
            "actor_id": "firas",
            "actor_type": "HUMAN",
            "scope_patterns": ["lib/**"],
            "depends_on": [],
            "dependency_mode": "INDEPENDENT",
            "risk_class": "HIGH",
            "mutation_class": "source-write",
            "required_capabilities": ["source.control", "runtime.verification"],
            "required_tests": ["GIT_DIFF_CHECK"],
        }
    )


def _run_request() -> CreateExecutionRunRequest:
    return CreateExecutionRunRequest.model_validate(
        {
            "execution_run_id": RUN_ID,
            "authority_reference": "AUTHORITY://EXTERNAL/RUNTIME/TEST",
            "prompt": "Apply one governed external repository source change.",
            "constraints": ["NO_SCOPE_EXPANSION", "NO_PRODUCTION"],
            "sandbox": "workspace-write",
            "max_turns": 4,
            "timeout_seconds": 300,
            "idempotency_key": "external.runtime.test.001",
            "relay_provider_id": "chatgpt",
            "requires_explicit_authorization": True,
        }
    )


def _build(
    tmp_path: Path,
) -> tuple[
    Path,
    str,
    EngineeringOsService,
    OperatorService,
    ExecutionRunAdapter,
    ExternalExecutionWorkspaceService,
]:
    remote, base = _seed_remote(tmp_path)
    store = MemoryStateStore()
    engineering = EngineeringOsService(store)
    operator = OperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    adapter = ExecutionRunAdapter(engineering, operator, store)
    engineering.create_task(_parent_request(base))
    view = adapter.create_governed_run(PARENT_ID, _run_request())
    assert view.operator_task.repository == BASE_REPOSITORY

    runtime = ExternalExecutionWorkspaceService(
        engineering,
        adapter,
        operator,
        store,
        workspace_root=tmp_path,
        execution_host_id="test-host",
        remote_url_resolver=lambda _: str(remote),
    )
    return remote, base, engineering, operator, adapter, runtime


def _authorize(operator: OperatorService, base: str) -> None:
    task = operator.get_task(RUN_ID)
    operator.authorize_task(
        RUN_ID,
        TaskAuthorizationRequest(
            expected_head=base,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="test-governance",
    )


def test_external_run_creation_preserves_parent_repository_authority(tmp_path: Path) -> None:
    _, base, _, operator, _, runtime = _build(tmp_path)
    task = operator.get_task(RUN_ID)
    assert task.repository == BASE_REPOSITORY
    assert task.branch == TASK_BRANCH
    assert task.expected_head == base

    status = runtime.status(RUN_ID)
    assert status.repository == BASE_REPOSITORY
    assert status.prepared is False
    assert status.authorized is False


def test_external_workspace_requires_explicit_authorization(tmp_path: Path) -> None:
    _, _, _, _, _, runtime = _build(tmp_path)
    with pytest.raises(
        GovernanceError,
        match="EXTERNAL_EXECUTION_REQUIRES_EXPLICIT_AUTHORIZATION",
    ):
        runtime.prepare(RUN_ID, PrepareExternalWorkspaceRequest())


def test_external_workspace_prepare_apply_validate_checkpoint_round_trip(
    tmp_path: Path,
) -> None:
    remote, base, engineering, operator, _, runtime = _build(tmp_path)
    _authorize(operator, base)

    prepared = runtime.prepare(RUN_ID, PrepareExternalWorkspaceRequest())
    assert prepared.prepared is True
    assert prepared.current_head == base
    assert prepared.changed_files == []
    workspace = Path(prepared.workspace_path or "")
    _git(workspace, "config", "user.email", "runtime@example.invalid")
    _git(workspace, "config", "user.name", "Runtime Test")

    applied = runtime.apply(
        RUN_ID,
        ApplyExternalWorkspaceRequest.model_validate(
            {
                "files": [
                    {
                        "path": "lib/runtime.txt",
                        "preimage_mode": "ABSENT",
                        "postimage_text": "runtime ready\n",
                    }
                ]
            }
        ),
    )
    assert applied.changed_files == ["lib/runtime.txt"]

    validated = runtime.validate(
        RUN_ID,
        ValidateExternalWorkspaceRequest(checks=[ExternalValidationCheck.git_diff_check]),
    )
    assert validated.validation is not None
    assert validated.validation.all_passed is True
    assert validated.validation.validated_paths == ["lib/runtime.txt"]

    checkpointed = runtime.checkpoint(
        RUN_ID,
        CheckpointExternalWorkspaceRequest(
            commit_message="test: external runtime checkpoint",
            evidence=["test:external-runtime"],
        ),
    )
    assert checkpointed.checkpoint_sha is not None
    assert checkpointed.remote_head == checkpointed.checkpoint_sha
    assert checkpointed.changed_files == ["lib/runtime.txt"]
    remote_sha = _git(
        remote,
        "rev-parse",
        f"refs/heads/{TASK_BRANCH}",
    ).lower()
    assert remote_sha == checkpointed.checkpoint_sha

    operator_task = operator.get_task(RUN_ID)
    assert operator_task.status.value == "pending_verification"
    assert operator_task.before_head == base
    assert operator_task.after_head == checkpointed.checkpoint_sha
    assert operator_task.changed_files == ["lib/runtime.txt"]

    parent = engineering.get_task(PARENT_ID)
    assert parent.latest_remote_task_sha == checkpointed.checkpoint_sha
    assert parent.wip_checkpoint_status == "REMOTE_CHECKPOINTED"
    assert parent.status.value == "WIP_REMOTE_CHECKPOINTED"


def test_external_workspace_rejects_out_of_scope_manifest(tmp_path: Path) -> None:
    _, base, _, operator, _, runtime = _build(tmp_path)
    _authorize(operator, base)
    runtime.prepare(RUN_ID, PrepareExternalWorkspaceRequest())

    with pytest.raises(
        GovernanceError,
        match="EXECUTION_RESULT_OUTSIDE_AUTHORIZED_SCOPE",
    ):
        runtime.apply(
            RUN_ID,
            ApplyExternalWorkspaceRequest.model_validate(
                {
                    "files": [
                        {
                            "path": "README.md",
                            "preimage_mode": "ABSENT",
                            "postimage_text": "outside scope\n",
                        }
                    ]
                }
            ),
        )


def test_external_workspace_remote_branch_drift_fails_closed(tmp_path: Path) -> None:
    remote, base, _, operator, _, runtime = _build(tmp_path)
    _authorize(operator, base)

    other = tmp_path / "other"
    _git(tmp_path / "source", "checkout", "-b", TASK_BRANCH)
    (tmp_path / "source" / "lib" / "drift.txt").write_text("drift\n", encoding="utf-8")
    _git(tmp_path / "source", "add", "lib/drift.txt")
    _git(tmp_path / "source", "commit", "-m", "drift")
    drift_sha = _git(tmp_path / "source", "rev-parse", "HEAD").lower()
    _git(tmp_path / "source", "push", "origin", f"HEAD:refs/heads/{TASK_BRANCH}")
    assert drift_sha != base
    assert remote.is_dir()
    assert not other.exists()

    with pytest.raises(GovernanceError, match="EXTERNAL_REMOTE_TASK_BRANCH_DRIFT"):
        runtime.prepare(RUN_ID, PrepareExternalWorkspaceRequest())


def test_external_workspace_http_surface_is_run_scoped(tmp_path: Path) -> None:
    _, base, _, operator, adapter, runtime = _build(tmp_path)
    _authorize(operator, base)

    app = FastAPI()
    _add_execution_run_routes(app, adapter, runtime)
    api = TestClient(app)

    initial = api.get(f"/v1/execution-runs/{RUN_ID}/workspace")
    assert initial.status_code == 200
    assert initial.json()["lifecycle"] == "UNPREPARED"

    prepared = api.post(
        f"/v1/execution-runs/{RUN_ID}/workspace/prepare",
        json={"recreate": False},
    )
    assert prepared.status_code == 200
    payload = prepared.json()
    assert payload["prepared"] is True
    assert payload["repository"] == BASE_REPOSITORY
    assert payload["expected_head"] == base
