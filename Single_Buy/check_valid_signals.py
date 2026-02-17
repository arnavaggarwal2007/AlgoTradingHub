import sqlite3

# Check the valid signals from last 24h
conn = sqlite3.connect('positions.db')
cursor = conn.cursor()

# Get all valid signals from last 24h
cursor.execute('SELECT id, symbol, signal_date, score, pattern, price, reason, executed FROM signal_history WHERE score >= 2.0 AND signal_date >= "2026-01-20" ORDER BY score DESC')
valid_signals = cursor.fetchall()

print(f'Valid Signals (score >= 2.0) in last 24h: {len(valid_signals)}')
print('=' * 80)

for signal in valid_signals:
    print(f'ID: {signal[0]}, Symbol: {signal[1]}, Date: {signal[2]}, Score: {signal[3]}')
    print(f'  Pattern: {signal[4]}, Price: ${signal[5]:.2f}')
    print(f'  Reason: {signal[6]}, Executed: {signal[7]}')
    print('-' * 40)

# Check for pattern vs touch signals
cursor.execute('SELECT pattern, COUNT(*) FROM signal_history WHERE score >= 2.0 AND signal_date >= "2026-01-20" GROUP BY pattern')
pattern_counts = cursor.fetchall()

print(f'\nSignal Type Breakdown:')
for pattern, count in pattern_counts:
    print(f'  {pattern}: {count} signals')

conn.close()