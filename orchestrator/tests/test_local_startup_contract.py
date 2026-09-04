from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "Start-PalWakfWorkspaceManager.ps1"


def launcher_source() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_launcher_uses_current_git_identity_instead_of_legacy_branch() -> None:
    source = launcher_source()

    assert "agent/workspace-manager-foundation-v1" not in source
    assert "git -C $repoRoot branch --show-current" in source
    assert "git -C $repoRoot rev-parse HEAD" in source
    assert "$env:PALWAKF_GOVERNED_BRANCH = $currentBranch" in source
    assert '$env:PALWAKF_PULL_REQUEST_NUMBER = "$pullRequestNumber"' in source


def test_launcher_uses_existing_same_origin_local_session_contract() -> None:
    source = launcher_source()

    assert '"/local/session/issue"' in source
    assert 'Start-Process "$baseUrl$($issued.launch_path)"' in source
    assert "SESSION=AUTO_ISSUED" in source
    assert "Set-Clipboard" not in source
    assert "TOKEN_COPIED_TO_CLIPBOARD" not in source


def test_launcher_recovers_runtime_state_without_trusting_stale_pid() -> None:
    source = launcher_source()

    assert "function Get-Listener" in source
    assert "function Test-ManagedOrchestratorProcess" in source
    assert "function Test-AuthenticatedReady" in source
    assert "source_branch = $Branch" in source
    assert "source_head = $Head" in source
    assert "build_head = $BuildHead" in source
    assert "Write-RuntimeRecord" in source
    assert "Stop-ManagedOrchestrator" in source


def test_launcher_fails_closed_for_unknown_port_owner() -> None:
    source = launcher_source()

    assert "LOOPBACK_PORT_IN_USE_BY_UNKNOWN_PROCESS" in source
    assert "Test-ManagedOrchestratorProcess $managedProcess $runtime" in source


def test_launcher_tracks_web_build_provenance() -> None:
    source = launcher_source()

    assert "build-web-head.txt" in source
    assert "$buildHead -eq $currentHead" in source
    assert "BUILD_MUTATED_SOURCE_WORKTREE" in source
    assert '--dart-define="ORCHESTRATOR_API_BASE_URL=$baseUrl"' in source


def test_launcher_never_logs_or_exports_plain_local_token() -> None:
    source = launcher_source()

    assert "protected_local_token" in source
    assert "ConvertFrom-SecureString" in source
    assert 'Write-Output "TOKEN=' not in source
    assert 'Write-Host "TOKEN=' not in source
    assert "$env:PALWAKF_LOCAL_TOKEN" not in source


def test_launcher_tolerates_legacy_runtime_record_schema_under_strict_mode() -> None:
    source = launcher_source()

    assert "function Get-RuntimeValue" in source
    assert 'Get-RuntimeValue -Record $RuntimeRecord -Name "source_branch"' in source
    assert 'Get-RuntimeValue -Record $RuntimeRecord -Name "pull_request_number"' in source
    assert 'Get-RuntimeValue -Record $runtime -Name "source_head"' in source
    assert 'Get-RuntimeValue -Record $runtime -Name "build_head"' in source

    forbidden_direct_accesses = (
        "$RuntimeRecord.source_branch",
        "$RuntimeRecord.pull_request_number",
        "$runtime.source_branch",
        "$runtime.source_head",
        "$runtime.pull_request_number",
        "$runtime.build_head",
    )
    for direct_access in forbidden_direct_accesses:
        assert direct_access not in source
