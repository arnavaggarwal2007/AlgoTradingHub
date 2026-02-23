"""
services/signal_scorer.py — Entry-signal scoring that mirrors v67 logic exactly.

Single Responsibility : Only computes the numerical score and action label.
Dependency Inversion  : Accepts pre-computed data (TechnicalLevels + booleans)
                        rather than fetching anything itself.
"""
from __future__ import annotations

import logging
from typing import Tuple

import pandas as pd

from config import (
    DEMAND_ZONE_MULTIPLIER,
    MIN_SIGNAL_SCORE,
    STOP_LOSS_PCT,
    TARGET_1_PCT,
    TARGET_2_PCT,
    TARGET_3_PCT,
)
from models import MarketState, ScoreBreakdown, TechnicalLevels

logger = logging.getLogger(__name__)


class SignalScorer:
    """
    Produces (score, ScoreBreakdown, action_label) for a single stock.

    Scoring table (mirrors Single_Buy v67)
    ──────────────────────────────────────
    RSI > 50                   +1.0
    Weekly close > weekly EMA21 +1.0
    Monthly close > monthly EMA10 +1.0
    Volume > 21-day avg         +1.0
    Price in demand zone        +1.0
    EMA21 touch  1st / 2nd      +1.0 / +0.5
    SMA50 touch  1st / 2nd      +1.0 / +0.5
    Pattern on touch            +1.0
    ──────────────────────────────────────
    Max theoretical score  ≈ 9
    """

    def score(
        self,
        df:            pd.DataFrame,
        t:             TechnicalLevels,
        market_state:  MarketState,
        weekly_ok:     bool,
        monthly_ok:    bool,
        pattern:       str,
        touch_signal:  str,
        touch_count:   int,
        is_stalling:   bool,
    ) -> Tuple[float, ScoreBreakdown, str]:
        """
        Returns
        -------
        (total_score, breakdown, action_label)
        action_label : 'Buy Setup' | 'Watch' | 'Wait' | 'Avoid'
        """
        bd = ScoreBreakdown()
        parts: list[str] = []

        price = float(df["Close"].iloc[-1]) if not df.empty else 0.0

        # ── Component Scores ──────────────────────────────────────────────────

        if t.rsi > 50:
            bd.rsi_bonus = 1.0
            parts.append("RSI>50 +1")

        if weekly_ok:
            bd.weekly_bonus = 1.0
            parts.append("Weekly OK +1")

        if monthly_ok:
            bd.monthly_bonus = 1.0
            parts.append("Monthly OK +1")

        if t.volume_ratio > 1.0:
            bd.volume_bonus = 1.0
            parts.append(f"Vol {t.volume_ratio:.1f}x +1")

        if not df.empty:
            low21  = float(df["Low"].tail(21).min())
            zone_hi = low21 * DEMAND_ZONE_MULTIPLIER
            if price <= zone_hi:
                bd.demand_zone_bonus = 1.0
                parts.append("Demand Zone +1")

        # Touch bonuses (count ≥ 3 → no bonus per v67)
        if touch_signal:
            if touch_count == 1:
                bd.touch_bonus = 1.0
                parts.append(f"{touch_signal} 1st Touch +1")
            elif touch_count == 2:
                bd.touch_bonus = 0.5
                parts.append(f"{touch_signal} 2nd Touch +0.5")

            if pattern:
                bd.pattern_bonus = 1.0
                parts.append(f"Pattern({pattern}) on Touch +1")

        # ── Total ─────────────────────────────────────────────────────────────
        total = (
            bd.rsi_bonus + bd.weekly_bonus + bd.monthly_bonus
            + bd.volume_bonus + bd.demand_zone_bonus
            + bd.touch_bonus + bd.pattern_bonus
        )
        bd.total   = round(total, 1)
        bd.details = " | ".join(parts) if parts else "No scoring bonuses met"

        action = self._determine_action(
            price=price, t=t,
            market_state=market_state,
            score=total,
            touch_signal=touch_signal,
            pattern=pattern,
            is_stalling=is_stalling,
            weekly_ok=weekly_ok,
            monthly_ok=monthly_ok,
        )

        return round(total, 1), bd, action

    # ── Trade Setup Levels ────────────────────────────────────────────────────

    def compute_levels(
        self, price: float, t: TechnicalLevels
    ) -> Tuple[str, float, float, float, float, float]:
        """
        Returns (entry_zone_str, stop_loss, target1, target2, target3, risk_reward).
        """
        if price <= 0:
            return "", 0.0, 0.0, 0.0, 0.0, 0.0

        # Entry zone: nearest MA below current price
        entry_candidates = []
        if 0 < t.ema21 <= price * 1.03:
            entry_candidates.append(t.ema21)
        if 0 < t.sma50 <= price * 1.05:
            entry_candidates.append(t.sma50)

        entry_ref = min(entry_candidates) if entry_candidates else price
        entry_zone = f"${entry_ref:.2f}–${price:.2f}"

        stop  = round(price * (1 - STOP_LOSS_PCT), 2)
        t1    = round(price * (1 + TARGET_1_PCT),  2)
        t2    = round(price * (1 + TARGET_2_PCT),  2)
        t3    = round(price * (1 + TARGET_3_PCT),  2)
        risk  = price - stop
        rrr   = round((t1 - price) / risk, 2) if risk > 0 else 0.0

        return entry_zone, stop, t1, t2, t3, rrr

    # ── Action Logic ──────────────────────────────────────────────────────────

    def _determine_action(
        self,
        price:        float,
        t:            TechnicalLevels,
        market_state: MarketState,
        score:        float,
        touch_signal: str,
        pattern:      str,
        is_stalling:  bool,
        weekly_ok:    bool,
        monthly_ok:   bool,
    ) -> str:
        # v67 CHECK 1: Market structure must be bullish
        market_ok = (t.sma50 > t.sma200) and (t.ema21 > t.sma50)
        if not market_ok:
            return "Avoid"

        # Price well below all MAs → avoid
        if price < t.sma200 * 0.90:
            return "Avoid"

        # Stalling → not actionable yet
        if is_stalling:
            return "Watch"

        has_signal = bool(touch_signal) or bool(pattern)

        if score >= MIN_SIGNAL_SCORE and has_signal:
            return "Buy Setup"

        if score >= MIN_SIGNAL_SCORE - 1:
            return "Watch"

        if score >= 2:
            return "Wait"

        return "Avoid"
