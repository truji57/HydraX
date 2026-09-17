@echo off
cd /d "%~dp0"

echo ============================
echo    HydraX-NT - Actualizacion
echo ============================
echo.

echo [1/3] Deteniendo servicios activos...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8006 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
timeout /t 4 /nobreak >nul
echo       Listo.
echo.

echo [2/3] Buscando actualizaciones...
git remote set-url origin https://github.com/truji57/HydraX-NT.git
del /f /q ".git\index.lock" 2>nul
for /f "delims=" %%h in ('git rev-parse HEAD') do set LOCAL=%%h
echo n | git fetch origin
for /f "delims=" %%h in ('git rev-parse origin/master') do set REMOTE=%%h

if "%LOCAL%"=="%REMOTE%" (
    echo       Ya esta actualizado.
    echo.
    echo ============================
    echo    Sin cambios
    echo ============================
    echo.
    pause
    exit /b 0
)

echo       Nueva version detectada. Actualizando...
git reset --hard origin/master
echo       Listo.
echo.

echo [3/3] Reconstruyendo frontend...
cd /d "%~dp0frontend"
call npx vite build --logLevel error
if %errorlevel% neq 0 (
    echo       ERROR: Fallo al construir el frontend.
    pause
    exit /b 1
)
echo       Listo.
echo.

echo ============================
echo    Actualizacion completada
echo ============================
echo.

set /p START="Deseas iniciar los servicios ahora? (s/n): "
if /i "%START%"=="s" (
    echo.
    call "%~dp0start.bat"
)
pause
