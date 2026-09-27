import pytest
from app import app
from datetime import datetime, timedelta


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _signup_login(client, username):
    """Helper: sign up (ignore 409) and log in a user."""
    client.post('/auth/signup', json={
        'username': username,
        'email': f'{username}@test.com',
        'password': 'p'
    })
    r = client.post('/auth/login', json={
        'username': username,
        'password': 'p'
    })
    assert r.status_code == 200


def _create_completed_session(client, iso_start_time, duration=60):
    """Create a session at a specific ISO time and immediately complete it."""
    r = client.post('/sessions', json={'start_time': iso_start_time})
    assert r.status_code == 201, f"Failed to create session: {r.json}"
    sid = r.json['sessionID']
    client.patch(f'/sessions/{sid}', json={
        'status': 'completed',
        'duration': duration
    })
    return sid


def test_heatmap_counts(client):
    """Create sessions at known hours and verify the heatmap counts match."""
    ts = datetime.now().timestamp()
    _signup_login(client, f'hm1_{ts}')

    # Pick a fixed date that is definitely "today" for the test
    today = datetime.today()
    day_str = today.strftime('%Y-%m-%d')

    # Session at 08:00 UTC  → 13:30 IST (hour 13)
    _create_completed_session(client, f'{day_str}T08:00:00Z')
    # Session at 14:00 UTC  → 19:30 IST (hour 19)
    _create_completed_session(client, f'{day_str}T14:00:00Z')
    # Session at 20:00 UTC  → 01:30 IST next day (hour 1, next day)
    _create_completed_session(client, f'{day_str}T20:00:00Z')

    # Query the range covering today only
    r = client.get(f'/analytics/heatmap?start={day_str}&end={day_str}')
    assert r.status_code == 200
    data = r.json

    # Must have exactly 24 entries
    assert len(data) == 24

    # Build a lookup
    by_hour = {d['hour']: d['count'] for d in data}
    assert by_hour[13] == 1  # 08:00 UTC → 13:30 IST
    assert by_hour[19] == 1  # 14:00 UTC → 19:30 IST
    # 20:00 UTC → 01:30 IST next day, which is outside today-only range
    assert by_hour[1] == 0

    # All other hours should be 0
    for h in range(24):
        if h not in (13, 19):
            assert by_hour[h] == 0, f"Hour {h} should be 0, got {by_hour[h]}"

    # Now query a range covering today and tomorrow to capture the rolled-over session
    tomorrow = today + timedelta(days=1)
    r2 = client.get(
        f'/analytics/heatmap?start={day_str}&end={tomorrow.strftime("%Y-%m-%d")}'
    )
    data2 = r2.json
    by_hour2 = {d['hour']: d['count'] for d in data2}
    assert by_hour2[1] == 1  # 20:00 UTC → 01:30 IST next day now included


def test_heatmap_zero_sessions(client):
    """A user with no sessions gets all 24 hours at count 0."""
    ts = datetime.now().timestamp()
    _signup_login(client, f'hm_zero_{ts}')

    r = client.get('/analytics/heatmap')
    assert r.status_code == 200
    data = r.json
    assert len(data) == 24
    for entry in data:
        assert entry['count'] == 0


def test_heatmap_user_isolation(client):
    """User 2's heatmap must NOT include User 1's sessions."""
    ts = datetime.now().timestamp()

    # User 1 creates sessions
    _signup_login(client, f'hm_iso1_{ts}')
    today = datetime.today()
    day_str = today.strftime('%Y-%m-%d')
    _create_completed_session(client, f'{day_str}T09:00:00Z')  # → 14:30 IST

    # User 2 signs up and creates their own session at a different hour
    _signup_login(client, f'hm_iso2_{ts}')
    _create_completed_session(client, f'{day_str}T03:00:00Z')  # → 08:30 IST

    # User 2 heatmap
    r = client.get(f'/analytics/heatmap?start={day_str}&end={day_str}')
    data2 = r.json
    by_hour2 = {d['hour']: d['count'] for d in data2}
    assert by_hour2[8] == 1   # User 2's own session
    assert by_hour2[14] == 0  # Must NOT see User 1's session

    # Switch back to User 1 and verify
    _signup_login(client, f'hm_iso1_{ts}')
    r = client.get(f'/analytics/heatmap?start={day_str}&end={day_str}')
    data1 = r.json
    by_hour1 = {d['hour']: d['count'] for d in data1}
    assert by_hour1[14] == 1  # User 1's own session
    assert by_hour1[8] == 0   # Must NOT see User 2's session


def test_heatmap_unauth(client):
    """Unauthenticated request returns 401."""
    with app.test_client() as unauth_client:
        r = unauth_client.get('/analytics/heatmap')
        assert r.status_code == 401
        assert r.json == {'error': 'authentication required'}


def test_heatmap_invalid_dates(client):
    """Invalid date params return 400 with proper messages."""
    ts = datetime.now().timestamp()
    _signup_login(client, f'hm_err_{ts}')

    # Invalid format
    r = client.get('/analytics/heatmap?start=bad&end=2026-01-01')
    assert r.status_code == 400
    assert r.json == {'error': 'start and end must be YYYY-MM-DD'}

    # Only start provided
    r = client.get('/analytics/heatmap?start=2026-01-01')
    assert r.status_code == 400
    assert r.json == {'error': 'start and end must be YYYY-MM-DD'}

    # Start after end
    r = client.get('/analytics/heatmap?start=2026-01-05&end=2026-01-01')
    assert r.status_code == 400
    assert r.json == {'error': 'start must be before end'}


def test_heatmap_db_failure(client, monkeypatch):
    """DB failure returns 500 with generic body, not a stack trace."""
    ts = datetime.now().timestamp()
    _signup_login(client, f'hm_db_{ts}')

    import app as my_app

    def mock_get_db(*args, **kwargs):
        raise Exception("Simulated DB failure")

    monkeypatch.setattr(my_app, 'get_db', mock_get_db)

    r = client.get('/analytics/heatmap')
    assert r.status_code == 500
    assert r.json == {'error': 'Database error occurred'}
