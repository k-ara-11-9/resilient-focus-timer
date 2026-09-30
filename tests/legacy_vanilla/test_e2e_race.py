import subprocess
import time
import sqlite3
from playwright.sync_api import sync_playwright
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')



def test_e2e_race(temp_db):
    print("Starting Flask server for race condition test...")
    
    env = dict(os.environ, TEST_DB_PATH=temp_db, FLASK_RUN_PORT='5005', SECRET_KEY='e2e_test_secret')
    server = subprocess.Popen([sys.executable, APP_PATH], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            print("=== TEST: Race condition in completeSession ===")
            page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
            page.goto('http://127.0.0.1:5005/')
            time.sleep(1)
            from tests.legacy_vanilla.e2e_helpers import e2e_login
            e2e_login(page)
            
            # Start a session
            page.locator('button.start-button').click()
            page.wait_for_selector('button.start-button:has-text("Pause")')
            
            # Get original session ID
            original_session_id = page.evaluate("currentSessionId")
            print(f"Started session. Original ID: {original_session_id}")
            
            # Inject a delay in notificationSound.play to simulate background-tab throttling
            page.evaluate("""
                window.originalPlay = notificationSound.play;
                notificationSound.play = function() {
                    return new Promise(resolve => setTimeout(() => resolve(), 2000));
                };
            """)
            
            # Setup route interception to capture the PATCH request URL
            patch_urls = []
            def handle_route(route):
                if route.request.method == 'PATCH':
                    patch_urls.append(route.request.url)
                route.continue_()
            
            page.route("**/sessions/*", handle_route)
            
            # Trigger completeSession and immediately simulate a new session starting
            # while the completion is delayed on the notificationSound.play() await.
            simulated_new_id = 999
            page.evaluate(f"""
                completeSession(); // Don't await it
                currentSessionId = {simulated_new_id};
            """)
            print(f"Simulated a new session starting, currentSessionId is now: {simulated_new_id}")
            
            # Wait for the delayed PATCH request to fire (the delay is 2 seconds, wait up to 4)
            page.wait_for_timeout(3000)
            
            assert len(patch_urls) > 0, "No PATCH request fired!"
            last_patch_url = patch_urls[-1]
            
            print(f"PATCH request fired to: {last_patch_url}")
            
            # Check if the URL contains the original session ID or the simulated new one
            if str(simulated_new_id) in last_patch_url:
                raise AssertionError(f"Bug detected: The PATCH request was sent to the WRONG session ID ({simulated_new_id})")
            elif str(original_session_id) in last_patch_url:
                print("Test passed! The PATCH request was sent to the original session ID.")
            else:
                raise AssertionError(f"Unexpected PATCH URL: {last_patch_url}")
            
            browser.close()
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

