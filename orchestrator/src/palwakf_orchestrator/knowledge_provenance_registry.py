from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.decision_registry import (
    DecisionStatus,
    DecisionSupersessionRegistryV1,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

STATE_KEY = "pre_l5_knowledge_provenance_registry_v1"


class ClaimStatus(StrEnum):
    current = "CURRENT"
    superseded = "SUPERSEDED"
    rejected = "REJECTED"


class PromotionStatus(StrEnum):
    candidate = "CANDIDATE"
    review_required = "REVIEW_REQUIRED"
    accepted_project_knowledge = "ACCEPTED_PROJECT_KNOWLEDGE"
    rejected = "REJECTED"


class ProvenanceReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=300)
    source_kind: str = Field(min_length=1, max_length=100)
    source_revision: str = Field(min_length=1, max_length=500)
    evidence_reference: str = Field(min_length=1, max_length=1000)


class KnowledgeClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1, max_length=200)
    claim_key: str = Field(min_length=1, max_length=300)
    statement: str = Field(min_length=1, max_length=10_000)
    project_id: str = Field(min_length=1, max_length=200)
    status: ClaimStatus
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: tuple[ProvenanceReferenceV1, ...] = Field(min_length=1, max_length=64)
    conflicts_with: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    promotion_status: PromotionStatus
    promotion_reference: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.claim_id in self.conflicts_with:
            raise ValueError("KNOWLEDGE_CLAIM_SELF_CONFLICT")
        if self.claim_id in self.supersedes:
            raise ValueError("KNOWLEDGE_CLAIM_SELF_SUPERSESSION")
        if len(set(self.conflicts_with)) != len(self.conflicts_with):
            raise ValueError("KNOWLEDGE_CLAIM_DUPLICATE_CONFLICT")
        if len(set(self.supersedes)) != len(self.supersedes):
            raise ValueError("KNOWLEDGE_CLAIM_DUPLICATE_SUPERSESSION")
        if (
            self.status == ClaimStatus.rejected
            and self.promotion_status != PromotionStatus.rejected
        ):
            raise ValueError("KNOWLEDGE_REJECTED_CLAIM_PROMOTION_STATUS_MISMATCH")
        if (
            self.promotion_status
            in {PromotionStatus.accepted_project_knowledge, PromotionStatus.rejected}
            and not (self.promotion_reference or "").strip()
        ):
            raise ValueError("KNOWLEDGE_PROMOTION_REFERENCE_REQUIRED")
        return self


class KnowledgeProvenanceRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_KNOWLEDGE_PROVENANCE_REGISTRY_V1"] = (
        "PALWAKF_KNOWLEDGE_PROVENANCE_REGISTRY_V1"
    )
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    source_revision: str = Field(min_length=1, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=1000)
    imported_at: datetime
    claims: tuple[KnowledgeClaimV1, ...] = Field(min_length=1)
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        by_id = {claim.claim_id: claim for claim in self.claims}
        if len(by_id) != len(self.claims):
            raise ValueError("KNOWLEDGE_REGISTRY_DUPLICATE_CLAIM_ID")
        self._validate_references(by_id)
        self._validate_supersession(by_id)
        self._validate_hash()
        return self

    def _validate_references(self, by_id: dict[str, KnowledgeClaimV1]) -> None:
        for claim in self.claims:
            for other_id in claim.conflicts_with:
                other = by_id.get(other_id)
                if other is None:
                    raise ValueError("KNOWLEDGE_REGISTRY_UNKNOWN_CONFLICT_TARGET")
                if claim.claim_id not in other.conflicts_with:
                    raise ValueError("KNOWLEDGE_REGISTRY_CONFLICT_NOT_RECIPROCAL")
            for target_id in claim.supersedes:
                target = by_id.get(target_id)
                if target is None:
                    raise ValueError("KNOWLEDGE_REGISTRY_UNKNOWN_SUPERSESSION_TARGET")
                if target.claim_key != claim.claim_key or target.project_id != claim.project_id:
                    raise ValueError("KNOWLEDGE_REGISTRY_CROSS_CLAIM_SUPERSESSION")
                if target.status != ClaimStatus.superseded:
                    raise ValueError("KNOWLEDGE_REGISTRY_TARGET_NOT_SUPERSEDED")

    def _validate_supersession(self, by_id: dict[str, KnowledgeClaimV1]) -> None:
        referenced = {target for claim in self.claims for target in claim.supersedes}
        for claim in self.claims:
            if claim.status == ClaimStatus.superseded and claim.claim_id not in referenced:
                raise ValueError("KNOWLEDGE_REGISTRY_UNLINKED_SUPERSEDED_CLAIM")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visiting:
                raise ValueError("KNOWLEDGE_REGISTRY_SUPERSESSION_CYCLE")
            if claim_id in visited:
                return
            visiting.add(claim_id)
            for target in by_id[claim_id].supersedes:
                visit(target)
            visiting.remove(claim_id)
            visited.add(claim_id)

        for claim_id in by_id:
            visit(claim_id)

    def _validate_hash(self) -> None:
        if self.registry_sha256 != _sha256(
            _snapshot_payload(
                source_revision=self.source_revision,
                authority_reference=self.authority_reference,
                claims=self.claims,
            )
        ):
            raise ValueError("KNOWLEDGE_REGISTRY_HASH_MISMATCH")

    def get(self, claim_id: str) -> KnowledgeClaimV1:
        for claim in self.claims:
            if claim.claim_id == claim_id:
                return claim
        raise GovernanceError("KNOWLEDGE_CLAIM_NOT_FOUND")

    def claims_for_project(self, project_id: str) -> tuple[KnowledgeClaimV1, ...]:
        return tuple(
            sorted(
                (claim for claim in self.claims if claim.project_id == project_id),
                key=lambda item: (item.claim_key, item.claim_id),
            )
        )

    def conflicts_for_claim(self, claim_id: str) -> tuple[KnowledgeClaimV1, ...]:
        claim = self.get(claim_id)
        return tuple(self.get(other_id) for other_id in claim.conflicts_with)

    def lineage(self, *, project_id: str, claim_key: str) -> tuple[KnowledgeClaimV1, ...]:
        return tuple(
            claim for claim in self.claims_for_project(project_id) if claim.claim_key == claim_key
        )

    def promotion_candidates(self, project_id: str) -> tuple[KnowledgeClaimV1, ...]:
        return tuple(
            claim
            for claim in self.claims_for_project(project_id)
            if claim.status == ClaimStatus.current
            and claim.promotion_status
            in {PromotionStatus.candidate, PromotionStatus.review_required}
        )



def require_governed_promotion_decision(
    claim: KnowledgeClaimV1,
    decision_registry: DecisionSupersessionRegistryV1 | None,
) -> None:
    if claim.promotion_status != PromotionStatus.accepted_project_knowledge:
        return
    if decision_registry is None:
        raise GovernanceError("GOVERNED_KNOWLEDGE_PROMOTION_DECISION_REQUIRED")
    reference = claim.promotion_reference or ""
    if not reference.startswith("DECISION://"):
        raise GovernanceError("KNOWLEDGE_PROMOTION_DECISION_REFERENCE_REQUIRED")
    decision_id = reference.removeprefix("DECISION://")
    decision = decision_registry.get(decision_id)
    if decision.status != DecisionStatus.current:
        raise GovernanceError("KNOWLEDGE_PROMOTION_DECISION_NOT_CURRENT")
    projects = set(decision.applies_to_projects)
    if "*" not in projects and claim.project_id not in projects:
        raise GovernanceError("KNOWLEDGE_PROMOTION_DECISION_PROJECT_MISMATCH")
    expected_key = f"KNOWLEDGE_PROMOTION::{claim.project_id}::{claim.claim_key}"
    if decision.conflict_key != expected_key:
        raise GovernanceError("KNOWLEDGE_PROMOTION_DECISION_KEY_MISMATCH")
    if f"knowledge-claim:{claim.claim_id}" not in decision.evidence:
        raise GovernanceError("KNOWLEDGE_PROMOTION_DECISION_CLAIM_EVIDENCE_REQUIRED")

def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _snapshot_payload(
    *,
    source_revision: str,
    authority_reference: str,
    claims: tuple[KnowledgeClaimV1, ...],
) -> dict[str, object]:
    return {
        "registry_id": "PALWAKF_KNOWLEDGE_PROVENANCE_REGISTRY_V1",
        "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
        "source_revision": source_revision,
        "authority_reference": authority_reference,
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "canonical_promotion_allowed": False,
    }


def build_knowledge_registry_snapshot(
    *,
    source_revision: str,
    authority_reference: str,
    claims: tuple[KnowledgeClaimV1, ...],
    imported_at: datetime | None = None,
) -> KnowledgeProvenanceRegistryV1:
    payload = _snapshot_payload(
        source_revision=source_revision,
        authority_reference=authority_reference,
        claims=claims,
    )
    return KnowledgeProvenanceRegistryV1(
        source_revision=source_revision,
        authority_reference=authority_reference,
        imported_at=imported_at or datetime.now(UTC),
        claims=claims,
        registry_sha256=_sha256(payload),
    )


class KnowledgeProvenanceRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def history(self) -> tuple[KnowledgeProvenanceRegistryV1, ...]:
        state = self._state_store.load()
        raw = state.get(STATE_KEY, {})
        snapshots = raw.get("snapshots", []) if isinstance(raw, dict) else []
        if not isinstance(snapshots, list):
            raise GovernanceError("KNOWLEDGE_REGISTRY_STORE_CORRUPT")
        return tuple(KnowledgeProvenanceRegistryV1.model_validate(item) for item in snapshots)

    def current(self) -> KnowledgeProvenanceRegistryV1:
        history = self.history()
        if not history:
            raise GovernanceError("KNOWLEDGE_REGISTRY_NOT_IMPORTED")
        return history[-1]

    def import_snapshot(
        self,
        *,
        source_revision: str,
        authority_reference: str,
        claims: tuple[KnowledgeClaimV1, ...],
        decision_registry: DecisionSupersessionRegistryV1 | None = None,
    ) -> KnowledgeProvenanceRegistryV1:
        for claim in claims:
            require_governed_promotion_decision(claim, decision_registry)
        snapshot = build_knowledge_registry_snapshot(
            source_revision=source_revision,
            authority_reference=authority_reference,
            claims=claims,
            imported_at=self._now(),
        )
        history = list(self.history())
        for existing in history:
            if existing.source_revision != source_revision:
                continue
            if existing.registry_sha256 != snapshot.registry_sha256:
                raise GovernanceError("KNOWLEDGE_REGISTRY_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(snapshot)
        state = self._state_store.load()
        state[STATE_KEY] = {
            "registry_version": "PALWAKF_KNOWLEDGE_PROVENANCE_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_QUERY_PROJECTION_ONLY",
            "canonical_promotion_allowed": False,
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return snapshot
