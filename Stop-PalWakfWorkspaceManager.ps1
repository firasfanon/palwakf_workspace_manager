[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$repoLeaf = Split-Path -Leaf $repoRoot
$runtimeFile = Join-Path $repoRoot ".palwakf\local-runtime.json"
if (-not (Test-Path -LiteralPath $runtimeFile)) {
    Write-Output "PALWAKF_WORKSPACE_MANAGER=STOPPED"
    exit 0
}

$runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $($runtime.orchestrator_pid)" `
    -ErrorAction SilentlyContinue
if ($process) {
    if ($process.CommandLine -notlike "*$repoLeaf*orchestrator*main.py*") {
        throw "RUNTIME_PROCESS_IDENTITY_MISMATCH"
    }
    Stop-Process -Id $process.ProcessId -Force
}
Remove-Item -LiteralPath $runtimeFile -Force
Write-Output "PALWAKF_WORKSPACE_MANAGER=STOPPED"
