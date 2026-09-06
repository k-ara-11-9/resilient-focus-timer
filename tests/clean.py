# WARNING: This script deletes all session and interruption data from the database.
# Do not run this in a production environment unless you intend to wipe all data.
import sqlite3
conn = sqlite3.connect('focus_timer.db')
conn.execute('DELETE FROM Interruption')
conn.execute('DELETE FROM Session')
conn.commit()
conn.close()
