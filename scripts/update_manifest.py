from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "MANIFEST_SHA256.json"


def repository_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(
        {
            path.replace("\\", "/")
            for path in result.stdout.splitlines()
            if path and path.replace("\\", "/") != MANIFEST
        }
    )


def main() -> None:
    files = []
    for relative in repository_files():
        content = (ROOT / relative).read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest().upper(),
                "size": len(content),
            }
        )
    manifest = {
        "batch": (
            "PALWAKF_WORKSPACE_MANAGER_MAIN_DASHBOARD_"
            "AND_PROJECT_OPERATIONS_SHELL_V1"
        ),
        "status": "MAIN_DASHBOARD_AND_OPERATIONS_SHELL_LOCAL_VALIDATION_PASS",
        "file_count": len(files),
        "files": files,
    }
    (ROOT / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"MANIFEST_UPDATED FILES={len(files)}")


if __name__ == "__main__":
    main()
