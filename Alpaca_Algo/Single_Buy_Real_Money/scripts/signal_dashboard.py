"""
Signal Dashboard - Interactive signal monitoring and analysis

Displays today's signals with scoring breakdown, execution status, and recommendations.
Replaces: signals_dashboard.py

Usage:
    python scripts/signal_dashboard.py              # Show today's dashboard
    python scripts/signal_dashboard.py --date YYYY-MM-DD  # Show specific date
    python scripts/signal_dashboard.py --watch      # Watch mode (auto-refresh every 60s)
"""

import sqlite3
import argparse
import os
import time
from datetime import datetime
from typing import List, Tuple

DB_PATH = 'db/positions.db'


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def show_signals_dashboard(signal_date: str = None, watch_mode: bool = False):
    """Display today's active signals dashboard"""
    
    if watch_mode:
        clear_screen()
    
    if not signal_date:
        signal_date = datetime.now().date().isoformat()
    
    print('=' * 80)
    print(f'ACTIVE SIGNALS DASHBOARD - {signal_date}')
    print('=' * 80)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get valid signals for the date (score > 0)
    cursor.execute('''
        SELECT id, symbol, signal_date, score, pattern, price, reason, executed, created_at 
        FROM signal_history 
        WHERE signal_date = ? AND score > 0 
        ORDER BY score DESC, created_at DESC
    ''', (signal_date,))
    valid_signals = cursor.fetchall()
    
    print(f'\n📊 VALID SIGNALS: {len(valid_signals)}')
    print('-' * 80)
    
    if valid_signals:
        # Show all signals
        for i, signal in enumerate(valid_signals, 1):
            status = '✅ EXECUTED' if signal['executed'] else '⏳ PENDING'
            
            # Determine pattern type
            pattern = signal['pattern'] or 'Unknown'
            if any(p in pattern for p in ['Engulfing', 'Piercing', 'Tweezer']):
                pattern_type = '🎯 Pattern'
            elif 'EMA21' in pattern or 'SMA50' in pattern:
                pattern_type = '📍 Touch'
            else:
                pattern_type = '❓ Other'
            
            # Score indicator
            if signal['score'] >= 5:
                score_indicator = '🌟🌟🌟'
            elif signal['score'] >= 4:
                score_indicator = '🌟🌟'
            elif signal['score'] >= 3:
                score_indicator = '🌟'
            else:
                score_indicator = '⭐'
            
            print(f'{i:2d}. {signal["symbol"]:<6} | Score: {signal["score"]:4.1f} {score_indicator} | {pattern_type:<12} | {status}')
            print(f'    Pattern: {pattern}')
            print(f'    Price: ${signal["price"]:.2f} | Created: {signal["created_at"]}')
        
        # Show execution summary
        print('\n' + '=' * 80)
        print('EXECUTION SUMMARY')
        print('-' * 80)
        
        pending_signals = [s for s in valid_signals if not s['executed']]
        executed_signals = [s for s in valid_signals if s['executed']]
        
        print(f'\n✅ Executed: {len(executed_signals)}')
        print(f'⏳ Pending: {len(pending_signals)}')
        
        if pending_signals:
            print('\n🎯 TOP PENDING SIGNALS (by Score):')
            print('-' * 80)
            
            for i, signal in enumerate(pending_signals[:5], 1):
                pattern = signal['pattern'] or 'Unknown'
                pattern_type = 'Pattern' if any(p in pattern for p in ['Engulfing', 'Piercing', 'Tweezer']) else 'Touch'
                print(f'{i}. {signal["symbol"]:<6} (Score: {signal["score"]:.1f}) - {pattern_type}: {pattern}')
            
            if len(pending_signals) > 5:
                print(f'   ... and {len(pending_signals) - 5} more')
        else:
            print('\n✅ All signals have been executed or no pending signals!')
        
        # Show signal type breakdown
        print('\n' + '=' * 80)
        print('SIGNAL TYPE BREAKDOWN')
        print('-' * 80)
        
        cursor.execute('''
            SELECT pattern, COUNT(*) as count, AVG(score) as avg_score
            FROM signal_history 
            WHERE signal_date = ? AND score > 0 
            GROUP BY pattern
            ORDER BY count DESC
        ''', (signal_date,))
        pattern_breakdown = cursor.fetchall()
        
        for row in pattern_breakdown:
            print(f'   {row["pattern"]:<20} : {row["count"]:2d} signals (avg score: {row["avg_score"]:.1f})')
    
    else:
        print('❌ No valid signals detected for this date yet.')
    
    # Check current positions and limits
    cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "OPEN"')
    open_positions = cursor.fetchone()['COUNT(*)']
    
    print('\n' + '=' * 80)
    print('CURRENT STATUS')
    print('-' * 80)
    print(f'   💼 Open Positions: {open_positions}/10 (max)')
    print(f'   📊 Valid Signals Today: {len(valid_signals)}')
    print(f'   ⏳ Pending Signals: {len([s for s in valid_signals if not s["executed"]])}')
    print(f'   ✅ Executed Signals: {len([s for s in valid_signals if s["executed"]])}')
    
    conn.close()
    
    if watch_mode:
        print('\n' + '=' * 80)
        print('🔄 Watch mode active - refreshing every 60 seconds... (Press Ctrl+C to exit)')
        print('=' * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Signal Dashboard - Monitor and analyze trading signals',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--date', type=str, metavar='YYYY-MM-DD',
                       help='Show signals for specific date (default: today)')
    parser.add_argument('--watch', action='store_true',
                       help='Watch mode - auto-refresh every 60 seconds')
    
    args = parser.parse_args()
    
    if not os.path.exists(DB_PATH):
        print(f'❌ Database not found at: {DB_PATH}')
        print('   Make sure you run this script from the Single_Buy directory')
        return
    
    if args.watch:
        try:
            while True:
                show_signals_dashboard(signal_date=args.date, watch_mode=True)
                time.sleep(60)
        except KeyboardInterrupt:
            print('\n\n✅ Watch mode stopped')
    else:
        show_signals_dashboard(signal_date=args.date)


if __name__ == "__main__":
    main()
