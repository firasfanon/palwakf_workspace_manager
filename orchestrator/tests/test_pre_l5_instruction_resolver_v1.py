import hashlib

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.intersystem_contracts import (
    WorkspaceAuthorityPackageV1,
)
from palwakf_orchestrator.pre_l5_instruction_resolver import (
    ActiveInstructionResolverV1,
    InstructionRecordV1,
    PreExecutionKnowledgeGateV1,
    PreL5WorkspaceBootstrapEnvelopeV1,
    build_pre_l5_bootstrap_envelope,
)

PROJECT = "PALWAKF_LOCAL_AGENTS"
TASK = "TASK-PRE-L5"
STATE = "workspace-state-pre-l5"
AUTH = "AUTHORITY:PRE-L5"


def fp(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def record(
    instruction_id: str,
    *,
    status="ACTIVE",
    project=PROJECT,
    supersedes=(),
    conflict_key="PRE_L5_POLICY",
    directive="CURRENT",
    source="WORKSPACE_DRIVE_SOVEREIGN",
    authority_rank=100,
    effective_at="2026-09-13T00:00:00Z",
    version="V1",
):
    return InstructionRecordV1(
        instruction_id=instruction_id,
        authority="GLOBAL_CROSS_PROJECT",
        authority_rank=authority_rank,
        version=version,
        effective_at=effective_at,
        status=status,
        source_authority=source,
        applies_to_projects=(project,),
        supersedes=supersedes,
        conflict_key=conflict_key,
        directive_fingerprint=fp(directive),
    )


def resolve(records):
    return ActiveInstructionResolverV1().resolve(
        project_id=PROJECT,
        task_id=TASK,
        state_package_id=STATE,
        authority_reference=AUTH,
        records=records,
    )


def package():
    return WorkspaceAuthorityPackageV1(
        state_package_id=STATE,
        execution_run_id="RUN-PRE-L5",
        project_id=PROJECT,
        task_id=TASK,
        repository="example/repo",
        task_branch="task/PRE-L5",
        base_sha="1" * 40,
        expected_head="2" * 40,
        authority_reference=AUTH,
        objective="Execute governed pre-L5 read-only work.",
        constraints=["READ_ONLY"],
        timeout_seconds=60,
        scope_patterns=["**"],
        required_capabilities=[],
        required_tests=["PRE_L5"],
    )


def knowledge_gate():
    return PreExecutionKnowledgeGateV1(
        project_id=PROJECT,
        task_id=TASK,
        active_lesson_ids=("LESSON-1",),
        known_failure_fingerprint_ids=("FP-1",),
        applicable_skill_ids=("SKILL-1",),
        preventive_gate_ids=("GATE-1",),
        known_relevant_lessons_reused=True,
    )


def test_historical_revoked_and_superseded_are_not_executable():
    old = record(
        "OLD",
        status="HISTORICAL",
    )

    revoked = record(
        "REVOKED",
        status="REVOKED",
    )

    prior_active = record(
        "PRIOR-ACTIVE",
        directive="OLD",
    )

    current = record(
        "CURRENT",
        supersedes=("PRIOR-ACTIVE",),
        directive="CURRENT",
    )

    resolved = resolve(
        [old, revoked, prior_active, current]
    )

    active_ids = {
        item.instruction_id
        for item in resolved.active_instructions
    }

    assert active_ids == {"CURRENT"}

    reasons = {
        item.instruction_id: item.reason
        for item in resolved.exclusions
    }

    assert reasons["OLD"] == (
        "STATUS_HISTORICAL_EXCLUDED"
    )
    assert reasons["REVOKED"] == (
        "STATUS_REVOKED_EXCLUDED"
    )
    assert reasons["PRIOR-ACTIVE"] == (
        "SUPERSEDED_BY_ACTIVE_INSTRUCTION"
    )


def test_stale_conflicting_instruction_cannot_reenter():
    stale = record(
        "STALE",
        directive="OLD",
        effective_at="2026-09-10T00:00:00Z",
    )

    current = record(
        "CURRENT",
        supersedes=("STALE",),
        directive="NEW",
        effective_at="2026-09-13T00:00:00Z",
    )

    resolved = resolve([stale, current])

    assert [
        item.instruction_id
        for item in resolved.active_instructions
    ] == ["CURRENT"]


def test_unresolved_active_conflict_fails_closed():
    with pytest.raises(
        GovernanceError,
        match="CONFLICTING_ACTIVE_INSTRUCTIONS",
    ):
        resolve(
            [
                record(
                    "A",
                    directive="A",
                ),
                record(
                    "B",
                    directive="B",
                ),
            ]
        )


def test_untrusted_active_source_fails_closed():
    with pytest.raises(
        GovernanceError,
        match="UNTRUSTED_ACTIVE_INSTRUCTION_SOURCE",
    ):
        resolve(
            [
                record(
                    "CHAT",
                    source="CHAT_MEMORY",
                )
            ]
        )


def test_project_local_instruction_does_not_leak():
    global_record = record(
        "GLOBAL",
        project="*",
        conflict_key="GLOBAL_POLICY",
    )

    foreign = record(
        "FOREIGN",
        project="OTHER_PROJECT",
        conflict_key="FOREIGN_POLICY",
    )

    resolved = resolve(
        [global_record, foreign]
    )

    assert {
        item.instruction_id
        for item in resolved.active_instructions
    } == {"GLOBAL"}

    assert any(
        item.instruction_id == "FOREIGN"
        and item.reason == "PROJECT_NOT_APPLICABLE"
        for item in resolved.exclusions
    )


def test_same_directive_uses_authority_effective_version_precedence():
    lower = record(
        "LOWER",
        directive="SAME",
        authority_rank=10,
        effective_at="2026-09-12T00:00:00Z",
    )

    higher = record(
        "HIGHER",
        directive="SAME",
        authority_rank=100,
        effective_at="2026-09-13T00:00:00Z",
    )

    resolved = resolve([lower, higher])

    assert [
        item.instruction_id
        for item in resolved.active_instructions
    ] == ["HIGHER"]


def test_bootstrap_envelope_binds_instruction_state_authority_and_knowledge():
    envelope = build_pre_l5_bootstrap_envelope(
        authority_package=package(),
        instruction_records=[
            record("CURRENT"),
        ],
        knowledge_gate=knowledge_gate(),
    )

    assert envelope.execution_admission == "READY"
    assert (
        envelope.active_instruction_set.project_id
        == envelope.authority_package.project_id
    )
    assert (
        envelope.active_instruction_set.state_package_id
        == envelope.authority_package.state_package_id
    )
    assert (
        envelope.active_instruction_set.authority_reference
        == envelope.authority_package.authority_reference
    )


def test_known_relevant_lesson_reuse_is_mandatory():
    with pytest.raises(ValidationError):
        PreExecutionKnowledgeGateV1(
            project_id=PROJECT,
            task_id=TASK,
            active_lesson_ids=("LESSON-1",),
            known_failure_fingerprint_ids=("FP-1",),
            applicable_skill_ids=("SKILL-1",),
            preventive_gate_ids=("GATE-1",),
            known_relevant_lessons_reused=False,
        )


def test_restart_resume_preserves_current_resolved_set_digest():
    original = build_pre_l5_bootstrap_envelope(
        authority_package=package(),
        instruction_records=[
            record("CURRENT"),
            record(
                "OLD",
                status="HISTORICAL",
            ),
        ],
        knowledge_gate=knowledge_gate(),
    )

    resumed = (
        PreL5WorkspaceBootstrapEnvelopeV1
        .model_validate_json(
            original.model_dump_json()
        )
    )

    assert (
        resumed.active_instruction_set.resolution_sha256
        == original.active_instruction_set.resolution_sha256
    )

    assert {
        item.instruction_id
        for item in (
            resumed
            .active_instruction_set
            .active_instructions
        )
    } == {"CURRENT"}


def test_empty_active_set_fails_closed():
    with pytest.raises(
        GovernanceError,
        match="ACTIVE_GOVERNING_INSTRUCTION_SET_EMPTY",
    ):
        resolve(
            [
                record(
                    "OLD",
                    status="HISTORICAL",
                )
            ]
        )

def test_explicit_superseded_status_is_not_executable():
    superseded = record(
        "SUPERSEDED",
        status="SUPERSEDED",
    )
    current = record(
        "CURRENT",
        conflict_key="CURRENT_POLICY",
    )

    resolved = resolve([superseded, current])
    reasons = {
        item.instruction_id: item.reason
        for item in resolved.exclusions
    }
    assert reasons["SUPERSEDED"] == "STATUS_SUPERSEDED_EXCLUDED"


def test_same_directive_newer_effective_at_wins_when_authority_equal():
    older = record(
        "OLDER",
        directive="SAME",
        authority_rank=100,
        effective_at="2026-09-12T00:00:00Z",
    )
    newer = record(
        "NEWER",
        directive="SAME",
        authority_rank=100,
        effective_at="2026-09-13T00:00:00Z",
    )

    resolved = resolve([older, newer])
    assert [item.instruction_id for item in resolved.active_instructions] == ["NEWER"]


def test_same_directive_natural_version_precedence_v10_over_v9():
    v9 = record(
        "V9",
        directive="SAME",
        authority_rank=100,
        effective_at="2026-09-13T00:00:00Z",
        version="V9",
    )
    v10 = record(
        "V10",
        directive="SAME",
        authority_rank=100,
        effective_at="2026-09-13T00:00:00Z",
        version="V10",
    )

    resolved = resolve([v9, v10])
    assert [item.instruction_id for item in resolved.active_instructions] == ["V10"]


def test_same_directive_higher_authority_wins_even_if_older():
    lower_newer = record(
        "LOWER-NEWER",
        directive="SAME",
        authority_rank=10,
        effective_at="2026-09-14T00:00:00Z",
    )
    higher_older = record(
        "HIGHER-OLDER",
        directive="SAME",
        authority_rank=100,
        effective_at="2026-09-12T00:00:00Z",
    )

    resolved = resolve([lower_newer, higher_older])
    assert [item.instruction_id for item in resolved.active_instructions] == ["HIGHER-OLDER"]
