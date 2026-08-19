from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from palwakf_orchestrator.api import _add_execution_run_routes, _add_legacy_routes
from palwakf_orchestrator.engineering_os_contracts import CreateEngineeringTaskRequest
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.execution_run_contracts import CreateExecutionRunRequest
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    ManualAcknowledgementRequest,
    ManualDispatchMarkRequest,
    ManualDispatchPackage,
    ManualResultRequest,
    TaskAuthorizationRequest,
    VerificationRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore

BASE = "a" * 40
AFTER = "b" * 40
REPO = "firasfanon/palwakf_workspace_manager"
PARENT_ID = "WM-PHASE6-ENG-001"
RUN_ID = "WM_PHASE6_RUN_001"
PARENT_BRANCH = "task/WM-GOVERNED-TASK-EXECUTION-VERTICAL-SLICE-PHASE6-V1"


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


class Phase6TestOperatorService(OperatorService):
    git_changed_files = [
        "lib/src/features/engineering_os/presentation/task_board_page.dart",
        "orchestrator/src/palwakf_orchestrator/api.py",
    ]

    def _changed_files(self, before_head: str, after_head: str) -> list[str]:
        return list(self.git_changed_files)


def parent_request() -> CreateEngineeringTaskRequest:
    return CreateEngineeringTaskRequest.model_validate(
        {
            "task_id": PARENT_ID,
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "title": "Governed task execution vertical slice",
            "description": "Own real execution runs beneath one engineering task.",
            "repository": REPO,
            "base_sha": BASE,
            "task_branch": PARENT_BRANCH,
            "owner_id": "firas",
            "actor_id": "firas",
            "actor_type": "HUMAN",
            "scope_patterns": ["lib/**", "orchestrator/**", "test/**"],
            "depends_on": [],
            "dependency_mode": "INDEPENDENT",
            "risk_class": "HIGH",
            "mutation_class": "source-write",
            "required_capabilities": ["source.control", "runtime.verification"],
            "required_tests": ["targeted", "regression"],
        }
    )


def run_request(**overrides: object) -> CreateExecutionRunRequest:
    data: dict[str, object] = {
        "execution_run_id": "WM_PHASE6_RUN_001",
        "authority_reference": "AUTHORITY://PHASE6/GOVERNED_EXECUTION",
        "prompt": "Apply one bounded source change under the parent engineering task authority.",
        "constraints": ["NO_SCOPE_EXPANSION", "NO_PRODUCTION", "NO_DATABASE_MUTATION"],
        "sandbox": "workspace-write",
        "max_turns": 6,
        "timeout_seconds": 1800,
        "idempotency_key": "phase6.run.001",
        "relay_provider_id": "chatgpt",
        "requires_explicit_authorization": True,
    }
    data.update(overrides)
    return CreateExecutionRunRequest.model_validate(data)


def build() -> tuple[EngineeringOsService, OperatorService, ExecutionRunAdapter]:
    store = MemoryStateStore()
    engineering = EngineeringOsService(store)
    operator = Phase6TestOperatorService(
        Path.cwd(),
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    adapter = ExecutionRunAdapter(engineering, operator, store)
    engineering.create_task(parent_request())
    return engineering, operator, adapter


def test_phase6_real_execution_run_inherits_parent_authority_and_relay_provider() -> None:
    engineering, operator, adapter = build()

    view = adapter.create_governed_run(PARENT_ID, run_request())
    task = view.operator_task

    assert view.parent_task.task_id == PARENT_ID
    assert task.project_id == "PALWAKF_WORKSPACE_MANAGER"
    assert task.repository == REPO
    assert task.branch == PARENT_BRANCH
    assert task.expected_head == BASE
    assert task.scope_patterns == ["lib/**", "orchestrator/**", "test/**"]
    assert task.relay_provider_id == "chatgpt"
    assert task.manual_fallback_selected is True
    assert task.automatic_failure_code == "AUTOMATIC_EXECUTION_PROVIDER_NOT_AUTHORIZED"
    assert task.requires_explicit_authorization is True
    assert view.rollup.signal.value == "PENDING"
    assert view.rollup.automatic_parent_transition is False
    assert engineering.get_task(PARENT_ID).status.value == "READY"

    with pytest.raises(GovernanceError, match="explicit task authorization"):
        operator.generate_manual_package(task.task_id)

    operator.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=BASE,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="phase6-governance",
    )
    package = operator.generate_manual_package(task.task_id)
    assert package.relay_provider_id == "chatgpt"
    assert "scope_patterns" not in ManualDispatchPackage.model_fields
    assert any(
        value.startswith("AUTHORIZED_SOURCE_SCOPE=")
        and "lib/**" in value
        and "orchestrator/**" in value
        and "test/**" in value
        for value in package.constraints
    )

    operator.mark_manual_dispatched(
        task.task_id,
        ManualDispatchMarkRequest(package_receipt=package.package_receipt),
    )
    operator.record_manual_ack(
        task.task_id,
        ManualAcknowledgementRequest(
            package_receipt=package.package_receipt,
            thread_reference="chatgpt-thread-phase6",
        ),
    )
    imported = operator.import_manual_result(
        task.task_id,
        ManualResultRequest(
            package_receipt=package.package_receipt,
            thread_reference="chatgpt-thread-phase6",
            before_head=BASE,
            after_head=AFTER,
            commit_sha=AFTER,
            result_summary="Bounded governed source change completed.",
            changed_files=[
                "lib/src/features/engineering_os/presentation/task_board_page.dart",
                "orchestrator/src/palwakf_orchestrator/api.py",
            ],
            tests=["flutter test:pass", "pytest:pass"],
            evidence=["phase6:execution-result"],
        ),
    )
    assert imported.status.value == "pending_verification"

    operator.verify_task(
        task.task_id,
        VerificationRequest(
            verification_receipt="phase6-independent-verification",
            ci_status="success",
            verified_head=AFTER,
        ),
    )
    verified = adapter.get_operational_view(task.task_id)
    assert verified.rollup.signal.value == "VERIFIED_RUN_AVAILABLE"
    assert [value.value for value in verified.rollup.allowed_explicit_parent_targets] == [
        "READY_FOR_REVIEW"
    ]
    assert verified.rollup.automatic_parent_transition is False
    assert engineering.get_task(PARENT_ID).status.value == "READY"


def test_phase6_scope_is_enforced_fail_closed() -> None:
    _, operator, adapter = build()
    view = adapter.create_governed_run(PARENT_ID, run_request())
    task = view.operator_task

    operator.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=BASE,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="phase6-governance",
    )
    package = operator.generate_manual_package(task.task_id)
    operator.mark_manual_dispatched(
        task.task_id,
        ManualDispatchMarkRequest(package_receipt=package.package_receipt),
    )
    operator.record_manual_ack(
        task.task_id,
        ManualAcknowledgementRequest(
            package_receipt=package.package_receipt,
            thread_reference="chatgpt-thread-phase6",
        ),
    )

    operator.git_changed_files = ["README.md"]
    with pytest.raises(GovernanceError, match="EXECUTION_RESULT_OUTSIDE_AUTHORIZED_SCOPE"):
        operator.import_manual_result(
            task.task_id,
            ManualResultRequest(
                package_receipt=package.package_receipt,
                thread_reference="chatgpt-thread-phase6",
                before_head=BASE,
                after_head=AFTER,
                commit_sha=AFTER,
                result_summary="Out of scope result.",
                changed_files=["README.md"],
                tests=[],
                evidence=[],
            ),
        )


def test_phase6_missing_tool_trace_is_governed_409_not_internal_500() -> None:
    _, operator, adapter = build()
    adapter.create_governed_run(PARENT_ID, run_request())

    app = FastAPI()
    _add_legacy_routes(app, operator, object())
    api = TestClient(app)

    decisions = api.get(f"/v1/tasks/{RUN_ID}/tool-decisions")
    assert decisions.status_code == 409
    assert decisions.json()["detail"] == "tool plan has not been persisted"

    reconciliation = api.get(f"/v1/tasks/{RUN_ID}/tool-reconciliation")
    assert reconciliation.status_code == 409
    assert reconciliation.json()["detail"] == "tool plan has not been persisted"

    invocations = api.get(f"/v1/tasks/{RUN_ID}/tool-invocations")
    assert invocations.status_code == 200
    assert invocations.json() == []


def test_phase6_secret_guard_distinguishes_task_branch_from_real_sk_secret() -> None:
    OperatorService._assert_secret_free({"branch": PARENT_BRANCH})

    with pytest.raises(GovernanceError, match="secret-like"):
        OperatorService._assert_secret_free({"value": "sk-" + ("a" * 24)})


def test_phase6_does_not_widen_legacy_operator_branch_authority() -> None:
    _, operator, _ = build()
    request = CreateOperatorTaskRequest.model_validate(
        {
            "task_id": "WM_PHASE6_DIRECT_TASK_BRANCH_REJECTED",
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "repository": REPO,
            "branch": PARENT_BRANCH,
            "expected_head": BASE,
            "authority_reference": "AUTHORITY://PHASE6/DIRECT_BRANCH_REJECT",
            "prompt": "Attempt direct task-branch creation outside the governed adapter.",
            "constraints": ["NO_SCOPE_EXPANSION"],
            "approval_policy": "never",
            "sandbox": "read-only",
            "max_turns": 2,
            "timeout_seconds": 120,
            "idempotency_key": "phase6.direct.branch.reject",
        }
    )

    with pytest.raises(GovernanceError, match="TASK_BRANCH_REQUIRES_ENGINEERING_RUN_ADAPTER"):
        operator.create_task(request)


def test_phase6_execution_context_http_surface_is_real_and_task_scoped() -> None:
    _, _, adapter = build()
    app = FastAPI()
    _add_execution_run_routes(app, adapter)
    api = TestClient(app)

    created = api.post(
        f"/v1/engineering-os/tasks/{PARENT_ID}/runs",
        json=run_request().model_dump(mode="json"),
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["parent_task"]["task_id"] == PARENT_ID
    assert payload["operator_task"]["branch"] == PARENT_BRANCH
    assert payload["operator_task"]["relay_provider_id"] == "chatgpt"
    assert payload["rollup"]["signal"] == "PENDING"

    context = api.get(f"/v1/engineering-os/tasks/{PARENT_ID}/execution-context")
    assert context.status_code == 200
    assert context.json()["parent_task"]["task_id"] == PARENT_ID
    assert [run["execution_run_id"] for run in context.json()["runs"]] == ["WM_PHASE6_RUN_001"]

    direct = api.get("/v1/execution-runs/WM_PHASE6_RUN_001")
    assert direct.status_code == 200
    assert direct.json()["legacy_operator_task_id"] == "WM_PHASE6_RUN_001"


def test_phase6_api_cannot_disable_explicit_authorization() -> None:
    _, _, adapter = build()
    app = FastAPI()
    _add_execution_run_routes(app, adapter)
    api = TestClient(app)

    payload = run_request().model_dump(mode="json")
    payload["requires_explicit_authorization"] = False
    response = api.post(
        f"/v1/engineering-os/tasks/{PARENT_ID}/runs",
        json=payload,
    )

    assert response.status_code == 422
    assert adapter.execution_context(PARENT_ID).runs == []


@pytest.mark.parametrize("terminal_status", ["INTEGRATED", "CANCELLED", "SUPERSEDED"])
def test_phase6_terminal_parent_cannot_spawn_execution_run(terminal_status: str) -> None:
    engineering, _, adapter = build()
    state = engineering.state_store.load()
    tasks = dict(state["engineering_os_tasks_v1"])
    tasks[PARENT_ID] = {**tasks[PARENT_ID], "status": terminal_status}
    state["engineering_os_tasks_v1"] = tasks
    engineering.state_store.save(state)

    with pytest.raises(GovernanceError, match="EXECUTION_RUN_PARENT_TERMINAL"):
        adapter.create_governed_run(PARENT_ID, run_request())


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_phase6_manual_result_reconciles_declared_files_with_real_git_truth(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "phase6@example.invalid")
    _git(repo, "config", "user.name", "Phase6 Test")

    (repo / "lib").mkdir()
    (repo / "lib" / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "lib/seed.txt")
    _git(repo, "commit", "-m", "seed")
    before = _git(repo, "rev-parse", "HEAD")

    store = MemoryStateStore()
    engineering = EngineeringOsService(store)
    parent = parent_request().model_copy(update={"base_sha": before})
    engineering.create_task(parent)
    operator = OperatorService(
        repo,
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    adapter = ExecutionRunAdapter(engineering, operator, store)

    view = adapter.create_governed_run(
        PARENT_ID,
        run_request(
            execution_run_id="WM_PHASE6_GIT_TRUTH_RUN",
            idempotency_key="phase6.git.truth.001",
        ),
    )
    task = view.operator_task
    operator.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=before,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="phase6-governance",
    )
    package = operator.generate_manual_package(task.task_id)
    operator.mark_manual_dispatched(
        task.task_id,
        ManualDispatchMarkRequest(package_receipt=package.package_receipt),
    )
    operator.record_manual_ack(
        task.task_id,
        ManualAcknowledgementRequest(
            package_receipt=package.package_receipt,
            thread_reference="chatgpt-thread-git-truth",
        ),
    )

    (repo / "lib" / "actual.txt").write_text("actual\n", encoding="utf-8")
    _git(repo, "add", "lib/actual.txt")
    _git(repo, "commit", "-m", "actual")
    after = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(
        GovernanceError,
        match="MANUAL_RESULT_CHANGED_FILES_MISMATCH_GIT_TRUTH",
    ):
        operator.import_manual_result(
            task.task_id,
            ManualResultRequest(
                package_receipt=package.package_receipt,
                thread_reference="chatgpt-thread-git-truth",
                before_head=before,
                after_head=after,
                commit_sha=after,
                result_summary="Relay claimed a different allowed file.",
                changed_files=["lib/reported.txt"],
                tests=[],
                evidence=[],
            ),
        )

    imported = operator.import_manual_result(
        task.task_id,
        ManualResultRequest(
            package_receipt=package.package_receipt,
            thread_reference="chatgpt-thread-git-truth",
            before_head=before,
            after_head=after,
            commit_sha=after,
            result_summary="Relay report now matches repository truth.",
            changed_files=["lib/actual.txt"],
            tests=[],
            evidence=[],
        ),
    )
    assert imported.changed_files == ["lib/actual.txt"]
    assert imported.status.value == "pending_verification"


def test_phase6_git_diff_unavailable_fails_closed(tmp_path: Path) -> None:
    operator = OperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        state_store=MemoryStateStore(),
    )
    with pytest.raises(GovernanceError, match="GIT_DIFF_CHANGED_FILES_UNAVAILABLE"):
        operator._changed_files(BASE, AFTER)
