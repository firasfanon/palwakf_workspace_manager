[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found: $python"
}

. (Join-Path $PSScriptRoot "orchestrator_runtime_env.ps1")
Import-PalWakfOpenAIRuntimeKey
$env:PALWAKF_WORKSPACE_ROOT = $repoRoot

$staticAuth = -not [string]::IsNullOrWhiteSpace($env:PALWAKF_AUTH_CLIENTS_JSON)
$oauthAuth = (
    -not [string]::IsNullOrWhiteSpace($env:PALWAKF_OAUTH_AUTHORIZATION_SERVER) -and
    -not [string]::IsNullOrWhiteSpace($env:PALWAKF_OAUTH_JWKS_URL) -and
    -not [string]::IsNullOrWhiteSpace($env:PALWAKF_OAUTH_AUDIENCE)
)
if (-not ($staticAuth -or $oauthAuth)) {
    throw "Connected service authentication is not configured"
}

& $python (Join-Path $repoRoot "orchestrator\main.py") credential-probe
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python (Join-Path $repoRoot "orchestrator\main.py") serve --live-agents
exit $LASTEXITCODE
