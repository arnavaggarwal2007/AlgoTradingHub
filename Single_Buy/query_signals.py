import sqlite3

# Connect to the main database
conn = sqlite3.connect('rajat_alpha_v67.db')
cursor = conn.cursor()

# Get signal history count
cursor.execute('SELECT COUNT(*) FROM signal_history')
count = cursor.fetchone()[0]
print(f'Total signals: {count}')

# Get recent signals
cursor.execute('SELECT * FROM signal_history ORDER BY signal_date DESC LIMIT 10')
rows = cursor.fetchall()
print('\nRecent signals:')
for row in rows:
    print(row)

conn.close()