@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Checking Python 3.12...
py -3.12 --version
if errorlevel 1 (
    echo Python 3.12 not found.
    echo Please install Python 3.12 x64, then run this file again.
    pause
    exit /b 1
)

echo [2/4] Creating virtual environment if needed...
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [3/4] Installing dependencies...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo [4/4] Starting desktop app...
python launcher.py

pause