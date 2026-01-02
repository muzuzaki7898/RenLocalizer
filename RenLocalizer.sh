#!/bin/bash
# RenLocalizer GUI Launcher for Linux/Mac

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    echo "Please install Python 3.10 or higher."
    exit 1
fi

# Change to script directory
cd "$(dirname "$0")"

# Setup virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Setting up RenLocalizer environment..."
    python3 -m venv venv
    source venv/bin/activate
    
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies..."
        pip install -r requirements.txt
    else
        echo "Warning: requirements.txt not found!"
    fi
else
    source venv/bin/activate
fi

# Run the application
echo "Starting RenLocalizer..."
python3 run.py
