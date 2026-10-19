#!/usr/bin/env python3
"""
Cleanup Script for Single_Buy_Real_Money - Prepare for Live Trading
Cleans databases, logs, and trade history while preserving code and configuration
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

# Configuration
BASE_DIR = Path(r"c:\Alpaca_Algo\Single_Buy_Real_Money")
CONFIG_FILE = BASE_DIR / "config" / "config.json"

# Files to delete
FILES_TO_DELETE = [
    # Log files
    BASE_DIR / "logs" / "rajat_alpha_v67.log",
    BASE_DIR / "logs" / "audit.log",
    
    # Trade history & analysis
    BASE_DIR / "logs" / "POSITIONS_ANALYSIS.csv",
    BASE_DIR / "logs" / "BUG_FIX_SUMMARY.md",
    BASE_DIR / "logs" / "PARTIAL_EXIT_BUG_ANALYSIS.md",
    BASE_DIR / "logs" / "TIER_SL_AND_PARTIAL_EXIT_ANALYSIS.md",
    BASE_DIR / "reports" / "BUG_VS_ACCOUNT_ANALYSIS.md",
    
    # Database files
    BASE_DIR / "db" / "positions.db",
    BASE_DIR / "logs" / "positions.db",
]

# Directories to delete completely
DIRS_TO_DELETE = [
    BASE_DIR / "__pycache__",
    BASE_DIR / "tools" / "__pycache__",
    BASE_DIR / "enterprise_features" / "__pycache__",
    BASE_DIR / "tools" / "preSwingTradeAnalysis" / ".pytest_cache",
]


def update_config_for_live_trading():
    """Update config.json to use live trading API endpoint"""
    print("\n📝 Step 1: Updating config.json for LIVE TRADING...")
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Store original URL for display
        original_url = config["api"]["base_url"]
        
        # Update to live trading API
        config["api"]["base_url"] = "https://api.alpaca.markets"
        
        # Write back to file
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"  ✅ API URL updated: {original_url}")
        print(f"  ✅ → NEW URL: {config['api']['base_url']}")
        print(f"  ✅ Position sizing: {config['position_sizing']['mode']} ({config['position_sizing']['percent_of_equity']*100}% equity)")
        print(f"  ✅ Max position: ${config['position_sizing']['fixed_amount']}")
        print(f"  ✅ Max open positions: {config['trading_rules']['max_open_positions']}")
        print(f"  ✅ Max trades/day: {config['trading_rules']['max_trades_per_day']}")
        return True
    except Exception as e:
        print(f"  ❌ ERROR updating config: {e}")
        return False


def delete_files():
    """Delete old log, trade history, and database files"""
    print("\n🗑️  Step 2: Deleting old paper trading data...")
    
    deleted_count = 0
    for file_path in FILES_TO_DELETE:
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"  ✅ Deleted: {file_path.name}")
                deleted_count += 1
            else:
                print(f"  ⏭️  Not found (OK): {file_path.name}")
        except Exception as e:
            print(f"  ⚠️  Could not delete {file_path.name}: {e}")
    
    print(f"\n  Total files deleted: {deleted_count}/{len(FILES_TO_DELETE)}")
    return deleted_count > 0


def delete_cache_directories():
    """Delete Python cache and pytest directories"""
    print("\n🗑️  Step 3: Cleaning Python cache directories...")
    
    deleted_count = 0
    for dir_path in DIRS_TO_DELETE:
        try:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"  ✅ Deleted directory: {dir_path.name}")
                deleted_count += 1
            else:
                print(f"  ⏭️  Not found (OK): {dir_path.name}")
        except Exception as e:
            print(f"  ⚠️  Could not delete {dir_path.name}: {e}")
    
    print(f"\n  Total directories deleted: {deleted_count}/{len(DIRS_TO_DELETE)}")
    return deleted_count > 0


def verify_cleanup():
    """Verify that cleanup was successful"""
    print("\n✔️  Step 4: VERIFICATION...")
    
    issues = []
    
    # Check database files don't exist
    print("\n  Checking database files...")
    for db_file in [BASE_DIR / "db" / "positions.db", BASE_DIR / "logs" / "positions.db"]:
        if db_file.exists():
            issues.append(f"Database still exists: {db_file}")
        else:
            print(f"    ✅ {db_file.name} - Confirmed deleted")
    
    # Check log files don't exist
    print("\n  Checking log files...")
    log_files = list((BASE_DIR / "logs").glob("*.log"))
    if log_files:
        issues.append(f"Log files still exist: {[f.name for f in log_files]}")
    else:
        print(f"    ✅ No .log files found - Confirmed deleted")
    
    # Check trade history files don't exist
    print("\n  Checking trade history files...")
    trade_files = list((BASE_DIR / "logs").glob("*.csv")) + list((BASE_DIR / "logs").glob("*ANALYSIS.md"))
    if trade_files:
        issues.append(f"Trade history files still exist: {[f.name for f in trade_files]}")
    else:
        print(f"    ✅ No trade history files found - Confirmed deleted")
    
    # Verify watchlist.txt is intact
    print("\n  Checking watchlist.txt...")
    watchlist_file = BASE_DIR / "config" / "watchlist.txt"
    if watchlist_file.exists():
        with open(watchlist_file, 'r') as f:
            watchlist = [line.strip() for line in f.readlines() if line.strip()]
        print(f"    ✅ Watchlist intact - {len(watchlist)} symbols")
    else:
        issues.append("Watchlist.txt not found!")
    
    # Verify config.json can be loaded
    print("\n  Checking config.json...")
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        api_url = config.get("api", {}).get("base_url", "")
        if "api.alpaca.markets" in api_url:
            print(f"    ✅ config.json valid - Using LIVE trading API")
        else:
            issues.append(f"Config still points to paper trading: {api_url}")
    except Exception as e:
        issues.append(f"Could not read config.json: {e}")
    
    # Summary
    print("\n" + "="*70)
    if issues:
        print("❌ VERIFICATION FAILED - Issues found:")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("✅ VERIFICATION SUCCESSFUL - All cleanup complete!")
        print("\n📊 READY FOR LIVE TRADING:")
        print(f"  • Initial capital: $5,000")
        print(f"  • Trading mode: LIVE (https://api.alpaca.markets)")
        print(f"  • Position sizing: 3% per trade")
        print(f"  • Max open positions: 15")
        print(f"  • Max trades/day: 3")
        print(f"  • Watchlist: Populated with your symbols")
        print(f"  • Databases: Fresh (will create new on first run)")
        print("\n🚀 You're ready to start real money trading!")
        print("="*70)
        return True


def main():
    """Execute all cleanup steps"""
    print("="*70)
    print("SINGLE_BUY_REAL_MONEY - CLEANUP FOR LIVE TRADING")
    print(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Execute steps
    step1 = update_config_for_live_trading()
    step2 = delete_files()
    step3 = delete_cache_directories()
    step4 = verify_cleanup()
    
    # Final summary
    print("\n" + "="*70)
    if all([step1, step4]):
        print("🎉 CLEANUP COMPLETE - Ready for real money trading!")
    else:
        print("⚠️  CLEANUP COMPLETE WITH WARNINGS - Review above")
    print("="*70)


if __name__ == "__main__":
    main()
