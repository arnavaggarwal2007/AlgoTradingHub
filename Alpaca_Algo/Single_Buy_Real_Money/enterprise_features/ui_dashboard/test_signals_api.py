import sqlite3

# Test the signals API logic directly (since Flask server may not be running)
conn = sqlite3.connect('../../db/positions.db')
cursor = conn.cursor()

# Test the same query used by the API
cursor.execute('''
    SELECT * FROM signal_history
    WHERE score > 0
    ORDER BY created_at DESC
    LIMIT 50
''')
signals = cursor.fetchall()

print(f'Database query returned {len(signals)} signals')

# Check if all signals have score > 0
valid_signals = [s for s in signals if s[3] > 0]  # score is at index 3
invalid_signals = [s for s in signals if s[3] <= 0]

print(f'Valid signals (score > 0): {len(valid_signals)}')
print(f'Invalid signals (score <= 0): {len(invalid_signals)}')

if len(signals) > 0:
    print('\nSample signals:')
    for i, signal in enumerate(signals[:3]):
        print(f'  {signal[1]}: Score {signal[3]}, Pattern: {signal[4]}')

conn.close()