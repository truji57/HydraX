@echo off
title HydraX - Backend
cd /d "%~dp0backend"
echo Starting HydraX Backend on http://localhost:8000...
echo API Docs: http://localhost:8000/docs
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning
pause
