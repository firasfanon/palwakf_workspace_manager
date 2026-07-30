from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import DispatchRequest
from palwakf_orchestrator.credentials import probe_openai_api_key, require_openai_api_key
from palwakf_orchestrator.service import OrchestratorService

TASK_ID = "PALWAKF_ORCHESTRATOR_AGENTS_RUNTIME_KEY_INHERITANCE_AND_LIVE_DISPATCH_CLOSURE_V1"
PROMPT = (
    "Inspect the repository identity, current branch, and current HEAD. "
    "Return structured JSON only. Do not edit files, run mutation commands, commit, push, "
    "create branches, or contact production services."
)


def git(workspace: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def repository_snapshot(workspace: Path) -> dict[str, str]:
    status = git(workspace, "status", "--porcelain")
    return {
        "head": git(workspace, "rev-parse", "HEAD"),
        "worktree": "CLEAN" if not status else "DIRTY",
    }


async def run(args: argparse.Namespace) -> dict[str, object]:
    presence = require_openai_api_key()
    settings = Settings()
    workspace = settings.workspace_root.resolve()
    before = repository_snapshot(workspace)
    request = DispatchRequest(
        task_id=TASK_ID,
        prompt=PROMPT,
        repository=settings.repository,
        branch=settings.governed_branch,
        expected_head=args.expected_head,
        idempotency_key=args.idempotency_key,
        transport="sdk",
    )
    service = OrchestratorService(settings)

    async with asyncio.timeout(args.timeout_seconds):
        first = await service.dispatch(request)
        second = await service.dispatch(request)

    after = repository_snapshot(workspace)
    if before != after or after["worktree"] != "CLEAN":
        raise RuntimeError(f"repository mutation detected: before={before}, after={after}")
    if first.execution_receipt != second.execution_receipt:
        raise RuntimeError("duplicate idempotency key created a second execution receipt")
    if first.codex_thread_id != second.codex_thread_id:
        raise RuntimeError("duplicate idempotency key created a second Codex thread")
    if first.idempotency_replayed or not second.idempotency_replayed:
        raise RuntimeError("idempotency replay markers are invalid")

    return {
        "task_id": TASK_ID,
        "runtime_key_presence": presence.as_safe_dict(),
        "before": before,
        "after": after,
        "agents_response_id": first.agents_response_id,
        "execution_receipt": first.execution_receipt,
        "codex_thread_id": first.codex_thread_id,
        "codex_status": first.status,
        "final_response": first.final_response,
        "idempotency": {
            "key": args.idempotency_key,
            "first_replayed": first.idempotency_replayed,
            "second_replayed": second.idempotency_replayed,
            "same_receipt": first.execution_receipt == second.execution_receipt,
            "same_thread": first.codex_thread_id == second.codex_thread_id,
        },
        "timeout_seconds": args.timeout_seconds,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=360)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(run_sync(args), ensure_ascii=False, sort_keys=True))


def run_sync(args: argparse.Namespace) -> dict[str, object]:
    presence = probe_openai_api_key()
    if presence.state != "SET":
        require_openai_api_key()
    return asyncio.run(run(args))


if __name__ == "__main__":
    main()
