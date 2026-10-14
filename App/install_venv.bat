@echo off
setlocal
cd /d "%~dp0"

REM Pass --no-pause when calling this from another script (run.bat does).
set "PAUSE_AT_END=1"
if /i "%~1"=="--no-pause" set "PAUSE_AT_END="

REM Find a Python that meets the minimum version in SystemSupport.py.
REM The py launcher picks the newest installed Python; "python" on PATH is the fallback.
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 SystemSupport.py >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 (
        python SystemSupport.py >nul 2>nul
        if not errorlevel 1 set "PY=python"
    )
)
if not defined PY (
    echo Error: Python 3.12 or newer was not found.
    where python >nul 2>nul && python SystemSupport.py
    echo Install Python 3.12 or newer from https://www.python.org/downloads/ and run this script again.
    goto :fail
)
%PY% SystemSupport.py

echo Creating virtual environment in venv...
%PY% -m venv venv
if errorlevel 1 (
    echo Error: couldn't create the virtual environment with "%PY%".
    goto :fail
)

echo Installing requirements...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error: installing the requirements failed. Check the messages above.
    goto :fail
)

venv\Scripts\python.exe -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo Warning: tkinter isn't available, so the GUI won't start. The command line still works.
    echo Reinstall Python with the "tcl/tk and IDLE" option selected to get it.
)

REM run.bat compares this copy with requirements.txt to know when to reinstall
copy /y requirements.txt venv\requirements.installed >nul

echo Done. Start the app with run.bat in the folder above this one.
if defined PAUSE_AT_END pause
exit /b 0

:fail
if defined PAUSE_AT_END pause
exit /b 1
