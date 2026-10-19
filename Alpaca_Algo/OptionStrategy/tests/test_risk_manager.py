"""
================================================================================
UNIT TESTS — Risk Manager (risk_manager.py)
================================================================================
Tests trade approval, position sizing, stop loss, portfolio exposure,
sector concentration, earnings conflicts, and trade tracking.
================================================================================
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.risk_manager import RiskManager, SECTOR_MAP


@pytest.fixture
def tmp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def risk_mgr(tmp_db):
    """Create a RiskManager with default config."""
    config = {
        'max_portfolio_risk_pct': 0.20,
        'max_risk_per_trade_pct': 0.05,
        'max_positions': 10,
        'max_same_sector': 3,
        'earnings_buffer_days': 5,
        'stop_loss_multiplier': 3.0,
        'profit_target_pct': 0.50,
    }
    return RiskManager(config, db_path=tmp_db)


# ──────────────────────────────────────────────────────────────
# Trade Approval — Position Limit
# ──────────────────────────────────────────────────────────────

class TestPositionLimit:
    def test_approve_under_limit(self, risk_mgr):
        approved, _ = risk_mgr.approve_trade(
            symbol='SPY_P', underlying='SPY', trade_type='csp',
            max_loss=2500, collateral_required=5000, account_equity=50000
        )
        assert approved

    def test_reject_at_max_positions(self, risk_mgr):
        # Fill up to max positions
        for i in range(10):
            risk_mgr.record_trade({
                'strategy': 'test', 'symbol': f'SYM{i}',
                'underlying': f'SYM{i}', 'trade_type': 'csp',
                'side': 'sell', 'quantity': 1, 'entry_price': 1.0,
                'premium_collected': 1.0, 'max_loss': 500,
                'collateral_used': 5000, 'entry_date': '2026-01-01',
            })
        approved, reason = risk_mgr.approve_trade(
            symbol='NEW', underlying='NEW', trade_type='csp',
            max_loss=500, collateral_required=5000, account_equity=50000
        )
        assert not approved
        assert 'Max positions' in reason


# ──────────────────────────────────────────────────────────────
# Trade Approval — 5% Risk Per Trade
# ──────────────────────────────────────────────────────────────

class TestRiskPerTrade:
    def test_approve_within_5pct(self, risk_mgr):
        approved, _ = risk_mgr.approve_trade(
            symbol='AAPL_P', underlying='AAPL', trade_type='csp',
            max_loss=2500, collateral_required=5000, account_equity=50000
        )
        assert approved

    def test_reject_over_5pct(self, risk_mgr):
        approved, reason = risk_mgr.approve_trade(
            symbol='AAPL_P', underlying='AAPL', trade_type='csp',
            max_loss=3000, collateral_required=5000, account_equity=50000
        )
        assert not approved
        assert '5%' in reason

    def test_edge_exactly_5pct(self, risk_mgr):
        approved, _ = risk_mgr.approve_trade(
            symbol='AAPL_P', underlying='AAPL', trade_type='csp',
            max_loss=2500, collateral_required=5000, account_equity=50000
        )
        assert approved


# ──────────────────────────────────────────────────────────────
# Trade Approval — 20% Portfolio Exposure
# ──────────────────────────────────────────────────────────────

class TestPortfolioExposure:
    def test_approve_under_20pct(self, risk_mgr):
        approved, _ = risk_mgr.approve_trade(
            symbol='SPY_P', underlying='SPY', trade_type='csp',
            max_loss=2500, collateral_required=9000, account_equity=50000
        )
        assert approved

    def test_reject_over_20pct(self, risk_mgr):
        approved, reason = risk_mgr.approve_trade(
            symbol='SPY_P', underlying='SPY', trade_type='csp',
            max_loss=2500, collateral_required=11000, account_equity=50000
        )
        assert not approved
        assert '20%' in reason

    def test_cumulative_exposure(self, risk_mgr):
        # Add existing trade using 6000 collateral
        risk_mgr.record_trade({
            'strategy': 'test', 'symbol': 'SYM1',
            'underlying': 'SPY', 'trade_type': 'csp',
            'side': 'sell', 'quantity': 1, 'entry_price': 1.0,
            'premium_collected': 1.0, 'max_loss': 500,
            'collateral_used': 6000, 'entry_date': '2026-01-01',
        })
        # Now approve 5000 more (total 11000 > 10000 limit)
        approved, reason = risk_mgr.approve_trade(
            symbol='QQQ_P', underlying='QQQ', trade_type='csp',
            max_loss=2500, collateral_required=5000, account_equity=50000
        )
        assert not approved


# ──────────────────────────────────────────────────────────────
# Trade Approval — Sector Concentration
# ──────────────────────────────────────────────────────────────

class TestSectorConcentration:
    def test_index_exempt(self, risk_mgr):
        """Index ETFs should be exempt from sector limits."""
        for i in range(5):
            risk_mgr.record_trade({
                'strategy': 'test', 'symbol': f'SPY{i}',
                'underlying': 'SPY', 'trade_type': 'csp',
                'side': 'sell', 'quantity': 1, 'entry_price': 1.0,
                'premium_collected': 1.0, 'max_loss': 500,
                'collateral_used': 1000, 'entry_date': '2026-01-01',
            })
        approved, _ = risk_mgr.approve_trade(
            symbol='SPY_new', underlying='SPY', trade_type='csp',
            max_loss=500, collateral_required=1000, account_equity=50000
        )
        assert approved

    def test_reject_same_sector(self, risk_mgr):
        """Max 3 positions in same sector."""
        tech_stocks = ['AAPL', 'MSFT', 'GOOGL']
        for stock in tech_stocks:
            risk_mgr.record_trade({
                'strategy': 'test', 'symbol': f'{stock}_P',
                'underlying': stock, 'trade_type': 'csp',
                'side': 'sell', 'quantity': 1, 'entry_price': 1.0,
                'premium_collected': 1.0, 'max_loss': 500,
                'collateral_used': 1000, 'entry_date': '2026-01-01',
            })
        approved, reason = risk_mgr.approve_trade(
            symbol='NVDA_P', underlying='NVDA', trade_type='csp',
            max_loss=500, collateral_required=1000, account_equity=50000
        )
        assert not approved
        assert 'sector' in reason.lower() or 'Sector' in reason

    def test_different_sectors_ok(self, risk_mgr):
        """Different sectors should be fine."""
        risk_mgr.record_trade({
            'strategy': 'test', 'symbol': 'AAPL_P',
            'underlying': 'AAPL', 'trade_type': 'csp',
            'side': 'sell', 'quantity': 1, 'entry_price': 1.0,
            'premium_collected': 1.0, 'max_loss': 500,
            'collateral_used': 1000, 'entry_date': '2026-01-01',
        })
        approved, _ = risk_mgr.approve_trade(
            symbol='JPM_P', underlying='JPM', trade_type='csp',
            max_loss=500, collateral_required=1000, account_equity=50000
        )
        assert approved


# ──────────────────────────────────────────────────────────────
# Earnings Conflict
# ──────────────────────────────────────────────────────────────

class TestEarningsConflict:
    def test_no_conflict(self, risk_mgr):
        approved, _ = risk_mgr.approve_trade(
            symbol='AAPL_P', underlying='AAPL', trade_type='csp',
            max_loss=500, collateral_required=5000, account_equity=50000,
            earnings_dates=['2026-06-01'], expiration_date='2026-03-20'
        )
        assert approved

    def test_conflict_within_buffer(self, risk_mgr):
        approved, reason = risk_mgr.approve_trade(
            symbol='AAPL_P', underlying='AAPL', trade_type='csp',
            max_loss=500, collateral_required=5000, account_equity=50000,
            earnings_dates=['2026-03-22'], expiration_date='2026-03-20'
        )
        assert not approved
        assert 'Earnings' in reason


# ──────────────────────────────────────────────────────────────
# Position Sizing
# ──────────────────────────────────────────────────────────────

class TestPositionSizing:
    def test_basic_sizing(self, risk_mgr):
        # 50000 × 5% = 2500 max risk, 500 per contract = 5 contracts
        contracts = risk_mgr.calculate_position_size(50000, 500)
        assert contracts == 5

    def test_zero_loss(self, risk_mgr):
        assert risk_mgr.calculate_position_size(50000, 0) == 0

    def test_negative_loss(self, risk_mgr):
        assert risk_mgr.calculate_position_size(50000, -100) == 0

    def test_large_max_loss(self, risk_mgr):
        contracts = risk_mgr.calculate_position_size(50000, 5000)
        assert contracts == 0  # 2500 / 5000 = 0.5 → 0


# ──────────────────────────────────────────────────────────────
# Stop Loss & Profit Target
# ──────────────────────────────────────────────────────────────

class TestExitPrices:
    def test_stop_loss_3x(self, risk_mgr):
        sl = risk_mgr.calculate_stop_loss(1.50)
        assert sl == 4.50  # 1.50 × 3

    def test_profit_target_50pct(self, risk_mgr):
        pt = risk_mgr.calculate_profit_target(2.00)
        assert pt == 1.00  # 2.00 × (1 - 0.50)


# ──────────────────────────────────────────────────────────────
# Trade Tracking
# ──────────────────────────────────────────────────────────────

class TestTradeTracking:
    def test_record_and_retrieve(self, risk_mgr):
        trade_id = risk_mgr.record_trade({
            'strategy': 'wheel_csp', 'symbol': 'AAPL260320P00150000',
            'underlying': 'AAPL', 'trade_type': 'csp',
            'side': 'sell', 'quantity': 1, 'entry_price': 2.50,
            'premium_collected': 2.50, 'max_loss': 750,
            'collateral_used': 15000, 'entry_date': '2026-01-15',
            'expiration_date': '2026-03-20',
        })
        assert trade_id > 0
        trades = risk_mgr.get_open_trades(strategy='wheel_csp')
        assert len(trades) == 1
        assert trades[0]['underlying'] == 'AAPL'

    def test_close_trade_and_pnl(self, risk_mgr):
        trade_id = risk_mgr.record_trade({
            'strategy': 'test', 'symbol': 'SYM1',
            'underlying': 'SPY', 'trade_type': 'csp',
            'side': 'sell', 'quantity': 1, 'entry_price': 2.0,
            'premium_collected': 2.0, 'max_loss': 500,
            'collateral_used': 5000, 'entry_date': '2026-01-01',
        })
        risk_mgr.close_trade(trade_id, exit_price=1.0, pnl=100.0, notes='50% profit')

        open_trades = risk_mgr.get_open_trades()
        assert len(open_trades) == 0

        summary = risk_mgr.get_performance_summary()
        assert summary['total_trades'] == 1
        assert summary['total_pnl'] == 100.0
        assert summary['win_rate'] == 100.0

    def test_performance_summary_mixed(self, risk_mgr):
        # Winner
        tid1 = risk_mgr.record_trade({
            'strategy': 'test', 'symbol': 'W1', 'underlying': 'SPY',
            'trade_type': 'csp', 'side': 'sell', 'quantity': 1,
            'entry_price': 2.0, 'premium_collected': 2.0,
            'max_loss': 500, 'collateral_used': 5000,
            'entry_date': '2026-01-01',
        })
        risk_mgr.close_trade(tid1, 1.0, 100.0, 'win')

        # Loser
        tid2 = risk_mgr.record_trade({
            'strategy': 'test', 'symbol': 'L1', 'underlying': 'QQQ',
            'trade_type': 'csp', 'side': 'sell', 'quantity': 1,
            'entry_price': 1.5, 'premium_collected': 1.5,
            'max_loss': 500, 'collateral_used': 5000,
            'entry_date': '2026-01-02',
        })
        risk_mgr.close_trade(tid2, 4.5, -300.0, 'loss')

        summary = risk_mgr.get_performance_summary()
        assert summary['total_trades'] == 2
        assert summary['winners'] == 1
        assert summary['losers'] == 1
        assert summary['win_rate'] == 50.0
        assert summary['total_pnl'] == -200.0
        assert summary['best_trade'] == 100.0
        assert summary['worst_trade'] == -300.0

    def test_filter_by_strategy(self, risk_mgr):
        risk_mgr.record_trade({
            'strategy': 'wheel_csp', 'symbol': 'W1', 'underlying': 'AAPL',
            'trade_type': 'csp', 'side': 'sell', 'quantity': 1,
            'entry_price': 2.0, 'premium_collected': 2.0,
            'max_loss': 500, 'collateral_used': 5000,
            'entry_date': '2026-01-01',
        })
        risk_mgr.record_trade({
            'strategy': 'spx_spread', 'symbol': 'S1', 'underlying': 'SPX',
            'trade_type': 'spread', 'side': 'sell', 'quantity': 1,
            'entry_price': 3.0, 'premium_collected': 3.0,
            'max_loss': 500, 'collateral_used': 5000,
            'entry_date': '2026-01-01',
        })
        wheel_trades = risk_mgr.get_open_trades(strategy='wheel_csp')
        assert len(wheel_trades) == 1
        assert wheel_trades[0]['strategy'] == 'wheel_csp'


# ──────────────────────────────────────────────────────────────
# Sector Map
# ──────────────────────────────────────────────────────────────

class TestSectorMap:
    def test_known_stocks(self):
        assert SECTOR_MAP['AAPL'] == 'Technology'
        assert SECTOR_MAP['JPM'] == 'Financials'
        assert SECTOR_MAP['JNJ'] == 'Healthcare'
        assert SECTOR_MAP['SPY'] == 'Index'

    def test_unknown_stock(self):
        assert SECTOR_MAP.get('ZZZZ', 'Unknown') == 'Unknown'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
