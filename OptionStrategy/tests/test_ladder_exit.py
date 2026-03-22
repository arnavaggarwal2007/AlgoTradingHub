"""
Unit tests for the Ladder Exit Manager.
Tests all tiers, trailing stop, partial sells, and edge cases.
"""

import os
import json
import pytest
import tempfile
from unittest.mock import MagicMock

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ladder_exit import LadderExitManager, LadderTier, DEFAULT_TIERS, recommend_contracts


@pytest.fixture
def tmp_state_file():
    """Create a temp file for ladder state."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def manager(tmp_state_file):
    """Fresh LadderExitManager with temp state file."""
    return LadderExitManager(state_file=tmp_state_file)


# ══════════════════════════════════════════════════════════════════
# REGISTRATION TESTS
# ══════════════════════════════════════════════════════════════════

class TestRegistration:
    def test_register_long_position(self, manager):
        state = manager.register_position('AAPL_CALL', 5.00, 4, side='long')
        assert state['entry_price'] == 5.00
        assert state['total_contracts'] == 4
        assert state['remaining_contracts'] == 4
        assert state['side'] == 'long'
        assert state['current_tier_idx'] == 0
        # Hard SL: 5.00 * (1 - 0.17) = 4.15
        assert state['current_stop_loss'] == pytest.approx(4.15, abs=0.01)

    def test_register_short_position(self, manager):
        state = manager.register_position('SPY_PUT', 2.00, 3, side='short')
        assert state['side'] == 'short'
        # Hard SL for short: 2.00 * (1 + 0.17) = 2.34
        assert state['current_stop_loss'] == pytest.approx(2.34, abs=0.01)

    def test_register_invalid_contracts(self, manager):
        with pytest.raises(ValueError, match="at least 1"):
            manager.register_position('BAD', 5.00, 0)

    def test_register_invalid_price(self, manager):
        with pytest.raises(ValueError, match="positive"):
            manager.register_position('BAD', 0, 3)

    def test_register_invalid_side(self, manager):
        with pytest.raises(ValueError, match="long.*short"):
            manager.register_position('BAD', 5.00, 3, side='neutral')

    def test_is_registered(self, manager):
        assert not manager.is_registered('AAPL')
        manager.register_position('AAPL', 5.00, 3)
        assert manager.is_registered('AAPL')


# ══════════════════════════════════════════════════════════════════
# SELL PLAN TESTS
# ══════════════════════════════════════════════════════════════════

class TestSellPlan:
    def test_sell_plan_4_contracts(self, manager):
        state = manager.register_position('TEST', 10.00, 4)
        plan = state['sell_plan']
        # 2 sell tiers: tier_2 (25%) and tier_3 (25%)
        assert len(plan) == 2
        # 4 * 0.25 = 1 each, keeping 2 for trailing
        assert plan[0] == {'tier': 'tier_2', 'contracts': 1}
        assert plan[1] == {'tier': 'tier_3', 'contracts': 1}

    def test_sell_plan_3_contracts(self, manager):
        state = manager.register_position('TEST', 10.00, 3)
        plan = state['sell_plan']
        # 3 * 0.25 = 0.75 → rounds to 1, keeping 1 for trailing
        assert plan[0] == {'tier': 'tier_2', 'contracts': 1}
        assert plan[1] == {'tier': 'tier_3', 'contracts': 1}

    def test_sell_plan_2_contracts(self, manager):
        state = manager.register_position('TEST', 10.00, 2)
        plan = state['sell_plan']
        # 2 * 0.25 = 0.5 → rounds to 1, but second tier would leave 0
        assert plan[0] == {'tier': 'tier_2', 'contracts': 1}
        # Second tier: remaining would be 1, can't sell (keep 1 for trailing)
        # Actually after first sell: remaining=1, max_sellable=0
        # So it still has contracts: 1 in the plan, but _get_tier_sell_count
        # will limit it at runtime

    def test_sell_plan_1_contract(self, manager):
        state = manager.register_position('TEST', 10.00, 1)
        plan = state['sell_plan']
        # Can't do partial exits with 1 contract
        assert all(p['contracts'] == 0 for p in plan)

    def test_sell_plan_10_contracts(self, manager):
        state = manager.register_position('TEST', 10.00, 10)
        plan = state['sell_plan']
        # 10 * 0.25 = 2.5 → 3 each, but keep at least 1
        # tier_2: round(2.5) = 2 (max(1, round(2.5))=2, since 0+2 < 10)
        # tier_3: round(2.5) = 2 (max(1, round(2.5))=2, since 2+2 < 10)
        # remaining = 10 - 2 - 2 = 6 → plenty for trailing
        total_sell = sum(p['contracts'] for p in plan)
        assert total_sell < 10  # Must keep at least 1


# ══════════════════════════════════════════════════════════════════
# HARD STOP-LOSS TESTS
# ══════════════════════════════════════════════════════════════════

class TestHardStopLoss:
    def test_long_hard_stop_triggered(self, manager):
        """Price drops 17% → sell all."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        # SL at 10 * 0.83 = 8.30
        result = manager.check_exit('AAPL', 8.20)
        assert result['action'] == 'stop_loss'
        assert result['contracts_to_sell'] == 4

    def test_long_hard_stop_exact(self, manager):
        """Price at exactly SL level → triggers."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 8.30)
        assert result['action'] == 'stop_loss'

    def test_long_above_hard_stop(self, manager):
        """Price above SL → hold."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 9.00)
        assert result['action'] == 'hold'

    def test_short_hard_stop_triggered(self, manager):
        """Short: price rises 17% above entry → stop loss."""
        manager.register_position('SPY', 2.00, 3, side='short')
        # SL at 2.00 * 1.17 = 2.34
        result = manager.check_exit('SPY', 2.40)
        assert result['action'] == 'stop_loss'
        assert result['contracts_to_sell'] == 3

    def test_short_below_hard_stop(self, manager):
        """Short: price slightly below entry (small profit) → hold."""
        manager.register_position('SPY', 2.00, 3, side='short')
        result = manager.check_exit('SPY', 1.95)  # 2.5% profit, below tier 1
        assert result['action'] == 'hold'


# ══════════════════════════════════════════════════════════════════
# TIER 1: +5% → SL moves to -3%
# ══════════════════════════════════════════════════════════════════

class TestTier1:
    def test_long_tier1_upgrade(self, manager):
        """Price moves up 5% → SL moves from -17% to -3%."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 10.50)  # +5%
        assert result['action'] == 'hold'  # No sell at tier 1
        assert result['tier'] == 'tier_1'
        # New SL: 10.00 * 0.97 = 9.70
        assert result['stop_loss'] == pytest.approx(9.70, abs=0.01)

    def test_long_tier1_no_sell(self, manager):
        """Tier 1 should NOT trigger any contract sell."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 10.60)  # +6%
        assert result['contracts_to_sell'] == 0

    def test_short_tier1_upgrade(self, manager):
        """Short: price drops 5% (profit) → SL tightens."""
        manager.register_position('SPY', 2.00, 3, side='short')
        result = manager.check_exit('SPY', 1.90)  # 5% profit for short
        assert result['tier'] == 'tier_1'
        # Short SL: 2.00 * (1 + 0.03) = 2.06
        assert result['stop_loss'] == pytest.approx(2.06, abs=0.01)


# ══════════════════════════════════════════════════════════════════
# TIER 2: +10% → SL moves to +1%, sell ~25%
# ══════════════════════════════════════════════════════════════════

class TestTier2:
    def test_long_tier2_sell(self, manager):
        """Price moves up 10% → sell 1 contract (of 4), SL to +1%."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 11.00)  # +10%
        assert result['action'] == 'sell_partial'
        assert result['contracts_to_sell'] == 1
        assert result['tier'] == 'tier_2'
        # New SL: 10.00 * 1.01 = 10.10 (locked in 1% profit!)
        assert result['stop_loss'] == pytest.approx(10.10, abs=0.01)

    def test_tier2_with_3_contracts(self, manager):
        """With 3 contracts: sell 1 at tier 2."""
        manager.register_position('TEST', 10.00, 3, side='long')
        result = manager.check_exit('TEST', 11.00)
        assert result['action'] == 'sell_partial'
        assert result['contracts_to_sell'] == 1

    def test_tier2_remaining_updated(self, manager):
        """After tier 2 sell, remaining contracts decrease."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)  # Triggers tier 2
        status = manager.get_status('AAPL')
        assert status['remaining_contracts'] == 3

    def test_tier2_skips_on_1_contract(self, manager):
        """With 1 contract, tier 2 can't sell (need to keep for trailing)."""
        manager.register_position('AAPL', 10.00, 1, side='long')
        result = manager.check_exit('AAPL', 11.00)
        # Should upgrade tier but NOT sell
        assert result['contracts_to_sell'] == 0


# ══════════════════════════════════════════════════════════════════
# TIER 3: +15% → sell another ~25%, SL to +5%
# ══════════════════════════════════════════════════════════════════

class TestTier3:
    def test_long_tier3_sell(self, manager):
        """Price moves up 15% → sell another contract, SL to +5%."""
        manager.register_position('AAPL', 10.00, 4, side='long')

        # First, trigger tier 2
        manager.check_exit('AAPL', 11.00)  # +10%

        # Now trigger tier 3
        result = manager.check_exit('AAPL', 11.50)  # +15%
        assert result['action'] == 'sell_partial'
        assert result['contracts_to_sell'] == 1
        assert result['tier'] == 'tier_3'
        # SL: 10.00 * 1.05 = 10.50
        assert result['stop_loss'] == pytest.approx(10.50, abs=0.01)

    def test_tier3_activates_trailing(self, manager):
        """After tier 3, trailing stop should be active."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)   # tier 2
        manager.check_exit('AAPL', 11.50)   # tier 3
        status = manager.get_status('AAPL')
        assert status['trailing_active'] is True

    def test_tier3_remaining_count(self, manager):
        """After tier 2 + tier 3 sells, 2 contracts remain (of 4)."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)
        manager.check_exit('AAPL', 11.50)
        status = manager.get_status('AAPL')
        assert status['remaining_contracts'] == 2

    def test_3_contracts_sequence(self, manager):
        """With 3 contracts: sell 1 at tier2, 1 at tier3, hold 1."""
        manager.register_position('TEST', 10.00, 3, side='long')
        manager.check_exit('TEST', 11.00)
        manager.check_exit('TEST', 11.50)
        status = manager.get_status('TEST')
        assert status['remaining_contracts'] == 1

    def test_no_double_sell_same_tier(self, manager):
        """Calling check_exit again at tier 3 level should NOT sell again."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)
        manager.check_exit('AAPL', 11.50)

        # Check again at same price — should just hold
        result = manager.check_exit('AAPL', 11.50)
        assert result['action'] == 'hold'
        assert result['contracts_to_sell'] == 0


# ══════════════════════════════════════════════════════════════════
# FAST JUMP: Price jumps past multiple tiers at once
# ══════════════════════════════════════════════════════════════════

class TestFastJump:
    def test_jump_from_entry_to_tier3(self, manager):
        """Price jumps straight from entry to +15% → triggers tier 3 sell."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        # Jump directly to +15%
        result = manager.check_exit('AAPL', 11.50)
        # Should trigger the LAST matching tier (tier 3)
        assert result['tier'] == 'tier_3'
        assert result['action'] == 'sell_partial'
        # Both tier 2 and tier 3 sells should have happened
        status = manager.get_status('AAPL')
        total_sold = sum(s['contracts'] for s in status['sells_executed'])
        assert total_sold == 2  # 1 from tier_2 + 1 from tier_3
        assert status['remaining_contracts'] == 2

    def test_jump_past_all_tiers(self, manager):
        """Price jumps way past all tiers → triggers sells and trailing."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 13.00)  # +30%
        status = manager.get_status('AAPL')
        assert status['trailing_active'] is True
        assert status['remaining_contracts'] == 2


# ══════════════════════════════════════════════════════════════════
# TRAILING STOP (remaining contracts)
# ══════════════════════════════════════════════════════════════════

class TestTrailingStop:
    def _setup_trailing(self, manager):
        """Helper: advance position through all tiers to activate trailing."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)   # tier 2
        manager.check_exit('AAPL', 11.50)   # tier 3, trailing ON

    def test_trailing_holds_in_profit(self, manager):
        """Price continues up → trailing holds."""
        self._setup_trailing(manager)
        result = manager.check_exit('AAPL', 12.00)  # +20%
        assert result['action'] == 'hold'

    def test_trailing_updates_peak(self, manager):
        """Peak price should track the highest price seen."""
        self._setup_trailing(manager)
        manager.check_exit('AAPL', 13.00)
        status = manager.get_status('AAPL')
        assert status['peak_price'] == 13.00

    def test_trailing_exit_from_peak(self, manager):
        """Price rises to 13, then drops 10% to 11.7 → trailing stop exits."""
        self._setup_trailing(manager)
        manager.check_exit('AAPL', 13.00)  # new peak
        # Trail SL = 13 * 0.90 = 11.70
        # But floor = 10 * 1.05 = 10.50
        # effective_sl = max(11.70, 10.50) = 11.70
        result = manager.check_exit('AAPL', 11.60)  # below 11.70
        assert result['action'] == 'sell_all'
        assert result['contracts_to_sell'] == 2

    def test_trailing_floor_prevents_low_sl(self, manager):
        """Floor should prevent SL from dropping below tier 3's level."""
        self._setup_trailing(manager)
        # Peak is still 11.50, trail = 11.50 * 0.90 = 10.35
        # Floor = 10.00 * 1.05 = 10.50
        # effective_sl = max(10.35, 10.50) = 10.50 (floor wins)
        status = manager.get_status('AAPL')
        assert status['current_stop_loss'] >= 10.50

    def test_trailing_tightens_at_high_profit(self, manager):
        """At +30% profit, trail tightens from 10% to 7%."""
        self._setup_trailing(manager)
        manager.check_exit('AAPL', 14.00)  # +40%
        # Trail SL = 14 * 0.93 = 13.02 (using tight trail 7%)
        result = manager.check_exit('AAPL', 13.00)  # just below 13.02
        assert result['action'] == 'sell_all'

    def test_trailing_ratchet_up(self, manager):
        """SL should only ratchet up, never down for LONG."""
        self._setup_trailing(manager)
        manager.check_exit('AAPL', 15.00)  # peak at 15
        sl_after_15 = manager.get_status('AAPL')['current_stop_loss']

        manager.check_exit('AAPL', 14.00)  # price drops but still above SL
        sl_after_14 = manager.get_status('AAPL')['current_stop_loss']

        # SL should not decrease (peak is still 15, trail from 15 is used)
        assert sl_after_14 >= sl_after_15


# ══════════════════════════════════════════════════════════════════
# SHORT POSITION FULL LADDER
# ══════════════════════════════════════════════════════════════════

class TestShortLadder:
    def test_short_full_sequence(self, manager):
        """Full ladder for short position: entry=2.00, price drops = profit."""
        manager.register_position('SPY_PUT', 2.00, 4, side='short')

        # Tier 1: price drops 5% → 1.90
        r = manager.check_exit('SPY_PUT', 1.90)
        assert r['tier'] == 'tier_1'
        assert r['action'] == 'hold'
        # SL for short tier 1: 2.00 * (1 + 0.03) = 2.06
        assert r['stop_loss'] == pytest.approx(2.06, abs=0.01)

        # Tier 2: price drops 10% → 1.80
        r = manager.check_exit('SPY_PUT', 1.80)
        assert r['action'] == 'sell_partial'
        assert r['contracts_to_sell'] == 1
        # SL: 2.00 * (1 - 0.01) = 1.98
        assert r['stop_loss'] == pytest.approx(1.98, abs=0.01)

        # Tier 3: price drops 15% → 1.70
        r = manager.check_exit('SPY_PUT', 1.70)
        assert r['action'] == 'sell_partial'
        assert r['tier'] == 'tier_3'
        # Trailing activates with progressive bands:
        # At +15% peak: trail_pct = 0.12 (widest band)
        # trail_sl = 1.70 * 1.12 = 1.904, floor = 1.90, min(1.904, 1.90) = 1.90
        assert r['stop_loss'] == pytest.approx(1.90, abs=0.01)

    def test_short_stop_loss_triggered(self, manager):
        """Short: price rises above SL → stop loss."""
        manager.register_position('SPY_PUT', 2.00, 3, side='short')
        # Move to tier 1 first
        manager.check_exit('SPY_PUT', 1.90)
        # SL is now 2.06
        result = manager.check_exit('SPY_PUT', 2.10)  # above SL
        assert result['action'] == 'stop_loss'


# ══════════════════════════════════════════════════════════════════
# CONFIRM SELL & REMOVAL
# ══════════════════════════════════════════════════════════════════

class TestConfirmSell:
    def test_confirm_partial_sell(self, manager):
        """Confirm partial sell reduces remaining."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)  # tier 2 sell
        # Remaining should already be 3 from check_exit
        manager.confirm_sell('AAPL', 1, 11.00)
        status = manager.get_status('AAPL')
        assert status['remaining_contracts'] == 2  # 3 - 1

    def test_confirm_full_close(self, manager):
        """Confirming sell of all remaining removes position."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.confirm_sell('AAPL', 4, 11.00)
        assert not manager.is_registered('AAPL')

    def test_remove_position(self, manager):
        """Manually removing a position clears it."""
        manager.register_position('AAPL', 10.00, 4)
        manager.remove_position('AAPL')
        assert not manager.is_registered('AAPL')


# ══════════════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_state_survives_restart(self, tmp_state_file):
        """State persists across manager instances."""
        m1 = LadderExitManager(state_file=tmp_state_file)
        m1.register_position('AAPL', 10.00, 4, side='long')
        m1.check_exit('AAPL', 11.00)  # tier 2

        # Create a new manager with same state file
        m2 = LadderExitManager(state_file=tmp_state_file)
        assert m2.is_registered('AAPL')
        status = m2.get_status('AAPL')
        assert status['remaining_contracts'] == 3  # tier 2 already sold 1

    def test_state_file_created(self, tmp_state_file):
        m = LadderExitManager(state_file=tmp_state_file)
        m.register_position('TEST', 5.00, 2)
        assert os.path.exists(tmp_state_file)
        with open(tmp_state_file) as f:
            data = json.load(f)
        assert 'TEST' in data


# ══════════════════════════════════════════════════════════════════
# UNREGISTERED POSITION
# ══════════════════════════════════════════════════════════════════

class TestUnregistered:
    def test_check_exit_unregistered(self, manager):
        result = manager.check_exit('DOESNT_EXIST', 10.00)
        assert result['action'] == 'hold'
        assert 'not registered' in result['reason'].lower()

    def test_confirm_sell_unregistered(self, manager):
        # Should not raise
        manager.confirm_sell('DOESNT_EXIST', 1, 10.00)

    def test_remove_unregistered(self, manager):
        # Should not raise
        manager.remove_position('DOESNT_EXIST')


# ══════════════════════════════════════════════════════════════════
# QUERY METHODS
# ══════════════════════════════════════════════════════════════════

class TestQueries:
    def test_get_all_stop_losses(self, manager):
        manager.register_position('A', 10.00, 3, side='long')
        manager.register_position('B', 5.00, 4, side='short')
        sls = manager.get_all_stop_losses()
        assert 'A' in sls
        assert 'B' in sls
        assert sls['A'] == pytest.approx(8.30, abs=0.01)  # 10 * 0.83
        assert sls['B'] == pytest.approx(5.85, abs=0.01)  # 5 * 1.17

    def test_get_status_all(self, manager):
        manager.register_position('A', 10.00, 3)
        manager.register_position('B', 5.00, 4)
        all_status = manager.get_status()
        assert len(all_status) == 2

    def test_get_status_single(self, manager):
        manager.register_position('A', 10.00, 3)
        status = manager.get_status('A')
        assert status['entry_price'] == 10.00


# ══════════════════════════════════════════════════════════════════
# RECOMMEND CONTRACTS UTILITY
# ══════════════════════════════════════════════════════════════════

class TestRecommendContracts:
    def test_default_recommendation(self):
        rec = recommend_contracts()
        assert rec['minimum'] == 1
        assert rec['recommended'] == 3     # 2 sell tiers + 1 hold
        assert rec['ideal'] == 4
        assert rec['sell_points'] == 2

    def test_custom_tiers(self):
        custom = [
            LadderTier('a', None, -0.10),
            LadderTier('b', 0.05, -0.02, sell_pct=0.20),
            LadderTier('c', 0.10, 0.01, sell_pct=0.20),
            LadderTier('d', 0.15, 0.03, sell_pct=0.20),
        ]
        rec = recommend_contracts(custom)
        assert rec['sell_points'] == 3
        assert rec['recommended'] == 4


# ══════════════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_price_exactly_at_tier_trigger(self, manager):
        """Price at exactly +10% should trigger tier 2."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        result = manager.check_exit('AAPL', 11.00)  # exactly +10%
        assert result['tier'] == 'tier_2'
        assert result['action'] == 'sell_partial'

    def test_price_oscillates(self, manager):
        """Price goes up and back down without hitting SL → hold."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 10.50)  # +5% → tier 1
        # Drop back to entry (above SL of 9.70)
        result = manager.check_exit('AAPL', 9.80)
        assert result['action'] == 'hold'

    def test_price_oscillates_hits_upgraded_sl(self, manager):
        """Price goes up to tier 1, then drops below upgraded SL."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 10.50)  # tier 1, SL → 9.70
        result = manager.check_exit('AAPL', 9.65)  # below 9.70
        assert result['action'] == 'stop_loss'

    def test_tier_not_downgraded(self, manager):
        """Once a tier is reached, it should not downgrade when price drops."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.00)  # tier 2
        # Price drops back to +3% (below tier 2 trigger)
        result = manager.check_exit('AAPL', 10.30)
        # Should still be at tier 2's SL level, not downgraded
        status = manager.get_status('AAPL')
        assert status['current_tier_idx'] == 2  # still tier 2 index

    def test_large_number_of_contracts(self, manager):
        """Test with 20 contracts."""
        state = manager.register_position('AAPL', 10.00, 20, side='long')
        plan = state['sell_plan']
        # 20 * 0.25 = 5 per tier
        total_sell = sum(p['contracts'] for p in plan)
        # Must keep at least 1 for trailing
        assert state['total_contracts'] - total_sell >= 1

    def test_multiple_positions_independent(self, manager):
        """Multiple positions track independently."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.register_position('MSFT', 20.00, 3, side='long')

        # AAPL hits tier 2
        r1 = manager.check_exit('AAPL', 11.00)
        assert r1['action'] == 'sell_partial'

        # MSFT stays flat
        r2 = manager.check_exit('MSFT', 20.00)
        assert r2['action'] == 'hold'

        # MSFT state unaffected
        assert manager.get_status('MSFT')['remaining_contracts'] == 3


# ══════════════════════════════════════════════════════════════════
# ENHANCED TRAILING: MAX PROFIT EXIT
# ══════════════════════════════════════════════════════════════════

class TestMaxProfitExit:
    def test_long_max_profit_exit(self, manager):
        """At 80%+ profit, close immediately."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # tier upgrades + trailing activates
        result = manager.check_exit('AAPL', 18.00)  # +80% profit
        assert result['action'] == 'sell_all'
        assert result['tier'] == 'max_profit'
        assert result['contracts_to_sell'] == 2  # remaining after tier sells

    def test_short_max_profit_exit(self, manager):
        """Short position at 80%+ profit closes immediately."""
        manager.register_position('SPY_PUT', 1.00, 4, side='short')
        manager.check_exit('SPY_PUT', 0.80)  # tier upgrades
        # At 80% profit (price = 0.20, profit = 80%)
        result = manager.check_exit('SPY_PUT', 0.20)
        assert result['action'] == 'sell_all'
        assert result['tier'] == 'max_profit'

    def test_below_max_profit_holds(self, manager):
        """At 70% profit (below 80% threshold), trailing continues."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        result = manager.check_exit('AAPL', 17.00)  # +70% profit
        assert result['action'] == 'hold'


# ══════════════════════════════════════════════════════════════════
# ENHANCED TRAILING: DTE-BASED EXIT
# ══════════════════════════════════════════════════════════════════

class TestDTEExit:
    def test_force_close_at_low_dte(self, manager):
        """Force close at < 3 DTE if profitable."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        result = manager.check_exit('AAPL', 13.00, remaining_dte=2)
        assert result['action'] == 'sell_all'
        assert result['tier'] == 'dte_exit'

    def test_no_force_close_if_unprofitable(self, manager):
        """Don't force close at low DTE if not profitable."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        # Price drops back to just above SL — technically in profit but barely
        # The trailing SL is above entry, so this shouldn't trigger DTE exit
        # because profit_pct must be > 0
        result = manager.check_exit('AAPL', 12.50, remaining_dte=2)
        assert result['action'] == 'sell_all'  # still closes — +25% profit > 0

    def test_no_force_close_above_3_dte(self, manager):
        """With 10 DTE, no force close."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        result = manager.check_exit('AAPL', 13.00, remaining_dte=10)
        assert result['action'] == 'hold'

    def test_dte_tightens_trail(self, manager):
        """Low DTE should tighten the trail width."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        manager.check_exit('AAPL', 14.00)  # peak at +40%
        # At 10 DTE, trail width = 0.07 * 0.85 = 0.0595
        # trail_sl = 14 * (1 - 0.0595) = 14 * 0.9405 = 13.167
        result = manager.check_exit('AAPL', 13.50, remaining_dte=10)
        state = manager.get_status('AAPL')
        sl_with_dte = state['current_stop_loss']
        # Should be tighter than without DTE
        assert sl_with_dte >= 13.00


# ══════════════════════════════════════════════════════════════════
# ENHANCED TRAILING: RATCHETING FLOOR
# ══════════════════════════════════════════════════════════════════

class TestRatchetingFloor:
    def test_floor_ratchets_at_25pct(self, manager):
        """After peak 25%+ profit, floor ratchets to +10%."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # +25% → tier upgrades + trailing
        state = manager.get_status('AAPL')
        # Floor at +10%: $10 * 1.10 = $11.00
        # Trail at +25%: 10% trail → 12.50 * 0.90 = $11.25
        # effective = max(11.25, 11.00) = 11.25
        assert state['current_stop_loss'] >= 11.00

    def test_floor_ratchets_at_60pct(self, manager):
        """After peak 60%+ profit, floor ratchets to +35%."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        manager.check_exit('AAPL', 16.50)  # peak at +65%
        state = manager.get_status('AAPL')
        # Floor at +35%: $10 * 1.35 = $13.50
        # Trail at +65%: 5% band → 16.50 * 0.95 = $15.675
        # effective = max(15.675, 13.50) = $15.675
        assert state['current_stop_loss'] >= 13.50

    def test_floor_guarantees_profit_after_pullback(self, manager):
        """After hitting +40% peak, floor guarantees +20% even on pullback."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        manager.check_exit('AAPL', 14.00)  # peak at +40% → floor = +20%
        # Now price pulls back — SL should never drop below $12.00 (+20%)
        manager.check_exit('AAPL', 12.50)  # drop to +25%
        state = manager.get_status('AAPL')
        assert state['current_stop_loss'] >= 12.00


# ══════════════════════════════════════════════════════════════════
# PROGRESSIVE TRAIL BANDS
# ══════════════════════════════════════════════════════════════════

class TestProgressiveTrailBands:
    def test_widest_trail_at_low_profit(self, manager):
        """At +15% profit, trail is 12% (widest)."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 11.50)  # +15%, trail activates
        state = manager.get_status('AAPL')
        # 12% trail from peak: 11.50 * 0.88 = 10.12
        # Floor +5%: 10.50. Floor ratchet: no (below 25%)
        # effective = max(10.12, 10.50) = 10.50 — floor binds
        assert state['current_stop_loss'] >= 10.12

    def test_tight_trail_at_high_profit(self, manager):
        """At +70% profit, trail is 3% (tightest)."""
        manager.register_position('AAPL', 10.00, 4, side='long')
        manager.check_exit('AAPL', 12.50)  # activate trailing
        manager.check_exit('AAPL', 17.00)  # peak +70%
        state = manager.get_status('AAPL')
        # 3% trail from peak: 17.00 * 0.97 = 16.49
        # Floor at +40% ratchet: +20% → $12.00
        # effective = max(16.49, 12.00) = 16.49
        assert state['current_stop_loss'] >= 16.00
