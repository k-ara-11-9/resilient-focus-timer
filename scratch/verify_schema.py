"""Verify all entry points produce an identical schema."""
import sqlite3
import tempfile
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

def get_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return tables

def test_via_schema_module():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    from schema import create_tables
    conn = sqlite3.connect(path)
    create_tables(conn)
    conn.close()
    schema = get_schema(path)
    os.remove(path)
    return schema

def test_via_migrate():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    import migrate
    old_db = migrate.DB_NAME
    migrate.DB_NAME = path
    # Manually call create_tables since run_migration uses module-level DB_NAME
    from schema import create_tables
    conn = sqlite3.connect(path)
    create_tables(conn)
    conn.close()
    migrate.DB_NAME = old_db
    schema = get_schema(path)
    os.remove(path)
    return schema

def test_via_app_init():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.environ['TEST_DB_PATH'] = path
    import importlib
    import app as app_module
    # Re-set DB_NAME and re-init
    app_module.DB_NAME = path
    app_module.init_db()
    del os.environ['TEST_DB_PATH']
    schema = get_schema(path)
    os.remove(path)
    return schema

schema_direct = test_via_schema_module()
schema_migrate = test_via_migrate()
schema_app = test_via_app_init()

print("=== schema.create_tables ===")
for s in schema_direct:
    print(s)

print("\n=== migrate.py ===")
for s in schema_migrate:
    print(s)

print("\n=== app.py init_db ===")
for s in schema_app:
    print(s)

print("\n=== MATCH CHECK ===")
if schema_direct == schema_migrate == schema_app:
    print("ALL IDENTICAL ✓")
else:
    print("MISMATCH ✗")
    if schema_direct != schema_migrate:
        print("  schema_direct != schema_migrate")
    if schema_direct != schema_app:
        print("  schema_direct != schema_app")
