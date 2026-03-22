"""
================================================================================
OPTION UTILITIES
================================================================================
Helper functions for options calculations:
- Black-Scholes Greeks approximation
- IV Rank / IV Percentile calculation
- DTE computation
- OCC symbol parsing
- Probability of Profit estimation
================================================================================
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger('options_strategy')


# ──────────────────────────────────────────────────────────────
# BLACK-SCHOLES GREEKS (Analytical Approximation)
# ──────────────────────────────────────────────────────────────

def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes_greeks(
    S: float,       # Current stock price
    K: float,       # Strike price
    T: float,       # Time to expiration in years
    r: float,       # Risk-free rate (e.g., 0.05 for 5%)
    sigma: float,   # Implied volatility (e.g., 0.20 for 20%)
    option_type: str = 'put'  # 'call' or 'put'
) -> dict:
    """
    Calculate Black-Scholes Greeks for a European option.
    
    Returns:
        dict with keys: price, delta, gamma, theta, vega, rho
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {'price': 0, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * norm_pdf(d1) * math.sqrt(T) / 100  # Per 1% change in IV
    
    if option_type == 'call':
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        delta = norm_cdf(d1)
        theta = (
            -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * norm_cdf(d2)
        ) / 365
        rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100
    else:  # put
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        delta = norm_cdf(d1) - 1  # Negative for puts
        theta = (
            -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * norm_cdf(-d2)
        ) / 365
        rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100
    
    return {
        'price': round(price, 4),
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 4),
        'vega': round(vega, 4),
        'rho': round(rho, 4),
    }


# ──────────────────────────────────────────────────────────────
# IV RANK & IV PERCENTILE
# ──────────────────────────────────────────────────────────────

def calculate_iv_rank(current_iv: float, iv_history: list) -> float:
    """
    IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV)
    
    Scale: 0-100
    - IVR > 50: IV is elevated → GOOD time to sell premium
    - IVR > 30: Acceptable for premium selling
    - IVR < 20: Low IV → avoid selling (poor premiums)
    """
    if not iv_history or len(iv_history) < 5:
        return 50.0  # Default to neutral if no history
    
    iv_low = min(iv_history)
    iv_high = max(iv_history)
    
    if iv_high == iv_low:
        return 50.0
    
    iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
    return round(max(0, min(100, iv_rank)), 1)


def calculate_iv_percentile(current_iv: float, iv_history: list) -> float:
    """
    IV Percentile = % of days in the past year where IV was BELOW current IV.
    
    More accurate than IV Rank for determining if IV is truly elevated.
    """
    if not iv_history or len(iv_history) < 5:
        return 50.0
    
    below_count = sum(1 for iv in iv_history if iv < current_iv)
    return round((below_count / len(iv_history)) * 100, 1)


# ──────────────────────────────────────────────────────────────
# DTE & TIME CALCULATIONS
# ──────────────────────────────────────────────────────────────

def calculate_dte(expiration_date: str) -> int:
    """
    Calculate Days to Expiration from today.
    
    Args:
        expiration_date: 'YYYY-MM-DD' format
    
    Returns:
        Integer days until expiration
    """
    exp = datetime.strptime(expiration_date, '%Y-%m-%d')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (exp - today).days


def get_target_expiration(min_dte: int = 30, max_dte: int = 45) -> Tuple[str, str]:
    """
    Get the target expiration date range.
    
    Returns:
        Tuple of (min_date, max_date) in YYYY-MM-DD format
    """
    today = datetime.now()
    min_date = (today + timedelta(days=min_dte)).strftime('%Y-%m-%d')
    max_date = (today + timedelta(days=max_dte)).strftime('%Y-%m-%d')
    return min_date, max_date


def dte_to_years(dte: int) -> float:
    """Convert DTE to fractional years for Black-Scholes."""
    return dte / 365.0


# ──────────────────────────────────────────────────────────────
# OCC SYMBOL PARSING
# ──────────────────────────────────────────────────────────────

def parse_occ_symbol(occ_symbol: str) -> Optional[dict]:
    """
    Parse an OCC option symbol into its components.
    
    OCC Format: SYMBOL + YYMMDD + C/P + Strike (8 digits, 5.3 format)
    Example: AAPL260320C00150000 → AAPL, 2026-03-20, Call, $150.000
    
    Returns:
        dict with keys: underlying, expiration, option_type, strike
    """
    try:
        # Find where the date starts (first digit sequence of length 6)
        i = 0
        while i < len(occ_symbol) and not occ_symbol[i].isdigit():
            i += 1
        
        if i > len(occ_symbol) - 15:  # Need at least YYMMDD + C/P + 8 digits
            return None
        
        underlying = occ_symbol[:i]
        date_str = occ_symbol[i:i+6]
        option_type = 'call' if occ_symbol[i+6] == 'C' else 'put'
        strike_str = occ_symbol[i+7:]
        
        # Parse date
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiration = f"{year}-{month:02d}-{day:02d}"
        
        # Parse strike (5.3 format: divide by 1000)
        strike = int(strike_str) / 1000.0
        
        return {
            'underlying': underlying,
            'expiration': expiration,
            'option_type': option_type,
            'strike': strike,
        }
    except (ValueError, IndexError):
        logger.error(f"Failed to parse OCC symbol: {occ_symbol}")
        return None


def build_occ_symbol(
    underlying: str,
    expiration: str,  # YYYY-MM-DD
    option_type: str,  # 'call' or 'put'
    strike: float,
) -> str:
    """
    Build an OCC option symbol from components.
    
    Example: build_occ_symbol('AAPL', '2026-03-20', 'call', 150.0) 
             → 'AAPL  260320C00150000'
    """
    # Parse expiration
    exp = datetime.strptime(expiration, '%Y-%m-%d')
    date_str = exp.strftime('%y%m%d')
    
    # Option type
    type_char = 'C' if option_type == 'call' else 'P'
    
    # Strike in 5.3 format (multiply by 1000, pad to 8 digits)
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    
    # Pad underlying to 6 characters
    underlying_padded = f"{underlying:<6}"
    
    return f"{underlying_padded}{date_str}{type_char}{strike_str}"


# ──────────────────────────────────────────────────────────────
# PROBABILITY OF PROFIT (POP)
# ──────────────────────────────────────────────────────────────

def probability_of_profit_put(
    stock_price: float,
    strike: float,
    premium: float,
    iv: float,
    dte: int,
) -> float:
    """
    Estimate probability that a sold put expires OTM (profitable).
    
    Uses Black-Scholes to estimate the probability.
    Breakeven = Strike - Premium collected
    """
    if dte <= 0 or iv <= 0:
        return 0.0
    
    breakeven = strike - premium
    T = dte / 365.0
    
    # Simplified: probability that stock stays above breakeven
    d2 = (math.log(stock_price / breakeven) + (0.05 - 0.5 * iv**2) * T) / (iv * math.sqrt(T))
    pop = norm_cdf(d2) * 100
    
    return round(pop, 1)


def probability_of_profit_spread(
    stock_price: float,
    short_strike: float,
    long_strike: float,
    net_credit: float,
    iv: float,
    dte: int,
) -> float:
    """
    Estimate probability of profit for a credit spread.
    
    For bull put spread: POP = P(stock > short_strike - net_credit)
    """
    if dte <= 0 or iv <= 0:
        return 0.0
    
    breakeven = short_strike - net_credit
    T = dte / 365.0
    
    d2 = (math.log(stock_price / breakeven) + (0.05 - 0.5 * iv**2) * T) / (iv * math.sqrt(T))
    pop = norm_cdf(d2) * 100
    
    return round(pop, 1)


# ──────────────────────────────────────────────────────────────
# PREMIUM ANALYSIS
# ──────────────────────────────────────────────────────────────

def annualized_return(premium: float, collateral: float, dte: int) -> float:
    """
    Calculate the annualized return on capital for a premium selling trade.
    
    Formula: (premium / collateral) × (365 / DTE) × 100
    
    Example: $2.00 premium on $50 stock (CSP), 30 DTE
    → (2/50) × (365/30) × 100 = 48.7% annualized
    """
    if collateral <= 0 or dte <= 0:
        return 0.0
    
    return round((premium / collateral) * (365 / dte) * 100, 2)


def risk_reward_ratio(max_profit: float, max_loss: float) -> float:
    """Calculate risk/reward ratio. Lower is better for defined-risk trades."""
    if max_profit <= 0:
        return float('inf')
    return round(max_loss / max_profit, 2)
