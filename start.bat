@echo off
cd /d "%~dp0"

echo ============================
echo    HydraX v2 - Trade Copier
echo ============================
echo.
echo Starting servers...

start "HydraX-Backend" cmd /c "%~dp0start_backend.bat"
start "HydraX-Frontend" cmd /c "%~dp0start_frontend.bat"

timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Close the cmd windows or press Ctrl+C in each to stop.
pause
