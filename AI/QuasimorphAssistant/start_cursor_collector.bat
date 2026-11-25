@echo off
setlocal

set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SCRIPT=%PROJECT%tools\collect_cursor_examples.py"

set "PYTHONUTF8=1"
chcp 65001 >nul

title Quasimorph Cursor Example Collector

if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment was not found:
    echo "%PYTHON%"
    echo.
    echo Check that this BAT file is located in the QuasimorphAssistant project root.
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo ERROR: Cursor collector script was not found:
    echo "%SCRIPT%"
    echo.
    echo Expected location: tools\collect_cursor_examples.py
    pause
    exit /b 1
)

pushd "%PROJECT%"
echo Starting Quasimorph cursor example collector...
echo.
"%PYTHON%" "%SCRIPT%"
set "RESULT=%ERRORLEVEL%"
popd

echo.
if not "%RESULT%"=="0" (
    echo Collector finished with error code %RESULT%.
) else (
    echo Collector finished.
)
echo.
pause
exit /b %RESULT%
