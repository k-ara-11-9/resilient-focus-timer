import subprocess
import time
import requests
import sys

server = subprocess.Popen([sys.executable, 'app.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)

try:
    print("Test 1: Bad date format (expect 400)")
    res1 = requests.get('http://127.0.0.1:5000/sessions?date_from=bad-date')
    print(res1.status_code, res1.json())
    
    print("\nTest 2: Getting history (expect completed only, with counts)")
    res2 = requests.get('http://127.0.0.1:5000/sessions')
    print(res2.status_code)
    for s in res2.json()[:3]:  # Print first 3 to verify sorting (newest first)
        print(s)
        
    print("\nTest 3: Date filters (expect empty list if in past)")
    res3 = requests.get('http://127.0.0.1:5000/sessions?date_to=2020-01-01')
    print(res3.status_code, res3.json())
    
finally:
    server.terminate()
    server.wait()
