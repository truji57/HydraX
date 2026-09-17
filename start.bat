@echo off
cd /d "%~dp0"

echo ============================
echo    HydraX-NT - NinjaTrader Copier
echo ============================
echo.
echo Arrancando...

REM Kill any existing backend on port 8006
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8006 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

start "HydraX-NT Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8006"
timeout /t 3 /nobreak >nul
start "HydraX-NT Frontend" cmd /c "cd /d %~dp0frontend && npx vite --host 0.0.0.0 --port 5173"
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo Backend:  http://localhost:8006
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8006/docs
echo.
pause
