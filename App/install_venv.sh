#!/usr/bin/env bash
# Linux / macOS counterpart of install_venv.bat.
set -u
cd "$(dirname "$0")" || exit 1

# Find the newest Python that meets the minimum version in SystemSupport.py
PY=""
for candidate in python3.14 python3.13 python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" SystemSupport.py >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "Error: Python 3.12 or newer was not found."
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            "$candidate" SystemSupport.py
            break
        fi
    done
    echo "Install Python 3.12 or newer with your package manager or from https://www.python.org/downloads/ and run this script again."
    exit 1
fi
"$PY" SystemSupport.py

echo "Creating virtual environment in venv..."
if ! "$PY" -m venv venv; then
    echo "Error: couldn't create the virtual environment with \"$PY\"."
    echo "On Debian/Ubuntu install it with 'sudo apt install python3-venv'."
    exit 1
fi

echo "Installing requirements..."
venv/bin/python -m pip install --upgrade pip
if ! venv/bin/python -m pip install -r requirements.txt; then
    echo "Error: installing the requirements failed. Check the messages above."
    exit 1
fi

if ! venv/bin/python -c "import tkinter" >/dev/null 2>&1; then
    echo "Warning: tkinter isn't available, so the GUI won't start. The command line still works."
    echo "Install it with your package manager, e.g. 'sudo apt install python3-tk' or 'brew install python-tk'."
fi

# run.sh compares this copy with requirements.txt to know when to reinstall
cp requirements.txt venv/requirements.installed

echo "Done. Start the app with run.sh in the folder above this one."
