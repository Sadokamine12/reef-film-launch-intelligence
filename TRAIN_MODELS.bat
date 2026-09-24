@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run FIRST_SETUP.bat first.
  exit /b 1
)
.venv\Scripts\python.exe train_models.py
exit /b %errorlevel%
