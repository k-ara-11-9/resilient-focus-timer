import sqlite3
import os

DB_NAME = 'focus_timer.db'

def run_migration():
    print(f"Connecting to {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    
    # Enable foreign key constraints for this connection
    conn.execute("PRAGMA foreign_keys = ON;")
    
    cursor = conn.cursor()
    
    print("Creating User table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS User (
        UserID INTEGER PRIMARY KEY AUTOINCREMENT
    );
    """)
    
    print("Creating Session table...")
    # Note: Using TEXT for status without a CHECK constraint as requested to avoid adding unlisted constraints.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Session (
        SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
        UserID INTEGER,
        date DATE NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME,
        duration INTEGER,
        status TEXT NOT NULL,
        FOREIGN KEY (UserID) REFERENCES User(UserID)
    );
    """)
    
    print("Creating Interruption table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Interruption (
        InterruptionID INTEGER PRIMARY KEY AUTOINCREMENT,
        SessionID INTEGER NOT NULL,
        timestamp DATETIME NOT NULL,
        FOREIGN KEY (SessionID) REFERENCES Session(SessionID)
    );
    """)
    
    conn.commit()
    conn.close()
    print("Migration successful! All tables created.")

if __name__ == '__main__':
    run_migration()
