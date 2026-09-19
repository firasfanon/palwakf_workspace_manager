from __future__ import annotations

from palwakf_orchestrator.decision_registry import DecisionSupersessionRegistryStore
from palwakf_orchestrator.engineering_os_contracts import EngineeringTaskStatus
from palwakf_orchestrator.lifecycle_decision_registry import (
    LifecycleDecisionRegistryStore,
    LifecycleStage,
)
from palwakf_orchestrator.operator_contracts import OperatorTaskStatus
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.portfolio_decision_inbox import PortfolioDecisionInboxProjection
from palwakf_orchestrator.project_change_inbox import (
    ProjectChangeInboxStatus,
    ProjectChangeInboxStore,
)
from tests.test_capability_preservation_baseline import (
    REMOTE_HEAD,
    engineering_record,
    operator_record,
)
from tests.test_decision_supersession_registry import (
    AUTH as DEC_AUTH,
)
from tests.test_decision_supersession_registry import (
    REV as DEC_REV,
)
from tests.test_decision_supersession_registry import (
    valid_records,
)
from tests.test_lifecycle_decision_registry import (
    AUTH as LIFE_AUTH,
)
from tests.test_lifecycle_decision_registry import (
    REV as LIFE_REV,
)
from tests.test_lifecycle_decision_registry import (
    _record,
)
from tests.test_project_change_inbox import B, _event

PROJECT = "PALWAKF_WORKSPACE_MANAGER"
OTHER = "PALWAKF_OTHER_PROJECT"


def test_project_filter_prevents_cross_project_leakage() -> None:
    store = MemoryStateStore()
    projection = PortfolioDecisionInboxProjection(store)
    local = operator_record(
        task_id="INBOX_LOCAL",
        status=OperatorTaskStatus.awaiting_approval,
    )
    foreign = operator_record(
        task_id="INBOX_FOREIGN",
        status=OperatorTaskStatus.awaiting_approval,
    ).model_copy(update={"project_id": OTHER})

    inbox = projection.build(
        operator_tasks=[local, foreign],
        engineering_tasks=[],
        projects=[],
        project_id=PROJECT,
    )

    assert inbox.total == 2
    assert {item.source_id for item in inbox.items} == {"INBOX_LOCAL"}
    assert all(
        PROJECT in item.applies_to_projects or "*" in item.applies_to_projects
        for item in inbox.items
    )


def test_stale_lifecycle_decision_does_not_satisfy_current_head() -> None:
    store = MemoryStateStore()
    LifecycleDecisionRegistryStore(store).import_snapshot(
        source_revision=LIFE_REV,
        authority_reference=LIFE_AUTH,
        records=(_record(LifecycleStage.integration_acceptance, sha="a" * 40),),
    )
    task = engineering_record(
        task_id="INBOX_STALE_HEAD",
        status=EngineeringTaskStatus.ready_for_integration,
        remote_sha="b" * 40,
    )

    inbox = PortfolioDecisionInboxProjection(store).build(
        operator_tasks=[],
        engineering_tasks=[task],
        projects=[],
        project_id=PROJECT,
    )

    pending = [item for item in inbox.items if item.kind == "PENDING_DECISION"]
    assert len(pending) == 1
    assert pending[0].subject_sha == "b" * 40
    assert pending[0].lifecycle_stage == LifecycleStage.integration_acceptance.value


def test_superseded_decision_is_not_reintroduced() -> None:
    store = MemoryStateStore()
    DecisionSupersessionRegistryStore(store).import_snapshot(
        source_revision=DEC_REV,
        authority_reference=DEC_AUTH,
        records=valid_records(),
    )

    inbox = PortfolioDecisionInboxProjection(store).build(
        operator_tasks=[],
        engineering_tasks=[],
        projects=[],
        project_id=PROJECT,
    )

    decision_ids = {
        item.source_id for item in inbox.items if item.source_kind == "DECISION_REGISTRY"
    }
    assert decision_ids == {"DEC-2"}


def test_resolved_change_does_not_reenter_projection() -> None:
    store = MemoryStateStore()
    changes = ProjectChangeInboxStore(store)
    item = changes.ingest_event(_event())[0]
    changes.transition(
        item.inbox_item_id,
        project_id=B,
        expected_status=ProjectChangeInboxStatus.open,
        new_status=ProjectChangeInboxStatus.resolved,
        lifecycle_evidence=("decision:closed",),
        resolution_reference="decision:closed",
    )

    inbox = PortfolioDecisionInboxProjection(store).build(
        operator_tasks=[],
        engineering_tasks=[],
        projects=[],
        project_id=B,
    )

    assert inbox.change_reviews == 0
    assert all(item.source_kind != "PROJECT_CHANGE_INBOX" for item in inbox.items)


def test_blocker_and_pending_approval_are_both_visible_and_exact_head_bound() -> None:
    store = MemoryStateStore()
    task = operator_record(
        task_id="INBOX_BLOCKED_APPROVAL",
        status=OperatorTaskStatus.awaiting_approval,
    )

    inbox = PortfolioDecisionInboxProjection(store).build(
        operator_tasks=[task],
        engineering_tasks=[],
        projects=[],
        project_id=PROJECT,
    )

    assert inbox.pending_approvals == 1
    assert inbox.blockers == 1
    approval = next(item for item in inbox.items if item.kind == "PENDING_APPROVAL")
    blocker = next(item for item in inbox.items if item.kind == "BLOCKER")
    assert approval.subject_sha == REMOTE_HEAD.lower()
    assert blocker.subject_sha == REMOTE_HEAD.lower()
    assert blocker.blocker == "PARITY_BLOCKER"
    assert inbox.durability == "DURABLE_SOURCE_READ_ONLY_PROJECTION"
    assert inbox.canonical_state_created is False


def test_exact_current_lifecycle_decision_removes_pending_decision() -> None:
    store = MemoryStateStore()
    task = engineering_record(
        task_id="INBOX_EXACT_HEAD",
        status=EngineeringTaskStatus.ready_for_integration,
        remote_sha="a" * 40,
    )
    LifecycleDecisionRegistryStore(store).import_snapshot(
        source_revision=LIFE_REV,
        authority_reference=LIFE_AUTH,
        records=(_record(LifecycleStage.integration_acceptance, sha="a" * 40),),
    )

    inbox = PortfolioDecisionInboxProjection(store).build(
        operator_tasks=[],
        engineering_tasks=[task],
        projects=[],
        project_id=PROJECT,
    )

    assert inbox.pending_decisions == 0
    assert any(
        item.source_kind == "LIFECYCLE_DECISION_REGISTRY" and item.subject_sha == "a" * 40
        for item in inbox.items
    )
