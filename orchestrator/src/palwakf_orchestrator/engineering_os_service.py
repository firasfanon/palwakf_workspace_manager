from __future__ import annotations

import os
import re
from collections.abc import Callable
from urllib.parse import quote

import httpx

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
from palwakf_orchestrator.provider_contracts import quarantined_role_authorities

TASKS_KEY = "engineering_os_tasks_v1"
EXTENSIONS_KEY = "engineering_os_extensions_v1"
_REMOTE_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
RemoteHeadResolver = Callable[[str, str], str]


def _github_remote_head(repository: str, branch: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise GovernanceError("ENGINEERING_TASK_REPOSITORY_INVALID")
    if not branch.startswith("task/"):
        raise GovernanceError("REMOTE_WIP_BRANCH_MUST_BE_TASK_BRANCH")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PalWakf-Engineering-Remote-WIP-Verifier",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    ref = quote(f"heads/{branch}", safe="/")
    try:
        with httpx.Client(headers=headers, timeout=15.0, follow_redirects=False) as client:
            response = client.get(
                f"https://api.github.com/repos/{repository}/git/ref/{ref}"
            )
    except httpx.HTTPError as exc:
        raise GovernanceError("REMOTE_WIP_HEAD_READ_FAILED") from exc

    if response.status_code == 404:
        raise GovernanceError("REMOTE_TASK_BRANCH_NOT_FOUND")
    if response.status_code >= 400:
        raise GovernanceError(f"REMOTE_WIP_HEAD_READ_FAILED:{response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise GovernanceError("REMOTE_WIP_HEAD_RESPONSE_INVALID") from exc
    if not isinstance(payload, dict):
        raise GovernanceError("REMOTE_WIP_HEAD_RESPONSE_INVALID")
    target = payload.get("object")
    if not isinstance(target, dict):
        raise GovernanceError("REMOTE_WIP_HEAD_RESPONSE_INVALID")
    observed = str(target.get("sha", ""))
    if not _REMOTE_SHA_RE.fullmatch(observed):
        raise GovernanceError("REMOTE_WIP_HEAD_INVALID")
    return observed.lower()


class EngineeringOsService:
    def __init__(
        self,
        state_store: StateStore,
        *,
        remote_head_resolver: RemoteHeadResolver | None = None,
    ) -> None:
        self.state_store = state_store
        self._remote_head_resolver = remote_head_resolver or _github_remote_head

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

        evidence = [*record.evidence, *request.evidence]
        if request.remote_sha is None:
            remote_sha = self._remote_head_resolver(
                record.repository,
                record.task_branch,
            ).lower()
            if not _REMOTE_SHA_RE.fullmatch(remote_sha):
                raise GovernanceError("REMOTE_WIP_HEAD_INVALID")
            evidence.append(
                "github-remote-head-verified:"
                f"{record.repository}:{record.task_branch}@{remote_sha}"
            )
        else:
            remote_sha = request.remote_sha.lower()

        updated = record.model_copy(
            update={
                "latest_remote_task_sha": remote_sha,
                "wip_checkpoint_status": "REMOTE_CHECKPOINTED",
                "status": EngineeringTaskStatus.wip_remote_checkpointed,
                "evidence": evidence,
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
            role_authorities=quarantined_role_authorities(request.declared_roles),
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
