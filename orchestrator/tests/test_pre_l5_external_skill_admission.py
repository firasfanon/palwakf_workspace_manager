import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.external_skill_admission import (
    AuthorityLayer,
    SkillAdmissionCandidate,
    SkillAdmissionStage,
    SkillCapabilityRequest,
    SkillSourcePin,
    WorkspaceSkillDecisionType,
    assert_skill_loadable,
    decide_external_skill,
    effective_skill_authority,
)


def source() -> SkillSourcePin:
    return SkillSourcePin(
        repository="supabase/agent-skills",
        commit_sha="a" * 40,
        path="skills/supabase/SKILL.md",
        content_sha256="b" * 64,
        license="MIT",
        provenance_verified=True,
    )


def layer(
    *, actions=(), tools=(), filesystem=(), network=(), secrets=(), database=(), production=()
):
    return AuthorityLayer(
        actions=actions,
        tools=tools,
        filesystem=filesystem,
        network=network,
        secrets=secrets,
        database=database,
        production=production,
    )


def test_effective_authority_is_intersection_and_does_not_expand_task() -> None:
    requested = SkillCapabilityRequest(
        actions=("read", "write", "merge"),
        tools=("git", "gh"),
        filesystem=("project", "outside"),
        network=("github.read", "github.write"),
        database=("schema.read", "schema.write"),
        production=("deploy",),
    )
    common = dict(
        project=layer(
            actions=("read", "write"),
            tools=("git", "gh"),
            filesystem=("project",),
            network=("github.read",),
            database=("schema.read",),
            production=(),
        ),
        task=layer(
            actions=("read",),
            tools=("git",),
            filesystem=("project",),
            network=("github.read",),
            database=("schema.read",),
            production=(),
        ),
        agent=layer(
            actions=("read", "write"),
            tools=("git",),
            filesystem=("project",),
            network=("github.read",),
            database=("schema.read",),
            production=(),
        ),
        provider=layer(
            actions=("read",),
            tools=("git",),
            filesystem=("project",),
            network=("github.read",),
            database=("schema.read",),
            production=(),
        ),
        tool=layer(
            actions=("read",),
            tools=("git",),
            filesystem=("project",),
            network=("github.read",),
            database=("schema.read",),
            production=(),
        ),
        environment=layer(
            actions=("read",),
            tools=("git",),
            filesystem=("project",),
            network=("github.read",),
            database=("schema.read",),
            production=(),
        ),
    )
    effective = effective_skill_authority(requested, **common)
    assert effective.actions == ("read",)
    assert effective.tools == ("git",)
    assert effective.filesystem == ("project",)
    assert effective.network == ("github.read",)
    assert effective.database == ("schema.read",)
    assert effective.production == ()
    assert effective.self_authorized is False


def candidate(stage: SkillAdmissionStage) -> SkillAdmissionCandidate:
    return SkillAdmissionCandidate(
        skill_id="supabase.readonly",
        name="Supabase Readonly",
        source=source(),
        requested=SkillCapabilityRequest(actions=("read",)),
        security_findings=(),
        eval_refs=("evidence:eval",),
        regression_refs=("evidence:regression",),
        mind_review_ref="mind:review",
        workspace_decision_ref="workspace:decision",
        stage=stage,
    )


@pytest.mark.parametrize(
    "stage",
    [
        SkillAdmissionStage.discovered,
        SkillAdmissionStage.quarantined,
        SkillAdmissionStage.sandbox_only,
        SkillAdmissionStage.hold,
        SkillAdmissionStage.rejected,
        SkillAdmissionStage.revoked,
    ],
)
def test_unadmitted_or_revoked_skill_is_not_loadable(stage: SkillAdmissionStage) -> None:
    with pytest.raises(GovernanceError, match="EXTERNAL_SKILL_NOT_ADMITTED"):
        assert_skill_loadable(candidate(stage))


def test_project_proven_skill_requires_complete_review_evidence() -> None:
    assert_skill_loadable(candidate(SkillAdmissionStage.project_proven))
    broken = candidate(SkillAdmissionStage.project_proven).model_copy(
        update={"mind_review_ref": None}
    )
    with pytest.raises(GovernanceError, match="EXTERNAL_SKILL_REVIEW_DECISION_REQUIRED"):
        assert_skill_loadable(broken)


def test_registry_is_quarantine_first_and_transitioned_without_self_authority() -> None:
    from palwakf_orchestrator.external_skill_admission_service import ExternalSkillAdmissionService
    from palwakf_orchestrator.persistence import MemoryStateStore

    service = ExternalSkillAdmissionService(MemoryStateStore())
    registered = service.register(candidate(SkillAdmissionStage.quarantined))
    assert registered.stage == SkillAdmissionStage.quarantined
    assert registered.external_execution_authority is False
    discovered = service.transition(registered.skill_id, SkillAdmissionStage.discovered)
    assert discovered.stage == SkillAdmissionStage.discovered
    with pytest.raises(GovernanceError, match="EXTERNAL_SKILL_INVALID_ADMISSION_TRANSITION"):
        service.transition(registered.skill_id, SkillAdmissionStage.project_proven)


def test_workspace_decision_keeps_external_skill_in_sandbox_without_execution_authority() -> None:
    decision = decide_external_skill(
        "verification-before-completion",
        mind_decision="RECOMMEND_PROJECT_PROVEN",
        sandbox_pass=True,
    )
    assert decision.decision == WorkspaceSkillDecisionType.bounded_pilot_candidate
    assert decision.stage == SkillAdmissionStage.sandbox_only
    assert decision.execution_authority_granted is False
    assert decision.canonical_promotion_granted is False
    assert decision.separate_execution_authorization_required is True


def test_workspace_decision_requires_adaptation_or_holds_fail_closed() -> None:
    adapted = decide_external_skill(
        "supabase",
        mind_decision="REQUIRE_ADAPTATION",
        sandbox_pass=True,
    )
    assert adapted.decision == WorkspaceSkillDecisionType.adaptation_required
    assert adapted.stage == SkillAdmissionStage.hold
    unknown = decide_external_skill("unknown", mind_decision="UNEXPECTED", sandbox_pass=True)
    assert unknown.decision == WorkspaceSkillDecisionType.hold
