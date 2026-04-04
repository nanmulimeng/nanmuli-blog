@echo off
:: ============================================
:: 数据库初始化脚本
:: 删除旧数据并重新初始化
:: ============================================

echo [Database Initialization]
echo.

cd /d "%~dp0"

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
