import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.environ.get('FOCUS_TIMER_DB', os.path.join(BASE_DIR, 'focus_timer.db'))

def migrate():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"Connecting to {DB_NAME}")
    
    # 1. Rename `user` columns
    try:
        cursor.execute("ALTER TABLE user RENAME COLUMN name TO username")
        print("Migrated user.name -> user.username")
    except sqlite3.OperationalError:
        print("user.username already exists or table doesn't exist.")

    try:
        cursor.execute("ALTER TABLE user RENAME COLUMN password TO password_hash")
        print("Migrated user.password -> user.password_hash")
    except sqlite3.OperationalError:
        print("user.password_hash already exists or table doesn't exist.")

    # 2. Rename `session` columns
    try:
        cursor.execute("ALTER TABLE session RENAME COLUMN id TO SessionID")
        print("Migrated session.id -> session.SessionID")
    except sqlite3.OperationalError:
        print("session.SessionID already exists or table doesn't exist.")

    # 3. Rename `interruption` columns
    try:
        cursor.execute("ALTER TABLE interruption RENAME COLUMN id TO InterruptionID")
        print("Migrated interruption.id -> interruption.InterruptionID")
    except sqlite3.OperationalError:
        print("interruption.InterruptionID already exists or table doesn't exist.")

    try:
        cursor.execute("ALTER TABLE interruption RENAME COLUMN session_id TO SessionID")
        print("Migrated interruption.session_id -> interruption.SessionID")
    except sqlite3.OperationalError:
        print("interruption.SessionID already exists or table doesn't exist.")

    # 4. Add new columns to `session`
    for col, col_type in [
        ("focus_duration", "INTEGER"),
        ("paused_ms", "INTEGER DEFAULT 0"),
        ("last_pause_start_iso", "TEXT"),
        ("task_name", "TEXT"),
        ("tags", "TEXT")
    ]:
        try:
            cursor.execute(f"ALTER TABLE session ADD COLUMN {col} {col_type}")
            print(f"Added {col} to session")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
