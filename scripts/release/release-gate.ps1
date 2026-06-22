param(
    [string]$EnvPath = "deploy/.env",
    [string]$CrawlerUrl = "http://localhost:8500",
    [string]$BackendUrl = "http://localhost:8081",
    [string]$CrawlerApiKey = $env:CRAWLER_API_KEY,
    [string]$ReportPath = "",
    [string]$MarkdownReportPath = "",
    [switch]$Fast,
    [switch]$RunSmoke,
    [switch]$TriggerDigest,
    [switch]$ForceDigest,
    [switch]$SkipBackendTests,
    [switch]$SkipCrawlerTests,
    [switch]$SkipFrontendBuild,
    [switch]$SkipAudit,
    [switch]$SkipComposeConfig,
    [switch]$SkipEnvCheck,
    [switch]$SkipSmoke,
    [int]$TimeoutMinutes = 30
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$StartedAt = Get-Date
$Results = New-Object System.Collections.Generic.List[object]

if ($Fast) {
    $SkipBackendTests = $true
    $SkipCrawlerTests = $true
    $SkipEnvCheck = $true
    $SkipSmoke = $true
}

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $ReportPath = Join-Path $Root "artifacts\release-gate\release-gate-$stamp.json"
}
if ([string]::IsNullOrWhiteSpace($MarkdownReportPath)) {
    $MarkdownReportPath = [System.IO.Path]::ChangeExtension($ReportPath, ".md")
}

function Redact-SecretText([string]$Text) {
    if ([string]::IsNullOrEmpty($Text)) {
        return $Text
    }
    $redacted = $Text
    $secretNames = @(
        "AI_API_KEY",
        "CRAWLER_API_KEY",
        "CRAWLER_CALLBACK_API_KEY",
        "CALLBACK_API_KEY",
        "API_KEYS",
        "BLOG_SECURITY_ENCRYPTION_KEY",
        "DB_PASSWORD"
    )
    foreach ($name in $secretNames) {
        $redacted = $redacted -replace "(?im)^(\s*$name\s*[:=]\s*).+$", "`${1}***REDACTED***"
    }
    $redacted = $redacted -replace "sk-[A-Za-z0-9_-]{12,}", "sk-***REDACTED***"
    return $redacted
}

function Add-Result([string]$Name, [string]$Status, [int]$ExitCode, [double]$Seconds, [string]$Output, [string]$ErrorText) {
    $safeOutput = Redact-SecretText $Output
    $safeError = Redact-SecretText $ErrorText
    $Results.Add([pscustomobject]@{
        name = $Name
        status = $Status
        exit_code = $ExitCode
        seconds = [math]::Round($Seconds, 2)
        output = $safeOutput
        error = $safeError
    }) | Out-Null
}

function Invoke-Step(
    [string]$Name,
    [string]$WorkDir,
    [string]$File,
    [string[]]$Arguments,
    [int]$TimeoutSec
) {
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $job = Start-Job -ScriptBlock {
        param($wd, $file, $argsForFile)
        Set-Location -LiteralPath $wd
        try {
            $lines = & $file @argsForFile 2>&1 | ForEach-Object { $_ | Out-String }
            $code = if ($null -eq $global:LASTEXITCODE) { 0 } else { $global:LASTEXITCODE }
            [pscustomobject]@{
                exit_code = [int]$code
                output = ($lines -join "")
            }
        } catch {
            [pscustomobject]@{
                exit_code = 1
                output = ($_ | Out-String)
            }
        }
    } -ArgumentList $WorkDir, $File, $Arguments

    $completed = Wait-Job $job -Timeout $TimeoutSec
    if (-not $completed) {
        Stop-Job $job -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $job -Force -ErrorAction SilentlyContinue | Out-Null
        $sw.Stop()
        $msg = "Timed out after $TimeoutSec seconds"
        Write-Host "FAIL: $msg" -ForegroundColor Red
        Add-Result $Name "failed" 124 $sw.Elapsed.TotalSeconds "" $msg
        return
    }

    $jobResult = Receive-Job $job
    $output = if ($jobResult -and ($jobResult.PSObject.Properties.Name -contains "output")) { [string]$jobResult.output } else { $jobResult | Out-String }
    $exitCode = if ($jobResult -and ($jobResult.PSObject.Properties.Name -contains "exit_code")) { [int]$jobResult.exit_code } else { 1 }

    Remove-Job $job -Force -ErrorAction SilentlyContinue | Out-Null
    $sw.Stop()

    if ($exitCode -eq 0) {
        Write-Host "PASS ($([math]::Round($sw.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Green
        Add-Result $Name "passed" 0 $sw.Elapsed.TotalSeconds $output ""
    } else {
        Write-Host "FAIL ($([math]::Round($sw.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Red
        Write-Host (Redact-SecretText $output)
        Add-Result $Name "failed" $exitCode $sw.Elapsed.TotalSeconds $output $output
    }
}

function Invoke-ScriptStep([string]$Name, [string[]]$Arguments, [int]$TimeoutSec) {
    Invoke-Step $Name $Root "powershell" (@("-NoProfile", "-ExecutionPolicy", "Bypass") + $Arguments) $TimeoutSec
}

function Add-Skipped([string]$Name, [string]$Reason) {
    Write-Host "`n==> $Name" -ForegroundColor DarkCyan
    Write-Host "SKIP: $Reason" -ForegroundColor Yellow
    Add-Result $Name "skipped" 0 0 "" $Reason
}

function Test-CommandAvailable([string]$Command) {
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Get-ResourceSnapshotText {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Top processes by working set:") | Out-Null
    Get-Process |
        Sort-Object WorkingSet64 -Descending |
        Select-Object -First 12 ProcessName, Id, CPU, @{Name="WorkingSetMB"; Expression={[math]::Round($_.WorkingSet64 / 1MB, 1)}} |
        Format-Table -AutoSize |
        Out-String |
        ForEach-Object { $lines.Add($_.TrimEnd()) | Out-Null }

    if (Test-CommandAvailable "docker") {
        $lines.Add("") | Out-Null
        $lines.Add("Docker stats:") | Out-Null
        try {
            $stats = & docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>&1 | Out-String
            $lines.Add($stats.TrimEnd()) | Out-Null
        } catch {
            $lines.Add("docker stats unavailable: $($_.Exception.Message)") | Out-Null
        }
    }

    if (Test-CommandAvailable "wsl") {
        $lines.Add("") | Out-Null
        $lines.Add("WSL status:") | Out-Null
        try {
            $wslStatus = & wsl --status 2>&1 | Out-String
            $lines.Add($wslStatus.TrimEnd()) | Out-Null
        } catch {
            $lines.Add("wsl status unavailable: $($_.Exception.Message)") | Out-Null
        }
    }
    return ($lines -join "`n")
}

function Add-ResourceSnapshot([string]$Name) {
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $snapshot = Get-ResourceSnapshotText
        $sw.Stop()
        Write-Host "PASS ($([math]::Round($sw.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Green
        Add-Result $Name "passed" 0 $sw.Elapsed.TotalSeconds $snapshot ""
    } catch {
        $sw.Stop()
        Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        Add-Result $Name "failed" 1 $sw.Elapsed.TotalSeconds "" ($_.Exception.Message)
    }
}

function Invoke-Preflight {
    Write-Host "`n==> preflight tools" -ForegroundColor Cyan
    $missing = New-Object System.Collections.Generic.List[string]
    if ((-not $SkipAudit -or -not $SkipFrontendBuild) -and -not (Test-CommandAvailable "npm.cmd")) {
        $missing.Add("npm.cmd") | Out-Null
    }
    if (-not $SkipBackendTests -and -not (Test-CommandAvailable "mvn.cmd")) {
        $missing.Add("mvn.cmd") | Out-Null
    }
    if (-not $SkipComposeConfig -and -not (Test-CommandAvailable "docker")) {
        $missing.Add("docker") | Out-Null
    }
    if (-not $SkipCrawlerTests) {
        $python = Join-Path $Root "crawler-service\.venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $python)) {
            $missing.Add($python) | Out-Null
        }
    }
    if (-not $SkipEnvCheck -and -not (Test-Path -LiteralPath (Join-Path $Root "scripts\release\check-deploy-env.ps1"))) {
        $missing.Add("scripts\release\check-deploy-env.ps1") | Out-Null
    }
    if ($RunSmoke -and -not $SkipSmoke -and -not (Test-Path -LiteralPath (Join-Path $Root "scripts\release\digest-smoke.ps1"))) {
        $missing.Add("scripts\release\digest-smoke.ps1") | Out-Null
    }

    if ($missing.Count -gt 0) {
        $msg = "Missing prerequisites: " + ($missing -join ", ")
        Write-Host "FAIL: $msg" -ForegroundColor Red
        Add-Result "preflight tools" "failed" 1 0 "" $msg
    } else {
        Write-Host "PASS" -ForegroundColor Green
        Add-Result "preflight tools" "passed" 0 0 "" ""
    }
}

function Escape-MarkdownCell([string]$Value) {
    if ($null -eq $Value) {
        return ""
    }
    return ($Value -replace "\|", "\|" -replace "`r?`n", "<br>")
}

function Write-MarkdownReport($Summary, [string]$Path) {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Release Gate Report") | Out-Null
    $lines.Add("") | Out-Null
    $lines.Add("- Status: $($Summary.status)") | Out-Null
    $lines.Add("- Started: $($Summary.started_at)") | Out-Null
    $lines.Add("- Finished: $($Summary.finished_at)") | Out-Null
    $lines.Add("- Duration: $($Summary.seconds)s") | Out-Null
    $lines.Add("- Passed: $($Summary.passed)") | Out-Null
    $lines.Add("- Failed: $($Summary.failed)") | Out-Null
    $lines.Add("- Skipped: $($Summary.skipped)") | Out-Null
    $lines.Add("") | Out-Null
    $lines.Add("| Step | Status | Seconds | Exit Code | Note |") | Out-Null
    $lines.Add("| --- | --- | ---: | ---: | --- |") | Out-Null
    foreach ($item in $Summary.results) {
        $note = if ($item.status -eq "failed") { $item.error } elseif ($item.status -eq "skipped") { $item.error } else { "" }
        if ($note.Length -gt 500) {
            $note = $note.Substring(0, 500) + "..."
        }
        $lines.Add("| $(Escape-MarkdownCell $item.name) | $($item.status) | $($item.seconds) | $($item.exit_code) | $(Escape-MarkdownCell $note) |") | Out-Null
    }

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $lines | Set-Content -LiteralPath $Path -Encoding UTF8
}

Invoke-Preflight
Add-ResourceSnapshot "resource snapshot before gate"

if (-not $SkipAudit) {
    Invoke-Step "frontend prod audit" (Join-Path $Root "frontend") "npm.cmd" @("audit", "--omit=dev", "--registry=https://registry.npmjs.org") 180
} else {
    Add-Skipped "frontend prod audit" "SkipAudit"
}

if (-not $SkipFrontendBuild) {
    Invoke-Step "frontend build" (Join-Path $Root "frontend") "npm.cmd" @("run", "build") 300
} else {
    Add-Skipped "frontend build" "SkipFrontendBuild"
}

if (-not $SkipCrawlerTests) {
    $python = Join-Path $Root "crawler-service\.venv\Scripts\python.exe"
    Invoke-Step "crawler tests" $Root $python @("-m", "pytest", "crawler-service\tests", "-q", "--tb=short") 600
} else {
    Add-Skipped "crawler tests" "SkipCrawlerTests"
}

if (-not $SkipBackendTests) {
    Invoke-Step "backend tests" (Join-Path $Root "backend") "mvn.cmd" @("test") 600
} else {
    Add-Skipped "backend tests" "SkipBackendTests"
}

if (-not $SkipComposeConfig) {
    Invoke-Step "deploy compose config" (Join-Path $Root "deploy") "docker" @("compose", "--env-file", ".env.example", "config") 120
} else {
    Add-Skipped "deploy compose config" "SkipComposeConfig"
}

if (Test-Path -LiteralPath (Join-Path $Root "scripts\release\digest-smoke.ps1")) {
    Invoke-ScriptStep "digest smoke self-test" @("-File", "scripts\release\digest-smoke.ps1", "-SelfTest") 60
} else {
    Add-Skipped "digest smoke self-test" "scripts\release\digest-smoke.ps1 not found"
}

if (-not $SkipEnvCheck) {
    Invoke-ScriptStep "deploy env check" @("-File", "scripts\release\check-deploy-env.ps1", "-EnvPath", $EnvPath) 60
} else {
    Add-Skipped "deploy env check" "SkipEnvCheck"
}

$shouldRunSmoke = $RunSmoke -and (-not $SkipSmoke)
if ($shouldRunSmoke) {
    $smokeArgs = @(
        "-File", "scripts\release\digest-smoke.ps1",
        "-CrawlerUrl", $CrawlerUrl,
        "-BackendUrl", $BackendUrl,
        "-CrawlerApiKey", $CrawlerApiKey,
        "-TimeoutMinutes", "$TimeoutMinutes"
    )
    if ($TriggerDigest) { $smokeArgs += "-Trigger" }
    if ($ForceDigest) { $smokeArgs += "-Force" }
    Invoke-ScriptStep "digest smoke" $smokeArgs ([Math]::Max(120, ($TimeoutMinutes + 2) * 60))
} else {
    Add-Skipped "digest smoke" "Pass -RunSmoke to enable; add -TriggerDigest -ForceDigest for real generation"
}

Add-ResourceSnapshot "resource snapshot after gate"

$FinishedAt = Get-Date
$failed = @($Results | Where-Object { $_.status -eq "failed" })
$passed = @($Results | Where-Object { $_.status -eq "passed" })
$skipped = @($Results | Where-Object { $_.status -eq "skipped" })
$summary = [pscustomobject]@{
    started_at = $StartedAt.ToString("o")
    finished_at = $FinishedAt.ToString("o")
    seconds = [math]::Round(($FinishedAt - $StartedAt).TotalSeconds, 2)
    status = if ($failed.Count -eq 0) { "passed" } else { "failed" }
    passed = $passed.Count
    failed = $failed.Count
    skipped = $skipped.Count
    results = $Results
}

$reportDir = Split-Path -Parent $ReportPath
if (-not (Test-Path -LiteralPath $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
Write-MarkdownReport $summary $MarkdownReportPath

Write-Host "`nRelease gate report: $ReportPath" -ForegroundColor Cyan
Write-Host "Markdown report: $MarkdownReportPath" -ForegroundColor Cyan
Write-Host "Summary: passed=$($passed.Count), failed=$($failed.Count), skipped=$($skipped.Count)" -ForegroundColor Cyan
if ($failed.Count -gt 0) {
    Write-Host "Failed steps:" -ForegroundColor Red
    foreach ($item in $failed) {
        Write-Host "- $($item.name)" -ForegroundColor Red
    }
    exit 1
}

exit 0
