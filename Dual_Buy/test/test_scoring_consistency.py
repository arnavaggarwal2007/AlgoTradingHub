#!/usr/bin/env python3
"""
Comprehensive test to verify Single_Buy and Dual_Buy implementations produce identical results
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Single_Buy'))

from rajat_alpha_v67_dual import RajatAlphaAnalyzer as DualAnalyzer
from rajat_alpha_v67_single import RajatAlphaAnalyzer as SingleAnalyzer
import pandas as pd
import numpy as np
from unittest.mock import Mock

def create_test_config():
    """Create identical mock configs for both implementations"""
    config = Mock()
    config.get = Mock(side_effect=lambda section, key: {
        'strategy_params': {
            'ma_touch_threshold_pct': 0.025,  # 2.5%
            'min_listing_days': 100,
            'pullback_days': 4,
            'stalling_days_long': 8,
            'stalling_days_short': 3,
            'stalling_range_pct': 5.0,
            'enable_extended_filter': False,
            'max_gap_pct': 0.04,
            'lookback_for_gap': 1
        },
        'trading_rules': {
            'min_signal_score': 3
        }
    }.get(section, {}).get(key, None))
    return config

def create_test_data_fetcher():
    """Create mock data fetcher with identical benchmark data"""
    fetcher = Mock()

    # Create benchmark data (QQQ/SPY)
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    benchmark_df = pd.DataFrame({
        'close': [400 + i*0.5 for i in range(30)]  # Steady upward trend
    }, index=dates)

    fetcher.get_daily_bars = Mock(return_value=benchmark_df)
    fetcher.get_weekly_bars = Mock(return_value=None)  # Not testing weekly bars
    fetcher.get_monthly_bars = Mock(return_value=None)  # Not testing monthly bars
    fetcher.get_current_price = Mock(return_value=100.0)

    return fetcher

def create_test_stock_data():
    """Create test stock data that should produce consistent results"""
    dates = pd.date_range('2024-01-01', periods=150, freq='D')

    # Create stock with upward trend, touches, and all positive signals
    base_price = 100
    prices = []
    for i in range(150):
        # Add some volatility but overall upward trend
        price = base_price + i * 0.1 + np.sin(i * 0.1) * 2
        prices.append(price)

    df = pd.DataFrame({
        'close': prices,
        'high': [p + 1 for p in prices],
        'low': [p - 1 for p in prices],
        'volume': [100000] * 150,
        'open': [p - 0.5 for p in prices]
    }, index=dates)

    # Pre-calculate indicators to ensure they exist
    import pandas_ta as ta
    df['SMA50'] = ta.sma(df['close'], length=50)
    df['SMA200'] = ta.sma(df['close'], length=200)
    df['EMA21'] = ta.ema(df['close'], length=21)
    df['VOL_SMA21'] = ta.sma(df['volume'], length=21)

    # Fill NaN values with reasonable defaults
    df = df.fillna(method='bfill').fillna(method='ffill')

    return df

def test_identical_scoring():
    """Test that both implementations produce identical scores"""
    print("Testing Identical Scoring Between Single_Buy and Dual_Buy...")

    # Create identical setups
    config = create_test_config()
    data_fetcher = create_test_data_fetcher()

    single_analyzer = SingleAnalyzer(config, data_fetcher)
    dual_analyzer = DualAnalyzer(config, data_fetcher)

    # Create test data
    df_daily = create_test_stock_data()

    # Calculate indicators for both
    df_single = single_analyzer.calculate_indicators(df_daily.copy())
    df_dual = dual_analyzer.calculate_indicators(df_daily.copy())

    # Update touch tracking for both
    single_analyzer.update_touch_tracking(df_single)
    dual_analyzer.update_touch_tracking(df_dual)

    # Test scoring with same inputs
    weekly_ok = True
    monthly_ok = True

    score_single = single_analyzer.calculate_score(df_single, 'TEST', weekly_ok, monthly_ok)
    score_dual = dual_analyzer.calculate_score(df_dual, 'TEST', weekly_ok, monthly_ok)

    print(f"Single_Buy score: {score_single}")
    print(f"Dual_Buy score: {score_dual}")

    assert abs(score_single - score_dual) < 0.001, f"Scores should be identical: Single={score_single}, Dual={score_dual}"
    print("✓ Scores are identical")

    # Test touch counters
    assert single_analyzer.touch_ema21_count == dual_analyzer.touch_ema21_count, "EMA21 touch counts should match"
    assert single_analyzer.touch_sma50_count == dual_analyzer.touch_sma50_count, "SMA50 touch counts should match"
    print("✓ Touch counters are identical")

    print("All scoring consistency tests passed! ✓")

def test_touch_bonus_scenarios():
    """Test various touch bonus scenarios with simple data"""
    print("\nTesting Touch Bonus Scenarios...")

    config = create_test_config()
    data_fetcher = create_test_data_fetcher()

    single_analyzer = SingleAnalyzer(config, data_fetcher)
    dual_analyzer = DualAnalyzer(config, data_fetcher)

    # Create simple test data with all indicators pre-calculated
    dates = pd.date_range('2024-01-01', periods=25, freq='D')
    df = pd.DataFrame({
        'close': [100] * 25,
        'high': [105] * 25,
        'low': [95] * 25,  # In demand zone
        'volume': [1000] * 25,
        'VOL_SMA21': [900] * 25,  # Volume above average
        'SMA50': [98] * 25,
        'SMA200': [90] * 25,
        'EMA21': [99] * 25
    }, index=dates)

    # Mock benchmark data
    benchmark_df = pd.DataFrame({'close': [50] * 25}, index=dates)
    data_fetcher.get_daily_bars = Mock(return_value=benchmark_df)

    # Test 1: No touches
    single_analyzer.touch_ema21_count = 0
    single_analyzer.touch_sma50_count = 0
    dual_analyzer.touch_ema21_count = 0
    dual_analyzer.touch_sma50_count = 0

    score_single = single_analyzer.calculate_score(df, 'TEST', True, True)
    score_dual = dual_analyzer.calculate_score(df, 'TEST', True, True)

    print(f"No touch - Single: {score_single}, Dual: {score_dual}")
    assert abs(score_single - score_dual) < 0.001, f"No touch scores should match: Single={score_single}, Dual={score_dual}"

    # Test 2: EMA21 touch only
    single_analyzer.touch_ema21_count = 1
    dual_analyzer.touch_ema21_count = 1

    score_single_ema = single_analyzer.calculate_score(df, 'TEST', True, True)
    score_dual_ema = dual_analyzer.calculate_score(df, 'TEST', True, True)

    print(f"EMA21 touch - Single: {score_single_ema}, Dual: {score_dual_ema}")
    assert abs(score_single_ema - score_dual_ema) < 0.001, "EMA21 touch scores should match"
    assert score_single_ema == score_single + 0.5, "EMA21 touch should add 0.5"

    # Test 3: Both touches
    single_analyzer.touch_sma50_count = 1
    dual_analyzer.touch_sma50_count = 1

    score_single_both = single_analyzer.calculate_score(df, 'TEST', True, True)
    score_dual_both = dual_analyzer.calculate_score(df, 'TEST', True, True)

    print(f"Both touches - Single: {score_single_both}, Dual: {score_dual_both}")
    assert abs(score_single_both - score_dual_both) < 0.001, "Both touch scores should match"
    assert score_single_both == score_single + 1.0, "Both touches should add 1.0"

    print("✓ All touch bonus scenarios working correctly")

if __name__ == "__main__":
    test_touch_bonus_scenarios()
    print("\n🎉 Touch bonus functionality verified! Single_Buy and Dual_Buy now have identical scoring.")