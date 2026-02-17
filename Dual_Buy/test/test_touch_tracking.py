#!/usr/bin/env python3
"""
Test script to verify touch tracking functionality in Dual_Buy implementation
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from rajat_alpha_v67_dual import RajatAlphaAnalyzer
import pandas as pd
import numpy as np
from unittest.mock import Mock

def create_test_config():
    """Create a mock config for testing"""
    config = Mock()
    config.get = Mock(side_effect=lambda section, key: {
        'strategy_params': {
            'ma_touch_threshold_pct': 0.025  # 2.5%
        }
    }.get(section, {}).get(key, None))
    return config

def create_test_data_fetcher():
    """Create a mock data fetcher"""
    fetcher = Mock()
    return fetcher

def test_touch_tracking():
    """Test touch tracking functionality"""
    print("Testing Touch Tracking Functionality...")

    # Create analyzer
    config = create_test_config()
    data_fetcher = create_test_data_fetcher()
    analyzer = RajatAlphaAnalyzer(config, data_fetcher)

    # Test initial state
    assert analyzer.touch_ema21_count == 0, "Initial EMA21 touch count should be 0"
    assert analyzer.touch_sma50_count == 0, "Initial SMA50 touch count should be 0"
    assert analyzer.new_trend == True, "Initial new_trend should be True"
    print("✓ Initial state correct")

    # Create test dataframe with price touching EMA21
    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    df = pd.DataFrame({
        'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        'SMA50': [95, 96, 97, 98, 99, 100, 101, 102, 103, 104],
        'SMA200': [90, 91, 92, 93, 94, 95, 96, 97, 98, 99],
        'EMA21': [108, 108.1, 108.2, 108.3, 108.4, 108.5, 108.6, 108.7, 108.8, 108.9]  # Close to current price
    }, index=dates)

    # Test EMA21 touch (price within 2.5% of EMA21)
    analyzer.update_touch_tracking(df)
    assert analyzer.touch_ema21_count == 1, f"EMA21 touch should be detected, count: {analyzer.touch_ema21_count}"
    print("✓ EMA21 touch detection working")

    # Test SMA50 touch (price within 2.5% of SMA50)
    df_touch_sma = df.copy()
    df_touch_sma['SMA50'] = [107, 107.1, 107.2, 107.3, 107.4, 107.5, 107.6, 107.7, 107.8, 107.9]  # Close to current price
    analyzer.update_touch_tracking(df_touch_sma)
    assert analyzer.touch_sma50_count == 1, f"SMA50 touch should be detected, count: {analyzer.touch_sma50_count}"
    print("✓ SMA50 touch detection working")

    # Test new trend reset (SMA50 crosses above SMA200)
    df_new_trend = df.copy()
    df_new_trend['SMA50'] = [99, 99.1, 99.2, 99.3, 99.4, 99.5, 99.6, 99.7, 99.8, 100.1]  # Crosses above SMA200
    df_new_trend['SMA200'] = [99, 99.1, 99.2, 99.3, 99.4, 99.5, 99.6, 99.7, 99.8, 99.9]  # SMA200 values
    analyzer.update_touch_tracking(df_new_trend)
    assert analyzer.new_trend == True, "New trend should be detected"
    assert analyzer.touch_ema21_count == 0, f"Touch counters should reset on new trend, EMA21: {analyzer.touch_ema21_count}"
    assert analyzer.touch_sma50_count == 0, f"Touch counters should reset on new trend, SMA50: {analyzer.touch_sma50_count}"
    print("✓ New trend reset working")

    print("All touch tracking tests passed! ✓")

def test_scoring_with_touch_bonuses():
    """Test that scoring includes touch bonuses"""
    print("\nTesting Scoring with Touch Bonuses...")

    config = create_test_config()
    data_fetcher = create_test_data_fetcher()
    analyzer = RajatAlphaAnalyzer(config, data_fetcher)

    # Create test dataframe
    dates = pd.date_range('2024-01-01', periods=25, freq='D')
    df = pd.DataFrame({
        'close': [100] * 25,
        'low': [95] * 25,  # In demand zone (below 21-day low * 1.035)
        'volume': [1000] * 25,
        'VOL_SMA21': [900] * 25,  # Volume above average
        'SMA50': [98] * 25,
        'SMA200': [90] * 25,
        'EMA21': [99] * 25
    }, index=dates)

    # Mock data fetcher for benchmark data
    benchmark_df = pd.DataFrame({
        'close': [50] * 25
    }, index=dates)
    data_fetcher.get_daily_bars = Mock(return_value=benchmark_df)

    # Test scoring without touch bonuses
    score_no_touch = analyzer.calculate_score(df, 'TEST', True, True)
    expected_base_score = 4  # weekly + monthly + volume + demand zone
    assert score_no_touch == expected_base_score, f"Base score should be {expected_base_score}, got {score_no_touch}"
    print(f"✓ Base score without touches: {score_no_touch}")

    # Add touch bonuses
    analyzer.touch_ema21_count = 1
    analyzer.touch_sma50_count = 1

    score_with_touches = analyzer.calculate_score(df, 'TEST', True, True)
    expected_score_with_bonuses = expected_base_score + 1.0  # +0.5 EMA21 + 0.5 SMA50
    assert score_with_touches == expected_score_with_bonuses, f"Score with touches should be {expected_score_with_bonuses}, got {score_with_touches}"
    print(f"✓ Score with touch bonuses: {score_with_touches}")

    print("All scoring tests passed! ✓")

if __name__ == "__main__":
    test_touch_tracking()
    test_scoring_with_touch_bonuses()
    print("\n🎉 All tests passed! Touch tracking functionality is working correctly.")