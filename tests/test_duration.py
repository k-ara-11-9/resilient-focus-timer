import pytest
from app import get_db

def test_create_session_with_valid_custom_duration(client):
    # Log in
    client.post('/auth/login', json={'username': 'testuser', 'password': 'testpass'})
    
    # Send custom duration
    resp = client.post('/sessions', json={
        'start_time': '2023-01-01T10:00:00Z',
        'focus_duration': 3000
    })
    
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['focus_duration'] == 3000
    
    session_id = data['sessionID']
    
    # Check DB directly
    from app import app as flask_app
    with flask_app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT focus_duration FROM Session WHERE SessionID = ?", (session_id,))
        row = cursor.fetchone()
        assert row['focus_duration'] == 3000

def test_create_session_default_duration(client):
    client.post('/auth/login', json={'username': 'testuser', 'password': 'testpass'})
    
    resp = client.post('/sessions', json={
        'start_time': '2023-01-01T10:00:00Z'
        # focus_duration omitted
    })
    
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['focus_duration'] == 1500  # Default value
    
    session_id = data['sessionID']
    
    from app import app as flask_app
    with flask_app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT focus_duration FROM Session WHERE SessionID = ?", (session_id,))
        row = cursor.fetchone()
        assert row['focus_duration'] == 1500

def test_create_session_invalid_durations(client):
    client.post('/auth/login', json={'username': 'testuser', 'password': 'testpass'})
    
    invalid_cases = [
        0,
        -100,
        10801, # Above max of 180 mins = 10800
        "abc"  # Not an integer
    ]
    
    for val in invalid_cases:
        resp = client.post('/sessions', json={
            'start_time': '2023-01-01T10:00:00Z',
            'focus_duration': val
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

def test_running_session_returns_focus_duration(client):
    # Log in
    client.post('/auth/login', json={'username': 'testuser', 'password': 'testpass'})

    # Create running session with custom focus_duration=900 (15 min)
    create_resp = client.post('/sessions', json={
        'start_time': '2023-06-15T09:00:00Z',
        'focus_duration': 900
    })
    assert create_resp.status_code == 201

    # Query running sessions
    resp = client.get('/sessions?status=running')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    sess = payload[0]
    assert sess['focus_duration'] == 900
    # Confirm all original fields still present and unchanged
    assert 'sessionID' in sess
    assert 'date' in sess
    assert 'start_time' in sess
    assert sess['status'] == 'running'
