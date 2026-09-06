import subprocess
import time
import sqlite3
import requests
from playwright.sync_api import sync_playwright
import sys
import os
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Interruption")
    cursor.execute("DELETE FROM Session")
    conn.commit()
    conn.close()

def run_tests():
    print("Starting Flask server for resync test...")
    setup_db()
    server = subprocess.Popen([sys.executable, APP_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            print("=== TEST: Resync of legitimately ended session ===")
            page.goto('http://127.0.0.1:5000/')
            
            # Start a session (Device A)
            page.locator('#actionBtn').click()
            page.wait_for_selector('button:has-text("Pause")')
            
            # Get original session ID
            session_id = page.evaluate("currentSessionId")
            print(f"Device A started session ID: {session_id}")
            
            # Device B ends it via API (Stop Early)
            print("Device B stopping session early via API...")
            true_end_time = datetime.datetime.utcnow().strftime('%H:%M:%S')
            response = requests.patch(f"http://127.0.0.1:5000/sessions/{session_id}", json={
                "status": "stopped_early",
                "end_time": true_end_time,
                "duration": 0
            })
            assert response.status_code == 200, f"Device B failed to stop session: {response.text}"
            
            # Device A runs loadState() (e.g. by page reload or visibility change)
            print("Device A re-running loadState() via page reload...")
            page.reload()
            time.sleep(1) # Wait for loadState to complete fetching
            
            # Check the UI state on Device A
            action_btn_text = page.locator('#actionBtn').inner_text()
            print(f"Device A action button text is: {action_btn_text}")
            
            if action_btn_text == "Resume":
                raise AssertionError("Bug detected: Device A reverted to 'paused' instead of 'idle'. 'Resume' button is a dead-end.")
            elif action_btn_text == "Start Timer":
                print("Test passed! Device A successfully reset to idle.")
            else:
                raise AssertionError(f"Unexpected button text: {action_btn_text}")
            
            browser.close()
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

if __name__ == '__main__':
    run_tests()
