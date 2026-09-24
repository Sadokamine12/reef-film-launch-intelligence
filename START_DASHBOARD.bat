@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run FIRST_SETUP.bat first.
  exit /b 1
)
.venv\Scripts\python.exe run_dashboard_stable.py
