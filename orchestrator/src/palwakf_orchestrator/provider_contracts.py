from __future__ import annotations

from enum import StrEnum
from typing import Final


class RoleAuthority(StrEnum):
    not_authorized = "NOT_AUTHORIZED"
    authorized = "AUTHORIZED"
    authorized_governed_scope = "AUTHORIZED_GOVERNED_SCOPE"
    requires_approval = "REQUIRES_APPROVAL"
    suspended = "SUSPENDED"
    forbidden = "FORBIDDEN"


class ProviderMode(StrEnum):
    execution_relay = "execution_relay"
    code_review = "code_review"
    diagnostic_debug = "diagnostic_debug"
    bounded_bug_fix = "bounded_bug_fix"
    engineering_proposal = "engineering_proposal"
    test_and_regression_analysis = "test_and_regression_analysis"


class ProviderCertificationState(StrEnum):
    discovered = "DISCOVERED"
    capability_probed = "CAPABILITY_PROBED"
    security_boundary_verified = "SECURITY_BOUNDARY_VERIFIED"
    repository_write_verified = "REPOSITORY_WRITE_VERIFIED"
    scope_enforcement_verified = "SCOPE_ENFORCEMENT_VERIFIED"
    test_execution_verified = "TEST_EXECUTION_VERIFIED"
    receipt_evidence_verified = "RECEIPT_EVIDENCE_VERIFIED"
    trial_authorized = "TRIAL_AUTHORIZED"
    approved_provider = "APPROVED_PROVIDER"


PROVIDER_MODE_CAPABILITIES: Final[dict[ProviderMode, str]] = {
    ProviderMode.execution_relay: "governed.patch_relay",
    ProviderMode.code_review: "governed.code_review",
    ProviderMode.diagnostic_debug: "governed.diagnostic_debug",
    ProviderMode.bounded_bug_fix: "governed.bounded_bug_fix",
    ProviderMode.engineering_proposal: "governed.engineering_proposal",
    ProviderMode.test_and_regression_analysis: "governed.test_regression_analysis",
}

GOVERNED_ENGINEERING_CAPABILITIES: Final[frozenset[str]] = frozenset(
    PROVIDER_MODE_CAPABILITIES.values()
)
MUTATING_PROVIDER_MODES: Final[frozenset[ProviderMode]] = frozenset(
    {ProviderMode.execution_relay, ProviderMode.bounded_bug_fix}
)
READ_ONLY_PROVIDER_MODES: Final[frozenset[ProviderMode]] = frozenset(
    set(ProviderMode) - set(MUTATING_PROVIDER_MODES)
)


def capability_for_provider_mode(mode: ProviderMode) -> str:
    return PROVIDER_MODE_CAPABILITIES[mode]


CODEX_ROLE_AUTHORITIES: Final[dict[str, RoleAuthority]] = {
    "autonomous_development": RoleAuthority.suspended,
    "autonomous_decision_making": RoleAuthority.forbidden,
    "independent_debugging": RoleAuthority.forbidden,
    "governed_patch_relay": RoleAuthority.authorized_governed_scope,
    "governed_code_review": RoleAuthority.authorized_governed_scope,
    "governed_diagnostic_debug": RoleAuthority.authorized_governed_scope,
    "governed_bounded_bug_fix": RoleAuthority.authorized_governed_scope,
    "governed_engineering_proposal": RoleAuthority.authorized_governed_scope,
    "governed_test_regression_analysis": RoleAuthority.authorized_governed_scope,
    "git_transport": RoleAuthority.authorized_governed_scope,
    "commit_push_pr": RoleAuthority.authorized_governed_scope,
}


def quarantined_role_authorities(
    declared_roles: list[str],
) -> dict[str, RoleAuthority]:
    return {role: RoleAuthority.not_authorized for role in declared_roles}
