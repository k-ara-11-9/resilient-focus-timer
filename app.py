from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
CORS(app) # Enable CORS for frontend

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'focus_timer.db')

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@app.route('/sessions', methods=['GET'])
def get_sessions():
    status_filter = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
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
        cursor.execute("SELECT SessionID, start_time, status FROM Session WHERE status = 'running'")
        session = cursor.fetchone()
        conn.close()
        
        if session:
            return jsonify([{
                'sessionID': session['SessionID'],
                'start_time': session['start_time'],
                'status': session['status']
            }]), 200
        else:
            return jsonify([]), 200
            
    # Default behavior: return completed sessions
    query = """
        SELECT s.SessionID, s.date, s.start_time, s.duration, s.status,
               COUNT(i.InterruptionID) as interruption_count
        FROM Session s
        LEFT JOIN Interruption i ON s.SessionID = i.SessionID
        WHERE s.status = 'completed'
    """
    params = []

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
def create_session():
    data = request.get_json()
    if not data or 'start_time' not in data:
        return jsonify({'error': 'start_time is required'}), 400

    start_time_raw = data['start_time']
    
    try:
        # Attempt to parse as ISO datetime
        dt = datetime.fromisoformat(start_time_raw.replace('Z', '+00:00'))
        date_part = dt.strftime('%Y-%m-%d')
        time_part = dt.strftime('%H:%M:%S')
    except ValueError:
        # Fallback if just time is provided
        date_part = datetime.now().strftime('%Y-%m-%d')
        time_part = start_time_raw

    conn = get_db()
    cursor = conn.cursor()

    # Check if a running session already exists
    cursor.execute("SELECT SessionID FROM Session WHERE status = 'running'")
    if cursor.fetchone() is not None:
        conn.close()
        return jsonify({'error': 'A running session already exists'}), 409

    # Insert new session
    cursor.execute(
        "INSERT INTO Session (date, start_time, status) VALUES (?, ?, ?)",
        (date_part, time_part, 'running')
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'sessionID': session_id,
        'start_time': start_time_raw,
        'status': 'running'
    }), 201

@app.route('/sessions/<int:session_id>', methods=['PATCH'])
def update_session(session_id):
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
    session = cursor.fetchone()

    if not session:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404

    current_status = session['status']

    # Validate transition
    if current_status in ['completed', 'stopped_early']:
        conn.close()
        return jsonify({'error': 'Cannot update a completed or stopped session'}), 409
        
    if current_status == new_status:
        conn.close()
        return jsonify({'error': f'Session is already {new_status}'}), 409

    # Update session
    end_time = data.get('end_time', session['end_time'])
    duration = data.get('duration', session['duration'])

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
def log_interruption(session_id):
    data = request.get_json()
    if not data or 'timestamp' not in data:
        return jsonify({'error': 'timestamp is required'}), 400

    timestamp = data['timestamp']

    conn = get_db()
    cursor = conn.cursor()

    # Verify session exists and is running
    cursor.execute("SELECT status FROM Session WHERE SessionID = ?", (session_id,))
    session = cursor.fetchone()

    if not session:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404

    if session['status'] != 'running':
        conn.close()
        return jsonify({'error': 'Cannot log interruption for a non-running session'}), 409

    # Insert interruption
    cursor.execute(
        "INSERT INTO Interruption (SessionID, timestamp) VALUES (?, ?)",
        (session_id, timestamp)
    )
    interruption_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'interruptionID': interruption_id,
        'timestamp': timestamp
    }), 201

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=False, port=5000)
