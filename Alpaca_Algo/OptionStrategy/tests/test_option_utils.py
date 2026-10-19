"""
================================================================================
UNIT TESTS — Option Utilities (option_utils.py)
================================================================================
Tests Black-Scholes Greeks, IV Rank, OCC parsing, POP, and premium analysis.
================================================================================
"""

import math
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.option_utils import (
    norm_cdf,
    norm_pdf,
    black_scholes_greeks,
    calculate_iv_rank,
    calculate_iv_percentile,
    calculate_dte,
    get_target_expiration,
    dte_to_years,
    parse_occ_symbol,
    build_occ_symbol,
    probability_of_profit_put,
    probability_of_profit_spread,
    annualized_return,
    risk_reward_ratio,
)


# ──────────────────────────────────────────────────────────────
# norm_cdf / norm_pdf
# ──────────────────────────────────────────────────────────────

class TestNormFunctions:
    def test_norm_cdf_zero(self):
        assert abs(norm_cdf(0) - 0.5) < 1e-10

    def test_norm_cdf_large_positive(self):
        assert norm_cdf(5.0) > 0.999

    def test_norm_cdf_large_negative(self):
        assert norm_cdf(-5.0) < 0.001

    def test_norm_cdf_symmetry(self):
        assert abs(norm_cdf(1.0) + norm_cdf(-1.0) - 1.0) < 1e-10

    def test_norm_pdf_zero(self):
        expected = 1 / math.sqrt(2 * math.pi)
        assert abs(norm_pdf(0) - expected) < 1e-10

    def test_norm_pdf_symmetric(self):
        assert abs(norm_pdf(1.5) - norm_pdf(-1.5)) < 1e-10

    def test_norm_pdf_positive(self):
        assert norm_pdf(2.0) > 0


# ──────────────────────────────────────────────────────────────
# Black-Scholes Greeks
# ──────────────────────────────────────────────────────────────

class TestBlackScholesGreeks:
    def test_put_price_positive(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='put')
        assert g['price'] > 0, "ATM put should have positive price"

    def test_call_price_positive(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='call')
        assert g['price'] > 0

    def test_put_delta_negative(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='put')
        assert g['delta'] < 0, "Put delta must be negative"

    def test_call_delta_positive(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='call')
        assert g['delta'] > 0, "Call delta must be positive"

    def test_atm_call_delta_near_half(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='call')
        assert 0.4 < g['delta'] < 0.65, f"ATM call delta should be ~0.5, got {g['delta']}"

    def test_deep_otm_put_low_delta(self):
        g = black_scholes_greeks(S=100, K=70, T=0.1, r=0.05, sigma=0.20, option_type='put')
        assert abs(g['delta']) < 0.05, "Deep OTM put should have delta near 0"

    def test_gamma_positive(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='put')
        assert g['gamma'] > 0, "Gamma should always be positive"

    def test_theta_negative_for_puts(self):
        g = black_scholes_greeks(S=100, K=95, T=0.25, r=0.05, sigma=0.20, option_type='put')
        assert g['theta'] < 0, "Theta for short-dated puts should be negative"

    def test_vega_positive(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='call')
        assert g['vega'] > 0

    def test_put_call_parity(self):
        """Put-call parity: C - P = S - K*e^(-rT)"""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.20
        c = black_scholes_greeks(S, K, T, r, sigma, 'call')
        p = black_scholes_greeks(S, K, T, r, sigma, 'put')
        parity = c['price'] - p['price'] - (S - K * math.exp(-r * T))
        assert abs(parity) < 0.01, f"Put-call parity violated: diff={parity}"

    def test_zero_time_returns_zeros(self):
        g = black_scholes_greeks(S=100, K=100, T=0, r=0.05, sigma=0.20)
        assert g['price'] == 0

    def test_zero_vol_returns_zeros(self):
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0)
        assert g['price'] == 0

    def test_higher_vol_higher_premium(self):
        low = black_scholes_greeks(S=100, K=95, T=0.25, r=0.05, sigma=0.15, option_type='put')
        high = black_scholes_greeks(S=100, K=95, T=0.25, r=0.05, sigma=0.40, option_type='put')
        assert high['price'] > low['price'], "Higher IV should mean higher premium"

    def test_longer_dte_higher_premium(self):
        short = black_scholes_greeks(S=100, K=95, T=0.08, r=0.05, sigma=0.20, option_type='put')
        long = black_scholes_greeks(S=100, K=95, T=0.25, r=0.05, sigma=0.20, option_type='put')
        assert long['price'] >= short['price'], "Longer DTE should have higher premium"


# ──────────────────────────────────────────────────────────────
# IV Rank / IV Percentile
# ──────────────────────────────────────────────────────────────

class TestIVMetrics:
    def test_iv_rank_midpoint(self):
        history = list(range(10, 50))  # 10..49
        result = calculate_iv_rank(30, history)
        # (30-10)/(49-10) = 20/39 ≈ 51.3
        assert 50 < result < 53

    def test_iv_rank_at_low(self):
        history = [10, 20, 30, 40, 50]
        assert calculate_iv_rank(10, history) == 0

    def test_iv_rank_at_high(self):
        history = [10, 20, 30, 40, 50]
        assert calculate_iv_rank(50, history) == 100

    def test_iv_rank_empty_history(self):
        assert calculate_iv_rank(25, []) == 50.0

    def test_iv_rank_short_history(self):
        assert calculate_iv_rank(25, [20]) == 50.0

    def test_iv_rank_same_values(self):
        assert calculate_iv_rank(25, [25, 25, 25, 25, 25]) == 50.0

    def test_iv_rank_clamped(self):
        history = [20, 30, 40, 25, 35]
        assert calculate_iv_rank(100, history) == 100
        assert calculate_iv_rank(5, history) == 0

    def test_iv_percentile_all_below(self):
        history = [10, 15, 20, 25, 30]
        assert calculate_iv_percentile(35, history) == 100.0

    def test_iv_percentile_all_above(self):
        history = [40, 45, 50, 55, 60]
        assert calculate_iv_percentile(35, history) == 0.0

    def test_iv_percentile_midpoint(self):
        history = [10, 20, 30, 40, 50]
        result = calculate_iv_percentile(30, history)
        # 2 out of 5 below 30 = 40%
        assert result == 40.0


# ──────────────────────────────────────────────────────────────
# DTE Calculations
# ──────────────────────────────────────────────────────────────

class TestDTE:
    def test_dte_future(self):
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        assert calculate_dte(future) == 30

    def test_dte_today(self):
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        assert calculate_dte(today) == 0

    def test_dte_past(self):
        assert calculate_dte('2020-01-01') < 0

    def test_get_target_expiration_format(self):
        min_d, max_d = get_target_expiration(30, 45)
        assert len(min_d) == 10  # YYYY-MM-DD
        assert len(max_d) == 10

    def test_dte_to_years(self):
        assert abs(dte_to_years(365) - 1.0) < 1e-10
        assert abs(dte_to_years(30) - 30 / 365) < 1e-10


# ──────────────────────────────────────────────────────────────
# OCC Symbol Parsing
# ──────────────────────────────────────────────────────────────

class TestOCCParsing:
    def test_parse_standard(self):
        result = parse_occ_symbol('AAPL260320C00150000')
        assert result is not None
        assert result['underlying'] == 'AAPL'
        assert result['expiration'] == '2026-03-20'
        assert result['option_type'] == 'call'
        assert result['strike'] == 150.0

    def test_parse_put(self):
        result = parse_occ_symbol('SPY260120P00450000')
        assert result is not None
        assert result['option_type'] == 'put'
        assert result['strike'] == 450.0

    def test_parse_fractional_strike(self):
        result = parse_occ_symbol('AAPL260320C00150500')
        assert result is not None
        assert result['strike'] == 150.5

    def test_parse_short_symbol(self):
        result = parse_occ_symbol('XOM260320P00085000')
        assert result is not None
        assert result['underlying'] == 'XOM'
        assert result['strike'] == 85.0

    def test_parse_invalid(self):
        result = parse_occ_symbol('INVALID')
        assert result is None

    def test_parse_empty(self):
        result = parse_occ_symbol('')
        assert result is None

    def test_build_occ_symbol(self):
        sym = build_occ_symbol('AAPL', '2026-03-20', 'call', 150.0)
        assert '260320' in sym
        assert 'C' in sym
        assert '00150000' in sym

    def test_build_and_parse_roundtrip(self):
        sym = build_occ_symbol('SPY', '2026-06-19', 'put', 430.0)
        parsed = parse_occ_symbol(sym.replace(' ', ''))
        assert parsed['strike'] == 430.0
        assert parsed['option_type'] == 'put'


# ──────────────────────────────────────────────────────────────
# Probability of Profit
# ──────────────────────────────────────────────────────────────

class TestPOP:
    def test_pop_put_far_otm(self):
        pop = probability_of_profit_put(
            stock_price=100, strike=80, premium=0.50, iv=0.20, dte=30
        )
        assert pop > 90, f"Deep OTM put should have >90% POP, got {pop}"

    def test_pop_put_atm(self):
        pop = probability_of_profit_put(
            stock_price=100, strike=100, premium=3.0, iv=0.25, dte=30
        )
        assert 40 < pop < 80, f"ATM put POP should be moderate, got {pop}"

    def test_pop_zero_dte(self):
        pop = probability_of_profit_put(
            stock_price=100, strike=95, premium=1.0, iv=0.20, dte=0
        )
        assert pop == 0.0

    def test_pop_spread(self):
        pop = probability_of_profit_spread(
            stock_price=450, short_strike=420, long_strike=415,
            net_credit=1.50, iv=0.18, dte=30
        )
        assert pop > 70

    def test_pop_spread_zero_iv(self):
        pop = probability_of_profit_spread(
            stock_price=450, short_strike=420, long_strike=415,
            net_credit=1.50, iv=0, dte=30
        )
        assert pop == 0.0


# ──────────────────────────────────────────────────────────────
# Premium Analysis
# ──────────────────────────────────────────────────────────────

class TestPremiumAnalysis:
    def test_annualized_return_basic(self):
        # $2 premium on $50 collateral, 30 DTE
        ar = annualized_return(2.0, 50.0, 30)
        expected = (2.0 / 50.0) * (365 / 30) * 100
        assert abs(ar - expected) < 0.01

    def test_annualized_return_zero_collateral(self):
        assert annualized_return(2.0, 0, 30) == 0.0

    def test_annualized_return_zero_dte(self):
        assert annualized_return(2.0, 50.0, 0) == 0.0

    def test_risk_reward_basic(self):
        rr = risk_reward_ratio(max_profit=100, max_loss=300)
        assert rr == 3.0

    def test_risk_reward_zero_profit(self):
        rr = risk_reward_ratio(max_profit=0, max_loss=100)
        assert rr == float('inf')

    def test_risk_reward_equal(self):
        assert risk_reward_ratio(100, 100) == 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
