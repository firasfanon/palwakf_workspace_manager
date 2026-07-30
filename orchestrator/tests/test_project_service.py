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


def service(store: MemoryStateStore | None = None) -> ExternalProjectService:
    return ExternalProjectService(
        {
            ProjectAdapterKind.github_repository: GitHubRepositoryRealityAdapter(
                FakeGitHubReadClient(),
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
    assert restored.reality(record.project_id).baseline_fingerprint == (
        report.baseline_fingerprint
    )
    assert restored.reality(record.project_id).capability_profile.blocked_tools[
        0
    ].adapter_id == "supabase"
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
