from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = re.compile(
    r"(^|/)(\.env($|\.)|[^/]+\.(pem|p12|pfx|jks|keystore))",
    re.IGNORECASE,
)
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


def tracked_and_pending_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(set(result.stdout.splitlines()))


def main() -> int:
    findings: list[str] = []
    for relative in tracked_and_pending_files():
        normalized = relative.replace("\\", "/")
        if FORBIDDEN_NAMES.search(normalized) and normalized != ".env.example":
            findings.append(f"{normalized}:forbidden_credential_file")
            continue
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{normalized}:{line_number}:{label}")
    if findings:
        print("SECRET_SCAN=FAIL")
        for finding in findings:
            print(finding)
        return 1
    print(f"SECRET_SCAN=PASS FILES={len(tracked_and_pending_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
