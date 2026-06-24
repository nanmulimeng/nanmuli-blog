param(
    [string]$EnvPath = "deploy/.env"
)

$ErrorActionPreference = "Stop"

$RequiredKeys = @(
    "DB_PASSWORD",
    "REDIS_PASSWORD",
    "AI_ENABLED",
    "DIGEST_ENABLED",
    "AI_API_KEY",
    "CRAWLER_API_KEY",
    "CRAWLER_CALLBACK_API_KEY",
    "BLOG_SECURITY_ENCRYPTION_KEY",
    "COOKIE_SECURE",
    "CORS_ALLOWED_ORIGINS"
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
    # X04-02: 收紧占位符正则，覆盖 your_secure_* / your_shared_* / your_16_plus_* 等 .env.example 模板默认值
    if ($Env[$Key] -match "^(your_|sk-your-|nanmuli-blog-key|local-dev-encryption-key)") {
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
# X04-05: 生产安全校验补充
if ($envValues["COOKIE_SECURE"].ToLowerInvariant() -ne "true") {
    throw "COOKIE_SECURE must be true in production (Sa-Token Cookie 安全属性)."
}
$cors = $envValues["CORS_ALLOWED_ORIGINS"]
if ([string]::IsNullOrWhiteSpace($cors) -or $cors -eq "*" -or $cors.StartsWith("http://localhost") -or $cors.StartsWith("http://127.0.0.1")) {
    throw "CORS_ALLOWED_ORIGINS must be set to real production origins (not '*', not localhost)."
}
if ($envValues["REDIS_PASSWORD"].Length -lt 8) {
    throw "REDIS_PASSWORD must be at least 8 characters (X01-08 redis 现已强制鉴权)."
}

Write-Host "Deploy env check OK: required digest release values are configured." -ForegroundColor Green
