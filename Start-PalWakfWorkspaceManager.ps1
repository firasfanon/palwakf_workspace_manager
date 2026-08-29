[CmdletBinding()]
param(
    [switch]$NoOpen,
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$runtimeRoot = Join-Path $repoRoot ".palwakf"
$runtimeFile = Join-Path $runtimeRoot "local-runtime.json"
$buildStampFile = Join-Path $runtimeRoot "build-web-head.txt"
$logRoot = Join-Path $runtimeRoot "logs"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$flutterCommand = Get-Command flutter -ErrorAction SilentlyContinue
$flutter = if ($flutterCommand) { $flutterCommand.Source } else { $null }
$port = 8421
$baseUrl = "http://127.0.0.1:$port"
$repository = "firasfanon/palwakf_workspace_manager"
$launcherVersion = 2

function ConvertFrom-ProtectedValue([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }
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

function Test-AuthenticatedReady([string]$Token) {
    if ([string]::IsNullOrWhiteSpace($Token)) {
        return $false
    }
    try {
        $null = Invoke-Authenticated "Get" "/ready" $Token
        return $true
    }
    catch {
        return $false
    }
}

function Open-LocalSession([string]$Token) {
    $issued = Invoke-Authenticated "Post" "/local/session/issue" $Token
    if ([string]::IsNullOrWhiteSpace($issued.launch_path)) {
        throw "LOCAL_SESSION_LAUNCH_NOT_ISSUED"
    }
    if (-not $issued.launch_path.StartsWith("/local/session/")) {
        throw "LOCAL_SESSION_LAUNCH_PATH_INVALID"
    }
    if (-not $NoOpen) {
        Start-Process "$baseUrl$($issued.launch_path)"
    }
}

function Read-RuntimeRecord {
    if (-not (Test-Path -LiteralPath $runtimeFile)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-Listener {
    $listeners = @(
        Get-NetTCPConnection `
            -LocalPort $port `
            -State Listen `
            -ErrorAction SilentlyContinue
    )
    if ($listeners.Count -eq 0) {
        return $null
    }
    return $listeners[0]
}

function Test-ManagedOrchestratorProcess($Process, $RuntimeRecord) {
    if (-not $Process) {
        return $false
    }

    $name = [string]$Process.Name
    if ($name -notin @("python.exe", "pythonw.exe")) {
        return $false
    }

    $commandLine = [string]$Process.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
    }

    $normalized = $commandLine.Replace("/", "\").ToLowerInvariant()
    $expectedMain = (Join-Path $repoRoot "orchestrator\main.py").Replace("/", "\").ToLowerInvariant()

    $isServe = $normalized.Contains(" serve ")
    $isLiveAgents = $normalized.Contains("--live-agents")
    if (-not ($isServe -and $isLiveAgents)) {
        return $false
    }

    if ($normalized.Contains($expectedMain)) {
        return $true
    }

    $legacyRelativeMain = $normalized.Contains("orchestrator\main.py")
    $runtimeClaimsPort = $RuntimeRecord -and ([int]$RuntimeRecord.port -eq $port)
    return $legacyRelativeMain -and $runtimeClaimsPort
}

function Stop-ManagedOrchestrator([int]$ProcessId) {
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (-not (Get-Listener)) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "ORCHESTRATOR_PORT_DID_NOT_RELEASE"
}

function Resolve-PullRequestNumber([string]$Branch, $RuntimeRecord) {
    if ($env:PALWAKF_PULL_REQUEST_NUMBER -match "^[1-9][0-9]*$") {
        return [int]$env:PALWAKF_PULL_REQUEST_NUMBER
    }

    if (
        $RuntimeRecord -and
        ([string]$RuntimeRecord.source_branch -eq $Branch) -and
        ([string]$RuntimeRecord.pull_request_number -match "^[1-9][0-9]*$")
    ) {
        return [int]$RuntimeRecord.pull_request_number
    }

    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) {
        try {
            $json = & $gh.Source pr list `
                --repo $repository `
                --head $Branch `
                --state open `
                --limit 1 `
                --json number 2>$null

            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($json)) {
                $items = $json | ConvertFrom-Json
                if ($items -and $items.Count -gt 0 -and [int]$items[0].number -gt 0) {
                    return [int]$items[0].number
                }
            }
        }
        catch {
            # Fall through to the read-only public REST lookup.
        }
    }

    try {
        $owner = $repository.Split("/")[0]
        $encodedHead = [Uri]::EscapeDataString("$owner`:$Branch")
        $headers = @{
            Accept = "application/vnd.github+json"
            "User-Agent" = "PalWakf-Workspace-Manager"
        }
        $pulls = Invoke-RestMethod `
            -Method Get `
            -Uri "https://api.github.com/repos/$repository/pulls?state=open&head=$encodedHead&per_page=1" `
            -Headers $headers `
            -TimeoutSec 10

        if ($pulls -and $pulls.Count -gt 0 -and [int]$pulls[0].number -gt 0) {
            return [int]$pulls[0].number
        }
    }
    catch {
        # Local startup must not depend on GitHub availability.
    }

    return 1
}

function Write-RuntimeRecord(
    [int]$ProcessId,
    [string]$ProtectedToken,
    [string]$Branch,
    [string]$Head,
    [int]$PullRequestNumber,
    [string]$BuildHead,
    [string]$StartedAt
) {
    @{
        version = $launcherVersion
        orchestrator_pid = $ProcessId
        port = $port
        protected_local_token = $ProtectedToken
        started_at = $StartedAt
        repository = $repository
        source_branch = $Branch
        source_head = $Head
        pull_request_number = $PullRequestNumber
        build_head = $BuildHead
    } |
        ConvertTo-Json |
        Set-Content -LiteralPath $runtimeFile -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "PYTHON_RUNTIME_NOT_FOUND"
}
if (-not $flutter) {
    throw "FLUTTER_RUNTIME_NOT_FOUND"
}

$currentBranch = (& git -C $repoRoot branch --show-current).Trim()
$currentHead = (& git -C $repoRoot rev-parse HEAD).Trim()

if ([string]::IsNullOrWhiteSpace($currentBranch)) {
    throw "DETACHED_HEAD_NOT_SUPPORTED"
}
if ([string]::IsNullOrWhiteSpace($currentHead)) {
    throw "SOURCE_HEAD_UNAVAILABLE"
}

$worktreeState = @(& git -C $repoRoot status --porcelain)
if ($worktreeState.Count -gt 0) {
    throw "WORKTREE_NOT_CLEAN_FOR_PRODUCT_START"
}

New-Item -ItemType Directory -Path $runtimeRoot, $logRoot -Force | Out-Null

$runtime = Read-RuntimeRecord
$pullRequestNumber = Resolve-PullRequestNumber $currentBranch $runtime
$buildIndex = Join-Path $repoRoot "build\web\index.html"

$buildHead = $null
if (Test-Path -LiteralPath $buildStampFile) {
    $buildHead = (Get-Content -LiteralPath $buildStampFile -Raw).Trim()
}

$buildCurrent = (
    (Test-Path -LiteralPath $buildIndex) -and
    ($buildHead -eq $currentHead)
)

if ($SkipBuild) {
    if (-not (Test-Path -LiteralPath $buildIndex)) {
        throw "LOCAL_FLUTTER_BUILD_NOT_FOUND"
    }
}
elseif (-not $buildCurrent) {
    & $flutter pub get
    if ($LASTEXITCODE -ne 0) {
        throw "FLUTTER_PUB_GET_FAILED"
    }

    & $flutter build web --release `
        --dart-define="ORCHESTRATOR_API_BASE_URL=$baseUrl"
    if ($LASTEXITCODE -ne 0) {
        throw "FLUTTER_WEB_BUILD_FAILED"
    }

    $postBuildWorktree = @(& git -C $repoRoot status --porcelain)
    if ($postBuildWorktree.Count -gt 0) {
        throw "BUILD_MUTATED_SOURCE_WORKTREE"
    }

    Set-Content -LiteralPath $buildStampFile -Value $currentHead -Encoding ASCII
    $buildHead = $currentHead
}
else {
    $buildHead = $currentHead
}

$listener = Get-Listener
$managedProcess = $null
$storedToken = $null
$canReuse = $false

if ($listener) {
    $managedProcess = Get-CimInstance Win32_Process `
        -Filter "ProcessId = $($listener.OwningProcess)" `
        -ErrorAction SilentlyContinue

    if (-not (Test-ManagedOrchestratorProcess $managedProcess $runtime)) {
        throw "LOOPBACK_PORT_IN_USE_BY_UNKNOWN_PROCESS:$port"
    }

    if ($runtime) {
        try {
            $storedToken = ConvertFrom-ProtectedValue ([string]$runtime.protected_local_token)
        }
        catch {
            $storedToken = $null
        }

        $provenanceMatches = (
            ([int]$runtime.port -eq $port) -and
            ([string]$runtime.source_branch -eq $currentBranch) -and
            ([string]$runtime.source_head -eq $currentHead) -and
            ([int]$runtime.pull_request_number -eq $pullRequestNumber) -and
            ([string]$runtime.build_head -eq $buildHead)
        )

        if ($provenanceMatches -and (Test-AuthenticatedReady $storedToken)) {
            $protectedToken = [string]$runtime.protected_local_token
            $startedAt = if ([string]::IsNullOrWhiteSpace([string]$runtime.started_at)) {
                [DateTimeOffset]::UtcNow.ToString("o")
            }
            else {
                [string]$runtime.started_at
            }

            Write-RuntimeRecord `
                -ProcessId ([int]$listener.OwningProcess) `
                -ProtectedToken $protectedToken `
                -Branch $currentBranch `
                -Head $currentHead `
                -PullRequestNumber $pullRequestNumber `
                -BuildHead $buildHead `
                -StartedAt $startedAt

            $canReuse = $true
        }
    }

    if (-not $canReuse) {
        Stop-ManagedOrchestrator ([int]$listener.OwningProcess)
        Remove-Item -LiteralPath $runtimeFile -Force -ErrorAction SilentlyContinue
        $runtime = $null
        $storedToken = $null
        $listener = $null
    }
}
elseif (Test-Path -LiteralPath $runtimeFile) {
    Remove-Item -LiteralPath $runtimeFile -Force
    $runtime = $null
}

if ($canReuse) {
    $null = Invoke-Authenticated "Post" "/v1/local-product/bootstrap" $storedToken
    Open-LocalSession $storedToken
    $storedToken = $null

    Write-Output "PALWAKF_WORKSPACE_MANAGER=ALREADY_RUNNING"
    Write-Output "ORCHESTRATOR=CONNECTED"
    Write-Output "AUTHENTICATION=VERIFIED"
    Write-Output "SESSION=AUTO_ISSUED"
    Write-Output "SOURCE_BRANCH=$currentBranch"
    Write-Output "SOURCE_HEAD=$currentHead"
    Write-Output "LOCAL_URL=$baseUrl/dashboard"
    exit 0
}

. (Join-Path $repoRoot "scripts\orchestrator_runtime_env.ps1")

$hadOpenAIKey = Test-Path Env:OPENAI_API_KEY
$previousOpenAIKey = if ($hadOpenAIKey) { $env:OPENAI_API_KEY } else { $null }

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
$env:PALWAKF_REPOSITORY = $repository
$env:PALWAKF_GOVERNED_BRANCH = $currentBranch
$env:PALWAKF_PULL_REQUEST_NUMBER = "$pullRequestNumber"
$env:PALWAKF_PORT = "$port"
$env:PALWAKF_BIND_HOST = "127.0.0.1"

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

        if (Test-AuthenticatedReady $token) {
            $ready = $true
            break
        }

        Start-Sleep -Seconds 1
    }

    if (-not $ready) {
        throw "ORCHESTRATOR_READINESS_TIMEOUT"
    }

    $null = Invoke-Authenticated "Post" "/v1/local-product/bootstrap" $token

    $protectedToken = (
        ConvertTo-SecureString $token -AsPlainText -Force |
        ConvertFrom-SecureString
    )

    Write-RuntimeRecord `
        -ProcessId $process.Id `
        -ProtectedToken $protectedToken `
        -Branch $currentBranch `
        -Head $currentHead `
        -PullRequestNumber $pullRequestNumber `
        -BuildHead $buildHead `
        -StartedAt ([DateTimeOffset]::UtcNow.ToString("o"))

    Open-LocalSession $token
}
catch {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $runtimeFile -Force -ErrorAction SilentlyContinue
    throw
}
finally {
    $token = $null
    $storedToken = $null
    $credential = $null
    Remove-Item Env:PALWAKF_AUTH_CLIENTS_JSON -ErrorAction SilentlyContinue
    Remove-Item Env:PALWAKF_GOVERNED_BRANCH -ErrorAction SilentlyContinue
    Remove-Item Env:PALWAKF_PULL_REQUEST_NUMBER -ErrorAction SilentlyContinue
    Remove-Item Env:PALWAKF_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:PALWAKF_BIND_HOST -ErrorAction SilentlyContinue

    if ($hadOpenAIKey) {
        $env:OPENAI_API_KEY = $previousOpenAIKey
    }
    else {
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    }
    $previousOpenAIKey = $null
}

Write-Output "PALWAKF_WORKSPACE_MANAGER=STARTED"
Write-Output "ORCHESTRATOR=CONNECTED"
Write-Output "AUTHENTICATION=VERIFIED"
Write-Output "SESSION=AUTO_ISSUED"
Write-Output "WORKSPACE_MANAGER_PROJECT=REGISTERED"
Write-Output "SOURCE_BRANCH=$currentBranch"
Write-Output "SOURCE_HEAD=$currentHead"
Write-Output "LOCAL_URL=$baseUrl/dashboard"
