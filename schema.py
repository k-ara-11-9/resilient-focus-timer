"""
Single source of truth for the focus_timer database schema.

Used by:
  - app.py       (init_db on startup)
  - migrate.py   (CLI migration tool)
  - conftest.py  (test DB setup)
"""

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS User (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Session (
        SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date DATE NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME,
        duration INTEGER,
        focus_duration INTEGER,
        status TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES User(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Interruption (
        InterruptionID INTEGER PRIMARY KEY AUTOINCREMENT,
        SessionID INTEGER NOT NULL,
        user_id INTEGER,
        timestamp DATETIME NOT NULL,
        FOREIGN KEY (SessionID) REFERENCES Session(SessionID),
        FOREIGN KEY (user_id) REFERENCES User(id)
    )
    """,
]


def create_tables(conn):
    """Execute all schema DDL statements on the given connection.

    Uses CREATE TABLE IF NOT EXISTS so it is safe to call repeatedly
    against an existing database.
    """
    conn.execute("PRAGMA foreign_keys = ON;")
    for stmt in SCHEMA_SQL:
        conn.execute(stmt)
    conn.commit()
