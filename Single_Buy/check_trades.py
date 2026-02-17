import sqlite3
import datetime

conn = sqlite3.connect('positions.db')
cursor = conn.cursor()

# Get all positions
cursor.execute('SELECT * FROM positions ORDER BY entry_date DESC')
positions = cursor.fetchall()

print('=== CURRENT POSITIONS ===')
for pos in positions:
    print(f'ID {pos[0]}: {pos[1]} - Entry: ${pos[3]:.2f} - Qty: {pos[4]} - Remaining: {pos[5]} - Status: {pos[7]} - P/L: {pos[10] or 0:.2f}%')

# Get today's trades
today = datetime.date.today().isoformat()
cursor.execute('SELECT * FROM positions WHERE date(entry_date) = ? ORDER BY entry_date DESC', (today,))
today_trades = cursor.fetchall()

print('\n=== TODAY\'S TRADES ===')
for trade in today_trades:
    print(f'{trade[1]}: ${trade[3]:.2f} x {trade[4]} shares - Score: {trade[12] or 0:.1f} - Pattern: {trade[13] or "Unknown"}')

# Get signal history for today
cursor.execute('SELECT COUNT(*) FROM signal_history WHERE date(created_at) = ?', (today,))
signal_count = cursor.fetchone()[0]

print(f'\n=== TODAY\'S SIGNALS ===')
print(f'Total signals analyzed today: {signal_count}')

conn.close()