import pytest
import os
import tempfile
import sqlite3
import importlib
import sys

@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Creates a temporary database for each test, overriding DB_NAME via env.

    Ensures the real `focus_timer.db` is NEVER touched by pytest.
    """
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    monkeypatch.setenv('FOCUS_TIMER_DB', temp_path)
    monkeypatch.setenv('TEST_DB_PATH', temp_path)

    # Reload `app` so DB_NAME is re-evaluated from env
    if 'app' in sys.modules:
        importlib.reload(sys.modules['app'])
    import app as app_module
    flask_app = app_module.app
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test_secret'

    with flask_app.app_context():
        conn = app_module.get_db()
        from schema import create_tables
        create_tables(conn)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(Session)")
            cols = {row[1] for row in cur.fetchall()}
            if 'paused_ms' not in cols:
                cur.execute("ALTER TABLE Session ADD COLUMN paused_ms INTEGER DEFAULT 0")
            if 'last_pause_start_iso' not in cols:
                cur.execute("ALTER TABLE Session ADD COLUMN last_pause_start_iso TEXT")
            if 'focus_duration' not in cols:
                cur.execute("ALTER TABLE Session ADD COLUMN focus_duration INTEGER")
            if 'user_id' not in cols:
                cur.execute("ALTER TABLE Session ADD COLUMN user_id INTEGER REFERENCES User(id)")
            conn.commit()
        except Exception:
            pass
        from werkzeug.security import generate_password_hash
        hashed_pw = generate_password_hash('testpass')
        conn.execute('INSERT INTO User (id, username, email, password_hash) VALUES (1, "testuser", "test@example.com", ?)', (hashed_pw,))
        conn.commit()
        conn.close()

    yield temp_path

    try:
        os.remove(temp_path)
    except OSError:
        pass

@pytest.fixture
def client(temp_db):
    """A test client for the app."""
    import app as app_module
    with app_module.app.test_client() as client:
        yield client
