import pytest
from app import app
from datetime import datetime, timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_analytics(client):
    # 1. Sign up and log in one user
    timestamp = datetime.now().timestamp()
    u1 = f"u1_{timestamp}"
    client.post('/auth/signup', json={'username': u1, 'email': f'{u1}@a.com', 'password': 'p'})
    r1 = client.post('/auth/login', json={'username': u1, 'password': 'p'})
    assert r1.status_code == 200

    # 2. Create 3 sessions across 2 days, varying durations
    today = datetime.today()
    yesterday = today - timedelta(days=1)
    
    # Session 1: Yesterday, 120 secs duration (2 mins)
    s1_start = yesterday.strftime('%Y-%m-%dT10:00:00Z')
    r = client.post('/sessions', json={'start_time': s1_start})
    assert r.status_code == 201
    s1_id = r.json['sessionID']
    
    # Add interruption to Session 1
    client.post(f'/sessions/{s1_id}/interruptions', json={'timestamp': '10:01:00'})
    
    # Complete Session 1
    client.patch(f'/sessions/{s1_id}', json={'status': 'completed', 'duration': 120})

    # Session 2: Today, 60 secs (1 min)
    s2_start = today.strftime('%Y-%m-%dT10:00:00Z')
    r = client.post('/sessions', json={'start_time': s2_start})
    s2_id = r.json['sessionID']
    client.patch(f'/sessions/{s2_id}', json={'status': 'completed', 'duration': 60})
    
    # Session 3: Today, 180 secs (3 mins)
    s3_start = today.strftime('%Y-%m-%dT11:00:00Z')
    r = client.post('/sessions', json={'start_time': s3_start})
    s3_id = r.json['sessionID']
    client.patch(f'/sessions/{s3_id}', json={'status': 'completed', 'duration': 180})

    # 3. Call GET /analytics/daily
    r = client.get(f'/analytics/daily?start={yesterday.strftime("%Y-%m-%d")}&end={today.strftime("%Y-%m-%d")}')
    assert r.status_code == 200
    data = r.json
    
    # Check Yesterday
    y_data = next((d for d in data if d['date'] == yesterday.strftime("%Y-%m-%d")), None)
    assert y_data is not None
    assert y_data['focus_minutes'] == 2 # 120 // 60
    assert y_data['interruptions'] == 1
    
    # Check Today
    t_data = next((d for d in data if d['date'] == today.strftime("%Y-%m-%d")), None)
    assert t_data is not None
    assert t_data['focus_minutes'] == 4 # (60 + 180) // 60
    assert t_data['interruptions'] == 0

    # 4. Day with no sessions
    two_days_ago = today - timedelta(days=2)
    r = client.get(f'/analytics/daily?start={two_days_ago.strftime("%Y-%m-%d")}&end={today.strftime("%Y-%m-%d")}')
    data = r.json
    d2_data = next((d for d in data if d['date'] == two_days_ago.strftime("%Y-%m-%d")), None)
    assert d2_data is not None
    assert d2_data['focus_minutes'] == 0
    assert d2_data['interruptions'] == 0
    
    # 5. Second user doesn't see first user's data (and vice versa)
    u2 = f"u2_{timestamp}"
    client.post('/auth/signup', json={'username': u2, 'email': f'{u2}@a.com', 'password': 'p'})
    client.post('/auth/login', json={'username': u2, 'password': 'p'})
    
    # Create a session for User 2 today (5 mins)
    s4_start = today.strftime('%Y-%m-%dT12:00:00Z')
    r = client.post('/sessions', json={'start_time': s4_start})
    s4_id = r.json['sessionID']
    client.patch(f'/sessions/{s4_id}', json={'status': 'completed', 'duration': 300})
    
    # User 2 GET analytics
    r = client.get(f'/analytics/daily?start={yesterday.strftime("%Y-%m-%d")}&end={today.strftime("%Y-%m-%d")}')
    data2 = r.json
    y_data2 = next((d for d in data2 if d['date'] == yesterday.strftime("%Y-%m-%d")), None)
    t_data2 = next((d for d in data2 if d['date'] == today.strftime("%Y-%m-%d")), None)
    
    # User 2 should NOT see User 1's data
    assert y_data2['focus_minutes'] == 0
    assert y_data2['interruptions'] == 0
    assert t_data2['focus_minutes'] == 5
    assert t_data2['interruptions'] == 0
    
    # Log back as User 1 and ensure their stats are unchanged
    client.post('/auth/login', json={'username': u1, 'password': 'p'})
    r = client.get(f'/analytics/daily?start={yesterday.strftime("%Y-%m-%d")}&end={today.strftime("%Y-%m-%d")}')
    data1 = r.json
    t_data1 = next((d for d in data1 if d['date'] == today.strftime("%Y-%m-%d")), None)
    assert t_data1['focus_minutes'] == 4 # Unchanged, User 2's 5 mins not included
        
    # 6. Unauthenticated returns 401
    with app.test_client() as unauth_client:
        r = unauth_client.get('/analytics/daily')
        assert r.status_code == 401
        assert r.json == {'error': 'authentication required'}
    assert r.json == {'error': 'authentication required'}

def test_analytics_errors(client):
    u = f"u3_{datetime.now().timestamp()}"
    client.post('/auth/signup', json={'username': u, 'email': f'{u}@a.com', 'password': 'p'})
    client.post('/auth/login', json={'username': u, 'password': 'p'})
    
    # Invalid date format
    r = client.get('/analytics/daily?start=invalid&end=2023-10-01')
    assert r.status_code == 400
    assert r.json == {'error': 'start and end must be YYYY-MM-DD'}
    
    # Missing end date
    r = client.get('/analytics/daily?start=2023-10-01')
    assert r.status_code == 400
    assert r.json == {'error': 'start and end must be YYYY-MM-DD'}
    
    # Start after end
    r = client.get('/analytics/daily?start=2023-10-02&end=2023-10-01')
    assert r.status_code == 400
    assert r.json == {'error': 'start must be before end'}

def test_analytics_db_failure(client, monkeypatch):
    u = f"u4_{datetime.now().timestamp()}"
    client.post('/auth/signup', json={'username': u, 'email': f'{u}@a.com', 'password': 'p'})
    client.post('/auth/login', json={'username': u, 'password': 'p'})
    
    import app as my_app
    def mock_get_db(*args, **kwargs):
        raise Exception("Simulated DB failure")
    
    monkeypatch.setattr(my_app, 'get_db', mock_get_db)
    
    r = client.get('/analytics/daily')
    assert r.status_code == 500
    assert r.json == {'error': 'Database error occurred'}
