from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from palwakf_orchestrator.engineering_os_contracts import (
    CreateEngineeringTaskRequest,
    DependencyMode,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore, StateStore
from palwakf_orchestrator.project_contracts import (
    CandidateWorkItem,
    CreateProjectEngineeringTaskRequest,
    ExternalProjectRealityReport,
    ExternalProjectRecord,
    PrepareGovernedTaskEnvelopeResponse,
    ProjectAdapterKind,
    ProjectIntakeRequest,
    ProjectStatus,
)
from palwakf_orchestrator.project_reality import ProjectRealityAdapter


class ExternalProjectService:
    def __init__(
        self,
        adapters: dict[ProjectAdapterKind, ProjectRealityAdapter],
        state_store: StateStore | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._adapters = adapters
        self._state_store = state_store or MemoryStateStore()
        self._now = now or (lambda: datetime.now(UTC))

    def intake(self, command: ProjectIntakeRequest) -> ExternalProjectRecord:
        if command.adapter == ProjectAdapterKind.local_git and not command.local_repository_path:
            raise GovernanceError("LOCAL_PROJECT_PATH_REQUIRED")
        if (
            command.adapter == ProjectAdapterKind.github_repository
            and command.local_repository_path is not None
        ):
            raise GovernanceError("GITHUB_PROJECT_REJECTS_LOCAL_PATH")
        project_id = self._project_id(command.repository_full_name)
        projects, reports = self._load()
        existing = projects.get(project_id)
        now = self._now()
        if existing:
            if existing.repository_full_name.casefold() != command.repository_full_name.casefold():
                raise GovernanceError("PROJECT_REGISTRY_IDENTITY_CONFLICT")
            if (
                existing.adapter != command.adapter
                or existing.local_repository_path != command.local_repository_path
            ):
                raise GovernanceError("PROJECT_REGISTRY_ADAPTER_CONFLICT")
            return existing
        record = ExternalProjectRecord(
            project_id=project_id,
            display_name=command.display_name,
            repository_full_name=command.repository_full_name,
            adapter=command.adapter,
            local_repository_path=command.local_repository_path,
            observed_head=command.expected_head,
            created_at=now,
            updated_at=now,
        )
        projects[project_id] = record
        self._save(projects, reports)
        return record

    def list_projects(self) -> list[ExternalProjectRecord]:
        projects, _ = self._load()
        return sorted(projects.values(), key=lambda project: project.project_id)

    def get_project(self, project_id: str) -> ExternalProjectRecord:
        projects, _ = self._load()
        try:
            return projects[project_id]
        except KeyError as exc:
            raise GovernanceError("PROJECT_NOT_REGISTERED") from exc

    async def probe(self, project_id: str) -> ExternalProjectRealityReport:
        projects, reports = self._load()
        try:
            project = projects[project_id]
        except KeyError as exc:
            raise GovernanceError("PROJECT_NOT_REGISTERED") from exc
        adapter = self._adapters.get(project.adapter)
        if adapter is None:
            raise GovernanceError(f"PROJECT_ADAPTER_UNAVAILABLE:{project.adapter}")
        try:
            report = await adapter.probe(project)
        except GovernanceError as exc:
            project.status = ProjectStatus.blocked
            project.blockers = [str(exc)]
            project.updated_at = self._now()
            projects[project_id] = project
            self._save(projects, reports)
            raise
        project.default_branch = report.default_branch
        project.observed_branch = report.observed_branch
        project.observed_head = report.observed_head
        project.visibility = report.visibility
        project.stack = report.stack
        project.package_managers = report.package_managers
        project.build_commands = [
            command.command for command in report.commands if command.purpose == "build"
        ]
        project.test_commands = [
            command.command
            for command in report.commands
            if command.purpose in {"format", "analyze", "test"}
        ]
        project.ci_providers = sorted({item.provider for item in report.ci})
        project.deployment_providers = sorted({item.provider for item in report.deployments})
        project.source_of_truth_references = [
            item.reference for item in report.source_of_truth_references
        ]
        project.last_probe_at = report.observed_at
        project.baseline_fingerprint = report.baseline_fingerprint
        project.status = (
            ProjectStatus.drifted if report.drift_status == "HEAD_DRIFT" else ProjectStatus.probed
        )
        project.blockers = report.blockers
        project.updated_at = self._now()
        projects[project_id] = project
        reports[project_id] = report
        self._save(projects, reports)
        return report

    def reality(self, project_id: str) -> ExternalProjectRealityReport:
        _, reports = self._load()
        try:
            return reports[project_id]
        except KeyError as exc:
            raise GovernanceError("PROJECT_REALITY_NOT_PROBED") from exc

    def candidate_work_items(self, project_id: str) -> list[CandidateWorkItem]:
        return self.reality(project_id).candidate_work_items

    def prepare_task_envelope(
        self,
        project_id: str,
        candidate_id: str,
    ) -> PrepareGovernedTaskEnvelopeResponse:
        report = self.reality(project_id)
        candidate = next(
            (item for item in report.candidate_work_items if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise GovernanceError("PROJECT_CANDIDATE_NOT_FOUND")
        return PrepareGovernedTaskEnvelopeResponse(
            project_id=project_id,
            repository=report.repository_full_name,
            expected_head=report.observed_head,
            authority_mode="READ_ONLY_ZERO_MUTATION",
            candidate_work_item=candidate,
        )

    def prepare_engineering_task_request(
        self,
        project_id: str,
        candidate_id: str,
        command: CreateProjectEngineeringTaskRequest,
    ) -> CreateEngineeringTaskRequest:
        report = self.reality(project_id)
        candidate = next(
            (item for item in report.candidate_work_items if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise GovernanceError("PROJECT_CANDIDATE_NOT_FOUND")
        if candidate.blocked:
            raise GovernanceError("PROJECT_CANDIDATE_BLOCKED")
        if report.blockers:
            raise GovernanceError("PROJECT_REALITY_BLOCKED_FOR_TASK_CREATION")

        required_tests = [
            item.command
            for item in report.commands
            if item.purpose in {"format", "analyze", "test"}
        ][:64]
        if not required_tests:
            required_tests = ["targeted", "regression"]

        evidence = " | ".join(candidate.evidence[:8])
        description = (
            f"{candidate.rationale}\n\n"
            f"Acceptance: {candidate.acceptance_test}\n\n"
            f"Candidate: {candidate.candidate_id}\n"
            f"Observed HEAD: {report.observed_head}\n"
            f"Evidence: {evidence}"
        )[:4000]

        return CreateEngineeringTaskRequest(
            task_id=command.task_id,
            project_id=project_id,
            title=candidate.title,
            description=description,
            repository=report.repository_full_name,
            base_sha=report.observed_head,
            task_branch=f"task/{command.task_id}",
            owner_id=command.owner_id,
            actor_id=command.actor_id,
            actor_type=command.actor_type,
            provider_id=command.provider_id,
            scope_patterns=command.scope_patterns,
            depends_on=[],
            dependency_mode=DependencyMode.independent,
            risk_class=command.risk_class,
            mutation_class=command.mutation_class,
            required_capabilities=[
                "source.control",
                "runtime.verification",
                "evidence.capture",
            ],
            required_tests=required_tests,
        )

    def _load(
        self,
    ) -> tuple[
        dict[str, ExternalProjectRecord],
        dict[str, ExternalProjectRealityReport],
    ]:
        state = self._state_store.load()
        namespace = state.get("external_projects", {})
        raw_projects = namespace.get("projects", {}) if isinstance(namespace, dict) else {}
        raw_reports = namespace.get("reports", {}) if isinstance(namespace, dict) else {}
        projects = {
            key: ExternalProjectRecord.model_validate(value) for key, value in raw_projects.items()
        }
        reports = {
            key: ExternalProjectRealityReport.model_validate(value)
            for key, value in raw_reports.items()
        }
        return projects, reports

    def _save(
        self,
        projects: dict[str, ExternalProjectRecord],
        reports: dict[str, ExternalProjectRealityReport],
    ) -> None:
        state = self._state_store.load()
        state["external_projects"] = {
            "registry_version": "EXTERNAL_PROJECT_REGISTRY_V1",
            "projects": {key: value.model_dump(mode="json") for key, value in projects.items()},
            "reports": {key: value.model_dump(mode="json") for key, value in reports.items()},
        }
        self._state_store.save(state)

    @staticmethod
    def _project_id(repository: str) -> str:
        slug = repository.replace("/", "_").replace("-", "_").upper()
        digest = hashlib.sha256(repository.casefold().encode()).hexdigest()[:8].upper()
        return f"{slug}_{digest}"
