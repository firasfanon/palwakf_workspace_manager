from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.evidence_acceptance_engine import (
    AcceptanceEvidenceV1,
    EvidenceKind,
    EvidenceStatus,
    evaluate_acceptance,
)
from palwakf_orchestrator.failure_retry_guard import (
    FailureRetryGuardStore,
    KnownFailureFingerprintV1,
    build_state_fingerprint,
)
from palwakf_orchestrator.incident_learning_engine import (
    IncidentFailureLearningStore,
    IncidentStatus,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore

PROJECT = "PALWAKF_WORKSPACE_MANAGER"
TASK = "PREL5_035_TEST"
FINGERPRINT = "KNOWN_FAILURE_X"
OBSERVATION = "OBS-PREL5-035-001"
STATE = build_state_fingerprint({"head": "a" * 40, "provider": "native"})


def fingerprint() -> KnownFailureFingerprintV1:
    return KnownFailureFingerprintV1(
        fingerprint_id=FINGERPRINT,
        lesson_id="LESSON_X",
        preventive_gate_id="GATE_X",
        source_revision="drive-rev-1",
        authority_reference="AUTHORITY://PREL5/035",
        evidence=("drive:lesson-x",),
        applies_to_projects=(PROJECT,),
    )


def stores(state_store):
    failure = FailureRetryGuardStore(state_store)
    failure.import_registry(
        source_revision="drive-rev-1",
        authority_reference="AUTHORITY://PREL5/035",
        records=(fingerprint(),),
    )
    failure.record_failure(
        observation_id=OBSERVATION,
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=STATE,
        evidence=("operator-event:TASK_EXECUTION_FAILED",),
    )
    return failure, IncidentFailureLearningStore(state_store, failure)


def accepted_decision():
    return evaluate_acceptance(
        subject_head="b" * 40,
        required_kinds=(EvidenceKind.ci,),
        evidence=(
            AcceptanceEvidenceV1(
                kind=EvidenceKind.ci,
                status=EvidenceStatus.passed,
                reference="ci:prel5-035",
                subject_head="b" * 40,
            ),
        ),
    )


def rejected_decision():
    return evaluate_acceptance(
        subject_head="b" * 40,
        required_kinds=(EvidenceKind.ci,),
        evidence=(
            AcceptanceEvidenceV1(
                kind=EvidenceKind.ci,
                status=EvidenceStatus.failed,
                reference="ci:prel5-035-failed",
                subject_head="b" * 40,
            ),
        ),
    )


def test_open_incident_requires_existing_failure_observation() -> None:
    state = MemoryStateStore()
    failure = FailureRetryGuardStore(state)
    store = IncidentFailureLearningStore(state, failure)
    with pytest.raises(GovernanceError, match="INCIDENT_FAILURE_OBSERVATION_NOT_FOUND"):
        store.open_incident(
            incident_id="INC-001",
            observation_id="missing",
            evidence=("triage:started",),
        )


def test_incident_binds_exact_failure_identity() -> None:
    _, store = stores(MemoryStateStore())
    incident = store.open_incident(
        incident_id="INC-001",
        observation_id=OBSERVATION,
        evidence=("triage:started",),
    )
    assert incident.status == IncidentStatus.open
    assert incident.fingerprint_id == FINGERPRINT
    assert incident.project_id == PROJECT
    assert incident.task_id == TASK
    assert incident.failure_state_fingerprint == STATE


def test_learning_cannot_bind_before_root_cause() -> None:
    _, store = stores(MemoryStateStore())
    store.open_incident(
        incident_id="INC-001",
        observation_id=OBSERVATION,
        evidence=("triage:started",),
    )
    with pytest.raises(GovernanceError, match="ROOT_CAUSE_REQUIRED_BEFORE_LEARNING"):
        store.bind_learning("INC-001", evidence=("analysis:pending",))


def test_learning_binding_comes_from_sovereign_failure_registry() -> None:
    _, store = stores(MemoryStateStore())
    store.open_incident(
        incident_id="INC-001",
        observation_id=OBSERVATION,
        evidence=("triage:started",),
    )
    store.classify_root_cause(
        "INC-001",
        root_cause_code="ROOT_CAUSE_X",
        evidence=("analysis:root-cause",),
    )
    incident = store.bind_learning("INC-001", evidence=("lesson:reused",))
    assert incident.status == IncidentStatus.learning_bound
    assert incident.lesson_id == "LESSON_X"
    assert incident.preventive_gate_id == "GATE_X"


def test_rejected_acceptance_cannot_verify_prevention() -> None:
    _, store = stores(MemoryStateStore())
    store.open_incident(incident_id="INC-001", observation_id=OBSERVATION, evidence=("triage",))
    store.classify_root_cause("INC-001", root_cause_code="ROOT_CAUSE_X", evidence=("root",))
    store.bind_learning("INC-001", evidence=("lesson",))
    with pytest.raises(GovernanceError, match="PREVENTION_ACCEPTANCE_REQUIRED"):
        store.verify_prevention(
            "INC-001",
            acceptance_decision=rejected_decision(),
            evidence=("prevention:test",),
        )


def test_close_requires_verified_prevention() -> None:
    _, store = stores(MemoryStateStore())
    store.open_incident(incident_id="INC-001", observation_id=OBSERVATION, evidence=("triage",))
    store.classify_root_cause("INC-001", root_cause_code="ROOT_CAUSE_X", evidence=("root",))
    store.bind_learning("INC-001", evidence=("lesson",))
    with pytest.raises(GovernanceError, match="PREVENTION_REQUIRED_BEFORE_CLOSE"):
        store.close_incident("INC-001", evidence=("closure",))


def test_complete_lifecycle_emits_noncanonical_learning_candidate() -> None:
    _, store = stores(MemoryStateStore())
    store.open_incident(incident_id="INC-001", observation_id=OBSERVATION, evidence=("triage",))
    store.classify_root_cause("INC-001", root_cause_code="ROOT_CAUSE_X", evidence=("root",))
    store.bind_learning("INC-001", evidence=("lesson",))
    verified = store.verify_prevention(
        "INC-001",
        acceptance_decision=accepted_decision(),
        evidence=("prevention:test",),
    )
    assert verified.status == IncidentStatus.prevention_verified
    closed, candidate = store.close_incident("INC-001", evidence=("closure:approved",))
    assert closed.status == IncidentStatus.closed
    assert closed.closed_at is not None
    assert candidate.lesson_id == "LESSON_X"
    assert candidate.preventive_gate_id == "GATE_X"
    assert candidate.canonical_promotion_allowed is False
    assert candidate.source_authority == "WORKSPACE_DRIVE_SOVEREIGN"


def test_open_incident_replay_is_idempotent_but_conflict_fails() -> None:
    failure, store = stores(MemoryStateStore())
    first = store.open_incident(
        incident_id="INC-001",
        observation_id=OBSERVATION,
        evidence=("triage",),
    )
    replay = store.open_incident(
        incident_id="INC-001",
        observation_id=OBSERVATION,
        evidence=("different-replay-note",),
    )
    assert replay == first
    failure.record_failure(
        observation_id="OTHER",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id="PREL5_035_OTHER",
        state_fingerprint=STATE,
        evidence=("operator-event:TASK_EXECUTION_FAILED",),
    )
    with pytest.raises(GovernanceError, match="INCIDENT_ID_CONFLICT"):
        store.open_incident(
            incident_id="INC-001",
            observation_id="OTHER",
            evidence=("triage",),
        )


def test_sqlite_restart_preserves_closed_incident_and_candidate(tmp_path: Path) -> None:
    db = tmp_path / "state.sqlite3"
    state = SQLiteStateStore(db)
    _, store = stores(state)
    store.open_incident(incident_id="INC-001", observation_id=OBSERVATION, evidence=("triage",))
    store.classify_root_cause("INC-001", root_cause_code="ROOT_CAUSE_X", evidence=("root",))
    store.bind_learning("INC-001", evidence=("lesson",))
    store.verify_prevention(
        "INC-001",
        acceptance_decision=accepted_decision(),
        evidence=("prevention:test",),
    )
    store.close_incident("INC-001", evidence=("closure",))

    restarted_state = SQLiteStateStore(db)
    restarted_failure = FailureRetryGuardStore(restarted_state)
    restarted = IncidentFailureLearningStore(restarted_state, restarted_failure)
    incident = restarted.get("INC-001")
    assert incident.status == IncidentStatus.closed
    assert len(restarted.learning_candidates()) == 1
    assert restarted.learning_candidates()[0].canonical_promotion_allowed is False
