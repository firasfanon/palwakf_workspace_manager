[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$repoLeaf = Split-Path -Leaf $repoRoot
$runtimeFile = Join-Path $repoRoot ".palwakf\local-runtime.json"
$defaultPort = 8421

function Get-Listener([int]$Port) {
    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Get-ManagedProcess([int]$ProcessId) {
    return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Test-WorkspaceProcess($Process) {
    if ($null -eq $Process) {
        return $false
    }
    $line = [string]$Process.CommandLine
    return ($line -like "*$repoLeaf*orchestrator*main.py*" -and $line -like "*serve*")
}

if (-not (Test-Path -LiteralPath $runtimeFile)) {
    $unmanagedListener = Get-Listener $defaultPort
    if ($null -ne $unmanagedListener) {
        throw "RUNTIME_STATE_MISSING_WITH_LISTENER:$($unmanagedListener.OwningProcess)"
    }
    Write-Output "PALWAKF_WORKSPACE_MANAGER=STOPPED"
    exit 0
}

$runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
$parentId = [int]$runtime.orchestrator_pid
$port = if ($runtime.PSObject.Properties.Name -contains "port") {
    [int]$runtime.port
}
else {
    $defaultPort
}

$parent = Get-ManagedProcess $parentId
if ($null -ne $parent -and -not (Test-WorkspaceProcess $parent)) {
    throw "RUNTIME_PROCESS_IDENTITY_MISMATCH"
}

$listener = Get-Listener $port
if ($null -ne $listener) {
    $listenerId = [int]$listener.OwningProcess
    $listenerProcess = Get-ManagedProcess $listenerId
    if (-not (Test-WorkspaceProcess $listenerProcess)) {
        throw "RUNTIME_LISTENER_IDENTITY_MISMATCH:$listenerId"
    }

    if ($listenerId -ne $parentId) {
        if ([int]$listenerProcess.ParentProcessId -ne $parentId) {
            throw "RUNTIME_LISTENER_PARENT_MISMATCH:$listenerId"
        }
        Stop-Process -Id $listenerId -Force -ErrorAction Stop
        Write-Output "WORKSPACE_CHILD_LISTENER=STOPPED PID=$listenerId"
    }
}

if ($null -ne $parent) {
    Stop-Process -Id $parentId -Force -ErrorAction Stop
    Write-Output "WORKSPACE_PARENT=STOPPED PID=$parentId"
}

for ($attempt = 1; $attempt -le 20; $attempt++) {
    if ($null -eq (Get-Listener $port)) {
        break
    }
    Start-Sleep -Milliseconds 250
}

if ($null -ne (Get-Listener $port)) {
    throw "WORKSPACE_PORT_DID_NOT_RELEASE:$port"
}

Remove-Item -LiteralPath $runtimeFile -Force
Write-Output "PALWAKF_WORKSPACE_MANAGER=STOPPED"
