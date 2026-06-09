@echo off
setlocal

cd /d "%~dp0"

echo [1/5] Checking Python 3.12...
py -3.12 --version
if errorlevel 1 (
    echo Python 3.12 not found.
    pause
    exit /b 1
)

echo [2/5] Reusing existing venv...
if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Please run run_desktop_dev.bat first.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [3/5] Checking app imports...
python -c "import fastapi, uvicorn, pydantic, webview; print('imports ok')"
if errorlevel 1 (
    echo Import check failed.
    pause
    exit /b 1
)

echo [4/5] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FinanceCalendar.spec del /q FinanceCalendar.spec
if exist FinanceCalendar_debug.spec del /q FinanceCalendar_debug.spec

echo [5/5] Building release exe...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name FinanceCalendar ^
  --add-data "index.html;." ^
  --hidden-import webview ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import clr ^
  --hidden-import pythonnet ^
  --hidden-import clr_loader ^
  --collect-all webview ^
  --collect-all clr_loader ^
  --collect-all pythonnet ^
  launcher.py

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\FinanceCalendar.exe
echo ============================================
pause
