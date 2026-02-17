import sqlite3

# Check recent signals with correct schema
conn = sqlite3.connect('positions.db')
cursor = conn.cursor()

# Check recent signals
cursor.execute('SELECT id, symbol, signal_date, score, pattern, price, reason, executed FROM signal_history ORDER BY id DESC LIMIT 10')
signals = cursor.fetchall()

print('Recent Signal History (10 records):')
for signal in signals:
    print(f'ID: {signal[0]}, Symbol: {signal[1]}, Date: {signal[2]}, Score: {signal[3]}, Pattern: {signal[4]}')
    print(f'  Price: ${signal[5]:.2f}, Reason: {signal[6]}, Executed: {signal[7]}')

# Check current positions
cursor.execute('SELECT id, symbol, entry_price, quantity, remaining_qty, stop_loss FROM positions WHERE status="open"')
positions = cursor.fetchall()

print(f'\nCurrent Open Positions ({len(positions)}):')
for pos in positions:
    print(f'ID: {pos[0]}, Symbol: {pos[1]}, Entry: ${pos[2]:.2f}, Qty: {pos[3]}, Remaining: {pos[4]}, Stop: ${pos[5]:.2f}')

# Check if there are any recent valid signals
cursor.execute('SELECT COUNT(*) FROM signal_history WHERE score >= 2.0 AND signal_date >= "2026-01-20"')
valid_signals = cursor.fetchone()[0]
print(f'\nValid signals (score >= 2.0) in last 24h: {valid_signals}')

conn.close()