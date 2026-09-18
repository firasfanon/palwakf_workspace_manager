from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.knowledge_provenance_registry import (
    ClaimStatus,
    KnowledgeClaimV1,
    KnowledgeProvenanceRegistryStore,
    KnowledgeProvenanceRegistryV1,
    PromotionStatus,
    ProvenanceReferenceV1,
    build_knowledge_registry_snapshot,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore


def provenance(source_id: str = "drive-doc-1") -> tuple[ProvenanceReferenceV1, ...]:
    return (
        ProvenanceReferenceV1(
            source_id=source_id,
            source_kind="WORKSPACE_DRIVE_DOC",
            source_revision="rev-1",
            evidence_reference=f"drive://{source_id}#claim",
        ),
    )


def claim(
    claim_id: str,
    *,
    claim_key: str = "architecture/control-plane",
    statement: str | None = None,
    status: ClaimStatus = ClaimStatus.current,
    confidence: float = 0.95,
    conflicts_with: tuple[str, ...] = (),
    supersedes: tuple[str, ...] = (),
    promotion_status: PromotionStatus = PromotionStatus.candidate,
    promotion_reference: str | None = None,
) -> KnowledgeClaimV1:
    return KnowledgeClaimV1(
        claim_id=claim_id,
        claim_key=claim_key,
        statement=statement or f"Statement for {claim_id}",
        project_id="PALWAKF_WORKSPACE_MANAGER",
        status=status,
        confidence=confidence,
        provenance=provenance(claim_id),
        conflicts_with=conflicts_with,
        supersedes=supersedes,
        promotion_status=promotion_status,
        promotion_reference=promotion_reference,
    )


def snapshot(*claims: KnowledgeClaimV1) -> KnowledgeProvenanceRegistryV1:
    return build_knowledge_registry_snapshot(
        source_revision="drive-rev-1",
        authority_reference="WORKSPACE_DRIVE://KNOWLEDGE_V1",
        claims=tuple(claims),
    )


def test_claim_surface_exposes_provenance_confidence_conflicts_and_promotion() -> None:
    left = claim("claim-a", conflicts_with=("claim-b",))
    right = claim(
        "claim-b",
        conflicts_with=("claim-a",),
        promotion_status=PromotionStatus.review_required,
    )
    registry = snapshot(left, right)

    assert registry.get("claim-a").confidence == 0.95
    assert registry.get("claim-a").provenance[0].source_id == "claim-a"
    assert registry.conflicts_for_claim("claim-a") == (right,)
    assert registry.promotion_candidates("PALWAKF_WORKSPACE_MANAGER") == (left, right)
    assert registry.canonical_promotion_allowed is False


def test_accepted_or_rejected_promotion_requires_reference() -> None:
    with pytest.raises(ValueError, match="KNOWLEDGE_PROMOTION_REFERENCE_REQUIRED"):
        claim(
            "claim-a",
            promotion_status=PromotionStatus.accepted_project_knowledge,
        )


def test_unknown_conflict_target_fails_closed() -> None:
    with pytest.raises(ValueError, match="KNOWLEDGE_REGISTRY_UNKNOWN_CONFLICT_TARGET"):
        snapshot(claim("claim-a", conflicts_with=("missing",)))


def test_nonreciprocal_conflict_fails_closed() -> None:
    with pytest.raises(ValueError, match="KNOWLEDGE_REGISTRY_CONFLICT_NOT_RECIPROCAL"):
        snapshot(
            claim("claim-a", conflicts_with=("claim-b",)),
            claim("claim-b"),
        )


def test_supersession_lineage_is_explicit_and_project_key_bound() -> None:
    old = claim(
        "claim-v1",
        status=ClaimStatus.superseded,
        promotion_status=PromotionStatus.review_required,
    )
    current = claim(
        "claim-v2",
        supersedes=("claim-v1",),
        promotion_status=PromotionStatus.accepted_project_knowledge,
        promotion_reference="drive://promotion/claim-v2",
    )
    registry = snapshot(old, current)

    assert registry.lineage(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        claim_key="architecture/control-plane",
    ) == (old, current)


def test_unlinked_superseded_claim_fails_closed() -> None:
    with pytest.raises(ValueError, match="KNOWLEDGE_REGISTRY_UNLINKED_SUPERSEDED_CLAIM"):
        snapshot(
            claim(
                "claim-v1",
                status=ClaimStatus.superseded,
                promotion_status=PromotionStatus.review_required,
            )
        )


def test_registry_hash_tamper_is_rejected() -> None:
    registry = snapshot(claim("claim-a"))
    raw = registry.model_dump(mode="json")
    raw["registry_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="KNOWLEDGE_REGISTRY_HASH_MISMATCH"):
        KnowledgeProvenanceRegistryV1.model_validate(raw)


def test_store_is_idempotent_and_rejects_same_revision_content_drift() -> None:
    store = KnowledgeProvenanceRegistryStore(MemoryStateStore())
    first = store.import_snapshot(
        source_revision="drive-rev-1",
        authority_reference="WORKSPACE_DRIVE://KNOWLEDGE_V1",
        claims=(claim("claim-a"),),
    )
    second = store.import_snapshot(
        source_revision="drive-rev-1",
        authority_reference="WORKSPACE_DRIVE://KNOWLEDGE_V1",
        claims=(claim("claim-a"),),
    )
    assert first == second

    with pytest.raises(GovernanceError, match="KNOWLEDGE_REGISTRY_SOURCE_REVISION_CONFLICT"):
        store.import_snapshot(
            source_revision="drive-rev-1",
            authority_reference="WORKSPACE_DRIVE://KNOWLEDGE_V1",
            claims=(claim("claim-a", confidence=0.5),),
        )


def test_sqlite_restart_preserves_governed_projection(tmp_path: Path) -> None:
    db = tmp_path / "state.sqlite3"
    first_store = KnowledgeProvenanceRegistryStore(SQLiteStateStore(db))
    first_store.import_snapshot(
        source_revision="drive-rev-1",
        authority_reference="WORKSPACE_DRIVE://KNOWLEDGE_V1",
        claims=(claim("claim-a"),),
    )

    restarted = KnowledgeProvenanceRegistryStore(SQLiteStateStore(db))
    restored = restarted.current()

    assert restored.get("claim-a").statement == "Statement for claim-a"
    assert restored.source_authority == "WORKSPACE_DRIVE_SOVEREIGN"
    assert restored.canonical_promotion_allowed is False
