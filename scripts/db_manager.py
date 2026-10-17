"""
Database Manager - Unified database query and management tool

This script consolidates all database query operations into a single, easy-to-use tool.
It replaces: check_db.py, query_db.py, check_signals.py, check_trades.py, 
check_recent_signals.py, check_valid_signals.py

Usage:
    python scripts/db_manager.py --tables              # List all tables
    python scripts/db_manager.py --positions           # Show positions
    python scripts/db_manager.py --signals             # Show recent signals
    python scripts/db_manager.py --signals-valid       # Show valid signals (score >= 2)
    python scripts/db_manager.py --signals-today       # Show today's signals
    python scripts/db_manager.py --stats               # Show performance stats
    python scripts/db_manager.py --all                 # Show everything
"""

import sqlite3
import argparse
import os
from datetime import datetime, timedelta
from typing import List, Tuple

DB_PATH = 'db/positions.db'


def check_database_exists() -> bool:
    """Check if database file exists"""
    if not os.path.exists(DB_PATH):
        print(f'❌ Database not found at: {DB_PATH}')
        print('   Make sure you run this script from the Single_Buy directory')
        return False
    return True


def get_connection() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def show_tables():
    """Show all database tables and their schemas"""
    print('\n' + '=' * 80)
    print('DATABASE TABLES & SCHEMAS')
    print('=' * 80)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for table_row in tables:
        table_name = table_row[0]
        print(f'\n📊 Table: {table_name}')
        print('-' * 80)
        
        # Get schema
        cursor.execute(f'PRAGMA table_info({table_name})')
        columns = cursor.fetchall()
        
        for col in columns:
            nullable = 'NULL' if col[3] == 0 else 'NOT NULL'
            default = f' DEFAULT {col[4]}' if col[4] else ''
            print(f'   {col[1]:<20} {col[2]:<15} {nullable}{default}')
        
        # Get row count
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'\n   Total records: {count}')
    
    conn.close()


def show_positions(status_filter: str = None):
    """Show positions with optional status filter"""
    print('\n' + '=' * 80)
    print('POSITIONS')
    print('=' * 80)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM positions'
    if status_filter:
        query += f' WHERE status = "{status_filter.upper()}"'
    query += ' ORDER BY entry_date DESC'
    
    cursor.execute(query)
    positions = cursor.fetchall()
    
    if not positions:
        print(f'No positions found{" with status: " + status_filter if status_filter else ""}')
        conn.close()
        return
    
    print(f'\nTotal: {len(positions)} positions\n')
    
    for pos in positions:
        status_emoji = '🟢' if pos['status'] == 'OPEN' else '🔴'
        print(f"{status_emoji} ID {pos['id']}: {pos['symbol']}")
        print(f"   Entry: {pos['entry_date']} @ ${pos['entry_price']:.2f}")
        print(f"   Quantity: {pos['quantity']} (Remaining: {pos['remaining_qty']})")
        print(f"   Stop Loss: ${pos['stop_loss']:.2f}")
        print(f"   Status: {pos['status']}")
        
        if pos['status'] == 'CLOSED':
            pnl_emoji = '📈' if pos['profit_loss_pct'] and pos['profit_loss_pct'] > 0 else '📉'
            print(f"   Exit: {pos['exit_date']} @ ${pos['exit_price']:.2f}")
            print(f"   {pnl_emoji} P/L: {pos['profit_loss_pct']:.2f}%")
            print(f"   Reason: {pos['exit_reason']}")
        
        print(f"   Score: {pos['score']:.1f} | Pattern: {pos['pattern']}")
        print()
    
    conn.close()


def show_signals(limit: int = 20, min_score: float = None, date_filter: str = None):
    """Show signal history with optional filters"""
    print('\n' + '=' * 80)
    print('SIGNAL HISTORY')
    print('=' * 80)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM signal_history WHERE 1=1'
    params = []
    
    if min_score is not None:
        query += ' AND score >= ?'
        params.append(min_score)
    
    if date_filter:
        query += ' AND signal_date = ?'
        params.append(date_filter)
    
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    signals = cursor.fetchall()
    
    if not signals:
        print('No signals found matching criteria')
        conn.close()
        return
    
    print(f'\nShowing {len(signals)} signals\n')
    
    for sig in signals:
        exec_emoji = '✅' if sig['executed'] else '⏳'
        score_emoji = '🌟' if sig['score'] >= 4 else '⭐' if sig['score'] >= 3 else '💫' if sig['score'] >= 2 else '·'
        
        print(f"{exec_emoji} {score_emoji} {sig['symbol']:<6} | Score: {sig['score']:4.1f} | {sig['signal_date']}")
        print(f"   Pattern: {sig['pattern']:<15} | Price: ${sig['price']:.2f}")
        print(f"   Reason: {sig['reason']}")
        print(f"   Created: {sig['created_at']} | Executed: {sig['executed']}")
        print()
    
    conn.close()


def show_performance_stats():
    """Show performance statistics"""
    print('\n' + '=' * 80)
    print('PERFORMANCE STATISTICS')
    print('=' * 80)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_trades,
            AVG(profit_loss_pct) as avg_pnl,
            MAX(profit_loss_pct) as max_profit,
            MIN(profit_loss_pct) as max_loss,
            SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN profit_loss_pct <= 0 THEN 1 ELSE 0 END) as losses
        FROM positions 
        WHERE status = 'CLOSED'
    ''')
    stats = cursor.fetchone()
    
    if stats['total_trades'] and stats['total_trades'] > 0:
        win_rate = (stats['wins'] / stats['total_trades']) * 100
        print(f"\n📊 Overall Performance:")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Win Rate: {win_rate:.1f}% ({stats['wins']} wins / {stats['losses']} losses)")
        print(f"   Average P/L: {stats['avg_pnl']:.2f}%")
        print(f"   Best Trade: {stats['max_profit']:.2f}%")
        print(f"   Worst Trade: {stats['max_loss']:.2f}%")
    else:
        print("\nNo closed trades yet")
    
    # Performance by Score
    print(f"\n📈 Performance by Signal Score:")
    cursor.execute('''
        SELECT 
            ROUND(score) as score_group,
            COUNT(*) as trades,
            AVG(profit_loss_pct) as avg_pnl,
            SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM positions 
        WHERE status = 'CLOSED' AND score IS NOT NULL
        GROUP BY score_group
        ORDER BY score_group DESC
    ''')
    score_stats = cursor.fetchall()
    
    for stat in score_stats:
        print(f"   Score {stat['score_group']:.0f}: {stat['trades']} trades | "
              f"Win Rate: {stat['win_rate']:.1f}% | Avg P/L: {stat['avg_pnl']:.2f}%")
    
    # Performance by Pattern
    print(f"\n🎯 Performance by Pattern:")
    cursor.execute('''
        SELECT 
            pattern,
            COUNT(*) as trades,
            AVG(profit_loss_pct) as avg_pnl,
            SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM positions 
        WHERE status = 'CLOSED' AND pattern IS NOT NULL
        GROUP BY pattern
        ORDER BY win_rate DESC
    ''')
    pattern_stats = cursor.fetchall()
    
    for stat in pattern_stats:
        print(f"   {stat['pattern']:<15}: {stat['trades']} trades | "
              f"Win Rate: {stat['win_rate']:.1f}% | Avg P/L: {stat['avg_pnl']:.2f}%")
    
    # Current open positions
    cursor.execute("SELECT COUNT(*) as count FROM positions WHERE status = 'OPEN'")
    open_count = cursor.fetchone()['count']
    print(f"\n💼 Current Status:")
    print(f"   Open Positions: {open_count}")
    
    # Recent signal activity
    today = datetime.now().date().isoformat()
    cursor.execute("SELECT COUNT(*) as count FROM signal_history WHERE signal_date = ?", (today,))
    today_signals = cursor.fetchone()['count']
    print(f"   Signals Today: {today_signals}")
    
    conn.close()


def show_dashboard():
    """Show comprehensive dashboard"""
    show_performance_stats()
    print("\n")
    show_positions(status_filter='OPEN')
    print("\n")
    show_signals(limit=10, min_score=2.0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Database Manager - Query and manage trading bot database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--tables', action='store_true', help='Show all tables and schemas')
    parser.add_argument('--positions', action='store_true', help='Show all positions')
    parser.add_argument('--positions-open', action='store_true', help='Show open positions only')
    parser.add_argument('--positions-closed', action='store_true', help='Show closed positions only')
    parser.add_argument('--signals', action='store_true', help='Show recent signals')
    parser.add_argument('--signals-valid', action='store_true', help='Show valid signals (score >= 2)')
    parser.add_argument('--signals-today', action='store_true', help='Show today\'s signals')
    parser.add_argument('--stats', action='store_true', help='Show performance statistics')
    parser.add_argument('--all', action='store_true', help='Show complete dashboard')
    parser.add_argument('--limit', type=int, default=20, help='Limit results (default: 20)')
    
    args = parser.parse_args()
    
    if not check_database_exists():
        return
    
    # If no args, show help
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    # Execute requested commands
    if args.tables:
        show_tables()
    
    if args.positions or args.positions_open or args.positions_closed:
        if args.positions_open:
            show_positions(status_filter='OPEN')
        elif args.positions_closed:
            show_positions(status_filter='CLOSED')
        else:
            show_positions()
    
    if args.signals:
        show_signals(limit=args.limit)
    
    if args.signals_valid:
        show_signals(limit=args.limit, min_score=2.0)
    
    if args.signals_today:
        today = datetime.now().date().isoformat()
        show_signals(date_filter=today, limit=100)
    
    if args.stats:
        show_performance_stats()
    
    if args.all:
        show_dashboard()


if __name__ == "__main__":
    main()
