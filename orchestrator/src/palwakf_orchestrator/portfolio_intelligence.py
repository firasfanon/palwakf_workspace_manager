from __future__ import annotations

import hashlib
import json
from collections import deque
from datetime import UTC, datetime
from typing import Any

from palwakf_orchestrator.dashboard_contracts import DashboardSummary, PortfolioProjectSummary
from palwakf_orchestrator.dashboard_service import DashboardAggregationService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.portfolio_intelligence_contracts import (
    ChangeItem,
    CriticalPathView,
    DependencyView,
    PortfolioCommandCenterSnapshot,
    PortfolioDecision,
    PortfolioKpi,
    PortfolioRecommendation,
    PortfolioRisk,
    ProjectForecast,
    ProjectIntelligence,
    RegistryEntity,
    ScoreFactor,
    SourceHealthItem,
    SourceHealthState,
    TruthState,
)
from palwakf_orchestrator.typed_dependency_graph import (
    DependencyEdgeStatus,
    TypedDependencyGraphStore,
)


class PortfolioIntelligenceService:
    """Read-only portfolio projection over existing governed Workspace sources."""

    def __init__(
        self,
        dashboard: DashboardAggregationService,
        state_store: StateStore,
    ) -> None:
        self._dashboard = dashboard
        self._state_store = state_store
        self._dependency_graph = TypedDependencyGraphStore(state_store)

    def snapshot(self) -> PortfolioCommandCenterSnapshot:
        summary = self._dashboard.summary()
        alerts = self._dashboard.alerts()
        activity = self._dashboard.activity(30)
        evidence = self._dashboard.evidence(50)
        dependencies, critical_path = self._dependencies()

        source_health = self._source_health(summary, evidence)
        truth_confidence = self._truth_confidence(source_health)
        truth_state = self._truth_state(source_health, truth_confidence)
        projects = [self._project(item) for item in summary.projects]
        recommendations = self._recommendations(summary, projects)
        capabilities, skills, tools, agents, providers = self._registries(summary)

        payload = {
            "projects": [
                {
                    "project_id": item.project_id,
                    "head": item.observed_head,
                    "readiness": item.readiness,
                    "priority": item.priority_score,
                }
                for item in projects
            ],
            "decision_items": [
                {
                    "id": item.item_id,
                    "status": item.status,
                    "subject_sha": item.subject_sha,
                }
                for item in summary.decision_inbox.items
            ],
            "sources": [
                {"id": item.source_id, "state": item.state.value, "freshness": item.freshness}
                for item in source_health
            ],
            "dependencies": [item.model_dump(mode="json") for item in dependencies],
        }
        snapshot_id = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()[:20]

        risks = [
            PortfolioRisk(
                risk_id=item.alert_id,
                severity=item.severity.upper(),
                subject_id=item.source_id,
                summary_ar=item.message,
                required_action_ar=item.required_action,
                evidence_ref=item.evidence_reference,
            )
            for item in alerts
        ]
        decisions = [
            PortfolioDecision(
                decision_id=item.item_id,
                kind=item.kind,
                project_id=item.project_id,
                summary_ar=item.summary,
                requires_human_action=item.requires_human_action,
                status=item.status,
                authority_reference=item.authority_reference,
            )
            for item in summary.decision_inbox.items
        ]
        changes = [
            ChangeItem(
                change_id=item.activity_id,
                subject_id=item.subject_id,
                title=item.title,
                detail=item.detail,
                occurred_at=item.occurred_at,
                status=item.status,
                provenance=item.provenance,
            )
            for item in activity
        ]
        return PortfolioCommandCenterSnapshot(
            generated_at=datetime.now(UTC),
            snapshot_id=snapshot_id,
            truth_state=truth_state,
            truth_confidence=truth_confidence,
            truth_explanation_ar=self._truth_explanation(source_health),
            source_health=source_health,
            kpis=self._kpis(summary, projects, truth_confidence, critical_path),
            projects=projects,
            recommendations=recommendations,
            dependencies=dependencies,
            critical_path=critical_path,
            forecasts=[item.forecast for item in projects],
            capabilities=capabilities,
            skills=skills,
            tools=tools,
            agents=agents,
            providers=providers,
            risks=risks,
            decisions=decisions,
            recent_changes=changes,
            evidence_refs=[item.safe_reference for item in evidence],
            provenance=[
                *summary.provenance,
                "PORTFOLIO_INTELLIGENCE_READ_ONLY_PROJECTION_V1",
                "TYPED_DEPENDENCY_GRAPH_WHEN_IMPORTED",
                "NO_SECOND_SOVEREIGN_STATE_STORE",
            ],
        )

    def recommendations(self) -> list[PortfolioRecommendation]:
        snapshot = self.snapshot()
        return snapshot.recommendations

    def critical_path(self) -> CriticalPathView:
        return self.snapshot().critical_path

    def forecasts(self) -> list[ProjectForecast]:
        return self.snapshot().forecasts

    def capabilities(self) -> list[RegistryEntity]:
        return self.snapshot().capabilities

    def skills(self) -> list[RegistryEntity]:
        return self.snapshot().skills

    def tools(self) -> list[RegistryEntity]:
        return self.snapshot().tools

    def agents(self) -> list[RegistryEntity]:
        return self.snapshot().agents

    def providers(self) -> list[RegistryEntity]:
        return self.snapshot().providers

    def dependencies(self) -> list[DependencyView]:
        return self.snapshot().dependencies

    def risks(self) -> list[PortfolioRisk]:
        return self.snapshot().risks

    def decisions(self) -> list[PortfolioDecision]:
        return self.snapshot().decisions

    def history(self) -> list[ChangeItem]:
        return self.snapshot().recent_changes

    def _source_health(
        self,
        summary: DashboardSummary,
        evidence: list[Any],
    ) -> list[SourceHealthItem]:
        now = datetime.now(UTC)
        workspace = summary.managed_workspace
        github_state = (
            self._capability_health(workspace.github.status)
            if workspace is not None
            else SourceHealthState.unknown
        )
        runtime_state = (
            self._capability_health(workspace.orchestrator.status)
            if workspace is not None
            else SourceHealthState.unknown
        )
        registry_state = (
            SourceHealthState.healthy if summary.portfolio_total > 0 else SourceHealthState.unknown
        )
        evidence_state = SourceHealthState.healthy if evidence else SourceHealthState.unknown

        return [
            SourceHealthItem(
                source_id="WORKSPACE_RUNTIME",
                label_ar="واقع التشغيل المحلي",
                state=(
                    SourceHealthState.healthy
                    if summary.connection.ready and runtime_state == SourceHealthState.healthy
                    else SourceHealthState.degraded
                ),
                freshness="LIVE",
                detail_ar=(
                    "Orchestrator متصل ويستجيب ضمن وضع التشغيل المحلي الآمن."
                    if summary.connection.ready
                    else "التشغيل المحلي غير جاهز بالكامل."
                ),
                authority="LOCAL_EXECUTION_REALITY",
                observed_at=now,
            ),
            SourceHealthItem(
                source_id="GITHUB_CODE_TRUTH",
                label_ar="حقيقة الكود في GitHub",
                state=github_state,
                freshness="LIVE_OR_LAST_OBSERVED",
                detail_ar=(
                    "حالة GitHub مأخوذة من Managed Workspace runtime readback."
                    if workspace is not None
                    else "لا توجد قراءة GitHub مرتبطة بالـruntime الحالي."
                ),
                authority="GITHUB_CODE_TRUTH",
                observed_at=workspace.refreshed_at if workspace is not None else None,
            ),
            SourceHealthItem(
                source_id="PROJECT_REALITY_REGISTRY",
                label_ar="سجل واقع المشاريع",
                state=registry_state,
                freshness=summary.freshness.value,
                detail_ar=f"عدد المشاريع المرصودة: {summary.portfolio_total}.",
                authority="WORKSPACE_PROJECT_REALITY_PROJECTION",
                observed_at=summary.generated_at,
            ),
            SourceHealthItem(
                source_id="DECISION_AND_CHANGE_REGISTRIES",
                label_ar="القرارات والتغييرات",
                state=SourceHealthState.healthy,
                freshness="CURRENT_RUNTIME_STATE",
                detail_ar=(
                    f"عناصر صندوق القرار الحالية: {summary.decision_inbox.total}; "
                    "إسقاط قراءة فقط من السجلات الدائمة."
                ),
                authority=summary.decision_inbox.durability,
                observed_at=summary.generated_at,
            ),
            SourceHealthItem(
                source_id="EVIDENCE_INDEX",
                label_ar="فهرس الأدلة",
                state=evidence_state,
                freshness="CURRENT_RUNTIME_SCAN",
                detail_ar=(
                    f"تم رصد {len(evidence)} مرجع دليل آمن."
                    if evidence
                    else "لا توجد مراجع أدلة متاحة في القراءة الحالية."
                ),
                authority="REPOSITORY_AND_TASK_EVIDENCE",
                observed_at=summary.generated_at,
            ),
            SourceHealthItem(
                source_id="WORKSPACE_DRIVE_SOVEREIGN",
                label_ar="Workspace Drive السيادي",
                state=SourceHealthState.unknown,
                freshness="NO_LIVE_RUNTIME_ADAPTER",
                detail_ar=(
                    "Drive يبقى المصدر السيادي للوثائق، لكن runtime الحالي لا يملك "
                    "Live Drive adapter؛ لا تُفسر هذه الحالة كغياب للوثائق."
                ),
                authority="WORKSPACE_DRIVE_SOVEREIGN",
                observed_at=None,
            ),
        ]

    @staticmethod
    def _capability_health(status: str) -> SourceHealthState:
        normalized = status.strip().upper()
        if normalized in {
            "READY",
            "AVAILABLE",
            "CONNECTED",
            "VERIFIED",
            "SUCCESS",
            "HEALTHY",
            "CONFIGURED",
        }:
            return SourceHealthState.healthy
        if normalized in {
            "BLOCKED",
            "DEGRADED",
            "SUSPENDED_BY_POLICY",
            "UNAVAILABLE",
            "FAILED",
        }:
            return SourceHealthState.degraded
        return SourceHealthState.unknown

    @staticmethod
    def _truth_confidence(source_health: list[SourceHealthItem]) -> int:
        scores = {
            SourceHealthState.healthy: 100,
            SourceHealthState.degraded: 55,
            SourceHealthState.unknown: 35,
            SourceHealthState.unavailable: 0,
        }
        weights = {
            "WORKSPACE_RUNTIME": 25,
            "GITHUB_CODE_TRUTH": 20,
            "PROJECT_REALITY_REGISTRY": 20,
            "DECISION_AND_CHANGE_REGISTRIES": 15,
            "EVIDENCE_INDEX": 10,
            "WORKSPACE_DRIVE_SOVEREIGN": 10,
        }
        total = sum(scores[item.state] * weights.get(item.source_id, 0) for item in source_health)
        return round(total / max(sum(weights.values()), 1))

    @staticmethod
    def _truth_state(
        source_health: list[SourceHealthItem],
        confidence: int,
    ) -> TruthState:
        if any(item.state == SourceHealthState.unavailable for item in source_health):
            return TruthState.degraded if confidence >= 40 else TruthState.unknown
        if confidence >= 75:
            return TruthState.verified
        if confidence >= 40:
            return TruthState.degraded
        return TruthState.unknown

    @staticmethod
    def _truth_explanation(source_health: list[SourceHealthItem]) -> list[str]:
        values = [
            f"{item.label_ar}: {item.state.value} — {item.detail_ar}" for item in source_health
        ]
        values.append("أي مصدر UNKNOWN لا يُعامل كدليل على عدم وجود الكيان.")
        return values

    def _project(self, item: PortfolioProjectSummary) -> ProjectIntelligence:
        factors = [
            ScoreFactor(
                factor="BLOCKING_IMPACT",
                value=100 if item.blockers else 0,
                weight=35,
                explanation_ar=("يوجد مانع مسجل." if item.blockers else "لا يوجد مانع صريح مسجل."),
            ),
            ScoreFactor(
                factor="DRIFT_RISK",
                value=(
                    0
                    if item.drift_status.upper() in {"ALIGNED", "UNCHANGED"}
                    else 100
                    if item.drift_status.upper() not in {"UNKNOWN", "NOT_DISCOVERED"}
                    else 50
                ),
                weight=25,
                explanation_ar=f"حالة الانحراف: {item.drift_status}.",
            ),
            ScoreFactor(
                factor="CAPABILITY_GAP",
                value=min(100, item.tool_gap_count * 25),
                weight=15,
                explanation_ar=f"فجوات الأدوات/القدرات المرصودة: {item.tool_gap_count}.",
            ),
            ScoreFactor(
                factor="FRESHNESS_RISK",
                value=0 if item.freshness.value == "FRESH" else 100,
                weight=15,
                explanation_ar=f"حداثة الواقع: {item.freshness.value}.",
            ),
            ScoreFactor(
                factor="ACTIVE_WORK",
                value=min(100, item.task_count * 10),
                weight=10,
                explanation_ar=f"عدد المهام المرتبطة: {item.task_count}.",
            ),
        ]
        score = round(sum(f.value * f.weight for f in factors) / 100)
        truth = (
            TruthState.verified
            if item.freshness.value == "FRESH"
            and item.drift_status.upper() in {"ALIGNED", "UNCHANGED"}
            else TruthState.degraded
            if item.freshness.value != "UNKNOWN"
            else TruthState.unknown
        )
        maturity = (
            "VERIFIED_RUNTIME"
            if item.readiness == "READY" and item.ci_status == "SUCCESS"
            else "READY_OBSERVED"
            if item.readiness == "READY"
            else "ATTENTION_REQUIRED"
        )
        next_action = self._next_action(item)
        forecast = self._forecast(item)
        return ProjectIntelligence(
            project_id=item.project_id,
            display_name=item.display_name,
            repository_full_name=item.repository_full_name,
            truth_state=truth,
            current_status=item.status,
            readiness=item.readiness,
            maturity_state=maturity,
            scope_progress_percent=None,
            scope_progress_basis="UNAVAILABLE_NO_CANONICAL_SCOPE_PROFILE_IN_RUNTIME",
            priority_score=score,
            priority_factors=factors,
            next_action_ar=next_action,
            blockers=item.blockers,
            observed_branch=item.observed_branch,
            observed_head=item.observed_head,
            ci_status=item.ci_status,
            deployment_status=item.deployment_status,
            drift_status=item.drift_status,
            evidence_count=item.evidence_count,
            task_count=item.task_count,
            tool_gap_count=item.tool_gap_count,
            last_verified_at=item.last_probe_at,
            forecast=forecast,
            evidence_refs=[],
        )

    @staticmethod
    def _next_action(item: PortfolioProjectSummary) -> str:
        if item.blockers:
            return "معالجة المانع المسجل قبل أي توسع في التنفيذ."
        if item.drift_status.upper() not in {"ALIGNED", "UNCHANGED", "UNKNOWN"}:
            return "تنفيذ Fresh Reconciliation قبل أي قرار تطوير أو دمج."
        if item.freshness.value != "FRESH":
            return "تحديث قراءة واقع المشروع قبل الاعتماد على حالته."
        if item.tool_gap_count:
            return "مراجعة فجوة الأداة/القدرة قبل إضافة تطوير جديد."
        if item.top_candidate_title:
            return f"مراجعة المرشح الحالي: {item.top_candidate_title}"
        return "NO_ACTION — لا توجد إشارة تشغيلية تفرض تطويرًا جديدًا الآن."

    @staticmethod
    def _forecast(item: PortfolioProjectSummary) -> ProjectForecast:
        conditions: list[str] = []
        if item.blockers:
            conditions.append("إغلاق الموانع الحالية.")
        if item.freshness.value != "FRESH":
            conditions.append("تحديث واقع المشروع.")
        if item.drift_status.upper() not in {"ALIGNED", "UNCHANGED"}:
            conditions.append("إغلاق الانحراف أو إثبات عدم أثره.")
        return ProjectForecast(
            project_id=item.project_id,
            status="CONDITIONAL" if conditions else "UNAVAILABLE",
            p50=None,
            p80=None,
            confidence=0.35 if conditions else 0.2,
            conditions_ar=conditions
            or ["لا توجد بعد عينة cycle-time كافية لإنتاج P50/P80 دون اختلاق."],
            basis="NO_FABRICATED_ETA_WITHOUT_HISTORICAL_CYCLE_TIME",
        )

    def _recommendations(
        self,
        summary: DashboardSummary,
        projects: list[ProjectIntelligence],
    ) -> list[PortfolioRecommendation]:
        values: list[PortfolioRecommendation] = []
        for project in sorted(projects, key=lambda value: value.priority_score, reverse=True):
            recommendation_type: str | None = None
            reason = project.next_action_ar
            risk = "استمرار الوضع الحالي دون معالجة قد يبقي عدم اليقين أو الدين التشغيلي."
            if project.blockers:
                recommendation_type = "REVIEW_NOW"
            elif project.drift_status.upper() not in {"ALIGNED", "UNCHANGED", "UNKNOWN"}:
                recommendation_type = "RECONCILE_NOW"
            elif project.tool_gap_count:
                recommendation_type = "CLOSE_CAPABILITY_GAP"
            elif project.priority_score >= 45:
                recommendation_type = "ASSESS_NOW"
            if recommendation_type is None:
                continue
            values.append(
                PortfolioRecommendation(
                    recommendation_id=f"project-{project.project_id.lower()}-{recommendation_type.lower()}",
                    type=recommendation_type,
                    subject_id=project.project_id,
                    reason_ar=reason,
                    evidence_refs=project.evidence_refs,
                    affected_projects=[project.project_id],
                    unlock_count=0,
                    risk_if_deferred_ar=risk,
                    estimated_effort="UNKNOWN",
                    confidence=0.8 if project.truth_state == TruthState.verified else 0.55,
                )
            )

        for item in summary.decision_inbox.items:
            if not item.requires_human_action:
                continue
            values.append(
                PortfolioRecommendation(
                    recommendation_id=f"decision-{item.item_id.lower()}",
                    type="DECIDE_NOW",
                    subject_id=item.item_id,
                    reason_ar=item.summary,
                    evidence_refs=[item.authority_reference] if item.authority_reference else [],
                    affected_projects=item.applies_to_projects,
                    unlock_count=len(item.applies_to_projects),
                    risk_if_deferred_ar="يبقى القرار أو المسار المرتبط به في حالة انتظار بشري.",
                    estimated_effort="LOW",
                    confidence=0.95,
                )
            )
        return values[:20]

    def _dependencies(self) -> tuple[list[DependencyView], CriticalPathView]:
        try:
            graph = self._dependency_graph.current()
        except GovernanceError:
            return [], CriticalPathView(
                status="UNAVAILABLE",
                project_ids=[],
                most_blocking_project_id=None,
                reason_ar=(
                    "Typed Dependency Graph غير مستورد في runtime الحالي؛ "
                    "لا يتم اختلاق critical path من أسماء المشاريع أو النشاط."
                ),
            )

        active = [edge for edge in graph.edges if edge.status == DependencyEdgeStatus.active]
        views = [
            DependencyView(
                edge_id=edge.edge_id,
                producer_project_id=edge.producer_project_id,
                consumer_project_id=edge.consumer_project_id,
                kind=edge.kind.value,
                contract_id=edge.contract_id,
                version=edge.version,
                status=edge.status.value,
                evidence=list(edge.evidence),
            )
            for edge in active
        ]
        path, blocker, cycle = self._longest_dependency_path(graph.project_ids, views)
        return views, CriticalPathView(
            status="UNAVAILABLE" if cycle else "AVAILABLE",
            project_ids=[] if cycle else path,
            most_blocking_project_id=blocker,
            reason_ar=(
                "تعذر حساب المسار الحرج لأن graph يحتوي دورة اعتماد."
                if cycle
                else "أطول مسار اعتماد نشط محسوب من Typed Dependency Graph السيادي المستورد."
            ),
            evidence_refs=[graph.authority_reference],
        )

    @staticmethod
    def _longest_dependency_path(
        project_ids: tuple[str, ...],
        edges: list[DependencyView],
    ) -> tuple[list[str], str | None, bool]:
        outgoing: dict[str, list[str]] = {project: [] for project in project_ids}
        indegree: dict[str, int] = {project: 0 for project in project_ids}
        for edge in edges:
            outgoing.setdefault(edge.producer_project_id, []).append(edge.consumer_project_id)
            indegree[edge.consumer_project_id] = indegree.get(edge.consumer_project_id, 0) + 1
            indegree.setdefault(edge.producer_project_id, 0)

        queue = deque(project for project, count in indegree.items() if count == 0)
        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for child in outgoing.get(current, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(order) != len(indegree):
            blocker = max(outgoing, key=lambda key: len(outgoing[key]), default=None)
            return [], blocker, True

        distance = {project: 0 for project in order}
        parent: dict[str, str] = {}
        for current in order:
            for child in outgoing.get(current, []):
                if distance[current] + 1 > distance.get(child, 0):
                    distance[child] = distance[current] + 1
                    parent[child] = current
        end = max(distance, key=lambda project: distance[project], default=None)
        path: list[str] = []
        while end is not None:
            path.append(end)
            end = parent.get(end)
        path.reverse()
        blocker = max(outgoing, key=lambda key: len(outgoing[key]), default=None)
        return path, blocker, False

    def _registries(
        self,
        summary: DashboardSummary,
    ) -> tuple[
        list[RegistryEntity],
        list[RegistryEntity],
        list[RegistryEntity],
        list[RegistryEntity],
        list[RegistryEntity],
    ]:
        workspace = summary.managed_workspace
        capabilities: list[RegistryEntity] = []
        tools: list[RegistryEntity] = []
        if workspace is not None:
            for key, label, state in (
                ("GITHUB", "GitHub — حقيقة الكود", workspace.github),
                ("AGENTS_SDK", "Agents SDK — تشغيل الوكلاء", workspace.agents_sdk),
                ("CODEX", "Codex — مزود هندسي", workspace.codex),
                ("AUTH", "المصادقة المحلية", workspace.authentication),
                ("ORCHESTRATOR", "Workspace Orchestrator", workspace.orchestrator),
            ):
                status = state.status
                if key == "CODEX":
                    status = "SUSPENDED_BY_POLICY"
                capabilities.append(
                    RegistryEntity(
                        entity_id=f"CAP_{key}",
                        name_ar=label,
                        category="CAPABILITY",
                        lifecycle="VERIFIED"
                        if status.upper() in {"READY", "CONNECTED", "SUCCESS"}
                        else "OBSERVED",
                        status=status,
                        description_ar=(
                            "قدرة تشغيلية مرصودة من Managed Workspace؛ وجود القدرة لا يمنح سلطة."
                        ),
                        owner="PALWAKF_WORKSPACE_MANAGER",
                        deferred_reason_ar=(
                            "CODEX_DEVELOPMENT_SUSPENDED" if key == "CODEX" else None
                        ),
                        reopen_trigger_ar=(
                            "SEPARATE_EXPLICIT_PROGRAM_DECISION" if key == "CODEX" else None
                        ),
                    )
                )
                tools.append(
                    RegistryEntity(
                        entity_id=f"TOOL_{key}",
                        name_ar=label,
                        category="TOOL",
                        lifecycle="AVAILABLE",
                        status=status,
                        description_ar="حالة الأداة/المزود كما يرصدها runtime الحالي.",
                        owner="PALWAKF_WORKSPACE_MANAGER",
                    )
                )
        tools.append(
            RegistryEntity(
                entity_id="TOOL_HEALTH_AGGREGATE",
                name_ar="صحة الأدوات",
                category="TOOL",
                lifecycle="VERIFIED_RUNTIME_PROJECTION",
                status=(
                    "HEALTHY" if summary.tools.required_attention == 0 else "ATTENTION_REQUIRED"
                ),
                description_ar=(
                    f"{summary.tools.healthy}/{summary.tools.total} أدوات صحية؛ "
                    f"{summary.tools.required_attention} تحتاج انتباهًا."
                ),
                owner="PALWAKF_WORKSPACE_MANAGER",
            )
        )

        skills = [
            RegistryEntity(
                entity_id="SKILL_REGISTRY_RUNTIME_PROJECTION",
                name_ar="سجل المهارات المؤسسية",
                category="SKILL",
                lifecycle="DEFERRED_RUNTIME_PROJECTION",
                status="NOT_IMPORTED_TO_RUNTIME",
                description_ar=(
                    "المهارات السيادية تبقى في Workspace Drive/Mind؛ runtime الحالي "
                    "لا يدّعي قائمة Canonical غير مستوردة."
                ),
                owner="PALWAKF_MIND_ASSISTANT",
                deferred_reason_ar=(
                    "لا يوجد Live sovereign skill-registry adapter في runtime الحالي."
                ),
                reopen_trigger_ar="توفر adapter موثق أو import محكوم من المصدر السيادي.",
            )
        ]
        agents = [
            RegistryEntity(
                entity_id="AGENT_RUNTIME_LAYER",
                name_ar="طبقة الوكلاء",
                category="AGENT",
                lifecycle="AVAILABLE",
                status=workspace.agents_sdk.status if workspace is not None else "UNKNOWN",
                description_ar=(
                    "تمثل جاهزية طبقة الوكلاء في Workspace؛ لا تستنتج Agent census غير مستورد."
                ),
                owner="PALWAKF_WORKSPACE_MANAGER",
            )
        ]
        providers = [
            RegistryEntity(
                entity_id="PROVIDER_GITHUB",
                name_ar="GitHub",
                category="PROVIDER",
                lifecycle="CURRENT",
                status=workspace.github.status if workspace is not None else "UNKNOWN",
                description_ar="مزود حقيقة الكود والقراءة البعيدة للمستودع.",
                owner="PALWAKF_WORKSPACE_MANAGER",
            ),
            RegistryEntity(
                entity_id="PROVIDER_LOCAL_ORCHESTRATOR",
                name_ar="Local Orchestrator",
                category="PROVIDER",
                lifecycle="CURRENT",
                status=workspace.orchestrator.status if workspace is not None else "UNKNOWN",
                description_ar="مزود التشغيل المحلي المحكوم لـWorkspace Manager.",
                owner="PALWAKF_WORKSPACE_MANAGER",
            ),
            RegistryEntity(
                entity_id="PROVIDER_CODEX",
                name_ar="Codex",
                category="PROVIDER",
                lifecycle="HOLD",
                status="SUSPENDED_BY_POLICY",
                description_ar="مزود هندسي محتمل لكنه غير مفوض للتطوير في البرنامج الحالي.",
                owner="PALWAKF_WORKSPACE_MANAGER",
                deferred_reason_ar="CODEX_DEVELOPMENT_SUSPENDED",
                reopen_trigger_ar="SEPARATE_EXPLICIT_PROGRAM_DECISION",
            ),
        ]
        return capabilities, skills, tools, agents, providers

    @staticmethod
    def _kpis(
        summary: DashboardSummary,
        projects: list[ProjectIntelligence],
        truth_confidence: int,
        critical_path: CriticalPathView,
    ) -> list[PortfolioKpi]:
        total_evidence = sum(project.evidence_count for project in projects)
        capability_gaps = sum(project.tool_gap_count for project in projects)
        active_tasks = (
            summary.tasks.running + summary.tasks.queued + summary.tasks.pending_verification
        )
        return [
            PortfolioKpi(
                kpi_id="truth_confidence",
                label_ar="ثقة الحقيقة",
                value=f"{truth_confidence}%",
                status="VERIFIED" if truth_confidence >= 75 else "DEGRADED",
                confidence=1.0,
                explanation_ar="مؤشر شفاف مشتق من Source Health الموزون، وليس نسبة إنجاز.",
            ),
            PortfolioKpi(
                kpi_id="projects",
                label_ar="المشاريع المرصودة",
                value=str(summary.portfolio_total),
                status="CURRENT",
                confidence=0.9,
                explanation_ar="عدد المشاريع في Workspace project reality projection.",
            ),
            PortfolioKpi(
                kpi_id="attention",
                label_ar="تحتاج انتباهًا",
                value=str(summary.portfolio_attention_required),
                status="ATTENTION" if summary.portfolio_attention_required else "CLEAR",
                confidence=0.9,
                explanation_ar="مشاريع readiness فيها ليست READY.",
            ),
            PortfolioKpi(
                kpi_id="human_decisions",
                label_ar="قرارات بشرية",
                value=str(
                    summary.decision_inbox.pending_decisions
                    + summary.decision_inbox.pending_approvals
                ),
                status="ATTENTION" if summary.human_action_required else "CLEAR",
                confidence=0.95,
                explanation_ar="من durable decision inbox؛ لا تتحول التوصية إلى سلطة.",
            ),
            PortfolioKpi(
                kpi_id="active_tasks",
                label_ar="عمل نشط",
                value=str(active_tasks),
                status="ACTIVE" if active_tasks else "IDLE",
                confidence=0.9,
                explanation_ar="queued + running + pending verification.",
            ),
            PortfolioKpi(
                kpi_id="capability_gaps",
                label_ar="فجوات قدرات/أدوات",
                value=str(capability_gaps),
                status="ATTENTION" if capability_gaps else "CLEAR",
                confidence=0.75,
                explanation_ar="مجموع tool gaps المرصودة؛ لا يعني ضرورة شراء أو إضافة أداة.",
            ),
            PortfolioKpi(
                kpi_id="evidence",
                label_ar="مراجع أدلة",
                value=str(total_evidence),
                status="CURRENT",
                confidence=0.85,
                explanation_ar="عدد مراجع الأدلة المرتبطة بالمشاريع في القراءة الحالية.",
            ),
            PortfolioKpi(
                kpi_id="critical_path",
                label_ar="المسار الحرج",
                value="متاح" if critical_path.status == "AVAILABLE" else "غير متاح",
                status=critical_path.status,
                confidence=0.9 if critical_path.status == "AVAILABLE" else 1.0,
                explanation_ar=critical_path.reason_ar,
            ),
        ]
