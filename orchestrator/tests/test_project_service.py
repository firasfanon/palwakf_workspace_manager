from __future__ import annotations

from datetime import UTC, datetime

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_contracts import (
    ProjectAdapterKind,
    ProjectIntakeRequest,
    ProjectStatus,
)
from palwakf_orchestrator.project_reality import GitHubRepositoryRealityAdapter
from palwakf_orchestrator.project_service import ExternalProjectService
from tests.test_project_reality import HEAD, FakeGitHubReadClient

NOW = datetime(2026, 7, 31, tzinfo=UTC)


def service(
    store: MemoryStateStore | None = None,
    client: FakeGitHubReadClient | None = None,
) -> ExternalProjectService:
    return ExternalProjectService(
        {
            ProjectAdapterKind.github_repository: GitHubRepositoryRealityAdapter(
                client or FakeGitHubReadClient(),
                now=lambda: NOW,
            )
        },
        store,
        now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_registry_persists_probe_report_profile_and_candidates() -> None:
    store = MemoryStateStore()
    first = service(store)
    record = first.intake(
        ProjectIntakeRequest(
            repository_full_name="firasfanon/Pal_Eyes",
            display_name="Pal Eyes",
        )
    )

    report = await first.probe(record.project_id)
    restored = service(store)

    assert restored.get_project(record.project_id).status == ProjectStatus.probed
    assert restored.reality(record.project_id).baseline_fingerprint == (report.baseline_fingerprint)
    assert (
        restored.reality(record.project_id).capability_profile.blocked_tools[0].adapter_id
        == "supabase"
    )
    assert restored.candidate_work_items(record.project_id)
    envelope = restored.prepare_task_envelope(
        record.project_id,
        restored.candidate_work_items(record.project_id)[0].candidate_id,
    )
    assert envelope.expected_head == HEAD
    assert envelope.prepared_only is True
    assert envelope.dispatched is False


def test_intake_is_idempotent_and_rejects_invalid_adapter_paths() -> None:
    registry = service()
    request = ProjectIntakeRequest(
        repository_full_name="firasfanon/Pal_Eyes",
        display_name="Pal Eyes",
    )

    first = registry.intake(request)
    replay = registry.intake(request)

    assert first == replay
    with pytest.raises(GovernanceError, match="PROJECT_REGISTRY_ADAPTER_CONFLICT"):
        registry.intake(
            ProjectIntakeRequest(
                repository_full_name="firasfanon/Pal_Eyes",
                display_name="Pal Eyes",
                adapter=ProjectAdapterKind.local_git,
                local_repository_path="C:/allowlisted/Pal_Eyes",
            )
        )
    with pytest.raises(ValueError):
        ProjectIntakeRequest(
            repository_full_name="not-a-repository",
            display_name="Broken",
        )


@pytest.mark.asyncio
async def test_repository_rename_preserves_project_id_and_updates_canonical_name() -> None:
    store = MemoryStateStore()
    registry = service(
        store,
        FakeGitHubReadClient(
            full_name="firasfanon/palwakf_Eyes",
            repository_id=1313727249,
            redirected=True,
        ),
    )
    record = registry.intake(
        ProjectIntakeRequest(
            repository_full_name="firasfanon/Pal_Eyes",
            display_name="Pal Eyes",
        )
    )

    report = await registry.probe(record.project_id)
    updated = registry.get_project(record.project_id)

    assert updated.project_id == record.project_id
    assert updated.repository_full_name == "firasfanon/palwakf_Eyes"
    assert updated.github_repository_id == 1313727249
    assert report.repository_full_name == "firasfanon/palwakf_Eyes"
    assert len(registry.list_projects()) == 1


@pytest.mark.asyncio
async def test_repository_rename_conflict_fails_closed() -> None:
    store = MemoryStateStore()
    registry = service(
        store,
        FakeGitHubReadClient(
            full_name="firasfanon/palwakf_Eyes",
            repository_id=1313727249,
            redirected=True,
        ),
    )
    old = registry.intake(
        ProjectIntakeRequest(
            repository_full_name="firasfanon/Pal_Eyes",
            display_name="Pal Eyes old",
        )
    )
    registry.intake(
        ProjectIntakeRequest(
            repository_full_name="firasfanon/palwakf_Eyes",
            display_name="Pal Eyes canonical",
        )
    )

    with pytest.raises(GovernanceError, match="PROJECT_REPOSITORY_RENAME_CONFLICT"):
        await registry.probe(old.project_id)

    assert registry.get_project(old.project_id).status == ProjectStatus.blocked
