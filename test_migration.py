import sqlite3
import os

db_name = 'test_legacy.db'
if os.path.exists(db_name):
    os.remove(db_name)

conn = sqlite3.connect(db_name)
conn.execute('''CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)''')
conn.execute('''CREATE TABLE session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME,
    duration INTEGER,
    status TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id)
)''')
conn.execute('''CREATE TABLE interruption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    user_id INTEGER,
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
)''')
conn.execute("INSERT INTO user (name, email, password) VALUES ('admin', 'admin@test.com', 'pw')")
conn.commit()
conn.close()

# Now run migration
os.environ['FOCUS_TIMER_DB'] = db_name
import migrate_robust
migrate_robust.migrate()

# Verify
conn = sqlite3.connect(db_name)
try:
    conn.execute("SELECT username FROM User")
    print("MIGRATION SUCCESS!")
except Exception as e:
    print("MIGRATION FAILED:", e)
