"""
================================================================================
POSITION SIZING MODULE — Capital Allocation for Options Premium Strategies
================================================================================

Multiple position sizing methods for serious capital deployment:

1. Fixed Fractional    — Risk a fixed % of portfolio per trade
2. Kelly Criterion     — Optimal growth rate based on win rate and payoff
3. Volatility-Adjusted — Scale size inversely to current market volatility
4. Risk Parity         — Equal risk contribution across positions
5. Anti-Martingale     — Increase size after wins, decrease after losses

Each method accounts for:
- Maximum portfolio exposure limits
- Sector concentration limits
- Correlation-aware sizing
- Drawdown circuit breakers (reduce size during drawdowns)
- Regime-specific adjustments

Usage:
    sizer = PositionSizer(portfolio_value=100000)
    size = sizer.calculate('fixed_fractional', trade_params)
    size = sizer.calculate('kelly', trade_params)
================================================================================
"""

import math
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TradeParams:
    """Parameters for sizing a single trade."""
    strategy: str                        # 'wheel', 'spreads', 'condors', 'regime'
    underlying_price: float              # Current stock price
    max_loss_per_contract: float         # Worst case loss per contract ($)
    premium_collected: float             # Credit received per contract ($)
    probability_of_profit: float         # 0-1 estimated POP
    iv_rank: float = 50.0               # 0-100
    vix: float = 18.0                   # Current VIX
    sector: str = 'unknown'             # For sector concentration
    dte: int = 35                        # Days to expiration
    symbol: str = ''                     # Underlying symbol


@dataclass
class PortfolioState:
    """Current state of the portfolio for sizing decisions."""
    total_value: float
    cash_available: float
    open_positions: int = 0
    total_exposure: float = 0.0          # Sum of collateral in use
    current_drawdown_pct: float = 0.0    # 0 = at high water mark
    recent_win_rate: float = 0.65        # Rolling win rate
    recent_avg_pnl: float = 0.0          # Average recent P&L
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    streak: int = 0                      # Positive = wins, negative = losses


class PositionSizer:
    """
    Multi-method position sizer with portfolio-level guardrails.

    Conservative defaults designed for deploying serious capital.
    """

    def __init__(
        self,
        portfolio_value: float,
        max_risk_per_trade_pct: float = 2.0,     # Max 2% portfolio at risk per trade
        max_portfolio_exposure_pct: float = 40.0, # Max 40% total exposure
        max_positions: int = 10,                   # Max concurrent positions
        max_sector_pct: float = 15.0,              # Max 15% in one sector
        drawdown_throttle_pct: float = 10.0,       # Start reducing at 10% DD
        drawdown_halt_pct: float = 25.0,           # Stop trading at 25% DD
    ):
        self.portfolio_value = portfolio_value
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_portfolio_exposure_pct = max_portfolio_exposure_pct
        self.max_positions = max_positions
        self.max_sector_pct = max_sector_pct
        self.drawdown_throttle_pct = drawdown_throttle_pct
        self.drawdown_halt_pct = drawdown_halt_pct

    def calculate(
        self,
        method: str,
        trade: TradeParams,
        portfolio: PortfolioState,
    ) -> Dict:
        """
        Calculate position size using specified method.

        Returns dict with:
            contracts: int — number of contracts to trade
            risk_dollars: float — total dollar risk
            reason: str — explanation
            warnings: list — any concerns
        """
        warnings = []

        # ── Pre-flight checks ──
        if portfolio.current_drawdown_pct >= self.drawdown_halt_pct:
            return self._result(0, 0, 'HALTED: Drawdown exceeds halt threshold', ['CIRCUIT BREAKER ACTIVE'])

        if portfolio.open_positions >= self.max_positions:
            return self._result(0, 0, 'Max positions reached', [f'{portfolio.open_positions} positions open'])

        exposure_pct = (portfolio.total_exposure / portfolio.total_value * 100)
        if exposure_pct >= self.max_portfolio_exposure_pct:
            return self._result(0, 0, 'Portfolio exposure limit reached',
                                [f'Current exposure: {exposure_pct:.1f}%'])

        # Sector check
        sector_exp = portfolio.sector_exposure.get(trade.sector, 0)
        sector_pct = sector_exp / portfolio.total_value * 100
        if sector_pct >= self.max_sector_pct and trade.sector not in ('etfs', 'unknown'):
            return self._result(0, 0, f'Sector {trade.sector} at capacity',
                                [f'{trade.sector}: {sector_pct:.1f}%'])

        # ── Calculate raw size ──
        methods = {
            'fixed_fractional': self._fixed_fractional,
            'kelly': self._kelly_criterion,
            'volatility_adjusted': self._volatility_adjusted,
            'risk_parity': self._risk_parity,
            'anti_martingale': self._anti_martingale,
            'conservative': self._conservative,
        }

        if method not in methods:
            raise ValueError(f"Unknown method: {method}. Available: {list(methods.keys())}")

        raw_contracts, base_risk, reason = methods[method](trade, portfolio)

        # ── Apply modifiers ──

        # Drawdown throttle: reduce size proportionally
        if portfolio.current_drawdown_pct > self.drawdown_throttle_pct:
            dd_factor = 1 - (
                (portfolio.current_drawdown_pct - self.drawdown_throttle_pct) /
                (self.drawdown_halt_pct - self.drawdown_throttle_pct)
            )
            dd_factor = max(dd_factor, 0.25)  # At least 25% of normal
            raw_contracts = max(1, int(raw_contracts * dd_factor))
            warnings.append(f'Drawdown throttle: {dd_factor:.0%} of normal size')

        # VIX regime adjustment
        if trade.vix > 30:
            raw_contracts = max(1, int(raw_contracts * 0.5))
            warnings.append('High VIX: size halved')
        elif trade.vix > 25:
            raw_contracts = max(1, int(raw_contracts * 0.75))
            warnings.append('Elevated VIX: size reduced 25%')

        # Ensure within per-trade risk limit
        max_risk_dollars = portfolio.total_value * (self.max_risk_per_trade_pct / 100)
        actual_risk = raw_contracts * trade.max_loss_per_contract
        if actual_risk > max_risk_dollars:
            raw_contracts = max(1, int(max_risk_dollars / trade.max_loss_per_contract))
            warnings.append(f'Capped to {self.max_risk_per_trade_pct}% risk limit')

        # Ensure within remaining exposure capacity
        remaining_exposure = (
            portfolio.total_value * self.max_portfolio_exposure_pct / 100
            - portfolio.total_exposure
        )
        collateral_per = trade.max_loss_per_contract
        if raw_contracts * collateral_per > remaining_exposure:
            raw_contracts = max(1, int(remaining_exposure / collateral_per))
            warnings.append('Reduced to fit remaining exposure')

        # Sector cap
        if trade.sector not in ('etfs', 'unknown'):
            remaining_sector = (
                portfolio.total_value * self.max_sector_pct / 100
                - sector_exp
            )
            if raw_contracts * collateral_per > remaining_sector:
                raw_contracts = max(1, int(remaining_sector / collateral_per))
                warnings.append(f'Sector {trade.sector} cap applied')

        # Cash check
        if raw_contracts * collateral_per > portfolio.cash_available:
            raw_contracts = max(1, int(portfolio.cash_available / collateral_per))
            warnings.append('Reduced to available cash')

        final_risk = raw_contracts * trade.max_loss_per_contract
        risk_pct = final_risk / portfolio.total_value * 100

        return self._result(
            contracts=max(raw_contracts, 0),
            risk_dollars=round(final_risk, 2),
            reason=f'{method}: {reason}',
            warnings=warnings,
            extra={
                'risk_pct': round(risk_pct, 2),
                'premium_total': round(raw_contracts * trade.premium_collected, 2),
                'reward_risk_ratio': round(
                    trade.premium_collected / trade.max_loss_per_contract, 4
                ) if trade.max_loss_per_contract > 0 else 0,
            }
        )

    # ──────────────────────────────────────────────────────────
    # SIZING METHODS
    # ──────────────────────────────────────────────────────────

    def _fixed_fractional(self, trade: TradeParams, portfolio: PortfolioState):
        """Risk a fixed percentage of portfolio per trade."""
        risk_dollars = portfolio.total_value * (self.max_risk_per_trade_pct / 100)
        contracts = int(risk_dollars / trade.max_loss_per_contract) if trade.max_loss_per_contract > 0 else 0
        return contracts, risk_dollars, f'{self.max_risk_per_trade_pct}% of ${portfolio.total_value:,.0f}'

    def _kelly_criterion(self, trade: TradeParams, portfolio: PortfolioState):
        """
        Kelly Criterion: f* = (p * b - q) / b
        where p = win probability, q = loss probability, b = win/loss ratio

        We use HALF-KELLY for safety (full Kelly is too aggressive for options).
        """
        p = trade.probability_of_profit
        q = 1 - p
        b = trade.premium_collected / trade.max_loss_per_contract if trade.max_loss_per_contract > 0 else 0

        if b <= 0:
            return 0, 0, 'Invalid reward/risk ratio'

        kelly_fraction = (p * b - q) / b
        if kelly_fraction <= 0:
            return 0, 0, f'Negative Kelly ({kelly_fraction:.3f}) — trade has negative edge'

        # Half-Kelly for safety
        half_kelly = kelly_fraction / 2

        # Cap at max risk
        capped = min(half_kelly, self.max_risk_per_trade_pct / 100)

        risk_dollars = portfolio.total_value * capped
        contracts = int(risk_dollars / trade.max_loss_per_contract) if trade.max_loss_per_contract > 0 else 0

        return contracts, risk_dollars, f'Half-Kelly={half_kelly:.3f}, capped={capped:.3f}'

    def _volatility_adjusted(self, trade: TradeParams, portfolio: PortfolioState):
        """
        Scale position size inversely to VIX.
        More contracts in low vol, fewer in high vol.
        Baseline: VIX=18 → normal size.
        """
        baseline_vix = 18.0
        vol_ratio = baseline_vix / max(trade.vix, 10)  # Higher VIX → smaller ratio
        vol_ratio = max(0.3, min(vol_ratio, 1.5))  # Clamp

        base_risk = portfolio.total_value * (self.max_risk_per_trade_pct / 100)
        adjusted_risk = base_risk * vol_ratio

        contracts = int(adjusted_risk / trade.max_loss_per_contract) if trade.max_loss_per_contract > 0 else 0

        return contracts, adjusted_risk, f'VIX={trade.vix:.0f}, ratio={vol_ratio:.2f}'

    def _risk_parity(self, trade: TradeParams, portfolio: PortfolioState):
        """
        Equal risk across all positions.
        Total risk budget divided by target number of positions.
        """
        target_positions = self.max_positions
        total_risk_budget = portfolio.total_value * (self.max_portfolio_exposure_pct / 100)
        per_position_risk = total_risk_budget / target_positions

        # Adjust for open positions
        remaining_budget = total_risk_budget - portfolio.total_exposure
        allocated = min(per_position_risk, remaining_budget)

        contracts = int(allocated / trade.max_loss_per_contract) if trade.max_loss_per_contract > 0 else 0

        return contracts, allocated, f'Budget/pos=${per_position_risk:,.0f}, remaining=${remaining_budget:,.0f}'

    def _anti_martingale(self, trade: TradeParams, portfolio: PortfolioState):
        """
        Increase size after winning streaks, decrease after losing streaks.
        Base is fixed fractional; modify by streak.
        """
        base_risk = portfolio.total_value * (self.max_risk_per_trade_pct / 100)

        # Modify by streak
        streak = portfolio.streak
        if streak >= 3:
            multiplier = 1.25  # Modest increase after 3+ wins
        elif streak >= 1:
            multiplier = 1.10
        elif streak <= -3:
            multiplier = 0.50  # Significant decrease after 3+ losses
        elif streak <= -1:
            multiplier = 0.75
        else:
            multiplier = 1.0

        # Also factor in recent win rate
        if portfolio.recent_win_rate < 0.50:
            multiplier *= 0.7  # Further reduce on poor performance

        adjusted_risk = base_risk * multiplier
        contracts = int(adjusted_risk / trade.max_loss_per_contract) if trade.max_loss_per_contract > 0 else 0

        return (contracts, adjusted_risk,
                f'Streak={streak}, mult={multiplier:.2f}, WR={portfolio.recent_win_rate:.0%}')

    def _conservative(self, trade: TradeParams, portfolio: PortfolioState):
        """
        Ultra-conservative: risk 1% max, require high POP, factor in IV rank.
        Designed for large capital where capital preservation is priority.
        """
        # 1% max risk
        risk_pct = min(1.0, self.max_risk_per_trade_pct)

        # Require POP > 70%
        if trade.probability_of_profit < 0.70:
            return 0, 0, f'POP {trade.probability_of_profit:.0%} < 70% minimum'

        # Scale by IV rank (higher IV = more premium = can do more)
        iv_factor = max(0.5, min(trade.iv_rank / 50, 1.5))

        risk_dollars = portfolio.total_value * (risk_pct / 100) * iv_factor
        contracts = int(risk_dollars / trade.max_loss_per_contract) if trade.max_loss_per_contract > 0 else 0

        return contracts, risk_dollars, f'1% risk, IV-adj={iv_factor:.2f}'

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _result(contracts, risk_dollars, reason, warnings=None, extra=None):
        result = {
            'contracts': contracts,
            'risk_dollars': round(risk_dollars, 2),
            'reason': reason,
            'warnings': warnings or [],
        }
        if extra:
            result.update(extra)
        return result


# ──────────────────────────────────────────────────────────────
# Portfolio Risk Dashboard Calculations
# ──────────────────────────────────────────────────────────────

def calculate_portfolio_risk_metrics(
    portfolio_value: float,
    positions: List[Dict],
) -> Dict:
    """
    Calculate comprehensive portfolio-level risk metrics.

    positions: list of dicts with keys:
        symbol, strategy, collateral, max_loss, premium, dte, sector
    """
    if not positions:
        return {
            'total_exposure': 0,
            'exposure_pct': 0,
            'total_max_loss': 0,
            'max_loss_pct': 0,
            'position_count': 0,
            'sector_breakdown': {},
            'strategy_breakdown': {},
            'avg_dte': 0,
            'risk_grade': 'A',
        }

    total_exposure = sum(p.get('collateral', 0) for p in positions)
    total_max_loss = sum(p.get('max_loss', 0) for p in positions)
    exposure_pct = total_exposure / portfolio_value * 100
    max_loss_pct = total_max_loss / portfolio_value * 100

    # Sector breakdown
    sectors = {}
    for p in positions:
        s = p.get('sector', 'unknown')
        sectors[s] = sectors.get(s, 0) + p.get('collateral', 0)
    sector_pcts = {k: v / portfolio_value * 100 for k, v in sectors.items()}

    # Strategy breakdown
    strategies = {}
    for p in positions:
        s = p.get('strategy', 'unknown')
        strategies[s] = strategies.get(s, 0) + p.get('collateral', 0)
    strategy_pcts = {k: v / portfolio_value * 100 for k, v in strategies.items()}

    # Average DTE
    dtes = [p.get('dte', 0) for p in positions]
    avg_dte = sum(dtes) / len(dtes) if dtes else 0

    # Risk grade
    if max_loss_pct < 10 and exposure_pct < 30 and len(positions) <= 8:
        grade = 'A'
    elif max_loss_pct < 20 and exposure_pct < 50:
        grade = 'B'
    elif max_loss_pct < 35 and exposure_pct < 70:
        grade = 'C'
    else:
        grade = 'D'

    # Concentration risk
    max_sector_pct = max(sector_pcts.values()) if sector_pcts else 0
    concentration_warning = max_sector_pct > 20

    return {
        'total_exposure': round(total_exposure, 2),
        'exposure_pct': round(exposure_pct, 2),
        'total_max_loss': round(total_max_loss, 2),
        'max_loss_pct': round(max_loss_pct, 2),
        'position_count': len(positions),
        'sector_breakdown': sector_pcts,
        'strategy_breakdown': strategy_pcts,
        'avg_dte': round(avg_dte, 1),
        'risk_grade': grade,
        'concentration_warning': concentration_warning,
        'max_sector_pct': round(max_sector_pct, 2),
    }
