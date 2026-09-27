import pytest
import os
import tempfile
import sqlite3
from app import app as flask_app
from app import get_db
import app

@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Creates a temporary database for each test, overriding DB_NAME."""
    # 1. Create a temporary SQLite file
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # 2. Point the Flask app's DB connection at this temp DB
    monkeypatch.setenv('TEST_DB_PATH', temp_path)
    monkeypatch.setattr(app, 'DB_NAME', temp_path)
    
    # Enable TESTING mode
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test_secret'
    
    # 3. Initialize schema in the temp DB using the shared source of truth
    with flask_app.app_context():
        conn = get_db()
        from schema import create_tables
        create_tables(conn)
        
        from werkzeug.security import generate_password_hash
        hashed_pw = generate_password_hash('testpass')
        conn.execute('INSERT INTO User (id, username, email, password_hash) VALUES (1, "testuser", "test@example.com", ?)', (hashed_pw,))
        conn.commit()
        conn.close()

    # Provide the temp_path (and active environment) to tests
    yield temp_path
    
    # 4. Tear down/delete the temp DB after tests finish
    try:
        os.remove(temp_path)
    except OSError:
        pass

@pytest.fixture
def client(temp_db):
    """A test client for the app."""
    with flask_app.test_client() as client:
        yield client
