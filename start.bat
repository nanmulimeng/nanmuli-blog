@echo off
chcp 65001 >nul 2>&1

:: ============================================
:: Start Dev Servers
:: ============================================

set NO_PAUSE=0
set REBUILD=0
if "%1"=="--no-pause" set NO_PAUSE=1
if "%1"=="--rebuild" set REBUILD=1
if "%2"=="--rebuild" set REBUILD=1

echo [Starting Development Servers]
echo.

cd /d "%~dp0"

:: Check and start Backend
netstat -ano | findstr ":8081 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [Backend] Port 8081 already in use
) else (
    echo [Backend] Starting Spring Boot on port 8081...
    if %REBUILD% EQU 1 (
        echo [Backend] Rebuilding and starting Spring Boot on port 8081...
        start "Backend" cmd /k "chcp 65001 >nul && cd /d "%~dp0backend" && mvn clean spring-boot:run"
    ) else (
        echo [Backend] Starting Spring Boot on port 8081...
        start "Backend" cmd /k "chcp 65001 >nul && cd /d "%~dp0backend" && mvn spring-boot:run"
    )
)

:: Check and start Frontend
netstat -ano | findstr ":3001 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [Frontend] Port 3001 already in use
) else (
    echo [Frontend] Starting Vue dev server on port 3001...
    start "Frontend" cmd /k "chcp 65001 >nul && cd /d "%~dp0frontend" && npm run dev"
)

echo.
echo ============================================
echo [OK] Servers starting!
echo ============================================
echo Frontend: http://localhost:3001
echo Backend:  http://localhost:8081
echo.

if %NO_PAUSE% EQU 0 pause
