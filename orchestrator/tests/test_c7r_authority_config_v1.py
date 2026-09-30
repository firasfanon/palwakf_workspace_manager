from __future__ import annotations

from pathlib import Path

from palwakf_orchestrator.config import Settings


def test_authority_key_path_matches_bootstrap_programdata_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    program_data = tmp_path / "ProgramData"
    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    settings = Settings(workspace_root=tmp_path)

    assert settings.resolved_authority_key_path == (
        program_data
        / "PalWakf"
        / "workspace_authority_v1"
        / "secrets"
        / "workspace-ed25519.dpapi"
    )
