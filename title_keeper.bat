@echo off
:loop
title %~1
timeout /t 1 /nobreak >nul
goto loop