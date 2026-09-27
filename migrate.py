"""
Database migration / initialization script.

Delegates to the canonical schema defined in schema.py so there is
exactly one source of truth for table definitions.
"""
import sqlite3
import os
from schema import create_tables

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'focus_timer.db')


def run_migration():
    print(f"Connecting to {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    create_tables(conn)
    conn.close()
    print("Migration successful! All tables created.")


if __name__ == '__main__':
    run_migration()
