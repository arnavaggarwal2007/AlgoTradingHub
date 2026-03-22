"""
================================================================================
RISK ANALYSIS ENGINE — Comprehensive Portfolio Risk Assessment
================================================================================

Provides:
1. Portfolio-level Greeks (delta, gamma, vega, theta)
2. Stress testing (simulated crash scenarios)
3. Value-at-Risk (VaR) and Conditional VaR
4. Correlation matrix and concentration risk
5. Over-exposure detection and alerts
6. Tail risk quantification
7. Risk-adjusted performance metrics
8. Drawdown analysis with recovery time estimation

Usage:
    engine = RiskAnalysisEngine(portfolio_value=100000)
    report = engine.full_risk_report(positions, trade_history)
    engine.print_report(report)
================================================================================
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RiskAnalysisEngine:
    """Comprehensive risk analysis for options premium portfolios."""

    def __init__(
        self,
        portfolio_value: float,
        risk_free_rate: float = 0.05,
        confidence_level: float = 0.95,
    ):
        self.portfolio_value = portfolio_value
        self.risk_free_rate = risk_free_rate
        self.confidence_level = confidence_level

    def full_risk_report(
        self,
        positions: List[Dict] = None,
        trade_history: List[Dict] = None,
        equity_curve: pd.DataFrame = None,
    ) -> Dict:
        """Generate comprehensive risk report."""
        positions = positions or []
        trade_history = trade_history or []

        report = {
            'timestamp': datetime.now().isoformat(),
            'portfolio_value': self.portfolio_value,
        }

        # 1. Exposure analysis
        report['exposure'] = self._analyze_exposure(positions)

        # 2. Portfolio Greeks
        report['greeks'] = self._portfolio_greeks(positions)

        # 3. Stress tests
        report['stress_tests'] = self._stress_test(positions)

        # 4. Historical performance risk
        if trade_history:
            report['performance_risk'] = self._performance_risk(trade_history)

        # 5. VaR and CVaR
        if equity_curve is not None and not equity_curve.empty:
            report['var_analysis'] = self._var_analysis(equity_curve)

        # 6. Over-exposure alerts
        report['alerts'] = self._generate_alerts(report)

        # 7. Overall risk score
        report['risk_score'] = self._calculate_risk_score(report)

        return report

    # ──────────────────────────────────────────────────────────
    # 1. EXPOSURE ANALYSIS
    # ──────────────────────────────────────────────────────────

    def _analyze_exposure(self, positions: List[Dict]) -> Dict:
        if not positions:
            return {
                'total_collateral': 0,
                'total_max_loss': 0,
                'exposure_pct': 0,
                'max_loss_pct': 0,
                'position_count': 0,
                'sector_exposure': {},
                'strategy_exposure': {},
                'dte_distribution': {},
                'largest_position_pct': 0,
            }

        total_collateral = sum(p.get('collateral', 0) for p in positions)
        total_max_loss = sum(p.get('max_loss', 0) for p in positions)

        # Sector exposure
        sectors = {}
        for p in positions:
            s = p.get('sector', 'unknown')
            sectors[s] = sectors.get(s, 0) + p.get('collateral', 0)

        # Strategy exposure
        strategies = {}
        for p in positions:
            s = p.get('strategy', 'unknown')
            strategies[s] = strategies.get(s, 0) + p.get('collateral', 0)

        # DTE buckets
        dte_buckets = {'0-7': 0, '8-21': 0, '22-45': 0, '46+': 0}
        for p in positions:
            dte = p.get('dte', 30)
            if dte <= 7:
                dte_buckets['0-7'] += 1
            elif dte <= 21:
                dte_buckets['8-21'] += 1
            elif dte <= 45:
                dte_buckets['22-45'] += 1
            else:
                dte_buckets['46+'] += 1

        # Largest single position
        largest = max(p.get('collateral', 0) for p in positions) if positions else 0

        return {
            'total_collateral': round(total_collateral, 2),
            'total_max_loss': round(total_max_loss, 2),
            'exposure_pct': round(total_collateral / self.portfolio_value * 100, 2),
            'max_loss_pct': round(total_max_loss / self.portfolio_value * 100, 2),
            'position_count': len(positions),
            'sector_exposure': {k: round(v / self.portfolio_value * 100, 2) for k, v in sectors.items()},
            'strategy_exposure': {k: round(v / self.portfolio_value * 100, 2) for k, v in strategies.items()},
            'dte_distribution': dte_buckets,
            'largest_position_pct': round(largest / self.portfolio_value * 100, 2),
        }

    # ──────────────────────────────────────────────────────────
    # 2. PORTFOLIO GREEKS
    # ──────────────────────────────────────────────────────────

    def _portfolio_greeks(self, positions: List[Dict]) -> Dict:
        """Aggregate Greeks across all positions."""
        total_delta = sum(p.get('delta', 0) * p.get('contracts', 1) * 100 for p in positions)
        total_gamma = sum(p.get('gamma', 0) * p.get('contracts', 1) * 100 for p in positions)
        total_theta = sum(p.get('theta', 0) * p.get('contracts', 1) * 100 for p in positions)
        total_vega = sum(p.get('vega', 0) * p.get('contracts', 1) * 100 for p in positions)

        # Dollar impact interpretation
        return {
            'net_delta': round(total_delta, 2),
            'net_gamma': round(total_gamma, 4),
            'net_theta': round(total_theta, 2),
            'net_vega': round(total_vega, 2),
            'delta_interpretation': self._interpret_delta(total_delta),
            'theta_daily_income': round(abs(total_theta), 2),
            'vega_risk_1pct_iv': round(abs(total_vega), 2),
        }

    @staticmethod
    def _interpret_delta(delta: float) -> str:
        """Interpret portfolio delta."""
        if abs(delta) < 10:
            return 'Delta-neutral — minimal directional exposure'
        elif delta > 50:
            return f'Bullish bias — equivalent to long {delta:.0f} shares'
        elif delta < -50:
            return f'Bearish bias — equivalent to short {abs(delta):.0f} shares'
        elif delta > 0:
            return f'Slightly bullish — equivalent to long {delta:.0f} shares'
        else:
            return f'Slightly bearish — equivalent to short {abs(delta):.0f} shares'

    # ──────────────────────────────────────────────────────────
    # 3. STRESS TESTING
    # ──────────────────────────────────────────────────────────

    def _stress_test(self, positions: List[Dict]) -> Dict:
        """Simulate portfolio impact under various scenarios."""
        if not positions:
            return {}

        total_collateral = sum(p.get('collateral', 0) for p in positions)
        total_max_loss = sum(p.get('max_loss', 0) for p in positions)
        net_delta = sum(p.get('delta', 0) * p.get('contracts', 1) * 100 for p in positions)
        net_vega = sum(p.get('vega', 0) * p.get('contracts', 1) * 100 for p in positions)

        scenarios = {
            'SPY -3% (normal correction)': {
                'spy_move': -0.03,
                'vix_move': 0.20,
                'estimated_pnl': round(net_delta * (-0.03 * 500) + net_vega * 3, 2),
            },
            'SPY -5% (sharp selloff)': {
                'spy_move': -0.05,
                'vix_move': 0.40,
                'estimated_pnl': round(net_delta * (-0.05 * 500) + net_vega * 6, 2),
            },
            'SPY -10% (crash)': {
                'spy_move': -0.10,
                'vix_move': 1.00,
                'estimated_pnl': round(-total_max_loss * 0.7, 2),  # ~70% of max loss
            },
            'SPY -20% (black swan)': {
                'spy_move': -0.20,
                'vix_move': 2.50,
                'estimated_pnl': round(-total_max_loss * 0.95, 2),
            },
            'SPY +5% (strong rally)': {
                'spy_move': 0.05,
                'vix_move': -0.15,
                'estimated_pnl': round(net_delta * (0.05 * 500), 2),
            },
            'VIX spike to 40 (vol explosion)': {
                'spy_move': -0.02,
                'vix_move': 1.00,
                'estimated_pnl': round(net_vega * 15, 2),
            },
        }

        for name, s in scenarios.items():
            pnl = s['estimated_pnl']
            s['portfolio_impact_pct'] = round(pnl / self.portfolio_value * 100, 2)
            s['surviving'] = (self.portfolio_value + pnl) > 0

        return scenarios

    # ──────────────────────────────────────────────────────────
    # 4. HISTORICAL PERFORMANCE RISK
    # ──────────────────────────────────────────────────────────

    def _performance_risk(self, trades: List[Dict]) -> Dict:
        """Analyze risk from trade history."""
        pnls = [t.get('pnl', 0) for t in trades]
        if not pnls:
            return {}

        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]

        win_rate = len(winners) / len(pnls) * 100

        avg_win = np.mean(winners) if winners else 0
        avg_loss = np.mean(losers) if losers else 0

        # Expectancy
        expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)

        # Profit factor
        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Consecutive losses
        max_consecutive_losses = 0
        current_streak = 0
        for p in pnls:
            if p <= 0:
                current_streak += 1
                max_consecutive_losses = max(max_consecutive_losses, current_streak)
            else:
                current_streak = 0

        # Worst single trade
        worst_trade = min(pnls)
        worst_trade_pct = worst_trade / self.portfolio_value * 100

        # Recovery factor (total profit / max drawdown)
        total_profit = sum(pnls)
        equity = np.cumsum(pnls) + self.portfolio_value
        peak = np.maximum.accumulate(equity)
        max_dd = np.min((equity - peak) / peak) * 100

        return {
            'total_trades': len(pnls),
            'win_rate': round(win_rate, 1),
            'avg_winner': round(avg_win, 2),
            'avg_loser': round(avg_loss, 2),
            'avg_win_loss_ratio': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
            'expectancy': round(expectancy, 2),
            'profit_factor': round(profit_factor, 2),
            'max_consecutive_losses': max_consecutive_losses,
            'worst_single_trade': round(worst_trade, 2),
            'worst_trade_pct': round(worst_trade_pct, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'total_pnl': round(total_profit, 2),
        }

    # ──────────────────────────────────────────────────────────
    # 5. VALUE-AT-RISK
    # ──────────────────────────────────────────────────────────

    def _var_analysis(self, equity_curve: pd.DataFrame) -> Dict:
        """Calculate VaR and CVaR from equity curve."""
        if 'equity' not in equity_curve.columns or len(equity_curve) < 10:
            return {}

        returns = equity_curve['equity'].pct_change().dropna()
        if returns.empty:
            return {}

        # Historical VaR
        var_pct = float(np.percentile(returns, (1 - self.confidence_level) * 100))
        var_dollar = var_pct * self.portfolio_value

        # Conditional VaR (Expected Shortfall)
        tail_returns = returns[returns <= var_pct]
        cvar_pct = float(tail_returns.mean()) if len(tail_returns) > 0 else var_pct
        cvar_dollar = cvar_pct * self.portfolio_value

        # Parametric VaR (assuming normal distribution)
        z_score = 1.645  # 95% confidence
        param_var = -(returns.mean() - z_score * returns.std()) * self.portfolio_value

        return {
            'confidence_level': self.confidence_level,
            'historical_var_pct': round(var_pct * 100, 3),
            'historical_var_dollar': round(abs(var_dollar), 2),
            'cvar_pct': round(cvar_pct * 100, 3),
            'cvar_dollar': round(abs(cvar_dollar), 2),
            'parametric_var_dollar': round(param_var, 2),
            'interpretation': (
                f'With {self.confidence_level:.0%} confidence, daily loss will not exceed '
                f'${abs(var_dollar):,.2f} ({abs(var_pct*100):.2f}%)'
            ),
        }

    # ──────────────────────────────────────────────────────────
    # 6. ALERTS
    # ──────────────────────────────────────────────────────────

    def _generate_alerts(self, report: Dict) -> List[Dict]:
        """Generate risk alerts from the report."""
        alerts = []

        exp = report.get('exposure', {})
        if exp.get('exposure_pct', 0) > 50:
            alerts.append({
                'level': 'CRITICAL',
                'message': f"Portfolio exposure at {exp['exposure_pct']}% — exceeds 50% limit",
                'action': 'Close positions to reduce exposure',
            })
        elif exp.get('exposure_pct', 0) > 35:
            alerts.append({
                'level': 'WARNING',
                'message': f"Portfolio exposure at {exp['exposure_pct']}% — approaching limit",
                'action': 'Avoid opening new positions',
            })

        if exp.get('max_loss_pct', 0) > 25:
            alerts.append({
                'level': 'CRITICAL',
                'message': f"Max loss scenario: {exp['max_loss_pct']}% of portfolio",
                'action': 'Reduce position sizes or add hedges',
            })

        if exp.get('largest_position_pct', 0) > 10:
            alerts.append({
                'level': 'WARNING',
                'message': f"Largest position is {exp['largest_position_pct']}% of portfolio",
                'action': 'Consider reducing largest position',
            })

        # Sector concentration
        for sector, pct in exp.get('sector_exposure', {}).items():
            if pct > 20:
                alerts.append({
                    'level': 'WARNING',
                    'message': f"{sector} sector at {pct}% — exceeds 20% concentration limit",
                    'action': f'Diversify away from {sector}',
                })

        # DTE clustering
        dte_dist = exp.get('dte_distribution', {})
        if dte_dist.get('0-7', 0) > 3:
            alerts.append({
                'level': 'WARNING',
                'message': f"{dte_dist['0-7']} positions expiring within 7 days",
                'action': 'Manage expiring positions — gamma risk is elevated',
            })

        # Greeks
        greeks = report.get('greeks', {})
        if abs(greeks.get('net_delta', 0)) > 100:
            alerts.append({
                'level': 'WARNING',
                'message': f"Net delta = {greeks['net_delta']} — significant directional risk",
                'action': 'Consider delta-neutral adjustments',
            })

        perf = report.get('performance_risk', {})
        if perf.get('max_consecutive_losses', 0) >= 5:
            alerts.append({
                'level': 'CRITICAL',
                'message': f"{perf['max_consecutive_losses']} consecutive losses recorded",
                'action': 'Review strategy parameters or pause trading',
            })

        return alerts

    # ──────────────────────────────────────────────────────────
    # 7. RISK SCORE
    # ──────────────────────────────────────────────────────────

    def _calculate_risk_score(self, report: Dict) -> Dict:
        """Calculate overall 0-100 risk score (0=safest, 100=highest risk)."""
        score = 0

        exp = report.get('exposure', {})
        score += min(exp.get('exposure_pct', 0), 30)  # Up to 30 points
        score += min(exp.get('max_loss_pct', 0) * 0.5, 20)  # Up to 20 points

        # Position concentration
        score += min(exp.get('largest_position_pct', 0), 10)  # Up to 10 points

        # Greeks risk
        greeks = report.get('greeks', {})
        score += min(abs(greeks.get('net_delta', 0)) / 50, 10)  # Up to 10 points

        # Performance degradation
        perf = report.get('performance_risk', {})
        if perf.get('win_rate', 65) < 50:
            score += 15
        elif perf.get('win_rate', 65) < 60:
            score += 5

        # Alerts
        critical_alerts = len([a for a in report.get('alerts', []) if a['level'] == 'CRITICAL'])
        score += critical_alerts * 10

        score = min(score, 100)

        if score < 25:
            grade = 'A'
            label = 'LOW RISK'
        elif score < 45:
            grade = 'B'
            label = 'MODERATE RISK'
        elif score < 65:
            grade = 'C'
            label = 'ELEVATED RISK'
        else:
            grade = 'D'
            label = 'HIGH RISK'

        return {
            'score': round(score, 1),
            'grade': grade,
            'label': label,
        }

    # ──────────────────────────────────────────────────────────
    # REPORTING
    # ──────────────────────────────────────────────────────────

    def print_report(self, report: Dict):
        """Print a formatted risk report to console."""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE RISK ANALYSIS REPORT")
        print(f"Portfolio Value: ${self.portfolio_value:,.2f}")
        print(f"Generated: {report.get('timestamp', '')}")
        print("=" * 80)

        # Risk score
        rs = report.get('risk_score', {})
        print(f"\n{'OVERALL RISK GRADE:':<30} {rs.get('grade', '?')} ({rs.get('label', '')})")
        print(f"{'Risk Score:':<30} {rs.get('score', 0)}/100")

        # Exposure
        exp = report.get('exposure', {})
        print(f"\n--- EXPOSURE ---")
        print(f"{'Portfolio Exposure:':<30} {exp.get('exposure_pct', 0):.1f}%")
        print(f"{'Max Loss Scenario:':<30} {exp.get('max_loss_pct', 0):.1f}% (${exp.get('total_max_loss', 0):,.2f})")
        print(f"{'Open Positions:':<30} {exp.get('position_count', 0)}")
        print(f"{'Largest Position:':<30} {exp.get('largest_position_pct', 0):.1f}%")

        # Greeks
        greeks = report.get('greeks', {})
        if greeks:
            print(f"\n--- PORTFOLIO GREEKS ---")
            print(f"{'Net Delta:':<30} {greeks.get('net_delta', 0):.2f} ({greeks.get('delta_interpretation', '')})")
            print(f"{'Net Theta (daily):':<30} ${greeks.get('theta_daily_income', 0):.2f}")
            print(f"{'Net Vega (1% IV):':<30} ${greeks.get('vega_risk_1pct_iv', 0):.2f}")

        # Stress tests
        stress = report.get('stress_tests', {})
        if stress:
            print(f"\n--- STRESS TEST SCENARIOS ---")
            for name, s in stress.items():
                pnl = s.get('estimated_pnl', 0)
                impact = s.get('portfolio_impact_pct', 0)
                color = '✅' if impact > -5 else '⚠️' if impact > -15 else '❌'
                print(f"  {color} {name:<35} P&L: ${pnl:>10,.2f} ({impact:>6.2f}%)")

        # VaR
        var = report.get('var_analysis', {})
        if var:
            print(f"\n--- VALUE-AT-RISK ({var.get('confidence_level', 0.95):.0%}) ---")
            print(f"{'Daily VaR:':<30} ${var.get('historical_var_dollar', 0):,.2f}")
            print(f"{'Conditional VaR (CVaR):':<30} ${var.get('cvar_dollar', 0):,.2f}")

        # Alerts
        alerts = report.get('alerts', [])
        if alerts:
            print(f"\n--- ALERTS ({len(alerts)}) ---")
            for a in alerts:
                icon = '🔴' if a['level'] == 'CRITICAL' else '🟡'
                print(f"  {icon} [{a['level']}] {a['message']}")
                print(f"     Action: {a['action']}")

        # Performance risk
        perf = report.get('performance_risk', {})
        if perf:
            print(f"\n--- PERFORMANCE RISK ---")
            print(f"{'Win Rate:':<30} {perf.get('win_rate', 0):.1f}%")
            print(f"{'Profit Factor:':<30} {perf.get('profit_factor', 0):.2f}")
            print(f"{'Expectancy:':<30} ${perf.get('expectancy', 0):.2f}/trade")
            print(f"{'Max Consecutive Losses:':<30} {perf.get('max_consecutive_losses', 0)}")
            print(f"{'Worst Single Trade:':<30} ${perf.get('worst_single_trade', 0):,.2f} ({perf.get('worst_trade_pct', 0):.2f}%)")
            print(f"{'Max Drawdown:':<30} {perf.get('max_drawdown_pct', 0):.2f}%")

        print("\n" + "=" * 80)
