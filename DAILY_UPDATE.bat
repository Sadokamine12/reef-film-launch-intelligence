@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run FIRST_SETUP.bat first.
  pause
  exit /b 1
)
echo [1/4] Collecting ESO comparable / Resolution seat snapshots...
.venv\Scripts\python.exe eso_sales_tracker.py
if errorlevel 1 echo WARNING: ESO collection stopped early; validating existing data.
echo [2/4] Migrating/deduplicating canonical daily snapshots...
.venv\Scripts\python.exe migrate_data.py
if errorlevel 1 exit /b 1
echo [3/4] Retraining all eligible models...
.venv\Scripts\python.exe train_models.py
if errorlevel 1 exit /b 1
echo [4/4] Checking project health...
.venv\Scripts\python.exe project_doctor.py
if errorlevel 1 exit /b 1
echo.
echo Daily update complete.
exit /b 0
