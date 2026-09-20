from palwakf_orchestrator.four_system_l4 import FourSystemL4OperationalService
from palwakf_orchestrator.intersystem_contracts import WorkspaceAuthorityPackageV1
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.risk_adaptive_execution import (
    MethodPilotRequest,
    PilotAction,
    RiskAdaptiveExecutionPilot,
    RiskLevel,
)

HEAD = "2" * 40
BASE = "1" * 40


def _record():
    package = WorkspaceAuthorityPackageV1(
        state_package_id="workspace-state-run-1",
        execution_run_id="run-1",
        project_id="PALWAKF_LOCAL_AGENTS",
        task_id="task-1",
        repository="firasfanon/palwakf_agenticAi_system",
        task_branch="task/example",
        base_sha=BASE,
        expected_head=HEAD,
        authority_reference="AUTH:test",
        objective="Perform governed method-pilot validation.",
        constraints=["NO_MAIN", "NO_PRODUCTION"],
        timeout_seconds=120,
        scope_patterns=["backend/**"],
        required_capabilities=["READ_ONLY_DIAGNOSTIC"],
        required_tests=["L4"],
    )
    service = FourSystemL4OperationalService(MemoryStateStore())
    return service.open_authority_run(package=package, correlation_id="corr-1")


def test_r0_resume_is_automatic_without_unnecessary_revalidation():
    decision = RiskAdaptiveExecutionPilot().decide(
        _record(), MethodPilotRequest(action=PilotAction.RESUME)
    )
    assert decision.risk_level == RiskLevel.R0
    assert decision.ready is True
    assert decision.automatic_execution_allowed is True
    assert decision.human_authorization_required is False
    assert decision.targeted_revalidation_required == ()


def test_r2_requires_fresh_expected_head_but_not_new_human_authorization():
    pilot = RiskAdaptiveExecutionPilot()
    blocked = pilot.decide(
        _record(), MethodPilotRequest(action=PilotAction.COMMIT_PUSH_PR)
    )
    assert blocked.ready is False
    assert blocked.blockers == ("FRESH_HEAD_OBSERVATION_REQUIRED",)
    assert blocked.human_authorization_required is False

    ready = pilot.decide(
        _record(),
        MethodPilotRequest(action=PilotAction.COMMIT_PUSH_PR, observed_head=HEAD),
    )
    assert ready.risk_level == RiskLevel.R2
    assert ready.ready is True
    assert ready.automatic_execution_allowed is True


def test_r2_fails_closed_on_head_drift():
    decision = RiskAdaptiveExecutionPilot().decide(
        _record(),
        MethodPilotRequest(action=PilotAction.COMMIT_PUSH_PR, observed_head="3" * 40),
    )
    assert decision.ready is False
    assert "EXPECTED_HEAD_DRIFT" in decision.blockers


def test_r3_never_auto_executes():
    decision = RiskAdaptiveExecutionPilot().decide(
        _record(),
        MethodPilotRequest(
            action=PilotAction.MAIN_BASELINE_PRODUCTION_DB,
            observed_head=HEAD,
        ),
    )
    assert decision.risk_level == RiskLevel.R3
    assert decision.ready is False
    assert decision.automatic_execution_allowed is False
    assert decision.human_authorization_required is True
