@echo off
chcp 65001 >nul 2>&1

:: ============================================
:: Restart Dev Servers
:: ============================================

echo [Restarting Development Servers]
echo.

cd /d "%~dp0"

echo Step 1: Stopping services...
call "%~dp0stop.bat"

echo.
echo Step 2: Waiting...
timeout /t 3 /nobreak >nul

echo.
echo Step 3: Starting services...
call "%~dp0start.bat" --no-pause --rebuild

echo.
echo [OK] Restart completed!
echo.
pause
