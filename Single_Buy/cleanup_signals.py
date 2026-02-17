import sqlite3

def cleanup_invalid_signals():
    """Remove all signals with score <= 0 from signal_history table"""

    conn = sqlite3.connect('positions.db')
    cursor = conn.cursor()

    # Check current count
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    total_before = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM signal_history WHERE score <= 0')
    invalid_count = cursor.fetchone()[0]

    print(f"Before cleanup: {total_before} total signals")
    print(f"Invalid signals to remove: {invalid_count}")

    # Remove invalid signals
    cursor.execute('DELETE FROM signal_history WHERE score <= 0')
    conn.commit()

    # Check after cleanup
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    total_after = cursor.fetchone()[0]

    print(f"After cleanup: {total_after} valid signals remaining")
    print(f"Removed: {invalid_count} invalid signals")

    # Show remaining signal distribution
    cursor.execute('SELECT score, COUNT(*) FROM signal_history GROUP BY score ORDER BY score DESC')
    score_dist = cursor.fetchall()
    print("\nRemaining signal distribution:")
    for score, count in score_dist:
        print(f"  Score {score}: {count} signals")

    conn.close()

if __name__ == "__main__":
    cleanup_invalid_signals()