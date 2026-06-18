@echo off
title HydraX - Frontend
cd /d "%~dp0frontend"
echo Starting HydraX Frontend on http://localhost:5173...
echo.
npx vite --host 0.0.0.0
pause
