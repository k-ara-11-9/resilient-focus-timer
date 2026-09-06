import subprocess
import time
import sqlite3
from playwright.sync_api import sync_playwright
import sys
import os
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')

def setup_db_backdated_session():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Interruption")
    cursor.execute("DELETE FROM Session")
    
    # Backdate by 13 minutes (so 12 minutes remain)
    thirteen_mins_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=13)
    date_str = thirteen_mins_ago.strftime('%Y-%m-%d')
    time_str = thirteen_mins_ago.strftime('%H:%M:%S')
    
    cursor.execute('''
        INSERT INTO Session (UserID, date, start_time, status)
        VALUES (1, ?, ?, 'running')
    ''', (date_str, time_str))
    conn.commit()
    conn.close()

def run_tests():
    print("Starting Flask server for E2E tests...")
    server = subprocess.Popen([sys.executable, APP_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context() # Fresh context (no localStorage)
            page = context.new_page()
            
            print("=== TEST: Recovery of backdated session ===")
            setup_db_backdated_session()
            
            page.goto('http://127.0.0.1:5000/')
            
            # Wait for JS to load and parse the running session
            page.wait_for_selector('button:has-text("Pause")')
            time.sleep(1) # Let a tick happen
            
            displayed_time = page.locator('#timeDisplay').inner_text()
            print(f"Displayed countdown value: {displayed_time}")
            
            # 13 minutes have elapsed, so ~12 minutes should be remaining.
            # E.g. "11:59" or "12:00". Buggy behavior shows ~"24:59"
            minutes_str = displayed_time.split(':')[0]
            minutes = int(minutes_str)
            
            assert 11 <= minutes <= 12, f"Bug detected: Expected ~12 minutes remaining, but displayed time is {displayed_time}"
            
            print("\nTest passed! The displayed time accurately reflects the server start_time.")
            browser.close()
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

if __name__ == '__main__':
    run_tests()
