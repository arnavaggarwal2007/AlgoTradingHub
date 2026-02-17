#!/usr/bin/env python3
"""
Test individual stock analysis to understand why signals are failing
"""
import sys
import os
# Add parent directory to path to import the bot module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import RajatAlphaTradingBot

def main():
    # Initialize bot
    bot = RajatAlphaTradingBot()

    # Test a few stocks to see why they're failing
    test_stocks = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']

    print('=== TESTING INDIVIDUAL STOCK ANALYSIS ===')
    print()

    for symbol in test_stocks:
        print(f'--- Analyzing {symbol} ---')
        try:
            signal_valid, signal_details = bot.analyzer.analyze_entry_signal(symbol)

            if signal_valid:
                print(f'✅ {symbol}: SIGNAL DETECTED!')
                print(f'   Score: {signal_details["score"]:.1f}')
                print(f'   Pattern: {signal_details["pattern"]}')
                print(f'   Price: ${signal_details["price"]:.2f}')
            else:
                print(f'❌ {symbol}: Signal failed - {signal_details["reason"]}')

            # Show the checks
            checks = signal_details.get('checks', {})
            print(f'   Market Structure: {"✅" if checks.get("market_structure", False) else "❌"}')
            print(f'   Weekly OK: {"✅" if checks.get("weekly_ok", False) else "❌"}')
            print(f'   Monthly OK: {"✅" if checks.get("monthly_ok", False) else "❌"}')
            print(f'   Pullback: {"✅" if checks.get("pullback", False) else "❌"}')
            print(f'   Pattern: {"✅" if checks.get("pattern", False) else "❌"}')
            print(f'   Stalling: {"✅" if not checks.get("stalling", True) else "❌"}')

        except Exception as e:
            print(f'❌ {symbol}: Error - {str(e)}')

        print()

if __name__ == "__main__":
    main()