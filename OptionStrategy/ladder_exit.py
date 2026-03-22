"""
================================================================================
LADDER EXIT MANAGER — Tiered Profit-Taking & Trailing Stop System
================================================================================
Implements a stepped exit strategy for options positions:

  Entry → Hard Stop-Loss at -17%
  +5%   → SL moves to -3% of entry (breakeven protection)
  +10%  → SL moves to +1% of entry, sell ~25% contracts (lock in profit)
  +15%  → Sell another ~25%, SL moves to +5% of entry
  Rest  → Trailing stop (10% below peak, tightens at +30%) for max profit

Works for BOTH long and short option positions via P&L percentage.
Handles whole-contract constraints (options can't be split fractionally).

Minimum Contracts:
  1 contract  → trailing stop only (no partial exits possible)
  3 contracts → ~33% per tier (1/1/1)
  4 contracts → exactly 25% per tier (1/1/2) ← ideal
================================================================================
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional


class LadderTier:
    """Definition of a single ladder tier."""

    __slots__ = ('name', 'trigger_pct', 'stop_loss_pct', 'sell_pct')

    def __init__(self, name: str, trigger_pct: Optional[float],
                 stop_loss_pct: float, sell_pct: float = 0.0):
        self.name = name
        self.trigger_pct = trigger_pct     # P&L % to trigger this tier (None = always active)
        self.stop_loss_pct = stop_loss_pct  # SL relative to entry (negative = below, positive = above)
        self.sell_pct = sell_pct            # Fraction of TOTAL position to sell at this tier


# Default tiers matching user specification
DEFAULT_TIERS = [
    LadderTier('hard_stop',  trigger_pct=None,  stop_loss_pct=-0.17, sell_pct=0.0),
    LadderTier('tier_1',     trigger_pct=0.05,  stop_loss_pct=-0.03, sell_pct=0.0),
    LadderTier('tier_2',     trigger_pct=0.10,  stop_loss_pct=0.01,  sell_pct=0.25),
    LadderTier('tier_3',     trigger_pct=0.15,  stop_loss_pct=0.05,  sell_pct=0.25),
]

DEFAULT_TRAIL_CONFIG = {
    # Progressive trail bands: (profit_threshold, trail_width)
    # Tighter at higher profits — captures more of big winning trades
    'trail_bands': [
        (0.15, 0.12),  # +15%: 12% trail (wide — let theta decay work)
        (0.20, 0.10),  # +20%: 10% trail (standard)
        (0.30, 0.07),  # +30%: 7% trail (protect meaningful gains)
        (0.50, 0.05),  # +50%: 5% trail (lock it in)
        (0.70, 0.03),  # +70%: 3% trail (near max — very tight)
    ],
    'floor_pct': 0.05,  # Base floor: +5% above entry (tier 3 level)
    # Ratcheting floor: as peak profit grows, floor ratchets up
    'floor_ratchets': [
        (0.25, 0.10),  # After +25% peak: floor → +10%
        (0.40, 0.20),  # After +40% peak: floor → +20%
        (0.60, 0.35),  # After +60% peak: floor → +35%
    ],
    # Close immediately at 80%+ of max profit captured
    # Remaining 20% has ~1:4 risk/reward — not worth holding
    'max_profit_close_pct': 0.80,
    # DTE-based trail tightening: (dte_threshold, multiplier)
    # As expiration nears, option gamma rises and theta accelerates
    'dte_trail_multipliers': [
        (21, 1.0),   # >21 DTE: normal width
        (14, 0.85),  # 14-21 DTE: 15% tighter
        (7, 0.70),   # 7-14 DTE: 30% tighter
        (3, 0.50),   # 3-7 DTE: 50% tighter
    ],
    # Force close if profitable with < 3 DTE (gamma risk > theta benefit)
    'force_close_dte': 3,
}


class LadderExitManager:
    """
    Manages tiered exits for options positions with whole-contract constraints.

    Supports both LONG and SHORT positions:
      LONG  — profit when option price rises above entry
      SHORT — profit when option price falls below entry credit

    All tier triggers are based on P&L percentage, so the same tiers
    work identically for both position types.
    """

    def __init__(self, state_file: str = None, tiers: list = None,
                 trail_config: dict = None, logger: logging.Logger = None):
        self.tiers = tiers or list(DEFAULT_TIERS)
        self.trail = trail_config or dict(DEFAULT_TRAIL_CONFIG)
        self.logger = logger or logging.getLogger('LadderExit')

        # Active positions: position_key → state dict
        self._positions = {}

        # Persistence
        self.state_file = state_file or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'ladder_state.json'
        )
        self._load_state()

    # ──────────────────────────────────────────────────────────────
    # POSITION REGISTRATION
    # ──────────────────────────────────────────────────────────────

    def register_position(self, position_key: str, entry_price: float,
                          total_contracts: int, side: str = 'long') -> dict:
        """
        Register a new position for ladder management.

        Args:
            position_key: Unique identifier (e.g., option symbol or trade ID)
            entry_price: Price paid (long) or credit received (short)
            total_contracts: Number of contracts
            side: 'long' or 'short'

        Returns:
            Initial state dict
        """
        if total_contracts < 1:
            raise ValueError("Need at least 1 contract")
        if entry_price <= 0:
            raise ValueError("Entry price must be positive")
        if side not in ('long', 'short'):
            raise ValueError("Side must be 'long' or 'short'")

        sell_plan = self._build_sell_plan(total_contracts)
        initial_sl = self._calc_sl_price(entry_price, self.tiers[0].stop_loss_pct, side)

        state = {
            'position_key': position_key,
            'entry_price': entry_price,
            'total_contracts': total_contracts,
            'remaining_contracts': total_contracts,
            'side': side,
            'current_tier_idx': 0,
            'peak_price': entry_price,
            'current_stop_loss': initial_sl,
            'sell_plan': sell_plan,
            'sells_executed': [],
            'registered_at': datetime.now().isoformat(),
            'trailing_active': False,
        }

        self._positions[position_key] = state
        self._save_state()

        self.logger.info(
            f"LADDER REGISTERED: {position_key} | "
            f"Entry: ${entry_price:.2f} | Contracts: {total_contracts} | "
            f"Side: {side} | Hard SL: ${initial_sl:.2f} | "
            f"Sell plan: {sell_plan}"
        )
        return state

    def _build_sell_plan(self, total_contracts: int) -> list:
        """
        Calculate how many whole contracts to sell at each sell-tier.

        With 4 contracts: [1, 1] → sell 1 at tier_2, 1 at tier_3, hold 2
        With 3 contracts: [1, 1] → sell 1 at tier_2, 1 at tier_3, hold 1
        With 1 contract:  [0, 0] → can't do partial, trailing stop only
        """
        sell_tiers = [t for t in self.tiers if t.sell_pct > 0]

        if total_contracts <= 1:
            return [{'tier': t.name, 'contracts': 0} for t in sell_tiers]

        plan = []
        cumulative_sold = 0

        for tier in sell_tiers:
            ideal = tier.sell_pct * total_contracts
            actual = max(1, round(ideal))

            # Never sell everything — keep at least 1 for trailing
            if cumulative_sold + actual >= total_contracts:
                actual = max(0, total_contracts - cumulative_sold - 1)

            cumulative_sold += actual
            plan.append({'tier': tier.name, 'contracts': actual})

        return plan

    # ──────────────────────────────────────────────────────────────
    # CORE: CHECK EXIT CONDITIONS
    # ──────────────────────────────────────────────────────────────

    def check_exit(self, position_key: str, current_price: float,
                   remaining_dte: int = None) -> dict:
        """
        Evaluate ladder exit conditions for a position.

        Call this on every price update / monitoring loop iteration.

        Args:
            position_key: The registered position identifier
            current_price: Current market price of the option
            remaining_dte: Days to expiration (enables DTE-based features)

        Returns:
            dict with:
              action: 'hold' | 'sell_partial' | 'sell_all' | 'stop_loss'
              contracts_to_sell: int
              stop_loss: float (current SL level)
              reason: str
              tier: str (current tier name)
              profit_pct: float
        """
        if position_key not in self._positions:
            return {'action': 'hold', 'reason': 'Position not registered',
                    'contracts_to_sell': 0, 'stop_loss': 0, 'tier': 'unknown',
                    'profit_pct': 0}

        state = self._positions[position_key]
        entry = state['entry_price']
        side = state['side']

        # Calculate P&L percentage
        profit_pct = self._calc_profit_pct(entry, current_price, side)

        # Update peak price (for trailing stop)
        self._update_peak(state, current_price)

        # 1. CHECK STOP-LOSS (highest priority — always checked first)
        if self._is_stop_hit(state, current_price):
            remaining = state['remaining_contracts']
            tier_name = self.tiers[state['current_tier_idx']].name
            action = 'stop_loss'
            if state['trailing_active']:
                tier_name = 'trailing'
                action = 'sell_all'
            result = {
                'action': action,
                'contracts_to_sell': remaining,
                'stop_loss': state['current_stop_loss'],
                'reason': (
                    f"Stop loss hit at ${current_price:.2f} "
                    f"(SL: ${state['current_stop_loss']:.2f}, P&L: {profit_pct:+.1%})"
                ),
                'tier': tier_name,
                'profit_pct': profit_pct,
            }
            self.logger.warning(f"LADDER STOP: {position_key} | {result['reason']}")
            return result

        # 2. CHECK TIER UPGRADES
        result = self._evaluate_tiers(state, current_price, profit_pct)

        # 3. CHECK TRAILING STOP (for remaining contracts after all tiers)
        if state['trailing_active']:
            trail_result = self._evaluate_trailing(state, current_price, profit_pct, remaining_dte)
            if trail_result:
                return trail_result
            # Even if trailing didn't trigger exit, update SL in result
            result['stop_loss'] = state['current_stop_loss']

        self._save_state()
        return result

    # ──────────────────────────────────────────────────────────────
    # TIER EVALUATION
    # ──────────────────────────────────────────────────────────────

    def _evaluate_tiers(self, state: dict, current_price: float,
                        profit_pct: float) -> dict:
        """Walk through tiers above current and check for upgrades."""
        current_idx = state['current_tier_idx']
        tier = self.tiers[current_idx]

        default_result = {
            'action': 'hold',
            'contracts_to_sell': 0,
            'stop_loss': state['current_stop_loss'],
            'reason': f"Holding at {tier.name} | P&L: {profit_pct:+.1%}",
            'tier': tier.name,
            'profit_pct': profit_pct,
        }

        result = default_result

        for i in range(current_idx + 1, len(self.tiers)):
            tier = self.tiers[i]
            if tier.trigger_pct is None:
                continue

            if profit_pct >= tier.trigger_pct - 1e-9:
                # Upgrade to this tier
                new_sl = self._calc_sl_price(
                    state['entry_price'], tier.stop_loss_pct, state['side']
                )
                state['current_tier_idx'] = i
                state['current_stop_loss'] = new_sl

                self.logger.info(
                    f"LADDER UPGRADE: {state['position_key']} → {tier.name} | "
                    f"P&L: {profit_pct:+.1%} | New SL: ${new_sl:.2f}"
                )

                # Check if this tier requires selling
                contracts_to_sell = self._get_tier_sell_count(state, tier.name)

                if contracts_to_sell > 0:
                    state['remaining_contracts'] -= contracts_to_sell
                    state['sells_executed'].append({
                        'tier': tier.name,
                        'contracts': contracts_to_sell,
                        'price': current_price,
                        'profit_pct': profit_pct,
                        'timestamp': datetime.now().isoformat(),
                    })

                    result = {
                        'action': 'sell_partial',
                        'contracts_to_sell': contracts_to_sell,
                        'stop_loss': new_sl,
                        'reason': (
                            f"{tier.name}: Sell {contracts_to_sell} contract(s) "
                            f"at ${current_price:.2f} ({profit_pct:+.1%} gain)"
                        ),
                        'tier': tier.name,
                        'profit_pct': profit_pct,
                    }

                    self.logger.info(
                        f"LADDER SELL: {state['position_key']} | "
                        f"{contracts_to_sell} contracts @ ${current_price:.2f} | "
                        f"Remaining: {state['remaining_contracts']}"
                    )
                else:
                    result = {
                        'action': 'hold',
                        'contracts_to_sell': 0,
                        'stop_loss': new_sl,
                        'reason': f"{tier.name}: SL upgraded to ${new_sl:.2f}",
                        'tier': tier.name,
                        'profit_pct': profit_pct,
                    }

                # Activate trailing stop after the last defined tier
                if i == len(self.tiers) - 1:
                    state['trailing_active'] = True
                    self.logger.info(
                        f"TRAILING ACTIVATED: {state['position_key']} | "
                        f"Floor: ${new_sl:.2f}"
                    )
            else:
                break  # Tiers are ordered; stop checking higher ones

        return result

    def _get_tier_sell_count(self, state: dict, tier_name: str) -> int:
        """How many contracts to sell at a specific tier (0 if already sold)."""
        already_sold = any(s['tier'] == tier_name for s in state['sells_executed'])
        if already_sold:
            return 0

        for item in state['sell_plan']:
            if item['tier'] == tier_name:
                # Never sell more than remaining minus 1 (keep at least 1 for trailing)
                max_sellable = max(0, state['remaining_contracts'] - 1)
                return min(item['contracts'], max_sellable)
        return 0

    # ──────────────────────────────────────────────────────────────
    # TRAILING STOP — Professional Multi-Factor Exit
    # ──────────────────────────────────────────────────────────────

    def _evaluate_trailing(self, state: dict, current_price: float,
                           profit_pct: float, remaining_dte: int = None) -> Optional[dict]:
        """
        Enhanced trailing stop for the remaining position.

        Professional multi-factor exit using:
          1. Progressive trail bands (tighter at higher profits)
          2. Ratcheting floor (never gives back too much)
          3. Max profit exit at 80%+ (risk/reward deteriorates)
          4. DTE-aware tightening (capture theta acceleration)
          5. Gamma protection (force close at <3 DTE)
        """
        entry = state['entry_price']
        side = state['side']
        peak = state['peak_price']
        remaining = state['remaining_contracts']

        # ── 1. MAX PROFIT EXIT ─────────────────────────────────
        # At 80%+ of max profit, remaining 20% has ~1:4 risk/reward.
        # Professional desks close here — don't risk reversal for pennies.
        max_profit_pct = self.trail.get('max_profit_close_pct', 0.80)
        if profit_pct >= max_profit_pct - 1e-9:
            result = {
                'action': 'sell_all',
                'contracts_to_sell': remaining,
                'stop_loss': state['current_stop_loss'],
                'reason': (
                    f"Max profit exit at {profit_pct:+.1%} "
                    f"(>={max_profit_pct:.0%} threshold)"
                ),
                'tier': 'max_profit',
                'profit_pct': profit_pct,
            }
            self.logger.info(
                f"LADDER MAX PROFIT: {state['position_key']} | "
                f"Closing {remaining} contracts at {profit_pct:+.1%}"
            )
            return result

        # ── 2. GAMMA PROTECTION — Force close near expiry ──────
        # < 3 DTE: gamma risk outweighs remaining theta benefit.
        force_close_dte = self.trail.get('force_close_dte', 3)
        if remaining_dte is not None and remaining_dte <= force_close_dte and profit_pct > 0:
            result = {
                'action': 'sell_all',
                'contracts_to_sell': remaining,
                'stop_loss': state['current_stop_loss'],
                'reason': (
                    f"DTE exit: {remaining_dte} DTE remaining, "
                    f"P&L: {profit_pct:+.1%} — gamma risk"
                ),
                'tier': 'dte_exit',
                'profit_pct': profit_pct,
            }
            self.logger.info(
                f"LADDER DTE EXIT: {state['position_key']} | "
                f"{remaining_dte} DTE | Closing {remaining} contracts"
            )
            return result

        # ── 3. PROGRESSIVE TRAIL WIDTH ─────────────────────────
        # Use PEAK profit level — don't widen trail on pullback
        peak_profit_pct = self._calc_profit_pct(entry, peak, side)
        trail_bands = self.trail.get('trail_bands', [(0.15, 0.10)])
        trail_pct = trail_bands[0][1]  # default to widest band
        for threshold, width in trail_bands:
            if peak_profit_pct >= threshold - 1e-9:
                trail_pct = width

        # ── 4. DTE-BASED TIGHTENING ────────────────────────────
        # As expiry approaches, tighten trail to capture theta acceleration
        if remaining_dte is not None:
            dte_multipliers = self.trail.get('dte_trail_multipliers', [])
            for dte_threshold, multiplier in dte_multipliers:
                if remaining_dte > dte_threshold:
                    trail_pct *= multiplier
                    break

        # ── 5. TRAILING SL FROM PEAK ───────────────────────────
        if side == 'long':
            trail_sl = round(peak * (1 - trail_pct), 4)
        else:
            trail_sl = round(peak * (1 + trail_pct), 4)

        # ── 6. RATCHETING FLOOR ────────────────────────────────
        # Floor increases with peak profit — never gives back too much
        floor_pct = self.trail.get('floor_pct', 0.05)
        floor_ratchets = self.trail.get('floor_ratchets', [])
        for threshold, new_floor in floor_ratchets:
            if peak_profit_pct >= threshold - 1e-9:
                floor_pct = new_floor

        if side == 'long':
            floor_sl = round(entry * (1 + floor_pct), 4)
            effective_sl = max(trail_sl, floor_sl)
        else:
            floor_sl = round(entry * (1 - floor_pct), 4)
            effective_sl = min(trail_sl, floor_sl)

        # ── 7. RATCHET: only update SL if more favourable ─────
        if side == 'long' and effective_sl > state['current_stop_loss']:
            state['current_stop_loss'] = effective_sl
        elif side == 'short' and effective_sl < state['current_stop_loss']:
            state['current_stop_loss'] = effective_sl

        # ── 8. CHECK IF TRAILING STOP HIT ──────────────────────
        if self._is_stop_hit(state, current_price):
            result = {
                'action': 'sell_all',
                'contracts_to_sell': remaining,
                'stop_loss': state['current_stop_loss'],
                'reason': (
                    f"Trailing stop hit at ${current_price:.2f} "
                    f"(Peak: ${peak:.2f}, Trail SL: ${effective_sl:.2f}, "
                    f"P&L: {profit_pct:+.1%})"
                ),
                'tier': 'trailing',
                'profit_pct': profit_pct,
            }
            self.logger.info(
                f"LADDER TRAIL EXIT: {state['position_key']} | "
                f"{remaining} contract(s) | {result['reason']}"
            )
            return result

        return None

    # ──────────────────────────────────────────────────────────────
    # EXECUTION CALLBACKS
    # ──────────────────────────────────────────────────────────────

    def confirm_sell(self, position_key: str, contracts_sold: int,
                     sell_price: float):
        """
        Record that a partial or full exit was executed.
        Call this AFTER the broker order fills successfully.
        """
        if position_key not in self._positions:
            return

        state = self._positions[position_key]

        if contracts_sold >= state['remaining_contracts']:
            # Position fully closed
            self.logger.info(
                f"LADDER COMPLETE: {position_key} | "
                f"All contracts closed at ${sell_price:.2f}"
            )
            del self._positions[position_key]
        else:
            state['remaining_contracts'] -= contracts_sold

        self._save_state()

    def remove_position(self, position_key: str):
        """Remove a position from ladder tracking (e.g., expired worthless)."""
        if position_key in self._positions:
            del self._positions[position_key]
            self._save_state()

    # ──────────────────────────────────────────────────────────────
    # QUERIES
    # ──────────────────────────────────────────────────────────────

    def get_status(self, position_key: str = None) -> dict:
        """Get current ladder state for one or all positions."""
        if position_key:
            return dict(self._positions.get(position_key, {}))
        return {k: dict(v) for k, v in self._positions.items()}

    def get_all_stop_losses(self) -> dict:
        """Return {position_key: stop_loss_price} for all managed positions."""
        return {k: v['current_stop_loss'] for k, v in self._positions.items()}

    def is_registered(self, position_key: str) -> bool:
        return position_key in self._positions

    # ──────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _calc_profit_pct(entry: float, current: float, side: str) -> float:
        """Calculate P&L percentage based on position side."""
        if entry <= 0:
            return 0.0
        if side == 'long':
            return (current - entry) / entry
        else:  # short
            return (entry - current) / entry

    @staticmethod
    def _calc_sl_price(entry: float, sl_pct: float, side: str) -> float:
        """
        Convert a SL percentage to an absolute price.

        For LONG:  sl_pct=-0.17 → entry * 0.83 (price below entry = loss)
        For SHORT: sl_pct=-0.17 → entry * 1.17 (price above entry = loss)
        """
        if side == 'long':
            return round(entry * (1 + sl_pct), 4)
        else:
            return round(entry * (1 - sl_pct), 4)

    def _is_stop_hit(self, state: dict, current_price: float) -> bool:
        """Check if the current stop loss level has been breached."""
        sl = state['current_stop_loss']
        if state['side'] == 'long':
            return current_price <= sl
        else:
            return current_price >= sl

    def _update_peak(self, state: dict, current_price: float):
        """Track the best price seen (highest for long, lowest for short)."""
        if state['side'] == 'long':
            if current_price > state['peak_price']:
                state['peak_price'] = current_price
        else:
            if current_price < state['peak_price']:
                state['peak_price'] = current_price

    # ──────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────────────────────

    def _save_state(self):
        """Persist ladder state to disk."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self._positions, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save ladder state: {e}")

    def _load_state(self):
        """Load ladder state from disk on restart."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self._positions = json.load(f)
                self.logger.info(
                    f"Loaded {len(self._positions)} ladder position(s) from state"
                )
            except Exception as e:
                self.logger.error(f"Failed to load ladder state: {e}")
                self._positions = {}


# ──────────────────────────────────────────────────────────────────
# UTILITY: Contract Recommendations
# ──────────────────────────────────────────────────────────────────

def recommend_contracts(tiers: list = None) -> dict:
    """
    Calculate minimum contracts needed for proper ladder execution.

    Returns recommendation dict with minimum, recommended, and ideal counts.
    """
    tiers = tiers or DEFAULT_TIERS
    sell_points = sum(1 for t in tiers if t.sell_pct > 0)

    # Need 1 per sell point + 1 for trailing
    recommended = sell_points + 1

    return {
        'minimum': 1,
        'recommended': recommended,
        'ideal': max(4, recommended + 1),
        'sell_points': sell_points,
        'explanation': (
            f"With {recommended} contracts: ~{100 // recommended}% per tier. "
            f"With 4 contracts: exactly 25% per tier. "
            f"With 1 contract: trailing stop only (no partial exits)."
        ),
    }
