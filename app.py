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
DB_NAME = os.environ.get('TEST_DB_PATH', os.path.join(BASE_DIR, 'focus_timer.db'))

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Ensure all tables exist.  Safe to call on every startup because
    the DDL uses CREATE TABLE IF NOT EXISTS."""
    from schema import create_tables
    conn = sqlite3.connect(DB_NAME)
    create_tables(conn)
    conn.close()

# Auto-initialize on import so both `flask run` and `python app.py` work.
init_db()

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
        cursor.execute("SELECT SessionID, date, start_time, status FROM Session WHERE status = 'running' AND user_id = ?", (user_id,))
        sess = cursor.fetchone()
        conn.close()
        
        if sess:
            return jsonify([{
                'sessionID': sess['SessionID'],
                'date': sess['date'],
                'start_time': sess['start_time'],
                'status': sess['status']
            }]), 200
        else:
            return jsonify([]), 200
            
    # Default behavior: return completed sessions
    query = """
        SELECT s.SessionID, s.date, s.start_time, s.duration, s.status,
               COUNT(i.InterruptionID) as interruption_count
        FROM Session s
        LEFT JOIN Interruption i ON s.SessionID = i.SessionID
        WHERE s.status = 'completed' AND s.user_id = ?
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

    # Insert new session
    cursor.execute(
        "INSERT INTO Session (date, start_time, status, user_id, focus_duration) VALUES (?, ?, ?, ?, ?)",
        (date_part, time_part, 'running', user_id, focus_duration)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'sessionID': session_id,
        'start_time': start_time_raw,
        'status': 'running',
        'focus_duration': focus_duration
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
        
    if current_status == new_status:
        conn.close()
        return jsonify({'error': f'Session is already {new_status}'}), 409

    # Update session
    end_time = data.get('end_time', sess['end_time'])
    duration = data.get('duration', sess['duration'])

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
        "UPDATE Session SET status = ?, end_time = ?, duration = ? WHERE SessionID = ?",
        (new_status, end_time, duration, session_id)
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
        'end_time': updated_session['end_time']
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
        end_date = date.today()
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
            SELECT s.date, s.start_time, s.SessionID, s.duration,
                   COUNT(i.InterruptionID) as interruption_count
            FROM Session s
            LEFT JOIN Interruption i ON s.SessionID = i.SessionID
            WHERE s.user_id = ? AND s.date >= ? AND s.date <= ?
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
        end_date = date.today()
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

@app.route('/history')
def history():
    if 'user_id' not in session:
        response = make_response(redirect('/login?next=/history'))
    else:
        response = make_response(render_template('history.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/')
def index():
    if 'user_id' not in session:
        response = make_response(redirect('/login?next=/'))
    else:
        response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(debug=False, port=port)
