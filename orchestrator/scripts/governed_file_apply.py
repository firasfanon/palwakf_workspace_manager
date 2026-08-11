from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path

from palwakf_orchestrator.file_apply_contracts import GovernedFileApplyRequest
from palwakf_orchestrator.persistence import SQLiteStateStore
from palwakf_orchestrator.transactional_file_apply import GovernedTransactionalFileApply


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Governed transactional source-file apply engine",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    state_db = (args.state_db or repo_root / ".palwakf" / "orchestrator.sqlite3").resolve()
    request = GovernedFileApplyRequest.model_validate_json(
        args.manifest.read_text(encoding="utf-8-sig")
    )
    service = GovernedTransactionalFileApply(
        repo_root,
        SQLiteStateStore(state_db),
        execution_host_id=f"host-{socket.gethostname().lower()}",
    )
    result = service.plan(request) if args.plan_only else service.apply(request)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
