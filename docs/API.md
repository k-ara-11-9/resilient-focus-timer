# Resilient Focus Timer API

All endpoints require authentication (except `/auth/login` and `/auth/signup`). Authentication is maintained via session cookies.

## Authentication

### `POST /auth/signup`
Creates a new user account.
- **Request Body**:
  ```json
  {
    "username": "testuser",
    "email": "test@example.com",
    "password": "mypassword"
  }
  ```
- **Response**: 
  - `201 Created`: `{"message": "User created successfully", "user_id": 1}`
  - `400 Bad Request`: `{"error": "Missing required fields: ..."}`
  - `409 Conflict`: `{"error": "username or email already taken"}`

### `POST /auth/login`
Authenticates a user and sets a session cookie.
- **Request Body**:
  ```json
  {
    "username": "testuser",
    "password": "mypassword"
  }
  ```
- **Response**:
  - `200 OK`: `{"message": "Logged in successfully"}`
  - `401 Unauthorized`: `{"error": "invalid credentials"}`

### `POST /auth/logout`
Clears the session cookie.
- **Response**: `200 OK`: `{"message": "Logged out successfully"}`

## Sessions

### `GET /sessions`
Retrieves a list of completed sessions, optionally filtered by date. Or, retrieves the currently running session.
- **Query Parameters**:
  - `status=running`: If provided, returns an array with the single currently running session (or an empty array).
  - `date_from=YYYY-MM-DD` (optional)
  - `date_to=YYYY-MM-DD` (optional)
- **Response (`?status=running`)**:
  ```json
  [
    {
      "sessionID": 1,
      "date": "2026-09-29",
      "start_time": "10:00:00",
      "status": "running",
      "focus_duration": 1500,
      "paused_ms": 0,
      "last_pause_start_iso": null
    }
  ]
  ```
- **Response (completed sessions)**:
  ```json
  [
    {
      "sessionID": 1,
      "date": "2026-09-29",
      "start_time": "10:00:00",
      "duration": 1500,
      "status": "completed",
      "task_name": "Reviewing PRs",
      "tags": "[\"#work\", \"#code\"]",
      "interruption_count": 2
    }
  ]
  ```

### `POST /sessions`
Creates a new session. Returns `409 Conflict` if a running session already exists.
- **Request Body**:
  ```json
  {
    "start_time": "2026-09-29T10:00:00.000Z",
    "focus_duration": 1500,
    "task_name": "Reviewing PRs",
    "tags": "[\"#work\", \"#code\"]"
  }
  ```
- **Response (`201 Created`)**:
  ```json
  {
    "sessionID": 2,
    "date": "2026-09-29",
    "start_time": "10:00:00",
    "status": "running",
    "focus_duration": 1500,
    "paused_ms": 0,
    "last_pause_start_iso": null
  }
  ```

### `GET /sessions/<session_id>`
Retrieves a specific session.
- **Response (`200 OK`)**:
  ```json
  {
    "sessionID": 2,
    "date": "2026-09-29",
    "start_time": "10:00:00",
    "end_time": "10:25:00",
    "duration": 1500,
    "status": "completed"
  }
  ```

### `PATCH /sessions/<session_id>`
Updates the status, duration, or pause state of a session. Cannot update a session that is already `completed` or `stopped_early`.
- **Request Body (example complete)**:
  ```json
  {
    "status": "completed",
    "end_time": "10:25:00",
    "duration": 1500
  }
  ```
- **Request Body (example pause)**:
  ```json
  {
    "status": "paused",
    "last_pause_start_iso": "2026-09-29T10:10:00.000Z"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "sessionID": 2,
    "status": "completed",
    "duration": 1500,
    "end_time": "10:25:00",
    "focus_duration": 1500,
    "paused_ms": 0,
    "last_pause_start_iso": null
  }
  ```

## Interruptions

### `POST /sessions/<session_id>/interruptions`
Logs a new interruption for a running session.
- **Request Body**:
  ```json
  {
    "timestamp": "2026-09-29T10:05:00.000Z"
  }
  ```
- **Response (`201 Created`)**:
  ```json
  {
    "interruptionID": 1,
    "timestamp": "2026-09-29T10:05:00.000Z"
  }
  ```

### `GET /sessions/<session_id>/interruptions`
Retrieves all interruptions for a specific session.
- **Response (`200 OK`)**:
  ```json
  [
    {
      "interruptionID": 1,
      "timestamp": "2026-09-29T10:05:00.000Z"
    }
  ]
  ```

## Analytics

### `GET /analytics/daily`
Retrieves daily aggregated focus minutes and interruptions.
- **Query Parameters**: `start=YYYY-MM-DD`, `end=YYYY-MM-DD` (defaults to last 7 days).
- **Response (`200 OK`)**:
  ```json
  [
    {
      "date": "2026-09-29",
      "focus_minutes": 25,
      "interruptions": 2
    }
  ]
  ```

### `GET /analytics/heatmap`
Retrieves a distribution of focus sessions across hours of the day (0-23).
- **Query Parameters**: `start=YYYY-MM-DD`, `end=YYYY-MM-DD` (defaults to last 7 days).
- **Response (`200 OK`)**:
  ```json
  [
    {
      "hour": 10,
      "count": 1
    }
  ]
  ```

### `GET /analytics/summary`
Retrieves high-level summary metrics for the dashboard.
- **Response (`200 OK`)**:
  ```json
  {
    "streak": 3,
    "consistency_pct": 80,
    "active_days_last7": 5,
    "weekly_minutes": [
      {
        "date": "2026-09-29",
        "focus_minutes": 25
      }
    ],
    "tags_distribution": {
      "#work": 25,
      "#code": 25
    }
  }
  ```
