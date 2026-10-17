import sys
import os
import unittest
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import (
    PositionDatabase,
    ConfigManager,
    MarketDataFetcher,
    PatternDetector,
    RajatAlphaAnalyzer,
    PositionManager
)

class TestRajatAlphaV32Upgrades(unittest.TestCase):
    """
    Comprehensive Institutional Test Suite for Rajat Alpha v67 (Version 3.2)
    Verifies all 10 bug fixes, mathematical models, and edge cases.
    """
    
    def setUp(self):
        self.test_db_path = "tests/test_positions_temp.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
            
        self.db = PositionDatabase(self.test_db_path)
        self.config = ConfigManager("config/config.json")
        
    def tearDown(self):
        self.db.conn.close()
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    # =========================================================================
    # 1. CANDLESTICK PATTERNS & REJECTION FILTERS
    # =========================================================================
    def test_hammer_pattern(self):
        """Test Bullish Hammer detection"""
        # Day 1: Red candle
        # Day 2: Hammer (Lower wick 2x body, upper wick <= 20% range)
        data = {
            'open':  [100.0, 95.0],
            'high':  [101.0, 96.0],
            'low':   [94.0,  88.0],
            'close': [95.0,  95.5]
        }
        df = pd.DataFrame(data)
        self.assertTrue(PatternDetector.is_hammer(df))

    def test_upside_reversal_pattern(self):
        """Test Upside Reversal detection"""
        # Day 1: Red candle (open 100, close 90, midpoint 95)
        # Day 2: Opens <= 90, closes > 95, green
        data = {
            'open':  [100.0, 89.5],
            'high':  [101.0, 97.0],
            'low':   [89.5,  89.0],
            'close': [90.0,  96.0]
        }
        df = pd.DataFrame(data)
        self.assertTrue(PatternDetector.is_upside_reversal(df))

    def test_shooting_star_rejection(self):
        """Test Shooting Star rejection filter (Bug 6 fix)"""
        # Green close, but massive upper wick (> 50% of range)
        candle = pd.Series({
            'open': 100.0,
            'high': 110.0,
            'low': 99.5,
            'close': 101.0
        })
        self.assertTrue(PatternDetector.is_shooting_star(candle))

        # Normal healthy green candle should NOT be rejected
        normal_candle = pd.Series({
            'open': 100.0,
            'high': 105.0,
            'low': 99.5,
            'close': 104.5
        })
        self.assertFalse(PatternDetector.is_shooting_star(normal_candle))

    # =========================================================================
    # 2. TOUCH ISOLATION & IMPULSE WAVE RESET (Bug 4 & 5 fixes)
    # =========================================================================
    def test_touch_counter_isolation(self):
        """Test that symbol A's touch count does NOT bleed into symbol B"""
        analyzer = RajatAlphaAnalyzer(self.config, None)
        
        # Simulate AAPL touch
        analyzer.symbol_touch_state['AAPL']['ema21_count'] = 2
        
        # Check MSFT is completely isolated and 0
        self.assertEqual(analyzer.symbol_touch_state['MSFT']['ema21_count'], 0)
        self.assertEqual(analyzer.symbol_touch_state['AAPL']['ema21_count'], 2)

    def test_impulse_wave_reset(self):
        """Test that printing a new 20-bar high >= 5% above EMA21 resets touch state"""
        analyzer = RajatAlphaAnalyzer(self.config, None)
        analyzer.symbol_touch_state['AAPL']['ema21_count'] = 3
        
        # Build 30 bars of data where the last 20 bars contain a strong breakout high
        prices = [100.0] * 25 + [115.0] * 5
        df = pd.DataFrame({
            'open': prices,
            'high': [p + 2.0 for p in prices],
            'low': [p - 1.0 for p in prices],
            'close': prices,
            'volume': [1000000] * 30
        })
        df = analyzer.calculate_indicators(df)
        
        analyzer.update_touch_tracking('AAPL', df)
        # Touch counter should have reset to 0
        self.assertEqual(analyzer.symbol_touch_state['AAPL']['ema21_count'], 0)

    # =========================================================================
    # 3. VOLATILITY-ADAPTIVE ATR INITIAL STOP LOSS
    # =========================================================================
    def test_atr_hybrid_stop_loss(self):
        """Test that low-beta stocks get tighter stops while adhering to caps/floors"""
        # Mock class for position manager
        class MockTradingClient:
            pass
            
        pm = PositionManager(MockTradingClient(), self.config, self.db, None)
        
        # Stock price $100, ATR $2.00 (Low volatility)
        df_low_vol = pd.DataFrame({'ATR14': [2.00]})
        sl_low_vol = pm.calculate_stop_loss('LOW_VOL', 100.0, score=4.0, df=df_low_vol)
        # 100 - (2.0 * 2.0) = $96.00 (-4%), but floor is 5% -> should be $95.00
        self.assertEqual(sl_low_vol, 95.0)

        # High volatility: Stock price $100, ATR $15.00
        df_high_vol = pd.DataFrame({'ATR14': [15.00]})
        sl_high_vol = pm.calculate_stop_loss('HIGH_VOL', 100.0, score=4.0, df=df_high_vol)
        # 100 - (2.0 * 15.0) = $70.00 (-30%), but cap is 17% -> should be $83.00
        self.assertEqual(sl_high_vol, 83.0)

    # =========================================================================
    # 4. MULTI-STAGE STOP LOSS STEPPER & MONOTONIC GUARANTEE
    # =========================================================================
    def test_multi_stage_stepper(self):
        """Test User-Fixed Stepper: -4% @ +5%, BE @ +8%, +3% @ +10%, +1% ratchet"""
        class MockTradingClient:
            pass
        pm = PositionManager(MockTradingClient(), self.config, self.db, None)
        
        # Insert test position: Entry $100, Initial SL $83 (-17%)
        pos_id = self.db.add_position('TEST', 100.0, 100, 83.0, 4.0, initial_stop_loss=83.0)
        pos = self.db.get_position_by_id(pos_id)
        
        # 1. Stock at $104 (+4% gain) -> SL should remain unchanged ($83.00)
        pm.update_trailing_stop_loss(pos, 104.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 83.0)
        
        # 2. Stock hits $105 (+5% gain) -> SL moves to $96.00 (-4% risk)
        pm.update_trailing_stop_loss(pos, 105.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 96.0)
        self.assertEqual(pos['sl_stage'], 1)
        
        # 3. Stock hits $108 (+8% gain) -> SL moves to $100.00 (Breakeven)
        pm.update_trailing_stop_loss(pos, 108.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 100.0)
        self.assertEqual(pos['sl_stage'], 2)
        
        # 4. Stock hits $110 (+10% gain) -> SL moves to $103.00 (+3% locked)
        pm.update_trailing_stop_loss(pos, 110.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 103.0)
        self.assertEqual(pos['sl_stage'], 3)
        
        # 5. Stock hits $115 (+15% gain) -> SL ratchets to $108.00 (+8% locked)
        pm.update_trailing_stop_loss(pos, 115.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 108.0)
        
        # 6. Monotonicity Test: Price drops back to $106 -> SL must NEVER decrease
        pm.update_trailing_stop_loss(pos, 106.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 108.0)

    # =========================================================================
    # 5. FOUR-TIER PARTIAL EXITS & RUNNER PROTOCOL
    # =========================================================================
    def test_four_tier_partial_exits(self):
        """Test PT1 (20% @ 5%), PT2 (25% @ 10%), PT3 (25% @ 15%), Runner (30%)"""
        class MockTradingClient:
            pass
        pm = PositionManager(MockTradingClient(), self.config, self.db, None)
        
        # 100 shares at $100.00
        pos_id = self.db.add_position('RUNNER_TEST', 100.0, 100, 83.0, 4.0)
        pos = self.db.get_position_by_id(pos_id)
        
        # At $105: PT1 should trigger for 20 shares
        exits_5pct = pm.check_partial_exit_targets(pos, 105.0)
        self.assertEqual(len(exits_5pct), 1)
        self.assertEqual(exits_5pct[0][0], 'PT1')
        self.assertEqual(exits_5pct[0][1], 20)
        
        # Execute PT1
        self.db.add_partial_exit(pos_id, 20, 105.0, 'PT1', 5.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['remaining_qty'], 80)
        
        # At $110: PT2 should trigger for 25 shares
        exits_10pct = pm.check_partial_exit_targets(pos, 110.0)
        self.assertEqual(len(exits_10pct), 1)
        self.assertEqual(exits_10pct[0][0], 'PT2')
        self.assertEqual(exits_10pct[0][1], 25)
        
        # Execute PT2
        self.db.add_partial_exit(pos_id, 25, 110.0, 'PT2', 10.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['remaining_qty'], 55)

        # At $115: PT3 should trigger for 25 shares, leaving 30 shares
        exits_15pct = pm.check_partial_exit_targets(pos, 115.0)
        self.assertEqual(len(exits_15pct), 1)
        self.assertEqual(exits_15pct[0][0], 'PT3')
        self.assertEqual(exits_15pct[0][1], 25)
        
        # Execute PT3 and activate runner mode
        self.db.add_partial_exit(pos_id, 25, 115.0, 'PT3', 15.0)
        self.db.set_runner_mode(pos_id)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['remaining_qty'], 30)
        self.assertEqual(pos['is_runner'], 1)

    # =========================================================================
    # 6. GHOST POSITION ZERO-QUANTITY BUG FIX (Bug 1 fix)
    # =========================================================================
    def test_ghost_position_exclusion(self):
        """Test that get_open_positions excludes records where remaining_qty <= 0"""
        # Add normal position
        self.db.add_position('ACTIVE', 50.0, 100, 45.0, 4.0)
        
        # Add ghost position (remaining_qty = 0, but status = 'OPEN')
        cursor = self.db.conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, quantity, remaining_qty, stop_loss, status)
            VALUES ('GHOST', CURRENT_TIMESTAMP, 50.0, 100, 0, 45.0, 'OPEN');
        ''')
        self.db.conn.commit()
        
        open_positions = self.db.get_open_positions()
        symbols = [p['symbol'] for p in open_positions]
        self.assertIn('ACTIVE', symbols)
        self.assertNotIn('GHOST', symbols)

    # =========================================================================
    # 7. TRUE CLOSING BASIS & FIRST-HOUR GUARD (Bug 2 fix)
    # =========================================================================
    def test_closing_basis_and_first_hour_guard(self):
        """Test that intraday dips and first-hour noise do NOT trigger premature stops"""
        class MockTradingClient:
            pass
        pm = PositionManager(MockTradingClient(), self.config, self.db, None)
        pos = {'entry_price': 100.0, 'stop_loss': 95.0, 'symbol': 'TEST'}
        
        # Price dips to $94.00 at 10:15 AM (Intraday, not closing window)
        # Should NOT trigger stop loss under confirmed daily close evaluation
        is_stopped = pm.check_stop_loss(pos, 94.0, is_closing_window=False, is_first_hour_suppressed=False)
        self.assertFalse(is_stopped)
        
        # Price at $94.00 during first hour (09:35 AM) with guard active -> SUPPRESSED
        is_stopped_fh = pm.check_stop_loss(pos, 94.0, is_closing_window=False, is_first_hour_suppressed=True)
        self.assertFalse(is_stopped_fh)
        
        # Price at $94.00 at 15:58 PM (Daily Close Window) -> TRIGGERS
        is_stopped_close = pm.check_stop_loss(pos, 94.0, is_closing_window=True, is_first_hour_suppressed=False)
        self.assertTrue(is_stopped_close)
        
        # Emergency catastrophic breaker: Price drops to $75.00 (-25%) -> IMMEDIATE TRIGGER ANYTIME
        is_catastrophic = pm.check_stop_loss(pos, 75.0, is_closing_window=False, is_first_hour_suppressed=True)
        self.assertTrue(is_catastrophic)

if __name__ == '__main__':
    unittest.main()
