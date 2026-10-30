@echo off
setlocal enabledelayedexpansion
REM Windows launcher for Hunter's Oracle.
REM
REM Fully self-healing: checks for a working virtual environment with the
REM right packages installed, and (re)builds it if anything's missing or
REM broken -- you should never need to manually delete .venv or pip install
REM anything yourself.
cd /d "%~dp0"

set VENV_PY=.venv\Scripts\python.exe

call :check_healthy
if "%HEALTHY%"=="1" goto :run

echo Setting up Hunter's Oracle (first run, or environment needs repair)...
if exist ".venv" rmdir /s /q ".venv"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYLAUNCH=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYLAUNCH=python"
    ) else (
        echo.
        echo Python 3 wasn't found on this system.
        echo Install it from https://www.python.org/downloads/windows/
        echo ^(check "Add python.exe to PATH" during install^), then re-run run.bat.
        echo.
        pause
        exit /b 1
    )
)

%PYLAUNCH% -m venv .venv
if not exist "%VENV_PY%" (
    echo FATAL: could not create the virtual environment.
    pause
    exit /b 1
)

"%VENV_PY%" -m pip install --quiet --upgrade pip
"%VENV_PY%" -m pip install --quiet -r requirements.txt

call :check_healthy
if not "%HEALTHY%"=="1" (
    echo FATAL: dependency install failed. Check your internet connection and try again.
    pause
    exit /b 1
)
echo Setup complete.

:run
"%VENV_PY%" app.py
pause
exit /b 0

:check_healthy
set HEALTHY=0
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import flask, requests" >nul 2>nul
    if !errorlevel!==0 set HEALTHY=1
)
exit /b 0
