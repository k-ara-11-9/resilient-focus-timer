# LG-01 End-to-End Test Results

| Test Case | Description | Given / When / Then | Result | Key Output |
|-----------|-------------|---------------------|--------|------------|
| 1 | Validates that a completed session appears in the history list with correct date, duration, and interruption count. | **Given** a session is completed and logged,<br>**When** I navigate to the history screen,<br>**Then** a card appears matching the session data. | ✅ Pass | `Aug 26 | 25 min - 0 interruptions` |
| 2 | Ensures that paused or incomplete sessions are not displayed in the history. | **Given** a session is currently running or paused,<br>**When** I view the history list,<br>**Then** that session is completely hidden. | ✅ Pass | Expected 2 cards, got 2 |
| 3 | Verifies multiple completed sessions are ordered chronologically with the newest first. | **Given** multiple completed sessions across different dates,<br>**When** I view the history list,<br>**Then** the most recent session is shown at the top. | ✅ Pass | Card 1: `Aug 26`, Card 2: `Aug 25` |
| 4 | Checks the empty state when no completed sessions exist. | **Given** zero completed sessions in the database,<br>**When** I open the history screen,<br>**Then** an empty state message is shown. | ✅ Pass | `No completed sessions yet. Get focused!` |
