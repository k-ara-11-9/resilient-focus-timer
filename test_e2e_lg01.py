import subprocess
import time
import sqlite3
from playwright.sync_api import sync_playwright
import sys

def setup_db():
    conn = sqlite3.connect('focus_timer.db')
    cursor = conn.cursor()
    # Delete all for clean test
    cursor.execute("DELETE FROM Interruption")
    cursor.execute("DELETE FROM Session")
    conn.commit()
    conn.close()

def seed_db(sessions):
    conn = sqlite3.connect('focus_timer.db')
    cursor = conn.cursor()
    for s in sessions:
        cursor.execute(
            "INSERT INTO Session (date, start_time, end_time, duration, status) VALUES (?, ?, ?, ?, ?)",
            (s['date'], s['start_time'], s.get('end_time'), s.get('duration'), s['status'])
        )
        sid = cursor.lastrowid
        for i in range(s.get('interruptions', 0)):
            cursor.execute("INSERT INTO Interruption (SessionID, timestamp) VALUES (?, ?)", (sid, s['start_time']))
    conn.commit()
    conn.close()

def run_tests():
    print("Starting Flask server for E2E tests...")
    server = subprocess.Popen([sys.executable, 'app.py'])
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # TEST: Loading state
            print("=== TEST: Loading State ===")
            route_event = []
            def delay_response(route):
                route_event.append(route)
            
            page.route("**/sessions*", delay_response)
            page.goto('http://127.0.0.1:5000/history', wait_until="domcontentloaded")
            
            loading_state = page.locator('#loadingState').inner_text()
            print(f"Loading state text: '{loading_state}'")
            assert "Loading..." in loading_state
            
            if route_event:
                route_event[0].continue_()
            
            # Wait for fetch to complete before moving to next test
            page.wait_for_selector('.history-list > div:not(#loadingState)')
            
            page.unroute("**/sessions*")
            
            # TEST: Empty state
            print("=== TEST: Empty State ===")
            setup_db()
            page.goto('http://127.0.0.1:5000/history')
            time.sleep(1)
            empty_state = page.locator('.empty-state').inner_text()
            print(f"Empty state text: '{empty_state}'")
            assert "No completed sessions" in empty_state
            
            # TEST 1, 2, 3
            print("\n=== TEST: History List (Completed, Paused, Ordering) ===")
            setup_db()
            import datetime
            today = datetime.datetime.now()
            yesterday = today - datetime.timedelta(days=1)
            older = today - datetime.timedelta(days=10)
            
            seed_db([
                # Oldest, completed, 2 interruptions
                {'date': older.strftime('%Y-%m-%d'), 'start_time': '10:00:00', 'end_time': '10:25:00', 'duration': 25, 'status': 'completed', 'interruptions': 2},
                # Yesterday, completed, 0 interruptions
                {'date': yesterday.strftime('%Y-%m-%d'), 'start_time': '11:00:00', 'end_time': '11:25:00', 'duration': 25, 'status': 'completed', 'interruptions': 0},
                # Today, paused (should not appear)
                {'date': today.strftime('%Y-%m-%d'), 'start_time': '12:00:00', 'status': 'paused', 'interruptions': 5}
            ])
            
            page.goto('http://127.0.0.1:5000/history')
            time.sleep(1)
            
            cards = page.locator('.history-card')
            count = cards.count()
            print(f"Found {count} history cards.")
            assert count == 2, f"Expected 2 cards, got {count}"
            
            # The newest completed should be first (Yesterday)
            card_0_date = cards.nth(0).locator('.history-date').inner_text()
            card_0_details = cards.nth(0).locator('.history-details').inner_text()
            print(f"Card 1: {card_0_date} | {card_0_details}")
            
            card_1_date = cards.nth(1).locator('.history-date').inner_text()
            card_1_details = cards.nth(1).locator('.history-details').inner_text()
            print(f"Card 2: {card_1_date} | {card_1_details}")
            
            assert "Yesterday" in card_0_date
            assert "0 interruptions" in card_0_details
            
            assert "Yesterday" not in card_1_date
            assert "Today" not in card_1_date
            assert "2 interruptions" in card_1_details
            
            browser.close()
            print("\nAll E2E tests passed!")
            
    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()

if __name__ == '__main__':
    run_tests()
