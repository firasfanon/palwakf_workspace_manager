from __future__ import annotations

from palwakf_orchestrator.engineering_os_contracts import (
    CreateEngineeringTaskRequest,
    DependencyMode,
    EngineeringOsSummary,
    EngineeringTaskRecord,
    EngineeringTaskStatus,
    ExtensionKind,
    ExtensionLifecycle,
    ExtensionRecord,
    RegisterExtensionRequest,
    RemoteCheckpointRequest,
    utc_now,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

TASKS_KEY = "engineering_os_tasks_v1"
EXTENSIONS_KEY = "engineering_os_extensions_v1"


class EngineeringOsService:
    def __init__(self, state_store: StateStore) -> None:
        self.state_store = state_store

    def list_tasks(self) -> list[EngineeringTaskRecord]:
        state = self.state_store.load()
        raw = state.get(TASKS_KEY, {})
        records = [EngineeringTaskRecord.model_validate(value) for value in raw.values()]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def get_task(self, task_id: str) -> EngineeringTaskRecord:
        for task in self.list_tasks():
            if task.task_id == task_id:
                return task
        raise GovernanceError("ENGINEERING_TASK_NOT_FOUND")

    def create_task(self, request: CreateEngineeringTaskRequest) -> EngineeringTaskRecord:
        if request.dependency_mode == DependencyMode.independent and request.depends_on:
            raise GovernanceError("INDEPENDENT_TASK_MUST_NOT_DECLARE_UPSTREAM")
        if request.dependency_mode != DependencyMode.independent and not request.depends_on:
            raise GovernanceError("DEPENDENT_TASK_REQUIRES_UPSTREAM")
        if request.provider_id and request.actor_type.value == "HUMAN":
            raise GovernanceError("HUMAN_ACTOR_MUST_NOT_REQUIRE_PROVIDER")

        state = self.state_store.load()
        tasks = dict(state.get(TASKS_KEY, {}))
        if request.task_id in tasks:
            raise GovernanceError("ENGINEERING_TASK_ALREADY_EXISTS")

        now = utc_now()
        payload = request.model_dump()
        payload["base_sha"] = request.base_sha.lower()
        record = EngineeringTaskRecord(
            **payload,
            integrated_head_at_creation=request.base_sha.lower(),
            status=EngineeringTaskStatus.ready,
            created_at=now,
            updated_at=now,
        )
        tasks[record.task_id] = record.model_dump(mode="json")
        state[TASKS_KEY] = tasks
        self.state_store.save(state)
        return record

    def checkpoint_task(
        self,
        task_id: str,
        request: RemoteCheckpointRequest,
    ) -> EngineeringTaskRecord:
        state = self.state_store.load()
        tasks = dict(state.get(TASKS_KEY, {}))
        raw = tasks.get(task_id)
        if raw is None:
            raise GovernanceError("ENGINEERING_TASK_NOT_FOUND")

        record = EngineeringTaskRecord.model_validate(raw)
        if record.status in {
            EngineeringTaskStatus.integrated,
            EngineeringTaskStatus.cancelled,
            EngineeringTaskStatus.superseded,
        }:
            raise GovernanceError("TASK_STATE_REJECTS_WIP_CHECKPOINT")

        updated = record.model_copy(
            update={
                "latest_remote_task_sha": request.remote_sha.lower(),
                "wip_checkpoint_status": "REMOTE_CHECKPOINTED",
                "status": EngineeringTaskStatus.wip_remote_checkpointed,
                "evidence": [*record.evidence, *request.evidence],
                "updated_at": utc_now(),
            }
        )
        tasks[task_id] = updated.model_dump(mode="json")
        state[TASKS_KEY] = tasks
        self.state_store.save(state)
        return updated

    def list_extensions(
        self,
        kind: ExtensionKind | None = None,
    ) -> list[ExtensionRecord]:
        state = self.state_store.load()
        raw = state.get(EXTENSIONS_KEY, {})
        records = [ExtensionRecord.model_validate(value) for value in raw.values()]
        if kind is not None:
            records = [item for item in records if item.kind == kind]
        return sorted(records, key=lambda item: (item.kind.value, item.name.lower()))

    def register_extension(
        self,
        request: RegisterExtensionRequest,
    ) -> ExtensionRecord:
        if request.open_source and not request.license:
            raise GovernanceError("OPEN_SOURCE_EXTENSION_REQUIRES_LICENSE")
        if request.source_kind.value == "GITHUB" and "/" not in request.source_reference:
            raise GovernanceError("GITHUB_EXTENSION_REQUIRES_REPOSITORY_REFERENCE")

        state = self.state_store.load()
        extensions = dict(state.get(EXTENSIONS_KEY, {}))
        if request.extension_id in extensions:
            raise GovernanceError("EXTENSION_ALREADY_REGISTERED")

        now = utc_now()
        record = ExtensionRecord(
            **request.model_dump(),
            lifecycle=ExtensionLifecycle.quarantined,
            created_at=now,
            updated_at=now,
        )
        extensions[record.extension_id] = record.model_dump(mode="json")
        state[EXTENSIONS_KEY] = extensions
        self.state_store.save(state)
        return record

    def summary(self) -> EngineeringOsSummary:
        tasks = self.list_tasks()
        extensions = self.list_extensions()

        task_counts = {status.value: 0 for status in EngineeringTaskStatus}
        for task in tasks:
            task_counts[task.status.value] += 1

        extension_counts = {kind.value: 0 for kind in ExtensionKind}
        for extension in extensions:
            extension_counts[extension.kind.value] += 1

        return EngineeringOsSummary(
            generated_at=utc_now(),
            parallel_tracks=[
                "PRODUCT_UI",
                "ENGINEERING_GOVERNANCE",
                "EXTENSIBILITY",
            ],
            tasks_by_status=task_counts,
            extensions_by_kind=extension_counts,
            quarantined_extensions=sum(
                1
                for extension in extensions
                if extension.lifecycle == ExtensionLifecycle.quarantined
            ),
            remote_checkpointed_tasks=sum(
                1 for task in tasks if task.wip_checkpoint_status == "REMOTE_CHECKPOINTED"
            ),
        )
