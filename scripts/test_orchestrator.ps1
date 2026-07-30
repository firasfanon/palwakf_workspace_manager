[CmdletBinding()]
param(
    [switch]$LiveDispatch,
    [string]$ExpectedHead = "",
    [string]$IdempotencyKey = "palwakf-runtime-closure-v1",
    [int]$TimeoutSeconds = 360
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found: $python"
}

. (Join-Path $PSScriptRoot "orchestrator_runtime_env.ps1")
Import-PalWakfOpenAIRuntimeKey
$env:PALWAKF_WORKSPACE_ROOT = $repoRoot

& $python (Join-Path $repoRoot "orchestrator\main.py") credential-probe
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python -m ruff format --check (Join-Path $repoRoot "orchestrator")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& $python -m ruff check (Join-Path $repoRoot "orchestrator")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& $python -m pytest (Join-Path $repoRoot "orchestrator")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($LiveDispatch) {
    if ([string]::IsNullOrWhiteSpace($ExpectedHead)) {
        throw "ExpectedHead is required for live dispatch"
    }
    & $python (Join-Path $repoRoot "orchestrator\scripts\live_dispatch.py") `
        --expected-head $ExpectedHead `
        --idempotency-key $IdempotencyKey `
        --timeout-seconds $TimeoutSeconds
    exit $LASTEXITCODE
}
