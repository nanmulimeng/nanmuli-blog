@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 启动前后端开发服务
:: ============================================

echo [Starting Development Servers]
echo.

cd /d "%~dp0"

:: 检查后端端口占用
netstat -ano | findstr ":8081" | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [Warning] Port 8081 is already in use. Backend may already be running.
) else (
    echo [Backend] Starting Spring Boot on port 8081...
    start "Backend" cmd /k "cd /d %~dp0backend && mvn spring-boot:run"
)

:: 检查前端端口占用
netstat -ano | findstr ":3001" | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [Warning] Port 3001 is already in use. Frontend may already be running.
) else (
    echo [Frontend] Starting Vue dev server on port 3001...
    start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
)

echo.
echo ============================================
echo [OK] Development servers starting!
echo ============================================
echo.
echo Frontend: http://localhost:3001
echo Backend:  http://localhost:8081
echo API Docs: http://localhost:8081/doc.html
echo.
echo Tip: Use stop.bat to stop all services
echo.
pause
