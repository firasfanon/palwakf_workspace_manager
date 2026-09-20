from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.failure_retry_guard import (
    FailureObservationV1,
    FailureRetryGuardStore,
    KnownFailureFingerprintV1,
    RetryGuardDecisionV1,
    build_state_fingerprint,
)
from palwakf_orchestrator.governance import GitHubRealitySnapshot
from palwakf_orchestrator.rdc_execution_channel import (
    RdcActionClass,
    RdcPreflightDecision,
    RdcPreflightRequestV1,
    evaluate_rdc_preflight,
)

CONNECTOR_403_FINGERPRINT_ID = "GITHUB_CONNECTOR_403_RESOURCE_NOT_ACCESSIBLE_BY_INTEGRATION"
CONNECTOR_403_LESSON_ID = "PALWAKF_REMOTE_DESKTOP_COMMANDER_GITHUB_MUTATION_CHANNEL_V1"
CONNECTOR_403_PREVENTIVE_GATE_ID = "PALWAKF_GITHUB_EXECUTION_CHANNEL_AND_REMOTE_READBACK_GATE_V1"
CONNECTOR_CHANNEL_ID: Literal["github-connector"] = "github-connector"
LOCAL_CHANNEL_ID: Literal["remote-desktop-commander"] = "remote-desktop-commander"
_CANONICAL_403_MESSAGE = "resource not accessible by integration"


class ConnectorMutationPermissionState(StrEnum):
    unknown = "UNKNOWN"
    allowed = "ALLOWED"
    denied_403 = "DENIED_403"


class GitHubExecutionRouteDecision(StrEnum):
    retry_connector = "RETRY_CONNECTOR"
    select_local_rdc = "SELECT_LOCAL_RDC"
    deny = "DENY"


class GitHubConnectorPermissionStateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel_id: Literal["github-connector"] = "github-connector"
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
    connector_identity: str = Field(min_length=1, max_length=200)
    operation: str = Field(min_length=1, max_length=200)
    repository_metadata_push_visible: bool | None = None
    mutation_permission: ConnectorMutationPermissionState

    @property
    def state_fingerprint(self) -> str:
        return build_state_fingerprint(self.model_dump(mode="json"))


class GitHubMutationFailureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel_id: Literal["github-connector"] = "github-connector"
    status_code: int = Field(ge=100, le=599)
    message: str = Field(min_length=1, max_length=1000)
    provider_error_code: str | None = Field(default=None, max_length=200)


class Connector403ClassificationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    matched: bool
    channel_id: Literal["github-connector"] = "github-connector"
    fingerprint_id: str | None
    permission_state_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class GitHubMutationAuthorityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
    project_id: str = Field(min_length=2, max_length=128)
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
    branch: str = Field(pattern=r"^task/[A-Za-z0-9._/-]{3,180}$")
    expected_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    expected_github_login: str = Field(min_length=1, max_length=100)
    authority_reference: str = Field(min_length=8, max_length=2000)
    mutation_allowed: bool


class LocalGitHubRealityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authenticated: bool
    github_login: str = Field(min_length=1, max_length=100)
    repository: str
    origin: str = Field(min_length=1, max_length=1000)
    branch: str
    local_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    remote_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    worktree_clean: bool
    can_pull: bool
    can_push: bool


class GitHubExecutionRouteReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: GitHubExecutionRouteDecision
    selected_channel: Literal["github-connector", "remote-desktop-commander"] | None
    task_id: str
    project_id: str
    connector_failure_fingerprint: str
    connector_permission_state_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    connector_retry_allowed: bool
    retry_decision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    rdc_preflight_request_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    blockers: tuple[str, ...]
    evidence: tuple[str, ...]
    authority_expansion_allowed: Literal[False] = False
    manual_user_relay_required: Literal[False] = False
    main_merge_authorized: Literal[False] = False
    baseline_promotion_authorized: Literal[False] = False
    production_authorized: Literal[False] = False
    database_mutation_authorized: Literal[False] = False


class GitHubRemoteReadbackReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: str
    branch: str
    expected_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    local_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    remote_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    remote_commit_object_verified: Literal[True] = True
    verified: Literal[True] = True


def connector_403_known_failure(
    *,
    source_revision: str,
    authority_reference: str,
    evidence: tuple[str, ...],
    applies_to_projects: tuple[str, ...] = ("PALWAKF_WORKSPACE_MANAGER",),
) -> KnownFailureFingerprintV1:
    return KnownFailureFingerprintV1(
        fingerprint_id=CONNECTOR_403_FINGERPRINT_ID,
        lesson_id=CONNECTOR_403_LESSON_ID,
        preventive_gate_id=CONNECTOR_403_PREVENTIVE_GATE_ID,
        source_revision=source_revision,
        authority_reference=authority_reference,
        evidence=evidence,
        applies_to_projects=applies_to_projects,
    )


def classify_connector_failure(
    failure: GitHubMutationFailureV1,
    permission_state: GitHubConnectorPermissionStateV1,
) -> Connector403ClassificationV1:
    normalized = re.sub(r"\s+", " ", failure.message.strip().casefold())
    matched = (
        failure.channel_id == CONNECTOR_CHANNEL_ID
        and failure.status_code == 403
        and _CANONICAL_403_MESSAGE in normalized
        and permission_state.mutation_permission is ConnectorMutationPermissionState.denied_403
    )
    return Connector403ClassificationV1(
        matched=matched,
        fingerprint_id=CONNECTOR_403_FINGERPRINT_ID if matched else None,
        permission_state_fingerprint=permission_state.state_fingerprint,
    )


def _require_binding(
    guard: FailureRetryGuardStore,
    *,
    project_id: str,
) -> None:
    if not guard.has_fingerprint(CONNECTOR_403_FINGERPRINT_ID, project_id):
        raise GovernanceError("GITHUB_CONNECTOR_403_FAILURE_BINDING_NOT_IMPORTED")


def record_connector_403_failure(
    guard: FailureRetryGuardStore,
    *,
    failure: GitHubMutationFailureV1,
    permission_state: GitHubConnectorPermissionStateV1,
    authority: GitHubMutationAuthorityV1,
    observation_id: str,
    evidence: tuple[str, ...],
) -> FailureObservationV1:
    classification = classify_connector_failure(failure, permission_state)
    if not classification.matched:
        raise GovernanceError("GITHUB_CONNECTOR_FAILURE_NOT_CANONICAL_403")
    if permission_state.repository != authority.repository:
        raise GovernanceError("GITHUB_CONNECTOR_PERMISSION_REPOSITORY_MISMATCH")
    _require_binding(guard, project_id=authority.project_id)
    return guard.record_failure(
        observation_id=observation_id,
        fingerprint_id=CONNECTOR_403_FINGERPRINT_ID,
        project_id=authority.project_id,
        task_id=authority.task_id,
        state_fingerprint=classification.permission_state_fingerprint,
        evidence=evidence,
    )


def evaluate_connector_retry(
    guard: FailureRetryGuardStore,
    *,
    permission_state: GitHubConnectorPermissionStateV1,
    authority: GitHubMutationAuthorityV1,
) -> RetryGuardDecisionV1:
    if permission_state.repository != authority.repository:
        raise GovernanceError("GITHUB_CONNECTOR_PERMISSION_REPOSITORY_MISMATCH")
    _require_binding(guard, project_id=authority.project_id)
    return guard.evaluate_retry(
        fingerprint_id=CONNECTOR_403_FINGERPRINT_ID,
        project_id=authority.project_id,
        task_id=authority.task_id,
        state_fingerprint=permission_state.state_fingerprint,
    )


def _canonical_origin(repository: str) -> str:
    return f"https://github.com/{repository}.git".casefold()


def _local_route_blockers(
    *,
    authority: GitHubMutationAuthorityV1,
    rdc_request: RdcPreflightRequestV1,
    local: LocalGitHubRealityV1,
) -> tuple[tuple[str, ...], str]:
    blockers: list[str] = []
    preflight = evaluate_rdc_preflight(rdc_request)
    if preflight.decision is not RdcPreflightDecision.allow:
        blockers.append("RDC_PREFLIGHT_DENIED")
        blockers.extend(preflight.blockers)

    binding = rdc_request.binding
    if binding.task_id != authority.task_id:
        blockers.append("GITHUB_ROUTE_TASK_BINDING_MISMATCH")
    if binding.project_id != authority.project_id:
        blockers.append("GITHUB_ROUTE_PROJECT_BINDING_MISMATCH")
    if binding.repository != authority.repository:
        blockers.append("GITHUB_ROUTE_REPOSITORY_BINDING_MISMATCH")
    if binding.branch != authority.branch:
        blockers.append("GITHUB_ROUTE_BRANCH_BINDING_MISMATCH")
    if binding.expected_head.lower() != authority.expected_head.lower():
        blockers.append("GITHUB_ROUTE_HEAD_BINDING_MISMATCH")
    if binding.authority_reference != authority.authority_reference:
        blockers.append("GITHUB_ROUTE_AUTHORITY_REFERENCE_MISMATCH")
    if binding.mutation_class != "source-write":
        blockers.append("GITHUB_ROUTE_MUTATION_AUTHORITY_MISSING")
    if rdc_request.requested_action not in {
        RdcActionClass.git_write,
        RdcActionClass.gh_write,
    }:
        blockers.append("GITHUB_ROUTE_LOCAL_ACTION_NOT_GIT_GH_WRITE")

    if not authority.mutation_allowed:
        blockers.append("GITHUB_ROUTE_TASK_MUTATION_NOT_AUTHORIZED")
    if not local.authenticated:
        blockers.append("GITHUB_ROUTE_LOCAL_GH_NOT_AUTHENTICATED")
    if local.github_login != authority.expected_github_login:
        blockers.append("GITHUB_ROUTE_LOCAL_GH_IDENTITY_MISMATCH")
    if local.repository != authority.repository:
        blockers.append("GITHUB_ROUTE_LOCAL_REPOSITORY_MISMATCH")
    if local.origin.casefold() != _canonical_origin(authority.repository):
        blockers.append("GITHUB_ROUTE_LOCAL_ORIGIN_MISMATCH")
    if local.branch != authority.branch:
        blockers.append("GITHUB_ROUTE_LOCAL_BRANCH_MISMATCH")
    if local.local_head.lower() != authority.expected_head.lower():
        blockers.append("GITHUB_ROUTE_LOCAL_HEAD_MISMATCH")
    if local.remote_head.lower() != authority.expected_head.lower():
        blockers.append("GITHUB_ROUTE_REMOTE_HEAD_MISMATCH")
    if not local.worktree_clean:
        blockers.append("GITHUB_ROUTE_WORKTREE_NOT_CLEAN")
    if not local.can_pull:
        blockers.append("GITHUB_ROUTE_LOCAL_GH_PULL_PERMISSION_MISSING")
    if not local.can_push:
        blockers.append("GITHUB_ROUTE_LOCAL_GH_PUSH_PERMISSION_MISSING")
    return tuple(dict.fromkeys(blockers)), preflight.request_sha256


def route_after_connector_403(
    guard: FailureRetryGuardStore,
    *,
    failure: GitHubMutationFailureV1,
    permission_state: GitHubConnectorPermissionStateV1,
    authority: GitHubMutationAuthorityV1,
    observation_id: str,
    failure_evidence: tuple[str, ...],
    rdc_request: RdcPreflightRequestV1,
    local: LocalGitHubRealityV1,
) -> GitHubExecutionRouteReceiptV1:
    classification = classify_connector_failure(failure, permission_state)
    if not classification.matched:
        raise GovernanceError("GITHUB_CONNECTOR_FAILURE_NOT_CANONICAL_403")
    record_connector_403_failure(
        guard,
        failure=failure,
        permission_state=permission_state,
        authority=authority,
        observation_id=observation_id,
        evidence=failure_evidence,
    )
    retry = evaluate_connector_retry(
        guard,
        permission_state=permission_state,
        authority=authority,
    )
    if retry.allowed:
        raise GovernanceError("GITHUB_CONNECTOR_403_RETRY_GUARD_INCONSISTENT")

    blockers, preflight_sha = _local_route_blockers(
        authority=authority,
        rdc_request=rdc_request,
        local=local,
    )
    decision = (
        GitHubExecutionRouteDecision.select_local_rdc
        if not blockers
        else GitHubExecutionRouteDecision.deny
    )
    return GitHubExecutionRouteReceiptV1(
        decision=decision,
        selected_channel=LOCAL_CHANNEL_ID if not blockers else None,
        task_id=authority.task_id,
        project_id=authority.project_id,
        connector_failure_fingerprint=CONNECTOR_403_FINGERPRINT_ID,
        connector_permission_state_fingerprint=permission_state.state_fingerprint,
        connector_retry_allowed=False,
        retry_decision_id=retry.decision_id,
        rdc_preflight_request_sha256=preflight_sha,
        blockers=blockers,
        evidence=(
            f"retry_disposition:{retry.disposition.value}",
            f"permission_state_sha256:{permission_state.state_fingerprint}",
            f"rdc_preflight_sha256:{preflight_sha}",
            f"local_github_login:{local.github_login}",
        ),
    )


def verify_remote_readback(
    snapshot: GitHubRealitySnapshot,
    *,
    authority: GitHubMutationAuthorityV1,
    expected_sha: str,
) -> GitHubRemoteReadbackReceiptV1:
    expected = expected_sha.lower()
    if snapshot.repository != authority.repository:
        raise GovernanceError("GITHUB_POSTFLIGHT_REPOSITORY_MISMATCH")
    if snapshot.branch != authority.branch:
        raise GovernanceError("GITHUB_POSTFLIGHT_BRANCH_MISMATCH")
    if snapshot.local_head.lower() != expected:
        raise GovernanceError("GITHUB_POSTFLIGHT_LOCAL_SHA_MISMATCH")
    if snapshot.remote_head.lower() != expected:
        raise GovernanceError("GITHUB_POSTFLIGHT_REMOTE_SHA_MISMATCH")
    if snapshot.pull_request_head is not None and snapshot.pull_request_head.lower() != expected:
        raise GovernanceError("GITHUB_POSTFLIGHT_PR_SHA_MISMATCH")
    if not snapshot.remote_commit_object_verified:
        raise GovernanceError("GITHUB_POSTFLIGHT_REMOTE_OBJECT_NOT_VERIFIED")
    return GitHubRemoteReadbackReceiptV1(
        repository=snapshot.repository,
        branch=snapshot.branch,
        expected_sha=expected,
        local_sha=snapshot.local_head.lower(),
        remote_sha=snapshot.remote_head.lower(),
    )
