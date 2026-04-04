@echo off
chcp 936 >nul 2>&1
:: ============================================
:: 停止前后端开发服务
:: ============================================

echo [Stopping Development Servers]
echo.

:: 查找并停止占用8081端口的Java进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081" ^| findstr "LISTENING"') do (
    echo [Backend] Stopping process %%a...
    taskkill /PID %%a /F >nul 2>&1
)

:: 查找并停止占用3001端口的Node进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do (
    echo [Frontend] Stopping process %%a...
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo [OK] All development servers stopped!
echo.
pause
