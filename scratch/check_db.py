import sqlite3
c = sqlite3.connect('focus_timer.db')
print('Row counts in focus_timer.db:')
print('User:', c.execute('SELECT COUNT(*) FROM User').fetchone()[0])
print('Session:', c.execute('SELECT COUNT(*) FROM Session').fetchone()[0])
print('Interruption:', c.execute('SELECT COUNT(*) FROM Interruption').fetchone()[0])
