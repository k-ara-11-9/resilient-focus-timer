@echo off
setlocal

echo ===============================================
echo   Resilient Focus Timer - Local Launcher
echo ===============================================
echo.

REM Check Python is available
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist yet
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Run migration only if the database doesn't exist yet
if not exist "focus_timer.db" (
    echo No database found - running migration...
    python migrate.py
) else (
    echo Existing database found - skipping migration.
)

echo.
echo Starting Flask server...
echo Once running, open http://127.0.0.1:5000 in your browser.
echo Press CTRL+C to stop the server.
echo.

python app.py

endlocal
