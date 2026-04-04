@echo off
:: ============================================
:: 重启服务脚本（保留数据）
:: ============================================

echo [Restarting Services]
echo.

cd /d "%~dp0"

echo Stopping containers...
docker-compose stop

echo.
echo Starting containers...
docker-compose start

echo.
echo Waiting for services to be ready...
timeout /t 3 /nobreak >nul

echo.
docker-compose ps

echo.
echo [OK] Services restarted successfully!
pause
