"""
================================================================================
TEST SUITE: API RESILIENCY, TRANSIENT ERROR RECOVERY, & ISOLATION
================================================================================
Validates:
1. Exponential backoff and retry (@with_api_retry) on transient API/network errors.
2. Graceful degradation when Alpaca returns empty/None bars or quotes.
3. Current price fallback: Latest Bar -> Midpoint Quote -> Cached Last Valid Price.
4. Sell Guardian per-symbol exception isolation (no single ticker halts portfolio monitoring).
5. Buy Hunter per-symbol exception isolation (no single watchlist ticker halts scanning).
6. Order fill polling (_wait_for_order_fill) network exception resilience.
7. Database auto-migration idempotency on existing production databases.
8. Complete elimination of KeyError on missing indicators in OHLCV bars.
================================================================================
"""

import time
import pytest
import sqlite3
import pandas as pd
from unittest.mock import MagicMock, patch, call
from alpaca.trading.enums import OrderStatus, OrderSide, TimeInForce

from rajat_alpha_v67_single import (
    with_api_retry,
    MarketDataFetcher,
    PositionDatabase,
    PositionManager,
    RajatAlphaTradingBot
)


def test_with_api_retry_recovers_after_transient_failure():
    """Verifies that transient network failures succeed when API recovers on retry"""
    attempts = 0
    
    @with_api_retry(max_retries=3, base_delay=0.01)
    def flaky_api_call():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionResetError("Remote host closed connection")
        return {"status": "ok"}
        
    res = flaky_api_call()
    assert res == {"status": "ok"}
    assert attempts == 2


def test_with_api_retry_returns_none_on_permanent_failure():
    """Verifies that permanent failures return None after retries without unhandled crash"""
    attempts = 0
    
    @with_api_retry(max_retries=3, base_delay=0.01)
    def doomed_api_call():
        nonlocal attempts
        attempts += 1
        raise TimeoutError("Alpaca API timeout (504 Gateway Timeout)")
        
    res = doomed_api_call()
    assert res is None
    assert attempts == 3


def test_get_current_price_fallback_ladder():
    """
    Verifies the 3-tier fallback ladder for get_current_price:
    1. Direct bar query fails ->
    2. Fallback to live midpoint quote ->
    3. Fallback to cached last_valid_price if quote also fails.
    """
    mock_client = MagicMock()
    fetcher = MarketDataFetcher(mock_client, feed='sip')
    
    # Pre-seed cache with last known good price
    fetcher.last_valid_price['FALLBACK_STOCK'] = 150.00
    
    # 1. Bar query raises exception
    mock_client.get_stock_latest_bar.side_effect = Exception("Bar API unavailable")
    
    # 2. Quote returns valid midpoint $152.50
    mock_quote = MagicMock(bid_price=152.00, ask_price=153.00)
    mock_client.get_stock_latest_quote.return_value = {'FALLBACK_STOCK': mock_quote}
    
    px = fetcher.get_current_price('FALLBACK_STOCK')
    assert px == 152.50
    assert fetcher.last_valid_price['FALLBACK_STOCK'] == 152.50
    
    # 3. Now simulate both bar AND quote completely failing
    mock_client.get_stock_latest_quote.side_effect = Exception("Quote API unavailable")
    px_cached = fetcher.get_current_price('FALLBACK_STOCK')
    assert px_cached == 152.50  # Retrieved from cache!


def test_sell_guardian_symbol_exception_isolation(tmp_path):
    """
    CRITICAL TEST FOR OCT 26 INCIDENT:
    Verifies that if an unexpected exception occurs on symbol 1 (e.g. ECPG),
    Sell Guardian logs the error, DOES NOT crash, and successfully processes symbol 2 (e.g. AMRX).
    """
    db_file = tmp_path / "test_guardian_iso.db"
    db = PositionDatabase(str(db_file))
    
    # Add two open positions
    pos1_id = db.add_position('ECPG', 97.55, 3, 90.00, 4.0)
    pos2_id = db.add_position('AMRX', 19.42, 100, 18.00, 4.0)
    
    bot = MagicMock()
    bot.db = db
    bot.last_portfolio_table_time = 0
    bot.portfolio_table_interval_seconds = 600
    bot.is_closing_window.return_value = False
    bot.is_first_hour.return_value = False
    bot.is_market_opening_down.return_value = False
    
    # Mock data fetcher: ECPG raises KeyError; AMRX succeeds
    def mock_get_current_price(sym):
        if sym == 'ECPG':
            raise KeyError("EMA21")
        return 21.05
    bot.data_fetcher.get_current_price.side_effect = mock_get_current_price
    
    # Mock position manager
    bot.position_manager = MagicMock()
    bot.position_manager.check_stop_loss.return_value = False
    bot.position_manager.check_partial_exit_targets.return_value = []
    bot.position_manager.check_time_exit.return_value = False
    bot.config = MagicMock()
    bot.config.get.return_value = True
    
    # Execute run_sell_guardian
    RajatAlphaTradingBot.run_sell_guardian(bot)
    
    # VERIFY: AMRX was still processed and its trailing stop was updated despite ECPG failure!
    amrx_pos = db.get_position_by_id(pos2_id)
    bot.position_manager.update_trailing_stop_loss.assert_called_with(amrx_pos, current_price=21.05)


def test_buy_hunter_symbol_exception_isolation(tmp_path):
    """
    Verifies that if one symbol in watchlist.txt throws an exception during analysis,
    Buy Hunter logs and continues to scan and stage the rest of the watchlist.
    """
    db_file = tmp_path / "test_hunter_iso.db"
    db = PositionDatabase(str(db_file))
    
    bot = MagicMock()
    bot.db = db
    bot.signal_queue = MagicMock()
    bot.signal_queue.signals = {}
    bot.signal_queue.monitoring_minutes = 30
    bot.signal_queue.get_queue_status.return_value = {'signals_queued': 0, 'minutes_elapsed': 0.0}
    bot.signal_queue.is_window_complete.return_value = False  # Stay in collection phase
    bot.config = MagicMock()
    bot.config.get.side_effect = lambda sec, k, d=None: {
        ('trading_rules', 'watchlist_file'): str(tmp_path / "watchlist.txt"),
        ('trading_rules', 'max_open_positions'): 15,
        ('trading_rules', 'max_trades_per_day'): 3,
        ('trading_rules', 'max_trades_per_stock'): 1
    }.get((sec, k), d)
    
    # Create watchlist with 2 symbols: CRASH_SYM and GOOD_SYM
    wl_file = tmp_path / "watchlist.txt"
    wl_file.write_text("CRASH_SYM\nGOOD_SYM\n")
    
    # Mock analyzer: CRASH_SYM raises exception; GOOD_SYM returns valid buy signal
    def mock_analyze(sym):
        if sym == 'CRASH_SYM':
            raise RuntimeError("Corrupted historical data stream from provider")
        return True, {'symbol': 'GOOD_SYM', 'score': 5.0, 'rs_score': 80.0, 'pattern': 'Engulfing', 'price': 50.00}
    
    bot.analyzer = MagicMock()
    bot.analyzer.analyze_entry_signal.side_effect = mock_analyze
    bot.is_buy_window.return_value = True  # Inside buy window
    bot.is_closing_window.return_value = False
    
    # Execute run_buy_hunter
    RajatAlphaTradingBot.run_buy_hunter(bot)
    
    # VERIFY: GOOD_SYM was successfully staged despite CRASH_SYM throwing RuntimeError!
    bot.signal_queue.add_signal.assert_called_with('GOOD_SYM', {'symbol': 'GOOD_SYM', 'score': 5.0, 'rs_score': 80.0, 'pattern': 'Engulfing', 'price': 50.00})


def test_order_fill_polling_network_error_resilience():
    """
    Verifies that _wait_for_order_fill gracefully handles network exceptions
    when polling order status from Alpaca without crashing.
    """
    mock_trading = MagicMock()
    # Fails 2 times with network error, then returns filled order
    filled_order = MagicMock(status=OrderStatus.FILLED, filled_qty=10, filled_avg_price=100.00)
    mock_trading.get_order_by_id.side_effect = [
        ConnectionError("TLS handshake error"),
        TimeoutError("Connection timed out"),
        filled_order
    ]
    
    cfg = MagicMock()
    db = MagicMock()
    fetcher = MagicMock()
    pm = PositionManager(mock_trading, cfg, db, fetcher)
    
    is_filled, ord_status = pm._wait_for_order_fill('test_ord_id', 'AAPL', timeout_seconds=5, poll_interval=0.01)
    assert is_filled is True
    assert ord_status == filled_order


def test_database_safe_auto_migration_idempotent(tmp_path):
    """
    Verifies that PositionDatabase can be initialized repeatedly on an existing
    database without altering or corrupting existing positions or throwing errors.
    """
    db_file = tmp_path / "positions.db"
    
    # 1. Initialize first time and insert position
    db1 = PositionDatabase(str(db_file))
    pos_id = db1.add_position('TEST', 100.00, 10, 90.00, 4.0)
    
    # 2. Re-initialize multiple times (simulating bot restarts)
    db2 = PositionDatabase(str(db_file))
    db3 = PositionDatabase(str(db_file))
    
    pos = db3.get_position_by_id(pos_id)
    assert pos is not None
    assert pos['symbol'] == 'TEST'
    assert pos['remaining_qty'] == 10
    assert pos['status'] == 'OPEN'


def test_check_time_exit_resilient_to_missing_indicators():
    """
    Verifies that check_time_exit dynamically calculates EMA21 if missing
    and does NOT raise KeyError 'EMA21'.
    """
    cfg = MagicMock()
    cfg_data = {
        'risk_management': {
            'max_hold_days': 21,
            'tes_extension_days': 10,
            'max_tes_extensions': 2,
            'enable_dynamic_tes_extension': True
        }
    }
    cfg.get.side_effect = lambda sec, k, d=None: cfg_data.get(sec, {}).get(k, d)
    
    # Effective limit: 21 + 2 * 10 = 41 days. Setting days_held = 45 triggers exit.
    db = MagicMock()
    db.get_days_held.return_value = 45
    pm = PositionManager(MagicMock(), cfg, db, MagicMock())
    
    position = {
        'id': 1,
        'symbol': 'ECPG',
        'entry_price': 97.55,
        'is_runner': 0,
        'tes_extensions_count': 2  # Max extensions reached
    }
    
    # Create raw OHLCV dataframe WITHOUT 'EMA21' column
    df_raw = pd.DataFrame({
        'open': [95.0] * 30,
        'high': [100.0] * 30,
        'low': [90.0] * 30,
        'close': [92.0] * 30,  # Below entry price
        'volume': [1000000] * 30
    })
    
    # Must NOT raise KeyError: 'EMA21'
    should_exit = pm.check_time_exit(position, df_raw)
    assert should_exit is True
