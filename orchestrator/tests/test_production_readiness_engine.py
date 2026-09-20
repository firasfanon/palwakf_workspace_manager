from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.production_readiness_engine import (
    ProductionReadinessEngine,
    ReadinessDimensionV1,
    ReadinessLevel,
    build_project_readiness_assessment,
)


def _dimension(
    level: ReadinessLevel,
    *,
    passed: bool = True,
    evidence: tuple[str, ...] = ("evidence/ref",),
    gaps: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
) -> ReadinessDimensionV1:
    return ReadinessDimensionV1(
        level=level,
        evidence=evidence,
        gaps=gaps,
        blockers=blockers,
        passed=passed,
    )
def _ready_through_l4() -> tuple[ReadinessDimensionV1, ...]:
    return (
        _dimension(ReadinessLevel.l0_code),
        _dimension(ReadinessLevel.l1_functional),
        _dimension(ReadinessLevel.l2_product),
        _dimension(ReadinessLevel.l3_integrated),
        _dimension(ReadinessLevel.l4_operable),
        _dimension(
            ReadinessLevel.l5_reliable_production,
            passed=False,
            evidence=(),
            gaps=("explicit L5 decision required",),
        ),
    )


def test_l0_to_l4_pass_is_pre_l5_ready_but_never_production_ready() -> None:
    result = build_project_readiness_assessment(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        dimensions=_ready_through_l4(),
    )

    assert result.highest_contiguous_level == ReadinessLevel.l4_operable
    assert result.pre_l5_exit_ready is True
    assert result.production_ready is False
    assert result.production_ready_decision == "NOT_AUTHORIZED_BY_READINESS_ENGINE"
def test_gap_breaks_contiguous_readiness_and_reports_gap() -> None:
    dimensions = list(_ready_through_l4())
    dimensions[2] = _dimension(
        ReadinessLevel.l2_product,
        passed=False,
        evidence=(),
        gaps=("product UAT missing",),
    )
    result = build_project_readiness_assessment(
        project_id="PALWAKF_MIND_ASSISTANT",
        dimensions=tuple(dimensions),
    )

    assert result.highest_contiguous_level == ReadinessLevel.l1_functional
    assert result.pre_l5_exit_ready is False
    assert "L2_PRODUCT:product UAT missing" in result.gaps


def test_blocker_is_reported_and_blocks_pre_l5_exit() -> None:
    dimensions = list(_ready_through_l4())
    dimensions[4] = _dimension(
        ReadinessLevel.l4_operable,
        passed=False,
        evidence=(),
        blockers=("runtime drift unresolved",),
    )
    result = build_project_readiness_assessment(
        project_id="PALWAKF_AGENTIC_AI_SYSTEM",
        dimensions=tuple(dimensions),
    )

    assert result.pre_l5_exit_ready is False
    assert result.blockers == ("L4_OPERABLE:runtime drift unresolved",)
def test_passed_dimension_requires_evidence_and_zero_gaps_blockers() -> None:
    with pytest.raises(ValidationError, match="READINESS_PASS_REQUIRES_EVIDENCE"):
        _dimension(ReadinessLevel.l0_code, evidence=())


def test_dimensions_must_cover_l0_to_l5_exactly_in_order() -> None:
    with pytest.raises(GovernanceError, match="READINESS_DIMENSIONS_MUST_COVER"):
        build_project_readiness_assessment(
            project_id="PALWAKF_WORKSPACE_MANAGER",
            dimensions=_ready_through_l4()[:-1],
        )


def test_engine_persists_and_reloads_assessment() -> None:
    store = MemoryStateStore()
    first = ProductionReadinessEngine(store)
    written = first.assess(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        dimensions=_ready_through_l4(),
    )

    restored = ProductionReadinessEngine(store).get("PALWAKF_WORKSPACE_MANAGER")
    assert restored == written
def test_pre_l5_exit_gate_fails_closed_without_assessment_or_with_gaps() -> None:
    engine = ProductionReadinessEngine(MemoryStateStore())
    with pytest.raises(GovernanceError, match="READINESS_ASSESSMENT_REQUIRED"):
        engine.require_pre_l5_exit_ready("PALWAKF_WORKSPACE_MANAGER")

    dimensions = list(_ready_through_l4())
    dimensions[3] = _dimension(
        ReadinessLevel.l3_integrated,
        passed=False,
        evidence=(),
        gaps=("integration evidence missing",),
    )
    engine.assess(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        dimensions=tuple(dimensions),
    )
    with pytest.raises(GovernanceError, match="PRE_L5_EXIT_READINESS_BLOCKED"):
        engine.require_pre_l5_exit_ready("PALWAKF_WORKSPACE_MANAGER")


def test_pre_l5_exit_gate_passes_for_l0_to_l4_only() -> None:
    engine = ProductionReadinessEngine(MemoryStateStore())
    engine.assess(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        dimensions=_ready_through_l4(),
    )
    result = engine.require_pre_l5_exit_ready("PALWAKF_WORKSPACE_MANAGER")
    assert result.pre_l5_exit_ready is True
    assert result.production_ready is False
def test_persisted_hash_tampering_fails_closed() -> None:
    store = MemoryStateStore()
    engine = ProductionReadinessEngine(store)
    engine.assess(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        dimensions=_ready_through_l4(),
    )
    state = copy.deepcopy(store.load())
    state["production_readiness_engine_v1"]["assessments"][
        "PALWAKF_WORKSPACE_MANAGER"
    ]["gaps"] = ["tampered"]
    store.save(state)

    with pytest.raises(ValidationError, match="READINESS_ASSESSMENT_HASH_MISMATCH"):
        ProductionReadinessEngine(store).get("PALWAKF_WORKSPACE_MANAGER")
