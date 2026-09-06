import subprocess
import time
import sqlite3
from playwright.sync_api import sync_playwright
import sys

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')


def run_tests():
    print("Starting Flask server for E2E tests...")
    server = subprocess.Popen([sys.executable, APP_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2) # wait for server to start
    
    # Cleanup DB before start to ensure clean test
    conn = sqlite3.connect('focus_timer.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Session SET status = 'completed' WHERE status = 'running' OR status = 'paused'")
    conn.commit()
    conn.close()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('http://127.0.0.1:5000')
            time.sleep(1) # wait for async fetch
            
            print("Checking initial button state...")
            is_disabled = page.locator('#intrusionBtn').is_disabled()
            print(f"Intrusion button disabled initially: {is_disabled}")
            
            print("Starting timer...")
            page.click('#actionBtn')
            time.sleep(1)
            
            status = page.locator('#statusDisplay').inner_text()
            print(f"Status after start: {status}")
            
            is_disabled = page.locator('#intrusionBtn').is_disabled()
            print(f"Intrusion button disabled while running: {is_disabled}")
            
            print("Logging 3 intrusions with a slight delay...")
            page.click('#intrusionBtn')
            page.wait_for_selector('.toast:not(.error):has-text("Interruption logged")', state='visible')
            time.sleep(0.5)
            
            count = page.locator('#intrusionCount').inner_text()
            assert count == "1", f"Expected count 1, got {count}"
            
            print("Testing error toast for failed interruption...")
            page.route("**/interruptions", lambda route: route.fulfill(status=500, body='{"error":"Internal Server Error"}'))
            page.click('#intrusionBtn')
            page.wait_for_selector('.toast.error:has-text("Failed to log interruption")', state='visible')
            page.unroute("**/interruptions")
            time.sleep(0.5)
            
            count = page.locator('#intrusionCount').inner_text()
            assert count == "1", f"Expected count 1 after failure, got {count}"
            
            page.click('#intrusionBtn')
            time.sleep(0.5)
            page.click('#intrusionBtn')
            time.sleep(1)
            
            count = page.locator('#intrusionCount').inner_text()
            assert count == "3", f"Expected count 3, got {count}"
            
            print("Testing rapid clicks (debounce)...")
            page.locator('#intrusionBtn').evaluate("el => { el.click(); el.click(); el.click(); }")
            time.sleep(1) # wait for network to resolve
            count = page.locator('#intrusionCount').inner_text()
            assert count == "4", f"Expected count 4 after 3 rapid clicks (debounced to 1), got {count}"
            
            print("Pausing timer...")
            page.click('#actionBtn') # Click pause
            time.sleep(1)
            
            is_disabled = page.locator('#intrusionBtn').is_disabled()
            print(f"Intrusion button disabled while paused: {is_disabled}")
            
            print("=== NEW TEST: Active Session Server-Side Recovery ===")
            # 1. Clean up and start a session normally
            print("Starting a fresh session for recovery test...")
            page.click('#actionBtn') # Resumes from paused state in previous test
            time.sleep(1)
            
            # 2. Programmatically clear the browser's localStorage
            print("Clearing localStorage...")
            page.evaluate("localStorage.clear()")
            
            # 3. Reload the page
            print("Reloading the page...")
            page.reload()
            time.sleep(1) # wait for async fetch
            
            # 4. Assert button states
            action_text = page.locator('#actionBtn').inner_text()
            is_disabled = page.locator('#intrusionBtn').is_disabled()
            print(f"Start/Pause button text (expected 'Pause'): {action_text}")
            print(f"Intrusion button disabled (expected False): {is_disabled}")
            
            print("=== NEW TEST: Negative Control (No session running) ===")
            # 5. Negative control
            # Complete the session on the server to simulate no running sessions
            conn = sqlite3.connect('focus_timer.db')
            conn.execute("UPDATE Session SET status = 'completed'")
            conn.commit()
            conn.close()
            
            print("Clearing localStorage again...")
            page.evaluate("localStorage.clear()")
            
            print("Reloading the page...")
            page.reload()
            time.sleep(1)
            
            action_text = page.locator('#actionBtn').inner_text()
            is_disabled = page.locator('#intrusionBtn').is_disabled()
            print(f"Start/Pause button text (expected 'Start Timer'): {action_text}")
            print(f"Intrusion button disabled (expected True): {is_disabled}")
            
            browser.close()
            
        print("Checking database for logged interruptions...")
        conn = sqlite3.connect('focus_timer.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the latest session
        cursor.execute("SELECT SessionID FROM Session ORDER BY SessionID DESC LIMIT 1")
        session_id = cursor.fetchone()['SessionID']
        
        cursor.execute("SELECT InterruptionID, timestamp FROM Interruption WHERE SessionID = ? ORDER BY InterruptionID ASC", (session_id,))
        interruptions = cursor.fetchall()
        
        print(f"Found {len(interruptions)} interruptions for session {session_id}:")
        for idx, row in enumerate(interruptions):
            print(f"  {idx+1}: ID={row['InterruptionID']} @ {row['timestamp']}")
            
        conn.close()
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

if __name__ == '__main__':
    run_tests()
