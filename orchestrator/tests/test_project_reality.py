from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.project_contracts import (
    DeploymentReality,
    ExternalProjectRecord,
    ProjectAdapterKind,
)
from palwakf_orchestrator.project_reality import (
    MAX_SCANNED_FILES,
    GitHubRepositoryRealityAdapter,
    LocalGitRealityAdapter,
)

HEAD = "c67ff5e28205aac57ff28e8b8120c3bac5de4488"
CHANGED_HEAD = "a" * 40
NOW = datetime(2026, 7, 31, tzinfo=UTC)

FILES = {
    ".env.example": "",
    ".gitignore": ".env\n.env.*\n!.env.example\n",
    "README.md": "flutter analyze\nflutter test\n",
    "analysis_options.yaml": "include: package:flutter_lints/flutter.yaml\n",
    "docs/11_LOCAL_RUN_AND_VALIDATION.md": (
        "flutter pub get\nflutter analyze\nflutter test\nflutter build web\n"
    ),
    "docs/project_memory/PAL_EYES_PROJECT_STATE_SNAPSHOT_CURRENT.json": (
        '{"next_priority":"APPLY_R8_0_1_AND_REPEAT_ANALYZE_TEST",'
        '"r7_0_2_hotfix":{"gis_review_tasks":4}}'
    ),
    "docs/project_memory/PAL_EYES_SESSION_HANDOFF_CURRENT.md": (
        "STATUS=BUILT_PENDING_LOCAL_UAT\nflutter_analyze=PENDING_REPEAT\n"
    ),
    "lib/features/workspace/presentation/gis_review_screen.dart": (
        "latitude: 0,\nlongitude: 0,\nsourceId: '',\n"
    ),
    "lib/main.dart": "void main() {}\n",
    "pubspec.lock": "packages: {}\n",
    "pubspec.yaml": (
        "name: pal_eyes\nversion: 8.0.1+27\nenvironment:\n"
        '  sdk: ">=3.10.0 <4.0.0"\n  flutter: ">=3.38.0"\n'
        "dependencies:\n  flutter:\n    sdk: flutter\n  supabase_flutter: ^2.16.0\n"
    ),
    "supabase/migrations/001.sql": "-- not read\n",
    "test/app_smoke_test.dart": "void main() {}\n",
}


class FakeGitHubReadClient:
    def __init__(
        self,
        *,
        head: str = HEAD,
        full_name: str = "firasfanon/Pal_Eyes",
        repository_id: int = 1313727249,
        redirected: bool = False,
        missing: bool = False,
        extra_files: int = 0,
    ) -> None:
        self.head = head
        self.full_name = full_name
        self.repository_id = repository_id
        self.redirected = redirected
        self.missing = missing
        self.calls: list[str] = []
        self.files = dict(FILES)
        for index in range(extra_files):
            self.files[f"generated/file_{index:04}.txt"] = "bounded"
        self.blobs = {path: f"blob-{index}" for index, path in enumerate(self.files)}

    async def get_json(self, path: str) -> Any:
        self.calls.append(path)
        if self.missing:
            raise GovernanceError("PROJECT_REPOSITORY_NOT_FOUND")
        if path == "/repos/firasfanon/Pal_Eyes":
            return {
                "id": self.repository_id,
                "full_name": self.full_name,
                "_palwakf_canonical_redirect": self.redirected,
                "default_branch": "main",
                "visibility": "public",
                "private": False,
            }
        if path.endswith("/commits/main"):
            return {"sha": self.head, "commit": {"tree": {"sha": "tree-sha"}}}
        if "/git/trees/" in path:
            return {
                "truncated": False,
                "tree": [
                    {"path": name, "type": "blob", "sha": sha} for name, sha in self.blobs.items()
                ],
            }
        if "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[-1]
            file_name = next(name for name, value in self.blobs.items() if value == sha)
            return {
                "encoding": "base64",
                "content": base64.b64encode(self.files[file_name].encode()).decode(),
            }
        if path.endswith("/actions/workflows?per_page=100"):
            return {"workflows": []}
        if "/actions/runs?" in path:
            return {"workflow_runs": []}
        raise AssertionError(f"Unexpected read path: {path}")


def project(
    *,
    observed_head: str | None = None,
    adapter: ProjectAdapterKind = ProjectAdapterKind.github_repository,
    local_path: str | None = None,
    github_repository_id: int | None = None,
) -> ExternalProjectRecord:
    return ExternalProjectRecord(
        project_id="FIRASFANON_PAL_EYES",
        display_name="Pal Eyes",
        repository_full_name="firasfanon/Pal_Eyes",
        github_repository_id=github_repository_id,
        adapter=adapter,
        local_repository_path=local_path,
        observed_head=observed_head,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_github_probe_is_bounded_read_only_and_detects_flutter() -> None:
    client = FakeGitHubReadClient(extra_files=MAX_SCANNED_FILES + 25)
    adapter = GitHubRepositoryRealityAdapter(
        client,
        deployment_observations={
            "firasfanon/Pal_Eyes": DeploymentReality(
                provider="vercel",
                status="NOT_DISCOVERED",
                evidence="read-only Vercel inventory",
            )
        },
        now=lambda: NOW,
    )

    report = await adapter.probe(project())

    assert report.default_branch == "main"
    assert report.observed_head == HEAD
    assert report.stack == ["Dart", "Flutter", "Supabase Flutter SDK"]
    assert report.toolchain_versions == {
        "application": "8.0.1+27",
        "dart": ">=3.10.0 <4.0.0",
        "flutter": ">=3.38.0",
    }
    assert report.tree.scanned_files == MAX_SCANNED_FILES
    assert report.tree.truncated is True
    assert report.tree.secret_risk_file_names == [".env.example"]
    assert report.tree.ignored_secret_policy_present is True
    assert report.indicators["supabase"] is True
    assert report.external_mutation_performed is False
    assert report.deployments[0].status == "NOT_DISCOVERED"
    assert report.ci_status == "NOT_CONFIGURED"
    assert report.deployment_status == "NOT_DISCOVERED"
    assert all(call.startswith("/") for call in client.calls)
    assert not any(
        token in call.casefold()
        for call in client.calls
        for token in ("create", "update", "delete", "dispatch")
    )


@pytest.mark.asyncio
async def test_identity_mismatch_and_missing_repository_are_typed() -> None:
    mismatch = GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(full_name="firasfanon/Other"),
        now=lambda: NOW,
    )
    with pytest.raises(GovernanceError, match="PROJECT_IDENTITY_MISMATCH"):
        await mismatch.probe(project())

    missing = GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(missing=True),
        now=lambda: NOW,
    )
    with pytest.raises(GovernanceError, match="PROJECT_REPOSITORY_NOT_FOUND"):
        await missing.probe(project())


@pytest.mark.asyncio
async def test_github_probe_accepts_safe_repository_rename_redirect() -> None:
    client = FakeGitHubReadClient(
        full_name="firasfanon/palwakf_Eyes",
        repository_id=1313727249,
        redirected=True,
    )
    report = await GitHubRepositoryRealityAdapter(
        client,
        now=lambda: NOW,
    ).probe(project())

    assert report.project_id == "FIRASFANON_PAL_EYES"
    assert report.repository_full_name == "firasfanon/palwakf_Eyes"
    assert report.github_repository_id == 1313727249
    assert any(call.startswith("/repos/firasfanon/palwakf_Eyes/commits/") for call in client.calls)


@pytest.mark.asyncio
async def test_github_probe_rejects_stable_repository_id_mismatch() -> None:
    adapter = GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(repository_id=222),
        now=lambda: NOW,
    )
    with pytest.raises(GovernanceError, match="PROJECT_STABLE_IDENTITY_MISMATCH"):
        await adapter.probe(project(github_repository_id=111))


@pytest.mark.asyncio
async def test_fingerprint_is_deterministic_and_head_sensitive() -> None:
    first = await GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(),
        now=lambda: NOW,
    ).probe(project())
    replay = await GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(),
        now=lambda: datetime(2026, 8, 1, tzinfo=UTC),
    ).probe(project(observed_head=HEAD))
    changed = await GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(head=CHANGED_HEAD),
        now=lambda: NOW,
    ).probe(project(observed_head=HEAD))

    assert first.baseline_fingerprint == replay.baseline_fingerprint
    assert replay.drift_status == "UNCHANGED"
    assert changed.drift_status == "HEAD_DRIFT"
    assert changed.baseline_fingerprint != first.baseline_fingerprint


@pytest.mark.asyncio
async def test_product_candidate_ranking_uses_repository_evidence() -> None:
    report = await GitHubRepositoryRealityAdapter(
        FakeGitHubReadClient(),
        now=lambda: NOW,
    ).probe(project())

    assert report.candidate_work_items[0].candidate_id == ("PAL_EYES_GIS_CANDIDATE_VALIDATION")
    assert "gis_review_screen.dart" in report.candidate_work_items[0].evidence[0]
    assert report.candidate_work_items[1].candidate_id == ("PAL_EYES_R8_0_1_RUNTIME_CLOSURE")


class FakeGitRunner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[tuple[str, ...]] = []

    async def run(self, cwd: Path, arguments: tuple[str, ...]) -> str:
        self.calls.append(arguments)
        values = {
            ("rev-parse", "--show-toplevel"): str(self.root),
            ("rev-parse", "HEAD"): HEAD,
            ("branch", "--show-current"): "main",
            ("status", "--porcelain=v1"): "",
            ("remote", "get-url", "origin"): "https://github.com/firasfanon/Pal_Eyes.git",
        }
        return values[arguments]


@pytest.mark.asyncio
async def test_local_git_adapter_requires_exact_allowlisted_path(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    denied = tmp_path / "denied"
    allowed.mkdir()
    denied.mkdir()
    (allowed / "pubspec.yaml").write_text("name: pal_eyes\n", encoding="utf-8")
    runner = FakeGitRunner(allowed)
    adapter = LocalGitRealityAdapter([allowed], runner, now=lambda: NOW)

    with pytest.raises(GovernanceError, match="NOT_ALLOWLISTED"):
        await adapter.probe(project(adapter=ProjectAdapterKind.local_git, local_path=str(denied)))

    report = await adapter.probe(
        project(adapter=ProjectAdapterKind.local_git, local_path=str(allowed))
    )

    assert report.local_clean is True
    assert report.external_mutation_performed is False
    assert set(runner.calls) == {
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "HEAD"),
        ("branch", "--show-current"),
        ("status", "--porcelain=v1"),
        ("remote", "get-url", "origin"),
    }


@pytest.mark.asyncio
async def test_local_scan_is_bounded_and_ignores_runtime_directories(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "bounded"
    allowed.mkdir()
    for index in range(MAX_SCANNED_FILES + 20):
        (allowed / f"file_{index:04}.txt").write_text("x", encoding="utf-8")
    runtime = allowed / "build"
    runtime.mkdir()
    (runtime / "generated.txt").write_text("ignored", encoding="utf-8")
    runner = FakeGitRunner(allowed)
    adapter = LocalGitRealityAdapter([allowed], runner, now=lambda: NOW)

    report = await adapter.probe(
        project(adapter=ProjectAdapterKind.local_git, local_path=str(allowed))
    )

    assert report.tree.scanned_files == MAX_SCANNED_FILES
    assert report.tree.total_files == MAX_SCANNED_FILES + 1
    assert report.tree.truncated is True
