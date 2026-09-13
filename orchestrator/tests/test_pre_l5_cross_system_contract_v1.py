import hashlib

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.intersystem_contracts import (
    WorkspaceAuthorityPackageV1,
)
from palwakf_orchestrator.pre_l5_cross_system_contract import (
    PreL5CrossSystemContractV1,
    PreL5FailureFingerprintBindingV1,
    build_pre_l5_cross_system_contract,
)
from palwakf_orchestrator.pre_l5_instruction_resolver import (
    InstructionRecordV1,
    PreExecutionKnowledgeGateV1,
    build_pre_l5_bootstrap_envelope,
)


PROJECT = "PALWAKF_LOCAL_AGENTS"
TASK = "TASK-CROSS-SYSTEM"
STATE = "workspace-state-cross-system"
RUN = "RUN-CROSS-SYSTEM"
AUTHORITY = "AUTH:CROSS-SYSTEM"


def sha(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def package():
    return WorkspaceAuthorityPackageV1(
        state_package_id=STATE,
        execution_run_id=RUN,
        project_id=PROJECT,
        task_id=TASK,
        repository="example/repo",
        task_branch="task/CROSS-SYSTEM",
        base_sha="1" * 40,
        expected_head="2" * 40,
        authority_reference=AUTHORITY,
        objective="Execute governed cross-system pre-L5 proof.",
        constraints=["READ_ONLY"],
        timeout_seconds=60,
        scope_patterns=["**"],
        required_capabilities=[],
        required_tests=["PRE_L5_CROSS_SYSTEM"],
    )


def instruction():
    return InstructionRecordV1(
        instruction_id="AMENDMENT-20260913",
        authority="GLOBAL_CROSS_PROJECT",
        authority_rank=100,
        version="V1",
        effective_at="2026-09-13T00:00:00Z",
        status="ACTIVE",
        source_authority="WORKSPACE_DRIVE_SOVEREIGN",
        applies_to_projects=(PROJECT,),
        supersedes=("OLD-INSTRUCTION",),
        conflict_key="PRE_L5_POLICY",
        directive_fingerprint=sha("CURRENT"),
    )


def knowledge():
    return PreExecutionKnowledgeGateV1(
        project_id=PROJECT,
        task_id=TASK,
        active_lesson_ids=("LESSON-1",),
        known_failure_fingerprint_ids=("FP-1",),
        applicable_skill_ids=("SKILL-1",),
        preventive_gate_ids=("GATE-1",),
        known_relevant_lessons_reused=True,
    )


def bootstrap():
    return build_pre_l5_bootstrap_envelope(
        authority_package=package(),
        instruction_records=[instruction()],
        knowledge_gate=knowledge(),
    )


def fingerprint(
    *,
    project=PROJECT,
):
    return PreL5FailureFingerprintBindingV1(
        fingerprint_id="FP-1",
        lesson_id="LESSON-1",
        preventive_gate_id="GATE-1",
        applies_to_projects=(project,),
    )


def test_workspace_emits_bound_cross_system_contract():
    contract = build_pre_l5_cross_system_contract(
        bootstrap=bootstrap(),
        reused_lesson_ids=("LESSON-1",),
        failure_fingerprints=(fingerprint(),),
    )

    assert contract.execution_admission == "READY"
    assert contract.canonical_promotion_allowed is False
    assert contract.project_id == PROJECT
    assert contract.task_id == TASK
    assert contract.active_lesson_ids == ("LESSON-1",)
    assert contract.reused_lesson_ids == ("LESSON-1",)

    resumed = (
        PreL5CrossSystemContractV1
        .model_validate_json(
            contract.model_dump_json()
        )
    )

    assert (
        resumed.active_instruction_set_sha256
        == contract.active_instruction_set_sha256
    )


def test_known_lesson_must_be_reused():
    with pytest.raises(
        ValidationError,
        match="CROSS_SYSTEM_KNOWN_LESSON_NOT_REUSED",
    ):
        build_pre_l5_cross_system_contract(
            bootstrap=bootstrap(),
            reused_lesson_ids=(),
            failure_fingerprints=(fingerprint(),),
        )


def test_failure_fingerprint_project_leakage_fails():
    with pytest.raises(
        ValidationError,
        match=(
            "CROSS_SYSTEM_FAILURE_"
            "FINGERPRINT_PROJECT_LEAKAGE"
        ),
    ):
        build_pre_l5_cross_system_contract(
            bootstrap=bootstrap(),
            reused_lesson_ids=("LESSON-1",),
            failure_fingerprints=(
                fingerprint(project="OTHER_PROJECT"),
            ),
        )


def test_failure_fingerprint_mapping_cannot_be_omitted():
    with pytest.raises(
        ValueError,
        match=(
            "WORKSPACE_FAILURE_FINGERPRINT_"
            "BINDING_INCOMPLETE"
        ),
    ):
        build_pre_l5_cross_system_contract(
            bootstrap=bootstrap(),
            reused_lesson_ids=("LESSON-1",),
            failure_fingerprints=(),
        )
