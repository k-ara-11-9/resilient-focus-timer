from flask import Flask, request, jsonify, render_template, session, redirect, make_response
from flask_cors import CORS
import sqlite3
from datetime import datetime, timezone, timedelta
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# IST has no DST; use a fixed offset so analytics works on Windows without tzdata.
UTC_TZ = timezone.utc
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def _safe_next_path(value):
    """Allow only same-origin relative paths (open-redirect safe)."""
    if isinstance(value, str) and value.startswith('/') and not value.startswith('//'):
        return value
    return '/'

import secrets
import sys

app = Flask(__name__)
_secret = os.environ.get('SECRET_KEY')
if _secret:
    app.secret_key = _secret
else:
    app.secret_key = secrets.token_hex(32)
    print("WARNING: SECRET_KEY not set — using a random key. "
          "Sessions will not survive a server restart.",
          file=sys.stderr)
CORS(app, supports_credentials=True) # Enable CORS for frontend

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.environ.get('FOCUS_TIMER_DB', os.environ.get('TEST_DB_PATH', os.path.join(BASE_DIR, 'focus_timer.db')))

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def auto_migrate_db():
    """Robustly migrate database schema and create missing tables/columns."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Legacy Migrations
    try:
        # Check 'user' -> 'User'
        cursor.execute("PRAGMA table_info(user)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'name' in cols:
            cursor.execute('''CREATE TABLE IF NOT EXISTS User_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)''')
            cursor.execute("INSERT INTO User_new (id, username, email, password_hash) SELECT id, name, email, password FROM user")
            cursor.execute("DROP TABLE user")
            cursor.execute("ALTER TABLE User_new RENAME TO User")

        # Check 'session' -> 'Session'
        cursor.execute("PRAGMA table_info(session)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'id' in cols and 'SessionID' not in cols:
            cursor.execute('''CREATE TABLE IF NOT EXISTS Session_new (
                SessionID INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                date DATE NOT NULL, start_time TIME NOT NULL, end_time TIME,
                duration INTEGER, focus_duration INTEGER, status TEXT NOT NULL,
                paused_ms INTEGER DEFAULT 0, last_pause_start_iso TEXT,
                task_name TEXT, tags TEXT, FOREIGN KEY (user_id) REFERENCES User(id))''')
            cursor.execute("INSERT INTO Session_new (SessionID, user_id, date, start_time, end_time, duration, status) SELECT id, user_id, date, start_time, end_time, duration, status FROM session")
            cursor.execute("DROP TABLE session")
            cursor.execute("ALTER TABLE Session_new RENAME TO Session")

        # Check 'interruption' -> 'Interruption'
        cursor.execute("PRAGMA table_info(interruption)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'id' in cols and 'InterruptionID' not in cols:
            cursor.execute('''CREATE TABLE IF NOT EXISTS Interruption_new (
                InterruptionID INTEGER PRIMARY KEY AUTOINCREMENT, SessionID INTEGER NOT NULL,
                user_id INTEGER, timestamp DATETIME NOT NULL,
                FOREIGN KEY (SessionID) REFERENCES Session(SessionID),
                FOREIGN KEY (user_id) REFERENCES User(id))''')
            cursor.execute("INSERT INTO Interruption_new (InterruptionID, SessionID, user_id, timestamp) SELECT id, session_id, user_id, timestamp FROM interruption")
            cursor.execute("DROP TABLE interruption")
            cursor.execute("ALTER TABLE Interruption_new RENAME TO Interruption")

        conn.commit()
    except Exception as e:
        print(f"Warning: Legacy migration check failed: {e}", file=sys.stderr)
        conn.rollback()

    # 2. Schema Creation (for new deployments)
    try:
        from schema import create_tables
        create_tables(conn)
    except Exception as e:
        print(f"Warning: create_tables failed: {e}", file=sys.stderr)

    # 3. Add missing columns to 'Session' if partially migrated
    try:
        cursor.execute("PRAGMA table_info(Session)")
        cols = {col[1] for col in cursor.fetchall()}
        for col, col_type in [
            ("focus_duration", "INTEGER"),
            ("paused_ms", "INTEGER DEFAULT 0"),
            ("last_pause_start_iso", "TEXT"),
            ("task_name", "TEXT"),
            ("tags", "TEXT")
        ]:
            if col not in cols:
                try:
                    cursor.execute(f"ALTER TABLE Session ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass
        conn.commit()
    except Exception as e:
        print(f"Warning: Column addition failed: {e}", file=sys.stderr)

    conn.close()

# Auto-initialize on import so both `flask run` and `python app.py` (WSGI) work.
auto_migrate_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'email', 'password')):
        missing = [k for k in ('username', 'email', 'password') if not data or k not in data]
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    username = data['username']
    email = data['email']
    password = data['password']
    password_hash = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO User (username, email, password_hash) VALUES (?, ?, ?)",
                       (username, email, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'username or email already taken'}), 409
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    
    conn.close()
    session['user_id'] = user_id
    return jsonify({'message': 'User created successfully', 'user_id': user_id}), 201

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'password')):
        return jsonify({'error': 'Missing username or password'}), 400

    username = data['username']
    password = data['password']

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM User WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        return jsonify({'message': 'Logged in successfully'}), 200
    else:
        return jsonify({'error': 'invalid credentials'}), 401

@app.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/sessions', methods=['GET'])
@login_required
def get_sessions():
    status_filter = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    user_id = session['user_id']
    
    import datetime
    def validate_date(date_text):
        try:
            if date_text:
                datetime.datetime.strptime(date_text, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    if not validate_date(date_from) or not validate_date(date_to):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    if status_filter == 'running':
        cursor.execute(
            "SELECT SessionID, date, start_time, status, focus_duration, paused_ms, last_pause_start_iso "
            "FROM Session WHERE status IN ('running', 'paused') AND user_id = ?",
            (user_id,)
        )
        sess = cursor.fetchone()
        conn.close()

        if sess:
            return jsonify([{
                'sessionID': sess['SessionID'],
                'date': sess['date'],
                'start_time': sess['start_time'],
                'status': sess['status'],
                'focus_duration': sess['focus_duration'],
                'paused_ms': sess['paused_ms'] if sess['paused_ms'] is not None else 0,
                'last_pause_start_iso': sess['last_pause_start_iso']
            }]), 200
        else:
            return jsonify([]), 200
            
    # Default behavior: return completed + stopped_early sessions
    query = """
        SELECT s.SessionID, s.date, s.start_time, s.duration, s.status, s.task_name, s.tags,
               COUNT(i.InterruptionID) as interruption_count
        FROM Session s
        LEFT JOIN Interruption i ON s.SessionID = i.SessionID
        WHERE s.status IN ('completed', 'stopped_early') AND s.user_id = ?
    """
    params = [user_id]

    if date_from:
        query += " AND s.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND s.date <= ?"
        params.append(date_to)

    query += " GROUP BY s.SessionID ORDER BY s.SessionID DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    sessions = []
    for row in rows:
        sessions.append({
            'sessionID': row['SessionID'],
            'date': row['date'],
            'start_time': row['start_time'],
            'duration': row['duration'],
            'status': row['status'],
            'task_name': row['task_name'],
            'tags': row['tags'],
            'interruption_count': row['interruption_count']
        })

    return jsonify(sessions), 200

@app.route('/sessions', methods=['POST'])
@login_required
def create_session():
    data = request.get_json()
    if not data or 'start_time' not in data:
        return jsonify({'error': 'start_time is required'}), 400

    start_time_raw = data['start_time']
    user_id = session['user_id']
    
    focus_duration = data.get('focus_duration')
    if focus_duration is not None:
        try:
            focus_duration = int(focus_duration)
            if focus_duration <= 0 or focus_duration > 10800:
                return jsonify({'error': 'focus_duration must be between 1 and 10800 seconds'}), 400
        except ValueError:
            return jsonify({'error': 'focus_duration must be an integer'}), 400
    else:
        focus_duration = 1500
    
    try:
        # Attempt to parse as ISO datetime
        from datetime import datetime as dt_module
        dt = dt_module.fromisoformat(start_time_raw.replace('Z', '+00:00'))
        date_part = dt.strftime('%Y-%m-%d')
        time_part = dt.strftime('%H:%M:%S')
    except ValueError:
        # Fallback if just time is provided
        from datetime import datetime as dt_module
        date_part = dt_module.now().strftime('%Y-%m-%d')
        time_part = start_time_raw

    conn = get_db()
    cursor = conn.cursor()

    # Check if a running session already exists
    cursor.execute("SELECT SessionID FROM Session WHERE status = 'running' AND user_id = ?", (user_id,))
    if cursor.fetchone() is not None:
        conn.close()
        return jsonify({'error': 'A running session already exists'}), 409

    task_name = data.get('task_name')
    tags = data.get('tags')

    # Insert new session
    cursor.execute(
        "INSERT INTO Session (date, start_time, status, user_id, focus_duration, task_name, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (date_part, time_part, 'running', user_id, focus_duration, task_name, tags)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'sessionID': session_id,
        'date': date_part,
        'start_time': time_part,
        'status': 'running',
        'focus_duration': focus_duration,
        'paused_ms': 0,
        'last_pause_start_iso': None
    }), 201

@app.route('/sessions/<int:session_id>', methods=['GET'])
@login_required
def get_session(session_id):
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Session WHERE SessionID = ?", (session_id,))
    sess = cursor.fetchone()
    conn.close()

    if sess:
        if sess['user_id'] != user_id:
            return jsonify({'error': 'forbidden'}), 403
        return jsonify({
            'sessionID': sess['SessionID'],
            'date': sess['date'],
            'start_time': sess['start_time'],
            'end_time': sess['end_time'],
            'duration': sess['duration'],
            'status': sess['status']
        }), 200
    else:
        return jsonify({'error': 'Session not found'}), 404

@app.route('/sessions/<int:session_id>', methods=['PATCH'])
@login_required
def update_session(session_id):
    user_id = session['user_id']
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status is required'}), 400

    new_status = data['status']
    if new_status not in ['running', 'paused', 'completed', 'stopped_early']:
        return jsonify({'error': 'Invalid status'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Get current session
    cursor.execute("SELECT * FROM Session WHERE SessionID = ?", (session_id,))
    sess = cursor.fetchone()

    if not sess:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404

    if sess['user_id'] != user_id:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    current_status = sess['status']

    # Validate transition
    if current_status in ['completed', 'stopped_early']:
        conn.close()
        return jsonify({'error': 'Cannot update a completed or stopped session'}), 409

    if current_status == new_status and not ('paused_ms' in data or 'last_pause_start_iso' in data or 'end_time' in data or 'duration' in data):
        conn.close()
        return jsonify({'error': f'Session is already {new_status}'}), 409

    # Update session
    end_time = data.get('end_time', sess['end_time'])
    duration = data.get('duration', sess['duration'])

    paused_ms = sess['paused_ms'] if sess['paused_ms'] is not None else 0
    if 'paused_ms' in data and data['paused_ms'] is not None:
        try:
            val = int(data['paused_ms'])
        except (TypeError, ValueError):
            conn.close()
            return jsonify({'error': 'paused_ms must be an integer'}), 400
        if val < 0:
            conn.close()
            return jsonify({'error': 'paused_ms must be >= 0'}), 400
        try:
            from datetime import datetime as dt_elapsed
            start_dt = dt_elapsed.strptime(f"{sess['date']} {sess['start_time']}", '%Y-%m-%d %H:%M:%S')
            start_dt = start_dt.replace(tzinfo=UTC_TZ)
            now_dt = dt_elapsed.now(UTC_TZ)
            elapsed_ms = max(0, int((now_dt - start_dt).total_seconds() * 1000))
            MAX_ALLOWED_PAUSED = max(elapsed_ms, 3_600_000)
            if val > MAX_ALLOWED_PAUSED:
                val = MAX_ALLOWED_PAUSED
        except (ValueError, TypeError):
            pass
        paused_ms = val

    last_pause = data.get('last_pause_start_iso', sess['last_pause_start_iso'])
    if last_pause is not None and last_pause != '':
        # Basic shape check — must have a T
        if 'T' not in str(last_pause):
            conn.close()
            return jsonify({'error': 'last_pause_start_iso must be a full ISO string'}), 400
    else:
        last_pause = None

    if end_time and sess['start_time']:
        try:
            from datetime import datetime as dt_module
            start_t = dt_module.strptime(sess['start_time'], '%H:%M:%S')
            end_t = dt_module.strptime(end_time, '%H:%M:%S')
            diff = (end_t - start_t).total_seconds()
            if diff < 0:
                diff += 24 * 3600 # Account for midnight crossing

            # If the calculated duration is suspiciously large (e.g. > 12 hours),
            # it means end_time was actually earlier in the day (stale completion bug)
            if diff > 12 * 3600:
                conn.close()
                return jsonify({'error': 'end_time cannot be earlier than start_time'}), 400
        except ValueError:
            pass

    cursor.execute(
        "UPDATE Session SET status = ?, end_time = ?, duration = ?, paused_ms = ?, last_pause_start_iso = ? WHERE SessionID = ?",
        (new_status, end_time, duration, paused_ms, last_pause, session_id)
    )
    conn.commit()

    # Fetch updated row to return
    cursor.execute("SELECT * FROM Session WHERE SessionID = ?", (session_id,))
    updated_session = cursor.fetchone()
    conn.close()

    return jsonify({
        'sessionID': updated_session['SessionID'],
        'status': updated_session['status'],
        'duration': updated_session['duration'],
        'end_time': updated_session['end_time'],
        'focus_duration': updated_session['focus_duration'],
        'paused_ms': updated_session['paused_ms'] if updated_session['paused_ms'] is not None else 0,
        'last_pause_start_iso': updated_session['last_pause_start_iso']
    }), 200

@app.route('/sessions/<int:session_id>/interruptions', methods=['POST'])
@login_required
def log_interruption(session_id):
    user_id = session['user_id']
    data = request.get_json()
    if not data or 'timestamp' not in data:
        return jsonify({'error': 'timestamp is required'}), 400

    timestamp = data['timestamp']

    conn = get_db()
    cursor = conn.cursor()

    # Verify session exists and is running
    cursor.execute("SELECT status, user_id FROM Session WHERE SessionID = ?", (session_id,))
    sess = cursor.fetchone()

    if not sess:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404

    if sess['user_id'] != user_id:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    if sess['status'] != 'running':
        conn.close()
        return jsonify({'error': 'Cannot log interruption for a non-running session'}), 409

    # Insert interruption
    cursor.execute(
        "INSERT INTO Interruption (SessionID, timestamp, user_id) VALUES (?, ?, ?)",
        (session_id, timestamp, user_id)
    )
    interruption_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'interruptionID': interruption_id,
        'timestamp': timestamp
    }), 201

@app.route('/sessions/<int:session_id>/interruptions', methods=['GET'])
@login_required
def get_interruptions(session_id):
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM Session WHERE SessionID = ?", (session_id,))
    sess = cursor.fetchone()
    if not sess:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404
        
    if sess['user_id'] != user_id:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403
        
    cursor.execute("SELECT InterruptionID, timestamp FROM Interruption WHERE SessionID = ? ORDER BY timestamp ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    interruptions = [{'interruptionID': r['InterruptionID'], 'timestamp': r['timestamp']} for r in rows]
    return jsonify(interruptions), 200

@app.route('/analytics/daily', methods=['GET'])
@login_required
def analytics_daily():
    user_id = session['user_id']
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')
    
    from datetime import datetime, timedelta, date

    def parse_date(date_text):
        try:
            return datetime.strptime(date_text, '%Y-%m-%d').date()
        except ValueError:
            return None

    if start_date_str or end_date_str:
        if not start_date_str or not end_date_str:
             return jsonify({'error': 'start and end must be YYYY-MM-DD'}), 400
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        if not start_date or not end_date:
            return jsonify({'error': 'start and end must be YYYY-MM-DD'}), 400
    else:
        end_date = datetime.now(IST_TZ).date()
        start_date = end_date - timedelta(days=6)
        
    if start_date > end_date:
        return jsonify({'error': 'start must be before end'}), 400
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Widen the date range by 1 day on both sides for the DB query to catch timezone boundary overlaps
        db_start_date = start_date - timedelta(days=1)
        db_end_date = end_date + timedelta(days=1)
        
        cursor.execute("""
            SELECT s.date, s.start_time, s.SessionID, s.duration, s.status,
                   COUNT(i.InterruptionID) as interruption_count
            FROM Session s
            LEFT JOIN Interruption i ON s.SessionID = i.SessionID
            WHERE s.user_id = ? AND s.date >= ? AND s.date <= ?
              AND s.status IN ('completed', 'stopped_early')
            GROUP BY s.SessionID
        """, (user_id, db_start_date.strftime('%Y-%m-%d'), db_end_date.strftime('%Y-%m-%d')))
        
        rows = cursor.fetchall()
        conn.close()
        
        from collections import defaultdict
        daily_stats = defaultdict(lambda: {'focus_minutes': 0, 'interruptions': 0})
        
        for row in rows:
            date_str = row['date']
            time_str = row['start_time']
            try:
                # Try to combine date and time. Assume stored timestamp is UTC.
                dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=UTC_TZ)
                ist_dt = dt.astimezone(IST_TZ)
                day = ist_dt.date()
            except ValueError:
                # Fallback if time_str is not HH:MM:SS
                try:
                    day = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue
            
            if not (start_date <= day <= end_date):
                continue
            
            day_str = day.strftime('%Y-%m-%d')
            duration_secs = row['duration'] if row['duration'] else 0
            focus_minutes = duration_secs // 60
            interruptions = row['interruption_count']
            
            daily_stats[day_str]['focus_minutes'] += focus_minutes
            daily_stats[day_str]['interruptions'] += interruptions
            
        result = []
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime('%Y-%m-%d')
            result.append({
                'date': day_str,
                'focus_minutes': daily_stats[day_str]['focus_minutes'],
                'interruptions': daily_stats[day_str]['interruptions']
            })
            current_date += timedelta(days=1)
            
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': 'Database error occurred'}), 500

@app.route('/analytics/heatmap', methods=['GET'])
@login_required
def analytics_heatmap():
    user_id = session['user_id']
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')

    from datetime import datetime, timedelta, date

    def parse_date(date_text):
        try:
            return datetime.strptime(date_text, '%Y-%m-%d').date()
        except ValueError:
            return None

    if start_date_str or end_date_str:
        if not start_date_str or not end_date_str:
            return jsonify({'error': 'start and end must be YYYY-MM-DD'}), 400
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        if not start_date or not end_date:
            return jsonify({'error': 'start and end must be YYYY-MM-DD'}), 400
    else:
        end_date = datetime.now(IST_TZ).date()
        start_date = end_date - timedelta(days=6)

    if start_date > end_date:
        return jsonify({'error': 'start must be before end'}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Widen the date range by 1 day on both sides to catch timezone boundary overlaps
        db_start_date = start_date - timedelta(days=1)
        db_end_date = end_date + timedelta(days=1)

        cursor.execute("""
            SELECT s.date, s.start_time
            FROM Session s
            WHERE s.user_id = ? AND s.date >= ? AND s.date <= ?
              AND s.status IN ('completed', 'stopped_early')
        """, (user_id, db_start_date.strftime('%Y-%m-%d'), db_end_date.strftime('%Y-%m-%d')))

        rows = cursor.fetchall()
        conn.close()

        hour_counts = [0] * 24

        for row in rows:
            date_str = row['date']
            time_str = row['start_time']
            try:
                # Combine date and time, assume stored as UTC, convert to IST
                dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=UTC_TZ)
                ist_dt = dt.astimezone(IST_TZ)
                day = ist_dt.date()
            except ValueError:
                try:
                    day = datetime.strptime(date_str, '%Y-%m-%d').date()
                    # Without a parseable time we can't determine the hour, skip
                    continue
                except ValueError:
                    continue

            if not (start_date <= day <= end_date):
                continue

            hour_counts[ist_dt.hour] += 1

        result = [{'hour': h, 'count': hour_counts[h]} for h in range(24) if hour_counts[h] > 0]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': 'Database error occurred'}), 500

@app.route('/analytics/summary', methods=['GET'])
@login_required
def analytics_summary():
    user_id = session['user_id']

    from datetime import date, datetime, timedelta as td_

    end_date = datetime.now(IST_TZ).date()
    start_date = end_date - td_(days=6)

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Query wide enough around last 7 days to catch timezone boundaries
        db_start = start_date - td_(days=1)
        db_end = end_date + td_(days=1)

        cursor.execute("""
            SELECT s.date, s.start_time, s.duration, s.status, s.tags
            FROM Session s
            WHERE s.user_id = ? AND s.status IN ('completed', 'stopped_early')
              AND s.date >= ? AND s.date <= ?
        """, (user_id, db_start.strftime('%Y-%m-%d'), db_end.strftime('%Y-%m-%d')))
        rows = cursor.fetchall()
        conn.close()

        # Build daily buckets keyed by IST-local date (YYYY-MM-DD string)
        # minutes_total -> focus minutes that day
        # has_completed -> True if any completed session that day (IST local)
        from collections import defaultdict
        per_day = defaultdict(lambda: {'minutes': 0, 'completed': False})

        for row in rows:
            date_str = row['date']
            time_str = row['start_time']
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=UTC_TZ).astimezone(IST_TZ)
                local_day = dt.date()
            except ValueError:
                try:
                    local_day = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue

            day_key = local_day.strftime('%Y-%m-%d')
            duration_secs = int(row['duration'] or 0)
            per_day[day_key]['minutes'] += max(0, duration_secs // 60)
            per_day[day_key]['completed'] = True
            
            tags = row['tags']
            if tags:
                try:
                    import json
                    tags_list = json.loads(tags)
                    for t in tags_list:
                        per_day[day_key].setdefault('tags_dist', defaultdict(int))
                        per_day[day_key]['tags_dist'][t] += max(0, duration_secs // 60)
                except Exception:
                    pass

        # Generate ordered 7-day window, oldest -> newest, today at end
        window = []
        cursor_day = start_date
        while cursor_day <= end_date:
            key = cursor_day.strftime('%Y-%m-%d')
            entry = per_day.get(key, {'minutes': 0, 'completed': False})
            window.append({
                'date': key,
                'focus_minutes': entry['minutes'],
                'has_completed': entry['completed']
            })
            cursor_day += td_(days=1)

        # Consistency: % of last 7 days with at least 1 completed session
        active_days = sum(1 for d in window if d['has_completed'])
        consistency_pct = 0 if len(window) == 0 else round((active_days / len(window)) * 100)

        # Streak: consecutive days ending at today with at least one completed session
        # Walk backwards from today; stop on the first empty day
        streak = 0
        reversed_days = list(reversed(window))  # today first
        for d in reversed_days:
            if d['has_completed']:
                streak += 1
            else:
                break

        weekly_minutes = [{'date': d['date'], 'focus_minutes': d['focus_minutes']} for d in window]
        
        # Aggregate tags_dist across the 7 days
        tags_distribution = defaultdict(int)
        for key, entry in per_day.items():
            if 'tags_dist' in entry:
                for t, mins in entry['tags_dist'].items():
                    tags_distribution[t] += mins

        return jsonify({
            'streak': streak,
            'consistency_pct': consistency_pct,
            'active_days_last7': active_days,
            'weekly_minutes': weekly_minutes,
            'tags_distribution': dict(tags_distribution)
        }), 200
    except Exception as e:
        return jsonify({'error': 'Database error occurred'}), 500

from flask import send_from_directory

def render_react():
    response = make_response(send_from_directory(os.path.join(BASE_DIR, 'frontend', 'dist'), 'index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'frontend', 'dist', 'assets'), filename)

@app.route('/history')
def history():
    return render_react()

@app.route('/login')
def login_page():
    return render_react()

@app.route('/signup')
def signup_page():
    return render_react()

@app.route('/')
def index():
    return render_react()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(debug=False, port=port)
