from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import httpx

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.project_contracts import (
    CandidateWorkItem,
    CIWorkflowReality,
    DeploymentReality,
    EvidenceReference,
    ExternalProjectRealityReport,
    ExternalProjectRecord,
    FileTreeSummary,
    ProjectAdapterKind,
    ProjectCapabilityProfile,
    ProjectCommand,
    ProjectToolDecision,
    ToolDisposition,
)

MAX_SCANNED_FILES = 500
MAX_METADATA_BYTES = 256_000
IGNORED_LOCAL_DIRECTORIES = {
    ".dart_tool",
    ".git",
    ".palwakf",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "node_modules",
}
SAFE_METADATA_FILES = {
    ".gitignore",
    "README.md",
    "analysis_options.yaml",
    "package.json",
    "pyproject.toml",
    "pubspec.yaml",
    "pubspec.lock",
    "vercel.json",
    "docs/11_LOCAL_RUN_AND_VALIDATION.md",
    "docs/project_memory/PAL_EYES_PROJECT_STATE_SNAPSHOT_CURRENT.json",
    "docs/project_memory/PAL_EYES_SESSION_HANDOFF_CURRENT.md",
}
SECRET_RISK_PATTERN = re.compile(
    r"(^|/)(\.env($|\.)|.*\.(pem|key|p12|jks)$|credentials[^/]*$|secrets?[^/]*$)",
    re.IGNORECASE,
)


class ProjectRealityAdapter(Protocol):
    kind: ProjectAdapterKind

    async def probe(
        self,
        project: ExternalProjectRecord,
    ) -> ExternalProjectRealityReport: ...


class GitHubReadClient(Protocol):
    async def get_json(self, path: str) -> Any: ...


class HttpxGitHubReadClient:
    def __init__(self, token: str | None = None) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "PalWakf-ReadOnly-Reality-Adapter",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=20,
            follow_redirects=False,
        )

    async def get_json(self, path: str) -> Any:
        response = await self._client.get(path)
        if response.status_code == 404:
            raise GovernanceError("PROJECT_REPOSITORY_NOT_FOUND")
        if response.status_code >= 400:
            raise GovernanceError(f"GITHUB_READ_FAILED:{response.status_code}")
        return response.json()


class GitHubRepositoryRealityAdapter:
    kind = ProjectAdapterKind.github_repository

    def __init__(
        self,
        client: GitHubReadClient,
        *,
        deployment_observations: Mapping[str, DeploymentReality] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._deployment_observations = {
            key.casefold(): value for key, value in (deployment_observations or {}).items()
        }
        self._now = now or (lambda: datetime.now(UTC))

    async def probe(self, project: ExternalProjectRecord) -> ExternalProjectRealityReport:
        repository = project.repository_full_name
        metadata = _object(await self._client.get_json(f"/repos/{repository}"))
        observed_identity = str(metadata.get("full_name", ""))
        if observed_identity.casefold() != repository.casefold():
            raise GovernanceError(
                f"PROJECT_IDENTITY_MISMATCH:{repository}:{observed_identity or 'missing'}"
            )

        default_branch = str(metadata.get("default_branch", ""))
        if not default_branch:
            raise GovernanceError("PROJECT_DEFAULT_BRANCH_MISSING")
        commit = _object(
            await self._client.get_json(f"/repos/{repository}/commits/{default_branch}")
        )
        observed_head = str(commit.get("sha", ""))
        if not re.fullmatch(r"[0-9a-fA-F]{40}", observed_head):
            raise GovernanceError("PROJECT_HEAD_INVALID")
        tree_sha = str(_object(_object(commit.get("commit")).get("tree")).get("sha", ""))
        tree_payload = _object(
            await self._client.get_json(
                f"/repos/{repository}/git/trees/{tree_sha}?recursive=1"
            )
        )
        raw_tree = [
            _object(item)
            for item in _sequence(tree_payload.get("tree"))
            if _object(item).get("type") == "blob"
        ]
        raw_tree.sort(key=lambda item: str(item.get("path", "")))
        priority_tree = [
            item
            for item in raw_tree
            if str(item.get("path", "")) in SAFE_METADATA_FILES
        ]
        ordinary_tree = [item for item in raw_tree if item not in priority_tree]
        safe_tree = (priority_tree + ordinary_tree)[:MAX_SCANNED_FILES]
        safe_tree.sort(key=lambda item: str(item.get("path", "")))
        paths = [str(item.get("path", "")) for item in safe_tree]
        blobs = {str(item.get("path", "")): str(item.get("sha", "")) for item in safe_tree}

        contents: dict[str, str] = {}
        for path in sorted(SAFE_METADATA_FILES.intersection(paths)):
            contents[path] = await self._read_blob(repository, blobs[path])

        workflows_payload = _object(
            await self._client.get_json(f"/repos/{repository}/actions/workflows?per_page=100")
        )
        runs_payload = _object(
            await self._client.get_json(
                f"/repos/{repository}/actions/runs?branch={default_branch}&per_page=20"
            )
        )
        ci = _ci_reality(workflows_payload, runs_payload)
        stack, package_managers, versions, indicators = _detect_stack(paths, contents)
        commands = _detect_commands(paths, contents)
        tree = _tree_summary(raw_tree, safe_tree, paths, contents)
        references = _source_references(repository, observed_head, paths)
        candidates = _candidate_work_items(contents, ci, paths)
        deployments = self._deployment_reality(repository, paths)
        profile = _capability_profile(
            project.project_id,
            observed_head,
            stack,
            paths,
            deployments,
        )
        previous_head = project.observed_head
        drift_status = (
            "BASELINE_CREATED"
            if previous_head is None
            else "UNCHANGED"
            if previous_head == observed_head
            else "HEAD_DRIFT"
        )
        report_data: dict[str, Any] = {
            "project_id": project.project_id,
            "repository_full_name": repository,
            "adapter": self.kind,
            "visibility": str(
                metadata.get("visibility")
                or ("private" if metadata.get("private") else "public")
            ),
            "default_branch": default_branch,
            "observed_branch": default_branch,
            "observed_head": observed_head,
            "previous_observed_head": previous_head,
            "drift_status": drift_status,
            "stack": stack,
            "package_managers": package_managers,
            "toolchain_versions": versions,
            "commands": commands,
            "ci": ci,
            "ci_status": _overall_ci_status(ci),
            "deployments": deployments,
            "deployment_status": _overall_deployment_status(deployments),
            "tree": tree,
            "indicators": indicators,
            "source_of_truth_references": references,
            "capability_profile": profile,
            "candidate_work_items": candidates,
            "blockers": [],
            "observed_at": self._now(),
            "baseline_fingerprint": "0" * 64,
        }
        report_data["baseline_fingerprint"] = reality_fingerprint(report_data)
        return ExternalProjectRealityReport.model_validate(report_data)

    async def _read_blob(self, repository: str, sha: str) -> str:
        payload = _object(
            await self._client.get_json(f"/repos/{repository}/git/blobs/{sha}")
        )
        if str(payload.get("encoding")) != "base64":
            return ""
        raw = base64.b64decode(str(payload.get("content", "")), validate=False)
        if len(raw) > MAX_METADATA_BYTES:
            return ""
        return raw.decode("utf-8", errors="replace")

    def _deployment_reality(
        self,
        repository: str,
        paths: list[str],
    ) -> list[DeploymentReality]:
        observed = self._deployment_observations.get(repository.casefold())
        if observed:
            return [observed]
        if "vercel.json" in paths:
            return [
                DeploymentReality(
                    provider="vercel",
                    status="CONFIGURATION_PRESENT_NOT_QUERIED",
                    evidence="repository:vercel.json",
                )
            ]
        return [
            DeploymentReality(
                provider="vercel",
                status="NOT_DISCOVERED",
                evidence="Vercel read-only project inventory and repository tree",
            )
        ]


class GitCommandRunner(Protocol):
    async def run(self, cwd: Path, arguments: Sequence[str]) -> str: ...


class ReadOnlyGitCommandRunner:
    _ALLOWED = {
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "HEAD"),
        ("branch", "--show-current"),
        ("status", "--porcelain=v1"),
        ("remote", "get-url", "origin"),
    }

    async def run(self, cwd: Path, arguments: Sequence[str]) -> str:
        command = tuple(arguments)
        if command not in self._ALLOWED:
            raise GovernanceError("LOCAL_GIT_WRITE_OR_UNAPPROVED_COMMAND_REJECTED")

        def execute() -> str:
            result = subprocess.run(
                ["git", *command],
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stdout.strip()

        return await asyncio.to_thread(execute)


class LocalGitRealityAdapter:
    kind = ProjectAdapterKind.local_git

    def __init__(
        self,
        allowlisted_paths: Sequence[Path],
        runner: GitCommandRunner | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._allowlist = {path.resolve() for path in allowlisted_paths}
        self._runner = runner or ReadOnlyGitCommandRunner()
        self._now = now or (lambda: datetime.now(UTC))

    async def probe(self, project: ExternalProjectRecord) -> ExternalProjectRealityReport:
        if not project.local_repository_path:
            raise GovernanceError("LOCAL_PROJECT_PATH_REQUIRED")
        root = await asyncio.to_thread(
            lambda: Path(project.local_repository_path or "").resolve()
        )
        if root not in self._allowlist:
            raise GovernanceError("LOCAL_PROJECT_PATH_NOT_ALLOWLISTED")
        if not await asyncio.to_thread(root.is_dir):
            raise GovernanceError("LOCAL_PROJECT_PATH_MISSING")
        raw_top_level = await self._runner.run(root, ("rev-parse", "--show-toplevel"))
        top_level = await asyncio.to_thread(lambda: Path(raw_top_level).resolve())
        if top_level != root:
            raise GovernanceError("LOCAL_PROJECT_ROOT_MISMATCH")
        observed_head = await self._runner.run(root, ("rev-parse", "HEAD"))
        branch = await self._runner.run(root, ("branch", "--show-current"))
        dirty = bool(await self._runner.run(root, ("status", "--porcelain=v1")))
        origin = await self._runner.run(root, ("remote", "get-url", "origin"))
        if _repository_from_remote(origin).casefold() != (
            project.repository_full_name.casefold()
        ):
            raise GovernanceError("PROJECT_IDENTITY_MISMATCH:LOCAL_ORIGIN")

        paths = await asyncio.to_thread(_local_file_paths, root)
        safe_paths = paths[:MAX_SCANNED_FILES]
        contents = await asyncio.to_thread(_local_metadata_contents, root, safe_paths)
        stack, managers, versions, indicators = _detect_stack(safe_paths, contents)
        commands = _detect_commands(safe_paths, contents)
        profile = _capability_profile(
            project.project_id,
            observed_head,
            stack,
            safe_paths,
            [],
        )
        previous_head = project.observed_head
        data: dict[str, Any] = {
            "project_id": project.project_id,
            "repository_full_name": project.repository_full_name,
            "adapter": self.kind,
            "visibility": "LOCAL_NOT_INFERRED",
            "default_branch": branch,
            "observed_branch": branch,
            "observed_head": observed_head,
            "previous_observed_head": previous_head,
            "drift_status": (
                "BASELINE_CREATED"
                if previous_head is None
                else "UNCHANGED"
                if previous_head == observed_head
                else "HEAD_DRIFT"
            ),
            "local_clean": not dirty,
            "stack": stack,
            "package_managers": managers,
            "toolchain_versions": versions,
            "commands": commands,
            "ci": [],
            "ci_status": "NOT_CONFIGURED",
            "deployments": [],
            "deployment_status": "NOT_CONFIGURED",
            "tree": _tree_summary_from_paths(paths, safe_paths, contents),
            "indicators": indicators,
            "source_of_truth_references": [
                EvidenceReference(
                    kind="local_git",
                    reference=f"{project.repository_full_name}@{observed_head}",
                    observation="allowlisted local repository; private path omitted",
                )
            ],
            "capability_profile": profile,
            "candidate_work_items": _candidate_work_items(contents, [], safe_paths),
            "blockers": ["LOCAL_WORKTREE_DIRTY"] if dirty else [],
            "observed_at": self._now(),
            "baseline_fingerprint": "0" * 64,
        }
        data["baseline_fingerprint"] = reality_fingerprint(data)
        return ExternalProjectRealityReport.model_validate(data)


def reality_fingerprint(report: Mapping[str, Any]) -> str:
    canonical_fields = {
        key: _jsonable(report[key])
        for key in (
            "repository_full_name",
            "default_branch",
            "observed_branch",
            "observed_head",
            "visibility",
            "stack",
            "package_managers",
            "toolchain_versions",
            "commands",
            "ci",
            "ci_status",
            "deployments",
            "deployment_status",
            "tree",
            "indicators",
            "source_of_truth_references",
            "capability_profile",
            "candidate_work_items",
        )
    }
    canonical = json.dumps(
        canonical_fields,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def _detect_stack(
    paths: list[str],
    contents: Mapping[str, str],
) -> tuple[list[str], list[str], dict[str, str], dict[str, bool]]:
    path_set = set(paths)
    stack: list[str] = []
    managers: list[str] = []
    versions: dict[str, str] = {}
    pubspec = contents.get("pubspec.yaml", "")
    if "pubspec.yaml" in path_set:
        stack.extend(["Flutter", "Dart"])
        managers.append("pub")
        dependency_markers = {
            "flutter_riverpod:": "Riverpod",
            "go_router:": "GoRouter",
            "flutter_map:": "Flutter Map",
            "supabase_flutter:": "Supabase Flutter SDK",
        }
        stack.extend(
            label
            for marker, label in dependency_markers.items()
            if marker in pubspec
        )
        app_version = re.search(r"(?m)^version:\s*([^\s]+)", pubspec)
        dart_match = re.search(r'(?m)^\s*sdk:\s*["\']?([^"\']+)', pubspec)
        flutter_match = re.search(r'(?m)^\s*flutter:\s*["\']?([^"\']+)', pubspec)
        if app_version:
            versions["application"] = app_version.group(1).strip()
        if dart_match:
            versions["dart"] = dart_match.group(1).strip()
        if flutter_match and "sdk: flutter" not in flutter_match.group(1):
            versions["flutter"] = flutter_match.group(1).strip()
    if "pyproject.toml" in path_set:
        stack.append("Python")
        managers.append("pyproject")
    if "package.json" in path_set:
        stack.append("Node")
        managers.append(
            "pnpm"
            if "pnpm-lock.yaml" in path_set
            else "yarn"
            if "yarn.lock" in path_set
            else "npm"
        )
    indicators = {
        "flutter": "pubspec.yaml" in path_set,
        "python": "pyproject.toml" in path_set,
        "node": "package.json" in path_set,
        "supabase": any(path.startswith("supabase/") for path in paths)
        or "supabase_flutter:" in pubspec,
        "database_migrations": any(
            path.startswith(("database/", "supabase/migrations/")) for path in paths
        ),
        "infrastructure": any(
            path in {"vercel.json", "Dockerfile", "docker-compose.yml"} for path in paths
        ),
    }
    return sorted(set(stack)), sorted(set(managers)), versions, indicators


def _detect_commands(
    paths: list[str],
    contents: Mapping[str, str],
) -> list[ProjectCommand]:
    commands: list[ProjectCommand] = []
    path_set = set(paths)
    evidence = (
        "docs/11_LOCAL_RUN_AND_VALIDATION.md"
        if "docs/11_LOCAL_RUN_AND_VALIDATION.md" in path_set
        else "pubspec.yaml"
    )
    if "pubspec.yaml" in path_set:
        for command, purpose in (
            ("dart format --output=none --set-exit-if-changed lib test", "format"),
            ("flutter analyze", "analyze"),
            ("flutter test", "test"),
            ("flutter build web --release", "build"),
        ):
            commands.append(
                ProjectCommand(command=command, purpose=purpose, evidence=evidence)
            )
    if "pyproject.toml" in path_set:
        commands.append(
            ProjectCommand(
                command="python -m pytest",
                purpose="test",
                evidence="pyproject.toml",
            )
        )
    return commands


def _tree_summary(
    raw_tree: list[dict[str, Any]],
    safe_tree: list[dict[str, Any]],
    paths: list[str],
    contents: Mapping[str, str],
) -> FileTreeSummary:
    return _tree_summary_from_paths(
        [str(item.get("path", "")) for item in raw_tree],
        [str(item.get("path", "")) for item in safe_tree],
        contents,
    )


def _tree_summary_from_paths(
    all_paths: list[str],
    paths: list[str],
    contents: Mapping[str, str],
) -> FileTreeSummary:
    return FileTreeSummary(
        total_files=len(all_paths),
        scanned_files=len(paths),
        truncated=len(all_paths) > len(paths),
        source_roots=sorted(
            root for root in ("lib", "src", "app") if any(p.startswith(f"{root}/") for p in paths)
        ),
        test_roots=sorted(
            root for root in ("test", "tests") if any(p.startswith(f"{root}/") for p in paths)
        ),
        manifest_files=sorted(
            path
            for path in paths
            if Path(path).name
            in {"pubspec.yaml", "pubspec.lock", "pyproject.toml", "package.json"}
        ),
        workflow_files=sorted(
            path for path in paths if path.startswith(".github/workflows/")
        ),
        state_files=sorted(
            path
            for path in paths
            if "state" in Path(path).name.casefold()
            or "handoff" in Path(path).name.casefold()
            or "baseline" in Path(path).name.casefold()
        )[:50],
        secret_risk_file_names=sorted(
            path for path in paths if SECRET_RISK_PATTERN.search(path)
        ),
        ignored_secret_policy_present=(
            ".env" in contents.get(".gitignore", "")
            and ".env.*" in contents.get(".gitignore", "")
        ),
    )


def _ci_reality(
    workflows_payload: Mapping[str, Any],
    runs_payload: Mapping[str, Any],
) -> list[CIWorkflowReality]:
    runs = [_object(value) for value in _sequence(runs_payload.get("workflow_runs"))]
    by_workflow: dict[int, dict[str, Any]] = {}
    for run in runs:
        workflow_id = int(run.get("workflow_id", 0) or 0)
        if workflow_id and workflow_id not in by_workflow:
            by_workflow[workflow_id] = run
    result: list[CIWorkflowReality] = []
    for workflow in _sequence(workflows_payload.get("workflows")):
        value = _object(workflow)
        workflow_id = int(value.get("id", 0) or 0)
        latest_run = by_workflow.get(workflow_id)
        result.append(
            CIWorkflowReality(
                provider="github_actions",
                name=str(value.get("name") or Path(str(value.get("path", ""))).name),
                path=str(value.get("path", "")) or None,
                status=(
                    str(latest_run.get("status"))
                    if latest_run
                    else "NO_RUN_OBSERVED"
                ),
                conclusion=(
                    str(latest_run.get("conclusion"))
                    if latest_run and latest_run.get("conclusion")
                    else None
                ),
                url=(
                    str(latest_run.get("html_url"))
                    if latest_run and latest_run.get("html_url")
                    else None
                ),
                observed_head=(
                    str(latest_run.get("head_sha"))
                    if latest_run and latest_run.get("head_sha")
                    else None
                ),
            )
        )
    return result


def _source_references(
    repository: str,
    head: str,
    paths: list[str],
) -> list[EvidenceReference]:
    references = [
        EvidenceReference(
            kind="github_commit",
            reference=f"https://github.com/{repository}/commit/{head}",
            observation="observed immutable repository HEAD",
        )
    ]
    for path in (
        "pubspec.yaml",
        "docs/11_LOCAL_RUN_AND_VALIDATION.md",
        "docs/project_memory/PAL_EYES_PROJECT_STATE_SNAPSHOT_CURRENT.json",
        "docs/project_memory/PAL_EYES_SESSION_HANDOFF_CURRENT.md",
    ):
        if path in paths:
            references.append(
                EvidenceReference(
                    kind="github_file",
                    reference=f"https://github.com/{repository}/blob/{head}/{path}",
                    observation="bounded metadata read",
                )
            )
    return references


def _overall_ci_status(ci: list[CIWorkflowReality]) -> str:
    if not ci:
        return "NOT_CONFIGURED"
    conclusions = {item.conclusion for item in ci}
    if "failure" in conclusions:
        return "FAILURE"
    if conclusions == {"success"}:
        return "SUCCESS"
    return "PENDING_OR_UNKNOWN"


def _overall_deployment_status(
    deployments: list[DeploymentReality],
) -> str:
    if not deployments:
        return "NOT_CONFIGURED"
    statuses = {item.status for item in deployments}
    if statuses == {"NOT_DISCOVERED"}:
        return "NOT_DISCOVERED"
    if "READY" in statuses:
        return "READY"
    return "UNKNOWN"


def _capability_profile(
    project_id: str,
    head: str,
    stack: list[str],
    paths: list[str],
    deployments: list[DeploymentReality],
) -> ProjectCapabilityProfile:
    selected = [
        ProjectToolDecision(
            adapter_id="github_repository",
            disposition=ToolDisposition.selected,
            reason="Required source-of-truth repository and CI reads.",
            evidence=[f"observed_head:{head}", "github_api:read_only"],
        ),
        ProjectToolDecision(
            adapter_id="workspace_manager_orchestrator",
            disposition=ToolDisposition.selected,
            reason="Required registry, report, fingerprint, and evidence persistence.",
            evidence=["external_project_registry:v1"],
        ),
    ]
    conditional = [
        ProjectToolDecision(
            adapter_id="vercel",
            disposition=ToolDisposition.conditional,
            reason="Read-only deployment discovery only when a matching project exists.",
            evidence=[deployment.status for deployment in deployments] or ["NOT_QUERIED"],
        ),
        ProjectToolDecision(
            adapter_id="local_git",
            disposition=ToolDisposition.conditional,
            reason="Available only for an explicitly allowlisted resolved path.",
            evidence=["allowlist_required"],
        ),
        ProjectToolDecision(
            adapter_id="figma",
            disposition=ToolDisposition.conditional,
            reason="Excluded from intake; reconsider only for later material UI implementation.",
            evidence=["read_only_intake_scope"],
        ),
    ]
    excluded = [
        ProjectToolDecision(
            adapter_id=adapter,
            disposition=ToolDisposition.excluded,
            reason="No concrete repository evidence requires this tool for read-only intake.",
            evidence=["bounded_minimum_tool_plan"],
        )
        for adapter in (
            "canva",
            "academic_research",
            "legal_research",
            "machine_learning",
            "gmail",
            "calendar",
            "contacts",
        )
    ]
    blocked = [
        ProjectToolDecision(
            adapter_id="supabase",
            disposition=ToolDisposition.blocked,
            reason=(
                "Task authority prohibits connection, schema, Auth, RLS, "
                "Storage, RPC, or data access."
            ),
            evidence=[
                "task:SUPABASE_EXCLUDED",
                "repository_indicator:true"
                if any(path.startswith("supabase/") for path in paths)
                else "repository_indicator:false",
            ],
        )
    ]
    return ProjectCapabilityProfile(
        project_id=project_id,
        observed_head=head,
        stack=stack,
        selected_tools=selected,
        conditional_tools=conditional,
        excluded_tools=excluded,
        blocked_tools=blocked,
    )


def _candidate_work_items(
    contents: Mapping[str, str],
    ci: list[CIWorkflowReality],
    paths: list[str],
) -> list[CandidateWorkItem]:
    result: list[CandidateWorkItem] = []
    failed = next((item for item in ci if item.conclusion == "failure"), None)
    if failed:
        result.append(
            CandidateWorkItem(
                rank=1,
                candidate_id="PAL_EYES_CI_FAILURE",
                title=f"Repair failing CI workflow: {failed.name}",
                rationale="The latest observed workflow conclusion is failure.",
                acceptance_test="The same workflow passes at a newly authorized immutable HEAD.",
                evidence=[failed.url or failed.name],
            )
        )
    gis_path = "lib/features/workspace/presentation/gis_review_screen.dart"
    if gis_path in paths:
        result.append(
            CandidateWorkItem(
                rank=len(result) + 1,
                candidate_id="PAL_EYES_GIS_CANDIDATE_VALIDATION",
                title="Require real coordinate and source evidence in GIS candidate intake",
                rationale=(
                    "The current product action creates a candidate with latitude 0, "
                    "longitude 0, and an empty source identifier."
                ),
                acceptance_test=(
                    "Widget and store tests reject empty source IDs and zero placeholder "
                    "coordinates, while a validated candidate remains internal-only."
                ),
                evidence=[gis_path, "project_state:r7_0_2_hotfix.gis_review_tasks=4"],
            )
        )
    state_path = "docs/project_memory/PAL_EYES_PROJECT_STATE_SNAPSHOT_CURRENT.json"
    handoff_path = "docs/project_memory/PAL_EYES_SESSION_HANDOFF_CURRENT.md"
    if state_path in contents or handoff_path in contents:
        result.append(
            CandidateWorkItem(
                rank=len(result) + 1,
                candidate_id="PAL_EYES_R8_0_1_RUNTIME_CLOSURE",
                title="Close R8.0.1 analyzer, test, and browser acceptance",
                rationale=(
                    "The canonical state and handoff report BUILT_PENDING_LOCAL_UAT "
                    "with format, analyze, test, and Browser UAT still pending."
                ),
                acceptance_test=(
                    "Pinned Flutter gates pass and desktop/mobile Arabic RTL browser UAT "
                    "records no overflow or legacy-label regression."
                ),
                evidence=[state_path, handoff_path],
            )
        )
    for index, item in enumerate(result[:10], start=1):
        item.rank = index
    return result[:10]


def _local_file_paths(root: Path) -> list[str]:
    paths: list[str] = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in IGNORED_LOCAL_DIRECTORIES
        )
        current_path = Path(current)
        for file_name in sorted(files):
            candidate = current_path / file_name
            if candidate.is_symlink():
                continue
            paths.append(candidate.relative_to(root).as_posix())
            if len(paths) > MAX_SCANNED_FILES:
                return paths
    return paths


def _local_metadata_contents(
    root: Path,
    safe_paths: list[str],
) -> dict[str, str]:
    contents: dict[str, str] = {}
    for relative in sorted(SAFE_METADATA_FILES.intersection(safe_paths)):
        candidate = root / relative
        if candidate.stat().st_size <= MAX_METADATA_BYTES:
            contents[relative] = candidate.read_text(
                encoding="utf-8",
                errors="replace",
            )
    return contents


def _repository_from_remote(origin: str) -> str:
    match = re.search(
        r"github\.com(?::|/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        origin.strip(),
        re.IGNORECASE,
    )
    if not match:
        raise GovernanceError("LOCAL_GIT_REMOTE_UNSUPPORTED")
    return match.group(1)


def _object(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
