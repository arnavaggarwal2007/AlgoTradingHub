#!/usr/bin/env python3
"""
Position Checker - Review Open Positions and Identify Issues
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import ConfigManager, PositionDatabase
from alpaca.trading.client import TradingClient


def check_positions():
    """Check all positions in database and Alpaca account"""
    
    print("=" * 80)
    print("📊 POSITION CHECKER - Database vs Alpaca Account")
    print("=" * 80)
    print()
    
    # Load configuration
    config_manager = ConfigManager('config/config.json')
    
    api_key = config_manager.get('api', 'key_id')
    secret_key = config_manager.get('api', 'secret_key')
    base_url = config_manager.get('api', 'base_url')
    paper = 'paper' in base_url.lower() if base_url else True
    
    # Initialize clients
    trading_client = TradingClient(api_key, secret_key, paper=paper)
    db = PositionDatabase('db/positions.db')
    
    print(f"Trading Mode: {'📝 PAPER TRADING' if paper else '💰 LIVE TRADING'}")
    print(f"Database: db/positions.db")
    print()
    
    # Get positions from database
    print("=" * 80)
    print("💾 POSITIONS IN DATABASE")
    print("=" * 80)
    print()
    
    active_positions = db.get_open_positions()
    # Get total count (active + closed would require query, just show active for now)
    db_positions = active_positions
    closed_positions = []  # Would need separate query
    
    print(f"Total Positions: {len(db_positions)}")
    print(f"  Active: {len(active_positions)}")
    print(f"  Closed: {len(closed_positions)}")
    print()
    
    if active_positions:
        print("-" * 80)
        print(f"{'ID':<5} {'Symbol':<8} {'Qty':<6} {'Remain':<8} {'Entry $':<10} {'Days':<6} {'Status':<10}")
        print("-" * 80)
        
        for pos in active_positions:
            entry_time = datetime.fromisoformat(pos.get('entry_date', pos.get('entry_time', datetime.now().isoformat())))
            days_held = (datetime.now() - entry_time).days
            
            print(f"{pos['id']:<5} {pos['symbol']:<8} {pos['quantity']:<6} "
                  f"{pos.get('remaining_qty', pos['quantity']):<8} ${pos.get('entry_price', 0):<9.2f} "
                  f"{days_held:<6} {pos.get('status', 'OPEN'):<10}")
        print()
    else:
        print("✅ No active positions in database")
        print()
    
    # Get positions from Alpaca
    print("=" * 80)
    print("☁️  POSITIONS IN ALPACA ACCOUNT")
    print("=" * 80)
    print()
    
    try:
        alpaca_positions = trading_client.get_all_positions()
        
        if alpaca_positions:
            print(f"Total Open Positions: {len(alpaca_positions)}")
            print()
            print("-" * 80)
            print(f"{'Symbol':<8} {'Qty':<8} {'Avg Entry':<12} {'Current $':<12} {'P&L $':<12} {'P&L %':<10}")
            print("-" * 80)
            
            total_pnl = 0
            
            for pos in alpaca_positions:
                qty = float(pos.qty)
                avg_entry = float(pos.avg_entry_price)
                current = float(pos.current_price)
                unrealized_pl = float(pos.unrealized_pl)
                unrealized_plpc = float(pos.unrealized_plpc)
                
                total_pnl += unrealized_pl
                
                pnl_symbol = "🟢" if unrealized_pl > 0 else "🔴" if unrealized_pl < 0 else "⚪"
                
                print(f"{pos.symbol:<8} {qty:<8.0f} ${avg_entry:<11.2f} "
                      f"${current:<11.2f} {pnl_symbol}${unrealized_pl:<10.2f} "
                      f"{unrealized_plpc*100:<9.2f}%")
            
            print("-" * 80)
            print(f"Total Unrealized P&L: {'🟢' if total_pnl > 0 else '🔴'}${total_pnl:,.2f}")
            print()
        else:
            print("✅ No open positions in Alpaca account")
            print()
    
    except Exception as e:
        print(f"❌ Error getting Alpaca positions: {e}")
        print()
    
    # Compare and find discrepancies
    print("=" * 80)
    print("🔍 POSITION RECONCILIATION")
    print("=" * 80)
    print()
    
    db_symbols = {p['symbol']: p for p in active_positions}
    alpaca_symbols = {p.symbol: p for p in alpaca_positions} if alpaca_positions else {}
    
    # Find positions in DB but not in Alpaca
    db_only = set(db_symbols.keys()) - set(alpaca_symbols.keys())
    if db_only:
        print("⚠️  Positions in DATABASE but NOT in ALPACA:")
        for symbol in db_only:
            pos = db_symbols[symbol]
            print(f"   {symbol}: {pos['remaining_qty']} shares (ID: {pos['id']})")
            print(f"      This position should be closed in database")
        print()
    
    # Find positions in Alpaca but not in DB
    alpaca_only = set(alpaca_symbols.keys()) - set(db_symbols.keys())
    if alpaca_only:
        print("⚠️  Positions in ALPACA but NOT in DATABASE:")
        for symbol in alpaca_only:
            pos = alpaca_symbols[symbol]
            print(f"   {symbol}: {float(pos.qty)} shares")
            print(f"      This is unusual - position not tracked by bot")
        print()
    
    # Find matching positions with quantity mismatches
    matching = set(db_symbols.keys()) & set(alpaca_symbols.keys())
    mismatches = []
    for symbol in matching:
        db_qty = db_symbols[symbol]['remaining_qty']
        alpaca_qty = float(alpaca_symbols[symbol].qty)
        
        if db_qty != alpaca_qty:
            mismatches.append((symbol, db_qty, alpaca_qty))
    
    if mismatches:
        print("⚠️  QUANTITY MISMATCHES (Database vs Alpaca):")
        for symbol, db_qty, alpaca_qty in mismatches:
            print(f"   {symbol}: DB shows {db_qty} shares, Alpaca shows {alpaca_qty} shares")
            diff = alpaca_qty - db_qty
            if diff > 0:
                print(f"      Alpaca has {diff} MORE shares than database")
            else:
                print(f"      Database has {-diff} MORE shares than Alpaca (CRITICAL)")
        print()
    
    if not db_only and not alpaca_only and not mismatches:
        print("✅ ✅ ✅  Perfect sync! Database matches Alpaca exactly.")
        print()
    
    # Identify stuck positions
    print("=" * 80)
    print("🚨 STUCK POSITION ANALYSIS")
    print("=" * 80)
    print()
    
    stuck_positions = []
    
    for pos in active_positions:
        entry_time = datetime.fromisoformat(pos.get('entry_date', pos.get('entry_time', datetime.now().isoformat())))
        days_held = (datetime.now() - entry_time).days
        
        # Position held for more than 7 days = potentially stuck
        if days_held > 7:
            stuck_positions.append((pos, days_held))
    
    if stuck_positions:
        print(f"Found {len(stuck_positions)} positions held longer than 7 days:")
        print()
        
        for pos, days_held in sorted(stuck_positions, key=lambda x: x[1], reverse=True):
            symbol = pos['symbol']
            print(f"🔴 {symbol}")
            print(f"   Position ID: {pos['id']}")
            print(f"   Quantity: {pos['remaining_qty']} shares")
            print(f"   Entry Price: ${pos.get('entry_price', 0):.2f}")
            entry_date_str = pos.get('entry_date', pos.get('entry_time', ''))[:10]
            print(f"   Entry Date: {entry_date_str}")
            print(f"   Days Held: {days_held} days ⚠️")
            
            # Check if this is one of the problem positions from logs
            if symbol in ['LLY', 'WELL', 'TKO']:
                print(f"   ⚠️  WARNING: This is one of the problem positions from logs!")
                print(f"   ⚠️  This position has been failing to exit")
            
            # Get current Alpaca data if available
            if symbol in alpaca_symbols:
                alpaca_pos = alpaca_symbols[symbol]
                current_price = float(alpaca_pos.current_price)
                unrealized_pl = float(alpaca_pos.unrealized_pl)
                
                print(f"   Current Price: ${current_price:.2f}")
                print(f"   Unrealized P&L: {'🟢' if unrealized_pl > 0 else '🔴'}${unrealized_pl:.2f}")
            
            print()
    else:
        print("✅ No stuck positions detected (all positions < 7 days old)")
        print()
    
    # Action items
    print("=" * 80)
    print("💡 RECOMMENDED ACTIONS")
    print("=" * 80)
    print()
    
    if stuck_positions:
        print("For stuck positions:")
        print()
        print("Option 1: Manual Close via Alpaca Dashboard")
        if paper:
            print("  1. Go to: https://app.alpaca.markets/paper/dashboard/positions")
        else:
            print("  1. Go to: https://app.alpaca.markets/live/dashboard/positions")
        print("  2. Find and close positions: ", end="")
        print(", ".join([pos[0]['symbol'] for pos in stuck_positions]))
        print("  3. Then update database:")
        print("     python scripts/db_manager.py --sync")
        print()
        
        print("Option 2: Force Close via Script")
        print("  (Not implemented yet - would need to add force_close_position.py)")
        print()
    
    if db_only:
        print("For database-only positions (ghost positions):")
        print("  1. These positions are already closed in Alpaca")
        print("  2. Update database to mark them as closed:")
        print("     python scripts/db_manager.py --close-ghost-positions")
        print()
    
    if mismatches:
        print("For quantity mismatches:")
        print("  1. Investigate which is correct (database or Alpaca)")
        print("  2. If Alpaca is correct, sync database:")
        print("     python scripts/db_manager.py --sync")
        print()
    
    print("=" * 80)
    print("✅ Position Check Complete")
    print("=" * 80)


if __name__ == '__main__':
    check_positions()
