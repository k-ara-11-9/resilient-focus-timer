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
