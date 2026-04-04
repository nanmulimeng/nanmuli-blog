@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 启动Docker数据库服务（PostgreSQL + Redis）
:: ============================================

echo [Starting Docker Database Services]
echo.

cd /d "%~dp0"

:: 检查 docker compose 命令
docker compose version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set COMPOSE_CMD=docker compose
) else (
    set COMPOSE_CMD=docker-compose
)

:: 检查容器状态
%COMPOSE_CMD% ps | findstr "nanmuli-postgres" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [Info] PostgreSQL container already running.
) else (
    echo [Info] Starting PostgreSQL container...
)

%COMPOSE_CMD% ps | findstr "nanmuli-redis" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [Info] Redis container already running.
) else (
    echo [Info] Starting Redis container...
)

echo.
%COMPOSE_CMD% up -d

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Failed to start services!
    echo Please check if Docker is running.
    pause
    exit /b 1
)

echo.
echo Waiting for services to be ready...
timeout /t 3 /nobreak >nul

echo.
%COMPOSE_CMD% ps

echo.
echo ============================================
echo [OK] Database services started!
echo ============================================
echo.
echo PostgreSQL: localhost:5433
echo Redis:      localhost:6380
echo.
pause
