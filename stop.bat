@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================
:: Stop Dev Servers
:: ============================================

echo [Stopping Development Servers]
echo.

:: Stop Backend (port 8081)
echo [Backend] Checking port 8081...
set BACKEND_PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081 " ^| findstr "LISTENING"') do (
    set BACKEND_PID=%%a
)
if not "!BACKEND_PID!"=="" (
    echo [Backend] Stopping PID !BACKEND_PID!...
    taskkill /PID !BACKEND_PID! /F >nul 2>&1
    echo [Backend] Stopped
) else (
    echo [Backend] Not running
)

timeout /t 2 /nobreak >nul

:: Stop Frontend (port 3001)
echo [Frontend] Checking port 3001...
set FRONTEND_PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001 " ^| findstr "LISTENING"') do (
    set FRONTEND_PID=%%a
)
if not "!FRONTEND_PID!"=="" (
    echo [Frontend] Stopping PID !FRONTEND_PID!...
    taskkill /PID !FRONTEND_PID! /F >nul 2>&1
    echo [Frontend] Stopped
) else (
    echo [Frontend] Not running
)

timeout /t 2 /nobreak >nul

echo.
echo [OK] All servers stopped!
echo.
