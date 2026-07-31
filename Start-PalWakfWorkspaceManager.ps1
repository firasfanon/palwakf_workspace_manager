[CmdletBinding()]
param(
    [switch]$NoOpen,
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$repoLeaf = Split-Path -Leaf $repoRoot
$runtimeRoot = Join-Path $repoRoot ".palwakf"
$runtimeFile = Join-Path $runtimeRoot "local-runtime.json"
$logRoot = Join-Path $runtimeRoot "logs"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$flutter = (Get-Command flutter -ErrorAction SilentlyContinue).Source
$port = 8421
$baseUrl = "http://127.0.0.1:$port"

function ConvertFrom-ProtectedValue([string]$Value) {
    $secure = ConvertTo-SecureString $Value
    $credential = New-Object System.Management.Automation.PSCredential("local", $secure)
    return $credential.GetNetworkCredential().Password
}

function New-LocalToken {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Get-TokenDigest([string]$Token) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Token)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Invoke-Authenticated([string]$Method, [string]$Path, [string]$Token) {
    return Invoke-RestMethod `
        -Method $Method `
        -Uri "$baseUrl$Path" `
        -Headers @{ Authorization = "Bearer $Token"; Accept = "application/json" } `
        -ContentType "application/json" `
        -TimeoutSec 20
}

function Open-LocalSession([string]$Token) {
    $issued = Invoke-Authenticated "Post" "/local/session/issue" $Token
    if ([string]::IsNullOrWhiteSpace($issued.launch_path)) {
        throw "Local session launch was not issued"
    }
    if (-not $NoOpen) {
        Start-Process "$baseUrl$($issued.launch_path)"
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "PYTHON_RUNTIME_NOT_FOUND"
}
if (-not $flutter) {
    throw "FLUTTER_RUNTIME_NOT_FOUND"
}
if ((git -C $repoRoot branch --show-current) -ne "agent/workspace-manager-foundation-v1") {
    throw "GOVERNED_BRANCH_NOT_CHECKED_OUT"
}

New-Item -ItemType Directory -Path $runtimeRoot, $logRoot -Force | Out-Null

if (Test-Path -LiteralPath $runtimeFile) {
    $runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($runtime.orchestrator_pid)" `
        -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -like "*$repoLeaf*orchestrator*main.py*") {
        $token = ConvertFrom-ProtectedValue $runtime.protected_local_token
        $null = Invoke-Authenticated "Get" "/ready" $token
        $null = Invoke-Authenticated "Post" "/v1/local-product/bootstrap" $token
        Open-LocalSession $token
        Write-Output "PALWAKF_WORKSPACE_MANAGER=ALREADY_RUNNING"
        Write-Output "LOCAL_URL=$baseUrl/dashboard"
        exit 0
    }
    Remove-Item -LiteralPath $runtimeFile -Force
}

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "LOOPBACK_PORT_IN_USE:$port"
}

if (-not $SkipBuild) {
    & $flutter pub get
    if ($LASTEXITCODE -ne 0) { throw "FLUTTER_PUB_GET_FAILED" }
    & $flutter build web --release `
        --dart-define="ORCHESTRATOR_API_BASE_URL=$baseUrl"
    if ($LASTEXITCODE -ne 0) { throw "FLUTTER_WEB_BUILD_FAILED" }
}
elseif (-not (Test-Path -LiteralPath (Join-Path $repoRoot "build\web\index.html"))) {
    throw "LOCAL_FLUTTER_BUILD_NOT_FOUND"
}

. (Join-Path $repoRoot "scripts\orchestrator_runtime_env.ps1")
Import-PalWakfOpenAIRuntimeKey
& $python (Join-Path $repoRoot "orchestrator\main.py") credential-probe | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "OPENAI_RUNTIME_CREDENTIAL_UNAVAILABLE"
}

$token = New-LocalToken
$credential = @{
    client_id = "workspace-manager-local-ui"
    token_sha256 = Get-TokenDigest $token
    scopes = @(
        "tasks:read",
        "tasks:dispatch",
        "tasks:continue",
        "tasks:cancel",
        "tasks:verify",
        "tools:probe"
    )
}
$env:PALWAKF_AUTH_CLIENTS_JSON = (ConvertTo-Json @($credential) -Compress)
$env:PALWAKF_WORKSPACE_ROOT = $repoRoot
$env:PALWAKF_LOCAL_PROJECT_ALLOWLIST_JSON = (ConvertTo-Json @($repoRoot) -Compress)
$env:PALWAKF_WORKER_COUNT = "1"

$stdout = Join-Path $logRoot "orchestrator.out.log"
$stderr = Join-Path $logRoot "orchestrator.err.log"
$process = Start-Process `
    -FilePath $python `
    -ArgumentList @((Join-Path $repoRoot "orchestrator\main.py"), "serve", "--live-agents") `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($process.HasExited) {
            throw "ORCHESTRATOR_EXITED_BEFORE_READY:$($process.ExitCode)"
        }
        try {
            $null = Invoke-Authenticated "Get" "/ready" $token
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $ready) {
        throw "ORCHESTRATOR_READINESS_TIMEOUT"
    }
    $null = Invoke-Authenticated "Post" "/v1/local-product/bootstrap" $token
    @{
        version = 1
        orchestrator_pid = $process.Id
        port = $port
        protected_local_token = (
            ConvertTo-SecureString $token -AsPlainText -Force | ConvertFrom-SecureString
        )
        started_at = [DateTimeOffset]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $runtimeFile -Encoding UTF8
    Open-LocalSession $token
}
catch {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    throw
}
finally {
    $token = $null
    Remove-Item Env:PALWAKF_AUTH_CLIENTS_JSON -ErrorAction SilentlyContinue
}

Write-Output "PALWAKF_WORKSPACE_MANAGER=STARTED"
Write-Output "ORCHESTRATOR=CONNECTED"
Write-Output "AUTHENTICATION=VERIFIED"
Write-Output "WORKSPACE_MANAGER_PROJECT=REGISTERED"
Write-Output "LOCAL_URL=$baseUrl/dashboard"
