from __future__ import annotations

from typing import Literal

import pytest

from palwakf_orchestrator.capability_router import (
    CapabilityRouter,
    workspace_manager_profile,
)
from palwakf_orchestrator.operator_contracts import TaskCapabilityRequest
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

HEAD = "6adc49bcaff143da63825a7cefeaaa0d1c6a6da1"
REPOSITORY = "firasfanon/palwakf_workspace_manager"
LOCAL_REPO = r"C:\Users\DELL\StudioProjects\palwakf_workspace_manager"
DEVICE_ID = "aa4e60a9-d391-4267-a41b-845151cf8b90"


def tool_config(
    *,
    allowed_directories: tuple[str, ...] = (),
    default_shell: str = "powershell.exe",
) -> RdcToolConfigSnapshotV1:
    return RdcToolConfigSnapshotV1(
        app_version="0.2.51",
        default_shell=default_shell,
        allowed_directories=allowed_directories,
        blocked_commands=("shutdown", "reboot", "runas"),
        telemetry_enabled=True,
    )


def preflight_request(
    *,
    config: RdcToolConfigSnapshotV1 | None = None,
    mutation_class: Literal["read-only", "source-write"] = "source-write",
    action: RdcActionClass = RdcActionClass.filesystem_write,
    requested_paths: tuple[str, ...] = (
        "orchestrator/src/palwakf_orchestrator/rdc_execution_channel.py",
    ),
) -> RdcPreflightRequestV1:
    config = config or tool_config()
    contract = RdcExecutionChannelContractV1(
        expected_device_id=DEVICE_ID,
        expected_device_name="DESKTOP-S5A0JSB",
        expected_local_user="DELL",
        expected_tool_config_sha256=config.fingerprint_sha256,
        allowed_actions=(
            RdcActionClass.filesystem_read,
            RdcActionClass.terminal_read,
            RdcActionClass.git_read,
            RdcActionClass.filesystem_write,
        ),
    )
    binding = RdcTaskBindingV1(
        task_id="PREL5-063",
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository=REPOSITORY,
        local_repository_path=LOCAL_REPO,
        branch="task/PREL5-ONE-GOVERNED-DEVELOPMENT-BATCH-V1",
        expected_head=HEAD,
        authority_reference="MPCE-20260914-010+PREL5-063",
        mutation_class=mutation_class,
        scope_patterns=("orchestrator/**",),
    )
    runtime = RdcRuntimeIdentityV1(
        device_id=DEVICE_ID,
        device_name="DESKTOP-S5A0JSB",
        device_status="online",
        local_user="DELL",
        user_profile=r"C:\Users\DELL",
        tool_config=config,
    )
    reality = RdcRepositoryRealityV1(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository=REPOSITORY,
        local_repository_path=LOCAL_REPO,
        branch=binding.branch,
        local_head=HEAD,
        remote_head=HEAD,
        origin="https://github.com/firasfanon/palwakf_workspace_manager.git",
        worktree_clean=True,
    )
    return RdcPreflightRequestV1(
        contract=contract,
        runtime=runtime,
        binding=binding,
        reality=reality,
        requested_action=action,
        requested_paths=requested_paths,
    )


def test_current_rdc_runtime_passes_under_narrow_task_scope() -> None:
    receipt = evaluate_rdc_preflight(preflight_request())

    assert receipt.decision == RdcPreflightDecision.allow
    assert receipt.blockers == ()
    assert receipt.tool_scope_broader_than_task_scope is True
    assert receipt.task_scope_enforced is True
    assert receipt.authority_expansion_allowed is False


@pytest.mark.parametrize(
    ("runtime_update", "expected_blocker"),
    [
        ({"device_id": "different-device"}, "RDC_DEVICE_ID_MISMATCH"),
        ({"device_name": "OTHER-PC"}, "RDC_DEVICE_NAME_MISMATCH"),
        ({"local_user": "OTHER"}, "RDC_LOCAL_USER_MISMATCH"),
        ({"device_status": "offline"}, "RDC_DEVICE_NOT_ONLINE"),
    ],
)
def test_runtime_identity_mismatch_denies(
    runtime_update: dict[str, str],
    expected_blocker: str,
) -> None:
    request = preflight_request()
    changed_runtime = request.runtime.model_copy(update=runtime_update)
    changed = request.model_copy(update={"runtime": changed_runtime})

    receipt = evaluate_rdc_preflight(changed)

    assert receipt.decision == RdcPreflightDecision.deny
    assert expected_blocker in receipt.blockers


def test_tool_config_fingerprint_drift_denies() -> None:
    request = preflight_request()
    changed_config = request.runtime.tool_config.model_copy(update={"default_shell": "pwsh.exe"})
    changed_runtime = request.runtime.model_copy(update={"tool_config": changed_config})
    changed = request.model_copy(update={"runtime": changed_runtime})

    receipt = evaluate_rdc_preflight(changed)

    assert receipt.decision == RdcPreflightDecision.deny
    assert "RDC_TOOL_CONFIG_MISMATCH" in receipt.blockers


@pytest.mark.parametrize(
    ("field", "value", "expected_blocker"),
    [
        ("project_id", "PALWAKF_MIND_ASSISTANT", "RDC_PROJECT_SCOPE_MISMATCH"),
        ("repository", "firasfanon/other", "RDC_TARGET_REPOSITORY_MISMATCH"),
        ("branch", "task/OTHER-BRANCH", "RDC_TASK_BRANCH_MISMATCH"),
        ("local_head", "1" * 40, "RDC_LOCAL_HEAD_MISMATCH"),
        ("remote_head", "2" * 40, "RDC_REMOTE_HEAD_MISMATCH"),
        ("worktree_clean", False, "RDC_WORKTREE_NOT_CLEAN"),
    ],
)
def test_repository_reality_mismatch_denies(
    field: str,
    value: object,
    expected_blocker: str,
) -> None:
    request = preflight_request()
    changed_reality = request.reality.model_copy(update={field: value})
    changed = request.model_copy(update={"reality": changed_reality})

    receipt = evaluate_rdc_preflight(changed)

    assert receipt.decision == RdcPreflightDecision.deny
    assert expected_blocker in receipt.blockers


def test_repository_path_mismatch_denies() -> None:
    request = preflight_request()
    reality = request.reality.model_copy(
        update={"local_repository_path": r"C:\Users\DELL\StudioProjects\other"}
    )
    receipt = evaluate_rdc_preflight(request.model_copy(update={"reality": reality}))

    assert receipt.decision == RdcPreflightDecision.deny
    assert "RDC_LOCAL_REPOSITORY_PATH_MISMATCH" in receipt.blockers


def test_path_escape_and_out_of_scope_are_denied() -> None:
    escaped = evaluate_rdc_preflight(preflight_request(requested_paths=("../secrets.txt",)))
    outside = evaluate_rdc_preflight(preflight_request(requested_paths=("README.md",)))

    assert "RDC_REQUESTED_PATH_ESCAPES_REPOSITORY" in escaped.blockers
    assert "RDC_REQUESTED_PATH_OUT_OF_SCOPE" in outside.blockers


def test_read_only_task_cannot_request_mutating_action() -> None:
    receipt = evaluate_rdc_preflight(preflight_request(mutation_class="read-only"))

    assert receipt.decision == RdcPreflightDecision.deny
    assert "RDC_MUTATION_EXCEEDS_TASK_AUTHORITY" in receipt.blockers


def test_action_outside_contract_denies() -> None:
    receipt = evaluate_rdc_preflight(preflight_request(action=RdcActionClass.git_write))

    assert receipt.decision == RdcPreflightDecision.deny
    assert "RDC_ACTION_NOT_ALLOWED" in receipt.blockers


def test_configured_tool_roots_must_include_target_repository() -> None:
    config = tool_config(allowed_directories=(r"D:\isolated",))
    receipt = evaluate_rdc_preflight(preflight_request(config=config))

    assert receipt.decision == RdcPreflightDecision.deny
    assert "RDC_TOOL_CONFIG_EXCLUDES_TARGET_REPOSITORY" in receipt.blockers


def test_configured_parent_root_can_bound_target_repository() -> None:
    config = tool_config(allowed_directories=(r"C:\Users\DELL\StudioProjects",))
    receipt = evaluate_rdc_preflight(preflight_request(config=config))

    assert receipt.decision == RdcPreflightDecision.allow
    assert receipt.tool_scope_broader_than_task_scope is False


def test_preflight_receipt_is_deterministic_for_identical_input() -> None:
    request = preflight_request()

    first = evaluate_rdc_preflight(request)
    second = evaluate_rdc_preflight(request)

    assert first.request_sha256 == second.request_sha256
    assert first == second


def test_rdc_adapter_is_explicit_and_not_in_default_workspace_profile() -> None:
    profile = workspace_manager_profile()
    assert "governed.local_execution_channel" not in profile.required_capabilities
    assert "governed.local_execution_channel" not in profile.conditional_capabilities

    request = TaskCapabilityRequest(
        task_id="PREL5-063",
        project_id=profile.project_id,
        required_capability_ids=["governed.local_execution_channel"],
        task_type="rdc-channel-admission",
        mutation_class="source-write",
        environment="local",
        data_classification="internal",
        acceptance_requirements=["rdc_preflight_receipt"],
    )
    plan = CapabilityRouter().plan(request, profile)
    decision = next(
        item for item in plan.decisions if item.capability_id == "governed.local_execution_channel"
    )

    assert decision.selected_adapter_id == "remote-desktop-commander"
    assert decision.approval_required is True
    assert decision.blocked is False
    assert "rdc_preflight_receipt" in decision.evidence_contract
