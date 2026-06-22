param(
    [string]$CrawlerUrl = "http://localhost:8500",
    [string]$BackendUrl = "http://localhost:8081",
    [string]$CrawlerApiKey = $env:CRAWLER_API_KEY,
    [switch]$Trigger,
    [switch]$Force,
    [switch]$SelfTest,
    [int]$TimeoutMinutes = 30
)

$ErrorActionPreference = "Stop"
$CoreSections = @("hot_trend", "open_source", "dev_tool", "tech_article", "paper")
$CompletedStatus = 3
$FailedStatus = 4

function Join-Url([string]$Base, [string]$Path) {
    return $Base.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Unwrap-ApiResult($Body, [string]$Url) {
    if ($null -eq $Body) {
        throw "Empty response from $Url"
    }

    $hasCode = $Body.PSObject.Properties.Name -contains "code"
    $hasData = $Body.PSObject.Properties.Name -contains "data"
    if ($hasCode -and $hasData) {
        if ([int]$Body.code -ne 200) {
            $message = if ($Body.message) { $Body.message } else { "API returned code $($Body.code)" }
            throw "$Url failed: $message"
        }
        return $Body.data
    }

    return $Body
}

function Invoke-Json([string]$Method, [string]$Url, [hashtable]$Headers = @{}, [int]$TimeoutSec = 30) {
    Write-Host "[$Method] $Url"
    $body = Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -TimeoutSec $TimeoutSec
    return Unwrap-ApiResult $body $Url
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Get-Field($Object, [string]$Name) {
    if ($null -eq $Object) {
        return $null
    }
    if ($Object.PSObject.Properties.Name -contains $Name) {
        return $Object.$Name
    }
    return $null
}

function As-Array($Value) {
    if ($null -eq $Value) {
        return @()
    }
    return @($Value)
}

function Get-ObjectProperties($Object) {
    if ($null -eq $Object) {
        return @()
    }
    return @($Object.PSObject.Properties)
}

function Validate-OptimizationSafety($Digest, [string]$Source) {
    $quality = Get-Field $Digest "quality_evaluation"
    $actions = Get-Field $quality "next_run_actions"
    if ($null -eq $actions) {
        return
    }

    $confidence = [string](Get-Field $actions "confidence")
    if ([string]::IsNullOrWhiteSpace($confidence) -or $confidence -eq "none") {
        return
    }

    $safety = Get-Field $actions "safety"
    Assert-True ($null -ne $safety) "$Source next_run_actions has no safety metadata"

    $sourceIds = Get-Field $actions "source_ids"
    $sourceUrls = Get-Field $actions "source_urls"
    $skipIds = As-Array (Get-Field $sourceIds "skip")
    $skipUrls = As-Array (Get-Field $sourceUrls "skip")
    $sources = Get-Field $actions "sources"

    if ($confidence -eq "low") {
        Assert-True ($skipIds.Count -eq 0) "$Source low-confidence next_run_actions still has source_id skip actions"
        Assert-True ($skipUrls.Count -eq 0) "$Source low-confidence next_run_actions still has source_url skip actions"
        foreach ($prop in Get-ObjectProperties $sources) {
            $src = $prop.Value
            Assert-True ((Get-Field $src "action") -ne "skip") "$Source low-confidence source $($prop.Name) still has action=skip"
        }
    }

    $sectionCounts = Get-Field $safety "section_source_counts"
    if ($null -ne $sectionCounts -and $null -ne $sources) {
        $skipBySection = @{}
        foreach ($prop in Get-ObjectProperties $sources) {
            $src = $prop.Value
            if ((Get-Field $src "action") -ne "skip") {
                continue
            }
            $section = [string](Get-Field $src "section")
            if (-not $skipBySection.ContainsKey($section)) {
                $skipBySection[$section] = 0
            }
            $skipBySection[$section] += 1
        }

        foreach ($prop in Get-ObjectProperties $sectionCounts) {
            $section = [string]$prop.Name
            $sourceCount = [int]$prop.Value
            $maxSkip = [Math]::Floor($sourceCount / 2)
            if ($sourceCount -le 1) {
                $maxSkip = 0
            }
            $actualSkip = if ($skipBySection.ContainsKey($section)) { [int]$skipBySection[$section] } else { 0 }
            Assert-True ($actualSkip -le $maxSkip) "$Source next_run_actions skips $actualSkip/$sourceCount sources in section $section"
        }
    }

    Write-Host "$Source optimization safety OK: confidence=$confidence" -ForegroundColor Green
}

function Get-Items($Sections) {
    $items = @()
    foreach ($section in @($Sections)) {
        foreach ($item in @($section.items)) {
            $items += $item
        }
    }
    return $items
}

function Print-Diagnostics($Digest) {
    if ($Digest.error_message) {
        Write-Host "error_message:" -ForegroundColor Yellow
        Write-Host $Digest.error_message
    }
    if ($Digest.quality_evaluation) {
        Write-Host "quality_evaluation:" -ForegroundColor Yellow
        $Digest.quality_evaluation | ConvertTo-Json -Depth 12
    }
    $plan = $Digest.orchestrator_plan
    if ($plan -and $plan.search_diagnostics) {
        Write-Host "search_diagnostics:" -ForegroundColor Yellow
        $plan.search_diagnostics | ConvertTo-Json -Depth 12
    }
    if ($plan -and $plan.event_diagnostics) {
        Write-Host "event_diagnostics:" -ForegroundColor Yellow
        $plan.event_diagnostics | ConvertTo-Json -Depth 12
    }
}

function Validate-Digest($Digest, [string]$Source) {
    Assert-True ($null -ne $Digest) "$Source returned empty digest"
    Assert-True ([string]::IsNullOrWhiteSpace($Digest.ai_title) -eq $false) "$Source digest has no ai_title"
    Assert-True ([string]::IsNullOrWhiteSpace($Digest.ai_full_content) -eq $false) "$Source digest has no ai_full_content"

    $sections = @($Digest.sections)
    Assert-True ($sections.Count -gt 0) "$Source digest has no structured sections"
    $items = Get-Items $sections
    Assert-True ($items.Count -gt 0) "$Source digest has no structured items"

    $coveredCore = @{}
    foreach ($section in $sections) {
        if ($CoreSections -contains $section.category -and @($section.items).Count -gt 0) {
            $coveredCore[$section.category] = $true
        }
    }
    Assert-True ($coveredCore.Count -ge 3) "$Source digest covers only $($coveredCore.Count) core sections"

    if ($Digest.quality_evaluation -and $Digest.quality_evaluation.publishable -eq $false) {
        throw "$Source digest is explicitly not publishable"
    }
    Validate-OptimizationSafety $Digest $Source
    Write-Host "$Source digest OK: sections=$($sections.Count), items=$($items.Count), core=$($coveredCore.Count)" -ForegroundColor Green
}

function Assert-DigestMatches($Expected, $Actual, [string]$Source) {
    $expectedId = Get-Field $Expected "id"
    $actualId = Get-Field $Actual "id"
    if ($null -ne $expectedId -and $null -ne $actualId) {
        Assert-True ("$expectedId" -eq "$actualId") "$Source digest id $actualId does not match triggered task id $expectedId"
        Validate-Digest $Actual $Source
        return
    }

    $expectedDate = Get-Field $Expected "digest_date"
    $actualDate = Get-Field $Actual "digest_date"
    if (-not [string]::IsNullOrWhiteSpace($expectedDate) -and -not [string]::IsNullOrWhiteSpace($actualDate)) {
        Assert-True ("$expectedDate" -eq "$actualDate") "$Source digest date $actualDate does not match triggered digest date $expectedDate"
        Validate-Digest $Actual $Source
        return
    }

    throw "$Source digest cannot be matched against triggered digest: missing both id and digest_date"
}

function Get-OptionalDigest([string]$Url, [hashtable]$Headers, [string]$Name) {
    try {
        return Invoke-Json "GET" $Url $Headers 30
    } catch {
        Write-Host "$Name not available yet: $($_.Exception.Message)" -ForegroundColor Yellow
        return $null
    }
}

function Validate-RuntimeHealth($RuntimeHealth, [bool]$RequireReady) {
    if ($null -eq $RuntimeHealth) {
        if ($RequireReady) {
            throw "Digest runtime health endpoint returned empty response"
        }
        return
    }

    $summary = Get-Field $RuntimeHealth "summary"
    $optimizationSafety = Get-Field $RuntimeHealth "optimization_safety"
    $searchFeedback = Get-Field $RuntimeHealth "search_feedback"
    $blocking = [bool](Get-Field $summary "blocking")
    $status = Get-Field $RuntimeHealth "status"
    $safetyStatus = Get-Field $optimizationSafety "status"
    $keepRate = Get-Field $searchFeedback "latest_keep_rate"

    Write-Host "Digest runtime health: status=$status, blocking=$blocking, optimization_safety=$safetyStatus, keep_rate=$keepRate"

    if ($RequireReady) {
        Assert-True (-not $blocking) "Digest runtime health has blocking checks"
        Assert-True ($status -ne "danger") "Digest runtime health status is danger"
    }
    Assert-True ($safetyStatus -ne "danger") "Digest optimization safety status is danger"
}

function Invoke-SelfTest {
    $goodLowConfidence = [pscustomobject]@{
        quality_evaluation = [pscustomobject]@{
            next_run_actions = [pscustomobject]@{
                confidence = "low"
                source_ids = [pscustomobject]@{ skip = @(); deprioritize = @(1) }
                source_urls = [pscustomobject]@{ skip = @(); deprioritize = @() }
                sources = [pscustomobject]@{
                    "1" = [pscustomobject]@{ action = "deprioritize"; section = "hot_trend" }
                }
                safety = [pscustomobject]@{
                    applied = @("low-confidence-skip-downgrade")
                    section_source_counts = [pscustomobject]@{ hot_trend = 1 }
                }
            }
        }
    }
    Validate-OptimizationSafety $goodLowConfidence "selftest good-low-confidence"

    $badLowConfidence = [pscustomobject]@{
        quality_evaluation = [pscustomobject]@{
            next_run_actions = [pscustomobject]@{
                confidence = "low"
                source_ids = [pscustomobject]@{ skip = @(1); deprioritize = @() }
                source_urls = [pscustomobject]@{ skip = @(); deprioritize = @() }
                sources = [pscustomobject]@{
                    "1" = [pscustomobject]@{ action = "skip"; section = "hot_trend" }
                }
                safety = [pscustomobject]@{
                    applied = @()
                    section_source_counts = [pscustomobject]@{ hot_trend = 1 }
                }
            }
        }
    }
    $failedAsExpected = $false
    try {
        Validate-OptimizationSafety $badLowConfidence "selftest bad-low-confidence"
    } catch {
        $failedAsExpected = $true
    }
    Assert-True $failedAsExpected "selftest bad-low-confidence should fail"

    $badSectionCap = [pscustomobject]@{
        quality_evaluation = [pscustomobject]@{
            next_run_actions = [pscustomobject]@{
                confidence = "medium"
                source_ids = [pscustomobject]@{ skip = @(1, 2, 3); deprioritize = @() }
                source_urls = [pscustomobject]@{ skip = @(); deprioritize = @() }
                sources = [pscustomobject]@{
                    "1" = [pscustomobject]@{ action = "skip"; section = "dev_tool" }
                    "2" = [pscustomobject]@{ action = "skip"; section = "dev_tool" }
                    "3" = [pscustomobject]@{ action = "skip"; section = "dev_tool" }
                    "4" = [pscustomobject]@{ action = "deprioritize"; section = "dev_tool" }
                }
                safety = [pscustomobject]@{
                    applied = @()
                    section_source_counts = [pscustomobject]@{ dev_tool = 4 }
                }
            }
        }
    }
    $failedCapAsExpected = $false
    try {
        Validate-OptimizationSafety $badSectionCap "selftest bad-section-cap"
    } catch {
        $failedCapAsExpected = $true
    }
    Assert-True $failedCapAsExpected "selftest bad-section-cap should fail"

    Write-Host "Digest smoke self-test completed successfully." -ForegroundColor Green
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

if ([string]::IsNullOrWhiteSpace($CrawlerApiKey)) {
    throw "CrawlerApiKey is required. Pass -CrawlerApiKey or set CRAWLER_API_KEY."
}

$headers = @{ "X-API-Key" = $CrawlerApiKey }

Write-Host "Checking crawler health..." -ForegroundColor Cyan
$health = Invoke-Json "GET" (Join-Url $CrawlerUrl "/health")
Assert-True ($health.status -eq "healthy") "Crawler health status is $($health.status)"
if ($health.components.ai -and $health.components.ai.available -ne $true) {
    if ($Trigger) {
        throw "Crawler AI component is not available in /health; cannot run trigger smoke."
    }
    Write-Host "Warning: crawler AI component is not available in /health." -ForegroundColor Yellow
}

Write-Host "Checking digest config and scheduler..." -ForegroundColor Cyan
$sections = Invoke-Json "GET" (Join-Url $CrawlerUrl "/api/v1/digests/config/sections") $headers
Assert-True (@($sections.sections).Count -gt 0) "Digest section config is empty"
$scheduler = Invoke-Json "GET" (Join-Url $CrawlerUrl "/api/v1/digests/scheduler/status") $headers
Write-Host "Scheduler running=$($scheduler.running), enabled=$($scheduler.enabled), ai_configured=$($scheduler.ai_configured)"
if ($Trigger -and $scheduler.ai_configured -eq $false) {
    throw "Scheduler reports ai_configured=false; cannot run trigger smoke."
}

$runtimeHealth = Invoke-Json "GET" (Join-Url $CrawlerUrl "/api/v1/digests/runtime/health") $headers
Validate-RuntimeHealth $runtimeHealth ([bool]$Trigger)

$digest = $null
if ($Trigger) {
    $forceValue = if ($Force) { "true" } else { "false" }
    $triggerUrl = Join-Url $CrawlerUrl "/api/v1/digests/trigger?force=$forceValue"
    $triggerResult = Invoke-Json "POST" $triggerUrl $headers 60
    Assert-True ($triggerResult.task_id -gt 0) "Digest trigger did not return task_id: $($triggerResult | ConvertTo-Json -Depth 6)"
    $taskId = [int]$triggerResult.task_id
    Write-Host "Digest task created: $taskId" -ForegroundColor Cyan

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    do {
        Start-Sleep -Seconds 10
        $digest = Invoke-Json "GET" (Join-Url $CrawlerUrl "/api/v1/digests/task/$taskId") $headers 30
        Write-Host "Task status=$($digest.status), title=$($digest.ai_title)"
        if ($digest.status -eq $CompletedStatus) { break }
        if ($digest.status -eq $FailedStatus) {
            Print-Diagnostics $digest
            throw "Digest task $taskId failed"
        }
    } while ((Get-Date) -lt $deadline)

    Assert-True ($digest.status -eq $CompletedStatus) "Digest task $taskId did not complete within $TimeoutMinutes minutes"
    Validate-Digest $digest "Crawler task"
} else {
    $digest = Get-OptionalDigest (Join-Url $CrawlerUrl "/api/v1/digests/latest") $headers "Crawler latest digest"
    if ($digest) {
        Validate-Digest $digest "Crawler latest"
    }
}

if (-not [string]::IsNullOrWhiteSpace($BackendUrl)) {
    $publicUrl = Join-Url $BackendUrl "/api/digest/latest"
    $public = if ($Trigger) {
        Invoke-Json "GET" $publicUrl @{} 30
    } else {
        Get-OptionalDigest $publicUrl @{} "Backend public latest digest"
    }
    if ($public) {
        if ($Trigger -and $digest) {
            Assert-DigestMatches $digest $public "Backend public latest"
        } else {
            Validate-Digest $public "Backend public latest"
        }
    }
}

Write-Host "Digest smoke completed successfully." -ForegroundColor Green
