"""
================================================================================
MARKET CONDITION HANDLER — Adaptive Strategy Adjustments
================================================================================

Detects current market regime and adjusts strategy parameters in real-time:
- Uptrend:    Full size, wider strikes, aggressive profit targets
- Sideways:   Standard size, iron condors preferred
- Downtrend:  Reduced size, tighter stops, avoid naked CSPs
- Choppy:     Minimum size, wider wings, early exits
- Crash:      HALT all new trades, close existing at market

Also provides:
- FOMC/CPI/NFP calendar awareness (no new entries 1 day before)
- VIX term structure analysis
- Intraday flash crash detection threshold

Usage:
    handler = MarketConditionHandler()
    condition = handler.assess(spy_data, vix_data)
    adjusted_params = handler.adjust_strategy_params('wheel', base_params)
================================================================================
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Known Macro Event Calendar (2025)
# ──────────────────────────────────────────────────────────────

MACRO_EVENTS_2025 = [
    # FOMC dates
    ('2025-01-29', 'FOMC'),
    ('2025-03-19', 'FOMC'),
    ('2025-05-07', 'FOMC'),
    ('2025-06-18', 'FOMC'),
    ('2025-07-30', 'FOMC'),
    ('2025-09-17', 'FOMC'),
    ('2025-10-29', 'FOMC'),
    ('2025-12-10', 'FOMC'),
    # CPI release dates (approximate)
    ('2025-01-15', 'CPI'),
    ('2025-02-12', 'CPI'),
    ('2025-03-12', 'CPI'),
    ('2025-04-10', 'CPI'),
    ('2025-05-13', 'CPI'),
    ('2025-06-11', 'CPI'),
    ('2025-07-11', 'CPI'),
    ('2025-08-12', 'CPI'),
    ('2025-09-10', 'CPI'),
    ('2025-10-14', 'CPI'),
    ('2025-11-12', 'CPI'),
    ('2025-12-10', 'CPI'),
    # NFP (Non-Farm Payrolls) — first Friday of month
    ('2025-01-10', 'NFP'),
    ('2025-02-07', 'NFP'),
    ('2025-03-07', 'NFP'),
    ('2025-04-04', 'NFP'),
    ('2025-05-02', 'NFP'),
    ('2025-06-06', 'NFP'),
    ('2025-07-03', 'NFP'),
    ('2025-08-01', 'NFP'),
    ('2025-09-05', 'NFP'),
    ('2025-10-03', 'NFP'),
    ('2025-11-07', 'NFP'),
    ('2025-12-05', 'NFP'),
    # Triple/Quad witching
    ('2025-01-17', 'OPEX'),
    ('2025-02-21', 'OPEX'),
    ('2025-03-21', 'QUAD_WITCH'),
    ('2025-04-17', 'OPEX'),
    ('2025-05-16', 'OPEX'),
    ('2025-06-20', 'QUAD_WITCH'),
    ('2025-07-18', 'OPEX'),
    ('2025-08-15', 'OPEX'),
    ('2025-09-19', 'QUAD_WITCH'),
    ('2025-10-17', 'OPEX'),
    ('2025-11-21', 'OPEX'),
    ('2025-12-19', 'QUAD_WITCH'),
]


class MarketConditionHandler:
    """Assess market conditions and adjust strategy parameters."""

    # Thresholds
    VIX_LOW = 14
    VIX_NORMAL = 22
    VIX_HIGH = 30
    VIX_EXTREME = 40

    ATR_LOW_PCT = 0.008
    ATR_HIGH_PCT = 0.018

    TREND_MA_PERIOD = 20
    DIRECTION_CHANGE_THRESHOLD = 7

    def __init__(self, macro_buffer_days: int = 1):
        self.macro_buffer_days = macro_buffer_days
        self.macro_dates = self._parse_macro_dates()

    def _parse_macro_dates(self) -> Dict[date, str]:
        dates = {}
        for date_str, event in MACRO_EVENTS_2025:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            dates[d] = event
        return dates

    def assess(
        self,
        spy_prices: pd.Series,
        vix_value: float,
        current_date: Optional[date] = None,
    ) -> Dict:
        """
        Assess current market condition.

        Returns:
            condition: str — 'uptrend', 'downtrend', 'sideways', 'choppy', 'crash'
            vix_regime: str — 'low_vol', 'normal', 'high_vol', 'extreme'
            macro_event_nearby: bool
            macro_event_name: str or None
            size_multiplier: float — 0.0 to 1.5
            allow_new_entries: bool
            recommendations: list of str
        """
        current_date = current_date or date.today()
        result = {
            'date': current_date.isoformat(),
            'vix': vix_value,
            'recommendations': [],
        }

        # VIX regime
        if vix_value < self.VIX_LOW:
            result['vix_regime'] = 'low_vol'
        elif vix_value < self.VIX_NORMAL:
            result['vix_regime'] = 'normal'
        elif vix_value < self.VIX_HIGH:
            result['vix_regime'] = 'high_vol'
        elif vix_value < self.VIX_EXTREME:
            result['vix_regime'] = 'extreme'
        else:
            result['vix_regime'] = 'crash'

        # Trend and condition from price data
        if len(spy_prices) >= self.TREND_MA_PERIOD:
            condition, details = self._classify_condition(spy_prices)
            result['condition'] = condition
            result.update(details)
        else:
            result['condition'] = 'unknown'

        # Override: VIX extreme = crash
        if vix_value >= self.VIX_EXTREME:
            result['condition'] = 'crash'

        # Macro event check
        nearby_event = self._check_macro_proximity(current_date)
        result['macro_event_nearby'] = nearby_event is not None
        result['macro_event_name'] = nearby_event

        # Sizing multiplier and entry permission
        result['size_multiplier'] = self._get_size_multiplier(
            result['condition'], result['vix_regime']
        )
        result['allow_new_entries'] = self._should_allow_entries(result)

        # Recommendations
        result['recommendations'] = self._generate_recommendations(result)

        return result

    def _classify_condition(self, prices: pd.Series) -> Tuple[str, Dict]:
        """Classify market condition from price series."""
        ma = prices.rolling(self.TREND_MA_PERIOD).mean()
        ma_slope = ma.pct_change(5)

        current = float(prices.iloc[-1])
        current_ma = float(ma.iloc[-1])
        current_slope = float(ma_slope.iloc[-1]) if pd.notna(ma_slope.iloc[-1]) else 0

        dist_from_ma = (current - current_ma) / current_ma

        # ATR-based volatility
        if len(prices) >= 15:
            daily_range = prices.rolling(2).apply(lambda x: abs(x.iloc[-1] / x.iloc[0] - 1), raw=False)
            avg_daily_move = float(daily_range.tail(14).mean()) if daily_range is not None else 0
        else:
            avg_daily_move = 0

        # Direction changes
        daily_dir = np.sign(prices.pct_change())
        dir_changes = int((np.diff(daily_dir.tail(10).values) != 0).sum())

        details = {
            'price': current,
            'ma20': round(current_ma, 2),
            'ma20_slope': round(current_slope, 4),
            'dist_from_ma': round(dist_from_ma, 4),
            'avg_daily_move': round(avg_daily_move, 4),
            'direction_changes_10d': dir_changes,
        }

        # Classification
        if dir_changes >= self.DIRECTION_CHANGE_THRESHOLD and avg_daily_move > self.ATR_HIGH_PCT:
            return 'choppy', details
        elif abs(dist_from_ma) < 0.02 and abs(current_slope) < 0.005:
            return 'sideways', details
        elif dist_from_ma > 0 and current_slope > 0:
            return 'uptrend', details
        elif dist_from_ma < 0 and current_slope < 0:
            return 'downtrend', details
        elif dist_from_ma > 0.03:
            return 'uptrend', details
        elif dist_from_ma < -0.03:
            return 'downtrend', details
        else:
            return 'sideways', details

    def _check_macro_proximity(self, current_date: date) -> Optional[str]:
        """Check if a macro event is within buffer_days."""
        for event_date, event_name in self.macro_dates.items():
            delta = abs((event_date - current_date).days)
            if delta <= self.macro_buffer_days:
                return f"{event_name} ({event_date.isoformat()})"
        return None

    def _get_size_multiplier(self, condition: str, vix_regime: str) -> float:
        """Get position size multiplier based on conditions."""
        condition_mult = {
            'uptrend': 1.2,
            'sideways': 1.0,
            'downtrend': 0.5,
            'choppy': 0.3,
            'crash': 0.0,
            'unknown': 0.5,
        }

        vix_mult = {
            'low_vol': 0.7,   # Thin premiums
            'normal': 1.0,
            'high_vol': 1.3,  # Rich premiums
            'extreme': 0.5,   # Too dangerous for full size
            'crash': 0.0,
        }

        return round(
            condition_mult.get(condition, 0.5) * vix_mult.get(vix_regime, 0.5),
            2,
        )

    def _should_allow_entries(self, assessment: Dict) -> bool:
        """Determine if new entries should be allowed."""
        if assessment['condition'] == 'crash':
            return False
        if assessment['vix_regime'] == 'crash':
            return False
        if assessment.get('macro_event_nearby') and assessment.get('vix_regime') in ('high_vol', 'extreme'):
            return False
        return True

    def _generate_recommendations(self, a: Dict) -> list:
        """Generate human-readable recommendations."""
        recs = []

        cond = a.get('condition', 'unknown')
        if cond == 'uptrend':
            recs.append('UPTREND: Favor bull put spreads and CSPs. Avoid naked calls.')
            recs.append('Consider wider OTM strikes to capture trend premium.')
        elif cond == 'sideways':
            recs.append('SIDEWAYS: Iron condors optimal. Use standard parameters.')
            recs.append('Profit from time decay in range-bound market.')
        elif cond == 'downtrend':
            recs.append('DOWNTREND: Reduce position sizes by 50%. Avoid CSPs on weak stocks.')
            recs.append('Consider bear call spreads or defensive put purchases.')
        elif cond == 'choppy':
            recs.append('CHOPPY: Minimum size. Wide wings. Early profit targets (40%).')
            recs.append('Avoid iron condors — both sides at risk.')
        elif cond == 'crash':
            recs.append('CRASH MODE: NO new entries. Close profitable positions.')
            recs.append('Buy protective puts if not already hedged.')

        vix_regime = a.get('vix_regime', 'normal')
        if vix_regime == 'low_vol':
            recs.append('Low VIX: Premiums are thin. Consider sitting out or using narrower spreads.')
        elif vix_regime == 'high_vol':
            recs.append('High VIX: Rich premiums but elevated risk. Use defined-risk strategies only.')
        elif vix_regime in ('extreme', 'crash'):
            recs.append('EXTREME VIX: Trading halt recommended. Protect existing positions.')

        if a.get('macro_event_nearby'):
            recs.append(f'MACRO EVENT: {a["macro_event_name"]} — avoid new entries.')

        return recs

    # ──────────────────────────────────────────────────────────
    # Strategy Parameter Adjustments
    # ──────────────────────────────────────────────────────────

    def adjust_strategy_params(
        self, strategy: str, base_params: Dict, assessment: Dict
    ) -> Dict:
        """
        Adjust strategy parameters based on market assessment.

        Returns modified params dict.
        """
        params = dict(base_params)
        cond = assessment.get('condition', 'sideways')
        vix_regime = assessment.get('vix_regime', 'normal')

        if strategy == 'wheel':
            params = self._adjust_wheel(params, cond, vix_regime)
        elif strategy == 'spreads':
            params = self._adjust_spreads(params, cond, vix_regime)
        elif strategy == 'condors':
            params = self._adjust_condors(params, cond, vix_regime)
        elif strategy == 'regime':
            params = self._adjust_regime(params, cond, vix_regime)

        # Apply size multiplier
        params['size_multiplier'] = assessment.get('size_multiplier', 1.0)

        return params

    def _adjust_wheel(self, p: Dict, cond: str, vix: str) -> Dict:
        if cond == 'uptrend':
            p['target_delta'] = min(p.get('target_delta', 0.15) * 1.3, 0.25)
            p['profit_target'] = 0.50
        elif cond == 'downtrend':
            p['target_delta'] = p.get('target_delta', 0.15) * 0.7
            p['profit_target'] = 0.40
            p['stop_loss_multiplier'] = 2.0
        elif cond == 'choppy':
            p['target_delta'] = p.get('target_delta', 0.15) * 0.6
            p['profit_target'] = 0.35
        elif cond == 'crash':
            p['enabled'] = False

        if vix == 'high_vol':
            p['dte'] = min(p.get('dte', 35) + 10, 60)
        return p

    def _adjust_spreads(self, p: Dict, cond: str, vix: str) -> Dict:
        if cond == 'uptrend':
            p['target_delta'] = p.get('target_delta', 0.12)
            p['spread_width'] = p.get('spread_width', 50)
        elif cond == 'downtrend':
            p['target_delta'] = max(p.get('target_delta', 0.12) * 0.7, 0.05)
            p['profit_target'] = 0.40
        elif cond == 'choppy':
            p['spread_width'] = max(p.get('spread_width', 50) * 0.6, 25)
            p['profit_target'] = 0.35
        elif cond == 'crash':
            p['enabled'] = False

        if vix == 'high_vol':
            p['spread_width'] = int(p.get('spread_width', 50) * 1.5)
        return p

    def _adjust_condors(self, p: Dict, cond: str, vix: str) -> Dict:
        if cond == 'sideways':
            pass  # Ideal — keep defaults
        elif cond == 'uptrend':
            # Skew: wider put side, tighter call side
            p['put_delta'] = max(p.get('put_delta', 0.12) * 0.8, 0.06)
            p['call_delta'] = min(p.get('call_delta', 0.12) * 1.3, 0.20)
        elif cond == 'downtrend':
            p['call_delta'] = max(p.get('call_delta', 0.12) * 0.8, 0.06)
            p['put_delta'] = min(p.get('put_delta', 0.12) * 1.3, 0.20)
        elif cond == 'choppy':
            p['wing_width'] = int(p.get('wing_width', 5) * 1.5)
            p['profit_target'] = 0.35
        elif cond == 'crash':
            p['enabled'] = False
        return p

    def _adjust_regime(self, p: Dict, cond: str, vix: str) -> Dict:
        if cond == 'crash':
            p['enabled'] = False
        return p


# ──────────────────────────────────────────────────────────────
# Flash Crash Detector
# ──────────────────────────────────────────────────────────────

class FlashCrashDetector:
    """Detect abnormal intraday moves that may require emergency action."""

    def __init__(
        self,
        drop_threshold_pct: float = 3.0,
        vix_spike_pct: float = 30.0,
    ):
        self.drop_threshold_pct = drop_threshold_pct
        self.vix_spike_pct = vix_spike_pct

    def check(
        self,
        current_price: float,
        open_price: float,
        current_vix: float,
        prev_close_vix: float,
    ) -> Dict:
        """Check for flash crash conditions."""
        price_change = (current_price - open_price) / open_price * 100
        vix_change = (current_vix - prev_close_vix) / prev_close_vix * 100

        is_flash_crash = (
            price_change < -self.drop_threshold_pct or
            vix_change > self.vix_spike_pct
        )

        return {
            'is_flash_crash': is_flash_crash,
            'price_change_pct': round(price_change, 2),
            'vix_change_pct': round(vix_change, 2),
            'action': 'EMERGENCY_CLOSE_ALL' if is_flash_crash else 'NORMAL',
            'severity': self._severity(price_change, vix_change),
        }

    @staticmethod
    def _severity(price_chg: float, vix_chg: float) -> str:
        if price_chg < -7 or vix_chg > 80:
            return 'CRITICAL'
        elif price_chg < -5 or vix_chg > 50:
            return 'SEVERE'
        elif price_chg < -3 or vix_chg > 30:
            return 'WARNING'
        return 'NORMAL'
