@echo off
setlocal
cd /d "%~dp0"
echo [1/5] Preparing local Python environment...
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto :fail

echo [2/5] Installing Windows-safe dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [3/5] Migrating existing data into canonical schemas...
.venv\Scripts\python.exe migrate_data.py
if errorlevel 1 goto :fail

echo [4/5] Training models from currently available real data...
.venv\Scripts\python.exe train_models.py
if errorlevel 1 goto :fail

echo [5/5] Running project doctor...
.venv\Scripts\python.exe project_doctor.py
if errorlevel 1 goto :fail

echo Running automated tests...
.venv\Scripts\python.exe -m unittest discover -s tests
if errorlevel 1 goto :fail

echo.
echo Setup complete. Use START_DASHBOARD.bat to open the dashboard.
exit /b 0
:fail
echo.
echo Setup stopped because a step failed. Copy the error above into ChatGPT.
pause
exit /b 1
