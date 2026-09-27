import sqlite3
c = sqlite3.connect('focus_timer.db')
c.execute('INSERT INTO User (username, email, password_hash) VALUES ("dummy", "dummy@example.com", "hash")')
c.execute('INSERT INTO Session (user_id, date, start_time, duration, status) VALUES (1, "2023-01-01", "10:00:00", 25, "completed")')
c.execute('INSERT INTO Interruption (SessionID, user_id, timestamp) VALUES (1, 1, "2023-01-01T10:05:00")')
c.commit()
print("Inserted dummy data")
