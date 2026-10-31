"""
================================================================================
TEST SUITE: INSTITUTIONAL V3.5 RESILIENCE & FIX VERIFICATION
================================================================================
Validates:
1. CPS Column Name Resilience:
   - analyze_entry_signal extracts EMA21/SMA50 regardless of case or underscores (no KeyError).
2. Exclusion List Enforcement:
   - load_exclusion_list correctly parses config/exclusionlist.txt.
   - run_buy_hunter excludes tickers from scanning and execution.
   - run_sell_guardian completely skips excluded open positions (e.g. TIGO, no SL/TES execution).
3. SOEE Partial Fill Order Desynchronization (NTAP Incident Protection):
   - Step 1 partial fill decrements remaining shares and updates DB quantity.
   - Step 2 is submitted for remaining shares only (preventing 403 insufficient qty).
   - Auto-reconciles on 403 insufficient qty rejection by querying live broker holdings.
   - Cleanly closes DB when broker reports 0 open shares.
================================================================================
"""

import time
import pytest
import sqlite3
import pandas as pd
from unittest.mock import MagicMock, patch, call
from alpaca.trading.enums import OrderStatus, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from rajat_alpha_v67_single import (
    PositionDatabase,
    PositionManager,
    RajatAlphaTradingBot,
    RajatAlphaAnalyzer,
    PatternDetector
)


@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary isolated SQLite database for testing"""
    db_file = tmp_path / "test_positions_resilience.db"
    return PositionDatabase(str(db_file))


@pytest.fixture
def mock_config():
    """Mock configuration with SOEE and trading rules parameters"""
    cfg = MagicMock()
    cfg_data = {
        'execution_schedule': {
            'enable_smart_execution': True,
            'soee_step_timeout_seconds': 15,
            'soee_allow_market_fallback': True,
            'enable_broker_reconciliation': True,
            'buy_window_start_time': '09:30',
            'buy_window_end_time': '15:59'
        },
        'trading_rules': {
            'min_signal_score': 4.0,
            'min_touch_only_score': 4.0,
            'require_bullish_confirmation_for_touch': False,
            'prevent_same_day_reentry': False,
            'max_trades_per_day': 5,
            'max_open_positions': 15,
            'max_trades_per_stock': 1,
            'watchlist_file': 'config/watchlist.txt',
            'exclusion_file': 'config/exclusionlist.txt',
            'log_excluded_symbols': True,
            'enable_swing_signals': True,
            'enable_21touch_signals': True,
            'enable_50touch_signals': True,
            'enable_composite_priority_ranking': True
        },
        'strategy_params': {
            'min_listing_days': 50,
            'sma_fast': 50,
            'sma_slow': 200,
            'ema_trend': 21,
            'pullback_days': 4,
            'pullback_pct': 5.0,
            'stalling_days_long': 8,
            'stalling_days_medium': 5,
            'stalling_days_short': 3,
            'max_adverse_move_pct': 0.05,
            'volume_surge_ratio': 1.0,
            'market_regime_sma_fast': 50,
            'enable_extended_filter': False
        },
        'pattern_config': {
            'enabled_patterns': {
                'Hammer': {'enable': True, 'score_weight': 1.0, 'tier': 'A'}
            }
        },
        'candle_quality': {
            'enable_shooting_star_filter': False,
            'max_upper_wick_ratio': 0.5,
            'max_wick_to_body_ratio': 2.0
        },
        'market_regime': {
            'enabled': False
        },
        'first_hour_guard': {
            'suppress_sl': True,
            'catastrophic_override_pct': -0.22
        },
        'risk_management': {
            'stop_loss_evaluation': 'tick',
            'max_hold_days': 21
        },
        'profit_taking': {
            'enable_partial_exits': True,
            'target_1_pct': 0.05,
            'target_1_qty': 0.20
        }
    }

    def get_cfg(section, key=None, default=None):
        if key is None or isinstance(key, dict):
            return cfg_data.get(section, default if default is not None else {})
        return cfg_data.get(section, {}).get(key, default)

    cfg.get.side_effect = get_cfg
    return cfg


# ==============================================================================
# TEST 1: CPS Column Name Resilience (Fix for KeyError: 'ema_21')
# ==============================================================================
def test_cps_column_name_resilience_uppercase_and_lowercase(mock_config):
    """
    Verifies analyze_entry_signal works with uppercase 'EMA21'/'SMA50' (as produced by
    calculate_indicators) without throwing KeyError: 'ema_21', and also handles lowercase.
    """
    mock_fetcher = MagicMock()
    analyzer = RajatAlphaAnalyzer(mock_config, mock_fetcher)
    
    # Create sample daily bars with uppercase indicators (as created by calculate_indicators)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=60, freq='D')
    df = pd.DataFrame({
        'open': [100.0 + i for i in range(60)],
        'high': [102.0 + i for i in range(60)],
        'low': [99.0 + i for i in range(60)],
        'close': [101.0 + i for i in range(60)],
        'volume': [1000000 for _ in range(60)],
        'EMA21': [100.0 + i for i in range(60)],
        'SMA50': [98.0 + i for i in range(60)],
        'SMA200': [90.0 + i for i in range(60)],
        'RSI14': [55.0 for _ in range(60)],
        'ATR14': [2.0 for _ in range(60)],
        'VOL_SMA21': [1000000 for _ in range(60)]
    }, index=dates)
    
    mock_fetcher.get_daily_bars.return_value = df
    mock_fetcher.get_current_price.return_value = 160.0
    mock_fetcher.get_ibd_rs_score.return_value = 80.0
    mock_fetcher.get_sp500_symbols.return_value = set()
    
    analyzer.check_market_regime = MagicMock(return_value=True)
    analyzer.check_market_structure = MagicMock(return_value=True)
    analyzer.check_ma_slopes = MagicMock(return_value=True)
    analyzer.check_pullback = MagicMock(return_value=True)
    analyzer.check_multitimeframe_confirmation = MagicMock(return_value=(True, True))
    analyzer.check_stalling = MagicMock(return_value=False)
    analyzer.calculate_score = MagicMock(return_value=5.0)
    
    with patch('rajat_alpha_v67_single.PatternDetector.has_pattern', return_value=(True, 'Hammer', 'A', 1.0)):
        valid, details = analyzer.analyze_entry_signal('TEST_UPPER')
        assert valid is True
        assert 'slope_21_pct' in details
        assert 'slope_50_pct' in details
        assert isinstance(details['slope_21_pct'], float)
        assert isinstance(details['slope_50_pct'], float)

    # Test with lowercase 'ema_21' and 'sma_50'
    df_lower = df.rename(columns={'EMA21': 'ema_21', 'SMA50': 'sma_50'})
    mock_fetcher.get_daily_bars.return_value = df_lower
    with patch('rajat_alpha_v67_single.PatternDetector.has_pattern', return_value=(True, 'Hammer', 'A', 1.0)):
        valid, details = analyzer.analyze_entry_signal('TEST_LOWER')
        assert valid is True
        assert 'slope_21_pct' in details
        assert 'slope_50_pct' in details


# ==============================================================================
# TEST 2: Exclusion List Parsing
# ==============================================================================
def test_load_exclusion_list(tmp_path, mock_config):
    """
    Verifies load_exclusion_list properly strips comments, whitespace,
    and capitalizes symbols into an uppercase set.
    """
    excl_file = tmp_path / "exclusionlist.txt"
    excl_file.write_text(
        "# This is a comment\n"
        "tigo\n"
        "  dxcm  \n"
        "ALL # in-line comment\n"
        "\n"
        "# another comment\n"
        "insw\n"
    )
    
    mock_config.get.side_effect = lambda sec, k=None, d=None: str(excl_file) if k == 'exclusion_file' else d
    
    bot = RajatAlphaTradingBot.__new__(RajatAlphaTradingBot)
    bot.config = mock_config
    
    exclusions = bot.load_exclusion_list()
    assert exclusions == {'TIGO', 'DXCM', 'ALL', 'INSW'}


# ==============================================================================
# TEST 3: Exclusion List Enforced in Buy Hunter
# ==============================================================================
def test_exclusion_list_enforced_in_buy_hunter(tmp_path, mock_config, temp_db):
    """
    Verifies Buy Hunter loads exclusion list and completely skips
    scanning or establishing positions in excluded symbols.
    """
    watchlist_file = tmp_path / "watchlist.txt"
    watchlist_file.write_text("AAPL\nTIGO\nMSFT\n")
    
    excl_file = tmp_path / "exclusionlist.txt"
    excl_file.write_text("TIGO\n")
    
    def get_cfg(section, key=None, default=None):
        if key == 'watchlist_file': return str(watchlist_file)
        if key == 'exclusion_file': return str(excl_file)
        if key == 'max_trades_per_day': return 5
        if key == 'max_open_positions': return 15
        if key == 'max_trades_per_stock': return 1
        return default
    
    mock_config.get.side_effect = get_cfg
    
    bot = RajatAlphaTradingBot.__new__(RajatAlphaTradingBot)
    bot.config = mock_config
    bot.db = temp_db
    bot.signal_queue = MagicMock()
    bot.signal_queue.monitoring_minutes = 30
    bot.signal_queue.get_queue_status.return_value = {'signals_queued': 0, 'minutes_elapsed': 0}
    bot.signal_queue.is_window_complete.return_value = False
    bot.is_buy_window = MagicMock(return_value=True)
    bot.is_closing_window = MagicMock(return_value=False)
    
    bot.analyzer = MagicMock()
    bot.analyzer.analyze_entry_signal.return_value = (True, {'score': 5.0, 'price': 100.0, 'pattern': 'Hammer'})
    
    bot.run_buy_hunter()
    
    # Verify AAPL and MSFT were scanned, but TIGO was completely excluded
    scanned_symbols = [c[0][0] for c in bot.analyzer.analyze_entry_signal.call_args_list]
    assert 'AAPL' in scanned_symbols
    assert 'MSFT' in scanned_symbols
    assert 'TIGO' not in scanned_symbols


# ==============================================================================
# TEST 4: Exclusion List Enforced in Sell Guardian (User's TIGO Incident)
# ==============================================================================
def test_exclusion_list_enforced_in_sell_guardian(tmp_path, mock_config, temp_db):
    """
    CRITICAL TEST FOR USER'S TIGO INCIDENT:
    Verifies that when a ticker (e.g. TIGO) is added to exclusionlist.txt,
    Sell Guardian completely skips it, even if Stop Loss or TES conditions are met!
    """
    excl_file = tmp_path / "exclusionlist.txt"
    excl_file.write_text("TIGO\n")
    
    # Add open positions for TIGO and NVDA
    tigo_id = temp_db.add_position('TIGO', entry_price=50.00, quantity=10, stop_loss=45.00, score=5.0)
    nvda_id = temp_db.add_position('NVDA', entry_price=100.00, quantity=10, stop_loss=90.00, score=5.0)
    
    def get_cfg(section, key=None, default=None):
        if key == 'exclusion_file': return str(excl_file)
        if key == 'suppress_sl': return False
        return default
        
    mock_config.get.side_effect = get_cfg
    
    bot = RajatAlphaTradingBot.__new__(RajatAlphaTradingBot)
    bot.config = mock_config
    bot.db = temp_db
    bot.is_first_hour = MagicMock(return_value=False)
    bot.is_closing_window = MagicMock(return_value=False)
    bot.last_portfolio_table_time = time.time()
    bot.portfolio_table_interval_seconds = 600
    
    mock_fetcher = MagicMock()
    mock_fetcher.get_current_price.side_effect = lambda sym: 40.00 if sym == 'TIGO' else 110.00
    bot.data_fetcher = mock_fetcher
    
    mock_pm = MagicMock()
    mock_pm.check_stop_loss.return_value = False
    mock_pm.check_partial_exit_targets.return_value = []
    mock_pm.check_time_exit.return_value = False
    bot.position_manager = mock_pm
    bot.analyzer = MagicMock()
    
    bot.run_sell_guardian()
    
    # Assert Sell Guardian NEVER called check_stop_loss on TIGO
    for call_args in mock_pm.check_stop_loss.call_args_list:
        pos = call_args[0][0]
        assert pos['symbol'] != 'TIGO'
        
    # TIGO must remain OPEN in the database untouched!
    tigo_pos = temp_db.get_position_by_id(tigo_id)
    assert tigo_pos['status'] == 'OPEN'
    assert tigo_pos['remaining_qty'] == 10


# ==============================================================================
# TEST 5: SOEE Partial Fill Order Desynchronization (NTAP Incident Reproduction)
# ==============================================================================
def test_soee_full_exit_partial_fill_synchronization_ntap_incident(temp_db, mock_config):
    """
    CRITICAL TEST FOR NTAP EXIT INCIDENT:
    Simulates:
    1. Position holds 11 shares of NTAP.
    2. Step 1 Midpoint Limit Sell is submitted for 11 shares.
    3. Step 1 times out after 15s. During timeout, 1 share was partially filled.
    4. Order is cancelled.
    5. Engine detects 1 share filled, updates DB remaining_qty to 10.
    6. Step 2 is submitted for EXACTLY 10 shares (NOT 11, which would trigger 403!).
    7. Step 2 fills 10 shares.
    8. Position is closed in DB without error.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 119.50, 'ask': 120.50, 'mid': 120.00, 'spread': 1.00
    }
    
    pos_id = temp_db.add_position('NTAP', entry_price=130.00, quantity=11, stop_loss=120.00, score=4.5)
    pos = temp_db.get_position_by_id(pos_id)
    assert pos['remaining_qty'] == 11
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    # Step 1 order: times out, but has filled_qty = 1 (partial fill!)
    ord1 = MagicMock(id='ord_step1', status=OrderStatus.PARTIALLY_FILLED, filled_qty=1, filled_avg_price=120.00)
    # Step 2 order: fills remaining 10 shares
    ord2 = MagicMock(id='ord_step2', status=OrderStatus.NEW)
    filled_ord2 = MagicMock(id='ord_step2', status=OrderStatus.FILLED, filled_qty=10, filled_avg_price=119.75)
    
    mock_trading.submit_order.side_effect = [ord1, ord2]
    mock_trading.get_order_by_id.side_effect = [ord1, filled_ord2]
    
    # Step 1 times out (is_filled=False), Step 2 succeeds (is_filled=True)
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, ord1),
        (True, filled_ord2)
    ])
    
    success = pm.execute_full_exit(pos, 120.00, "Stop Loss")
    assert success is True
    
    # Verify Step 1 was cancelled
    mock_trading.cancel_order_by_id.assert_called_with('ord_step1')
    
    # Verify Step 2 request was submitted for 10 SHARES, NOT 11!
    step2_req = mock_trading.submit_order.call_args_list[1][0][0]
    assert isinstance(step2_req, LimitOrderRequest)
    assert step2_req.qty == 10, f"Expected 10 shares for Step 2, but got {step2_req.qty}!"
    
    # Verify DB position is closed cleanly
    closed_pos = temp_db.get_position_by_id(pos_id)
    assert closed_pos['status'] == 'CLOSED'
    assert closed_pos['remaining_qty'] == 0


# ==============================================================================
# TEST 6: SOEE Insufficient Qty Auto-Reconciliation Protection
# ==============================================================================
def test_soee_insufficient_qty_auto_reconciliation(temp_db, mock_config):
    """
    Verifies that if Alpaca rejects an order submission with 403 / 'insufficient qty',
    the engine automatically queries broker open position, reconciles DB quantity,
    and resubmits for the verified available shares.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.80, 'ask': 100.20, 'mid': 100.00, 'spread': 0.40
    }
    
    pos_id = temp_db.add_position('RECON_SYM', entry_price=105.00, quantity=11, stop_loss=99.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    # Broker holds 10 shares in reality
    mock_broker_pos = MagicMock(qty='10.0')
    mock_trading.get_open_position.return_value = mock_broker_pos
    
    # First submit throws 403 insufficient qty, second submit (reconciled for 10 shares) succeeds
    successful_ord = MagicMock(id='ord_reconciled', status=OrderStatus.NEW)
    filled_ord = MagicMock(id='ord_reconciled', status=OrderStatus.FILLED, filled_qty=10, filled_avg_price=100.00)
    
    mock_trading.submit_order.side_effect = [
        Exception("403 Client Error: Forbidden for url ... insufficient qty available for order (requested: 11, available: 10)"),
        successful_ord
    ]
    pm._wait_for_order_fill = MagicMock(return_value=(True, filled_ord))
    
    success = pm.execute_full_exit(pos, 100.00, "Stop Loss")
    assert success is True
    
    # Verify DB quantity was reconciled and closed
    closed_pos = temp_db.get_position_by_id(pos_id)
    assert closed_pos['status'] == 'CLOSED'


# ==============================================================================
# TEST 7: SOEE Broker Reports 0 Shares Closes DB Immediately
# ==============================================================================
def test_soee_broker_confirms_zero_shares_closes_db(temp_db, mock_config):
    """
    Verifies that if broker position is 0 (e.g. 404 position does not exist),
    the engine immediately marks the position CLOSED in DB without submitting bad orders.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 49.80, 'ask': 50.20, 'mid': 50.00, 'spread': 0.40
    }
    
    pos_id = temp_db.add_position('GHOST_SYM', entry_price=55.00, quantity=5, stop_loss=49.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    # Broker throws 404 (position already closed on exchange)
    mock_trading.submit_order.side_effect = Exception("403 Client Error: Forbidden ... insufficient qty available")
    mock_trading.get_open_position.side_effect = Exception("404 Client Error: position does not exist")
    
    success = pm.execute_full_exit(pos, 50.00, "Stop Loss")
    assert success is True
    
    closed_pos = temp_db.get_position_by_id(pos_id)
    assert closed_pos['status'] == 'CLOSED'
    assert closed_pos['remaining_qty'] == 0
