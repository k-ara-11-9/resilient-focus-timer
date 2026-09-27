import subprocess
import time
import requests
import sys

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, 'app.py')
DB_PATH = os.path.join(BASE_DIR, 'focus_timer.db')

def test_get_history(temp_db):
    env = dict(os.environ, TEST_DB_PATH=temp_db, FLASK_RUN_PORT='5005')
    server = subprocess.Popen([sys.executable, APP_PATH], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    try:
        session = requests.Session()
        res_login = session.post('http://127.0.0.1:5005/auth/login', json={'username': 'testuser', 'password': 'testpass'})
        if res_login.status_code != 200:
            print("Login failed:", res_login.status_code, res_login.text)

        print("Test 1: Bad date format (expect 400)")
        res1 = session.get('http://127.0.0.1:5005/sessions?date_from=bad-date')
        print(res1.status_code, res1.json())
        
        print("\nTest 2: Getting history (expect completed only, with counts)")
        res2 = session.get('http://127.0.0.1:5005/sessions')
        print(res2.status_code)
        # Handle empty json gracefully since temp_db might be empty
        data = res2.json() if res2.status_code == 200 else []
        for s in data[:3]:  # Print first 3 to verify sorting (newest first)
            print(s)
            
        print("\nTest 3: Date filters (expect empty list if in past)")
        res3 = session.get('http://127.0.0.1:5005/sessions?date_to=2020-01-01')
        print(res3.status_code, res3.json())
        
    finally:
        server.terminate()
        server.wait()
