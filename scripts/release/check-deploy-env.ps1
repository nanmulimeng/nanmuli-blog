param(
    [string]$EnvPath = "deploy/.env"
)

$ErrorActionPreference = "Stop"

$RequiredKeys = @(
    "AI_ENABLED",
    "DIGEST_ENABLED",
    "AI_API_KEY",
    "CRAWLER_API_KEY",
    "CRAWLER_CALLBACK_API_KEY",
    "BLOG_SECURITY_ENCRYPTION_KEY"
)

function Read-EnvFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Env file not found: $Path"
    }
    $result = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $name, $value = $trimmed.Split("=", 2)
        $result[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $result
}

function Assert-Configured([hashtable]$Env, [string]$Key) {
    if (-not $Env.ContainsKey($Key) -or [string]::IsNullOrWhiteSpace($Env[$Key])) {
        throw "$Key is required in deploy env."
    }
    if ($Env[$Key] -match "^(your_|sk-your-|nanmuli-blog-key$)") {
        throw "$Key still looks like a placeholder/default value."
    }
}

$envValues = Read-EnvFile $EnvPath
foreach ($key in $RequiredKeys) {
    Assert-Configured $envValues $key
}

if ($envValues["AI_ENABLED"].ToLowerInvariant() -ne "true") {
    throw "AI_ENABLED must be true for digest release validation."
}
if ($envValues["DIGEST_ENABLED"].ToLowerInvariant() -ne "true") {
    throw "DIGEST_ENABLED must be true for scheduled digest release."
}
if ($envValues["BLOG_SECURITY_ENCRYPTION_KEY"].Length -lt 16) {
    throw "BLOG_SECURITY_ENCRYPTION_KEY must be at least 16 characters."
}

Write-Host "Deploy env check OK: required digest release values are configured." -ForegroundColor Green
