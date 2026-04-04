@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 重启前后端开发服务
:: ============================================

echo [Restarting Development Servers]
echo.

cd /d "%~dp0"

echo Step 1: Stopping services...
call "%~dp0stop.bat"

echo.
echo Step 2: Waiting for cleanup...
timeout /t 2 /nobreak >nul

echo.
echo Step 3: Starting services...
start.bat
