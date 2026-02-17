import sqlite3
import os

db_path = 'positions.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check tables
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = cursor.fetchall()
    print('Tables:', tables)

    # Check signal_history table
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    count = cursor.fetchone()[0]
    print('Signal history records:', count)

    # Check latest records
    cursor.execute('SELECT * FROM signal_history ORDER BY id DESC LIMIT 5')
    records = cursor.fetchall()
    print('Latest records:', records)

    # Check yesterday's records
    cursor.execute("SELECT COUNT(*) FROM signal_history WHERE signal_date = date('now', '-1 day')")
    yesterday_count = cursor.fetchone()[0]
    print('Yesterday records:', yesterday_count)

    # Check today's records
    cursor.execute("SELECT COUNT(*) FROM signal_history WHERE signal_date = date('now')")
    today_count = cursor.fetchone()[0]
    print('Today records:', today_count)

    conn.close()
else:
    print('❌ Database not found')