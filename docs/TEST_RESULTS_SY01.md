# SY-01 End-to-End Test Results

| Test Case | Description | Given / When / Then | Result | Key Output |
|-----------|-------------|---------------------|--------|------------|
| 1 | Verifies that no network calls are made to the backend while the timer is actively running. | **Given** the timer has been started successfully,<br>**When** the timer runs normally (unpaused),<br>**Then** no fetch/XHR requests are made to the server. | ✅ Pass | `Captured network calls during active phase: []` |
