# Resilient Focus Timer

A modern, robust Pomodoro/Focus Timer built with a Flask API backend and a Vite+React frontend. 

It is designed to handle common browser limitations (background throttling, tab visibility changes, accidental closures) and provide reliable tracking of focus sessions, interruptions, and task analytics.

## Features

- **Strict Mode**: Automatically logs an interruption whenever you navigate away from the tab or switch windows during a running session.
- **Robust State Recovery**: Resyncs the timer perfectly upon tab restoration, even if the browser killed the tab or you closed it accidentally.
- **Task Tags & Analytics**: Categorize sessions using #tags and visualize focus trends, streaks, and a GitHub-style heatmap.
- **Audio Notifications**: Plays an alert when a focus session completes.
- **Pause & Resume**: Supports pausing a session indefinitely without losing track of elapsed time across backend/frontend restarts.

## Tech Stack

- **Backend**: Python 3.10+, Flask 3, SQLite (via `sqlite3`)
- **Frontend**: React 18, Vite, Recharts, TailwindCSS (for utility styling conceptually applied in vanilla CSS structure)
- **Testing**: `pytest` for comprehensive backend and E2E lifecycle testing

## Getting Started

### Local Development

Use the included launcher scripts which automatically provision a virtual environment, install dependencies, initialize the database (with migrations handled automatically on startup), and run the server.

**Windows:**
```bat
run.bat
```

**macOS / Linux:**
```bash
./run.sh
```

Then, open `http://127.0.0.1:5000` in your browser.

### Manual Setup (Without Script)

1. Create a virtual environment: `python -m venv venv`
2. Activate it: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (macOS/Linux)
3. Install requirements: `pip install -r requirements.txt`
4. Set a local secret key: `set SECRET_KEY=your_secret_key` (Windows) or `export SECRET_KEY=your_secret_key` (macOS/Linux)
5. Start Flask: `flask run`

### Frontend Assets

The current implementation serves a bundled React app from the Flask backend (the built assets are in `static/`). The old vanilla JS assets from Release 1 are still present in `templates/` and `static/` but are deprecated in favor of the React implementation.

## Project Structure

- `app.py`: Flask application, route handlers, and API endpoints.
- `schema.py`: Single source of truth for the SQLite database schema and database initialization logic.
- `tests/`: Comprehensive test suite containing unit, integration, and E2E tests (`pytest`).
- `frontend/`: The Vite+React frontend application source code.
- `docs/API.md`: Detailed API route documentation.

## Testing

Run the test suite using `pytest`:

```bash
# Ensure venv is activated
pytest -v
```

The repository currently maintains a 100% pass rate (27/27 tests).

## Known Limitations

- **Timezone Drift**: Analytics bucketing (`/analytics/daily` and `/analytics/heatmap`) currently relies on timezone resolution via `app.py`. If a user crosses timezone boundaries between starting a session and viewing analytics, date boundary buckets might misalign.
- **Frontend Consolidation**: The React app operates alongside legacy vanilla JS code. Vite build output must currently be manually transferred to `static/` and `templates/` for Flask to serve it correctly, which complicates deployment. Consolidating this build pipeline is a pending priority.
- **E2E Tests Structure**: The old `test_e2e.py` still expects legacy DOM selectors (from the Vanilla JS app). It needs a complete rewrite to utilize React-specific classes and test IDs.

## API Documentation

See [API.md](docs/API.md) for full endpoint specifications.
