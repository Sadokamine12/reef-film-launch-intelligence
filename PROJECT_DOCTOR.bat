@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run FIRST_SETUP.bat first.
  exit /b 1
)
.venv\Scripts\python.exe project_doctor.py
exit /b %errorlevel%
