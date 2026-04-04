@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 停止服务脚本（保留数据）
:: ============================================

echo [Stopping Services]
echo.

cd /d "%~dp0"

:: 检查 docker compose 命令
docker compose version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set COMPOSE_CMD=docker compose
) else (
    set COMPOSE_CMD=docker-compose
)

echo Stopping containers (data will be preserved)...
%COMPOSE_CMD% stop

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Warning] Some containers may not be running.
)

echo.
echo [OK] Services stopped successfully!
echo.
echo Your data is safe in Docker volumes.
echo Use start.bat to restart services.
pause
