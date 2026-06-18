@echo off
cd /d "%~dp0"
echo Current tags:
git tag --sort=-v:refname
echo.
set /p NEW="New version (e.g. 2.1.0): "
git tag -a v%NEW% -m "v%NEW%"
git push origin v%NEW%
echo Tag v%NEW% created and pushed.
echo Restart HydraX to see the new version.
pause
