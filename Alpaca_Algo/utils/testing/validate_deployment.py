"""
PRE-DEPLOYMENT VALIDATION SCRIPT
Run this before starting rajat_alpha_v67.py to ensure everything is ready
"""

import sys
import os

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def print_result(test_name, passed, message=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if message:
        print(f"      {message}")

def main():
    print_header("RAJAT ALPHA V67 - PRE-DEPLOYMENT VALIDATION")
    
    all_passed = True
    
    # Test 1: Import module
    print_header("TEST 1: Module Import")
    try:
        import rajat_alpha_v67 as bot
        print_result("Import rajat_alpha_v67", True)
    except Exception as e:
        print_result("Import rajat_alpha_v67", False, str(e))
        all_passed = False
        return False
    
    # Test 2: Critical method exists
    print_header("TEST 2: Critical Method Verification")
    try:
        analyzer = bot.RajatAlphaAnalyzer(None, None)
        
        # Check the fixed method exists
        has_correct = hasattr(analyzer, 'check_multitimeframe_confirmation')
        print_result("Method 'check_multitimeframe_confirmation' exists", has_correct)
        
        # Check typo version does NOT exist
        has_typo = hasattr(analyzer, 'check_multitimet_confirmation')
        print_result("No typo version 'check_multitimet_confirmation'", not has_typo)
        
        if not has_correct or has_typo:
            all_passed = False
    except Exception as e:
        print_result("Method verification", False, str(e))
        all_passed = False
    
    # Test 3: Configuration file
    print_header("TEST 3: Configuration Check")
    try:
        if not os.path.exists('config.json'):
            print_result("config.json exists", False, "File not found!")
            all_passed = False
        else:
            config = bot.ConfigManager('config.json')
            print_result("config.json valid", True)
            
            # Check critical settings
            max_pos = config.get('trading_rules', 'max_open_positions')
            print_result(f"Max positions configured: {max_pos}", max_pos is not None)
            
            api_key = config.get('api', 'key_id')
            print_result("API key configured", api_key is not None and len(api_key) > 0)
    except Exception as e:
        print_result("Configuration check", False, str(e))
        all_passed = False
    
    # Test 4: Database initialization
    print_header("TEST 4: Database Check")
    try:
        db = bot.PositionDatabase(':memory:')  # Test with in-memory DB
        
        # Try basic operations
        pos_id = db.add_position('TEST', 100.0, 10, 85.0, 4.0)
        positions = db.get_open_positions()
        
        print_result("Database operations", len(positions) == 1)
        db.conn.close()
    except Exception as e:
        print_result("Database check", False, str(e))
        all_passed = False
    
    # Test 5: Pattern detector
    print_header("TEST 5: Pattern Detection")
    try:
        import pandas as pd
        
        # Test engulfing
        df = pd.DataFrame({
            'open': [110.0, 105.0],
            'high': [111.0, 112.0],
            'low': [104.0, 104.5],
            'close': [105.0, 111.0]
        })
        
        is_engulfing = bot.PatternDetector.is_engulfing(df)
        print_result("Engulfing pattern detection", is_engulfing)
        
        has_pattern, name = bot.PatternDetector.has_pattern(df)
        print_result(f"Pattern recognition: {name}", has_pattern)
    except Exception as e:
        print_result("Pattern detection", False, str(e))
        all_passed = False
    
    # Test 6: Dependencies
    print_header("TEST 6: Python Dependencies")
    required_modules = [
        'pandas',
        'pandas_ta',
        'sqlite3',
        'pytz',
        'alpaca'
    ]
    
    for module_name in required_modules:
        try:
            if module_name == 'alpaca':
                import alpaca.trading
                import alpaca.data
            else:
                __import__(module_name)
            print_result(f"Module '{module_name}' installed", True)
        except ImportError:
            print_result(f"Module '{module_name}' installed", False, "Missing!")
            all_passed = False
    
    # Test 7: Watchlist
    print_header("TEST 7: Watchlist File")
    try:
        watchlist_file = 'watchlist.txt'
        if not os.path.exists(watchlist_file):
            print_result("watchlist.txt exists", False, "File not found!")
            all_passed = False
        else:
            with open(watchlist_file, 'r') as f:
                symbols = [line.strip() for line in f if line.strip()]
            print_result(f"Watchlist loaded: {len(symbols)} symbols", len(symbols) > 0)
    except Exception as e:
        print_result("Watchlist check", False, str(e))
        all_passed = False
    
    # Final Summary
    print_header("VALIDATION SUMMARY")
    
    if all_passed:
        print("\n🎉 ALL CHECKS PASSED - READY FOR DEPLOYMENT\n")
        print("Next steps:")
        print("  1. Run: python rajat_alpha_v67.py")
        print("  2. Monitor: tail -f rajat_alpha_v67.log")
        print("  3. Verify first buy signal executes correctly")
        print()
        return True
    else:
        print("\n⚠️  SOME CHECKS FAILED - DO NOT DEPLOY\n")
        print("Please fix the issues above before running the bot.")
        print()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
