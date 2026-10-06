@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   TNU Timetable System - One-time Setup
echo ==============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv was not found in this project folder.
    echo Create the virtual environment first, then run this setup again.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo SETUP FAILED. Take a screenshot of this window.
    pause
    exit /b 1
)

echo.
echo DESKTOP SETUP COMPLETE
echo You can now double-click: TNU Timetable System.vbs
pause
