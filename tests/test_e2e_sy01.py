import subprocess
import time
import sqlite3
from playwright.sync_api import sync_playwright
import sys

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')


def setup_db():
    conn = sqlite3.connect('focus_timer.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Interruption")
    cursor.execute("DELETE FROM Session")
    conn.commit()
    conn.close()

def run_tests():
    print("Starting Flask server for E2E tests...")
    server = subprocess.Popen([sys.executable, APP_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            print("=== TEST: No network calls during active session ===")
            setup_db()
            page.goto('http://127.0.0.1:5000/')
            time.sleep(1)
            
            # Start timer
            page.click('button:has-text("Start Timer")')
            
            # Wait a bit for the POST /sessions request to finish and timer to establish
            page.wait_for_selector('button:has-text("Pause")')
            time.sleep(1)
            
            # Now we monitor network requests
            network_calls = []
            def on_request(request):
                # We only care about XHR/fetch requests to our backend API endpoints
                if request.resource_type in ["fetch", "xhr"]:
                    network_calls.append(f"{request.method} {request.url}")
            
            page.on("request", on_request)
            
            print("Timer is running. Waiting 5 seconds to monitor network traffic...")
            time.sleep(5)
            
            print(f"Captured network calls during active phase: {network_calls}")
            assert len(network_calls) == 0, f"Expected 0 network calls, but got: {network_calls}"
            
            browser.close()
            print("\nAll E2E tests passed! The timer correctly runs entirely locally after starting.")
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

if __name__ == '__main__':
    run_tests()
