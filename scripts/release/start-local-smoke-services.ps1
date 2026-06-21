param(
    [string]$DeployEnvPath = "deploy/.env",
    [string]$CrawlerEnvPath = "crawler-service/.env",
    [switch]$BackendOnly,
    [switch]$CrawlerOnly
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Read-EnvFile([string]$Path) {
    $resolved = Join-Path $Root $Path
    $map = @{}
    if (-not (Test-Path -LiteralPath $resolved)) {
        return $map
    }
    foreach ($line in Get-Content -LiteralPath $resolved) {
        if ($line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $idx = $line.IndexOf("=")
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1)
        if ($name) {
            $map[$name] = $value
        }
    }
    return $map
}

function Set-ProcessEnv([hashtable]$Values, [string[]]$Skip = @()) {
    foreach ($key in $Values.Keys) {
        if ($Skip -contains $key) {
            continue
        }
        [Environment]::SetEnvironmentVariable($key, [string]$Values[$key], "Process")
    }
}

function Test-Port([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connections
}

function Start-HiddenProcess(
    [string]$Name,
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [string]$LogPath,
    [string]$ErrorPath
) {
    $logFull = Join-Path $Root $LogPath
    $errFull = Join-Path $Root $ErrorPath
    $logDir = Split-Path -Parent $logFull
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory (Join-Path $Root $WorkingDirectory) `
        -RedirectStandardOutput $logFull `
        -RedirectStandardError $errFull `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "$Name started: pid=$($process.Id), log=$LogPath, err=$ErrorPath"
}

$deployEnv = Read-EnvFile $DeployEnvPath
$crawlerEnv = Read-EnvFile $CrawlerEnvPath

# Do not inject deploy DB/encryption values into local dev by default; existing
# local databases are often initialized with the dev defaults.
Set-ProcessEnv $deployEnv @("DB_PASSWORD", "BLOG_SECURITY_ENCRYPTION_KEY")
Set-ProcessEnv $crawlerEnv

if ($deployEnv.ContainsKey("CRAWLER_API_KEY")) {
    [Environment]::SetEnvironmentVariable("API_KEYS", $deployEnv["CRAWLER_API_KEY"], "Process")
}
if ($deployEnv.ContainsKey("CRAWLER_CALLBACK_API_KEY")) {
    [Environment]::SetEnvironmentVariable("CALLBACK_API_KEY", $deployEnv["CRAWLER_CALLBACK_API_KEY"], "Process")
}
[Environment]::SetEnvironmentVariable("CRAWLER_SERVICE_URL", "http://localhost:8500", "Process")
[Environment]::SetEnvironmentVariable("CRAWLER_CALLBACK_URL", "http://localhost:8081/api/internal/collector/callback", "Process")
[Environment]::SetEnvironmentVariable("JAVA_API_URL", "http://localhost:8081", "Process")
[Environment]::SetEnvironmentVariable("CALLBACK_URL", "http://localhost:8081/api/internal/collector/callback", "Process")

if (-not $CrawlerOnly) {
    if (Test-Port 8081) {
        Write-Host "Backend already listening on 8081"
    } else {
        Start-HiddenProcess `
            "Backend" `
            "mvn.cmd" `
            @("spring-boot:run") `
            "backend" `
            "runtime-logs/backend-smoke.log" `
            "runtime-logs/backend-smoke.err.log"
    }
}

if (-not $BackendOnly) {
    if (Test-Port 8500) {
        Write-Host "Crawler already listening on 8500"
    } else {
        $python = Join-Path $Root "crawler-service\.venv\Scripts\python.exe"
        Start-HiddenProcess `
            "Crawler" `
            $python `
            @("-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8500") `
            "crawler-service" `
            "runtime-logs/crawler-smoke.log" `
            "runtime-logs/crawler-smoke.err.log"
    }
}
