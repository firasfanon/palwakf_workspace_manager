from __future__ import annotations

import pytest

from palwakf_orchestrator.policy_decision_engine import (
    REQUIRED_POLICY_LAYERS,
    DeterministicPolicyDecisionEngine,
    PolicyDecisionContext,
    PolicyDecisionRequest,
    PolicyDecisionType,
    PolicyLayerKind,
    PolicyLayerRule,
)


def context(**overrides: object) -> PolicyDecisionContext:
    data: dict[str, object] = {
        "subject_identity": "agent:builder",
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "task_id": "PREL5-048",
        "authorization_id": "AUTH-PREL5-048",
        "action": "READ_SOURCE",
        "tool_id": "git",
        "resource": "repository",
        "environment": "local",
        "provider_id": "NATIVE",
        "risk": "LOW",
        "requested_permissions": ("source.read",),
    }
    data.update(overrides)
    return PolicyDecisionContext.model_validate(data)


def rule(
    kind: PolicyLayerKind,
    *,
    permissions: tuple[str, ...] = ("source.read",),
    known: bool = True,
    **scope: object,
) -> PolicyLayerRule:
    return PolicyLayerRule(
        layer=kind,
        known=known,
        allowed_permissions=permissions,
        **scope,
    )


def all_layers(
    *,
    permissions: tuple[str, ...] = ("source.read",),
) -> tuple[PolicyLayerRule, ...]:
    return tuple(rule(kind, permissions=permissions) for kind in REQUIRED_POLICY_LAYERS)


def decide(
    *,
    ctx: PolicyDecisionContext | None = None,
    layers: tuple[PolicyLayerRule, ...] | None = None,
):
    return DeterministicPolicyDecisionEngine().decide(
        PolicyDecisionRequest(
            context=ctx or context(),
            layers=layers or all_layers(),
        )
    )


def test_effective_permission_is_intersection_of_all_governing_layers() -> None:
    layers = tuple(
        rule(
            kind,
            permissions=(
                ("source.read", "source.write")
                if kind != PolicyLayerKind.data_production_policy
                else ("source.read",)
            ),
        )
        for kind in REQUIRED_POLICY_LAYERS
    )

    decision = decide(
        ctx=context(requested_permissions=("source.read",)),
        layers=layers,
    )

    assert decision.decision == PolicyDecisionType.allow
    assert decision.effective_permissions == ("source.read",)
    assert decision.fail_closed is True
    assert decision.denied_by == ()


def test_permission_missing_from_one_layer_is_denied_without_union_expansion() -> None:
    layers = tuple(
        rule(
            kind,
            permissions=(
                ("source.read",)
                if kind == PolicyLayerKind.tool_policy
                else ("source.read", "source.write")
            ),
        )
        for kind in REQUIRED_POLICY_LAYERS
    )

    decision = decide(
        ctx=context(requested_permissions=("source.write",)),
        layers=layers,
    )

    assert decision.decision == PolicyDecisionType.deny
    assert decision.effective_permissions == ("source.read",)
    assert decision.denied_by == (PolicyLayerKind.tool_policy.value,)
    assert decision.reasons == ("PERMISSION_DENIED:source.write",)


@pytest.mark.parametrize(
    "field",
    (
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
    ),
)
def test_unknown_authority_bearing_input_denies_fail_closed(field: str) -> None:
    decision = decide(ctx=context(**{field: "UNKNOWN"}))

    assert decision.decision == PolicyDecisionType.deny
    assert decision.effective_permissions == ()
    assert decision.denied_by == ("INPUT",)
    assert f"UNKNOWN_AUTHORITY_FIELD:{field}" in decision.reasons


def test_unknown_requested_permission_denies_fail_closed() -> None:
    decision = decide(ctx=context(requested_permissions=("UNKNOWN",)))

    assert decision.decision == PolicyDecisionType.deny
    assert decision.reasons == ("UNKNOWN_AUTHORITY_FIELD:requested_permissions",)


def test_missing_required_policy_layer_denies() -> None:
    layers = all_layers()[:-1]

    decision = decide(layers=layers)

    assert decision.decision == PolicyDecisionType.deny
    assert decision.denied_by == (PolicyLayerKind.data_production_policy.value,)
    assert decision.reasons == ("MISSING_LAYER:DATA_PRODUCTION_POLICY",)


def test_duplicate_policy_layer_denies() -> None:
    layers = all_layers() + (rule(PolicyLayerKind.project_policy),)

    decision = decide(layers=layers)

    assert decision.decision == PolicyDecisionType.deny
    assert decision.denied_by == (PolicyLayerKind.project_policy.value,)
    assert decision.reasons == ("DUPLICATE_LAYER:PROJECT_POLICY",)


def test_unknown_policy_layer_denies() -> None:
    layers = tuple(
        rule(kind, known=kind != PolicyLayerKind.provider_policy) for kind in REQUIRED_POLICY_LAYERS
    )

    decision = decide(layers=layers)

    assert decision.decision == PolicyDecisionType.deny
    assert decision.denied_by == (PolicyLayerKind.provider_policy.value,)
    assert decision.reasons == ("UNKNOWN_POLICY_LAYER:PROVIDER_POLICY",)


def test_context_scope_mismatch_denies_at_governing_layer() -> None:
    layers = tuple(
        rule(
            kind,
            project_ids=(
                ("PALWAKF_OTHER_PROJECT",) if kind == PolicyLayerKind.project_policy else None
            ),
        )
        for kind in REQUIRED_POLICY_LAYERS
    )

    decision = decide(layers=layers)

    assert decision.decision == PolicyDecisionType.deny
    assert decision.denied_by == (PolicyLayerKind.project_policy.value,)
    assert decision.reasons == ("SCOPE_MISMATCH:PROJECT_POLICY:project_id",)


def test_wildcard_scope_is_explicit_and_deterministic() -> None:
    layers = tuple(rule(kind, project_ids=("*",)) for kind in REQUIRED_POLICY_LAYERS)

    decision = decide(layers=layers)

    assert decision.decision == PolicyDecisionType.allow


def test_layer_order_does_not_change_decision_or_effective_permissions() -> None:
    ordered = all_layers(permissions=("source.read", "evidence.read"))
    reversed_layers = tuple(reversed(ordered))

    first = decide(layers=ordered)
    second = decide(layers=reversed_layers)

    assert first.decision == second.decision == PolicyDecisionType.allow
    assert first.effective_permissions == second.effective_permissions
    assert first.denied_by == second.denied_by
    assert first.reasons == second.reasons


def test_input_fingerprint_is_stable_for_identical_request() -> None:
    request = PolicyDecisionRequest(context=context(), layers=all_layers())
    engine = DeterministicPolicyDecisionEngine()

    first = engine.decide(request)
    second = engine.decide(request)

    assert first.input_fingerprint_sha256 == second.input_fingerprint_sha256
    assert len(first.input_fingerprint_sha256) == 64
