from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    OperatorTaskRecord,
    PermissionStatus,
    ToolPlanResponse,
    ToolSelectionDecision,
)
from palwakf_orchestrator.persistence import MemoryStateStore, SQLiteStateStore, StateStore
from palwakf_orchestrator.rdc_execution_channel import (
    RdcActionClass,
    RdcExecutionChannelContractV1,
    RdcPreflightRequestV1,
    RdcRepositoryRealityV1,
    RdcRuntimeIdentityV1,
    RdcTaskBindingV1,
    RdcToolConfigSnapshotV1,
)
from palwakf_orchestrator.rdc_session_resume import (
    RDC_ADAPTER_ID,
    RDC_CAPABILITY_ID,
    RdcSessionBootstrapProofV1,
    RdcSessionLifecycle,
    RdcSessionResumeRecordV1,
    RdcSessionResumeStore,
)

TASK = "PREL5-065"
PROJECT = "PALWAKF_WORKSPACE_MANAGER"
REPOSITORY = "firasfanon/palwakf_workspace_manager"
BRANCH = "task/PREL5-ONE-GOVERNED-DEVELOPMENT-BATCH-V1"
HEAD = "9f38a2402f9f0b3130f1290e9f384d5f2bae79e1"
AUTHORITY = "TASK_CONTRACT:PREL5-065"
LOCAL_PATH = r"C:\workspace\palwakf_workspace_manager\PREL5-065"
SCOPE = (
    "orchestrator/src/palwakf_orchestrator/rdc_session_resume.py",
    "orchestrator/tests/test_rdc_session_resume.py",
)


def task(*, authorized: bool = True, head: str = HEAD) -> OperatorTaskRecord:
    now = datetime.now(UTC)
    return OperatorTaskRecord(
        task_id=TASK,
        project_id=PROJECT,
        repository=REPOSITORY,
        branch=BRANCH,
        expected_head=head,
        authority_reference=AUTHORITY,
        prompt="Execute the governed PREL5-065 RDC session and resume proof.",
        constraints=["NO_MAIN_MERGE", "NO_PRODUCTION"],
        approval_policy="on-request",
        sandbox="workspace-write",
        max_turns=1,
        timeout_seconds=60,
        idempotency_key="prel5-065-rdc-session",
        requires_explicit_authorization=True,
        scope_patterns=list(SCOPE),
        relay_provider_id="chatgpt",
        authorized_at=now if authorized else None,
        authorized_by="human-authority" if authorized else None,
        created_at=now,
        updated_at=now,
        last_event="TASK_AUTHORIZED" if authorized else "TASK_CREATED",
    )


def plan(*, include_rdc: bool = True, selected: str | None = RDC_ADAPTER_ID) -> ToolPlanResponse:
    decisions = []
    if include_rdc:
        decisions.append(
            ToolSelectionDecision(
                capability_id=RDC_CAPABILITY_ID,
                selected_adapter_id=selected,
                fallback_adapter_id=None,
                selected_reason="PREL5-065 governed local execution channel",
                excluded_adapters_with_reason=[],
                permission_status=PermissionStatus.approval_required,
                approval_required=True,
                invocation_order=1,
                evidence_contract=[
                    "rdc_preflight_receipt",
                    "postflight_remote_readback",
                ],
                decision_timestamp=datetime.now(UTC),
                registry_version="TEST-RDC-REGISTRY",
                blocked=selected is None,
                substituted=False,
            )
        )
    return ToolPlanResponse(
        task_id=TASK,
        project_id=PROJECT,
        decisions=decisions,
        dispatch_blocked=False,
        blockers=[],
    )


def bootstrap(*, head: str = HEAD) -> RdcSessionBootstrapProofV1:
    return RdcSessionBootstrapProofV1(
        project_id=PROJECT,
        task_id=TASK,
        current_head=head,
        todo_boot_rule_ids=("TODO-BOOT-014", "TODO-BOOT-015", "TODO-BOOT-016"),
        latest_handoff_loaded=True,
        fresh_git_readback=True,
        fresh_drive_readback=True,
        live_rdc_readback=True,
    )


def config() -> RdcToolConfigSnapshotV1:
    return RdcToolConfigSnapshotV1(
        app_version="0.2.51",
        default_shell="powershell.exe",
        allowed_directories=(),
        blocked_commands=("shutdown", "reboot"),
        telemetry_enabled=True,
    )


def request(
    *,
    action: RdcActionClass = RdcActionClass.filesystem_write,
    paths: tuple[str, ...] = (SCOPE[0],),
    clean: bool = True,
    head: str = HEAD,
) -> RdcPreflightRequestV1:
    cfg = config()
    contract = RdcExecutionChannelContractV1(
        expected_device_id="device-prel5-065",
        expected_device_name="TEST-PC",
        expected_local_user="DELL",
        expected_tool_config_sha256=cfg.fingerprint_sha256,
        allowed_actions=(
            RdcActionClass.filesystem_write,
            RdcActionClass.terminal_mutating,
            RdcActionClass.git_read,
            RdcActionClass.git_write,
        ),
    )
    runtime = RdcRuntimeIdentityV1(
        device_id="device-prel5-065",
        device_name="TEST-PC",
        device_status="online",
        local_user="DELL",
        user_profile=r"C:\Users\DELL",
        tool_config=cfg,
    )
    binding = RdcTaskBindingV1(
        task_id=TASK,
        project_id=PROJECT,
        repository=REPOSITORY,
        local_repository_path=LOCAL_PATH,
        branch=BRANCH,
        expected_head=head,
        authority_reference=AUTHORITY,
        mutation_class="source-write",
        scope_patterns=SCOPE,
    )
    reality = RdcRepositoryRealityV1(
        project_id=PROJECT,
        repository=REPOSITORY,
        local_repository_path=LOCAL_PATH,
        branch=BRANCH,
        local_head=head,
        remote_head=head,
        origin=f"https://github.com/{REPOSITORY}.git",
        worktree_clean=clean,
    )
    return RdcPreflightRequestV1(
        contract=contract,
        runtime=runtime,
        binding=binding,
        reality=reality,
        requested_action=action,
        requested_paths=paths,
    )


def start(
    store: StateStore | None = None,
) -> tuple[RdcSessionResumeStore, RdcSessionResumeRecordV1]:
    workflow = RdcSessionResumeStore(store or MemoryStateStore())
    record = workflow.start(
        task=task(),
        plan=plan(),
        bootstrap=bootstrap(),
        request=request(),
        evidence=("bootstrap:pass", "rdc-live:pass"),
    )
    return workflow, record


def test_session_start_binds_bootstrap_plan_authority_and_rdc_preflight() -> None:
    _, record = start()

    assert record.lifecycle == RdcSessionLifecycle.active
    assert record.selected_channel == RDC_ADAPTER_ID
    assert record.manual_user_relay_required is False
    assert record.manual_relay_is_default is False
    assert record.authority_expansion_allowed is False
    assert record.main_merge_authorized is False
    assert record.baseline_promotion_authorized is False
    assert record.production_authorized is False
    assert record.database_mutation_authorized is False


def test_required_bootstrap_rules_are_fail_closed() -> None:
    with pytest.raises(
        ValidationError,
        match="RDC_SESSION_REQUIRED_BOOTSTRAP_RULES_MISSING",
    ):
        RdcSessionBootstrapProofV1(
            project_id=PROJECT,
            task_id=TASK,
            current_head=HEAD,
            todo_boot_rule_ids=("TODO-BOOT-014", "TODO-BOOT-015", "TODO-BOOT-999"),
            latest_handoff_loaded=True,
            fresh_git_readback=True,
            fresh_drive_readback=True,
            live_rdc_readback=True,
        )


def test_source_write_requires_explicit_authorization() -> None:
    workflow = RdcSessionResumeStore(MemoryStateStore())

    with pytest.raises(
        GovernanceError,
        match="RDC_SESSION_RDC_APPROVAL_NOT_SATISFIED",
    ):
        workflow.start(
            task=task(authorized=False),
            plan=plan(),
            bootstrap=bootstrap(),
            request=request(),
            evidence=("preflight",),
        )


@pytest.mark.parametrize(
    ("changed_plan", "expected"),
    [
        (plan(include_rdc=False), "RDC_SESSION_LOCAL_CHANNEL_NOT_PLANNED"),
        (plan(selected=None), "RDC_SESSION_RDC_NOT_SELECTED"),
    ],
)
def test_rdc_must_be_selected_in_tool_plan(changed_plan: ToolPlanResponse, expected: str) -> None:
    workflow = RdcSessionResumeStore(MemoryStateStore())

    with pytest.raises(GovernanceError, match=expected):
        workflow.start(
            task=task(),
            plan=changed_plan,
            bootstrap=bootstrap(),
            request=request(),
            evidence=("preflight",),
        )


def test_live_preflight_denial_blocks_session_admission() -> None:
    workflow = RdcSessionResumeStore(MemoryStateStore())

    with pytest.raises(GovernanceError, match="RDC_SESSION_PREFLIGHT_DENIED"):
        workflow.start(
            task=task(),
            plan=plan(),
            bootstrap=bootstrap(),
            request=request(clean=False),
            evidence=("preflight",),
        )


def test_binding_and_bootstrap_head_drift_fail_closed() -> None:
    workflow = RdcSessionResumeStore(MemoryStateStore())
    with pytest.raises(
        GovernanceError,
        match="RDC_SESSION_BOOTSTRAP_HEAD_MISMATCH",
    ):
        workflow.start(
            task=task(),
            plan=plan(),
            bootstrap=bootstrap(head="1" * 40),
            request=request(),
            evidence=("preflight",),
        )

    with pytest.raises(
        GovernanceError,
        match="RDC_SESSION_HEAD_BINDING_MISMATCH",
    ):
        workflow.start(
            task=task(),
            plan=plan(),
            bootstrap=bootstrap(),
            request=request(head="2" * 40),
            evidence=("preflight",),
        )


def test_interruption_restart_resume_preserves_actions_without_duplicate(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.sqlite3"
    state = SQLiteStateStore(state_path)
    state.save({"operator": {"sentinel": "preserve-me"}})
    workflow = RdcSessionResumeStore(state)
    workflow.start(
        task=task(),
        plan=plan(),
        bootstrap=bootstrap(),
        request=request(),
        evidence=("bootstrap:pass",),
    )
    terminal_request = request(
        action=RdcActionClass.terminal_mutating,
        paths=(SCOPE[1],),
    )
    first = workflow.record_action(
        TASK,
        action_id="TARGETED_TESTS",
        request=terminal_request,
        evidence=("pytest:pass",),
    )
    assert len(first.actions) == 1
    interrupted = workflow.interrupt(
        TASK,
        evidence=("controlled-interruption",),
    )
    assert interrupted.lifecycle == RdcSessionLifecycle.interrupted

    restarted = RdcSessionResumeStore(SQLiteStateStore(state_path))
    restored = restarted.get(TASK)
    assert restored.lifecycle == RdcSessionLifecycle.interrupted
    assert len(restored.actions) == 1
    assert SQLiteStateStore(state_path).load()["operator"]["sentinel"] == "preserve-me"
    resumed = restarted.resume(
        task=task(),
        plan=plan(),
        bootstrap=bootstrap(),
        request=request(),
        evidence=("fresh-rdc-readback:pass",),
    )
    assert resumed.lifecycle == RdcSessionLifecycle.resumed

    replay = restarted.record_action(
        TASK,
        action_id="TARGETED_TESTS",
        request=terminal_request,
        evidence=("pytest:pass",),
    )
    assert len(replay.actions) == 1

    second = restarted.record_action(
        TASK,
        action_id="FULL_REGRESSION",
        request=terminal_request,
        evidence=("full-pytest:pass",),
    )
    assert len(second.actions) == 2

    completed = restarted.complete(
        TASK,
        evidence=("remote-readback:pass",),
    )
    assert completed.lifecycle == RdcSessionLifecycle.completed


def test_action_id_reuse_with_different_evidence_is_rejected() -> None:
    workflow, _ = start()
    terminal_request = request(
        action=RdcActionClass.terminal_mutating,
        paths=(SCOPE[1],),
    )
    workflow.record_action(
        TASK,
        action_id="TEST-1",
        request=terminal_request,
        evidence=("result:a",),
    )

    with pytest.raises(
        GovernanceError,
        match="RDC_SESSION_ACTION_ID_REUSE_MISMATCH",
    ):
        workflow.record_action(
            TASK,
            action_id="TEST-1",
            request=terminal_request,
            evidence=("result:b",),
        )


def test_manual_user_relay_is_only_explicit_interruption_exception() -> None:
    workflow, record = start()
    assert record.manual_user_relay_required is False

    with pytest.raises(
        GovernanceError,
        match="RDC_MANUAL_RELAY_EXCEPTION_REQUIRES_INTERRUPTION",
    ):
        workflow.record_manual_relay_exception(
            TASK,
            exception_reference="EXCEPTION-065",
            rdc_blockers=("RDC_DEVICE_NOT_ONLINE",),
            evidence=("operator-decision",),
        )

    workflow.interrupt(TASK, evidence=("rdc-unavailable",))

    with pytest.raises(
        GovernanceError,
        match="RDC_MANUAL_RELAY_EXCEPTION_BLOCKERS_REQUIRED",
    ):
        workflow.record_manual_relay_exception(
            TASK,
            exception_reference="EXCEPTION-065",
            rdc_blockers=(),
            evidence=("operator-decision",),
        )

    exception = workflow.record_manual_relay_exception(
        TASK,
        exception_reference="EXCEPTION-065",
        rdc_blockers=("RDC_DEVICE_NOT_ONLINE",),
        evidence=("operator-decision",),
    )
    assert exception.manual_user_relay_required is True
    assert exception.manual_relay_is_default is False
    assert exception.manual_relay_exception_reference == "EXCEPTION-065"
    assert exception.manual_relay_exception_blockers == ("RDC_DEVICE_NOT_ONLINE",)


def test_restart_identity_drift_cannot_resume(tmp_path: Path) -> None:
    state_path = tmp_path / "state.sqlite3"
    workflow, _ = start(SQLiteStateStore(state_path))
    workflow.interrupt(TASK, evidence=("controlled-interruption",))

    restarted = RdcSessionResumeStore(SQLiteStateStore(state_path))
    with pytest.raises(
        GovernanceError,
        match="RDC_SESSION_PERSISTED_IDENTITY_DRIFT",
    ):
        restarted.resume(
            task=task(head="3" * 40),
            plan=plan(),
            bootstrap=bootstrap(head="3" * 40),
            request=request(head="3" * 40),
            evidence=("resume-attempt",),
        )
