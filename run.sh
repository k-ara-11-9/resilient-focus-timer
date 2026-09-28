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

# Generate a stable SECRET_KEY for local dev if not set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY="local_development_secret_key_12345"
fi

echo
echo "Starting Flask server..."
echo "Once running, open http://127.0.0.1:5000 in your browser."
echo "Press CTRL+C to stop the server."
echo

python app.py
