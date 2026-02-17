#!/usr/bin/env python3
"""
Stock Analysis Report - Available for Trade Based on Ratings
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def main():
    # Connect to database
    conn = sqlite3.connect('positions.db')
    cursor = conn.cursor()

    # Get today's signals (last 24 hours)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')

    print('=== RECENT SIGNAL ANALYSIS (Last 24 hours) ===')
    print(f'Date range: {yesterday} to {today}')
    print()

    # Get all signals from today
    cursor.execute('''
        SELECT symbol, score, pattern, executed, created_at
        FROM signal_history
        WHERE created_at >= ?
        ORDER BY score DESC, created_at DESC
    ''', (yesterday,))

    signals = cursor.fetchall()

    if signals:
        print(f'Found {len(signals)} signals analyzed:')
        print()

        # Group by score ranges
        score_ranges = {
            'High (4.0+)': [],
            'Medium-High (3.0-3.9)': [],
            'Medium (2.0-2.9)': [],
            'Low (0-1.9)': []
        }

        for symbol, score, pattern, executed, created_at in signals:
            if score >= 4.0:
                score_ranges['High (4.0+)'].append((symbol, score, pattern, executed))
            elif score >= 3.0:
                score_ranges['Medium-High (3.0-3.9)'].append((symbol, score, pattern, executed))
            elif score >= 2.0:
                score_ranges['Medium (2.0-2.9)'].append((symbol, score, pattern, executed))
            else:
                score_ranges['Low (0-1.9)'].append((symbol, score, pattern, executed))

        for range_name, stocks in score_ranges.items():
            if stocks:
                print(f'{range_name}: {len(stocks)} stocks')
                for symbol, score, pattern, executed in sorted(stocks, key=lambda x: x[1], reverse=True):
                    status = 'EXECUTED' if executed else 'NOT EXECUTED'
                    print(f'  {symbol}: Score {score:.1f}, Pattern: {pattern}, Status: {status}')
                print()
    else:
        print('No signals found in the last 24 hours.')
        print()

    # Get current open positions
    print('=== CURRENT OPEN POSITIONS ===')
    cursor.execute('SELECT symbol, entry_price, remaining_qty, score FROM positions WHERE status = "OPEN" ORDER BY entry_date DESC')
    positions = cursor.fetchall()

    if positions:
        for symbol, entry_price, qty, score in positions:
            print(f'{symbol}: {qty} shares @ ${entry_price:.2f}, Score: {score:.1f}')
    else:
        print('No open positions.')
        print()

    # Get today's trade count
    cursor.execute('SELECT COUNT(*) FROM positions WHERE DATE(entry_date) = DATE("now")')
    today_trades = cursor.fetchone()[0]
    print(f'=== TODAY\'S TRADING ACTIVITY ===')
    print(f'Trades executed today: {today_trades}')

    # Get trading limits from config
    print()
    print('=== TRADING LIMITS & CONSTRAINTS ===')
    try:
        import json
        with open('config/config.json', 'r') as f:
            config = json.load(f)

        trading_rules = config.get('trading_rules', {})
        print(f'Max open positions: {trading_rules.get("max_open_positions", "N/A")}')
        print(f'Max trades per stock: {trading_rules.get("max_trades_per_stock", "N/A")}')
        print(f'Max trades per day: {trading_rules.get("max_trades_per_day", "N/A")}')
        print(f'Min signal score required: {trading_rules.get("min_signal_score", "N/A")}')
        print(f'Per trade % of equity: {trading_rules.get("per_trade_pct", "N/A")*100:.1f}%')
        print(f'Max allocation per stock: {trading_rules.get("max_allocation_per_stock_pct", "N/A")*100:.1f}%')
        print(f'Max equity utilization: {trading_rules.get("max_equity_utilization_pct", "N/A")*100:.1f}%')

    except Exception as e:
        print(f'Could not load config: {e}')

    conn.close()

if __name__ == "__main__":
    main()