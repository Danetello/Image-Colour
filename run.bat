@echo off
setlocal
cd /d "%~dp0"

REM Set up the virtual environment first if it's missing or requirements.txt has changed since
set "NEEDS_INSTALL="
if not exist "venv\Scripts\python.exe" set "NEEDS_INSTALL=1"
if not exist "venv\requirements.installed" set "NEEDS_INSTALL=1"
if not defined NEEDS_INSTALL (
    fc /b requirements.txt venv\requirements.installed >nul 2>nul || set "NEEDS_INSTALL=1"
)
if defined NEEDS_INSTALL (
    echo Setting up the virtual environment first...
    call "%~dp0install_venv.bat" --no-pause
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

REM No arguments opens the GUI; any arguments run the command line (try: run.bat --help)
venv\Scripts\python.exe main.py %*
if errorlevel 1 pause
