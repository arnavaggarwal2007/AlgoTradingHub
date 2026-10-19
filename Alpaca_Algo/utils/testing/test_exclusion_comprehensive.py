"""
Comprehensive Test for Exclusion List Implementation
Tests all three bot implementations: Single Buy, Dual Buy, and E*TRADE
"""

import sys
import os
from pathlib import Path

def test_exclusion_feature(script_name, config_path, exclusion_path, watchlist_path):
    """Test exclusion list implementation for a specific bot"""
    print(f"\n{'='*80}")
    print(f"Testing: {script_name}")
    print(f"{'='*80}")
    
    # Check if files exist
    print(f"\n1. Checking files...")
    files_ok = True
    for file_path, file_type in [(config_path, "Config"), 
                                   (exclusion_path, "Exclusion list"),
                                   (watchlist_path, "Watchlist")]:
        if os.path.exists(file_path):
            print(f"   ✓ {file_type}: {file_path}")
        else:
            print(f"   ✗ {file_type} NOT FOUND: {file_path}")
            files_ok = False
    
    if not files_ok:
        print("   ⚠ Missing files - skipping this test")
        return False
    
    # Read watchlist
    print(f"\n2. Reading watchlist...")
    with open(watchlist_path, 'r') as f:
        watchlist = [line.strip().upper() for line in f 
                    if line.strip() and not line.strip().startswith('#')]
    print(f"   Found {len(watchlist)} symbols in watchlist")
    if len(watchlist) > 0:
        print(f"   First 5: {watchlist[:5]}")
    
    # Test 1: Empty exclusion list
    print(f"\n3. Test 1: Empty exclusion list")
    with open(exclusion_path, 'w') as f:
        f.write("# EXCLUSION LIST - Stocks to Skip in Analysis\n")
        f.write("# Currently empty for testing\n")
    
    # Import and test the module
    try:
        # Add script directory to path
        script_dir = os.path.dirname(os.path.abspath(config_path))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        
        # Import the appropriate module
        if "etrade" in script_name.lower():
            module_name = "rajat_alpha_v67_etrade"
        elif "dual" in script_name.lower():
            module_name = "rajat_alpha_v67_dual"
        else:
            module_name = "rajat_alpha_v67"
        
        print(f"   Importing {module_name}...")
        
        # Dynamic import
        if module_name in sys.modules:
            del sys.modules[module_name]  # Force reload
        
        module = __import__(module_name)
        
        # Create bot instance
        bot_class = getattr(module, 'RajatAlphaTradingBot')
        bot = bot_class(config_path)
        
        # Test watchlist loading
        symbols = bot.get_watchlist()
        print(f"   ✓ Loaded {len(symbols)} symbols (expected: {len(watchlist)})")
        
        if len(symbols) == len(watchlist):
            print(f"   ✓ PASS: No symbols excluded (as expected)")
        else:
            print(f"   ✗ FAIL: Expected {len(watchlist)}, got {len(symbols)}")
            return False
    
    except Exception as e:
        print(f"   ✗ Error during empty exclusion test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Exclusion list with test symbols
    print(f"\n4. Test 2: Exclusion list with test symbols")
    
    # Pick 2-3 symbols from watchlist to exclude
    if len(watchlist) >= 3:
        test_exclusions = watchlist[:3]
    elif len(watchlist) >= 1:
        test_exclusions = watchlist[:1]
    else:
        print("   ⚠ Watchlist too small for exclusion test")
        return True
    
    print(f"   Adding to exclusion list: {test_exclusions}")
    
    with open(exclusion_path, 'w') as f:
        f.write("# EXCLUSION LIST - Test symbols\n")
        for symbol in test_exclusions:
            f.write(f"{symbol}\n")
    
    try:
        # Reload module to pick up new exclusion list
        if module_name in sys.modules:
            del sys.modules[module_name]
        module = __import__(module_name)
        bot_class = getattr(module, 'RajatAlphaTradingBot')
        bot = bot_class(config_path)
        
        # Test watchlist loading
        symbols = bot.get_watchlist()
        expected_count = len(watchlist) - len(test_exclusions)
        
        print(f"   Loaded {len(symbols)} symbols (expected: {expected_count})")
        
        # Check that excluded symbols are not in the result
        excluded_found = [s for s in test_exclusions if s in symbols]
        
        if len(excluded_found) > 0:
            print(f"   ✗ FAIL: Excluded symbols still present: {excluded_found}")
            return False
        
        if len(symbols) == expected_count:
            print(f"   ✓ PASS: Correctly excluded {len(test_exclusions)} symbols")
        else:
            print(f"   ✗ FAIL: Expected {expected_count}, got {len(symbols)}")
            return False
            
    except Exception as e:
        print(f"   ✗ Error during exclusion test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Case insensitivity
    print(f"\n5. Test 3: Case insensitivity")
    
    if len(watchlist) >= 1:
        test_symbol = watchlist[0]
        # Write in mixed case
        mixed_case = test_symbol.lower() if test_symbol.isupper() else test_symbol.upper()
        
        print(f"   Testing with symbol in different case: {test_symbol} -> {mixed_case}")
        
        with open(exclusion_path, 'w') as f:
            f.write("# EXCLUSION LIST - Case test\n")
            f.write(f"{mixed_case}\n")
        
        try:
            # Reload
            if module_name in sys.modules:
                del sys.modules[module_name]
            module = __import__(module_name)
            bot_class = getattr(module, 'RajatAlphaTradingBot')
            bot = bot_class(config_path)
            
            symbols = bot.get_watchlist()
            
            if test_symbol not in symbols and test_symbol.upper() not in symbols:
                print(f"   ✓ PASS: Case-insensitive exclusion works")
            else:
                print(f"   ✗ FAIL: Symbol not excluded despite case difference")
                return False
                
        except Exception as e:
            print(f"   ✗ Error during case test: {e}")
            return False
    
    # Clean up - restore empty exclusion list
    print(f"\n6. Cleanup...")
    with open(exclusion_path, 'w') as f:
        f.write("# EXCLUSION LIST - Stocks to Skip in Analysis\n")
        f.write("# One symbol per line\n")
        f.write("# Lines starting with # are comments\n")
        f.write("# Currently empty - add symbols below as needed:\n\n")
    print(f"   ✓ Restored empty exclusion list")
    
    print(f"\n{'='*80}")
    print(f"✓ ALL TESTS PASSED for {script_name}")
    print(f"{'='*80}")
    
    return True


def main():
    """Run tests for all three implementations"""
    print(f"\n{'#'*80}")
    print(f"# EXCLUSION LIST FEATURE - COMPREHENSIVE TEST SUITE")
    print(f"{'#'*80}")
    
    base_dir = Path(__file__).parent
    
    tests = [
        {
            "name": "Single Buy (Alpaca)",
            "config": base_dir / "Single_Buy" / "config.json",
            "exclusion": base_dir / "Single_Buy" / "exclusionlist.txt",
            "watchlist": base_dir / "Single_Buy" / "watchlist.txt"
        },
        {
            "name": "Dual Buy (Alpaca)",
            "config": base_dir / "Dual_Buy" / "config_dual.json",
            "exclusion": base_dir / "Dual_Buy" / "exclusionlist.txt",
            "watchlist": base_dir / "Dual_Buy" / "watchlist.txt"
        },
        {
            "name": "Single Buy (E*TRADE)",
            "config": base_dir / "Etrade_Algo" / "single_Trade" / "config_etrade_single.json",
            "exclusion": base_dir / "Etrade_Algo" / "single_Trade" / "exclusionlist.txt",
            "watchlist": base_dir / "Etrade_Algo" / "single_Trade" / "watchlist.txt"
        }
    ]
    
    results = {}
    
    for test in tests:
        try:
            result = test_exclusion_feature(
                test["name"],
                str(test["config"]),
                str(test["exclusion"]),
                str(test["watchlist"])
            )
            results[test["name"]] = result
        except Exception as e:
            print(f"\n✗ FATAL ERROR testing {test['name']}: {e}")
            import traceback
            traceback.print_exc()
            results[test["name"]] = False
    
    # Summary
    print(f"\n\n{'#'*80}")
    print(f"# TEST SUMMARY")
    print(f"{'#'*80}")
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print(f"{'#'*80}")
    
    if all_passed:
        print("\n✓✓✓ ALL IMPLEMENTATIONS PASSED ✓✓✓\n")
        return 0
    else:
        print("\n✗✗✗ SOME IMPLEMENTATIONS FAILED ✗✗✗\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
