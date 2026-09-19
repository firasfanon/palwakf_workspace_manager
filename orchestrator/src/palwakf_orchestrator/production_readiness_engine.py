from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore, StateStore

SOURCE_AUTHORITY = "WORKSPACE_DRIVE_SOVEREIGN"
STANDARD_ID = "PALWAKF_PRODUCTION_READINESS_STANDARD_V1"
STATE_KEY = "production_readiness_engine_v1"


class ReadinessLevel(StrEnum):
    l0_code = "L0_CODE"
    l1_functional = "L1_FUNCTIONAL"
    l2_product = "L2_PRODUCT"
    l3_integrated = "L3_INTEGRATED"
    l4_operable = "L4_OPERABLE"
    l5_reliable_production = "L5_RELIABLE_PRODUCTION"


_ORDER = tuple(ReadinessLevel)
_PRE_L5_LEVELS = _ORDER[:5]
class ReadinessDimensionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: ReadinessLevel
    evidence: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    passed: bool = False

    @model_validator(mode="after")
    def validate_dimension(self) -> ReadinessDimensionV1:
        for values, code in (
            (self.evidence, "READINESS_EVIDENCE_INVALID"),
            (self.gaps, "READINESS_GAP_INVALID"),
            (self.blockers, "READINESS_BLOCKER_INVALID"),
        ):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError(code)
        if self.passed and (not self.evidence or self.gaps or self.blockers):
            raise ValueError("READINESS_PASS_REQUIRES_EVIDENCE_AND_ZERO_GAPS_BLOCKERS")
        return self


class ProjectReadinessAssessmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    standard_id: Literal["PALWAKF_PRODUCTION_READINESS_STANDARD_V1"] = (
        "PALWAKF_PRODUCTION_READINESS_STANDARD_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    project_id: str = Field(min_length=2, max_length=128)
    dimensions: tuple[ReadinessDimensionV1, ...]
    highest_contiguous_level: ReadinessLevel | None = None
    pre_l5_exit_ready: bool
    production_ready: Literal[False] = False
    production_ready_decision: Literal["NOT_AUTHORIZED_BY_READINESS_ENGINE"] = (
        "NOT_AUTHORIZED_BY_READINESS_ENGINE"
    )
    gaps: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence: tuple[str, ...]
    assessment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_integrity(self) -> ProjectReadinessAssessmentV1:
        levels = tuple(item.level for item in self.dimensions)
        if levels != _ORDER:
            raise ValueError("READINESS_DIMENSIONS_MUST_COVER_L0_TO_L5_IN_ORDER")
        payload = self.model_dump(mode="json", exclude={"assessment_sha256"})
        expected = _hash_payload(payload)
        if self.assessment_sha256 != expected:
            raise ValueError("READINESS_ASSESSMENT_HASH_MISMATCH")
        if self.production_ready:
            raise ValueError("PRODUCTION_READY_MAY_NOT_BE_INFERRED")
        return self


def _hash_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def build_project_readiness_assessment(
    *, project_id: str, dimensions: tuple[ReadinessDimensionV1, ...]
) -> ProjectReadinessAssessmentV1:
    levels = tuple(item.level for item in dimensions)
    if levels != _ORDER:
        raise GovernanceError("READINESS_DIMENSIONS_MUST_COVER_L0_TO_L5_IN_ORDER")

    highest: ReadinessLevel | None = None
    for item in dimensions:
        if not item.passed:
            break
        highest = item.level

    pre_l5_ready = all(item.passed for item in dimensions[: len(_PRE_L5_LEVELS)])
    gaps = tuple(f"{item.level.value}:{gap}" for item in dimensions for gap in item.gaps)
    blockers = tuple(
        f"{item.level.value}:{blocker}" for item in dimensions for blocker in item.blockers
    )
    evidence = tuple(
        f"{item.level.value}:{reference}"
        for item in dimensions
        for reference in item.evidence
    )
    payload: dict[str, object] = {
        "standard_id": STANDARD_ID,
        "source_authority": SOURCE_AUTHORITY,
        "project_id": project_id,
        "dimensions": [item.model_dump(mode="json") for item in dimensions],
        "highest_contiguous_level": highest.value if highest else None,
        "pre_l5_exit_ready": pre_l5_ready,
        "production_ready": False,
        "production_ready_decision": "NOT_AUTHORIZED_BY_READINESS_ENGINE",
        "gaps": list(gaps),
        "blockers": list(blockers),
        "evidence": list(evidence),
    }
    return ProjectReadinessAssessmentV1(
        standard_id="PALWAKF_PRODUCTION_READINESS_STANDARD_V1",
        source_authority="WORKSPACE_DRIVE_SOVEREIGN",
        project_id=project_id,
        dimensions=dimensions,
        highest_contiguous_level=highest,
        pre_l5_exit_ready=pre_l5_ready,
        production_ready=False,
        production_ready_decision="NOT_AUTHORIZED_BY_READINESS_ENGINE",
        gaps=gaps,
        blockers=blockers,
        evidence=evidence,
        assessment_sha256=_hash_payload(payload),
    )


class ProductionReadinessEngine:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store or MemoryStateStore()

    def assess(
        self, *, project_id: str, dimensions: tuple[ReadinessDimensionV1, ...]
    ) -> ProjectReadinessAssessmentV1:
        assessment = build_project_readiness_assessment(
            project_id=project_id,
            dimensions=dimensions,
        )
        state = self._state_store.load()
        registry = state.setdefault(STATE_KEY, {})
        if not isinstance(registry, dict):
            raise GovernanceError("READINESS_STATE_CORRUPT")
        assessments = registry.setdefault("assessments", {})
        if not isinstance(assessments, dict):
            raise GovernanceError("READINESS_ASSESSMENTS_CORRUPT")
        assessments[project_id] = assessment.model_dump(mode="json")
        registry["standard_id"] = STANDARD_ID
        registry["source_authority"] = SOURCE_AUTHORITY
        registry["canonical_promotion_allowed"] = False
        self._state_store.save(state)
        return assessment

    def get(self, project_id: str) -> ProjectReadinessAssessmentV1 | None:
        raw = self._state_store.load().get(STATE_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("READINESS_STATE_CORRUPT")
        assessments = raw.get("assessments", {})
        if not isinstance(assessments, dict):
            raise GovernanceError("READINESS_ASSESSMENTS_CORRUPT")
        value = assessments.get(project_id)
        return ProjectReadinessAssessmentV1.model_validate(value) if value else None

    def require_pre_l5_exit_ready(self, project_id: str) -> ProjectReadinessAssessmentV1:
        assessment = self.get(project_id)
        if assessment is None:
            raise GovernanceError("READINESS_ASSESSMENT_REQUIRED")
        if not assessment.pre_l5_exit_ready:
            raise GovernanceError("PRE_L5_EXIT_READINESS_BLOCKED")
        return assessment
