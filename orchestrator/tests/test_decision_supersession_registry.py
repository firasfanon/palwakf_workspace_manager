from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.decision_registry import (
    DecisionRecordV1,
    DecisionStatus,
    DecisionSupersessionRegistryStore,
    build_decision_registry_snapshot,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.pre_l5_instruction_resolver import (
    ActiveInstructionResolverV1,
    InstructionRecordV1,
)

PROJECT = "PALWAKF_WORKSPACE_MANAGER"
AUTH = "AUTH:PREL5-BATCH"
REV = "DRIVE-REV-001"
NOW = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)


def fp(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def decision(
    decision_id: str,
    *,
    status: DecisionStatus,
    version: str,
    effective_at: datetime,
    directive: str,
    supersedes: tuple[str, ...] = (),
    conflict_key: str = "POLICY",
    instruction_ids: tuple[str, ...] = (),
    project: str = PROJECT,
    source_revision: str = REV,
) -> DecisionRecordV1:
    return DecisionRecordV1(
        decision_id=decision_id,
        conflict_key=conflict_key,
        version=version,
        effective_at=effective_at,
        status=status,
        authority="WORKSPACE_CONTROL_PLANE",
        source_revision=source_revision,
        authority_reference=AUTH,
        evidence=(f"evidence:{decision_id}",),
        applies_to_projects=(project,),
        supersedes=supersedes,
        instruction_ids=instruction_ids,
        directive_fingerprint=fp(directive),
    )


def valid_records() -> tuple[DecisionRecordV1, ...]:
    old = decision(
        "DEC-1",
        status=DecisionStatus.superseded,
        version="V1",
        effective_at=datetime(2026, 9, 10, tzinfo=UTC),
        directive="OLD",
        instruction_ids=("OLD-INSTRUCTION",),
    )
    current = decision(
        "DEC-2",
        status=DecisionStatus.current,
        version="V2",
        effective_at=NOW,
        directive="CURRENT",
        supersedes=("DEC-1",),
        instruction_ids=("CURRENT-INSTRUCTION",),
    )
    return (old, current)


def registry():
    return build_decision_registry_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=valid_records(),
        imported_at=NOW,
    )


def instruction(
    instruction_id: str,
    *,
    decision_id: str | None,
    version: str,
    directive: str,
) -> InstructionRecordV1:
    return InstructionRecordV1(
        instruction_id=instruction_id,
        authority="WORKSPACE_CONTROL_PLANE",
        authority_rank=100,
        version=version,
        decision_id=decision_id,
        effective_at=NOW,
        status="ACTIVE",
        source_authority="WORKSPACE_DRIVE_SOVEREIGN",
        applies_to_projects=(PROJECT,),
        conflict_key="POLICY",
        directive_fingerprint=fp(directive),
    )


def resolve(records: list[InstructionRecordV1]):
    return ActiveInstructionResolverV1().resolve(
        project_id=PROJECT,
        task_id="TASK-010",
        state_package_id="STATE-010",
        authority_reference=AUTH,
        records=records,
        decision_registry=registry(),
    )


def test_registry_selects_only_current_decision_for_project() -> None:
    current = registry().current_for_project(PROJECT)
    assert [item.decision_id for item in current] == ["DEC-2"]
    assert current[0].evidence == ("evidence:DEC-2",)
    assert registry().canonical_promotion_allowed is False


def test_registry_rejects_multiple_current_decisions_for_same_key() -> None:
    first = decision(
        "DEC-A",
        status=DecisionStatus.current,
        version="V1",
        effective_at=NOW,
        directive="A",
    )
    second = decision(
        "DEC-B",
        status=DecisionStatus.current,
        version="V2",
        effective_at=NOW,
        directive="B",
    )
    with pytest.raises(ValidationError, match="MULTIPLE_CURRENT_DECISIONS"):
        build_decision_registry_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=(first, second),
            imported_at=NOW,
        )


def test_registry_rejects_unlinked_superseded_decision() -> None:
    stale = decision(
        "DEC-STALE",
        status=DecisionStatus.superseded,
        version="V1",
        effective_at=datetime(2026, 9, 10, tzinfo=UTC),
        directive="OLD",
    )
    with pytest.raises(ValidationError, match="UNLINKED_SUPERSEDED_DECISION"):
        build_decision_registry_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=(stale,),
            imported_at=NOW,
        )


def test_registry_rejects_cross_key_supersession() -> None:
    old = decision(
        "DEC-OLD",
        status=DecisionStatus.superseded,
        version="V1",
        effective_at=datetime(2026, 9, 10, tzinfo=UTC),
        directive="OLD",
        conflict_key="OLD-KEY",
    )
    current = decision(
        "DEC-CURRENT",
        status=DecisionStatus.current,
        version="V2",
        effective_at=NOW,
        directive="CURRENT",
        supersedes=("DEC-OLD",),
        conflict_key="NEW-KEY",
    )
    with pytest.raises(ValidationError, match="CROSS_KEY_SUPERSESSION"):
        build_decision_registry_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=(old, current),
            imported_at=NOW,
        )


def test_registry_rejects_non_forward_supersession() -> None:
    old = decision(
        "DEC-OLD",
        status=DecisionStatus.superseded,
        version="V1",
        effective_at=NOW,
        directive="OLD",
    )
    current = decision(
        "DEC-CURRENT",
        status=DecisionStatus.current,
        version="V2",
        effective_at=datetime(2026, 9, 15, tzinfo=UTC),
        directive="CURRENT",
        supersedes=("DEC-OLD",),
    )
    with pytest.raises(ValidationError, match="NON_FORWARD_SUPERSESSION"):
        build_decision_registry_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=(old, current),
            imported_at=NOW,
        )


def test_store_persists_and_idempotently_replays_same_revision() -> None:
    state = MemoryStateStore()
    store = DecisionSupersessionRegistryStore(state, now=lambda: NOW)
    first = store.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=valid_records(),
    )
    restored = DecisionSupersessionRegistryStore(state, now=lambda: NOW)
    replay = restored.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=valid_records(),
    )
    assert replay.registry_sha256 == first.registry_sha256
    assert restored.current().registry_sha256 == first.registry_sha256
    assert len(restored.history()) == 1


def test_store_rejects_same_revision_with_different_content() -> None:
    state = MemoryStateStore()
    store = DecisionSupersessionRegistryStore(state, now=lambda: NOW)
    store.import_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=valid_records(),
    )
    changed = list(valid_records())
    changed[1] = changed[1].model_copy(update={"evidence": ("evidence:changed",)})
    with pytest.raises(GovernanceError, match="SOURCE_REVISION_CONFLICT"):
        store.import_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=tuple(changed),
        )


def test_resolver_excludes_instruction_bound_to_superseded_decision() -> None:
    old = instruction(
        "OLD-INSTRUCTION",
        decision_id="DEC-1",
        version="V1",
        directive="OLD",
    )
    current = instruction(
        "CURRENT-INSTRUCTION",
        decision_id="DEC-2",
        version="V2",
        directive="CURRENT",
    )
    resolved = resolve([old, current])
    assert [item.instruction_id for item in resolved.active_instructions] == ["CURRENT-INSTRUCTION"]
    reasons = {item.instruction_id: item.reason for item in resolved.exclusions}
    assert reasons["OLD-INSTRUCTION"] == "DECISION_SUPERSEDED_EXCLUDED"


def test_resolver_requires_decision_binding_when_registry_is_supplied() -> None:
    unbound = instruction(
        "CURRENT-INSTRUCTION",
        decision_id=None,
        version="V2",
        directive="CURRENT",
    )
    with pytest.raises(
        GovernanceError,
        match="ACTIVE_INSTRUCTION_DECISION_BINDING_REQUIRED",
    ):
        resolve([unbound])


def test_resolver_rejects_instruction_decision_fingerprint_drift() -> None:
    drifted = instruction(
        "CURRENT-INSTRUCTION",
        decision_id="DEC-2",
        version="V2",
        directive="DIFFERENT",
    )
    with pytest.raises(
        GovernanceError,
        match="DECISION_DIRECTIVE_FINGERPRINT_MISMATCH",
    ):
        resolve([drifted])


def test_registry_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        DecisionRecordV1(
            decision_id="DEC-NO-EVIDENCE",
            conflict_key="POLICY",
            version="V1",
            effective_at=NOW,
            status=DecisionStatus.current,
            authority="WORKSPACE_CONTROL_PLANE",
            source_revision=REV,
            authority_reference=AUTH,
            evidence=(),
            applies_to_projects=(PROJECT,),
            instruction_ids=("CURRENT-INSTRUCTION",),
            directive_fingerprint=fp("CURRENT"),
        )


def test_registry_allows_same_key_current_decisions_for_disjoint_projects() -> None:
    first = decision(
        "DEC-A",
        status=DecisionStatus.current,
        version="V1",
        effective_at=NOW,
        directive="A",
        project="PROJECT-A",
    )
    second = decision(
        "DEC-B",
        status=DecisionStatus.current,
        version="V1",
        effective_at=NOW,
        directive="B",
        project="PROJECT-B",
    )
    snapshot = build_decision_registry_snapshot(
        source_revision=REV,
        authority_reference=AUTH,
        records=(first, second),
        imported_at=NOW,
    )
    assert [item.decision_id for item in snapshot.current_for_project("PROJECT-A")] == ["DEC-A"]


def test_registry_rejects_cross_project_supersession() -> None:
    old = decision(
        "DEC-OLD-PROJECT-B",
        status=DecisionStatus.superseded,
        version="V1",
        effective_at=datetime(2026, 9, 10, tzinfo=UTC),
        directive="OLD-B",
        project="PROJECT-B",
    )
    current = decision(
        "DEC-CURRENT-PROJECT-A",
        status=DecisionStatus.current,
        version="V2",
        effective_at=NOW,
        directive="CURRENT-A",
        supersedes=("DEC-OLD-PROJECT-B",),
        project="PROJECT-A",
    )
    with pytest.raises(ValidationError, match="CROSS_PROJECT_SUPERSESSION"):
        build_decision_registry_snapshot(
            source_revision=REV,
            authority_reference=AUTH,
            records=(old, current),
            imported_at=NOW,
        )
