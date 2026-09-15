from __future__ import annotations

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.external_skill_admission import (
    SkillAdmissionCandidate,
    SkillAdmissionStage,
    assert_skill_loadable,
)
from palwakf_orchestrator.persistence import StateStore

EXTERNAL_SKILLS_KEY = "engineering_os_external_skill_admissions_v1"


_ALLOWED_TRANSITIONS: dict[SkillAdmissionStage, set[SkillAdmissionStage]] = {
    SkillAdmissionStage.quarantined: {SkillAdmissionStage.discovered, SkillAdmissionStage.rejected},
    SkillAdmissionStage.discovered: {
        SkillAdmissionStage.source_verified,
        SkillAdmissionStage.hold,
        SkillAdmissionStage.rejected,
    },
    SkillAdmissionStage.source_verified: {
        SkillAdmissionStage.license_verified,
        SkillAdmissionStage.hold,
        SkillAdmissionStage.rejected,
    },
    SkillAdmissionStage.license_verified: {
        SkillAdmissionStage.security_reviewed,
        SkillAdmissionStage.hold,
        SkillAdmissionStage.rejected,
    },
    SkillAdmissionStage.security_reviewed: {
        SkillAdmissionStage.sandbox_only,
        SkillAdmissionStage.hold,
        SkillAdmissionStage.rejected,
    },
    SkillAdmissionStage.sandbox_only: {
        SkillAdmissionStage.project_proven,
        SkillAdmissionStage.hold,
        SkillAdmissionStage.rejected,
    },
    SkillAdmissionStage.project_proven: {
        SkillAdmissionStage.cross_project_candidate,
        SkillAdmissionStage.revoked,
    },
    SkillAdmissionStage.cross_project_candidate: {
        SkillAdmissionStage.canonical_approved,
        SkillAdmissionStage.revoked,
    },
    SkillAdmissionStage.canonical_approved: {SkillAdmissionStage.revoked},
    SkillAdmissionStage.hold: {SkillAdmissionStage.discovered, SkillAdmissionStage.rejected},
    SkillAdmissionStage.rejected: set(),
    SkillAdmissionStage.revoked: set(),
}


class ExternalSkillAdmissionService:
    def __init__(self, state_store: StateStore) -> None:
        self.state_store = state_store

    def list(self) -> list[SkillAdmissionCandidate]:
        state = self.state_store.load()
        raw = state.get(EXTERNAL_SKILLS_KEY, {})
        return sorted(
            (SkillAdmissionCandidate.model_validate(item) for item in raw.values()),
            key=lambda item: item.skill_id,
        )

    def get(self, skill_id: str) -> SkillAdmissionCandidate:
        for item in self.list():
            if item.skill_id == skill_id:
                return item
        raise GovernanceError("EXTERNAL_SKILL_NOT_FOUND")

    def register(self, candidate: SkillAdmissionCandidate) -> SkillAdmissionCandidate:
        if candidate.stage != SkillAdmissionStage.quarantined:
            raise GovernanceError("EXTERNAL_SKILL_MUST_ENTER_QUARANTINE")
        state = self.state_store.load()
        raw = dict(state.get(EXTERNAL_SKILLS_KEY, {}))
        if candidate.skill_id in raw:
            raise GovernanceError("EXTERNAL_SKILL_ALREADY_REGISTERED")
        raw[candidate.skill_id] = candidate.model_dump(mode="json")
        state[EXTERNAL_SKILLS_KEY] = raw
        self.state_store.save(state)
        return candidate

    def transition(self, skill_id: str, stage: SkillAdmissionStage) -> SkillAdmissionCandidate:
        current = self.get(skill_id)
        if stage not in _ALLOWED_TRANSITIONS[current.stage]:
            raise GovernanceError("EXTERNAL_SKILL_INVALID_ADMISSION_TRANSITION")
        updated = current.model_copy(update={"stage": stage})
        if stage in {
            SkillAdmissionStage.project_proven,
            SkillAdmissionStage.cross_project_candidate,
            SkillAdmissionStage.canonical_approved,
        }:
            assert_skill_loadable(updated)
        state = self.state_store.load()
        raw = dict(state.get(EXTERNAL_SKILLS_KEY, {}))
        raw[skill_id] = updated.model_dump(mode="json")
        state[EXTERNAL_SKILLS_KEY] = raw
        self.state_store.save(state)
        return updated

    def require_loadable(self, skill_id: str) -> SkillAdmissionCandidate:
        candidate = self.get(skill_id)
        assert_skill_loadable(candidate)
        return candidate
