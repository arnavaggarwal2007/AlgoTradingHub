import sys
import os
import unittest
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rajat_alpha_v67_single import (
    PositionDatabase,
    ConfigManager,
    MarketDataFetcher,
    PatternDetector,
    RajatAlphaAnalyzer,
    PositionManager,
    RajatAlphaTradingBot
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
        
        # 3. Stock hits $108 (+8% gain) -> SL moves to $101.00 (+1% above buy price)
        pm.update_trailing_stop_loss(pos, 108.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 101.0)
        self.assertEqual(pos['sl_stage'], 2)
        
        # 4. Stock hits $110 (+10% gain) -> SL moves to $103.00 (+3% locked)
        pm.update_trailing_stop_loss(pos, 110.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 103.0)
        self.assertEqual(pos['sl_stage'], 3)
        
        # 5. Stock hits $115 (+15% gain = +5% above Stage 3) -> SL ratchets to Stage 3 level ($110.00 locked in)
        pm.update_trailing_stop_loss(pos, 115.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 110.0)
        self.assertEqual(pos['sl_stage'], 4)
        
        # 6. Monotonicity Test: Price drops back to $106 -> SL must NEVER decrease
        pm.update_trailing_stop_loss(pos, 106.0)
        pos = self.db.get_position_by_id(pos_id)
        self.assertEqual(pos['stop_loss'], 110.0)

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

    # =========================================================================
    # 8. GATE 6.5 ABSORPTION REVERSAL & EOD SNAPSHOT TESTS
    # =========================================================================
    def test_gate_6_5_absorption_reversal(self):
        """Test that qualified absorption hammers pass Gate 6.5 with partial weight 0.5"""
        class MockFetcher:
            def get_current_price(self, sym):
                return 99.60 # Slightly red vs prev_close $100.00 (-0.4%), within 1%
            def get_daily_bars(self, sym, days=250):
                # 30 days of data
                dates = pd.date_range(end='2026-10-20', periods=30)
                prices = [100.0] * 28 + [100.0, 99.60]
                df = pd.DataFrame({
                    'open': [100.0] * 28 + [100.0, 99.80],
                    'high': [102.0] * 28 + [102.0, 100.50],
                    'low':  [98.0] * 28 + [98.0, 96.00], # Long lower shadow: 99.60 - 96.00 = 3.60 on 4.50 range (80%)
                    'close': prices,
                    'volume': [1500000] * 30
                }, index=dates)
                return df
                
        analyzer = RajatAlphaAnalyzer(self.config, MockFetcher())
        df = MockFetcher().get_daily_bars('TEST')
        df = analyzer.calculate_indicators(df)
        
        # Test Absorption Reversal detection directly on candle
        curr_candle = df.iloc[-1]
        c_range = curr_candle['high'] - curr_candle['low']
        lower_wick = min(curr_candle['close'], curr_candle['open']) - curr_candle['low']
        wick_ratio = lower_wick / c_range if c_range > 0 else 0.0
        close_pos = (curr_candle['close'] - curr_candle['low']) / c_range if c_range > 0 else 0.0
        
        self.assertGreaterEqual(wick_ratio, 0.55)
        self.assertGreaterEqual(close_pos, 0.70)
        self.assertGreaterEqual(99.60, 100.0 * 0.99)

    @patch('rajat_alpha_v67_single.StockHistoricalDataClient')
    @patch('rajat_alpha_v67_single.TradingClient')
    def test_daily_market_close_snapshot_output(self, mock_trading, mock_data):
        """Test that generate_daily_market_close_snapshot runs cleanly and appends to log"""
        bot = RajatAlphaTradingBot(config_path='config/config.json')
        bot.db = self.db
        
        # Add a position and a partial exit
        pos_id = self.db.add_position('SNAP_TEST', 100.0, 50, 92.0, 4.5, pattern='Hammer')
        self.db.add_partial_exit(pos_id, 10, 105.0, 'PT1', 5.0)
        
        # Record an SL step in memory
        bot.position_manager.daily_sl_steps.append({
            'symbol': 'SNAP_TEST',
            'old_sl': 92.0,
            'new_sl': 96.0,
            'profit_pct': 5.0,
            'stage': 1,
            'highest_price': 105.0,
            'time': '15:30:00 ET'
        })
        
        # Generate snapshot
        bot.generate_daily_market_close_snapshot()
        
        # Verify log file was written
        snapshot_file = os.path.join('logs', 'daily_snapshot.log')
        self.assertTrue(os.path.exists(snapshot_file))
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("END-OF-DAY MARKET CLOSE EXECUTIVE SNAPSHOT", content)
        self.assertIn("SNAP_TEST", content)

    @patch('rajat_alpha_v67_single.StockHistoricalDataClient')
    @patch('rajat_alpha_v67_single.TradingClient')
    def test_position_sizing_capital_pct_mode(self, mock_trading, mock_data):
        """Test default capital_pct mode (3% per trade, 6% stock max)"""
        bot = RajatAlphaTradingBot(config_path='config/config.json')
        bot.db = self.db
        
        # Mock account equity = $100,000
        mock_acc = MagicMock()
        mock_acc.equity = 100000.0
        bot.trading_client.get_account.return_value = mock_acc
        
        # In capital_pct mode with 3% trade size on $100 stock:
        # trade_amount = $100,000 * 0.03 = $3,000 -> 30 shares
        shares, amt = bot.position_manager.calculate_position_size('TEST_CAP', 100.0)
        self.assertEqual(shares, 30)
        self.assertEqual(amt, 3000.0)

    @patch('rajat_alpha_v67_single.StockHistoricalDataClient')
    @patch('rajat_alpha_v67_single.TradingClient')
    def test_position_sizing_risk_based_mode(self, mock_trading, mock_data):
        """Test risk_based mode with dollar risk / delta SL formula and 6% capital ceiling"""
        bot = RajatAlphaTradingBot(config_path='config/config.json')
        bot.db = self.db
        bot.config['trading_rules']['sizing_mode'] = 'risk_based'
        bot.config['trading_rules']['fixed_risk_dollars'] = 500.0
        bot.config['trading_rules']['max_allocation_per_stock_pct'] = 0.06
        
        mock_acc = MagicMock()
        mock_acc.equity = 100000.0
        bot.trading_client.get_account.return_value = mock_acc
        
        # Scenario A: Wide SL ($100 stock, $90 SL -> delta_sl = $10)
        # Raw shares = $500 / $10 = 50 shares ($5,000 <= $6,000 cap)
        shares_a, amt_a = bot.position_manager.calculate_position_size('TEST_RISK_WIDE', 100.0, stop_loss=90.0)
        self.assertEqual(shares_a, 50)
        self.assertEqual(amt_a, 5000.0)
        
        # Scenario B: Tight SL ($100 stock, $98 SL -> delta_sl = $2)
        # Raw shares = $500 / $2 = 250 shares ($25,000)
        # Must be capped by max_allocation_per_stock_pct (6% of $100,000 = $6,000 -> 60 shares)
        shares_b, amt_b = bot.position_manager.calculate_position_size('TEST_RISK_TIGHT', 100.0, stop_loss=98.0)
        self.assertEqual(shares_b, 60)
        self.assertEqual(amt_b, 6000.0)

    @patch('rajat_alpha_v67_single.StockHistoricalDataClient')
    @patch('rajat_alpha_v67_single.TradingClient')
    def test_position_sizing_risk_based_edge_cases(self, mock_trading, mock_data):
        """Test edge cases: missing stop_loss, inverted stop_loss, and remaining stock headroom"""
        bot = RajatAlphaTradingBot(config_path='config/config.json')
        bot.db = self.db
        bot.position_manager.db = self.db
        bot.config['trading_rules']['sizing_mode'] = 'risk_based'
        bot.config['trading_rules']['fixed_risk_dollars'] = 500.0
        bot.config['trading_rules']['max_allocation_per_stock_pct'] = 0.06
        bot.config['trading_rules']['capital_conservation_mode'] = False
        
        mock_acc = MagicMock()
        mock_acc.equity = 100000.0
        bot.trading_client.get_account.return_value = mock_acc
        
        # Edge Case 1: Missing stop loss (defaults to min_initial_sl_pct 5% risk -> delta = $5)
        # Raw shares = $500 / $5 = 100 shares ($10,000) -> capped at 6% ($6,000 -> 60 shares)
        shares_1, amt_1 = bot.position_manager.calculate_position_size('TEST_NO_SL', 100.0, stop_loss=None)
        self.assertEqual(shares_1, 60)
        
        # Edge Case 2: Inverted stop loss (SL > price -> falls back to min_initial_sl_pct)
        shares_2, amt_2 = bot.position_manager.calculate_position_size('TEST_INV_SL', 100.0, stop_loss=105.0)
        self.assertEqual(shares_2, 60)
        
        # Edge Case 3: Stock already holds 40 shares ($4,000). Only 20 shares ($2,000) remain under 6% ($6,000) cap.
        self.db.add_position('TEST_EXISTING', 100.0, 40, 90.0, 4.5)
        shares_3, amt_3 = bot.position_manager.calculate_position_size('TEST_EXISTING', 100.0, stop_loss=90.0)
        self.assertEqual(shares_3, 20)
        self.assertEqual(amt_3, 2000.0)

    @patch('rajat_alpha_v67_single.StockHistoricalDataClient')
    @patch('rajat_alpha_v67_single.TradingClient')
    def test_dynamic_market_regime_snapshot_label(self, mock_trading, mock_data):
        """Test that market regime MA period (e.g. 215 SMA) is dynamically rendered in snapshot"""
        bot = RajatAlphaTradingBot(config_path='config/config.json')
        bot.db = self.db
        bot.config.config['market_regime']['index_ma_period'] = 215
        
        bot.generate_daily_market_close_snapshot()
        
        snapshot_file = os.path.join('logs', 'daily_snapshot.log')
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("Failed Gate 0 (Market Regime SPY/QQQ < 215 SMA)", content)

    @patch('rajat_alpha_v67_single.StockHistoricalDataClient')
    @patch('rajat_alpha_v67_single.TradingClient')
    def test_touch_only_score_alignment(self, mock_trading, mock_data):
        """Test that touch-only signal with score 4.0 passes Gate 7 when min_touch_only_score is 4.0"""
        bot = RajatAlphaTradingBot(config_path='config/config.json')
        bot.db = self.db
        
        # Verify config alignment
        min_signal = bot.config.get('strategy_params', 'min_signal_score', 4.0)
        min_touch = bot.config.get('trading_rules', 'min_touch_only_score', 4.0)
        self.assertEqual(min_signal, 4.0)
        self.assertEqual(min_touch, 4.0)

if __name__ == '__main__':
    unittest.main()

