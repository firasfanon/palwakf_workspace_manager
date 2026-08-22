from __future__ import annotations

import re
import subprocess
from pathlib import Path

from palwakf_orchestrator.database_contracts import SupabaseCliToolStatus


class SupabaseCliAdapter:
    """Governed project-local Supabase CLI boundary."""

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root.resolve()
        self._binary = (self._workspace_root / "node_modules" / ".bin" / "supabase.cmd").resolve()

    def probe(self) -> SupabaseCliToolStatus:
        if not self._binary.is_file():
            return SupabaseCliToolStatus(available=False)

        try:
            completed = subprocess.run(
                [str(self._binary), "--version"],
                cwd=self._workspace_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return SupabaseCliToolStatus(available=False)

        if completed.returncode != 0:
            return SupabaseCliToolStatus(available=False)

        raw = (completed.stdout or completed.stderr).strip()
        match = re.search(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?", raw)
        return SupabaseCliToolStatus(
            available=True,
            version=match.group(0) if match else raw or None,
        )

    def remote_mutation(self, *_: object, **__: object) -> None:
        raise PermissionError("SUPABASE_REMOTE_MUTATION_DENIED_BY_DEFAULT")
