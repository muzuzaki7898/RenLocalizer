#!/bin/bash
# RenLocalizer CLI Launcher for Linux/Mac

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Setting up environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run CLI
python3 run_cli.py "$@"
