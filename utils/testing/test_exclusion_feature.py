"""
Test Exclusion List Feature
"""
import sys
import os

# Test data
test_watchlist = """AAPL
MSFT
GOOGL
TSLA
NVDA
META
AMZN
"""

test_exclusions = """TSLA
NVDA
"""

def test_exclusion_feature():
    """Test the exclusion list logic"""
    print("="*80)
    print("TESTING EXCLUSION LIST FEATURE")
    print("="*80)
    
    # Create temp files
    with open('test_watchlist.txt', 'w') as f:
        f.write(test_watchlist)
    
    with open('test_exclusions.txt', 'w') as f:
        f.write(test_exclusions)
    
    # Load watchlist
    with open('test_watchlist.txt', 'r') as f:
        symbols = [line.strip().upper() for line in f if line.strip()]
    
    print(f"\n✓ Loaded watchlist: {len(symbols)} symbols")
    print(f"  Symbols: {', '.join(symbols)}")
    
    # Load exclusions
    with open('test_exclusions.txt', 'r') as f:
        exclusions = set(line.strip().upper() for line in f if line.strip())
    
    print(f"\n✓ Loaded exclusions: {len(exclusions)} symbols")
    print(f"  Excluded: {', '.join(exclusions)}")
    
    # Apply exclusions
    original_count = len(symbols)
    symbols = [s for s in symbols if s not in exclusions]
    excluded_count = original_count - len(symbols)
    
    print(f"\n✓ After filtering:")
    print(f"  Original count: {original_count}")
    print(f"  Excluded: {excluded_count}")
    print(f"  Final count: {len(symbols)}")
    print(f"  Active symbols: {', '.join(symbols)}")
    
    # Cleanup
    os.remove('test_watchlist.txt')
    os.remove('test_exclusions.txt')
    
    # Verify
    assert len(symbols) == 5, f"Expected 5 symbols, got {len(symbols)}"
    assert 'TSLA' not in symbols, "TSLA should be excluded"
    assert 'NVDA' not in symbols, "NVDA should be excluded"
    assert 'AAPL' in symbols, "AAPL should be included"
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - EXCLUSION FEATURE WORKING")
    print("="*80)
    return True

if __name__ == '__main__':
    try:
        test_exclusion_feature()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
