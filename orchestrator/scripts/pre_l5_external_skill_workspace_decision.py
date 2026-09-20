from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from palwakf_orchestrator.external_skill_admission import decide_external_skill


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mind-review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    review = json.loads(Path(args.mind_review).read_text(encoding="utf-8"))
    decisions: list[dict[str, Any]] = []
    for item in review["reviews"]:
        mind = item["mind_review"]
        blocking = tuple(
            finding["finding_id"] for finding in item.get("bundle_blocking_findings", [])
        )
        sandbox_pass = item.get("admission_decision") == "SANDBOX_PASS"
        decision = decide_external_skill(
            item["parsed_name"],
            mind_decision=mind["decision"],
            sandbox_pass=sandbox_pass,
            blocking_findings=blocking,
        )
        decisions.append(
            {
                "repository": item["repository"],
                "commit_sha": item["commit_sha"],
                "path": item["path"],
                "priority": item["priority"],
                "license": item["license"],
                "content_sha256": item["content_sha256"],
                "bundle_manifest_sha256": item["bundle_report"]["manifest_sha256"],
                "capability_flags": item.get("capability_flags", []),
                "mind_review": mind,
                "workspace_decision": decision.model_dump(mode="json"),
            }
        )

    counts: dict[str, int] = {}
    for item in decisions:
        key = item["workspace_decision"]["decision"]
        counts[key] = counts.get(key, 0) + 1

    output = {
        "schema": "PALWAKF_EXTERNAL_SKILL_WORKSPACE_DECISION_V1",
        "candidate_count": len(decisions),
        "bulk_install": False,
        "external_skill_execution_authority": False,
        "auto_canonical_promotion": False,
        "decision_counts": counts,
        "decisions": decisions,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": len(decisions), "decision_counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
