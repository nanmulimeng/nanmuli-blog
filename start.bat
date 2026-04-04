@echo off
setlocal EnableDelayedExpansion

:: ============================================
:: Nanmuli Blog - One-click Startup Script
:: ============================================

title Nanmuli Blog Dev Environment

:: Project root directory
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

cls
echo.
echo ============================================
echo    Nanmuli Blog Development Startup
echo ============================================
echo.

:: Check Java
echo [1/5] Checking Java...
java -version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Java not found. Please install Java 21.
    pause
    exit /b 1
)
echo [OK] Java found

:: Check Maven
echo [2/5] Checking Maven...
where mvn >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Maven not found. Please install Maven 3.9+
    pause
    exit /b 1
)
echo [OK] Maven found

:: Check Node.js
echo [3/5] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Node.js found

:: Check npm dependencies
echo [4/5] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo Installing npm packages, please wait...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [FAIL] npm install failed
        pause
        exit /b 1
    )
    cd ..
)
echo [OK] Dependencies ready

:: Check Docker
echo [5/5] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)
echo [OK] Docker is running

echo.
echo ============================================
echo    Starting Services...
echo ============================================
echo.

:: Start Docker
echo Starting PostgreSQL and Redis...
cd deploy
call docker-compose up -d >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Failed to start Docker containers
    pause
    exit /b 1
)
echo [OK] Database containers started
cd ..

timeout /t 3 /nobreak >nul

:: Start Backend
echo Starting Backend (Spring Boot)...
if not exist "backend\target\blog-backend-1.0.0.jar" (
    echo Building backend project...
    cd backend
    call mvn clean package -DskipTests -q
    if errorlevel 1 (
        echo [FAIL] Maven build failed
        pause
        exit /b 1
    )
    cd ..
)

start "Backend" cmd /k "cd /d %PROJECT_ROOT%\backend && java -jar target\blog-backend-1.0.0.jar --spring.profiles.active=dev"
echo [OK] Backend started

:: Wait for backend to initialize
timeout /t 5 /nobreak >nul

:: Start Frontend
echo Starting Frontend (Vite)...
cd frontend
start "Frontend" cmd /k "cd /d %PROJECT_ROOT%\frontend && npm run dev"
cd ..
echo [OK] Frontend started

timeout /t 2 /nobreak >nul

:: Show final info
echo.
echo ============================================
echo    All Services Started!
echo ============================================
echo.
echo   Frontend:  http://localhost:3001
echo   Backend:   http://localhost:8081
echo   API Docs:  http://localhost:8081/doc.html
echo.
echo   Database:
echo     PostgreSQL: localhost:5433
echo     Redis:      localhost:6380
echo.
echo ============================================
echo.

:: Wait for user input before exiting main window
echo Press any key to STOP all services and exit...
pause >nul

:: Stop services
echo.
echo Stopping services...
taskkill /F /IM java.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

:: Ask about Docker
echo.
set /p stop_docker="Stop Docker containers? (y/n): "
if /i "%stop_docker%"=="y" (
    cd deploy
    call docker-compose down >nul 2>&1
    cd ..
    echo Docker containers stopped
)

echo.
echo All services stopped.
pause
