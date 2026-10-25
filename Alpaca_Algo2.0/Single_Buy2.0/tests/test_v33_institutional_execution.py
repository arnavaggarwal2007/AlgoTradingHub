"""
================================================================================
TEST SUITE: V3.3 INSTITUTIONAL UPGRADES & BROKER SYNCHRONIZATION
================================================================================
Covers:
1. SOEE 3-Step Escalation Ladder & Strict Broker Fill Confirmation Handshake
2. Zero-DB Entry on Unfilled/Canceled/Timed-Out Orders (Eliminates INSW Bug)
3. Quote Sanitization against Distorted / Fragmented Books (e.g. IEX Illiquidity)
4. Broker State Reconciliation (Eliminates Phantom Positions / Naked Short Selling)
5. Multi-Tier Composite Priority Score (CPS) Deterministic Candidate Ranking
6. Auto-Closing Positions when Remaining Quantity Reaches Zero
"""

import os
import sqlite3
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from alpaca.trading.enums import OrderStatus, OrderSide, TimeInForce

# Import bot components
from rajat_alpha_v67_single import (
    PositionDatabase,
    ConfigManager,
    PositionManager,
    SignalQueue,
    RajatAlphaTradingBot,
    MarketDataFetcher
)


@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary isolated SQLite database for testing"""
    db_file = tmp_path / "test_positions.db"
    db = PositionDatabase(str(db_file))
    return db


@pytest.fixture
def mock_config():
    """Mock configuration with V3.3 execution and priority parameters"""
    cfg = MagicMock()
    cfg_data = {
        'execution_schedule': {
            'enable_smart_execution': True,
            'soee_step_timeout_seconds': 2,
            'soee_max_spread_pct': 0.005,
            'soee_allow_market_fallback': True,
            'enable_broker_reconciliation': True,
            'data_feed': 'sip',
            'signal_monitoring_minutes': 30,
            'top_n_trades': 5
        },
        'trading_rules': {
            'enable_composite_priority_ranking': True,
            'sizing_mode': 'capital_pct',
            'per_trade_pct': 0.03,
            'max_allocation_per_stock_pct': 0.06
        },
        'risk_management': {
            'stop_loss_mode': 'hybrid_atr',
            'max_initial_sl_pct': 0.17,
            'min_initial_sl_pct': 0.05
        }
    }
    cfg.get.side_effect = lambda section, key, default=None: cfg_data.get(section, {}).get(key, default)
    return cfg


def test_soee_three_step_escalator_and_fill_confirmation(temp_db, mock_config):
    """
    Verifies that execute_buy runs through the SOEE ladder and only persists to DB
    when Alpaca confirms the fill with actual fill price and quantity.
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    
    # Stock price is $100.00, quote is Bid $99.90 / Ask $100.10 (Mid $100.00, Spread $0.20)
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.90, 'ask': 100.10, 'mid': 100.00, 'spread': 0.20
    }
    mock_fetcher.get_daily_bars.return_value = pd.DataFrame({
        'close': [98.0, 99.0, 100.0],
        'high': [99.0, 100.0, 101.0],
        'low': [97.0, 98.0, 99.0],
        'volume': [1000000, 1100000, 1200000]
    })
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    pm.calculate_position_size = MagicMock(return_value=(10, 1000.0))
    pm.calculate_stop_loss = MagicMock(return_value=95.00)
    
    # Simulate Step 1 unfilled, then Step 2 FILLED by broker
    order1 = MagicMock(id='ord_step1', status=OrderStatus.NEW)
    order2 = MagicMock(id='ord_step2', status=OrderStatus.NEW)
    filled_order2 = MagicMock(
        id='ord_step2',
        status=OrderStatus.FILLED,
        filled_avg_price=100.05,
        filled_qty=10
    )
    
    mock_trading.submit_order.side_effect = [order1, order2]
    # _wait_for_order_fill: Step 1 times out (False), Step 2 fills (True)
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, order1),
        (True, filled_order2)
    ])
    
    signal_details = {
        'price': 100.00,
        'score': 5.0,
        'pattern': 'Engulfing',
        'rs_score': 75.0
    }
    
    success = pm.execute_buy('AAPL', signal_details)
    assert success is True
    
    # Verify Step 1 order was cancelled
    mock_trading.cancel_order_by_id.assert_called_with('ord_step1')
    
    # Verify DB entry was written with actual broker fill price ($100.05) and filled quantity (10)
    open_pos = temp_db.get_open_positions('AAPL')
    assert len(open_pos) == 1
    assert open_pos[0]['entry_price'] == 100.05
    assert open_pos[0]['quantity'] == 10
    assert open_pos[0]['remaining_qty'] == 10
    assert open_pos[0]['status'] == 'OPEN'


def test_soee_clean_abort_unfilled_zero_db_entry(temp_db, mock_config):
    """
    CRITICAL TEST FOR INSW BUG:
    Verifies that if all SOEE steps time out or are canceled by Alpaca,
    the bot CLEANLY ABORTS and writes ZERO entries to positions.db!
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    
    # Spread is wide ($1.00 on $100 stock = 1.0%), so market order fallback is disabled
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 99.50, 'ask': 100.50, 'mid': 100.00, 'spread': 1.00
    }
    mock_fetcher.get_daily_bars.return_value = pd.DataFrame({
        'close': [100.0], 'high': [101.0], 'low': [99.0], 'volume': [500000]
    })
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    pm.calculate_position_size = MagicMock(return_value=(5, 500.0))
    pm.calculate_stop_loss = MagicMock(return_value=92.00)
    
    # Both Step 1 and Step 2 time out unfilled
    order1 = MagicMock(id='ord1', status=OrderStatus.NEW)
    order2 = MagicMock(id='ord2', status=OrderStatus.NEW)
    mock_trading.submit_order.side_effect = [order1, order2]
    pm._wait_for_order_fill = MagicMock(side_effect=[
        (False, order1),
        (False, order2)
    ])
    
    signal_details = {
        'price': 100.00,
        'score': 4.0,
        'pattern': '21Touch',
        'rs_score': 62.5
    }
    
    success = pm.execute_buy('INSW', signal_details)
    assert success is False
    
    # VERIFY: Absolutely zero rows exist in positions.db!
    open_pos = temp_db.get_open_positions('INSW')
    assert len(open_pos) == 0
    all_rows = temp_db.conn.cursor().execute("SELECT count(*) FROM positions").fetchone()[0]
    assert all_rows == 0


def test_distorted_quote_rejection_and_sanitization():
    """
    Verifies that get_latest_quote rejects distorted quotes from fragmented/illiquid feeds
    where midpoint deviates > 2.0% from the current market price or spread is absurd.
    """
    mock_client = MagicMock()
    fetcher = MarketDataFetcher(mock_client, feed='sip')
    
    # Distorted IEX quote: Bid $95.50, Ask $115.00 -> Mid $105.25 when market price is $111.65 (5.7% dev!)
    distorted_quote = MagicMock(bid_price=95.50, ask_price=115.00)
    mock_client.get_stock_latest_quote.return_value = {'INSW': distorted_quote}
    
    # When market price is $111.65, quote should be rejected as None
    clean_quote = fetcher.get_latest_quote('INSW', current_price=111.65)
    assert clean_quote is None
    
    # Tight healthy quote: Bid $111.50, Ask $111.70 -> Mid $111.60 (0.04% dev)
    healthy_quote = MagicMock(bid_price=111.50, ask_price=111.70)
    mock_client.get_stock_latest_quote.return_value = {'INSW': healthy_quote}
    
    valid_quote = fetcher.get_latest_quote('INSW', current_price=111.65)
    assert valid_quote is not None
    assert valid_quote['mid'] == 111.60
    assert valid_quote['spread'] == 0.20


def test_broker_state_reconciliation_phantom_elimination(temp_db, mock_config):
    """
    Verifies that reconcile_positions_with_broker detects when DB has an 'OPEN' position
    that does not exist on Alpaca broker (e.g. INSW phantom position),
    and marks it 'CANCELLED_UNFILLED' to prevent naked shorting.
    """
    # 1. Insert a phantom position into DB (1 share of INSW OPEN)
    pos_id = temp_db.add_position(
        symbol='INSW',
        entry_price=111.65,
        quantity=1,
        stop_loss=100.76,
        score=4.0,
        pattern='swing+21Touch'
    )
    
    # Also insert a legitimate position (5 shares of AAPL)
    aapl_id = temp_db.add_position(
        symbol='AAPL',
        entry_price=150.00,
        quantity=5,
        stop_loss=140.00,
        score=5.0,
        pattern='Engulfing'
    )
    
    # 2. Setup mock bot with Alpaca holding ONLY AAPL (0 shares of INSW!)
    bot = MagicMock()
    bot.db = temp_db
    bot.config = mock_config
    bot.trading_client = MagicMock()
    
    alpaca_aapl = MagicMock(symbol='AAPL', qty='5.0')
    bot.trading_client.get_all_positions.return_value = [alpaca_aapl]
    
    # Bind the reconciliation function to bot instance
    discrepancies = RajatAlphaTradingBot.reconcile_positions_with_broker(bot)
    assert discrepancies == 1
    
    # 3. Verify INSW was safely neutralized
    insw_record = temp_db.get_position_by_id(pos_id)
    assert insw_record['status'] == 'CANCELLED_UNFILLED'
    assert 'No Broker Position' in insw_record['exit_reason']
    
    # 4. Verify AAPL remained OPEN and unaffected
    aapl_record = temp_db.get_position_by_id(aapl_id)
    assert aapl_record['status'] == 'OPEN'
    assert aapl_record['remaining_qty'] == 5


def test_composite_priority_score_deterministic_tie_breaker():
    """
    Verifies that SignalQueue deterministically ranks equal-score (4.0/7.0) candidates
    using the Institutional Composite Priority Score (CPS), prioritizing:
    - High-win-rate Candlestick Reversal (Bullish Engulfing wt: 1.0 vs Touch wt: 0.4)
    - Institutional Relative Volume (RVol 2.5x vs 0.7x)
    - Positive Moving Average Slopes (+2.5% vs -0.8%)
    - IBD RS Composite (85 vs 35)
    """
    sq = SignalQueue(monitoring_minutes=30, top_n=5)
    
    # Setup Candidate A: Strong Institutional Momentum Setup
    cand_a = {
        'score': 4.0,
        'candle_weight': 1.00,  # Bullish Engulfing
        'candle_pattern': 'Bullish Engulfing',
        'rvol': 2.4,            # Heavy volume surge
        'slope_21_pct': 2.8,    # Accelerating 21 EMA
        'slope_50_pct': 1.2,    # Upward 50 SMA
        'dist_to_ema21_pct': 0.8,
        'rs_score': 85.0,
        'dollar_volume': 50000000.0
    }
    
    # Setup Candidate B: Weak Laggard Touch Setup
    cand_b = {
        'score': 4.0,
        'candle_weight': 0.40,  # Generic Touch
        'candle_pattern': 'Touch-Only',
        'rvol': 0.6,            # Dry volume
        'slope_21_pct': -0.2,   # Flat/soft EMA
        'slope_50_pct': -0.9,   # Downward sloping 50 SMA
        'dist_to_ema21_pct': 2.5,
        'rs_score': 35.0,
        'dollar_volume': 15000000.0
    }
    
    cps_a = SignalQueue.calculate_composite_priority_score(cand_a)
    cps_b = SignalQueue.calculate_composite_priority_score(cand_b)
    
    # Candidate A must overwhelmingly outperform Candidate B
    assert cps_a > cps_b
    assert cps_a >= 0.65
    assert cps_b <= 0.30
    
    # Test deterministic ranking in get_top_signals
    sq.signals = {'WEAK_TICKER': cand_b, 'STRONG_TICKER': cand_a}
    mock_analyzer = MagicMock()
    mock_analyzer.analyze_entry_signal.side_effect = [
        (True, cand_b),
        (True, cand_a)
    ]
    
    ranked = sq.get_top_signals(mock_analyzer)
    assert len(ranked) == 2
    # STRONG_TICKER must be #1 regardless of insertion order!
    assert ranked[0][0] == 'STRONG_TICKER'
    assert ranked[1][0] == 'WEAK_TICKER'


def test_partial_exit_auto_close_zero_remaining(temp_db):
    """
    Verifies that when partial exits reduce remaining_qty to 0,
    PositionDatabase automatically marks status='CLOSED', eliminating
    legacy zero-share zombie records.
    """
    pos_id = temp_db.add_position(
        symbol='TEST',
        entry_price=50.00,
        quantity=10,
        stop_loss=45.00,
        score=5.0,
        pattern='Engulfing'
    )
    
    # Exit 1: 5 shares
    temp_db.add_partial_exit(pos_id, quantity=5, exit_price=55.00, profit_target='PT1', profit_pct=10.0)
    pos = temp_db.get_position_by_id(pos_id)
    assert pos['status'] == 'OPEN'
    assert pos['remaining_qty'] == 5
    
    # Exit 2: remaining 5 shares
    temp_db.add_partial_exit(pos_id, quantity=5, exit_price=60.00, profit_target='PT2', profit_pct=20.0)
    pos = temp_db.get_position_by_id(pos_id)
    
    # MUST BE CLOSED
    assert pos['status'] == 'CLOSED'
    assert pos['remaining_qty'] == 0
    assert pos['exit_reason'] == 'Partial Exits Complete'
    
    # Must NOT show up in get_open_positions
    open_positions = temp_db.get_open_positions()
    assert not any(p['id'] == pos_id for p in open_positions)


def test_sell_side_fill_handshake_aborts_on_unfilled_order(temp_db, mock_config):
    """
    Verifies that if a sell order (partial or full exit) fails to fill on Alpaca broker,
    PositionManager cleanly aborts and leaves the DB position OPEN and intact!
    """
    mock_trading = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.get_latest_quote.return_value = {
        'bid': 109.90, 'ask': 110.10, 'mid': 110.00, 'spread': 0.20
    }
    
    pm = PositionManager(mock_trading, mock_config, temp_db, mock_fetcher)
    pos_id = temp_db.add_position(
        symbol='TEST_SELL',
        entry_price=100.00,
        quantity=10,
        stop_loss=90.00,
        score=4.0
    )
    pos = temp_db.get_position_by_id(pos_id)
    
    # 1. Partial exit unfilled test
    unfilled_order = MagicMock(id='sell_unfilled', status=OrderStatus.NEW)
    mock_trading.submit_order.return_value = unfilled_order
    pm._wait_for_order_fill = MagicMock(return_value=(False, None))
    
    pm.execute_partial_exit(pos, 'PT1', 2, 105.00)
    
    # Verify DB was NOT modified
    pos_after = temp_db.get_position_by_id(pos_id)
    assert pos_after['remaining_qty'] == 10
    assert pos_after['status'] == 'OPEN'
    cursor = temp_db.conn.cursor()
    assert cursor.execute("SELECT count(*) FROM partial_exits WHERE position_id = ?", (pos_id,)).fetchone()[0] == 0
    
    # 2. Full exit unfilled test
    full_success = pm.execute_full_exit(pos, 85.00, "Stop Loss")
    assert full_success is False
    pos_after_full = temp_db.get_position_by_id(pos_id)
    assert pos_after_full['status'] == 'OPEN'  # Position remains OPEN for Sell Guardian retry!


def test_deterministic_score_precedence_and_cps_tie_breaker():
    """
    Verifies that:
    1. Primary sorting uses Conviction Score (e.g. 5.0 > 4.0).
    2. Among equal scores (4.0 vs 4.0), CPS deterministically breaks the tie!
    """
    sq = SignalQueue(monitoring_minutes=30, top_n=5)
    
    # Candidate 1: Score 5.0, Moderate CPS
    cand_5_0 = {
        'score': 5.0,
        'cps': 0.60,
        'rs_score': 70.0,
        'dollar_volume': 20000000.0
    }
    
    # Candidate 2: Score 4.0, High CPS
    cand_4_0_high_cps = {
        'score': 4.0,
        'cps': 0.88,
        'rs_score': 85.0,
        'dollar_volume': 50000000.0
    }
    
    # Candidate 3: Score 4.0, Low CPS
    cand_4_0_low_cps = {
        'score': 4.0,
        'cps': 0.35,
        'rs_score': 50.0,
        'dollar_volume': 15000000.0
    }
    
    sq.signals = {
        'CAND_4_LOW': cand_4_0_low_cps,
        'CAND_5_HIGH_SCORE': cand_5_0,
        'CAND_4_HIGH_CPS': cand_4_0_high_cps
    }
    
    mock_analyzer = MagicMock()
    mock_analyzer.analyze_entry_signal.side_effect = [
        (True, cand_4_0_low_cps),
        (True, cand_5_0),
        (True, cand_4_0_high_cps)
    ]
    
    ranked = sq.get_top_signals(mock_analyzer)
    assert len(ranked) == 3
    # Candidate 1 (Score 5.0) MUST come first due to primary score precedence
    assert ranked[0][0] == 'CAND_5_HIGH_SCORE'
    # Candidate 2 (Score 4.0, CPS 0.88) MUST beat Candidate 3 (Score 4.0, CPS 0.35)
    assert ranked[1][0] == 'CAND_4_HIGH_CPS'
    assert ranked[2][0] == 'CAND_4_LOW'
