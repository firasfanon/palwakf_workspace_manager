from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.project_contracts import (
    DeploymentReality,
    ProjectAdapterKind,
    ProjectIntakeRequest,
)
from palwakf_orchestrator.project_reality import (
    GitHubRepositoryRealityAdapter,
    HttpxGitHubReadClient,
)
from palwakf_orchestrator.project_service import ExternalProjectService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded read-only external-project reality probe."
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument(
        "--deployment-status",
        default="NOT_DISCOVERED",
        choices=("NOT_DISCOVERED", "READY", "ERROR", "UNKNOWN"),
    )
    parser.add_argument(
        "--deployment-evidence",
        default="Vercel read-only project inventory",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    observed_at = datetime.fromisoformat(args.observed_at.replace("Z", "+00:00"))
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    repository = str(args.repository)
    adapter = GitHubRepositoryRealityAdapter(
        HttpxGitHubReadClient(os.environ.get("GITHUB_TOKEN")),
        deployment_observations={
            repository: DeploymentReality(
                provider="vercel",
                status=args.deployment_status,
                evidence=args.deployment_evidence,
            )
        },
        now=lambda: observed_at,
    )
    state_store = MemoryStateStore()
    service = ExternalProjectService(
        {ProjectAdapterKind.github_repository: adapter},
        state_store,
        now=lambda: observed_at,
    )
    record = service.intake(
        ProjectIntakeRequest(
            repository_full_name=repository,
            display_name=args.display_name,
        )
    )
    report = await service.probe(record.project_id)
    restored = ExternalProjectService(
        {ProjectAdapterKind.github_repository: adapter},
        state_store,
        now=lambda: observed_at,
    )
    if restored.reality(record.project_id).baseline_fingerprint != (
        report.baseline_fingerprint
    ):
        raise RuntimeError("PERSISTED_REALITY_FINGERPRINT_MISMATCH")

    report_payload = {
        "task_id": (
            "PALWAKF_WORKSPACE_MANAGER_EXTERNAL_PROJECT_INTAKE_"
            "AND_REALITY_ADAPTER_V1"
        ),
        "probe_mode": "READ_ONLY_ZERO_MUTATION",
        "registry_persistence": "PASS_MEMORY_STATE_STORE_ROUND_TRIP",
        "report": report.model_dump(mode="json"),
        "external_mutation": False,
        "supabase_connected": False,
        "production_mutation": False,
        "secret_values_exposed": False,
    }
    _write_json(args.report_output, report_payload)
    _write_json(
        args.profile_output,
        report.capability_profile.model_dump(mode="json"),
    )
    print(
        "PAL_EYES_READ_ONLY_PROBE_PASS "
        f"HEAD={report.observed_head} "
        f"FINGERPRINT={report.baseline_fingerprint} "
        f"CANDIDATES={len(report.candidate_work_items)}"
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
