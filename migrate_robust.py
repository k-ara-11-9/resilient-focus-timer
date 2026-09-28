import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.environ.get('FOCUS_TIMER_DB', os.path.join(BASE_DIR, 'focus_timer.db'))

def migrate():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"Connecting to {DB_NAME}")

    try:
        # Check if legacy 'user' table exists and needs migration
        cursor.execute("PRAGMA table_info(user)")
        cols = [col[1] for col in cursor.fetchall()]
        
        if 'name' in cols:
            print("Legacy 'user' table detected. Migrating data...")
            
            # Create the NEW User table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS User_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            ''')
            
            # Copy data over
            cursor.execute('''
                INSERT INTO User_new (id, username, email, password_hash)
                SELECT id, name, email, password FROM user
            ''')
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE user")
            cursor.execute("ALTER TABLE User_new RENAME TO User")
            print("Successfully migrated 'user' to 'User' with correct columns.")
            
        else:
            print("'User' table appears to be already migrated.")

        # Check if legacy 'session' table exists
        cursor.execute("PRAGMA table_info(session)")
        cols = [col[1] for col in cursor.fetchall()]
        
        if 'id' in cols and 'SessionID' not in cols:
            print("Legacy 'session' table detected. Migrating data...")
            
            # Create the NEW Session table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Session_new (
                    SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    date DATE NOT NULL,
                    start_time TIME NOT NULL,
                    end_time TIME,
                    duration INTEGER,
                    focus_duration INTEGER,
                    status TEXT NOT NULL,
                    paused_ms INTEGER DEFAULT 0,
                    last_pause_start_iso TEXT,
                    task_name TEXT,
                    tags TEXT,
                    FOREIGN KEY (user_id) REFERENCES User(id)
                )
            ''')
            
            # Copy data over
            cursor.execute('''
                INSERT INTO Session_new (
                    SessionID, user_id, date, start_time, end_time, duration, status
                )
                SELECT id, user_id, date, start_time, end_time, duration, status FROM session
            ''')
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE session")
            cursor.execute("ALTER TABLE Session_new RENAME TO Session")
            print("Successfully migrated 'session' to 'Session' with correct columns.")
        else:
            print("'Session' table appears to be already migrated.")
            
            # Ensure new columns exist in case it was partially migrated
            for col, col_type in [
                ("focus_duration", "INTEGER"),
                ("paused_ms", "INTEGER DEFAULT 0"),
                ("last_pause_start_iso", "TEXT"),
                ("task_name", "TEXT"),
                ("tags", "TEXT")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE Session ADD COLUMN {col} {col_type}")
                    print(f"Added missing column {col} to Session")
                except sqlite3.OperationalError:
                    pass

        # Check legacy 'interruption'
        cursor.execute("PRAGMA table_info(interruption)")
        cols = [col[1] for col in cursor.fetchall()]
        
        if 'id' in cols and 'InterruptionID' not in cols:
            print("Legacy 'interruption' table detected. Migrating data...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Interruption_new (
                    InterruptionID INTEGER PRIMARY KEY AUTOINCREMENT,
                    SessionID INTEGER NOT NULL,
                    user_id INTEGER,
                    timestamp DATETIME NOT NULL,
                    FOREIGN KEY (SessionID) REFERENCES Session(SessionID),
                    FOREIGN KEY (user_id) REFERENCES User(id)
                )
            ''')
            cursor.execute('''
                INSERT INTO Interruption_new (InterruptionID, SessionID, user_id, timestamp)
                SELECT id, session_id, user_id, timestamp FROM interruption
            ''')
            cursor.execute("DROP TABLE interruption")
            cursor.execute("ALTER TABLE Interruption_new RENAME TO Interruption")
            print("Successfully migrated 'interruption' to 'Interruption'.")

        conn.commit()
        print("All migrations finished successfully!")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
