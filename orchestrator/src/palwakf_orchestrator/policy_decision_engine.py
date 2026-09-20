from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class PolicyLayerKind(StrEnum):
    external_workspace_authorization = "EXTERNAL_WORKSPACE_AUTHORIZATION"
    project_policy = "PROJECT_POLICY"
    environment_policy = "ENVIRONMENT_POLICY"
    agent_capability = "AGENT_CAPABILITY"
    provider_policy = "PROVIDER_POLICY"
    tool_policy = "TOOL_POLICY"
    data_production_policy = "DATA_PRODUCTION_POLICY"


REQUIRED_POLICY_LAYERS: tuple[PolicyLayerKind, ...] = tuple(PolicyLayerKind)


class PolicyDecisionType(StrEnum):
    allow = "ALLOW"
    deny = "DENY"


class PolicyDecisionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_identity: str | None
    project_id: str | None
    task_id: str | None
    authorization_id: str | None
    action: str | None
    tool_id: str | None
    resource: str | None
    environment: str | None
    provider_id: str | None
    risk: str | None
    requested_permissions: tuple[str, ...] = Field(min_length=1)


class PolicyLayerRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: PolicyLayerKind
    known: bool = True
    allowed_permissions: tuple[str, ...] = ()
    subject_identities: tuple[str, ...] | None = None
    project_ids: tuple[str, ...] | None = None
    task_ids: tuple[str, ...] | None = None
    authorization_ids: tuple[str, ...] | None = None
    actions: tuple[str, ...] | None = None
    tool_ids: tuple[str, ...] | None = None
    resources: tuple[str, ...] | None = None
    environments: tuple[str, ...] | None = None
    provider_ids: tuple[str, ...] | None = None
    risks: tuple[str, ...] | None = None


class PolicyDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: PolicyDecisionContext
    layers: tuple[PolicyLayerRule, ...] = Field(min_length=1)


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_id: Literal["PALWAKF_DETERMINISTIC_POLICY_ENGINE_V1"] = (
        "PALWAKF_DETERMINISTIC_POLICY_ENGINE_V1"
    )
    decision: PolicyDecisionType
    effective_permissions: tuple[str, ...]
    denied_by: tuple[str, ...]
    reasons: tuple[str, ...]
    input_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fail_closed: Literal[True] = True


class PolicyDecisionEngine(Protocol):
    def decide(self, request: PolicyDecisionRequest) -> PolicyDecision: ...


_AUTHORITY_FIELDS = (
    "subject_identity",
    "project_id",
    "task_id",
    "authorization_id",
    "action",
    "tool_id",
    "resource",
    "environment",
    "provider_id",
    "risk",
)

_SCOPE_FIELDS: tuple[tuple[str, str], ...] = (
    ("subject_identity", "subject_identities"),
    ("project_id", "project_ids"),
    ("task_id", "task_ids"),
    ("authorization_id", "authorization_ids"),
    ("action", "actions"),
    ("tool_id", "tool_ids"),
    ("resource", "resources"),
    ("environment", "environments"),
    ("provider_id", "provider_ids"),
    ("risk", "risks"),
)

_UNKNOWN_SENTINELS = frozenset({"UNKNOWN", "UNRESOLVED", "UNSPECIFIED"})


def _is_unknown(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    return not normalized or normalized.upper() in _UNKNOWN_SENTINELS


def _matches_scope(value: str, allowed: tuple[str, ...] | None) -> bool:
    if allowed is None:
        return True
    return "*" in allowed or value in allowed


def _fingerprint(request: PolicyDecisionRequest) -> str:
    payload = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class DeterministicPolicyDecisionEngine:
    """Fail-closed policy intersection with no external policy-engine dependency."""

    def decide(self, request: PolicyDecisionRequest) -> PolicyDecision:
        fingerprint = _fingerprint(request)
        context = request.context

        unknown_fields = [
            field for field in _AUTHORITY_FIELDS if _is_unknown(getattr(context, field))
        ]
        unknown_permissions = [
            permission for permission in context.requested_permissions if _is_unknown(permission)
        ]
        if unknown_fields or unknown_permissions:
            reasons = tuple(f"UNKNOWN_AUTHORITY_FIELD:{field}" for field in unknown_fields)
            if unknown_permissions:
                reasons += ("UNKNOWN_AUTHORITY_FIELD:requested_permissions",)
            return PolicyDecision(
                decision=PolicyDecisionType.deny,
                effective_permissions=(),
                denied_by=("INPUT",),
                reasons=reasons,
                input_fingerprint_sha256=fingerprint,
            )

        by_kind: dict[PolicyLayerKind, PolicyLayerRule] = {}
        duplicates: set[PolicyLayerKind] = set()
        for rule in request.layers:
            if rule.layer in by_kind:
                duplicates.add(rule.layer)
            by_kind[rule.layer] = rule

        missing = [kind for kind in REQUIRED_POLICY_LAYERS if kind not in by_kind]
        if missing or duplicates:
            reasons = tuple(f"MISSING_LAYER:{kind.value}" for kind in missing)
            reasons += tuple(
                f"DUPLICATE_LAYER:{kind.value}"
                for kind in sorted(duplicates, key=lambda item: item.value)
            )
            return PolicyDecision(
                decision=PolicyDecisionType.deny,
                effective_permissions=(),
                denied_by=tuple(
                    sorted(
                        {
                            *(kind.value for kind in missing),
                            *(kind.value for kind in duplicates),
                        }
                    )
                ),
                reasons=reasons,
                input_fingerprint_sha256=fingerprint,
            )

        ordered_rules = tuple(by_kind[kind] for kind in REQUIRED_POLICY_LAYERS)
        unknown_layers = tuple(rule for rule in ordered_rules if not rule.known)
        if unknown_layers:
            return PolicyDecision(
                decision=PolicyDecisionType.deny,
                effective_permissions=(),
                denied_by=tuple(rule.layer.value for rule in unknown_layers),
                reasons=tuple(
                    f"UNKNOWN_POLICY_LAYER:{rule.layer.value}" for rule in unknown_layers
                ),
                input_fingerprint_sha256=fingerprint,
            )

        scope_failures: list[tuple[PolicyLayerRule, str]] = []
        for rule in ordered_rules:
            for context_field, rule_field in _SCOPE_FIELDS:
                value = getattr(context, context_field)
                assert isinstance(value, str)
                if not _matches_scope(value, getattr(rule, rule_field)):
                    scope_failures.append((rule, context_field))
        if scope_failures:
            return PolicyDecision(
                decision=PolicyDecisionType.deny,
                effective_permissions=(),
                denied_by=tuple(sorted({rule.layer.value for rule, _ in scope_failures})),
                reasons=tuple(
                    f"SCOPE_MISMATCH:{rule.layer.value}:{field}" for rule, field in scope_failures
                ),
                input_fingerprint_sha256=fingerprint,
            )

        effective = set(ordered_rules[0].allowed_permissions)
        for rule in ordered_rules[1:]:
            effective.intersection_update(rule.allowed_permissions)
        effective_permissions = tuple(sorted(effective))

        requested = tuple(dict.fromkeys(context.requested_permissions))
        missing_permissions = tuple(
            permission for permission in requested if permission not in effective
        )
        if missing_permissions:
            denied_by = sorted(
                {
                    rule.layer.value
                    for rule in ordered_rules
                    for permission in missing_permissions
                    if permission not in rule.allowed_permissions
                }
            )
            return PolicyDecision(
                decision=PolicyDecisionType.deny,
                effective_permissions=effective_permissions,
                denied_by=tuple(denied_by),
                reasons=tuple(
                    f"PERMISSION_DENIED:{permission}" for permission in missing_permissions
                ),
                input_fingerprint_sha256=fingerprint,
            )

        return PolicyDecision(
            decision=PolicyDecisionType.allow,
            effective_permissions=effective_permissions,
            denied_by=(),
            reasons=("ALL_GOVERNING_POLICIES_ALLOW",),
            input_fingerprint_sha256=fingerprint,
        )
