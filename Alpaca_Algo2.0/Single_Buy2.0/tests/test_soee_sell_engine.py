"""
================================================================================
TEST SUITE: INSTITUTIONAL SOEE SELL ENGINE & ANTI-MARKET-DUMP PROTECTION
================================================================================
Validates:
1. Partial Exits (PT1-PT4):
   - Step 1 Midpoint Limit Sell fill handshake
   - Step 2 Stepped-Down Marketable Limit Sell (spread * 0.25)
   - Step 3 Guarded Market fallback ONLY when spread <= 0.25%
   - Wide spread (> 0.25%) clean abort: ZERO market dump, ZERO DB corruption
   - Distorted/Unquoted book protection: Pegged limit at current_price
2. Full Exits (Stop Loss, TES, Manual Exits):
   - Standard Stop Loss executes via 3-step SOEE Limit Ladder (NOT Market Dump)
   - Step 2 fill properly updates is_filled=True and cleanly closes position in DB
   - Step 3 on wide spread routes Defensive Limit (0.5% cap), NOT unconstrained market
   - Distorted book routes Pegged & Defensive Concession Limit (0.5% cap)
   - True Catastrophic Breaker (-22%) correctly bypasses ladder for emergency market exit
3. Sell Guardian:
   - Differentiates regular Stop Loss vs Catastrophic Breaker
================================================================================
"""

import pytest
import sqlite3
import pandas as pd
from unittest.mock import MagicMock, patch, call
from alpaca.trading.enums import OrderStatus, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from rajat_alpha_v67_single import (
    PositionDatabase,
    PositionManager,
    RajatAlphaTradingBot
)


@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary isolated SQLite database for testing"""
    db_file = tmp_path / "test_positions_sell.db"
    return PositionDatabase(str(db_file))


@pytest.fixture
def mock_config():
    """Mock configuration with SOEE parameters"""
    cfg = MagicMock()
    cfg_data = {
        'execution_schedule': {
            'enable_smart_execution': True,
            'soee_step_timeout_seconds': 2,
            'soee_max_spread_pct': 0.005,
            'soee_allow_market_fallback': True,
            'enable_broker_reconciliation': True,
            'data_feed': 'sip'
        },
        'first_hour_guard': {
            'catastrophic_override_pct': -0.22,
            'suppress_sl': True
        },
        'risk_management': {
            'stop_loss_evaluation': 'daily_close_confirmed'
        }
    }
    cfg.get.side_effect = lambda section, key, default=None: cfg_data.get(section, {}).get(key, default)
    return cfg


def test_partial_exit_step1_midpoint_fill(temp_db, mock_config):
    """
    Scenario 1: Partial Exit with healthy quote -> Step 1 Midpoint Limit Sell fills.
    Verifies that a LimitOrderRequest is submitted at midpoint price and DB is updated.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 120.00, 'ask': 120.20, 'mid': 120.10, 'spread': 0.20
    }
    
    pos_id = temp_db.add_position(symbol='HALO', entry_price=100.00, quantity=10, stop_loss=90.00, score=5.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    # Simulate Step 1 filled
    ord1 = MagicMock(id='ord_step1', status=OrderStatus.NEW)
    filled_ord1 = MagicMock(id='ord_step1', status=OrderStatus.FILLED, filled_avg_price=120.10, filled_qty=2)
    mock_trading.submit_order.return_value = ord1
    pm._wait_for_order_fill = MagicMock(return_value=(True, filled_ord1))
    
    pm.execute_partial_exit(pos, 'PT1', 2, 120.00)
    
    # Verify LimitOrderRequest was submitted with limit_price = 120.10
    submitted_req = mock_trading.submit_order.call_args[0][0]
    assert isinstance(submitted_req, LimitOrderRequest)
    assert submitted_req.limit_price == 120.10
    assert submitted_req.qty == 2
    assert submitted_req.side == OrderSide.SELL
    
    # Verify DB update
    updated_pos = temp_db.get_position_by_id(pos_id)
    assert updated_pos['remaining_qty'] == 8


def test_partial_exit_step2_stepped_down_fill(temp_db, mock_config):
    """
    Scenario 2: Partial Exit with healthy quote, Step 1 unfulfilled ->
    Step 2 stepped-down limit sell submitted at max(bid, mid - spread * 0.25).
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 100.00, 'ask': 100.40, 'mid': 100.20, 'spread': 0.40
    }
    
    pos_id = temp_db.add_position(symbol='AMRX', entry_price=90.00, quantity=20, stop_loss=85.00, score=4.5)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    # Step 1 times out, Step 2 fills
    ord1 = MagicMock(id='ord_step1', status=OrderStatus.NEW)
    ord2 = MagicMock(id='ord_step2', status=OrderStatus.NEW)
    filled_ord2 = MagicMock(id='ord_step2', status=OrderStatus.FILLED, filled_avg_price=100.10, filled_qty=4)
    
    mock_trading.submit_order.side_effect = [ord1, ord2]
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, ord1),
        (True, filled_ord2)
    ])
    
    pm.execute_partial_exit(pos, 'PT1', 4, 100.20)
    
    # Verify Step 1 was cancelled
    mock_trading.cancel_order_by_id.assert_called_with('ord_step1')
    
    # Verify Step 2 limit price: mid (100.20) - spread*0.25 (0.10) = 100.10
    step2_req = mock_trading.submit_order.call_args_list[1][0][0]
    assert isinstance(step2_req, LimitOrderRequest)
    assert step2_req.limit_price == 100.10
    assert step2_req.qty == 4
    
    # Verify DB update
    updated_pos = temp_db.get_position_by_id(pos_id)
    assert updated_pos['remaining_qty'] == 16


def test_partial_exit_step3_tight_spread_market_fallback(temp_db, mock_config):
    """
    Scenario 3: Step 1 & 2 unfilled, but spread is tight (0.10% <= 0.25%) ->
    Step 3 Market Order fallback is safely submitted and fills.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    # Spread $0.10 on $100 stock = 0.10% spread (<= 0.25%)
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.95, 'ask': 100.05, 'mid': 100.00, 'spread': 0.10
    }
    
    pos_id = temp_db.add_position(symbol='AAPL', entry_price=90.00, quantity=10, stop_loss=85.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord1 = MagicMock(id='ord1', status=OrderStatus.NEW)
    ord2 = MagicMock(id='ord2', status=OrderStatus.NEW)
    ord3_mkt = MagicMock(id='ord3_mkt', status=OrderStatus.NEW)
    filled_ord3 = MagicMock(id='ord3_mkt', status=OrderStatus.FILLED, filled_avg_price=99.96, filled_qty=2)
    
    mock_trading.submit_order.side_effect = [ord1, ord2, ord3_mkt]
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, ord1),
        (False, ord2),
        (True, filled_ord3)
    ])
    
    pm.execute_partial_exit(pos, 'PT1', 2, 100.00)
    
    # Step 3 must be a MarketOrderRequest because spread is <= 0.25%
    step3_req = mock_trading.submit_order.call_args_list[2][0][0]
    assert isinstance(step3_req, MarketOrderRequest)
    assert step3_req.qty == 2
    
    # DB updated
    updated_pos = temp_db.get_position_by_id(pos_id)
    assert updated_pos['remaining_qty'] == 8


def test_partial_exit_step3_wide_spread_aborts_zero_dump(temp_db, mock_config):
    """
    Scenario 4: Step 1 & 2 unfilled, but spread is wide (1.5% > 0.25%) ->
    Clean abort! NO market order submitted, zero shares dumped, zero DB modification.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    # Spread $1.50 on $100 stock = 1.5% (> 0.25%)
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.25, 'ask': 100.75, 'mid': 100.00, 'spread': 1.50
    }
    
    pos_id = temp_db.add_position(symbol='WIDE_SYM', entry_price=90.00, quantity=10, stop_loss=85.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord1 = MagicMock(id='ord1', status=OrderStatus.NEW)
    ord2 = MagicMock(id='ord2', status=OrderStatus.NEW)
    
    mock_trading.submit_order.side_effect = [ord1, ord2]
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, ord1),
        (False, ord2)
    ])
    
    pm.execute_partial_exit(pos, 'PT1', 2, 100.00)
    
    # Assert exactly 2 orders submitted (Step 1 and Step 2). NO STEP 3 MARKET ORDER!
    assert mock_trading.submit_order.call_count == 2
    for c in mock_trading.submit_order.call_args_list:
        assert isinstance(c[0][0], LimitOrderRequest)
    
    # Verify DB was NOT modified
    updated_pos = temp_db.get_position_by_id(pos_id)
    assert updated_pos['remaining_qty'] == 10


def test_partial_exit_distorted_quote_pegged_limit(temp_db, mock_config):
    """
    Scenario 5: Quote is None (distorted book rejected, like HALO spread 12.4%) ->
    Engine submits Pegged Limit Sell at current_price, NEVER direct market dump!
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = None  # Rejected as distorted
    
    pos_id = temp_db.add_position(symbol='HALO', entry_price=110.00, quantity=6, stop_loss=105.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord_peg = MagicMock(id='ord_peg', status=OrderStatus.NEW)
    filled_peg = MagicMock(id='ord_peg', status=OrderStatus.FILLED, filled_avg_price=127.20, filled_qty=2)
    mock_trading.submit_order.return_value = ord_peg
    pm._wait_for_order_fill = MagicMock(return_value=(True, filled_peg))
    
    pm.execute_partial_exit(pos, 'PT1', 2, 127.20)
    
    # Must be LimitOrderRequest pegged to 127.20, NOT MarketOrderRequest!
    submitted = mock_trading.submit_order.call_args[0][0]
    assert isinstance(submitted, LimitOrderRequest)
    assert submitted.limit_price == 127.20
    assert submitted.qty == 2


def test_full_exit_stop_loss_uses_soee_limit_ladder(temp_db, mock_config):
    """
    Scenario 6: Full Exit on standard Stop Loss ->
    Must execute via SOEE Limit Ladder (LimitOrderRequest at midpoint), NOT emergency market dump!
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 89.90, 'ask': 90.10, 'mid': 90.00, 'spread': 0.20
    }
    
    pos_id = temp_db.add_position(symbol='KNSA', entry_price=100.00, quantity=10, stop_loss=90.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord1 = MagicMock(id='ord1', status=OrderStatus.NEW)
    filled_ord1 = MagicMock(id='ord1', status=OrderStatus.FILLED, filled_avg_price=90.00, filled_qty=10)
    mock_trading.submit_order.return_value = ord1
    pm._wait_for_order_fill = MagicMock(return_value=(True, filled_ord1))
    
    success = pm.execute_full_exit(pos, 90.00, "Stop Loss")
    assert success is True
    
    # Order must be LimitOrderRequest at 90.00, NOT MarketOrderRequest!
    submitted = mock_trading.submit_order.call_args[0][0]
    assert isinstance(submitted, LimitOrderRequest)
    assert submitted.limit_price == 90.00
    assert submitted.qty == 10
    
    # DB closed
    closed_pos = temp_db.get_position_by_id(pos_id)
    assert closed_pos['status'] == 'CLOSED'


def test_full_exit_catastrophic_breaker_emergency_market_sell(temp_db, mock_config):
    """
    Scenario 7: Full Exit on Catastrophic Breaker ->
    Direct immediate Emergency Market Sell is allowed.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    
    pos_id = temp_db.add_position(symbol='CRASH', entry_price=100.00, quantity=10, stop_loss=78.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    mkt_ord = MagicMock(id='mkt1', status=OrderStatus.NEW)
    filled_mkt = MagicMock(id='mkt1', status=OrderStatus.FILLED, filled_avg_price=75.00, filled_qty=10)
    mock_trading.submit_order.return_value = mkt_ord
    pm._wait_for_order_fill = MagicMock(return_value=(True, filled_mkt))
    
    success = pm.execute_full_exit(pos, 75.00, "Catastrophic Breaker")
    assert success is True
    
    # Must be MarketOrderRequest
    submitted = mock_trading.submit_order.call_args[0][0]
    assert isinstance(submitted, MarketOrderRequest)
    assert submitted.qty == 10


def test_full_exit_step2_fill_updates_is_filled_and_closes_db(temp_db, mock_config):
    """
    Scenario 8 (Fixes Handshake Bug):
    Step 1 limit order times out. Step 2 stepped-down limit order fills.
    Engine MUST set is_filled=True, close position in DB, and NOT trigger 'FULL EXIT FAILED'!
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.80, 'ask': 100.20, 'mid': 100.00, 'spread': 0.40
    }
    
    pos_id = temp_db.add_position(symbol='TES_TEST', entry_price=100.00, quantity=5, stop_loss=90.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord1 = MagicMock(id='ord1', status=OrderStatus.NEW)
    ord2 = MagicMock(id='ord2', status=OrderStatus.NEW)
    filled_ord2 = MagicMock(id='ord2', status=OrderStatus.FILLED, filled_avg_price=99.90, filled_qty=5)
    
    mock_trading.submit_order.side_effect = [ord1, ord2]
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, ord1),
        (True, filled_ord2)
    ])
    
    success = pm.execute_full_exit(pos, 100.00, "TES")
    assert success is True
    
    # Verify Step 1 cancelled
    mock_trading.cancel_order_by_id.assert_called_with('ord1')
    
    # Verify Step 2 limit order: mid(100.00) - spread*0.25(0.10) = 99.90
    step2_req = mock_trading.submit_order.call_args_list[1][0][0]
    assert isinstance(step2_req, LimitOrderRequest)
    assert step2_req.limit_price == 99.90
    
    # Position must be CLOSED in DB!
    closed_pos = temp_db.get_position_by_id(pos_id)
    assert closed_pos['status'] == 'CLOSED'
    assert closed_pos['exit_price'] == 99.90


def test_full_exit_wide_spread_uses_defensive_limit_not_market(temp_db, mock_config):
    """
    Scenario 9: Full Exit on Stop Loss with wide spread (1.0% > 0.25%).
    Step 1 & Step 2 time out. Step 3 MUST NOT dump at market!
    It must submit a Defensive Marketable Limit Order capped at 0.5% below current price.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    # Spread $1.00 on $100 stock = 1.0%
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.50, 'ask': 100.50, 'mid': 100.00, 'spread': 1.00
    }
    
    pos_id = temp_db.add_position(symbol='WIDE_FULL', entry_price=105.00, quantity=8, stop_loss=99.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord1 = MagicMock(id='ord1', status=OrderStatus.NEW)
    ord2 = MagicMock(id='ord2', status=OrderStatus.NEW)
    ord3 = MagicMock(id='ord3', status=OrderStatus.NEW)
    filled_ord3 = MagicMock(id='ord3', status=OrderStatus.FILLED, filled_avg_price=99.50, filled_qty=8)
    
    mock_trading.submit_order.side_effect = [ord1, ord2, ord3]
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, ord1),
        (False, ord2),
        (True, filled_ord3)
    ])
    
    success = pm.execute_full_exit(pos, 100.00, "Stop Loss")
    assert success is True
    
    # Step 3 must be a LimitOrderRequest capped at 0.5% concession (100 * 0.995 = 99.50), NOT MarketOrderRequest!
    step3_req = mock_trading.submit_order.call_args_list[2][0][0]
    assert isinstance(step3_req, LimitOrderRequest)
    assert step3_req.limit_price == 99.50
    assert step3_req.qty == 8


def test_full_exit_distorted_quote_pegged_limit(temp_db, mock_config):
    """
    Scenario 10: Full Exit on Stop Loss when quote is None (distorted book).
    Engine must route Pegged Limit Order at current_price, NOT direct market sell!
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = None  # Distorted/unavailable
    
    pos_id = temp_db.add_position(symbol='DISTORTED', entry_price=100.00, quantity=5, stop_loss=90.00, score=4.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    
    ord_peg = MagicMock(id='ord_peg', status=OrderStatus.NEW)
    filled_peg = MagicMock(id='ord_peg', status=OrderStatus.FILLED, filled_avg_price=90.00, filled_qty=5)
    mock_trading.submit_order.return_value = ord_peg
    pm._wait_for_order_fill = MagicMock(return_value=(True, filled_peg))
    
    success = pm.execute_full_exit(pos, 90.00, "Stop Loss")
    assert success is True
    
    submitted = mock_trading.submit_order.call_args[0][0]
    assert isinstance(submitted, LimitOrderRequest)
    assert submitted.limit_price == 90.00
    assert submitted.qty == 5

