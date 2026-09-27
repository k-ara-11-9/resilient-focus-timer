import pytest
import sqlite3
from app import app, get_db



def test_auth_cases(client):
    # Test missing fields in signup (Case 5)
    res_missing = client.post('/auth/signup', json={'username': 'noemail'})
    assert res_missing.status_code == 400
    assert "Missing required fields:" in res_missing.get_json()['error']

    # 1. Signs up two distinct users (User A, User B).
    res1 = client.post('/auth/signup', json={
        'username': 'userA',
        'email': 'a@example.com',
        'password': 'password123'
    })
    assert res1.status_code == 201
    
    # Check duplicate signup (Case 3)
    res_dup = client.post('/auth/signup', json={
        'username': 'userA',
        'email': 'b@example.com',
        'password': 'password123'
    })
    assert res_dup.status_code == 409
    assert res_dup.get_json() == {"error": "username or email already taken"}

    res2 = client.post('/auth/signup', json={
        'username': 'userB',
        'email': 'b@example.com',
        'password': 'password123'
    })
    assert res2.status_code == 201

    # Test wrong login credentials (Case 4)
    res_bad_login = client.post('/auth/login', json={'username': 'userA', 'password': 'wrongpassword'})
    assert res_bad_login.status_code == 401
    assert res_bad_login.get_json() == {"error": "invalid credentials"}
    
    res_no_user = client.post('/auth/login', json={'username': 'nobody', 'password': 'password123'})
    assert res_no_user.status_code == 401
    assert res_no_user.get_json() == {"error": "invalid credentials"}

    # 2. Confirms User A can create a session (POST /sessions) and it succeeds.
    client.post('/auth/login', json={'username': 'userA', 'password': 'password123'})
    
    res_sess = client.post('/sessions', json={'start_time': '2023-01-01T10:00:00Z'})
    assert res_sess.status_code == 201
    session_id = res_sess.get_json()['sessionID']
    
    # Log in as User B
    client.post('/auth/login', json={'username': 'userB', 'password': 'password123'})
    
    # 3. Confirms User B gets 403 when attempting PATCH /sessions/{id} on User A's session.
    res_patch = client.patch(f'/sessions/{session_id}', json={'status': 'completed'})
    assert res_patch.status_code == 403
    assert res_patch.get_json() == {"error": "forbidden"}
    
    # 4. Confirms User B gets 403 on GET /sessions/{id} for User A's session
    res_get = client.get(f'/sessions/{session_id}')
    assert res_get.status_code == 403
    assert res_get.get_json() == {"error": "forbidden"}
    
    # 5. Confirms an unauthenticated request to any mutating endpoint gets 401 (Case 1)
    with client.application.test_client() as c_unauth:
        res_unauth = c_unauth.post(f'/sessions/{session_id}/interruptions', json={'timestamp': '2023-01-01T10:05:00Z'})
        assert res_unauth.status_code == 401
        assert res_unauth.get_json() == {"error": "authentication required"}
