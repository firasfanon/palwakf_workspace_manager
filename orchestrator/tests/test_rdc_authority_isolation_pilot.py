from datetime import UTC, datetime
from typing import Literal

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.github_execution_channel import (
    GitHubMutationAuthorityV1,
    verify_remote_readback,
)
from palwakf_orchestrator.governance import GitHubRealitySnapshot
from palwakf_orchestrator.operator_contracts import (
    OperatorTaskRecord,
    PermissionStatus,
    ToolPlanResponse,
    ToolSelectionDecision,
)
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.rdc_execution_channel import (
    RdcActionClass,
    RdcExecutionChannelContractV1,
    RdcPreflightDecision,
    RdcPreflightRequestV1,
    RdcRepositoryRealityV1,
    RdcRuntimeIdentityV1,
    RdcTaskBindingV1,
    RdcToolConfigSnapshotV1,
    evaluate_rdc_preflight,
)
from palwakf_orchestrator.rdc_session_resume import (
    RDC_ADAPTER_ID,
    RDC_CAPABILITY_ID,
    RdcSessionBootstrapProofV1,
    RdcSessionResumeStore,
)

TASK = "PREL5-066"
PROJECT = "PALWAKF_WORKSPACE_MANAGER"
OTHER_PROJECT = "PALWAKF_MIND_ASSISTANT"
REPOSITORY = "firasfanon/palwakf_workspace_manager"
OTHER_REPOSITORY = "firasfanon/palwakf_mind_assistant"
BRANCH = "task/PREL5-ONE-GOVERNED-DEVELOPMENT-BATCH-V1"
HEAD = "f236ecb4e19c536b6c3353fcd736d86b939e75e1"
AUTHORITY = "TASK_CONTRACT:PREL5-066"
LOCAL_PATH = (
    r"C:\Users\DELL\StudioProjects\_PALWAKF_LOCAL_WORKTREES\palwakf_workspace_manager\PREL5-064"
)
SCOPE = ("orchestrator/tests/test_rdc_authority_isolation_pilot.py",)


def config() -> RdcToolConfigSnapshotV1:
    return RdcToolConfigSnapshotV1(
        app_version="0.2.51",
        default_shell="powershell.exe",
        allowed_directories=(),
        blocked_commands=(),
        telemetry_enabled=True,
    )


def request(
    *,
    binding_project: str = PROJECT,
    binding_repository: str = REPOSITORY,
    reality_project: str = PROJECT,
    reality_repository: str = REPOSITORY,
    mutation_class: Literal["read-only", "source-write"] = "source-write",
) -> RdcPreflightRequestV1:
    cfg = config()
    contract = RdcExecutionChannelContractV1(
        expected_device_id="aa4e60a9-d391-4267-a41b-845151cf8b90",
        expected_device_name="DESKTOP-S5A0JSB",
        expected_local_user="DELL",
        expected_tool_config_sha256=cfg.fingerprint_sha256,
        allowed_actions=(RdcActionClass.filesystem_write, RdcActionClass.git_write),
    )
    runtime = RdcRuntimeIdentityV1(
        device_id="aa4e60a9-d391-4267-a41b-845151cf8b90",
        device_name="DESKTOP-S5A0JSB",
        device_status="online",
        local_user="DELL",
        user_profile=r"C:\Users\DELL",
        tool_config=cfg,
    )
    binding = RdcTaskBindingV1(
        task_id=TASK,
        project_id=binding_project,
        repository=binding_repository,
        local_repository_path=LOCAL_PATH,
        branch=BRANCH,
        expected_head=HEAD,
        authority_reference=AUTHORITY,
        mutation_class=mutation_class,
        scope_patterns=SCOPE,
    )
    reality = RdcRepositoryRealityV1(
        project_id=reality_project,
        repository=reality_repository,
        local_repository_path=LOCAL_PATH,
        branch=BRANCH,
        local_head=HEAD,
        remote_head=HEAD,
        origin=f"https://github.com/{reality_repository}.git",
        worktree_clean=True,
    )
    return RdcPreflightRequestV1(
        contract=contract,
        runtime=runtime,
        binding=binding,
        reality=reality,
        requested_action=RdcActionClass.filesystem_write,
        requested_paths=SCOPE,
    )


def task() -> OperatorTaskRecord:
    now = datetime.now(UTC)
    return OperatorTaskRecord(
        task_id=TASK,
        project_id=PROJECT,
        repository=REPOSITORY,
        branch=BRANCH,
        expected_head=HEAD,
        authority_reference=AUTHORITY,
        prompt="Run PREL5-066 authority-isolation pilot.",
        constraints=["NO_MAIN_MERGE", "NO_PRODUCTION"],
        approval_policy="on-request",
        sandbox="workspace-write",
        max_turns=1,
        timeout_seconds=60,
        idempotency_key="prel5-066-authority-isolation",
        requires_explicit_authorization=True,
        scope_patterns=list(SCOPE),
        relay_provider_id="chatgpt",
        authorized_at=now,
        authorized_by="human-authority",
        created_at=now,
        updated_at=now,
        last_event="TASK_AUTHORIZED",
    )


def plan() -> ToolPlanResponse:
    return ToolPlanResponse(
        task_id=TASK,
        project_id=PROJECT,
        decisions=[
            ToolSelectionDecision(
                capability_id=RDC_CAPABILITY_ID,
                selected_adapter_id=RDC_ADAPTER_ID,
                fallback_adapter_id=None,
                selected_reason="PREL5-066 governed RDC pilot",
                excluded_adapters_with_reason=[],
                permission_status=PermissionStatus.approval_required,
                approval_required=True,
                invocation_order=1,
                evidence_contract=["rdc_preflight_receipt", "postflight_remote_readback"],
                decision_timestamp=datetime.now(UTC),
                registry_version="PREL5-066",
                blocked=False,
                substituted=False,
            )
        ],
        dispatch_blocked=False,
        blockers=[],
    )


def bootstrap() -> RdcSessionBootstrapProofV1:
    return RdcSessionBootstrapProofV1(
        project_id=PROJECT,
        task_id=TASK,
        current_head=HEAD,
        todo_boot_rule_ids=("TODO-BOOT-014", "TODO-BOOT-015", "TODO-BOOT-016"),
        latest_handoff_loaded=True,
        fresh_git_readback=True,
        fresh_drive_readback=True,
        live_rdc_readback=True,
    )


def test_authorized_same_project_scope_is_allowed_without_authority_expansion() -> None:
    receipt = evaluate_rdc_preflight(request())

    assert receipt.decision is RdcPreflightDecision.allow
    assert receipt.task_scope_enforced is True
    assert receipt.authority_expansion_allowed is False


def test_cross_project_reality_is_denied() -> None:
    receipt = evaluate_rdc_preflight(request(reality_project=OTHER_PROJECT))

    assert receipt.decision is RdcPreflightDecision.deny
    assert "RDC_PROJECT_SCOPE_MISMATCH" in receipt.blockers


def test_cross_repository_reality_is_denied() -> None:
    receipt = evaluate_rdc_preflight(request(reality_repository=OTHER_REPOSITORY))

    assert receipt.decision is RdcPreflightDecision.deny
    assert "RDC_TARGET_REPOSITORY_MISMATCH" in receipt.blockers


def test_read_only_authority_cannot_use_mutating_rdc_action() -> None:
    receipt = evaluate_rdc_preflight(request(mutation_class="read-only"))

    assert receipt.decision is RdcPreflightDecision.deny
    assert "RDC_MUTATION_EXCEEDS_TASK_AUTHORITY" in receipt.blockers


def test_cross_project_binding_cannot_bypass_workspace_task_authority() -> None:
    workflow = RdcSessionResumeStore(MemoryStateStore())

    with pytest.raises(GovernanceError, match="RDC_SESSION_PROJECT_BINDING_MISMATCH"):
        workflow.start(
            task=task(),
            plan=plan(),
            bootstrap=bootstrap(),
            request=request(
                binding_project=OTHER_PROJECT,
                reality_project=OTHER_PROJECT,
            ),
            evidence=("prel5-066:cross-project-negative",),
        )


def github_authority() -> GitHubMutationAuthorityV1:
    return GitHubMutationAuthorityV1(
        task_id=TASK,
        project_id=PROJECT,
        repository=REPOSITORY,
        branch=BRANCH,
        expected_head=HEAD,
        expected_github_login="firasfanon",
        authority_reference=AUTHORITY,
        mutation_allowed=True,
    )


def snapshot(*, repository: str = REPOSITORY, remote_head: str = HEAD) -> GitHubRealitySnapshot:
    return GitHubRealitySnapshot(
        repository=repository,
        branch=BRANCH,
        local_head=HEAD,
        remote_head=remote_head,
        pull_request_number=None,
        pull_request_head=None,
        pull_request_state="NONE",
        remote_commit_object_verified=True,
    )


def test_exact_postflight_readback_is_required() -> None:
    receipt = verify_remote_readback(snapshot(), authority=github_authority(), expected_sha=HEAD)
    assert receipt.verified is True
    assert receipt.local_sha == receipt.remote_sha == HEAD


def test_cross_repository_or_remote_sha_postflight_fails_closed() -> None:
    with pytest.raises(GovernanceError, match="GITHUB_POSTFLIGHT_REPOSITORY_MISMATCH"):
        verify_remote_readback(
            snapshot(repository=OTHER_REPOSITORY),
            authority=github_authority(),
            expected_sha=HEAD,
        )

    with pytest.raises(GovernanceError, match="GITHUB_POSTFLIGHT_REMOTE_SHA_MISMATCH"):
        verify_remote_readback(
            snapshot(remote_head="1" * 40),
            authority=github_authority(),
            expected_sha=HEAD,
        )
