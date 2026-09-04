from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.capability_router import CapabilityRouter
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.contracts import DispatchRequest
from palwakf_orchestrator.engineering_os_contracts import CreateEngineeringTaskRequest
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.execution_run_adapter import ExecutionRunAdapter
from palwakf_orchestrator.execution_run_contracts import CreateExecutionRunRequest
from palwakf_orchestrator.mcp_server import create_mcp_server
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    OperatorTaskStatus,
    TaskAuthorizationRequest,
    TaskCapabilityRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.provider_contracts import (
    CODEX_ROLE_AUTHORITIES,
    ProviderMode,
    RoleAuthority,
)

BEFORE = "a" * 40
AFTER = "b" * 40
REPO = "firasfanon/palwakf_workspace_manager"
BRANCH = "task/WM-CONTROL-PLANE-MEGA-BATCH-V1"
AUTHORIZED_FILE = "orchestrator/src/palwakf_orchestrator/operator_service.py"


class AcceptingVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def verify(self, branch: str, expected_head: str) -> str:
        self.calls.append((branch, expected_head))
        if branch != BRANCH or expected_head not in {BEFORE, AFTER}:
            raise GovernanceError("HEAD drift")
        return expected_head


class FakeProviderOrchestrator:
    async def dispatch(self, request: DispatchRequest) -> object:
        after = AFTER if request.boundaries.workspace_write else BEFORE
        return SimpleNamespace(
            executor_thread_id=f"{request.executor_provider_id}-thread-mb00",
            execution_receipt=f"{request.executor_provider_id}-receipt-mb00",
            repository_state=SimpleNamespace(local_head=BEFORE),
            result_repository_state=SimpleNamespace(local_head=after),
            tool_outputs=[
                {
                    "command_summary": "python -m pytest orchestrator",
                    "exit_code": 0,
                }
            ],
            executor_id=request.executor_provider_id,
        )


class RelayOperatorService(OperatorService):
    changed_files = [AUTHORIZED_FILE]

    def _changed_files(self, before_head: str, after_head: str) -> list[str]:
        return [] if before_head == after_head else list(self.changed_files)


def task_request(
    *,
    provider: str = "codex",
    mode: ProviderMode = ProviderMode.code_review,
    sandbox: str = "read-only",
    scope: list[str] | None = None,
    trial: bool = True,
) -> CreateOperatorTaskRequest:
    constraints = ["NO_SCOPE_EXPANSION", "NO_PRODUCTION", "NO_DATABASE_MUTATION"]
    if trial:
        constraints.append("PROVIDER_CERTIFICATION_TRIAL")
    return CreateOperatorTaskRequest.model_validate(
        {
            "task_id": "MB00_PROVIDER_RUNTIME_TEST",
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "repository": REPO,
            "branch": BRANCH,
            "expected_head": BEFORE,
            "authority_reference": "AUTHORITY://MB00/PROVIDER_RUNTIME_TEST",
            "prompt": "Execute the bounded governed engineering-provider task and return evidence.",
            "constraints": constraints,
            "approval_policy": "on-request",
            "sandbox": sandbox,
            "max_turns": 4,
            "timeout_seconds": 300,
            "idempotency_key": (
                f"mb00.provider.{provider}.{mode.value}.{sandbox}".replace("_", "-")
            ),
            "automatic_failure_code": None,
            "manual_fallback_selected": False,
            "requires_explicit_authorization": True,
            "scope_patterns": scope or [],
            "relay_provider_id": provider,
            "provider_mode": mode,
        }
    )


def tool_request(*, mutation_class: str) -> TaskCapabilityRequest:
    return TaskCapabilityRequest.model_validate(
        {
            "task_id": "MB00_PROVIDER_RUNTIME_TEST",
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "required_capability_ids": [],
            "optional_capability_ids": [],
            "task_type": "engineering-provider-runtime",
            "mutation_class": mutation_class,
            "environment": "local",
            "data_classification": "internal",
            "acceptance_requirements": ["tests", "evidence"],
        }
    )


def authorize(service: OperatorService) -> None:
    task = service.get_task("MB00_PROVIDER_RUNTIME_TEST")
    service.authorize_task(
        task.task_id,
        TaskAuthorizationRequest(
            expected_head=BEFORE,
            authority_reference=task.authority_reference,
            acknowledgement="AUTHORIZE_GOVERNED_EXECUTION",
        ),
        principal_id="chatgpt-workspace-controller",
    )


def test_registry_is_pluggable_but_unverified_candidates_remain_quarantined() -> None:
    registry = CapabilityRouter().registry
    snapshot = registry.public_snapshot()

    assert snapshot["registry_version"].endswith("R3_20260824")
    for capability in (
        "governed.patch_relay",
        "governed.code_review",
        "governed.diagnostic_debug",
        "governed.bounded_bug_fix",
        "governed.engineering_proposal",
        "governed.test_regression_analysis",
    ):
        assert snapshot["capabilities"][capability] == [
            "codex",
            "claude-code",
            "kimi",
            "local-agent",
        ]

    assert registry.adapter("codex")["provider_certification_status"] == "TRIAL_AUTHORIZED"
    for provider in ("claude-code", "kimi", "local-agent"):
        metadata = registry.adapter(provider)
        assert metadata["lifecycle"] == "discovered"
        assert metadata["permission_status"] == "untested"
        assert metadata["provider_certification_status"] == "DISCOVERED"


def test_codex_independent_debugging_stays_forbidden_while_governed_debug_is_allowed() -> None:
    assert CODEX_ROLE_AUTHORITIES["independent_debugging"] == RoleAuthority.forbidden
    assert (
        CODEX_ROLE_AUTHORITIES["governed_diagnostic_debug"]
        == RoleAuthority.authorized_governed_scope
    )
    assert CODEX_ROLE_AUTHORITIES["autonomous_development"] == RoleAuthority.suspended


def test_dispatch_contract_allows_task_branch_write_but_rejects_main_write() -> None:
    request = DispatchRequest.model_validate(
        {
            "task_id": "MB00_PROVIDER_RUNTIME_TEST",
            "prompt": "Apply the bounded governed source patch exactly as authorized.",
            "repository": REPO,
            "branch": BRANCH,
            "expected_head": BEFORE,
            "idempotency_key": "mb00.dispatch.contract",
            "executor_provider_id": "codex",
            "provider_mode": "bounded_bug_fix",
            "boundaries": {"workspace_write": True},
        }
    )
    assert request.provider_mode == ProviderMode.bounded_bug_fix

    with pytest.raises(ValidationError):
        DispatchRequest.model_validate(
            {
                "task_id": "MB00_PROVIDER_RUNTIME_TEST",
                "prompt": "Attempt an unauthorized main source mutation.",
                "repository": REPO,
                "branch": "main",
                "expected_head": BEFORE,
                "idempotency_key": "mb00.dispatch.main.reject",
                "executor_provider_id": "codex",
                "provider_mode": "execution_relay",
                "boundaries": {"workspace_write": True},
            }
        )


@pytest.mark.asyncio
async def test_governed_codex_code_review_is_read_only_and_pending_verification(
    tmp_path: Path,
) -> None:
    service = RelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        orchestrator=FakeProviderOrchestrator(),  # type: ignore[arg-type]
        automatic_agents_available=True,
    )
    service.create_task(task_request(), allow_task_branch=True)
    authorize(service)
    plan = service.plan_tools(
        "MB00_PROVIDER_RUNTIME_TEST",
        tool_request(mutation_class="read-only"),
    )

    assert plan.dispatch_blocked is False
    review = next(
        decision
        for decision in plan.decisions
        if decision.capability_id == "governed.code_review"
    )
    assert review.selected_adapter_id == "codex"

    result = await service.dispatch_task("MB00_PROVIDER_RUNTIME_TEST")

    assert result.status == OperatorTaskStatus.pending_verification
    assert result.selected_provider_id == "codex"
    assert result.before_head == BEFORE
    assert result.after_head == BEFORE
    assert result.changed_files == []


@pytest.mark.asyncio
async def test_bounded_bug_fix_allows_exact_scope_write_only(tmp_path: Path) -> None:
    service = RelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        orchestrator=FakeProviderOrchestrator(),  # type: ignore[arg-type]
        automatic_agents_available=True,
    )
    service.create_task(
        task_request(
            mode=ProviderMode.bounded_bug_fix,
            sandbox="workspace-write",
            scope=["orchestrator/src/palwakf_orchestrator/**"],
        ),
        allow_task_branch=True,
    )
    authorize(service)
    plan = service.plan_tools(
        "MB00_PROVIDER_RUNTIME_TEST",
        tool_request(mutation_class="source-write"),
    )

    assert plan.dispatch_blocked is False
    result = await service.dispatch_task("MB00_PROVIDER_RUNTIME_TEST")

    assert result.status == OperatorTaskStatus.pending_verification
    assert result.before_head == BEFORE
    assert result.after_head == AFTER
    assert result.changed_files == [AUTHORIZED_FILE]
    assert result.selected_provider_id == "codex"


@pytest.mark.asyncio
async def test_mutating_provider_task_without_scope_fails_closed(tmp_path: Path) -> None:
    service = RelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        orchestrator=FakeProviderOrchestrator(),  # type: ignore[arg-type]
        automatic_agents_available=True,
    )
    service.create_task(
        task_request(
            mode=ProviderMode.bounded_bug_fix,
            sandbox="workspace-write",
            scope=[],
        ),
        allow_task_branch=True,
    )
    authorize(service)
    service.plan_tools(
        "MB00_PROVIDER_RUNTIME_TEST",
        tool_request(mutation_class="source-write"),
    )

    with pytest.raises(
        GovernanceError,
        match="MUTATING_PROVIDER_TASK_REQUIRES_NONEMPTY_SCOPE",
    ):
        await service.dispatch_task("MB00_PROVIDER_RUNTIME_TEST")


@pytest.mark.asyncio
async def test_read_only_provider_mode_cannot_receive_workspace_write(
    tmp_path: Path,
) -> None:
    service = RelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        orchestrator=FakeProviderOrchestrator(),  # type: ignore[arg-type]
        automatic_agents_available=True,
    )
    service.create_task(
        task_request(
            mode=ProviderMode.code_review,
            sandbox="workspace-write",
            scope=["orchestrator/**"],
        ),
        allow_task_branch=True,
    )
    authorize(service)
    service.plan_tools(
        "MB00_PROVIDER_RUNTIME_TEST",
        tool_request(mutation_class="source-write"),
    )

    with pytest.raises(
        GovernanceError,
        match="READ_ONLY_PROVIDER_MODE_REQUIRES_READ_ONLY_SANDBOX",
    ):
        await service.dispatch_task("MB00_PROVIDER_RUNTIME_TEST")


def test_codex_trial_requires_explicit_trial_authority(tmp_path: Path) -> None:
    service = RelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        automatic_agents_available=True,
    )
    service.create_task(task_request(trial=False), allow_task_branch=True)
    authorize(service)
    plan = service.plan_tools(
        "MB00_PROVIDER_RUNTIME_TEST",
        tool_request(mutation_class="read-only"),
    )
    assert plan.dispatch_blocked is True
    assert "PROVIDER_CERTIFICATION_REQUIRED:codex" in plan.blockers


def test_discovered_explicit_provider_is_not_silently_substituted(tmp_path: Path) -> None:
    service = RelayOperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        automatic_agents_available=True,
    )
    service.create_task(
        task_request(provider="claude-code"),
        allow_task_branch=True,
    )
    authorize(service)
    plan = service.plan_tools(
        "MB00_PROVIDER_RUNTIME_TEST",
        tool_request(mutation_class="read-only"),
    )
    assert plan.dispatch_blocked is True
    assert "REQUESTED_PROVIDER_NOT_ELIGIBLE:claude-code" in plan.blockers


def parent_request() -> CreateEngineeringTaskRequest:
    return CreateEngineeringTaskRequest.model_validate(
        {
            "task_id": "MB00_PARENT_TASK",
            "project_id": "PALWAKF_WORKSPACE_MANAGER",
            "title": "Governed engineering provider runtime",
            "description": "Prove provider-neutral execution without widening authority.",
            "repository": REPO,
            "base_sha": BEFORE,
            "task_branch": BRANCH,
            "owner_id": "firas",
            "actor_id": "chatgpt",
            "actor_type": "HUMAN",
            "scope_patterns": ["orchestrator/**"],
            "depends_on": [],
            "dependency_mode": "INDEPENDENT",
            "risk_class": "HIGH",
            "mutation_class": "source-write",
            "required_capabilities": ["source.control", "runtime.verification"],
            "required_tests": ["targeted", "regression"],
        }
    )


def run_request(
    *,
    provider: str,
    run_id: str,
    mode: ProviderMode,
    sandbox: str,
) -> CreateExecutionRunRequest:
    return CreateExecutionRunRequest.model_validate(
        {
            "execution_run_id": run_id,
            "authority_reference": f"AUTHORITY://MB00/{run_id}",
            "prompt": "Execute one bounded governed engineering-provider run.",
            "constraints": [
                "NO_SCOPE_EXPANSION",
                "NO_PRODUCTION",
                "NO_DATABASE_MUTATION",
                "PROVIDER_CERTIFICATION_TRIAL",
            ],
            "sandbox": sandbox,
            "max_turns": 4,
            "timeout_seconds": 300,
            "idempotency_key": f"mb00.{run_id.lower()}",
            "relay_provider_id": provider,
            "provider_mode": mode,
            "requires_explicit_authorization": True,
        }
    )


def test_execution_run_adapter_enables_provider_runtime_and_preserves_chatgpt_manual_path(
    tmp_path: Path,
) -> None:
    store = MemoryStateStore()
    engineering = EngineeringOsService(store)
    operator = OperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    adapter = ExecutionRunAdapter(engineering, operator, store)
    engineering.create_task(parent_request())

    codex = adapter.create_governed_run(
        "MB00_PARENT_TASK",
        run_request(
            provider="codex",
            run_id="MB00_CODEX_RUN",
            mode=ProviderMode.bounded_bug_fix,
            sandbox="workspace-write",
        ),
    ).operator_task
    assert codex.relay_provider_id == "codex"
    assert codex.provider_mode == ProviderMode.bounded_bug_fix
    assert codex.automatic_failure_code is None
    assert codex.manual_fallback_selected is False

    chatgpt = adapter.create_governed_run(
        "MB00_PARENT_TASK",
        run_request(
            provider="chatgpt",
            run_id="MB00_CHATGPT_RUN",
            mode=ProviderMode.execution_relay,
            sandbox="workspace-write",
        ),
    ).operator_task
    assert chatgpt.relay_provider_id == "chatgpt"
    assert chatgpt.automatic_failure_code == "AUTOMATIC_EXECUTION_PROVIDER_NOT_AUTHORIZED"
    assert chatgpt.manual_fallback_selected is True


async def test_mcp_exposes_provider_neutral_engineering_surface_when_adapter_is_bound(
    tmp_path: Path,
) -> None:
    settings = Settings(workspace_root=tmp_path)
    store = MemoryStateStore()
    engineering = EngineeringOsService(store)
    operator = OperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        state_store=store,
    )
    adapter = ExecutionRunAdapter(engineering, operator, store)
    connected = ConnectedApplicationService(
        settings,
        operator,
        store,
        authentication_configured=True,
    )
    registry = AuthRegistry.for_testing("mcp-provider-test", "mcp-provider-token")

    server = create_mcp_server(
        connected,
        registry,
        engineering_os=engineering,
        execution_runs=adapter,
    )
    names = {tool.name for tool in await server.list_tools()}

    assert {
        "create_engineering_task",
        "get_engineering_task",
        "dispatch_engineering_run",
        "get_engineering_run_status",
        "continue_engineering_run",
        "cancel_engineering_run",
        "verify_engineering_run_result",
    }.issubset(names)
    assert {
        "dispatch_codex_task",
        "continue_codex_task",
        "get_codex_task_status",
        "cancel_codex_task",
        "verify_codex_result",
    }.issubset(names)
