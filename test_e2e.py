import subprocess
import time
from playwright.sync_api import sync_playwright
import sys

def run_tests():
    import sqlite3
    conn = sqlite3.connect('focus_timer.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Session")
    conn.commit()
    conn.close()

    print("Starting Flask server for E2E tests...")
    server = subprocess.Popen([sys.executable, 'app.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2) # wait for server to start
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://127.0.0.1:5000')
        
        print("Starting timer and checking if button disables...")
        page.locator('#actionBtn').evaluate("el => { el.click(); }")
        
        is_disabled = page.locator('#actionBtn').evaluate("el => el.disabled")
        print(f"Button disabled immediately after click: {is_disabled}")
        assert is_disabled, "Button did not disable during fetch"
        
        # Wait for the network request to finish and button to re-enable (become 'Pause')
        page.wait_for_selector('button:has-text("Pause")')
        is_disabled_after = page.locator('#actionBtn').evaluate("el => el.disabled")
        print(f"Button disabled after fetch completes: {is_disabled_after}")
        assert not is_disabled_after, "Button remained disabled after fetch"
        
        status = page.locator('#statusDisplay').inner_text()
        print(f"Status after start: {status}")
        
        print("Reloading page to test state restoration...")
        page.reload()
        time.sleep(1)
        
        status_after_reload = page.locator('#statusDisplay').inner_text()
        print(f"Status after reload: {status_after_reload}")
        
        has_paused_class = page.locator('.progress-ring__circle').evaluate("el => el.classList.contains('paused')")
        print(f"Circle has 'paused' class while running: {has_paused_class}")
        assert not has_paused_class, "Circle should not have paused class while running"
        
        print("Pausing timer...")
        page.locator('#actionBtn').dispatch_event('click')
        page.wait_for_selector('button:has-text("Resume")')
        
        status_paused = page.locator('#statusDisplay').inner_text()
        time_displayed_paused = page.locator('#timeDisplay').inner_text()
        
        print(f"Status after pause: {status_paused}")
        
        has_paused_class_now = page.locator('.progress-ring__circle').evaluate("el => el.classList.contains('paused')")
        print(f"Circle has 'paused' class while paused: {has_paused_class_now}")
        assert has_paused_class_now, "Circle should have paused class while paused"
        print(f"Time displayed when paused: {time_displayed_paused}")
        
        print("Waiting 30 seconds to check for drift while paused...")
        time.sleep(30)
        
        time_displayed_after_wait = page.locator('#timeDisplay').inner_text()
        print(f"Time displayed after wait (should be unchanged): {time_displayed_after_wait}")
        
        print("Resuming timer...")
        page.click('#actionBtn') # Click resume
        time.sleep(1.5) # Wait for a tick
        
        time_displayed_resumed = page.locator('#timeDisplay').inner_text()
        print(f"Time displayed shortly after resume: {time_displayed_resumed}")
        
        browser.close()
        
    print("Stopping server...")
    server.terminate()
    server.wait()

if __name__ == '__main__':
    run_tests()
