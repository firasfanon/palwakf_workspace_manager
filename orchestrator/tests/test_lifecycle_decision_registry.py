from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.lifecycle_decision_registry import (
    REGISTRY_STATE_KEY,
    LifecycleDecisionRecordV1,
    LifecycleDecisionRegistryStore,
    LifecycleDisposition,
    LifecycleRecordStatus,
    LifecycleStage,
    build_lifecycle_decision_registry,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore

REV = "drive-revision-020"
AUTH = "PREL5-020-AUTHORITY"
NOW = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)
PROJECT = "PALWAKF_WORKSPACE_MANAGER"
SHA = "a" * 40


def _record(
    stage: LifecycleStage,
    *,
    disposition: LifecycleDisposition = LifecycleDisposition.approved,
    suffix: str = "1",
    sha: str = SHA,
) -> LifecycleDecisionRecordV1:
    return LifecycleDecisionRecordV1(
        decision_id=f"decision-{stage.value.lower()}-{suffix}",
        project_id=PROJECT,
        stage=stage,
        subject_sha=sha,
        disposition=disposition,
        status=LifecycleRecordStatus.current,
        source_revision=REV,
        authority_reference=AUTH,
        decided_at=NOW,
        decided_by="workspace-control-plane",
        evidence=(f"evidence:{stage.value}",),
    )


def _registry(*records: LifecycleDecisionRecordV1):
    return build_lifecycle_decision_registry(
        source_revision=REV,
        authority_reference=AUTH,
        records=tuple(records),
        imported_at=NOW,
    )


def test_merge_approval_does_not_implicitly_authorize_baseline() -> None:
    registry = _registry(_record(LifecycleStage.main_merge))
    assert (
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.main_merge,
            subject_sha=SHA,
        ).stage
        == LifecycleStage.main_merge
    )
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_MISSING"):
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.baseline_promotion,
            subject_sha=SHA,
        )


def test_each_release_stage_requires_its_own_approval() -> None:
    registry = _registry(
        _record(LifecycleStage.baseline_promotion),
        _record(LifecycleStage.deployment_acceptance),
    )
    assert (
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.baseline_promotion,
            subject_sha=SHA,
        ).disposition
        == LifecycleDisposition.approved
    )
    assert (
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.deployment_acceptance,
            subject_sha=SHA,
        ).disposition
        == LifecycleDisposition.approved
    )
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_MISSING"):
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.production_acceptance,
            subject_sha=SHA,
        )


def test_rejected_decision_fails_closed() -> None:
    registry = _registry(
        _record(
            LifecycleStage.integration_acceptance,
            disposition=LifecycleDisposition.rejected,
        )
    )
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_NOT_APPROVED"):
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.integration_acceptance,
            subject_sha=SHA,
        )


def test_project_and_sha_are_exact_bindings() -> None:
    registry = _registry(_record(LifecycleStage.main_merge))
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_MISSING"):
        registry.require_approved(
            project_id="OTHER_PROJECT",
            stage=LifecycleStage.main_merge,
            subject_sha=SHA,
        )
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_MISSING"):
        registry.require_approved(
            project_id=PROJECT,
            stage=LifecycleStage.main_merge,
            subject_sha="b" * 40,
        )


def test_multiple_current_decisions_for_same_stage_and_sha_are_rejected() -> None:
    with pytest.raises(ValueError, match="LIFECYCLE_DECISION_MULTIPLE_CURRENT"):
        _registry(
            _record(LifecycleStage.main_merge, suffix="1"),
            _record(LifecycleStage.main_merge, suffix="2"),
        )


def test_sqlite_restart_persists_registry(tmp_path) -> None:
    db = tmp_path / "state.sqlite3"
    first = LifecycleDecisionRegistryStore(SQLiteStateStore(db), now=lambda: NOW)
    created = first.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=(_record(LifecycleStage.main_merge),),
    )
    restarted = LifecycleDecisionRegistryStore(SQLiteStateStore(db), now=lambda: NOW)
    assert restarted.current() == created


def test_same_source_revision_replay_is_idempotent() -> None:
    store = LifecycleDecisionRegistryStore(MemoryStateStore(), now=lambda: NOW)
    record = _record(LifecycleStage.main_merge)
    first = store.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=(record,),
    )
    second = store.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=(record,),
    )
    assert second == first


def test_same_source_revision_with_changed_content_fails_closed() -> None:
    store = LifecycleDecisionRegistryStore(MemoryStateStore(), now=lambda: NOW)
    store.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=(_record(LifecycleStage.main_merge),),
    )
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_SOURCE_REVISION_CONFLICT"):
        store.import_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=(_record(LifecycleStage.baseline_promotion),),
        )


def test_persisted_registry_hash_tampering_is_rejected() -> None:
    state_store = MemoryStateStore()
    store = LifecycleDecisionRegistryStore(state_store, now=lambda: NOW)
    store.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=(_record(LifecycleStage.main_merge),),
    )
    state = state_store.load()
    state[REGISTRY_STATE_KEY]["snapshots"][0]["registry_sha256"] = "0" * 64
    state_store.save(state)
    with pytest.raises(GovernanceError, match="LIFECYCLE_DECISION_REGISTRY_HASH_MISMATCH"):
        store.current()
