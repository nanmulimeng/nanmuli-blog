@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 重启服务脚本（保留数据）
:: ============================================

echo [Restarting Services]
echo.

cd /d "%~dp0"

:: 检查 docker compose 命令
docker compose version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set COMPOSE_CMD=docker compose
) else (
    set COMPOSE_CMD=docker-compose
)

echo Stopping containers...
%COMPOSE_CMD% stop

echo.
echo Starting containers...
%COMPOSE_CMD% start

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Failed to restart services!
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
echo [OK] Services restarted successfully!
pause
