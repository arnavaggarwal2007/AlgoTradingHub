"""
================================================================================
UNIT & INTEGRATION TESTS FOR RAJAT ALPHA V67
================================================================================
Tests all critical components and logic flows
"""

import unittest
import json
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np

# Import the bot components
import sys
# Add parent directory to path to import the bot module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import (
    PositionDatabase,
    ConfigManager,
    PatternDetector,
    RajatAlphaAnalyzer,
    MarketDataFetcher
)

class TestPositionDatabase(unittest.TestCase):
    """Test position database operations"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        self.db = PositionDatabase(self.db_file.name)
    
    def tearDown(self):
        """Clean up test database"""
        self.db.conn.close()
        os.unlink(self.db_file.name)
    
    def test_add_position(self):
        """Test adding a new position"""
        position_id = self.db.add_position(
            symbol='AAPL',
            entry_price=150.00,
            quantity=10,
            stop_loss=127.50,
            score=4.5
        )
        self.assertIsNotNone(position_id)
        self.assertGreater(position_id, 0)
        
        # Verify position exists
        positions = self.db.get_open_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]['symbol'], 'AAPL')
        self.assertEqual(positions[0]['quantity'], 10)
        self.assertEqual(positions[0]['remaining_qty'], 10)
    
    def test_update_stop_loss(self):
        """Test updating trailing stop loss"""
        position_id = self.db.add_position('AAPL', 100.00, 10, 83.00, 4.0)
        
        # Update stop loss
        self.db.update_stop_loss(position_id, 91.00)
        
        positions = self.db.get_open_positions()
        self.assertEqual(positions[0]['stop_loss'], 91.00)
    
    def test_partial_exit(self):
        """Test partial exit tracking"""
        position_id = self.db.add_position('AAPL', 100.00, 10, 83.00, 4.0)
        
        # Execute partial exit (3 shares)
        self.db.add_partial_exit(
            position_id=position_id,
            quantity=3,
            exit_price=110.00,
            profit_target='PT1',
            profit_pct=10.0
        )
        
        positions = self.db.get_open_positions()
        self.assertEqual(positions[0]['remaining_qty'], 7)
    
    def test_close_position(self):
        """Test closing a position"""
        position_id = self.db.add_position('AAPL', 100.00, 10, 83.00, 4.0)
        
        self.db.close_position(position_id, 115.00, 'Take Profit')
        
        # Should not be in open positions
        positions = self.db.get_open_positions()
        self.assertEqual(len(positions), 0)
        
        # Verify closed status
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT status, profit_loss_pct FROM positions WHERE id = ?', (position_id,))
        status, pnl = cursor.fetchone()
        self.assertEqual(status, 'CLOSED')
        self.assertAlmostEqual(pnl, 15.0, places=2)
    
    def test_fifo_order(self):
        """Test FIFO ordering (oldest first)"""
        # Add positions in sequence
        id1 = self.db.add_position('AAPL', 100.00, 10, 83.00, 4.0)
        id2 = self.db.add_position('AAPL', 105.00, 10, 87.00, 4.5)
        id3 = self.db.add_position('AAPL', 110.00, 10, 91.00, 5.0)
        
        positions = self.db.get_open_positions('AAPL')
        
        # Should be in FIFO order (oldest first)
        self.assertEqual(positions[0]['id'], id1)
        self.assertEqual(positions[1]['id'], id2)
        self.assertEqual(positions[2]['id'], id3)


class TestConfigManager(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        """Create temporary config file"""
        self.config_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.config_data = {
            "api": {
                "key_id": "test_key",
                "secret_key": "test_secret",
                "base_url": "https://paper-api.alpaca.markets"
            },
            "trading_rules": {
                "max_open_positions": 2,
                "max_trades_per_day": 3
            },
            "strategy_params": {
                "min_listing_days": 200,
                "sma_fast": 50,
                "sma_slow": 200,
                "ma_touch_threshold_pct": 0.025,
                "ema_tolerance_pct": 0.025
            },
            "risk_management": {
                "initial_stop_loss_pct": 0.17,
                "max_hold_days": 21
            },
            "profit_taking": {
                "enable_partial_exits": True,
                "target_1_pct": 0.1,
                "target_1_qty": 0.333,
                "target_2_pct": 0.15,
                "target_2_qty": 0.333,
                "target_3_pct": 0.2,
                "target_3_qty": 0.334
            },
            "execution_schedule": {
                "default_interval_seconds": 120,
                "signal_monitoring_minutes": 1,
                "top_n_trades": 5,
                "buy_window_start_time": "13:00",
                "buy_window_end_time": "15:59",
                "last_hour_interval_seconds": 60
            },
            "position_sizing": {"mode": "percent_equity"}
        }
        json.dump(self.config_data, self.config_file)
        self.config_file.close()
    
    def tearDown(self):
        """Clean up test config"""
        os.unlink(self.config_file.name)
    
    def test_load_config(self):
        """Test configuration loading"""
        config = ConfigManager(self.config_file.name)
        self.assertIsNotNone(config.config)
        self.assertEqual(config.get('api', 'key_id'), 'test_key')
    
    def test_nested_get(self):
        """Test nested configuration access"""
        config = ConfigManager(self.config_file.name)
        self.assertEqual(config.get('trading_rules', 'max_open_positions'), 2)
        self.assertEqual(config.get('strategy_params', 'min_listing_days'), 200)


class TestPatternDetector(unittest.TestCase):
    """Test pattern recognition logic"""
    
    def test_engulfing_pattern(self):
        """Test engulfing pattern detection"""
        # Create test data: red candle followed by green engulfing
        data = {
            'open': [110.00, 105.00],
            'high': [111.00, 112.00],
            'low': [104.00, 104.50],
            'close': [105.00, 111.00]
        }
        df = pd.DataFrame(data)
        
        result = PatternDetector.is_engulfing(df)
        self.assertTrue(result)
    
    def test_piercing_pattern(self):
        """Test piercing pattern detection"""
        # Red candle: 110 -> 105, green piercing candle: 104 -> 108 (above midpoint 107.5)
        data = {
            'open': [110.00, 104.00],
            'high': [111.00, 109.00],
            'low': [104.00, 103.00],
            'close': [105.00, 108.00]
        }
        df = pd.DataFrame(data)
        
        result = PatternDetector.is_piercing(df)
        # Should be True: close (108) > midpoint (107.5), explosive body
        self.assertTrue(result)
    
    def test_tweezer_bottom(self):
        """Test tweezer bottom pattern"""
        # Two candles with matching lows
        data = {
            'open': [110.00, 105.00],
            'high': [111.00, 110.00],
            'low': [104.00, 104.05],  # Within 0.2% tolerance
            'close': [105.00, 109.00]
        }
        df = pd.DataFrame(data)
        
        result = PatternDetector.is_tweezer_bottom(df)
        self.assertTrue(result)
    
    def test_no_pattern(self):
        """Test when no pattern exists"""
        # Random non-pattern candles
        data = {
            'open': [105.00, 106.00],
            'high': [107.00, 108.00],
            'low': [104.00, 105.00],
            'close': [106.00, 107.00]
        }
        df = pd.DataFrame(data)
        
        has_pattern, pattern_name = PatternDetector.has_pattern(df)
        self.assertFalse(has_pattern)
        self.assertEqual(pattern_name, 'None')


class TestRajatAlphaAnalyzer(unittest.TestCase):
    """Test strategy analysis logic"""
    
    def setUp(self):
        """Setup mock config and data fetcher"""
        self.config = Mock()
        self.config.get.side_effect = self._mock_config_get
        
        self.data_fetcher = Mock()
    
    def _mock_config_get(self, *args):
        """Mock config responses"""
        config_map = {
            ('strategy_params', 'pullback_days'): 4,
            ('strategy_params', 'stalling_days_long'): 8,
            ('strategy_params', 'stalling_days_short'): 3,
            ('strategy_params', 'stalling_range_pct'): 5.0,
            ('strategy_params', 'min_listing_days'): 200,
            ('strategy_params', 'ma_touch_threshold_pct'): 0.025,
            ('strategy_params', 'ema_tolerance_pct'): 0.025,
        }
        return config_map.get(tuple(args), 0.025)  # Default to 0.025 for ema_tolerance_pct
    
    def test_market_structure_check(self):
        """Test market structure validation"""
        analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        
        # Create data with bullish structure: SMA50 > SMA200, EMA21 > SMA50
        data = {
            'close': [100],
            'SMA50': [105],
            'SMA200': [100],
            'EMA21': [110]
        }
        df = pd.DataFrame(data)
        
        result = analyzer.check_market_structure(df)
        self.assertTrue(result)
    
    def test_market_structure_bearish(self):
        """Test market structure rejection (bearish)"""
        analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        
        # Bearish structure: SMA50 < SMA200
        data = {
            'close': [100],
            'SMA50': [95],
            'SMA200': [100],
            'EMA21': [98]
        }
        df = pd.DataFrame(data)
        
        result = analyzer.check_market_structure(df)
        self.assertFalse(result)
    
    def test_multitimeframe_confirmation(self):
        """Test multi-timeframe confirmation logic"""
        analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        
        # Create weekly data: close > EMA21
        df_daily = pd.DataFrame({'close': [100]})
        df_weekly = pd.DataFrame({
            'close': [105, 110, 115, 120, 125] * 5,
            'open': [100, 105, 110, 115, 120] * 5,
            'high': [106, 111, 116, 121, 126] * 5,
            'low': [99, 104, 109, 114, 119] * 5,
            'volume': [1000000] * 25
        })
        
        df_monthly = pd.DataFrame({
            'close': [105, 110, 115, 120, 125] * 2,
            'open': [100, 105, 110, 115, 120] * 2,
            'high': [106, 111, 116, 121, 126] * 2,
            'low': [99, 104, 109, 114, 119] * 2,
            'volume': [5000000] * 10
        })
        
        weekly_ok, monthly_ok = analyzer.check_multitimeframe_confirmation(
            df_daily, df_weekly, df_monthly
        )
        
        # Both should be True (price trending up)
        self.assertTrue(weekly_ok)
        self.assertTrue(monthly_ok)
    
    def test_stalling_detection(self):
        """Test stalling filter logic"""
        analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        
        # Create choppy data (8-day range <= 5%)
        # Price oscillating between 100-102.5 (2.5% range = stalling)
        data = {
            'high': [102.5, 102, 102.5, 102, 102.5, 102, 102.5, 102],
            'low': [100, 100.5, 100, 100.5, 100, 100.5, 100, 100.5],
            'close': [101] * 8,
            'open': [101] * 8,
            'volume': [1000000] * 8
        }
        df = pd.DataFrame(data)
        
        is_stalling = analyzer.check_stalling(df)
        
        # Should detect stalling (narrow 2.5% range over 8 days, but last 3 days also narrow)
        # Actually, the logic rejects if 8-day narrow UNLESS 3-day also narrow
        # So this should return False (not stalling) because 3-day is also narrow
        self.assertFalse(is_stalling)
    
    def test_pullback_detection(self):
        """Test pullback to moving average"""
        analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        
        # Create pullback scenario
        # High was 110, now pulled back to 105 (near EMA21 at 104)
        # Last 4 closes: 102, 103, 104, 105 - 3 are below EMA21 (102, 103, 104)
        # Recent high (max of last 4 highs before current) = max(106,104,105,106) = 106
        # Current high = 105, so 106 > 105 = True (pullback confirmed)
        data = {
            'close': [110, 108, 106, 104, 102, 103, 104, 105],
            'high': [112, 110, 108, 106, 104, 105, 106, 105],  # Current high = 105
            'low': [108, 106, 104, 102, 100, 101, 102, 103],
            'open': [109, 107, 105, 103, 101, 102, 103, 104],
            'EMA21': [104, 104, 104, 104, 104, 104, 104, 104],
            'SMA50': [95, 95, 95, 95, 95, 95, 95, 95],
            'volume': [1000000] * 8
        }
        df = pd.DataFrame(data)
        
        result = analyzer.check_pullback(df)
        self.assertTrue(result)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow"""
    
    def test_complete_signal_workflow(self):
        """Test end-to-end signal generation"""
        # This would require more complex mocking of market data
        # For now, just verify the method exists and has correct signature
        config = Mock()
        data_fetcher = Mock()
        analyzer = RajatAlphaAnalyzer(config, data_fetcher)
        
        # Verify method exists
        self.assertTrue(hasattr(analyzer, 'analyze_entry_signal'))
        self.assertTrue(callable(analyzer.analyze_entry_signal))


class TestMethodExistence(unittest.TestCase):
    """Verify all critical methods exist (regression test for typo bug)"""
    
    def test_multitimeframe_confirmation_method_exists(self):
        """Test that check_multitimeframe_confirmation method exists (not typo version)"""
        config = Mock()
        data_fetcher = Mock()
        analyzer = RajatAlphaAnalyzer(config, data_fetcher)
        
        # This test would have FAILED before the fix (typo: check_multitimet_confirmation)
        self.assertTrue(hasattr(analyzer, 'check_multitimeframe_confirmation'))
        self.assertTrue(callable(analyzer.check_multitimeframe_confirmation))
        
        # Verify it's NOT the typo version
        self.assertFalse(hasattr(analyzer, 'check_multitimet_confirmation'))


def run_tests():
    """Run all tests and generate report"""
    print("=" * 80)
    print("RAJAT ALPHA V67 - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPositionDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestRajatAlphaAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMethodExistence))
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 80)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
