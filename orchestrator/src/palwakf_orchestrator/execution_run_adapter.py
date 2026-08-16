from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from palwakf_orchestrator.engineering_os_contracts import EngineeringTaskRecord
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import CreateOperatorTaskRequest, OperatorTaskRecord
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import StateStore

EXECUTION_RUN_LINKS_KEY = "execution_run_links_v1"


class ExecutionRunLinkRecord(BaseModel):
    execution_run_id: str
    legacy_operator_task_id: str
    parent_engineering_task_id: str
    project_id: str
    repository: str
    expected_head_at_creation: str
    created_at: datetime


class ExecutionRunRecord(BaseModel):
    execution_run_id: str
    legacy_operator_task_id: str
    parent_engineering_task_id: str
    operator_task: OperatorTaskRecord


class ExecutionRunAdapter:
    """Additive relation layer over the existing EngineeringTask and OperatorTask engines."""

    def __init__(
        self,
        engineering_tasks: EngineeringOsService,
        operator_tasks: OperatorService,
        state_store: StateStore,
    ) -> None:
        self._engineering_tasks = engineering_tasks
        self._operator_tasks = operator_tasks
        self._state_store = state_store

    def create_run(
        self,
        parent_engineering_task_id: str,
        request: CreateOperatorTaskRequest,
    ) -> ExecutionRunRecord:
        parent = self._engineering_tasks.get_task(parent_engineering_task_id)
        self._assert_authority(parent, request)

        links = self._load_links()
        existing_link = links.get(request.task_id)
        existing_operator = self._find_existing_operator(request)

        if existing_link is not None:
            if existing_link.parent_engineering_task_id != parent.task_id:
                raise GovernanceError("EXECUTION_RUN_PARENT_IDEMPOTENCY_CONFLICT")
            if existing_operator is None:
                raise GovernanceError("EXECUTION_RUN_LINK_ORPHANED")
            operator_task = self._operator_tasks.create_task(request)
            return self._compose(existing_link, operator_task)

        if existing_operator is not None:
            raise GovernanceError("EXISTING_OPERATOR_TASK_REQUIRES_SEPARATE_MIGRATION")

        operator_task = self._operator_tasks.create_task(request)
        link = ExecutionRunLinkRecord(
            execution_run_id=operator_task.task_id,
            legacy_operator_task_id=operator_task.task_id,
            parent_engineering_task_id=parent.task_id,
            project_id=operator_task.project_id,
            repository=operator_task.repository,
            expected_head_at_creation=operator_task.expected_head,
            created_at=datetime.now(UTC),
        )
        self._save_link(link)
        return self._compose(link, operator_task)

    def list_runs(self, parent_engineering_task_id: str) -> list[ExecutionRunRecord]:
        self._engineering_tasks.get_task(parent_engineering_task_id)
        records: list[ExecutionRunRecord] = []
        for link in self._load_links().values():
            if link.parent_engineering_task_id != parent_engineering_task_id:
                continue
            operator_task = self._operator_tasks.get_task(link.legacy_operator_task_id)
            records.append(self._compose(link, operator_task))
        return sorted(records, key=lambda item: item.operator_task.created_at, reverse=True)

    def get_run(self, execution_run_id: str) -> ExecutionRunRecord:
        link = self._load_links().get(execution_run_id)
        if link is None:
            raise GovernanceError("EXECUTION_RUN_NOT_FOUND")
        self._engineering_tasks.get_task(link.parent_engineering_task_id)
        operator_task = self._operator_tasks.get_task(link.legacy_operator_task_id)
        return self._compose(link, operator_task)

    def _assert_authority(
        self,
        parent: EngineeringTaskRecord,
        request: CreateOperatorTaskRequest,
    ) -> None:
        if request.project_id != parent.project_id:
            raise GovernanceError("EXECUTION_RUN_PROJECT_OUTSIDE_PARENT_AUTHORITY")
        if request.repository != parent.repository:
            raise GovernanceError("EXECUTION_RUN_REPOSITORY_OUTSIDE_PARENT_AUTHORITY")
        authority_head = parent.latest_remote_task_sha or parent.base_sha
        if request.expected_head.lower() != authority_head.lower():
            raise GovernanceError("EXECUTION_RUN_HEAD_OUTSIDE_PARENT_AUTHORITY")
        if parent.mutation_class == "read-only" and request.sandbox != "read-only":
            raise GovernanceError("EXECUTION_RUN_MUTATION_WIDENS_PARENT_AUTHORITY")

    def _find_existing_operator(
        self,
        request: CreateOperatorTaskRequest,
    ) -> OperatorTaskRecord | None:
        for task in self._operator_tasks.list_tasks():
            if task.task_id == request.task_id or task.idempotency_key == request.idempotency_key:
                return task
        return None

    def _load_links(self) -> dict[str, ExecutionRunLinkRecord]:
        raw = self._state_store.load().get(EXECUTION_RUN_LINKS_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("EXECUTION_RUN_LINK_STATE_INVALID")
        return {
            str(execution_run_id): ExecutionRunLinkRecord.model_validate(value)
            for execution_run_id, value in raw.items()
        }

    def _save_link(self, link: ExecutionRunLinkRecord) -> None:
        state = self._state_store.load()
        raw = state.get(EXECUTION_RUN_LINKS_KEY, {})
        if not isinstance(raw, dict):
            raise GovernanceError("EXECUTION_RUN_LINK_STATE_INVALID")
        links = dict(raw)
        links[link.execution_run_id] = link.model_dump(mode="json")
        state[EXECUTION_RUN_LINKS_KEY] = links
        self._state_store.save(state)

    @staticmethod
    def _compose(
        link: ExecutionRunLinkRecord,
        operator_task: OperatorTaskRecord,
    ) -> ExecutionRunRecord:
        if operator_task.task_id != link.legacy_operator_task_id:
            raise GovernanceError("EXECUTION_RUN_OPERATOR_IDENTITY_DRIFT")
        if operator_task.project_id != link.project_id:
            raise GovernanceError("EXECUTION_RUN_PROJECT_DRIFT")
        if operator_task.repository != link.repository:
            raise GovernanceError("EXECUTION_RUN_REPOSITORY_DRIFT")
        if operator_task.expected_head.lower() != link.expected_head_at_creation.lower():
            raise GovernanceError("EXECUTION_RUN_EXPECTED_HEAD_DRIFT")
        return ExecutionRunRecord(
            execution_run_id=link.execution_run_id,
            legacy_operator_task_id=link.legacy_operator_task_id,
            parent_engineering_task_id=link.parent_engineering_task_id,
            operator_task=operator_task,
        )
