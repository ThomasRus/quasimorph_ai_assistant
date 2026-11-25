@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "BASE_DIR=%~dp0"
set "PYTHON=%BASE_DIR%.venv\Scripts\python.exe"
set "SCRIPT=%BASE_DIR%app\screen_watcher.py"

if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment was not found.
    echo Expected: %PYTHON%
    pause
    exit /b 1
)
if not exist "%SCRIPT%" (
    echo ERROR: screen_watcher.py was not found.
    echo Expected: %SCRIPT%
    pause
    exit /b 1
)

cd /d "%BASE_DIR%"
echo ============================================================
echo Quasimorph Assistant - Screen Watcher v1.6
echo Project: %BASE_DIR%
echo ============================================================
"%PYTHON%" "%SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" echo Program exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
