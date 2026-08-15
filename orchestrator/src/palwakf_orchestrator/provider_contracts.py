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


CODEX_ROLE_AUTHORITIES: Final[dict[str, RoleAuthority]] = {
    "autonomous_development": RoleAuthority.suspended,
    "autonomous_decision_making": RoleAuthority.forbidden,
    "independent_debugging": RoleAuthority.forbidden,
    "governed_patch_relay": RoleAuthority.authorized_governed_scope,
    "git_transport": RoleAuthority.authorized_governed_scope,
    "commit_push_pr": RoleAuthority.authorized_governed_scope,
}


def quarantined_role_authorities(
    declared_roles: list[str],
) -> dict[str, RoleAuthority]:
    return {role: RoleAuthority.not_authorized for role in declared_roles}
