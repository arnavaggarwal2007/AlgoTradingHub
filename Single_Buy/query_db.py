import sqlite3

# Connect to the database
conn = sqlite3.connect('positions.db')
cursor = conn.cursor()

# Get table names
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
print('Tables:', tables)

# Get schema for each table
for table_name in tables:
    table = table_name[0]
    cursor.execute(f'PRAGMA table_info({table})')
    columns = cursor.fetchall()
    print(f'\n{table} table schema:')
    for col in columns:
        print(f'  {col[1]}: {col[2]}')

# Get some sample data from positions table
if ('positions',) in tables:
    cursor.execute('SELECT COUNT(*) FROM positions')
    count = cursor.fetchone()[0]
    print(f'\nTotal positions: {count}')

    if count > 0:
        cursor.execute('SELECT * FROM positions LIMIT 5')
        rows = cursor.fetchall()
        print('\nSample positions:')
        for row in rows:
            print(row)

# Get signal history data
if ('signal_history',) in tables:
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    count = cursor.fetchone()[0]
    print(f'\nTotal signals: {count}')

    if count > 0:
        cursor.execute('SELECT * FROM signal_history ORDER BY signal_date DESC LIMIT 5')
        rows = cursor.fetchall()
        print('\nRecent signals:')
        for row in rows:
            print(row)

conn.close()