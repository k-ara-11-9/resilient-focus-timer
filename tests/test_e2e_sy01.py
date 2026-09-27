import subprocess
import time
import sqlite3
from playwright.sync_api import sync_playwright
import sys

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')




def test_e2e_sy01(temp_db):
    print("Starting Flask server for E2E tests...")
    env = dict(os.environ, TEST_DB_PATH=temp_db, FLASK_RUN_PORT='5005')
    server = subprocess.Popen([sys.executable, APP_PATH], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            print("=== TEST: No network calls during active session ===")
            
            external_calls = []
            local_fetch_calls = []
            monitoring_local_fetch = False
            
            def on_request(request):
                from urllib.parse import urlparse
                parsed = urlparse(request.url)
                
                # Check for external domains (ignore data:/about: etc)
                if parsed.scheme in ['http', 'https']:
                    if parsed.hostname not in ['127.0.0.1', 'localhost']:
                        external_calls.append(f"{request.resource_type} to {request.url}")
                    elif monitoring_local_fetch and request.resource_type in ["fetch", "xhr"]:
                        local_fetch_calls.append(f"{request.method} {request.url}")
            
            page.on("request", on_request)
            
            page.goto('http://127.0.0.1:5005/')
            time.sleep(1)
            if '/login' in page.url:
                page.locator('#username').fill('testuser')
                page.locator('#password').fill('testpass')
                page.locator('button[type="submit"]').click()
                time.sleep(1)
            time.sleep(1)
            
            # Start timer
            page.click('button:has-text("Start Timer")')
            
            # Wait a bit for the POST /sessions request to finish and timer to establish
            page.wait_for_selector('button:has-text("Pause")')
            time.sleep(1)
            
            # Now we monitor local fetch/xhr requests during the active phase
            monitoring_local_fetch = True
            
            print("Timer is running. Waiting 5 seconds to monitor network traffic...")
            time.sleep(5)
            
            print(f"Captured external network calls during whole flow: {external_calls}")
            assert len(external_calls) == 0, f"Expected 0 external network calls, but got: {external_calls}"
            
            print(f"Captured local fetch/xhr calls during active phase: {local_fetch_calls}")
            assert len(local_fetch_calls) == 0, f"Expected 0 local fetch/xhr calls, but got: {local_fetch_calls}"
            
            browser.close()
            print("\nAll E2E tests passed! The timer correctly runs entirely locally after starting.")
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

