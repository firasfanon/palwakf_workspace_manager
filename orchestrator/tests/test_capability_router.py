from copy import deepcopy

from palwakf_orchestrator.capability_router import (
    CapabilityRouter,
    workspace_manager_profile,
)
from palwakf_orchestrator.operator_contracts import (
    ProjectCapabilityProfile,
    TaskCapabilityRequest,
)


def request(
    *,
    required: list[str],
    task_type: str = "backend-repository",
    mutation_class: str = "source-write",
) -> TaskCapabilityRequest:
    return TaskCapabilityRequest(
        task_id="PALWAKF_TOOL_TEST",
        project_id="PALWAKF_WORKSPACE_MANAGER",
        required_capability_ids=required,
        optional_capability_ids=[],
        task_type=task_type,
        mutation_class=mutation_class,
        environment="local",
        data_classification="internal",
        acceptance_requirements=["tests", "evidence"],
    )


def decision_map(plan):
    return {decision.capability_id: decision for decision in plan.decisions}


def test_backend_task_selects_minimum_and_excludes_irrelevant_tools() -> None:
    plan = CapabilityRouter().plan(request(required=[]), workspace_manager_profile())
    decisions = decision_map(plan)

    assert plan.dispatch_blocked is False
    assert decisions["governed.patch_relay"].selected_adapter_id == "codex"
    assert "code.execution" not in decisions
    assert decisions["source.control"].selected_adapter_id == "github"
    assert decisions["continuous.integration"].selected_adapter_id == "github-actions"
    assert decisions["runtime.verification"].selected_adapter_id == "local-runtime"
    assert decisions["evidence.capture"].selected_adapter_id == "evidence-recorder"
    for capability in (
        "product.design",
        "communication.asset",
        "relational.runtime",
        "academic.discovery",
    ):
        assert decisions[capability].selected_adapter_id is None
        assert decisions[capability].excluded_adapters_with_reason


def test_material_ui_change_selects_figma_when_authorized() -> None:
    plan = CapabilityRouter().plan(
        request(required=["product.design"], task_type="material-ui"),
        workspace_manager_profile(),
    )

    design = decision_map(plan)["product.design"]
    assert design.selected_adapter_id == "figma"
    assert design.blocked is False


def test_blocked_design_adapter_fails_closed() -> None:
    router = CapabilityRouter()
    router.registry._snapshot["adapters"]["figma"]["lifecycle"] = "blocked"

    plan = router.plan(
        request(required=["product.design"], task_type="material-ui"),
        workspace_manager_profile(),
    )

    assert plan.dispatch_blocked is True
    assert plan.blockers == ["NO_USABLE_ADAPTER:product.design"]


def profile_for(
    required: list[str],
    preferred: dict[str, list[str]],
    *,
    prohibited: list[str] | None = None,
) -> ProjectCapabilityProfile:
    base = workspace_manager_profile().model_dump()
    base.update(
        required_capabilities=required,
        conditional_capabilities=[],
        prohibited_capabilities=prohibited or [],
        preferred_adapters=preferred,
        fallback_adapters={"legal.authority": ["official-source"]},
    )
    return ProjectCapabilityProfile.model_validate(base)


def test_legal_task_prefers_midpage_and_records_official_fallback() -> None:
    profile = profile_for(["legal.authority"], {"legal.authority": ["midpage"]})
    plan = CapabilityRouter().plan(
        request(required=["legal.authority"], task_type="legal-authority"),
        profile,
    )

    legal = decision_map(plan)["legal.authority"]
    assert legal.selected_adapter_id == "midpage"
    assert legal.fallback_adapter_id == "official-source"
    assert all(
        exclusion.adapter_id not in {"consensus", "scispace"}
        for exclusion in legal.excluded_adapters_with_reason
    )


def test_academic_task_selects_consensus_and_scispace_without_code_tools() -> None:
    profile = profile_for(
        ["academic.discovery", "academic.fulltext"],
        {
            "academic.discovery": ["consensus"],
            "academic.fulltext": ["scispace"],
        },
    )
    plan = CapabilityRouter().plan(
        request(
            required=["academic.discovery", "academic.fulltext"],
            task_type="academic-research",
            mutation_class="read-only",
        ),
        profile,
    )
    decisions = decision_map(plan)

    assert decisions["academic.discovery"].selected_adapter_id == "consensus"
    assert decisions["academic.fulltext"].selected_adapter_id == "scispace"
    assert "code.execution" not in decisions


def test_ml_upload_requires_approval() -> None:
    profile = profile_for(["ml.hub"], {"ml.hub": ["hugging-face"]})
    plan = CapabilityRouter().plan(
        request(required=["ml.hub"], task_type="ml-upload"),
        profile,
    )

    decision = decision_map(plan)["ml.hub"]
    assert decision.selected_adapter_id == "hugging-face"
    assert decision.approval_required is True


def test_communication_asset_selects_canva() -> None:
    profile = profile_for(
        ["communication.asset"],
        {"communication.asset": ["canva"]},
    )
    plan = CapabilityRouter().plan(
        request(required=["communication.asset"], task_type="communication-asset"),
        profile,
    )

    assert decision_map(plan)["communication.asset"].selected_adapter_id == "canva"


def test_supabase_is_never_selected_merely_because_it_exists() -> None:
    plan = CapabilityRouter().plan(request(required=[]), workspace_manager_profile())

    relational = decision_map(plan)["relational.runtime"]
    assert relational.selected_adapter_id is None
    assert relational.permission_status == "blocked"


def test_blocked_required_adapter_prevents_dispatch() -> None:
    router = CapabilityRouter()
    snapshot = deepcopy(router.registry._snapshot)
    snapshot["adapters"]["codex"]["permission_status"] = "blocked"
    router.registry._snapshot = snapshot

    plan = router.plan(request(required=[]), workspace_manager_profile())

    assert plan.dispatch_blocked is True
    assert "NO_USABLE_ADAPTER:governed.patch_relay" in plan.blockers


def test_autonomous_code_execution_fails_closed_without_authorized_executor() -> None:
    plan = CapabilityRouter().plan(
        request(required=["code.execution"]),
        workspace_manager_profile(),
    )
    decisions = decision_map(plan)

    assert plan.dispatch_blocked is True
    assert decisions["code.execution"].selected_adapter_id is None
    assert decisions["code.execution"].blocked is True
    assert "NO_USABLE_ADAPTER:code.execution" in plan.blockers


def test_codex_registry_role_authority_separates_relay_from_autonomous_development() -> None:
    metadata = CapabilityRouter().registry.adapter("codex")

    assert metadata["lifecycle"] == "available"
    assert metadata["permission_status"] == "authorized"
    assert metadata["role_authorities"]["autonomous_development"] == "SUSPENDED"
    assert metadata["role_authorities"]["governed_patch_relay"] == "AUTHORIZED_GOVERNED_SCOPE"
    assert metadata["role_authorities"]["git_transport"] == "AUTHORIZED_GOVERNED_SCOPE"
