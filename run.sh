#!/usr/bin/env bash
set -e

echo "==============================================="
echo "  Resilient Focus Timer - Local Launcher"
echo "==============================================="
echo

# Check Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 was not found on PATH."
    echo "Please install Python 3.10+ and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist yet
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Run migration only if the database doesn't exist yet
if [ ! -f "focus_timer.db" ]; then
    echo "No database found - running migration..."
    python migrate.py
else
    echo "Existing database found - skipping migration."
fi

echo
echo "Starting Flask server..."
echo "Once running, open http://127.0.0.1:5000 in your browser."
echo "Press CTRL+C to stop the server."
echo

python app.py
