from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.failure_retry_guard import (
    FailureRetryGuardStore,
    KnownFailureFingerprintV1,
    RetryDisposition,
    build_state_fingerprint,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore

PROJECT = "PALWAKF_WORKSPACE_MANAGER"
TASK = "PREL5-011"
FINGERPRINT = "FAILURE-GITHUB-REMOTE-READBACK"
AUTHORITY = "AUTH-PREL5-011"
REVISION = "drive-revision-011"


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def record(
    *,
    fingerprint_id: str = FINGERPRINT,
    applies_to_projects: tuple[str, ...] = (PROJECT,),
    preventive_gate_id: str = "GATE-NO-BLIND-RETRY",
) -> KnownFailureFingerprintV1:
    return KnownFailureFingerprintV1(
        fingerprint_id=fingerprint_id,
        lesson_id="LESSON-RETRY-001",
        preventive_gate_id=preventive_gate_id,
        source_revision=REVISION,
        authority_reference=AUTHORITY,
        evidence=("drive://lessons/retry-001",),
        applies_to_projects=applies_to_projects,
    )


def store(state_store=None) -> FailureRetryGuardStore:
    guard = FailureRetryGuardStore(state_store or MemoryStateStore(), now=Clock())
    guard.import_registry(
        source_revision=REVISION,
        authority_reference=AUTHORITY,
        records=(record(),),
    )
    return guard


def test_first_attempt_is_allowed_without_prior_failure():
    guard = store()
    state = build_state_fingerprint({"head": "abc", "stage": "RUN"})
    decision = guard.require_retry_allowed(
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
    )
    assert decision.allowed is True
    assert decision.disposition is RetryDisposition.allow_no_prior_failure


def test_same_failure_same_state_is_blocked():
    guard = store()
    state = build_state_fingerprint({"head": "abc", "stage": "RUN"})
    guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    decision = guard.evaluate_retry(
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
    )
    assert decision.allowed is False
    assert decision.disposition is RetryDisposition.block_same_failure_same_state
    with pytest.raises(
        GovernanceError,
        match="BLIND_RETRY_BLOCKED_SAME_FAILURE_SAME_STATE",
    ):
        guard.require_retry_allowed(
            fingerprint_id=FINGERPRINT,
            project_id=PROJECT,
            task_id=TASK,
            state_fingerprint=state,
        )


def test_changed_state_allows_retry():
    guard = store()
    old_state = build_state_fingerprint({"head": "abc", "stage": "RUN"})
    new_state = build_state_fingerprint({"head": "def", "stage": "RUN"})
    guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=old_state,
        evidence=("evidence://failure/1",),
    )
    decision = guard.require_retry_allowed(
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=new_state,
    )
    assert decision.disposition is RetryDisposition.allow_state_changed


def test_same_state_requires_governed_override_authority():
    guard = store()
    state = build_state_fingerprint({"head": "abc"})
    guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    with pytest.raises(GovernanceError, match="RETRY_OVERRIDE_AUTHORITY_MISMATCH"):
        guard.evaluate_retry(
            fingerprint_id=FINGERPRINT,
            project_id=PROJECT,
            task_id=TASK,
            state_fingerprint=state,
            override_reference="OVERRIDE-1",
            override_authority_reference="WRONG-AUTHORITY",
        )


def test_same_state_governed_override_is_allowed():
    guard = store()
    state = build_state_fingerprint({"head": "abc"})
    guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    decision = guard.require_retry_allowed(
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        override_reference="OVERRIDE-1",
        override_authority_reference=AUTHORITY,
    )
    assert decision.disposition is RetryDisposition.allow_governed_override
    assert decision.override_reference == "OVERRIDE-1"


def test_observation_replay_is_idempotent():
    guard = store()
    state = build_state_fingerprint({"head": "abc"})
    first = guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    replay = guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    assert replay == first
    assert len(guard.observations()) == 1


def test_registry_revision_replay_is_idempotent_and_conflict_fails_closed():
    state_store = MemoryStateStore()
    guard = FailureRetryGuardStore(state_store, now=Clock())
    first = guard.import_registry(
        source_revision=REVISION,
        authority_reference=AUTHORITY,
        records=(record(),),
    )
    replay = guard.import_registry(
        source_revision=REVISION,
        authority_reference=AUTHORITY,
        records=(record(),),
    )
    assert replay == first
    with pytest.raises(
        GovernanceError,
        match="KNOWN_FAILURE_REGISTRY_REVISION_CONFLICT",
    ):
        guard.import_registry(
            source_revision=REVISION,
            authority_reference=AUTHORITY,
            records=(record(preventive_gate_id="GATE-DIFFERENT"),),
        )


def test_project_scope_mismatch_fails_closed():
    guard = store()
    with pytest.raises(
        GovernanceError,
        match="KNOWN_FAILURE_FINGERPRINT_PROJECT_MISMATCH",
    ):
        guard.evaluate_retry(
            fingerprint_id=FINGERPRINT,
            project_id="OTHER_PROJECT",
            task_id=TASK,
            state_fingerprint=build_state_fingerprint({"head": "abc"}),
        )


def test_sqlite_restart_preserves_failure_and_blocks_blind_retry(tmp_path):
    path = tmp_path / "retry-guard.sqlite3"
    first = store(SQLiteStateStore(path))
    state = build_state_fingerprint({"head": "abc", "stage": "RUN"})
    first.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    restarted = FailureRetryGuardStore(SQLiteStateStore(path), now=Clock())
    decision = restarted.evaluate_retry(
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
    )
    assert decision.allowed is False
    assert decision.disposition is RetryDisposition.block_same_failure_same_state
    assert restarted.current_registry().source_revision == REVISION


def test_same_failure_same_state_cannot_bypass_guard_with_new_task_id():
    guard = store()
    state = build_state_fingerprint({"head": "abc", "stage": "RUN"})
    guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id="TASK-A",
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    decision = guard.evaluate_retry(
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id="TASK-B",
        state_fingerprint=state,
    )
    assert decision.allowed is False
    assert decision.prior_observation_id == "OBS-1"


def test_blank_override_reference_is_rejected():
    guard = store()
    state = build_state_fingerprint({"head": "abc"})
    guard.record_failure(
        observation_id="OBS-1",
        fingerprint_id=FINGERPRINT,
        project_id=PROJECT,
        task_id=TASK,
        state_fingerprint=state,
        evidence=("evidence://failure/1",),
    )
    with pytest.raises(GovernanceError, match="RETRY_OVERRIDE_REFERENCE_REQUIRED"):
        guard.evaluate_retry(
            fingerprint_id=FINGERPRINT,
            project_id=PROJECT,
            task_id=TASK,
            state_fingerprint=state,
            override_reference="   ",
            override_authority_reference=AUTHORITY,
        )


def test_registry_hash_tampering_is_rejected():
    from pydantic import ValidationError

    from palwakf_orchestrator.failure_retry_guard import (
        KnownFailureFingerprintRegistryV1,
        build_failure_registry_snapshot,
    )

    snapshot = build_failure_registry_snapshot(
        source_revision=REVISION,
        authority_reference=AUTHORITY,
        records=(record(),),
        imported_at=datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
    )
    payload = snapshot.model_dump(mode="json")
    payload["registry_sha256"] = "0" * 64
    with pytest.raises(
        ValidationError,
        match="FAILURE_FINGERPRINT_REGISTRY_HASH_MISMATCH",
    ):
        KnownFailureFingerprintRegistryV1.model_validate(payload)


def operator_task_request():
    from palwakf_orchestrator.operator_contracts import CreateOperatorTaskRequest

    return CreateOperatorTaskRequest(
        task_id="PREL5_011_RETRY_TASK",
        project_id=PROJECT,
        repository="firasfanon/palwakf_workspace_manager",
        branch="agent/workspace-manager-foundation-v1",
        expected_head="a" * 40,
        authority_reference="AUTHORITY://PREL5-011",
        prompt="Exercise the governed known-failure retry preflight contract.",
        constraints=["NO_PRODUCTION", "NO_DATABASE_WRITE"],
        sandbox="read-only",
        max_turns=1,
        timeout_seconds=60,
        idempotency_key="prel5-011-retry-task",
    )


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def test_operator_service_blocks_known_failure_same_state_continue(tmp_path):
    from palwakf_orchestrator.operator_service import OperatorService

    state_store = MemoryStateStore()
    guard = store(state_store)
    operator = OperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        state_store=state_store,
        failure_retry_guard=guard,
    )
    task = operator.create_task(operator_task_request())
    operator.fail_task(task.task_id, FINGERPRINT)
    assert len(guard.observations()) == 1
    with pytest.raises(
        GovernanceError,
        match="BLIND_RETRY_BLOCKED_SAME_FAILURE_SAME_STATE",
    ):
        operator.continue_task(task.task_id)


def test_operator_service_allows_only_governed_override(tmp_path):
    from palwakf_orchestrator.operator_contracts import OperatorTaskStatus
    from palwakf_orchestrator.operator_service import OperatorService

    state_store = MemoryStateStore()
    guard = store(state_store)
    operator = OperatorService(
        tmp_path,
        verifier=AcceptingVerifier(),
        state_store=state_store,
        failure_retry_guard=guard,
    )
    task = operator.create_task(operator_task_request())
    operator.fail_task(task.task_id, FINGERPRINT)
    continued = operator.continue_task(
        task.task_id,
        retry_override_reference="OVERRIDE-PREL5-011",
        retry_override_authority_reference=AUTHORITY,
    )
    assert continued.status is OperatorTaskStatus.pending
    assert guard.retry_decisions()[-1].disposition is RetryDisposition.allow_governed_override
