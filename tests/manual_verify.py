import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def signup(username, email, password):
    r = requests.post(f"{BASE_URL}/auth/signup", json={
        "username": username,
        "email": email,
        "password": password
    })
    if r.status_code == 201:
        print(f"Signup {username} success.")
    elif r.status_code == 409:
        print(f"Signup {username} conflict (already exists), continuing.")
    else:
        print(f"Signup {username} failed: {r.status_code} {r.text}")
        sys.exit(1)

def login(session, username, password):
    r = session.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": password
    })
    if r.status_code == 200:
        print(f"Login {username} success.")
    else:
        print(f"Login {username} failed: {r.status_code} {r.text}")
        sys.exit(1)

def run():
    checks_passed = 0
    checks_failed = []

    def check(condition, desc, expected, actual, body=""):
        nonlocal checks_passed
        if condition:
            checks_passed += 1
            print(f"[PASS] {desc}")
        else:
            checks_failed.append(f"{desc} (Expected {expected}, got {actual}. Body: {body})")
            print(f"[FAIL] {desc}")

    # 1. Sign up Alice and Bob
    signup("alice", "alice@example.com", "pass123")
    signup("bob", "bob@example.com", "pass123")

    # 2. Log in as Alice
    alice_session = requests.Session()
    login(alice_session, "alice", "pass123")

    # 3. Create session for Alice
    r = alice_session.post(f"{BASE_URL}/sessions", json={
        "start_time": "10:00:00"
    })
    if r.status_code == 409:
        # If Alice already has a running session, we'll try to retrieve it so the script can proceed
        r_get = alice_session.get(f"{BASE_URL}/sessions?status=running")
        if r_get.status_code == 200 and len(r_get.json()) > 0:
            alice_sess_id = r_get.json()[0]["sessionID"]
            print(f"Found existing running session for Alice: {alice_sess_id}")
        else:
            print(f"Failed to create or find session for Alice. POST returned: {r.status_code} {r.text}")
            sys.exit(1)
    elif r.status_code == 201:
        alice_sess_id = r.json()["sessionID"]
        print(f"Created session for Alice: {alice_sess_id}")
    else:
        print(f"Failed to create session for Alice: {r.status_code} {r.text}")
        sys.exit(1)

    # 4. Log in as Bob
    bob_session = requests.Session()
    login(bob_session, "bob", "pass123")

    # 5. Bob GET Alice's session
    r = bob_session.get(f"{BASE_URL}/sessions/{alice_sess_id}")
    check(r.status_code == 403, "Bob GET Alice's session -> 403", 403, r.status_code, r.text)

    # 6. Bob PATCH Alice's session
    r = bob_session.patch(f"{BASE_URL}/sessions/{alice_sess_id}", json={"status": "completed"})
    check(r.status_code == 403, "Bob PATCH Alice's session -> 403", 403, r.status_code, r.text)

    # 7. Bob POST interruption to Alice's session
    r = bob_session.post(f"{BASE_URL}/sessions/{alice_sess_id}/interruptions", json={"timestamp": "10:15:00"})
    check(r.status_code == 403, "Bob POST interruption -> 403", 403, r.status_code, r.text)

    # 8. No session GET Alice's session
    r = requests.get(f"{BASE_URL}/sessions/{alice_sess_id}")
    check(r.status_code == 401, "No session GET Alice's session -> 401", 401, r.status_code, r.text)

    # 9. Alice GET her own session
    r = alice_session.get(f"{BASE_URL}/sessions/{alice_sess_id}")
    success = r.status_code == 200 and r.json().get("sessionID") == alice_sess_id
    check(success, "Alice GET her own session -> 200 and correct data", 200, r.status_code, r.text)

    # 10. Summary
    print("\n--- SUMMARY ---")
    print(f"Checks passed: {checks_passed}/5")
    if checks_failed:
        for f in checks_failed:
            print(f"  - {f}")
    else:
        print("All checks passed successfully!")

if __name__ == '__main__':
    run()
