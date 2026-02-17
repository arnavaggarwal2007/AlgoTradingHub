import sqlite3
from datetime import datetime

def show_signals_dashboard():
    """Display today's active signals dashboard"""

    conn = sqlite3.connect('positions.db')
    cursor = conn.cursor()

    today = datetime.now().date().isoformat()
    print(f'TODAY\'S ACTIVE SIGNALS DASHBOARD - {today}')
    print('=' * 60)

    # Get valid signals for today (score > 0)
    cursor.execute('SELECT id, symbol, signal_date, score, pattern, price, reason, executed, created_at FROM signal_history WHERE signal_date = ? AND score > 0 ORDER BY score DESC, created_at DESC', (today,))
    valid_signals = cursor.fetchall()

    print(f'VALID SIGNALS TODAY: {len(valid_signals)}')
    print('-' * 60)

    if valid_signals:
        for i, signal in enumerate(valid_signals, 1):
            status = 'EXECUTED' if signal[7] else 'PENDING'
            pattern_type = 'Pattern' if 'Engulfing' in str(signal[4]) or 'Piercing' in str(signal[4]) else 'Touch'
            print(f'{i:2d}. {signal[1]:<6} | Score: {signal[3]:4.1f} | Type: {pattern_type:<7} | Pattern: {signal[4]:<12} | Status: {status}')

        print('\n' + '=' * 60)
        print('TOP EXECUTION CANDIDATES (by Score):')
        print('-' * 60)

        # Show top 5 pending signals
        pending_signals = [s for s in valid_signals if not s[7]][:5]
        for i, signal in enumerate(pending_signals, 1):
            pattern_type = 'Pattern' if 'Engulfing' in str(signal[4]) or 'Piercing' in str(signal[4]) else 'Touch'
            print(f'{i}. {signal[1]} (Score: {signal[3]:.1f}) - {pattern_type}: {signal[4]}')

        if not pending_signals:
            print('No pending signals - all have been executed!')

    else:
        print('No valid signals detected today yet.')

    # Check current positions
    cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "OPEN"')
    open_positions = cursor.fetchone()[0]

    print(f'\nCURRENT STATUS:')
    print(f'   • Open Positions: {open_positions}/10 (max)')
    print(f'   • Valid Signals Today: {len(valid_signals)}')
    print(f'   • Pending Signals: {len([s for s in valid_signals if not s[7]])}')

    # Config info
    print(f'\nCONFIGURATION:')
    print(f'   • Max Open Positions: 10')
    print(f'   • Top N Trades: 5')
    print(f'   • Min Signal Score: 2.0')

    conn.close()

if __name__ == "__main__":
    show_signals_dashboard()