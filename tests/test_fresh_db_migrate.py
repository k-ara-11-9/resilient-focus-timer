import os
import tempfile
import importlib
import sys
import time
from datetime import datetime, timezone, timedelta


def test_fresh_db_migrate_and_full_lifecycle(monkeypatch):
    """Create a brand-new temp DB via migrate.py, then exercise full lifecycle.

    No data is pre-seeded; schema tables + required columns must be created
    solely by migrate.run_migration() + app.py auto-init migrations.
    """
    fd, fresh_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    # Don't let the file exist yet — create_tables / migrate should create it.
    os.remove(fresh_path)
    assert not os.path.exists(fresh_path), "temp DB must not pre-exist"

    try:
        monkeypatch.setenv('FOCUS_TIMER_DB', fresh_path)
        monkeypatch.setenv('TEST_DB_PATH', fresh_path)
        monkeypatch.setenv('SECRET_KEY', 'fresh_test_secret')

        # 1. Now import/reload app so it picks up FOCUS_TIMER_DB env
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if 'app' in sys.modules:
            importlib.reload(sys.modules['app'])
        import app as app_mod
        app_mod.init_db()
        app_mod.migrate_add_pause_columns()
        assert os.path.exists(fresh_path), "init_db should have created the DB file"

        flask_app = app_mod.app
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'fresh_test_secret'

        with flask_app.test_client() as c:
            # 2a. Signup + login
            ts = int(time.time() * 1000)
            u = f'fresh_u_{ts}'
            r = c.post('/auth/signup', json={'username': u, 'email': f'{u}@x.com', 'password': 'pw'})
            assert r.status_code == 201, r.get_data(as_text=True)
            r = c.post('/auth/login', json={'username': u, 'password': 'pw'})
            assert r.status_code == 200

            # 2b. Create a running focus session
            start = datetime.now(timezone.utc).isoformat()
            r = c.post('/sessions', json={'start_time': start, 'focus_duration': 900})
            assert r.status_code == 201, r.get_data(as_text=True)
            data = r.get_json()
            assert 'sessionID' in data
            sid = data['sessionID']

            # 2c. Log one interruption WHILE running (server requires status==running)
            r = c.post(f'/sessions/{sid}/interruptions', json={'timestamp': datetime.now(timezone.utc).isoformat()})
            assert r.status_code == 201

            # 2d. Pause it (paused_ms must be preserved)
            r = c.patch(f'/sessions/{sid}', json={'status': 'paused', 'paused_ms': 5000})
            assert r.status_code == 200, r.get_data(as_text=True)
            pb = r.get_json()
            assert pb['paused_ms'] == 5000

            # 2e. Complete it as a 15-minute completed session (=900s) with 5s paused.
            now = datetime.now(timezone.utc)
            end_hms = now.strftime('%H:%M:%S')
            r = c.patch(f'/sessions/{sid}', json={
                'status': 'completed',
                'end_time': end_hms,
                'duration': 900,
                'paused_ms': 5000,
                'last_pause_start_iso': None,
            })
            assert r.status_code == 200, r.get_data(as_text=True)
            body = r.get_json()
            assert body['status'] == 'completed'
            assert body['duration'] == 900

            # 2f. Create a stopped_early session (5 minutes = 300s) to test filter
            r = c.post('/sessions', json={
                'start_time': now.isoformat(),
                'focus_duration': 900,
            })
            assert r.status_code == 201
            sid2 = r.get_json()['sessionID']
            r = c.patch(f'/sessions/{sid2}', json={
                'status': 'stopped_early',
                'end_time': (now + timedelta(seconds=300)).strftime('%H:%M:%S'),
                'duration': 300,
                'paused_ms': 0,
            })
            assert r.status_code == 200

            # 2g. Create a paused (incomplete) session — must NOT count in analytics
            r = c.post('/sessions', json={
                'start_time': now.isoformat(),
                'focus_duration': 1500,
            })
            sid3 = r.get_json()['sessionID']
            r = c.patch(f'/sessions/{sid3}', json={'status': 'paused', 'paused_ms': 1000})
            assert r.status_code == 200

            # 3. GET /sessions?status=running → ensure focus_duration/paused_ms present
            r = c.get('/sessions?status=running')
            assert r.status_code == 200
            for s in r.get_json():
                assert 'focus_duration' in s
                assert 'paused_ms' in s
                assert 'status' in s

            # 4. All /analytics endpoints: call with no errors, correct minutes
            today = datetime.now().date()
            yest = today - timedelta(days=6)
            r = c.get(f'/analytics/daily?start={yest}&end={today}')
            assert r.status_code == 200, r.get_data(as_text=True)
            daily = r.get_json()
            assert isinstance(daily, list)
            today_row = [x for x in daily if x['date'] == today.isoformat()]
            assert today_row, "daily must include today"
            # 15 min completed + 5 min stopped_early = 20 focus minutes on today
            assert today_row[0]['focus_minutes'] == 20, f"expected 20 got {today_row[0]}"
            assert today_row[0]['interruptions'] == 1

            r = c.get(f'/analytics/heatmap?start={yest}&end={today}')
            assert r.status_code == 200, r.get_data(as_text=True)
            heat = r.get_json()
            assert isinstance(heat, list)
            # 2 finished sessions today -> 2 entries expected across the hour buckets
            assert sum(h['count'] for h in heat) == 2, f"heatmap count={heat}"

            r = c.get('/analytics/summary')
            assert r.status_code == 200, r.get_data(as_text=True)
            summary = r.get_json()
            for field in ('streak', 'consistency_pct', 'active_days_last7', 'weekly_minutes'):
                assert field in summary, f"missing {field}"
            assert isinstance(summary['weekly_minutes'], list)
            assert len(summary['weekly_minutes']) == 7
            today_summary_entry = [x for x in summary['weekly_minutes'] if x['date'] == today.isoformat()]
            assert today_summary_entry and today_summary_entry[0]['focus_minutes'] == 20, summary['weekly_minutes']
            # Completed session today -> streak at least 1, active_days_last7 >= 1, consistency_pct >= 1
            assert summary['streak'] >= 1
            assert summary['active_days_last7'] >= 1
            assert summary['consistency_pct'] >= 1

            # 5. Interruptions endpoint + history expansion
            r = c.get(f'/sessions/{sid}/interruptions')
            assert r.status_code == 200
            ints = r.get_json()
            assert len(ints) >= 1, f"expected at least 1 interruption, got {ints}"

            # GET all sessions (history): default history filters to completed only
            r = c.get('/sessions')
            assert r.status_code == 200
            hist = r.get_json()
            completed_rows = [s for s in hist if s['status'] == 'completed']
            assert len(completed_rows) >= 1
            for s in completed_rows:
                assert (s['duration'] or 0) >= 300
                mins = (s['duration'] or 0) // 60
                assert mins in (5, 15)

    finally:
        if os.path.exists(fresh_path):
            try:
                os.remove(fresh_path)
            except OSError:
                pass
