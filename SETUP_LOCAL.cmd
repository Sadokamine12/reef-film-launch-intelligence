@echo off
cd /d "%~dp0"
py -3.12 scripts\setup-local.py
if errorlevel 1 (
  echo Setup did not complete. Check the error above. Requires Python 3.12 and Node.js 22+.
  pause
  exit /b 1
)
pause
