import pytest
import sqlite3
from app import app, get_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    
    # Recreate tables to have a clean slate for tests
    with app.app_context():
        conn = get_db()
        conn.execute('DROP TABLE IF EXISTS Interruption')
        conn.execute('DROP TABLE IF EXISTS Session')
        conn.execute('DROP TABLE IF EXISTS User')
        
        conn.execute('''
        CREATE TABLE User (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        ''')
        
        conn.execute('''
        CREATE TABLE Session (
            SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME,
            duration INTEGER,
            status TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES User(id)
        )
        ''')
        
        conn.execute('''
        CREATE TABLE Interruption (
            InterruptionID INTEGER PRIMARY KEY AUTOINCREMENT,
            SessionID INTEGER NOT NULL,
            user_id INTEGER,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (SessionID) REFERENCES Session(SessionID),
            FOREIGN KEY (user_id) REFERENCES User(id)
        )
        ''')
        conn.commit()
        conn.close()

    return app

def test_auth_cases(client):
    with client.test_client() as c:
        # Test missing fields in signup (Case 5)
        res_missing = c.post('/auth/signup', json={'username': 'noemail'})
        assert res_missing.status_code == 400
        assert "Missing required fields:" in res_missing.get_json()['error']

        # 1. Signs up two distinct users (User A, User B).
        res1 = c.post('/auth/signup', json={
            'username': 'userA',
            'email': 'a@example.com',
            'password': 'password123'
        })
        assert res1.status_code == 201
        
        # Check duplicate signup (Case 3)
        res_dup = c.post('/auth/signup', json={
            'username': 'userA',
            'email': 'b@example.com',
            'password': 'password123'
        })
        assert res_dup.status_code == 409
        assert res_dup.get_json() == {"error": "username or email already taken"}
    
        res2 = c.post('/auth/signup', json={
            'username': 'userB',
            'email': 'b@example.com',
            'password': 'password123'
        })
        assert res2.status_code == 201
    
        # Test wrong login credentials (Case 4)
        res_bad_login = c.post('/auth/login', json={'username': 'userA', 'password': 'wrongpassword'})
        assert res_bad_login.status_code == 401
        assert res_bad_login.get_json() == {"error": "invalid credentials"}
        
        res_no_user = c.post('/auth/login', json={'username': 'nobody', 'password': 'password123'})
        assert res_no_user.status_code == 401
        assert res_no_user.get_json() == {"error": "invalid credentials"}

        # 2. Confirms User A can create a session (POST /sessions) and it succeeds.
        c.post('/auth/login', json={'username': 'userA', 'password': 'password123'})
        
        res_sess = c.post('/sessions', json={'start_time': '2023-01-01T10:00:00Z'})
        assert res_sess.status_code == 201
        session_id = res_sess.get_json()['sessionID']
        
        # Log in as User B
        c.post('/auth/login', json={'username': 'userB', 'password': 'password123'})
        
        # 3. Confirms User B gets 403 when attempting PATCH /sessions/{id} on User A's session.
        res_patch = c.patch(f'/sessions/{session_id}', json={'status': 'completed'})
        assert res_patch.status_code == 403
        assert res_patch.get_json() == {"error": "forbidden"}
        
        # 4. Confirms User B gets 403 on GET /sessions/{id} for User A's session
        res_get = c.get(f'/sessions/{session_id}')
        assert res_get.status_code == 403
        assert res_get.get_json() == {"error": "forbidden"}
    
    # 5. Confirms an unauthenticated request to any mutating endpoint gets 401 (Case 1)
    with client.test_client() as c_unauth:
        res_unauth = c_unauth.post(f'/sessions/{session_id}/interruptions', json={'timestamp': '2023-01-01T10:05:00Z'})
        assert res_unauth.status_code == 401
        assert res_unauth.get_json() == {"error": "authentication required"}
