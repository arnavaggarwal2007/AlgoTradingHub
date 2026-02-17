import sqlite3
import json
from datetime import datetime, timedelta

conn = sqlite3.connect('positions.db')
cursor = conn.cursor()

# Get recent signal history (last 6 hours)
six_hours_ago = (datetime.now() - timedelta(hours=6)).isoformat()
cursor.execute('SELECT * FROM signal_history WHERE created_at > ? ORDER BY created_at DESC LIMIT 20', (six_hours_ago,))
recent_signals = cursor.fetchall()

print('=== RECENT SIGNAL HISTORY (Last 6 Hours) ===')
for sig in recent_signals:
    data = json.loads(sig[2])  # signal_data column
    score = data.get('score', 0)
    passed = data.get('passed_all_checks', False)
    reason = data.get('failure_reason', 'N/A')
    print(f'{sig[1]} - {sig[3]} - Score: {score:.1f} - Passed: {passed} - Reason: {reason}')

conn.close()