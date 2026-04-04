@echo off
:: ============================================
:: 数据库初始化脚本
:: 注意：此脚本会重置数据库数据，请谨慎使用！
:: ============================================

echo [Database Initialization]
echo ============================================
echo WARNING: This will RESET all database data!
echo ============================================
echo.

:: 确认提示
set /p confirm="Are you sure? Type 'yes' to continue: "
if /I not "%confirm%"=="yes" (
    echo Cancelled.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo.
echo Stopping existing containers...
docker-compose down >nul 2>&1

echo Removing old data volumes...
docker volume rm deploy_postgres_data >nul 2>&1
docker volume rm deploy_redis_data >nul 2>&1

echo Starting fresh containers...
docker-compose up -d >nul 2>&1

echo Waiting for PostgreSQL to initialize...
timeout /t 10 /nobreak >nul

echo.
echo [OK] Database initialized successfully!
echo.
echo PostgreSQL: localhost:5433
echo Redis:      localhost:6380
pause
