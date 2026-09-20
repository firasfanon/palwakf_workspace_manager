from __future__ import annotations

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.failure_retry_guard import (
    FailureRetryGuardStore,
    RetryDisposition,
)
from palwakf_orchestrator.github_execution_channel import (
    CONNECTOR_403_FINGERPRINT_ID,
    ConnectorMutationPermissionState,
    GitHubConnectorPermissionStateV1,
    GitHubExecutionRouteDecision,
    GitHubMutationAuthorityV1,
    GitHubMutationFailureV1,
    LocalGitHubRealityV1,
    classify_connector_failure,
    connector_403_known_failure,
    evaluate_connector_retry,
    record_connector_403_failure,
    route_after_connector_403,
    verify_remote_readback,
)
from palwakf_orchestrator.governance import GitHubRealitySnapshot
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.rdc_execution_channel import (
    RdcActionClass,
    RdcExecutionChannelContractV1,
    RdcPreflightRequestV1,
    RdcRepositoryRealityV1,
    RdcRuntimeIdentityV1,
    RdcTaskBindingV1,
    RdcToolConfigSnapshotV1,
)

PROJECT = "PALWAKF_WORKSPACE_MANAGER"
REPOSITORY = "firasfanon/palwakf_workspace_manager"
BRANCH = "task/PREL5-ONE-GOVERNED-DEVELOPMENT-BATCH-V1"
HEAD = "55e0cf659449a34d025d39120038cbbf48c56b26"
DEVICE_ID = "aa4e60a9-d391-4267-a41b-845151cf8b90"
LOCAL_REPO = r"C:\worktrees\palwakf_workspace_manager\PREL5-064"
SOURCE = "orchestrator/src/palwakf_orchestrator/github_execution_channel.py"
TEST = "orchestrator/tests/test_github_execution_channel.py"
AUTHORITY = "PALWAKF_ONE_GOVERNED_PRE_L5_DEVELOPMENT_BATCH+PREL5-064"
REVISION = "drive-prel5-064-current"


def guard() -> FailureRetryGuardStore:
    value = FailureRetryGuardStore(MemoryStateStore())
    value.import_registry(
        source_revision=REVISION,
        authority_reference=AUTHORITY,
        records=(
            connector_403_known_failure(
                source_revision=REVISION,
                authority_reference=AUTHORITY,
                evidence=("drive://prel5-064/connector-403",),
            ),
        ),
    )
    return value


def permission_state(
    *,
    mutation_permission: ConnectorMutationPermissionState = (
        ConnectorMutationPermissionState.denied_403
    ),
) -> GitHubConnectorPermissionStateV1:
    return GitHubConnectorPermissionStateV1(
        repository=REPOSITORY,
        connector_identity="chatgpt-github-connector",
        operation="repository-collaborator-permission-read",
        repository_metadata_push_visible=True,
        mutation_permission=mutation_permission,
    )


def failure(
    *,
    status_code: int = 403,
    message: str = "Resource not accessible by integration",
) -> GitHubMutationFailureV1:
    return GitHubMutationFailureV1(
        status_code=status_code,
        message=message,
        provider_error_code="FORBIDDEN",
    )


def authority(
    *,
    task_id: str = "PREL5-064",
    mutation_allowed: bool = True,
) -> GitHubMutationAuthorityV1:
    return GitHubMutationAuthorityV1(
        task_id=task_id,
        project_id=PROJECT,
        repository=REPOSITORY,
        branch=BRANCH,
        expected_head=HEAD,
        expected_github_login="firasfanon",
        authority_reference=AUTHORITY,
        mutation_allowed=mutation_allowed,
    )


def tool_config() -> RdcToolConfigSnapshotV1:
    return RdcToolConfigSnapshotV1(
        app_version="0.2.51",
        default_shell="powershell.exe",
        allowed_directories=(),
        blocked_commands=("shutdown", "reboot", "runas"),
        telemetry_enabled=True,
    )


def rdc_request(
    *,
    task_id: str = "PREL5-064",
    runtime_update: dict[str, object] | None = None,
    reality_update: dict[str, object] | None = None,
) -> RdcPreflightRequestV1:
    config = tool_config()
    contract = RdcExecutionChannelContractV1(
        expected_device_id=DEVICE_ID,
        expected_device_name="DESKTOP-S5A0JSB",
        expected_local_user="DELL",
        expected_tool_config_sha256=config.fingerprint_sha256,
        allowed_actions=(
            RdcActionClass.git_read,
            RdcActionClass.git_write,
            RdcActionClass.gh_read,
            RdcActionClass.gh_write,
        ),
    )
    binding = RdcTaskBindingV1(
        task_id=task_id,
        project_id=PROJECT,
        repository=REPOSITORY,
        local_repository_path=LOCAL_REPO,
        branch=BRANCH,
        expected_head=HEAD,
        authority_reference=AUTHORITY,
        mutation_class="source-write",
        scope_patterns=(SOURCE, TEST),
    )
    runtime = RdcRuntimeIdentityV1(
        device_id=DEVICE_ID,
        device_name="DESKTOP-S5A0JSB",
        device_status="online",
        local_user="DELL",
        user_profile=r"C:\Users\DELL",
        tool_config=config,
    )
    if runtime_update:
        runtime = runtime.model_copy(update=runtime_update)
    reality = RdcRepositoryRealityV1(
        project_id=PROJECT,
        repository=REPOSITORY,
        local_repository_path=LOCAL_REPO,
        branch=BRANCH,
        local_head=HEAD,
        remote_head=HEAD,
        origin=f"https://github.com/{REPOSITORY}.git",
        worktree_clean=True,
    )
    if reality_update:
        reality = reality.model_copy(update=reality_update)
    return RdcPreflightRequestV1(
        contract=contract,
        runtime=runtime,
        binding=binding,
        reality=reality,
        requested_action=RdcActionClass.git_write,
        requested_paths=(SOURCE, TEST),
    )


def local_reality(**updates: object) -> LocalGitHubRealityV1:
    value = LocalGitHubRealityV1(
        authenticated=True,
        github_login="firasfanon",
        repository=REPOSITORY,
        origin=f"https://github.com/{REPOSITORY}.git",
        branch=BRANCH,
        local_head=HEAD,
        remote_head=HEAD,
        worktree_clean=True,
        can_pull=True,
        can_push=True,
    )
    return value.model_copy(update=updates)


def record_current_failure(
    value: FailureRetryGuardStore,
    *,
    auth: GitHubMutationAuthorityV1 | None = None,
    state: GitHubConnectorPermissionStateV1 | None = None,
) -> None:
    record_connector_403_failure(
        value,
        failure=failure(),
        permission_state=state or permission_state(),
        authority=auth or authority(),
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        evidence=("connector://403/resource-not-accessible-by-integration",),
    )


def test_exact_connector_403_is_classified_with_permission_state_fingerprint() -> None:
    state = permission_state()
    result = classify_connector_failure(failure(), state)

    assert result.matched is True
    assert result.fingerprint_id == CONNECTOR_403_FINGERPRINT_ID
    assert result.permission_state_fingerprint == state.state_fingerprint


def test_noncanonical_connector_failure_is_not_misclassified() -> None:
    result = classify_connector_failure(
        failure(status_code=500, message="internal error"),
        permission_state(),
    )

    assert result.matched is False
    assert result.fingerprint_id is None


def test_same_connector_403_same_permission_state_routes_to_authorized_local_channel() -> None:
    value = guard()

    receipt = route_after_connector_403(
        value,
        failure=failure(),
        permission_state=permission_state(),
        authority=authority(),
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        failure_evidence=("connector://403/resource-not-accessible-by-integration",),
        rdc_request=rdc_request(),
        local=local_reality(),
    )

    assert receipt.connector_retry_allowed is False
    assert receipt.decision is GitHubExecutionRouteDecision.select_local_rdc
    assert receipt.selected_channel == "remote-desktop-commander"
    assert receipt.blockers == ()
    assert receipt.manual_user_relay_required is False


def test_task_id_change_does_not_bypass_same_connector_failure_state() -> None:
    value = guard()
    record_current_failure(value, auth=authority(task_id="PREL5-064-A"))

    decision = evaluate_connector_retry(
        value,
        permission_state=permission_state(),
        authority=authority(task_id="PREL5-064-B"),
    )

    assert decision.allowed is False
    assert decision.disposition is RetryDisposition.block_same_failure_same_state


def test_changed_connector_permission_state_can_reopen_connector_retry() -> None:
    value = guard()
    record_current_failure(value)

    changed = permission_state(
        mutation_permission=ConnectorMutationPermissionState.allowed,
    )
    decision = evaluate_connector_retry(
        value,
        permission_state=changed,
        authority=authority(),
    )

    assert decision.allowed is True
    assert decision.disposition is RetryDisposition.allow_state_changed


def test_channel_change_without_task_mutation_authority_denies() -> None:
    value = guard()
    auth = authority(mutation_allowed=False)
    record_current_failure(value, auth=auth)

    receipt = route_after_connector_403(
        value,
        failure=failure(),
        permission_state=permission_state(),
        authority=auth,
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        failure_evidence=("connector://403/resource-not-accessible-by-integration",),
        rdc_request=rdc_request(),
        local=local_reality(),
    )

    assert receipt.decision is GitHubExecutionRouteDecision.deny
    assert receipt.selected_channel is None
    assert "GITHUB_ROUTE_TASK_MUTATION_NOT_AUTHORIZED" in receipt.blockers


@pytest.mark.parametrize(
    ("runtime_update", "local_update", "expected_blocker"),
    [
        ({"device_id": "different-device"}, {}, "RDC_DEVICE_ID_MISMATCH"),
        ({"local_user": "OTHER"}, {}, "RDC_LOCAL_USER_MISMATCH"),
        ({}, {"repository": "firasfanon/other"}, "GITHUB_ROUTE_LOCAL_REPOSITORY_MISMATCH"),
        (
            {},
            {"origin": "https://github.com/firasfanon/other.git"},
            "GITHUB_ROUTE_LOCAL_ORIGIN_MISMATCH",
        ),
        ({}, {"branch": "task/OTHER-BRANCH"}, "GITHUB_ROUTE_LOCAL_BRANCH_MISMATCH"),
        ({}, {"local_head": "1" * 40}, "GITHUB_ROUTE_LOCAL_HEAD_MISMATCH"),
        ({}, {"remote_head": "2" * 40}, "GITHUB_ROUTE_REMOTE_HEAD_MISMATCH"),
        ({}, {"worktree_clean": False}, "GITHUB_ROUTE_WORKTREE_NOT_CLEAN"),
    ],
)
def test_wrong_local_channel_reality_denies(
    runtime_update: dict[str, object],
    local_update: dict[str, object],
    expected_blocker: str,
) -> None:
    value = guard()
    record_current_failure(value)

    receipt = route_after_connector_403(
        value,
        failure=failure(),
        permission_state=permission_state(),
        authority=authority(),
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        failure_evidence=("connector://403/resource-not-accessible-by-integration",),
        rdc_request=rdc_request(runtime_update=runtime_update or None),
        local=local_reality(**local_update),
    )

    assert receipt.decision is GitHubExecutionRouteDecision.deny
    assert expected_blocker in receipt.blockers


def test_wrong_local_github_identity_and_push_permission_deny() -> None:
    value = guard()
    record_current_failure(value)

    identity = route_after_connector_403(
        value,
        failure=failure(),
        permission_state=permission_state(),
        authority=authority(),
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        failure_evidence=("connector://403/resource-not-accessible-by-integration",),
        rdc_request=rdc_request(),
        local=local_reality(github_login="other"),
    )
    permission = route_after_connector_403(
        value,
        failure=failure(),
        permission_state=permission_state(),
        authority=authority(),
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        failure_evidence=("connector://403/resource-not-accessible-by-integration",),
        rdc_request=rdc_request(),
        local=local_reality(can_push=False),
    )

    assert "GITHUB_ROUTE_LOCAL_GH_IDENTITY_MISMATCH" in identity.blockers
    assert "GITHUB_ROUTE_LOCAL_GH_PUSH_PERMISSION_MISSING" in permission.blockers


def test_successful_local_selection_never_implies_higher_authority() -> None:
    value = guard()
    record_current_failure(value)

    receipt = route_after_connector_403(
        value,
        failure=failure(),
        permission_state=permission_state(),
        authority=authority(),
        observation_id="OBS-PREL5-064-CONNECTOR-403",
        failure_evidence=("connector://403/resource-not-accessible-by-integration",),
        rdc_request=rdc_request(),
        local=local_reality(),
    )

    assert receipt.authority_expansion_allowed is False
    assert receipt.main_merge_authorized is False
    assert receipt.baseline_promotion_authorized is False
    assert receipt.production_authorized is False
    assert receipt.database_mutation_authorized is False


def snapshot(
    *,
    repository: str = REPOSITORY,
    branch: str = BRANCH,
    local_head: str = HEAD,
    remote_head: str = HEAD,
    pr_head: str | None = HEAD,
    object_verified: bool = True,
) -> GitHubRealitySnapshot:
    return GitHubRealitySnapshot(
        repository=repository,
        branch=branch,
        local_head=local_head,
        remote_head=remote_head,
        pull_request_number=9 if pr_head else None,
        pull_request_head=pr_head,
        pull_request_state="OPEN" if pr_head else "NONE",
        remote_commit_object_verified=object_verified,
    )


def test_postflight_reuses_github_reality_snapshot_for_exact_sha_verification() -> None:
    receipt = verify_remote_readback(
        snapshot(),
        authority=authority(),
        expected_sha=HEAD,
    )

    assert receipt.verified is True
    assert receipt.local_sha == receipt.remote_sha == HEAD


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (snapshot(repository="firasfanon/other"), "GITHUB_POSTFLIGHT_REPOSITORY_MISMATCH"),
        (snapshot(branch="task/OTHER-BRANCH"), "GITHUB_POSTFLIGHT_BRANCH_MISMATCH"),
        (snapshot(local_head="1" * 40), "GITHUB_POSTFLIGHT_LOCAL_SHA_MISMATCH"),
        (snapshot(remote_head="2" * 40), "GITHUB_POSTFLIGHT_REMOTE_SHA_MISMATCH"),
        (snapshot(pr_head="3" * 40), "GITHUB_POSTFLIGHT_PR_SHA_MISMATCH"),
        (snapshot(object_verified=False), "GITHUB_POSTFLIGHT_REMOTE_OBJECT_NOT_VERIFIED"),
    ],
)
def test_postflight_remote_readback_mismatch_fails_closed(
    value: GitHubRealitySnapshot,
    error: str,
) -> None:
    with pytest.raises(GovernanceError, match=error):
        verify_remote_readback(
            value,
            authority=authority(),
            expected_sha=HEAD,
        )


def test_unimported_connector_failure_binding_fails_closed() -> None:
    value = FailureRetryGuardStore(MemoryStateStore())

    with pytest.raises(
        GovernanceError,
        match="GITHUB_CONNECTOR_403_FAILURE_BINDING_NOT_IMPORTED",
    ):
        evaluate_connector_retry(
            value,
            permission_state=permission_state(),
            authority=authority(),
        )
