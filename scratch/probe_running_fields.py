import tempfile, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from werkzeug.security import generate_password_hash
from schema import create_tables

fd, temp_path = tempfile.mkstemp(suffix='.db')
os.close(fd)
os.environ['TEST_DB_PATH'] = temp_path

conn = sqlite3.connect(temp_path)
create_tables(conn)
hashed_pw = generate_password_hash('testpass')
conn.execute('INSERT INTO User (id, username, email, password_hash) VALUES (1, ?, ?, ?)',
             ('testuser', 'test@example.com', hashed_pw))
conn.commit()
conn.close()

if 'app' in sys.modules:
    del sys.modules['app']
import app as appmod

client = appmod.app.test_client()
# Login first (sets session cookie via test_client internal state)
r = client.post('/auth/login', json={'username': 'testuser', 'password': 'testpass'})
print(f'login {r.status_code}: {r.get_json()}')

# Create a focus session with focus_duration
r = client.post('/sessions', json={'start_time': '2026-09-28T05:30:00.000Z', 'focus_duration': 1800})
print(f'POST /sessions {r.status_code}: {r.get_json()}')

# Now probe ?status=running
r = client.get('/sessions?status=running')
print(f'\n==== PROBE RESULT GET /sessions?status=running ====')
print(f'Status: {r.status_code}')
import json
body = r.get_json()
print(f'Full JSON: {json.dumps(body, indent=2)}')
if isinstance(body, list) and len(body) > 0:
    print(f'\nKeys in the running session object: {list(body[0].keys())}')
    print(f'Note: casing and presence of focus_duration: {[k for k in body[0].keys()]}')

# Also probe PATCH response shape by completing the session just created
if isinstance(body, list) and len(body) > 0:
    sid = body[0]['sessionID']
    r2 = client.patch(f'/sessions/{sid}', json={
        'status': 'completed',
        'end_time': '06:00:00',
        'duration': 1800
    })
    print(f'\nPATCH /sessions/{sid} response:')
    print(f'Status: {r2.status_code}, body={r2.get_json()}')

# Also probe analytics/daily shape briefly
r3 = client.get('/analytics/daily')
print(f'\nGET /analytics/daily[0..1] sample keys:')
arr = r3.get_json()
if arr and len(arr):
    print(f'  length = {len(arr)}')
    print(f'  keys of first entry: {list(arr[0].keys())}')
    print(f'  last entry (today): {arr[-1]}')

r4 = client.get('/analytics/heatmap')
print(f'\nGET /analytics/heatmap:')
arr = r4.get_json()
print(f'  length = {len(arr)}')
if arr:
    print(f'  sample: {arr[:3]}')

os.remove(temp_path)
print('\nDone')
