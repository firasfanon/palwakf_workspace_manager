from __future__ import annotations

from palwakf_orchestrator.dashboard_contracts import (
    PortfolioDecisionInboxItem,
    PortfolioDecisionInboxSummary,
    PortfolioProjectSummary,
)
from palwakf_orchestrator.decision_registry import (
    DecisionStatus,
    DecisionSupersessionRegistryStore,
)
from palwakf_orchestrator.engineering_os_contracts import (
    EngineeringTaskRecord,
    EngineeringTaskStatus,
)
from palwakf_orchestrator.lifecycle_decision_registry import (
    LifecycleDecisionRegistryStore,
    LifecycleDisposition,
    LifecycleRecordStatus,
    LifecycleStage,
)
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord, OperatorTaskStatus
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.project_change_inbox import (
    ProjectChangeInboxStatus,
    ProjectChangeInboxStore,
)


class PortfolioDecisionInboxProjection:
    """Read-only projection over existing durable governance sources."""

    def __init__(self, state_store: StateStore) -> None:
        self._decisions = DecisionSupersessionRegistryStore(state_store)
        self._lifecycle = LifecycleDecisionRegistryStore(state_store)
        self._changes = ProjectChangeInboxStore(state_store)

    @staticmethod
    def _project_matches(project_id: str, requested_project_id: str | None) -> bool:
        return requested_project_id is None or project_id == requested_project_id

    @staticmethod
    def _decision_scope_matches(
        applies_to_projects: tuple[str, ...],
        requested_project_id: str | None,
    ) -> bool:
        if requested_project_id is None:
            return True
        return "*" in applies_to_projects or requested_project_id in applies_to_projects

    def build(
        self,
        *,
        operator_tasks: list[OperatorTaskRecord],
        engineering_tasks: list[EngineeringTaskRecord],
        projects: list[PortfolioProjectSummary],
        project_id: str | None = None,
    ) -> PortfolioDecisionInboxSummary:
        items: list[PortfolioDecisionInboxItem] = []
        lifecycle_history = self._lifecycle.history()
        lifecycle_records = lifecycle_history[-1].records if lifecycle_history else ()
        lifecycle_current = {
            (record.project_id, record.stage, record.subject_sha): record
            for record in lifecycle_records
            if record.status == LifecycleRecordStatus.current
        }

        for operator_task in operator_tasks:
            if not self._project_matches(operator_task.project_id, project_id):
                continue
            if operator_task.status == OperatorTaskStatus.awaiting_approval:
                items.append(
                    PortfolioDecisionInboxItem(
                        item_id=f"operator:{operator_task.task_id}:approval",
                        kind="PENDING_APPROVAL",
                        project_id=operator_task.project_id,
                        applies_to_projects=[operator_task.project_id],
                        source_kind="OPERATOR_TASK",
                        source_id=operator_task.task_id,
                        status=operator_task.status.value,
                        summary="Operator operator_task is awaiting explicit approval.",
                        requires_human_action=True,
                        subject_sha=operator_task.expected_head.lower(),
                        authority_reference=operator_task.authority_reference,
                        updated_at=operator_task.updated_at,
                    )
                )
            if operator_task.blocker:
                items.append(
                    PortfolioDecisionInboxItem(
                        item_id=f"operator:{operator_task.task_id}:blocker",
                        kind="BLOCKER",
                        project_id=operator_task.project_id,
                        applies_to_projects=[operator_task.project_id],
                        source_kind="OPERATOR_TASK",
                        source_id=operator_task.task_id,
                        status=operator_task.status.value,
                        summary="Operator operator_task has a recorded blocker.",
                        requires_human_action=True,
                        subject_sha=operator_task.expected_head.lower(),
                        authority_reference=operator_task.authority_reference,
                        blocker=operator_task.blocker,
                        updated_at=operator_task.updated_at,
                    )
                )

        for engineering_task in engineering_tasks:
            if not self._project_matches(engineering_task.project_id, project_id):
                continue
            stage = (
                LifecycleStage.integration_acceptance
                if engineering_task.status == EngineeringTaskStatus.ready_for_integration
                else LifecycleStage.main_merge
                if engineering_task.status == EngineeringTaskStatus.in_merge_queue
                else None
            )
            if stage is not None:
                subject_sha = (
                    engineering_task.latest_remote_task_sha.lower()
                    if engineering_task.latest_remote_task_sha is not None
                    else None
                )
                if subject_sha is None:
                    items.append(
                        PortfolioDecisionInboxItem(
                            item_id=f"engineering:{engineering_task.task_id}:head-binding",
                            kind="BLOCKER",
                            project_id=engineering_task.project_id,
                            applies_to_projects=[engineering_task.project_id],
                            source_kind="ENGINEERING_TASK",
                            source_id=engineering_task.task_id,
                            status="MISSING_EXACT_HEAD_BINDING",
                            summary="Lifecycle decision requires an exact remote task head.",
                            requires_human_action=True,
                            lifecycle_stage=stage.value,
                            blocker="MISSING_EXACT_HEAD_BINDING",
                            updated_at=engineering_task.updated_at,
                        )
                    )
                else:
                    exact_decision = lifecycle_current.get(
                        (engineering_task.project_id, stage, subject_sha)
                    )
                    if exact_decision is None:
                        items.append(
                            PortfolioDecisionInboxItem(
                                item_id=f"engineering:{engineering_task.task_id}:{stage.value}",
                                kind="PENDING_DECISION",
                                project_id=engineering_task.project_id,
                                applies_to_projects=[engineering_task.project_id],
                                source_kind="ENGINEERING_TASK",
                                source_id=engineering_task.task_id,
                                status=engineering_task.status.value,
                                summary=f"{stage.value} requires an exact-head lifecycle decision.",
                                requires_human_action=True,
                                subject_sha=subject_sha,
                                lifecycle_stage=stage.value,
                                updated_at=engineering_task.updated_at,
                            )
                        )
                    elif exact_decision.disposition != LifecycleDisposition.approved:
                        items.append(
                            PortfolioDecisionInboxItem(
                                item_id=f"engineering:{engineering_task.task_id}:{stage.value}:blocked",
                                kind="BLOCKER",
                                project_id=engineering_task.project_id,
                                applies_to_projects=[engineering_task.project_id],
                                source_kind="ENGINEERING_TASK",
                                source_id=engineering_task.task_id,
                                status=f"LIFECYCLE_{exact_decision.disposition.value}",
                                summary="Current lifecycle decision blocks this task state.",
                                requires_human_action=True,
                                subject_sha=subject_sha,
                                lifecycle_stage=stage.value,
                                authority_reference=exact_decision.authority_reference,
                                blocker=f"LIFECYCLE_{exact_decision.disposition.value}",
                                updated_at=engineering_task.updated_at,
                            )
                        )

            if engineering_task.status in {
                EngineeringTaskStatus.blocked_dependency,
                EngineeringTaskStatus.reconciliation_required,
            }:
                items.append(
                    PortfolioDecisionInboxItem(
                        item_id=f"engineering:{engineering_task.task_id}:blocker",
                        kind="BLOCKER",
                        project_id=engineering_task.project_id,
                        applies_to_projects=[engineering_task.project_id],
                        source_kind="ENGINEERING_TASK",
                        source_id=engineering_task.task_id,
                        status=engineering_task.status.value,
                        summary="Engineering engineering_task is blocked by its governed state.",
                        requires_human_action=True,
                        subject_sha=(
                            engineering_task.latest_remote_task_sha.lower()
                            if engineering_task.latest_remote_task_sha is not None
                            else None
                        ),
                        blocker=engineering_task.status.value,
                        updated_at=engineering_task.updated_at,
                    )
                )

        decision_history = self._decisions.history()
        decision_records = decision_history[-1].records if decision_history else ()
        for decision in decision_records:
            if decision.status != DecisionStatus.current:
                continue
            if not self._decision_scope_matches(decision.applies_to_projects, project_id):
                continue
            items.append(
                PortfolioDecisionInboxItem(
                    item_id=f"decision:{decision.decision_id}",
                    kind="CURRENT_DECISION",
                    project_id=None,
                    applies_to_projects=list(decision.applies_to_projects),
                    source_kind="DECISION_REGISTRY",
                    source_id=decision.decision_id,
                    status=decision.status.value,
                    summary=f"{decision.conflict_key} @ {decision.version}",
                    requires_human_action=False,
                    authority_reference=decision.authority_reference,
                    updated_at=decision.effective_at,
                )
            )

        for lifecycle_decision in lifecycle_records:
            if lifecycle_decision.status != LifecycleRecordStatus.current:
                continue
            if not self._project_matches(lifecycle_decision.project_id, project_id):
                continue
            items.append(
                PortfolioDecisionInboxItem(
                    item_id=f"lifecycle:{lifecycle_decision.decision_id}",
                    kind="CURRENT_DECISION",
                    project_id=lifecycle_decision.project_id,
                    applies_to_projects=[lifecycle_decision.project_id],
                    source_kind="LIFECYCLE_DECISION_REGISTRY",
                    source_id=lifecycle_decision.decision_id,
                    status=f"{lifecycle_decision.stage.value}:{lifecycle_decision.disposition.value}",
                    summary="Current exact-head lifecycle lifecycle_decision.",
                    requires_human_action=False,
                    subject_sha=lifecycle_decision.subject_sha,
                    lifecycle_stage=lifecycle_decision.stage.value,
                    authority_reference=lifecycle_decision.authority_reference,
                    updated_at=lifecycle_decision.decided_at,
                )
            )

        change_snapshot = self._changes.snapshot()
        for change in change_snapshot.items:
            if change.status == ProjectChangeInboxStatus.resolved:
                continue
            if not self._project_matches(change.project_id, project_id):
                continue
            items.append(
                PortfolioDecisionInboxItem(
                    item_id=f"change:{change.inbox_item_id}",
                    kind="CHANGE_REVIEW",
                    project_id=change.project_id,
                    applies_to_projects=[change.project_id],
                    source_kind="PROJECT_CHANGE_INBOX",
                    source_id=change.inbox_item_id,
                    status=change.status.value,
                    summary=f"{change.event_type.value} from {change.source_project_id}",
                    requires_human_action=True,
                    authority_reference=change.authority_reference,
                    updated_at=change.updated_at,
                )
            )

        for project in projects:
            if not self._project_matches(project.project_id, project_id):
                continue
            for index, blocker in enumerate(project.blockers):
                items.append(
                    PortfolioDecisionInboxItem(
                        item_id=f"project:{project.project_id}:blocker:{index}",
                        kind="BLOCKER",
                        project_id=project.project_id,
                        applies_to_projects=[project.project_id],
                        source_kind="PROJECT_REALITY",
                        source_id=project.project_id,
                        status=project.readiness,
                        summary="Project reality has a recorded blocker.",
                        requires_human_action=True,
                        subject_sha=(
                            project.observed_head.lower()
                            if project.observed_head is not None
                            else None
                        ),
                        blocker=blocker,
                        updated_at=project.last_probe_at,
                    )
                )

        items.sort(
            key=lambda item: (
                not item.requires_human_action,
                item.project_id or "",
                item.kind,
                item.source_kind,
                item.source_id,
                item.item_id,
            )
        )
        return PortfolioDecisionInboxSummary(
            total=len(items),
            pending_approvals=sum(item.kind == "PENDING_APPROVAL" for item in items),
            pending_decisions=sum(item.kind == "PENDING_DECISION" for item in items),
            blockers=sum(item.kind == "BLOCKER" for item in items),
            change_reviews=sum(item.kind == "CHANGE_REVIEW" for item in items),
            current_decisions=sum(item.kind == "CURRENT_DECISION" for item in items),
            items=items,
        )
