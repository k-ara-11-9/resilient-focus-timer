"""Tests for server-side pause reconciliation.

These verify that:
1. POST /sessions returns paused_ms=0 / last_pause_start_iso=null
2. GET /sessions?status=running returns both new fields
3. PATCH /sessions/{id} with paused_ms + last_pause_start_iso stores and echoes them
4. Reload sim: after a pause write, GET running returns the same values so a
   second browser (or a refresh) sees the identical paused_ms, not zero.
"""
import pytest
from datetime import datetime, timezone


def _signup_and_login(client, username, email, password):
    client.post('/auth/signup', json={'username': username, 'email': email, 'password': password})
    client.post('/auth/login', json={'username': username, 'password': password})


def test_new_session_returns_zero_paused_ms(client):
    _signup_and_login(client, 'pauser_a', 'pauser_a@example.com', 'pw')
    start = datetime.now(timezone.utc).isoformat()
    resp = client.post('/sessions', json={'start_time': start, 'focus_duration': 900})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['paused_ms'] == 0
    assert body['last_pause_start_iso'] is None
    assert body['status'] == 'running'


def test_get_running_returns_pause_fields(client):
    _signup_and_login(client, 'pauser_b', 'pauser_b@example.com', 'pw')
    start = datetime.now(timezone.utc).isoformat()
    created = client.post('/sessions', json={'start_time': start, 'focus_duration': 1200}).get_json()
    sid = created['sessionID']
    patch_iso = datetime.now(timezone.utc).isoformat()
    patch = client.patch(f'/sessions/{sid}', json={
        'status': 'paused',
        'paused_ms': 4217,
        'last_pause_start_iso': patch_iso,
    })
    assert patch.status_code == 200
    patch_body = patch.get_json()
    assert patch_body['status'] == 'paused'
    assert patch_body['paused_ms'] == 4217
    assert patch_body['last_pause_start_iso'] == patch_iso

    running = client.get('/sessions?status=running')
    assert running.status_code == 200
    arr = running.get_json()
    assert len(arr) == 1
    row = arr[0]
    assert row['paused_ms'] == 4217
    assert row['last_pause_start_iso'] == patch_iso
    assert row['status'] == 'paused'
    assert row['focus_duration'] == 1200


def test_paused_ms_rejects_negative(client):
    _signup_and_login(client, 'pauser_c', 'pauser_c@example.com', 'pw')
    start = datetime.now(timezone.utc).isoformat()
    created = client.post('/sessions', json={'start_time': start, 'focus_duration': 1500}).get_json()
    resp = client.patch(f'/sessions/{created["sessionID"]}', json={
        'status': 'paused', 'paused_ms': -1,
    })
    assert resp.status_code == 400


def test_complete_session_keeps_paused_ms(client):
    _signup_and_login(client, 'pauser_d', 'pauser_d@example.com', 'pw')
    start = datetime.now(timezone.utc).isoformat()
    created = client.post('/sessions', json={'start_time': start, 'focus_duration': 600}).get_json()
    sid = created['sessionID']
    client.patch(f'/sessions/{sid}', json={'status': 'paused', 'paused_ms': 30_000})
    end_hms = datetime.now(timezone.utc).strftime('%H:%M:%S')
    patch = client.patch(f'/sessions/{sid}', json={
        'status': 'completed', 'end_time': end_hms, 'duration': 570,
        'paused_ms': 30_000, 'last_pause_start_iso': None
    })
    assert patch.status_code == 200
    body = patch.get_json()
    assert body['duration'] == 570
    assert body['paused_ms'] == 30_000
