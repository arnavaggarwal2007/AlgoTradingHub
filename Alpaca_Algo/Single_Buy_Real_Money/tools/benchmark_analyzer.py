#!/usr/bin/env python3
"""
Test script to check SPY and QQQ data fetching
"""
import sys
import os
# Add parent directory to path to import the bot module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import RajatAlphaTradingBot
import pandas as pd
from datetime import datetime, timedelta

def test_benchmark_data():
    """Test fetching SPY and QQQ data"""
    print("Testing SPY and QQQ data fetching...")

    try:
        # Initialize bot
        bot = RajatAlphaTradingBot(config_path='config/config.json')

        # Test symbols
        symbols = ['SPY', 'QQQ']

        for symbol in symbols:
            print(f"\n--- Testing {symbol} ---")

            try:
                # Get data using the same method as the bot
                df = bot.data_fetcher.get_daily_bars(symbol, days=30)

                if df is not None and not df.empty:
                    print(f"✅ {symbol}: Successfully fetched {len(df)} rows")
                    print(f"   Date range: {df.index.min()} to {df.index.max()}")
                    print(f"   Latest price: {df['close'].iloc[-1]:.2f}")
                    print(f"   Columns: {list(df.columns)}")

                    # Check for required columns
                    required_cols = ['open', 'high', 'low', 'close', 'volume']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        print(f"   ⚠️  Missing columns: {missing_cols}")
                    else:
                        print("   ✅ All required columns present")
                else:
                    print(f"❌ {symbol}: No data returned or empty dataframe")

            except Exception as e:
                print(f"❌ {symbol}: Error fetching data - {str(e)}")

        print("\n--- Test Complete ---")

    except Exception as e:
        print(f"❌ Bot initialization failed: {str(e)}")

if __name__ == "__main__":
    test_benchmark_data()