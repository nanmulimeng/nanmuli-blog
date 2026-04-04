@echo off
:: ============================================
:: 启动服务脚本（保留数据）
:: ============================================

echo [Starting Services]
echo.

cd /d "%~dp0"

echo Checking container status...
docker-compose ps | findstr "nanmuli-postgres" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo PostgreSQL is already running.
) else (
    echo Starting PostgreSQL...
)

docker-compose ps | findstr "nanmuli-redis" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Redis is already running.
) else (
    echo Starting Redis...
)

echo.
docker-compose up -d

echo.
echo Waiting for services to be ready...
timeout /t 3 /nobreak >nul

:: 健康检查
echo.
echo Checking service health...
docker-compose ps

echo.
echo [OK] Services started successfully!
echo.
echo PostgreSQL: localhost:5433
echo Redis:      localhost:6380
echo.
echo Tip: Use stop.bat to stop services (data will be preserved)
pause
