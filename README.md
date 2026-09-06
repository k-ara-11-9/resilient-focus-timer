# Resilient Focus Timer

A Pomodoro-based focus timer with interruption logging and session history, built as part of a Software Development Lab (DSC3153) team project. The app tracks 25-minute focus sessions, lets a user log interruptions mid-session without breaking their timer, and keeps a local-first, offline-capable history of completed sessions.

This repository covers **Sprint 1 (Release 1)** — the four Must-have stories from the project's backlog: starting/completing a timer, one-tap interruption logging, session history, and local-first storage.

---

## Project Structure

```
resilient-focus-timer/
│
├── app.py                  # Flask app: routes + REST API endpoints
├── migrate.py               # Creates focus_timer.db and its tables
├── requirements.txt          # Runtime dependencies (Flask, flask-cors)
├── requirements-dev.txt      # Additional dependencies for running tests
├── run.bat                   # One-click setup + launch (Windows)
│
├── static/
│   ├── script.js            # Timer logic, interruption logging, notifications
│   ├── history.js           # Session history rendering
│   └── style.css
│
├── templates/
│   ├── index.html            # Main Timer screen
│   └── history.html          # Session History screen
│
├── tests/
│   ├── test_e2e.py           # Timer start/pause/resume/complete flow
│   ├── test_e2e_tm02.py      # Intrusion logging flow
│   ├── test_e2e_lg01.py      # Session history flow
│   ├── test_e2e_sy01.py      # Local-only storage verification
│   ├── test_get_history.py
│   └── clean.py              # Dev utility: wipes all session/interruption data
│
├── docs/
│   ├── TEST_RESULTS_TM02.md
│   ├── TEST_RESULTS_LG01.md
│   └── TEST_RESULTS_SY01.md
│
└── .github/workflows/ci.yml  # Build + lint check on every push
```

---

## Schema

| Table | Columns |
|---|---|
| `User` | `UserID` (PK) — intentionally a minimal stub; no Sprint 1 story requires distinguishing between users |
| `Session` | `SessionID` (PK), `UserID` (FK), `date`, `start_time`, `end_time`, `duration`, `status` (`running` / `paused` / `completed` / `stopped_early`) |
| `Interruption` | `InterruptionID` (PK), `SessionID` (FK), `timestamp` |

`Session` is stored locally in SQLite by default (see **SY-01** below) — no cloud sync exists yet.

---

## API Contract

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions` | Start a new session |
| `PATCH` | `/sessions/{id}` | Update a session's status (pause, resume, complete, stop early) |
| `POST` | `/sessions/{id}/interruptions` | Log an interruption against a running session |
| `GET` | `/sessions` | List completed sessions (history) |
| `GET` | `/sessions?status=running` | Check if a session is currently active |

---

## Setup

### 1. Windows — one-click

Double-click `run.bat`. It creates a virtual environment, installs dependencies, runs the database migration if needed, and starts the server at `http://127.0.0.1:5000`.

### 2. Linux / macOS — one-click

Run `./run.sh` from the repo root (make it executable first if needed:
`chmod +x run.sh`). It creates a virtual environment, installs
dependencies, runs the database migration if needed, and starts the
server at http://127.0.0.1:5000.

### 3. Manual (all platforms)

**Windows (PowerShell):**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python migrate.py
python app.py
```

**Linux / macOS:**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python migrate.py
python app.py
```

Open `http://127.0.0.1:5000` once the server starts.

### 4. Running tests (optional)

Tests use Playwright, which is not required to run the app itself:
```
pip install -r requirements-dev.txt
playwright install chromium
python tests/test_e2e.py
```

---

## Sprint 1 Stories

- **TM-01** — Start, pause/resume, and complete a 25-minute focus timer
- **TM-02** — Log an interruption with one tap without stopping the timer
- **LG-01** — View a history of completed sessions
- **SY-01** — Store session data locally by default, with no network calls during normal use

---

## Notes

- The countdown is timestamp-based (comparing the current time against a stored end-timestamp), not a simple decrementing counter — this keeps it accurate even if the browser tab is backgrounded.
- `User` currently has no attributes beyond its primary key. The app is effectively single-user for Sprint 1; multi-user support would be a future story.
- `duration` is currently fixed at 25 minutes for completed sessions, since Sprint 1's only flow is a fixed-length Pomodoro.

---

## Known Limitations

This release covers Sprint 1's Must-have stories only. The following are deliberate scope boundaries, not bugs:

- **Single-user, single-session by design.** The `User` table is a minimal stub with no authentication. Every visitor to a deployed instance shares the same database and the same "current session" — if one person starts a timer, anyone else who opens the app sees that same session running, not a fresh one. Multi-user support is out of scope for Sprint 1.
- **No cloud sync.** Data is stored locally in SQLite only (`SY-01`). Multi-device sync (`SY-02`) is a planned future story, not yet implemented.
- **Fixed 25-minute sessions.** `duration` is not yet configurable or dynamically computed for partial sessions — every completed session is recorded as 25 minutes by design.
- **Development server only.** The app currently runs on Flask's built-in development server, which is not intended for production traffic. A production WSGI server (e.g. gunicorn) would be the next step for a public, multi-user deployment.

---

## License

See [LICENSE](LICENSE).

---

## Roadmap

- [x] TM-01 — Focus timer (start/pause/resume/complete)
- [x] TM-02 — Interruption logging
- [x] LG-01 — Session history
- [x] SY-01 — Local-first storage
- [ ] SY-02 — Optional encrypted cloud sync
- [ ] Context-Aware Analytics (charts, heatmaps)
- [ ] Smart Task Engine (duplicate-detecting task list)
