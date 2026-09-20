from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.agent_census_registry import (
    AgentCensusRegistryStore,
    AgenticLineageRef,
    AgenticSourceLineageV1,
    AgentRegistrySourceClass,
    AgentRegistrySourceRecordV1,
    RuntimeProfileAdmission,
    RuntimeProfileRecordV1,
    SpecializedAgentRecordV1,
    ToolCandidateRecordV1,
    WorkflowReferenceRecordV1,
    build_agent_census_snapshot,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore

NOW = datetime(2026, 9, 17, 10, 40, tzinfo=UTC)
MAIN = "e780c2ecd68f69f7b91a7ab27b8ecfa060f068f6"
WIP_SKILLS = "54ebb033287bbfb8b60d891be830c20a724e602f"
WIP_PREL5 = "197546f3811f064326910a0c3e1045b7843c41b4"


def _lineage() -> AgenticSourceLineageV1:
    return AgenticSourceLineageV1(
        canonical_main_sha=MAIN,
        refs=(
            AgenticLineageRef(
                ref_name="origin/main", commit_sha=MAIN, classification="CANONICAL_MAIN"
            ),
            AgenticLineageRef(
                ref_name="task/PREL5-031-067-SKILL-ADMISSION-MEGA-BATCH-V1",
                commit_sha=WIP_SKILLS,
                classification="WIP_DIVERGED",
            ),
            AgenticLineageRef(
                ref_name="task/AGENTIC-L4-WIP-PRE-L5-ENFORCEMENT-V1",
                commit_sha=WIP_PREL5,
                classification="WIP_DIVERGED",
            ),
        ),
        registry_content_equivalent_across_refs=True,
        runtime_lineage_diverged=True,
    )


def _source(source_id: str, path: str, digest: str, classification: AgentRegistrySourceClass):
    return AgentRegistrySourceRecordV1(
        source_id=source_id,
        path=path,
        content_sha256=digest,
        classification=classification,
        observed_at=NOW,
    )


def _sources() -> tuple[AgentRegistrySourceRecordV1, ...]:
    return (
        _source(
            "roles-v1",
            "agents/registry.yaml",
            "837da52b9edc026532d16adb2ec8cfd0eaeb835930d9d33af836b409320c4a6a",
            AgentRegistrySourceClass.legacy_role_registry,
        ),
        _source(
            "roles-v2",
            "agents/registry_v2.yaml",
            "de63bd1e4eedef2d90f9092963e37d75dfe4adbcdb369636ff72eba6b7eb23c0",
            AgentRegistrySourceClass.current_role_registry,
        ),
        _source(
            "legacy-skill-assignments",
            "agents/registry/AGENT_SKILL_ASSIGNMENTS_V1.json",
            "03a22998ce9f44bce676f44e6fe4e9078175a376e1aceb40df99f57572386392",
            AgentRegistrySourceClass.legacy_partial_assignments,
        ),
        _source(
            "runtime-profiles",
            "backend/src/palwakf_local_agents/local_agent_core/registry.py",
            "bc932844bfb2de78a5b39691b59b3fde674e0a8f7b26d896df10b91d6e1d3ae1",
            AgentRegistrySourceClass.current_runtime_registry,
        ),
        _source(
            "role-runtime-projection",
            "backend/src/palwakf_local_agents/agentic_core_v1/registry_projection.py",
            "dc4fc62949f098ba5168632c088ab3edd7b6b0e31745e2990c346371e0d18b34",
            AgentRegistrySourceClass.current_projection,
        ),
        _source(
            "skill-workflow",
            "docs/SKILL_AWARE_GOAL_AND_TASK_WORKFLOW_V1_CONTRACT.json",
            "d20b0062e9c11036a734c1e793c8cf2ee784a1a129c8813c482163dfd495bc4a",
            AgentRegistrySourceClass.reference_workflow,
        ),
        _source(
            "specialized-catalog",
            "docs/SPECIALIZED_AGENT_CATALOG_AND_DOMAIN_CAPABILITY_MATRIX_V1_CONTRACT.json",
            "1f00ff4f3e5b1ba5534c409de2f0af2cf6bebdb8f86ac96dc9c77b8f531f9e98",
            AgentRegistrySourceClass.reference_workflow,
        ),
        _source(
            "tool-candidates",
            "backend/src/palwakf_local_agents/open_source_capability_registry_v1.json",
            "8d7d66e31372275394edd8fa60837e09693d6b046e299037b1e67a9b28ca8a77",
            AgentRegistrySourceClass.reference_tool_catalog,
        ),
    )


def _profiles() -> tuple[RuntimeProfileRecordV1, ...]:
    rows = (
        ("policy_guardian_agent_v1", ("policy_review", "risk_flags", "review_gate")),
        ("local_agent_coordinator_v1", ("request_routing", "agent_selection", "bounded_plan")),
        ("evidence_audit_agent_v1", ("evidence_summary", "gap_detection", "audit_packet")),
        (
            "repository_test_triage_agent_v1",
            ("manifest_analysis", "test_failure_triage", "risk_flags"),
        ),
        ("task_planning_runbook_agent_v1", ("mega_batch_plan", "uat_plan", "rollback_prompts")),
        ("human_review_copilot_v1", ("review_packet", "decision_prompts", "evidence_links")),
    )
    return tuple(
        RuntimeProfileRecordV1(
            profile_id=profile_id,
            source_path="backend/src/palwakf_local_agents/local_agent_core/registry.py",
            execution_mode="LOCAL_DETERMINISTIC_PREPARE_ONLY",
            admission=RuntimeProfileAdmission.prepare_only,
            output_authority="PROPOSAL_ONLY_NO_EXECUTION",
            capabilities=capabilities,
        )
        for profile_id, capabilities in rows
    )


def _agent(
    role_id: str,
    status: str,
    profile_id: str,
    skills: tuple[str, ...],
    task_classes: tuple[str, ...] = ("READ_ONLY_DIAGNOSTIC",),
) -> SpecializedAgentRecordV1:
    return SpecializedAgentRecordV1(
        agent_id=f"{role_id}_agentic_v1",
        role_id=role_id,
        role_source_status=status,
        runtime_profile_id=profile_id,
        skill_ids=skills,
        tool_bindings=("repository_manifest_read",),
        task_classes=task_classes,
        technical_runnable=True,
        operational_admitted=False,
    )


def _agents() -> tuple[SpecializedAgentRecordV1, ...]:
    required = "admission_required_v2"
    disabled = "disabled_pending_admission"
    return (
        _agent(
            "coordinator",
            required,
            "local_agent_coordinator_v1",
            (
                "baseline_read",
                "task_triage",
                "risk_assessment",
                "fact_assumption_decision_register",
                "workspace_lock_planning",
                "evidence_assessment",
            ),
            ("READ_ONLY_DIAGNOSTIC", "TASK_PLANNING"),
        ),
        _agent(
            "sovereignty_reviewer",
            required,
            "policy_guardian_agent_v1",
            (
                "governance_review",
                "evidence_assessment",
                "prompt_injection_screening",
                "data_classification_review",
                "baseline_read",
            ),
            ("READ_ONLY_DIAGNOSTIC", "POLICY_REVIEW"),
        ),
        _agent(
            "knowledge_researcher",
            required,
            "evidence_audit_agent_v1",
            (
                "knowledge_source_review",
                "evidence_assessment",
                "fact_assumption_decision_register",
                "prompt_injection_screening",
            ),
            ("READ_ONLY_DIAGNOSTIC", "EVIDENCE_REVIEW"),
        ),
        _agent(
            "ui_ux_designer",
            required,
            "task_planning_runbook_agent_v1",
            ("ui_ux_contract_review", "requirements_mvp_analysis", "documentation_handoff"),
        ),
        _agent(
            "documentation_handoff",
            required,
            "human_review_copilot_v1",
            (
                "documentation_handoff",
                "baseline_read",
                "fact_assumption_decision_register",
                "memory_learning_candidate",
            ),
        ),
        _agent(
            "product_analyst",
            disabled,
            "task_planning_runbook_agent_v1",
            (
                "requirements_mvp_analysis",
                "task_triage",
                "fact_assumption_decision_register",
                "risk_assessment",
            ),
        ),
        _agent(
            "solution_architect",
            disabled,
            "task_planning_runbook_agent_v1",
            (
                "architecture_analysis",
                "data_api_design_plan",
                "risk_assessment",
                "baseline_read",
                "system_contract_review",
            ),
        ),
        _agent(
            "qa_security_reviewer",
            disabled,
            "policy_guardian_agent_v1",
            (
                "qa_security_review",
                "evidence_assessment",
                "prompt_injection_screening",
                "data_classification_review",
                "test_plan_generation",
            ),
        ),
        _agent(
            "tester",
            disabled,
            "repository_test_triage_agent_v1",
            ("test_plan_generation", "qa_security_review", "evidence_assessment"),
            ("READ_ONLY_DIAGNOSTIC", "TEST_TRIAGE"),
        ),
        _agent(
            "coding_builder",
            disabled,
            "repository_test_triage_agent_v1",
            (
                "repository_static_trace",
                "architecture_analysis",
                "patch_plan_generation",
                "evidence_assessment",
            ),
            ("READ_ONLY_DIAGNOSTIC", "REPOSITORY_ANALYSIS"),
        ),
        _agent(
            "frontend_engineer",
            disabled,
            "repository_test_triage_agent_v1",
            (
                "repository_static_trace",
                "ui_ux_contract_review",
                "patch_plan_generation",
                "test_plan_generation",
            ),
            ("READ_ONLY_DIAGNOSTIC", "FRONTEND_ANALYSIS"),
        ),
        _agent(
            "backend_engineer",
            disabled,
            "repository_test_triage_agent_v1",
            (
                "architecture_analysis",
                "data_api_design_plan",
                "repository_static_trace",
                "patch_plan_generation",
            ),
            ("READ_ONLY_DIAGNOSTIC", "BACKEND_ANALYSIS"),
        ),
        _agent(
            "database_engineer",
            disabled,
            "policy_guardian_agent_v1",
            (
                "data_api_design_plan",
                "system_contract_review",
                "risk_assessment",
                "migration_plan_review",
            ),
        ),
        _agent(
            "release_engineer",
            disabled,
            "human_review_copilot_v1",
            ("release_readiness_review", "incident_analysis", "baseline_read", "risk_assessment"),
        ),
    )


def _workflows() -> tuple[WorkflowReferenceRecordV1, ...]:
    return (
        WorkflowReferenceRecordV1(
            workflow_id="skill-aware-goal-task-workflow-v1",
            source_path="docs/SKILL_AWARE_GOAL_AND_TASK_WORKFLOW_V1_CONTRACT.json",
            mode="PREPARE_ONLY_FRONTEND_AUGMENTATION",
        ),
        WorkflowReferenceRecordV1(
            workflow_id="specialized-agent-domain-capability-matrix-v1",
            source_path="docs/SPECIALIZED_AGENT_CATALOG_AND_DOMAIN_CAPABILITY_MATRIX_V1_CONTRACT.json",
            mode="DESIGN_ONLY_FRONTEND_POLISH",
        ),
    )


def _tools() -> tuple[ToolCandidateRecordV1, ...]:
    rows = (
        ("tree_sitter", "high_priority_read_only_candidate", "safe_adapter_contract_only"),
        ("opentelemetry", "high_priority_local_telemetry_candidate", "safe_adapter_contract_only"),
        ("semgrep", "accepted_candidate_runtime_blocked", "safe_adapter_contract_only"),
        ("gitleaks", "accepted_candidate_runtime_blocked", "safe_adapter_contract_only"),
        ("trivy", "deferred_accepted_candidate", "safe_adapter_contract_only"),
        ("temporal", "architecture_deferred", "registry_reference_only"),
        ("prefect", "architecture_deferred", "registry_reference_only"),
        ("langfuse", "optional_later_license_boundary_required", "registry_reference_only"),
        ("phoenix", "license_review_required", "registry_reference_only"),
        ("swe_agent", "reference_only_current_phase", "registry_reference_only"),
        ("aider", "reference_only_current_phase", "registry_reference_only"),
    )
    return tuple(
        ToolCandidateRecordV1(tool_id=tool_id, decision=decision, integration_mode=mode)
        for tool_id, decision, mode in rows
    )


def _snapshot(source_revision: str = "drive-revision-023"):
    return build_agent_census_snapshot(
        source_revision=source_revision,
        lineage=_lineage(),
        sources=_sources(),
        runtime_profiles=_profiles(),
        agents=_agents(),
        workflows=_workflows(),
        tool_candidates=_tools(),
        observed_at=NOW,
    )


def test_fresh_census_matches_observed_agentic_reality() -> None:
    snapshot = _snapshot()
    assert len(snapshot.agents) == 14
    assert len(snapshot.runtime_profiles) == 6
    assert len(snapshot.unique_skill_ids) == 24
    assert len(snapshot.tool_candidates) == 11
    assert len(snapshot.workflows) == 2
    assert all(agent.technical_runnable for agent in snapshot.agents)
    assert all(not agent.operational_admitted for agent in snapshot.agents)
    assert snapshot.lineage.runtime_lineage_diverged is True


def test_registry_v1_is_legacy_and_registry_v2_is_unique_current() -> None:
    snapshot = _snapshot()
    by_path = {item.path: item.classification for item in snapshot.sources}
    assert by_path["agents/registry.yaml"] == AgentRegistrySourceClass.legacy_role_registry
    assert by_path["agents/registry_v2.yaml"] == AgentRegistrySourceClass.current_role_registry
    current = [
        item
        for item in snapshot.sources
        if item.classification == AgentRegistrySourceClass.current_role_registry
    ]
    assert len(current) == 1


def test_technical_runnable_does_not_grant_operational_admission() -> None:
    snapshot = _snapshot()
    agent = snapshot.get_agent("coding_builder_agentic_v1")
    assert agent.technical_runnable is True
    assert agent.operational_admitted is False
    with pytest.raises(GovernanceError, match="AGENT_NOT_OPERATIONALLY_ADMITTED"):
        snapshot.assert_operationally_admitted(agent.agent_id)


def test_pending_role_cannot_be_marked_operationally_admitted() -> None:
    with pytest.raises(ValidationError, match="PENDING_ROLE_CANNOT_BE_OPERATIONALLY_ADMITTED"):
        SpecializedAgentRecordV1(
            agent_id="coding_builder_agentic_v1",
            role_id="coding_builder",
            role_source_status="disabled_pending_admission",
            runtime_profile_id="repository_test_triage_agent_v1",
            skill_ids=("repository_static_trace",),
            tool_bindings=("repository_manifest_read",),
            task_classes=("REPOSITORY_ANALYSIS",),
            technical_runnable=True,
            operational_admitted=True,
            operational_admission_reference="PREL5-024",
        )


def test_shared_runtime_profile_is_role_sharing_not_duplicate_agent() -> None:
    groups = _snapshot().shared_runtime_profiles()
    assert groups["repository_test_triage_agent_v1"] == (
        "backend_engineer",
        "coding_builder",
        "frontend_engineer",
        "tester",
    )
    assert groups["policy_guardian_agent_v1"] == (
        "database_engineer",
        "qa_security_reviewer",
        "sovereignty_reviewer",
    )


def test_unknown_runtime_profile_fails_closed() -> None:
    agents = list(_agents())
    agents[0] = agents[0].model_copy(update={"runtime_profile_id": "missing_profile"})
    with pytest.raises(ValidationError, match="UNKNOWN_RUNTIME_PROFILE"):
        build_agent_census_snapshot(
            source_revision="rev",
            lineage=_lineage(),
            sources=_sources(),
            runtime_profiles=_profiles(),
            agents=tuple(agents),
            observed_at=NOW,
        )


def test_registry_content_drift_across_refs_requires_reconciliation() -> None:
    with pytest.raises(ValidationError, match="REGISTRY_CONTENT_DRIFT_REQUIRES_RECONCILIATION"):
        AgenticSourceLineageV1(
            canonical_main_sha=MAIN,
            refs=(
                AgenticLineageRef(
                    ref_name="origin/main",
                    commit_sha=MAIN,
                    classification="CANONICAL_MAIN",
                ),
            ),
            registry_content_equivalent_across_refs=False,
            runtime_lineage_diverged=True,
        )


def test_store_persists_and_replays_same_revision_idempotently() -> None:
    state = MemoryStateStore()
    store = AgentCensusRegistryStore(state, now=lambda: NOW)
    first = store.import_snapshot(
        source_revision="drive-revision-023",
        lineage=_lineage(),
        sources=_sources(),
        runtime_profiles=_profiles(),
        agents=_agents(),
        workflows=_workflows(),
        tool_candidates=_tools(),
    )
    second = store.import_snapshot(
        source_revision="drive-revision-023",
        lineage=_lineage(),
        sources=_sources(),
        runtime_profiles=_profiles(),
        agents=_agents(),
        workflows=_workflows(),
        tool_candidates=_tools(),
    )
    assert first.census_sha256 == second.census_sha256
    assert len(store.history()) == 1


def test_same_revision_with_changed_census_fails_closed() -> None:
    state = MemoryStateStore()
    store = AgentCensusRegistryStore(state, now=lambda: NOW)
    kwargs = dict(
        source_revision="drive-revision-023",
        lineage=_lineage(),
        sources=_sources(),
        runtime_profiles=_profiles(),
        workflows=_workflows(),
        tool_candidates=_tools(),
    )
    store.import_snapshot(agents=_agents(), **kwargs)
    changed = list(_agents())
    changed[0] = changed[0].model_copy(update={"skill_ids": (*changed[0].skill_ids, "new_skill")})
    with pytest.raises(GovernanceError, match="SOURCE_REVISION_CONFLICT"):
        store.import_snapshot(agents=tuple(changed), **kwargs)


def test_persisted_census_tamper_is_detected() -> None:
    state = MemoryStateStore()
    store = AgentCensusRegistryStore(state, now=lambda: NOW)
    store.import_snapshot(
        source_revision="drive-revision-023",
        lineage=_lineage(),
        sources=_sources(),
        runtime_profiles=_profiles(),
        agents=_agents(),
        workflows=_workflows(),
        tool_candidates=_tools(),
    )
    raw = state.load()
    raw["pre_l5_agent_census_registry_v1"]["snapshots"][0]["agents"][0]["skill_ids"].append(
        "tampered_skill"
    )
    state.save(raw)
    with pytest.raises(GovernanceError, match="AGENT_CENSUS_HASH_MISMATCH"):
        store.current()


def test_runtime_profile_admission_does_not_auto_admit_specialized_role() -> None:
    snapshot = _snapshot()
    assert all(
        profile.admission == RuntimeProfileAdmission.prepare_only
        for profile in snapshot.runtime_profiles
    )
    assert snapshot.get_agent("coordinator_agentic_v1").operational_admitted is False
