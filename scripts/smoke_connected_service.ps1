[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot "orchestrator\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Orchestrator Python environment not found: $python"
}

Push-Location (Join-Path $repoRoot "orchestrator")
try {
    & $python "scripts\connected_service_smoke.py"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
