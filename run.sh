#!/usr/bin/env bash
# Linux / macOS counterpart of run.bat.
cd "$(dirname "$0")" || exit 1

# Set up the virtual environment first if it's missing or requirements.txt has changed since
if [ ! -x App/venv/bin/python ] || ! cmp -s App/requirements.txt App/venv/requirements.installed; then
    echo "Setting up the virtual environment first..."
    bash App/install_venv.sh || exit 1
fi

# No arguments opens the GUI; any arguments run the command line (try: ./run.sh --help)
exec App/venv/bin/python App/main.py "$@"
