#!/usr/bin/env python3
"""
Comprehensive analysis of all stocks in watchlist.txt
"""
import sys
import os
# Add parent directory to path to import the bot module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import RajatAlphaTradingBot
import json

def load_watchlist():
    """Load watchlist from file"""
    watchlist_file = 'config/watchlist.txt'
    try:
        with open(watchlist_file, 'r') as f:
            symbols = [line.strip().upper() for line in f if line.strip()]
        return symbols
    except FileNotFoundError:
        print(f"Watchlist file {watchlist_file} not found!")
        return []

def analyze_stock(bot, symbol):
    """Analyze a single stock and return detailed results"""
    try:
        signal_valid, signal_details = bot.analyzer.analyze_entry_signal(symbol)

        result = {
            'symbol': symbol,
            'signal_valid': signal_valid,
            'reason': signal_details.get('reason', 'Unknown'),
            'score': signal_details.get('score', 0),
            'pattern': signal_details.get('pattern', 'None'),
            'price': signal_details.get('price', 0),
            'checks': signal_details.get('checks', {})
        }

        return result

    except Exception as e:
        return {
            'symbol': symbol,
            'signal_valid': False,
            'reason': f'Error: {str(e)}',
            'score': 0,
            'pattern': 'Error',
            'price': 0,
            'checks': {}
        }

def main():
    print('=== COMPREHENSIVE WATCHLIST ANALYSIS ===')
    print('Analyzing all stocks in watchlist.txt with Rajat Alpha v67 criteria')
    print()

    # Initialize bot
    try:
        bot = RajatAlphaTradingBot(config_path='config/config.json')
    except Exception as e:
        print(f"Failed to initialize bot: {e}")
        return

    # Load watchlist
    watchlist = load_watchlist()
    if not watchlist:
        print("No stocks in watchlist!")
        return

    print(f"Analyzing {len(watchlist)} stocks...")
    print("=" * 80)

    # Analyze all stocks
    results = []
    for symbol in watchlist:
        result = analyze_stock(bot, symbol)
        results.append(result)

    # Categorize results
    passing_stocks = [r for r in results if r['signal_valid']]
    failing_stocks = [r for r in results if not r['signal_valid']]

    # Summary
    print(f"\n=== ANALYSIS SUMMARY ===")
    print(f"Total stocks analyzed: {len(results)}")
    print(f"Stocks PASSING all criteria: {len(passing_stocks)}")
    print(f"Stocks FAILING criteria: {len(failing_stocks)}")
    print()

    # Show passing stocks first
    if passing_stocks:
        print("🎯 STOCKS READY FOR TRADE:")
        print("-" * 40)
        for stock in passing_stocks:
            print(f"✅ {stock['symbol']}: Score {stock['score']:.1f}, Pattern: {stock['pattern']}, Price: ${stock['price']:.2f}")
        print()

    # Group failing stocks by failure reason
    failure_categories = {}
    for stock in failing_stocks:
        reason = stock['reason']
        if reason not in failure_categories:
            failure_categories[reason] = []
        failure_categories[reason].append(stock)

    print("❌ STOCKS FAILING CRITERIA (Grouped by Reason):")
    print("-" * 50)

    for reason, stocks in failure_categories.items():
        print(f"\n🔴 Reason: {reason}")
        print(f"   Affected stocks ({len(stocks)}): {', '.join([s['symbol'] for s in stocks[:10]])}{'...' if len(stocks) > 10 else ''}")

        # Show detailed breakdown for first few stocks in each category
        if len(stocks) <= 5:  # Show details for categories with 5 or fewer stocks
            for stock in stocks:
                checks = stock['checks']
                print(f"   📊 {stock['symbol']} breakdown:")
                print(f"      Market Structure: {'✅' if checks.get('market_structure', False) else '❌'}")
                print(f"      Weekly OK: {'✅' if checks.get('weekly_ok', False) else '❌'}")
                print(f"      Monthly OK: {'✅' if checks.get('monthly_ok', False) else '❌'}")
                print(f"      Pullback: {'✅' if checks.get('pullback', False) else '❌'}")
                print(f"      Pattern: {'✅' if checks.get('pattern', False) else '❌'}")
                print(f"      Stalling: {'✅' if not checks.get('stalling', True) else '❌'}")
                print(f"      Score: {stock['score']:.1f}")

    print("\n" + "=" * 80)
    print("DETAILED ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()