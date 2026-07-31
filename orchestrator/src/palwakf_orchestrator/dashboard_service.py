from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.dashboard_contracts import (
    ConnectionReadinessSummary,
    DashboardAction,
    DashboardSummary,
    EvidenceIndexItem,
    FreshnessState,
    OperationalAlertSummary,
    PortfolioProjectSummary,
    RecentActivityItem,
    ResumeCheckpointSummary,
    TaskStatusSummary,
    ToolHealthSummary,
)
from palwakf_orchestrator.local_product import LocalProductService
from palwakf_orchestrator.operator_contracts import OperatorTaskRecord, OperatorTaskStatus
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.project_contracts import ExternalProjectRealityReport
from palwakf_orchestrator.project_service import ExternalProjectService

_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")
_FINGERPRINT = re.compile(r"^[0-9A-Fa-f]{40,64}$")
_TERMINAL_TASK_STATUSES = {
    OperatorTaskStatus.failed,
    OperatorTaskStatus.verified,
    OperatorTaskStatus.timed_out,
    OperatorTaskStatus.cancelled,
}


class DashboardAggregationService:
    def __init__(
        self,
        operator: OperatorService,
        projects: ExternalProjectService,
        connected: ConnectedApplicationService,
        store: StateStore,
        workspace_root: Path,
        *,
        stale_seconds: int = 86_400,
        now: Callable[[], datetime] | None = None,
        local_product: LocalProductService | None = None,
    ) -> None:
        self._operator = operator
        self._projects = projects
        self._connected = connected
        self._store = store
        self._workspace_root = workspace_root.resolve()
        self._stale_after = timedelta(seconds=stale_seconds)
        self._now = now or (lambda: datetime.now(UTC))
        self._local_product = local_product

    def summary(self) -> DashboardSummary:
        now = self._now()
        tasks = self._operator.list_tasks()
        project_summaries = self._project_summaries(tasks, now)
        alerts = self.alerts()
        task_summary = self._task_summary(tasks, now)
        tool_summary = self._tool_summary()
        readiness = self._connected.readiness()
        metrics = self._connected.metrics()
        connection = ConnectionReadinessSummary(
            mode=readiness.mode.value,
            ready=readiness.ready,
            authentication_configured=readiness.authentication_configured,
            store_healthy=readiness.store_healthy,
            workers_started=readiness.workers_started,
            local_secure=readiness.mode.value == "LOCAL_SECURE_MODE",
            last_successful_codex_execution_at=metrics.last_successful_codex_execution_at,
        )
        return DashboardSummary(
            generated_at=now,
            freshness=FreshnessState.fresh,
            portfolio_total=len(project_summaries),
            portfolio_ready=sum(item.readiness == "READY" for item in project_summaries),
            portfolio_attention_required=sum(item.attention_required for item in project_summaries),
            active_repository_writers=sum(item.active_writer for item in project_summaries),
            human_action_required=sum(item.severity in {"warning", "critical"} for item in alerts),
            tasks=task_summary,
            tools=tool_summary,
            alert_count=len(alerts),
            critical_alert_count=sum(item.severity == "critical" for item in alerts),
            projects=project_summaries,
            connection=connection,
            checkpoints=self._checkpoints(tasks),
            actions=self._actions(project_summaries, alerts, task_summary),
            managed_workspace=(
                self._local_product.status() if self._local_product is not None else None
            ),
        )

    def alerts(self) -> list[OperationalAlertSummary]:
        now = self._now()
        values: list[OperationalAlertSummary] = []
        for alert in self._connected.tool_health.alerts():
            values.append(
                OperationalAlertSummary(
                    alert_id=alert.alert_id,
                    severity=alert.severity.value,
                    source_kind="tool",
                    source_id=alert.adapter_id,
                    code=alert.code,
                    message=alert.message,
                    required_action=alert.operator_action,
                    observed_at=alert.observed_at,
                    freshness=FreshnessState.fresh,
                )
            )
        for project in self._projects.list_projects():
            freshness = self._freshness(project.last_probe_at, now)
            if project.status.value in {"blocked", "drifted"} or freshness != FreshnessState.fresh:
                code = (
                    "PROJECT_BLOCKED"
                    if project.status.value == "blocked"
                    else "PROJECT_HEAD_DRIFT"
                    if project.status.value == "drifted"
                    else "PROJECT_REALITY_STALE_OR_UNAVAILABLE"
                )
                values.append(
                    OperationalAlertSummary(
                        alert_id=f"project-{project.project_id}-{code.lower()}",
                        severity="critical" if project.status.value == "blocked" else "warning",
                        source_kind="project",
                        source_id=project.project_id,
                        code=code,
                        message=(
                            project.blockers[0]
                            if project.blockers
                            else "Project reality requires a current read-only probe"
                        ),
                        required_action="Review the project reality before governed work",
                        observed_at=project.updated_at,
                        freshness=freshness,
                    )
                )
        for task in self._operator.list_tasks():
            if task.blocker or task.status in {
                OperatorTaskStatus.failed,
                OperatorTaskStatus.drifted,
                OperatorTaskStatus.timed_out,
                OperatorTaskStatus.awaiting_approval,
                OperatorTaskStatus.pending_verification,
            }:
                values.append(
                    OperationalAlertSummary(
                        alert_id=f"task-{task.task_id}-{task.status.value}",
                        severity=(
                            "critical"
                            if task.status
                            in {
                                OperatorTaskStatus.failed,
                                OperatorTaskStatus.drifted,
                                OperatorTaskStatus.timed_out,
                            }
                            else "warning"
                        ),
                        source_kind="task",
                        source_id=task.task_id,
                        code=f"TASK_{task.status.value.upper()}",
                        message=task.blocker or task.last_event,
                        required_action=(
                            "Resolve the recorded blocker"
                            if task.blocker
                            else "Review the task checkpoint"
                        ),
                        observed_at=task.updated_at,
                        freshness=self._freshness(task.updated_at, now),
                        evidence_reference=self._first_safe_reference(task.evidence),
                    )
                )
        deduplicated = {item.alert_id: item for item in values}
        return sorted(
            deduplicated.values(),
            key=lambda item: (item.severity != "critical", -item.observed_at.timestamp()),
        )[:100]

    def activity(self, limit: int) -> list[RecentActivityItem]:
        values: list[RecentActivityItem] = []
        for task in self._operator.list_tasks():
            if task.events:
                for index, event in enumerate(task.events):
                    values.append(
                        RecentActivityItem(
                            activity_id=f"task-{task.task_id}-{index}",
                            kind="task_event",
                            subject_id=task.task_id,
                            title=event.event_type,
                            detail=event.message,
                            occurred_at=event.occurred_at,
                            status=event.status.value,
                            provenance="OPERATOR_TASK_STORE",
                        )
                    )
            else:
                values.append(
                    RecentActivityItem(
                        activity_id=f"task-{task.task_id}-current",
                        kind="task_event",
                        subject_id=task.task_id,
                        title="task_state",
                        detail=task.last_event,
                        occurred_at=task.updated_at,
                        status=task.status.value,
                        provenance="OPERATOR_TASK_STORE",
                    )
                )
        for project in self._projects.list_projects():
            if project.last_probe_at is not None:
                values.append(
                    RecentActivityItem(
                        activity_id=f"project-{project.project_id}-probe",
                        kind="project_probe",
                        subject_id=project.project_id,
                        title="project_reality_probe",
                        detail=f"Observed {project.repository_full_name}",
                        occurred_at=project.last_probe_at,
                        status=project.status.value,
                        provenance="EXTERNAL_PROJECT_REGISTRY",
                    )
                )
        state = self._store.load()
        for index, raw in enumerate(state.get("audit", [])[-100:]):
            if not isinstance(raw, dict):
                continue
            occurred_at = self._parse_datetime(raw.get("occurred_at"))
            if occurred_at is None:
                continue
            values.append(
                RecentActivityItem(
                    activity_id=f"audit-{index}-{raw.get('correlation_id', 'unknown')}",
                    kind="audit",
                    subject_id=str(raw.get("task_id") or raw.get("client_id") or "service"),
                    title=str(raw.get("action") or "service_action"),
                    detail=str(raw.get("outcome") or "unknown"),
                    occurred_at=occurred_at,
                    status=str(raw.get("outcome") or "unknown"),
                    provenance="CONNECTED_SERVICE_AUDIT",
                )
            )
        values.sort(key=lambda item: item.occurred_at, reverse=True)
        return values[:limit]

    def evidence(self, limit: int) -> list[EvidenceIndexItem]:
        values: list[EvidenceIndexItem] = []
        for task in self._operator.list_tasks():
            for index, reference in enumerate(task.evidence):
                safe = self._safe_reference(reference)
                if safe is None:
                    continue
                values.append(
                    EvidenceIndexItem(
                        evidence_id=f"task-{task.task_id}-{index}",
                        association_kind="task",
                        association_id=task.task_id,
                        evidence_type="task_receipt",
                        observed_at=task.updated_at,
                        fingerprint=None,
                        safe_reference=safe,
                        status=task.status.value,
                        provenance="TASK_STORE",
                    )
                )
        evidence_root = self._workspace_root / "evidence"
        if evidence_root.is_dir():
            for path in sorted(evidence_root.glob("*.json")):
                relative = path.relative_to(self._workspace_root).as_posix()
                raw = self._read_json(path)
                association_kind: Literal["task", "project", "workspace"] = "workspace"
                association_id: str | None = None
                if raw.get("project_id"):
                    association_kind = "project"
                    association_id = str(raw["project_id"])
                elif raw.get("task_id"):
                    association_kind = "task"
                    association_id = str(raw["task_id"])
                observed = self._parse_datetime(
                    raw.get("observed_at") or raw.get("generated_at") or raw.get("completed_at")
                )
                fingerprint = self._fingerprint(raw)
                values.append(
                    EvidenceIndexItem(
                        evidence_id=hashlib.sha256(relative.encode()).hexdigest()[:16],
                        association_kind=association_kind,
                        association_id=association_id,
                        evidence_type=str(
                            raw.get("report_version")
                            or raw.get("profile_version")
                            or raw.get("evidence_type")
                            or "repository_evidence"
                        )[:120],
                        observed_at=observed,
                        fingerprint=fingerprint,
                        safe_reference=relative,
                        status=str(raw.get("status") or "RECORDED")[:80],
                        provenance="REPOSITORY_EVIDENCE",
                    )
                )
        values.sort(
            key=lambda item: item.observed_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return values[:limit]

    def _project_summaries(
        self, tasks: list[OperatorTaskRecord], now: datetime
    ) -> list[PortfolioProjectSummary]:
        result: list[PortfolioProjectSummary] = []
        if self._local_product is not None:
            workspace = self._local_product.status()
            heads_match = bool(
                workspace.local_head
                and workspace.local_head == workspace.remote_head
                and workspace.local_head == workspace.pull_request_head
            )
            ready = (
                heads_match
                and workspace.worktree_clean is True
                and workspace.pull_request_state == "OPEN"
                and workspace.ci_status == "SUCCESS"
            )
            blockers = [
                code
                for condition, code in (
                    (not heads_match, "HEADS_NOT_ALIGNED"),
                    (workspace.worktree_clean is not True, "WORKTREE_NOT_CLEAN"),
                    (workspace.pull_request_state != "OPEN", "PR_NOT_OPEN"),
                    (workspace.ci_status != "SUCCESS", "CI_NOT_SUCCESS"),
                )
                if condition
            ]
            result.append(
                PortfolioProjectSummary(
                    project_id="PALWAKF_WORKSPACE_MANAGER",
                    display_name="PalWakf Workspace Manager",
                    repository_full_name=workspace.repository,
                    status="registered",
                    readiness="READY" if ready else "ATTENTION_REQUIRED",
                    attention_required=not ready,
                    observed_branch=workspace.branch,
                    observed_head=workspace.local_head,
                    last_probe_at=workspace.refreshed_at,
                    freshness=FreshnessState.fresh,
                    stack=["Flutter", "Python", "FastAPI"],
                    package_managers=["pub", "uv"],
                    ci_status=workspace.ci_status,
                    deployment_status=workspace.preview_status,
                    drift_status="ALIGNED" if heads_match else "DRIFTED",
                    blockers=blockers,
                    tool_gap_count=sum(
                        state.status == "BLOCKED"
                        for state in (
                            workspace.github,
                            workspace.agents_sdk,
                            workspace.codex,
                            workspace.authentication,
                            workspace.orchestrator,
                        )
                    ),
                    top_candidate_id=None,
                    top_candidate_title=None,
                    task_count=sum(
                        task.project_id == "PALWAKF_WORKSPACE_MANAGER" for task in tasks
                    ),
                    active_writer=workspace.active_writer_task_id is not None,
                    evidence_count=0,
                    provenance="LOCAL_MANAGED_WORKSPACE",
                )
            )
        for project in self._projects.list_projects():
            report: ExternalProjectRealityReport | None
            try:
                report = self._projects.reality(project.project_id)
            except Exception:
                report = None
            freshness = self._freshness(project.last_probe_at, now)
            project_tasks = [
                task
                for task in tasks
                if task.project_id == project.project_id
                or task.repository.casefold() == project.repository_full_name.casefold()
            ]
            profile = report.capability_profile if report else None
            candidates = report.candidate_work_items if report else []
            readiness = (
                "BLOCKED"
                if project.status.value == "blocked"
                else "ATTENTION_REQUIRED"
                if project.status.value == "drifted"
                or freshness != FreshnessState.fresh
                or project.blockers
                else "READY"
            )
            result.append(
                PortfolioProjectSummary(
                    project_id=project.project_id,
                    display_name=project.display_name,
                    repository_full_name=project.repository_full_name,
                    status=project.status.value,
                    readiness=readiness,
                    attention_required=readiness != "READY",
                    observed_branch=project.observed_branch,
                    observed_head=project.observed_head,
                    last_probe_at=project.last_probe_at,
                    freshness=freshness,
                    stack=project.stack,
                    package_managers=project.package_managers,
                    ci_status=report.ci_status if report else "UNKNOWN",
                    deployment_status=report.deployment_status if report else "UNKNOWN",
                    drift_status=report.drift_status if report else "UNKNOWN",
                    blockers=project.blockers,
                    tool_gap_count=(
                        len(profile.blocked_tools) + len(profile.conditional_tools)
                        if profile
                        else 0
                    ),
                    top_candidate_id=candidates[0].candidate_id if candidates else None,
                    top_candidate_title=candidates[0].title if candidates else None,
                    task_count=len(project_tasks),
                    active_writer=self._store.writer_for(project.repository_full_name) is not None,
                    evidence_count=len(project.source_of_truth_references),
                )
            )
        return result

    def _task_summary(self, tasks: list[OperatorTaskRecord], now: datetime) -> TaskStatusSummary:
        counts = Counter(task.status.value for task in tasks)
        stale = sum(
            task.status not in _TERMINAL_TASK_STATUSES
            and self._freshness(task.updated_at, now) == FreshnessState.stale
            for task in tasks
        )
        verified = sorted(
            (task for task in tasks if task.status == OperatorTaskStatus.verified),
            key=lambda task: task.updated_at,
            reverse=True,
        )
        active = [
            task.task_id
            for task in tasks
            if task.status
            in {
                OperatorTaskStatus.queued,
                OperatorTaskStatus.running,
                OperatorTaskStatus.awaiting_approval,
                OperatorTaskStatus.pending_verification,
            }
        ]
        return TaskStatusSummary(
            total=len(tasks),
            pending=counts["pending"],
            queued=counts["queued"],
            running=counts["running"],
            awaiting_approval=counts["awaiting_approval"],
            failed=counts["failed"],
            pending_verification=counts["pending_verification"],
            verified=counts["verified"],
            drifted=counts["drifted"],
            timed_out=counts["timed_out"],
            cancelled=counts["cancelled"],
            stale=stale,
            active_task_ids=active[:20],
            latest_verified_task_id=verified[0].task_id if verified else None,
            latest_verified_at=verified[0].updated_at if verified else None,
        )

    def _tool_summary(self) -> ToolHealthSummary:
        categories: Counter[str] = Counter()
        for item in self._connected.tool_health.list_health():
            permission = str(item.permission.value or "").casefold()
            freshness = str(item.freshness.value or "").casefold()
            authentication = str(item.authentication.value or "").casefold()
            connection = str(item.connection.value or "").casefold()
            if permission == "blocked":
                categories["blocked"] += 1
            elif freshness != "fresh":
                categories["stale"] += 1
            elif authentication in {"set", "not_applicable"} or connection:
                categories["healthy"] += 1
            elif item.required:
                categories["degraded"] += 1
            else:
                categories["unknown"] += 1
        total = sum(categories.values())
        attention = total - categories["healthy"]
        return ToolHealthSummary(
            total=total,
            healthy=categories["healthy"],
            degraded=categories["degraded"],
            blocked=categories["blocked"],
            stale=categories["stale"],
            unknown=categories["unknown"],
            required_attention=attention,
        )

    def _checkpoints(self, tasks: list[OperatorTaskRecord]) -> list[ResumeCheckpointSummary]:
        values: list[ResumeCheckpointSummary] = []
        for task in sorted(tasks, key=lambda item: item.updated_at, reverse=True):
            if task.status in _TERMINAL_TASK_STATUSES:
                continue
            next_action = (
                "Verify the recorded result"
                if task.status == OperatorTaskStatus.pending_verification
                else "Resolve the recorded blocker"
                if task.blocker
                else "Resume from the latest task event"
            )
            values.append(
                ResumeCheckpointSummary(
                    checkpoint_id=f"task-{task.task_id}",
                    task_id=task.task_id,
                    status=task.status.value,
                    updated_at=task.updated_at,
                    next_action=next_action,
                    evidence_reference=self._first_safe_reference(task.evidence),
                )
            )
        return values[:10]

    @staticmethod
    def _actions(
        projects: list[PortfolioProjectSummary],
        alerts: list[OperationalAlertSummary],
        tasks: TaskStatusSummary,
    ) -> list[DashboardAction]:
        return [
            DashboardAction(
                action_id="review-alerts",
                label="Review operational alerts",
                route="/alerts",
                enabled=bool(alerts),
                disabled_reason=None if alerts else "No current alerts",
                authority="READ_ONLY_REVIEW",
            ),
            DashboardAction(
                action_id="resume-tasks",
                label="Open governed tasks",
                route="/tasks",
                enabled=bool(tasks.active_task_ids),
                disabled_reason=None if tasks.active_task_ids else "No active task checkpoint",
                authority="EXISTING_TASK_WORKFLOW",
            ),
            DashboardAction(
                action_id="review-projects",
                label="Review project reality",
                route="/projects",
                enabled=bool(projects),
                disabled_reason=None if projects else "No registered projects",
                authority="READ_ONLY_PROJECT_REALITY",
            ),
        ]

    def _freshness(self, observed_at: datetime | None, now: datetime) -> FreshnessState:
        if observed_at is None:
            return FreshnessState.unknown
        return (
            FreshnessState.stale
            if now - observed_at.astimezone(UTC) > self._stale_after
            else FreshnessState.fresh
        )

    @staticmethod
    def _safe_reference(value: str) -> str | None:
        candidate = value.strip().replace("\\", "/")
        if (
            not candidate
            or len(candidate) > 240
            or _ABSOLUTE_PATH.match(value)
            or ".." in candidate.split("/")
            or any(token in candidate.casefold() for token in ("api_key", "token=", "secret="))
        ):
            return None
        return candidate

    def _first_safe_reference(self, values: list[str]) -> str | None:
        return next(
            (safe for value in values if (safe := self._safe_reference(value)) is not None),
            None,
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _fingerprint(raw: dict[str, Any]) -> str | None:
        for key in ("baseline_fingerprint", "fingerprint", "sha256"):
            value = raw.get(key)
            if isinstance(value, str) and _FINGERPRINT.fullmatch(value):
                return value.upper()
        return None
