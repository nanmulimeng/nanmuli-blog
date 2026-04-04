@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 启动服务脚本（保留数据）
:: ============================================

echo [Starting Services]
echo.

cd /d "%~dp0"

:: 检查 docker compose 命令
docker compose version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set COMPOSE_CMD=docker compose
) else (
    set COMPOSE_CMD=docker-compose
)

echo Checking container status...
%COMPOSE_CMD% ps 2>nul | findstr "nanmuli-postgres" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo PostgreSQL is already running.
) else (
    echo Starting PostgreSQL...
)

%COMPOSE_CMD% ps 2>nul | findstr "nanmuli-redis" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Redis is already running.
) else (
    echo Starting Redis...
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

:: 健康检查
echo.
echo Checking service health...
%COMPOSE_CMD% ps

echo.
echo [OK] Services started successfully!
echo.
echo PostgreSQL: localhost:5433
echo Redis:      localhost:6380
echo.
echo Tip: Use stop.bat to stop services (data will be preserved)
pause
