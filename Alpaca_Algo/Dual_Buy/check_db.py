import sqlite3
import os

# Check database contents
db_path = 'db/positions_dual.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check positions table
    cursor.execute('SELECT COUNT(*) FROM positions')
    positions_count = cursor.fetchone()[0]
    print(f"Positions table: {positions_count} records")

    if positions_count > 0:
        cursor.execute('SELECT id, symbol, position_type, entry_date, entry_price, quantity, status FROM positions ORDER BY entry_date DESC LIMIT 5')
        positions = cursor.fetchall()
        print("Recent positions:")
        for pos in positions:
            print(f"  {pos}")

    # Check signal history table
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    signals_count = cursor.fetchone()[0]
    print(f"\nSignal history table: {signals_count} records")

    if signals_count > 0:
        cursor.execute('SELECT symbol, signal_date, score, pattern, executed FROM signal_history ORDER BY signal_date DESC LIMIT 5')
        signals = cursor.fetchall()
        print("Recent signals:")
        for sig in signals:
            print(f"  {sig}")

    conn.close()
else:
    print("Database file not found")