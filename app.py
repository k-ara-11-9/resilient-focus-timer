from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app) # Enable CORS for frontend

DB_NAME = 'focus_timer.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

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
    if new_status not in ['running', 'paused', 'completed']:
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
    if current_status == 'completed':
        conn.close()
        return jsonify({'error': 'Cannot update a completed session'}), 409
        
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

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
