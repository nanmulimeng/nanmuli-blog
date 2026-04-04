@echo off
:: ============================================
:: 停止服务脚本（保留数据）
:: ============================================

echo [Stopping Services]
echo.

cd /d "%~dp0"

echo Stopping containers (data will be preserved)...
docker-compose stop

echo.
echo [OK] Services stopped successfully!
echo.
echo Your data is safe in Docker volumes.
echo Use start.bat to restart services.
pause
