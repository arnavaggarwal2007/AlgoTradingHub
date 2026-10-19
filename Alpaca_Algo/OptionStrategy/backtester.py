"""
================================================================================
BACKTESTING ENGINE — Historical Strategy Performance Validation
================================================================================

Simulates all 4 options strategies against 1 year of real SPY/VIX/QQQ/IWM
historical data to measure:
- Total P&L and annualized return
- Win rate and average trade P&L
- Max drawdown
- Sharpe ratio
- Performance across market regimes (uptrend, downtrend, sideways, choppy)
- Comparison between strategies

Uses yfinance for historical OHLCV data and simulates option premium
collection using Black-Scholes pricing given historical IV levels.

Usage:
    python backtester.py                  # Run all strategies
    python backtester.py --strategy wheel # Run specific strategy
    python backtester.py --output results # Save results to folder

================================================================================
"""

import os
import sys
import json
import math
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.option_utils import (
    black_scholes_greeks,
    norm_cdf,
    calculate_iv_rank,
)
from ladder_exit import LadderExitManager

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Market Regime Classification (for analysis)
# ──────────────────────────────────────────────────────────────

def classify_market_conditions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each day's market condition into one of four regimes
    based on SPY price action and VIX.

    Regimes:
        'uptrend'   — SPY above 20-day MA AND 20-day MA rising
        'downtrend' — SPY below 20-day MA AND 20-day MA falling
        'sideways'  — SPY within 2% of 20-day MA, low ATR
        'choppy'    — high daily range relative to ATR, frequent crossovers
    """
    df = df.copy()
    df['ma20'] = df['spy_close'].rolling(20).mean()
    df['ma20_slope'] = df['ma20'].pct_change(5)
    df['atr_14'] = _calculate_atr(df, 14)
    df['atr_pct'] = df['atr_14'] / df['spy_close']
    df['dist_from_ma'] = (df['spy_close'] - df['ma20']) / df['ma20']

    # Count directional change in last 10 days
    daily_dir = np.sign(df['spy_close'].pct_change())
    df['direction_changes'] = daily_dir.rolling(10).apply(
        lambda x: (np.diff(x) != 0).sum(), raw=True
    )

    conditions = []
    for _, row in df.iterrows():
        if pd.isna(row.get('ma20')) or pd.isna(row.get('atr_pct')):
            conditions.append('unknown')
            continue

        dist = row['dist_from_ma']
        slope = row['ma20_slope']
        chg = row.get('direction_changes', 5)

        if chg >= 7 and row['atr_pct'] > 0.012:
            conditions.append('choppy')
        elif abs(dist) < 0.02 and abs(slope) < 0.005:
            conditions.append('sideways')
        elif dist > 0 and slope > 0:
            conditions.append('uptrend')
        elif dist < 0 and slope < 0:
            conditions.append('downtrend')
        elif dist > 0.03:
            conditions.append('uptrend')
        elif dist < -0.03:
            conditions.append('downtrend')
        else:
            conditions.append('sideways')

    df['market_condition'] = conditions
    return df


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df['spy_high'] - df['spy_low']
    hc = (df['spy_high'] - df['spy_close'].shift(1)).abs()
    lc = (df['spy_low'] - df['spy_close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ──────────────────────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────────────────────

def load_historical_data(
    symbols: List[str] = None,
    start: str = None,
    end: str = None,
) -> pd.DataFrame:
    """Load historical OHLCV + VIX data."""
    symbols = symbols or ['SPY']
    if end is None:
        end = datetime.now().strftime('%Y-%m-%d')
    if start is None:
        start = (datetime.now() - timedelta(days=370)).strftime('%Y-%m-%d')

    logger.info(f"Loading data: {symbols} from {start} to {end}")

    # VIX for IV proxy
    vix = yf.download('^VIX', start=start, end=end, progress=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)

    all_data = {}
    for sym in symbols:
        raw = yf.download(sym, start=start, end=end, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        if raw.empty:
            logger.warning(f"No data for {sym}")
            continue

        df = pd.DataFrame(index=raw.index)
        df['spy_close'] = raw['Close']
        df['spy_high'] = raw['High']
        df['spy_low'] = raw['Low']
        df['spy_open'] = raw['Open']
        df['volume'] = raw['Volume']
        df['vix_close'] = vix['Close'].reindex(raw.index)
        df.dropna(inplace=True)
        df['symbol'] = sym
        all_data[sym] = df

    return all_data


# ──────────────────────────────────────────────────────────────
# Trade Simulation Helpers
# ──────────────────────────────────────────────────────────────

def simulate_put_premium(
    spot: float, strike: float, dte: int, vix: float, r: float = 0.05
) -> float:
    """Estimate put option premium using Black-Scholes with VIX as IV proxy."""
    iv = vix / 100.0
    T = dte / 365.0
    if T <= 0 or iv <= 0:
        return 0.0
    g = black_scholes_greeks(spot, strike, T, r, iv, 'put')
    return max(g['price'], 0.01)


def simulate_call_premium(
    spot: float, strike: float, dte: int, vix: float, r: float = 0.05
) -> float:
    iv = vix / 100.0
    T = dte / 365.0
    if T <= 0 or iv <= 0:
        return 0.0
    g = black_scholes_greeks(spot, strike, T, r, iv, 'call')
    return max(g['price'], 0.01)


# ──────────────────────────────────────────────────────────────
# Strategy 1 Backtest: The Wheel (CSP)
# ──────────────────────────────────────────────────────────────

def backtest_wheel(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    target_delta: float = 0.15,
    dte: int = 35,
    profit_target: float = 0.50,
    stop_loss_mult: float = 3.0,
    max_risk_pct: float = 0.05,
) -> Dict:
    """Backtest the Wheel strategy (sell CSPs)."""
    trades = []
    equity_curve = []
    capital = initial_capital
    open_trades = []

    for i in range(len(df)):
        row = df.iloc[i]
        date = df.index[i]
        spot = row['spy_close']
        vix = row['vix_close']

        # Monitor open trades
        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining_dte = t['dte'] - days_held

            # Simulate current put price
            current_premium = simulate_put_premium(spot, t['strike'], max(remaining_dte, 1), vix)

            pnl_pct = (t['entry_premium'] - current_premium) / t['entry_premium'] if t['entry_premium'] > 0 else 0

            # Assignment check — stock below strike at expiry
            if remaining_dte <= 0:
                if spot < t['strike']:
                    # Assigned — loss = (strike - spot) * 100, keep premium
                    pnl = (t['entry_premium'] - (t['strike'] - spot)) * 100
                else:
                    # Expired OTM — keep full premium
                    pnl = t['entry_premium'] * 100

                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            # Profit target
            if pnl_pct >= profit_target:
                cost_to_close = current_premium * 100
                pnl = (t['entry_premium'] * 100) - cost_to_close
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'profit_target'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            # Stop loss
            if current_premium >= t['entry_premium'] * stop_loss_mult:
                cost_to_close = current_premium * 100
                pnl = (t['entry_premium'] * 100) - cost_to_close
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'stop_loss'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            new_open.append(t)

        open_trades = new_open

        # New entry: every 7 days if capital available and no open trade
        if i % 7 == 0 and len(open_trades) < 3:
            # Target strike at delta ~0.15 (roughly 5-8% OTM for 30-45 DTE)
            otm_pct = target_delta * 0.5  # Approximate
            strike = round(spot * (1 - otm_pct), 0)
            premium = simulate_put_premium(spot, strike, dte, vix)

            collateral = strike * 100
            max_risk = capital * max_risk_pct

            if premium > 0.10 and collateral <= capital and premium * 3 * 100 <= max_risk:
                capital -= collateral
                open_trades.append({
                    'entry_date': date,
                    'symbol': 'SPY',
                    'strike': strike,
                    'dte': dte,
                    'entry_premium': premium,
                    'entry_spot': spot,
                    'entry_vix': vix,
                    'collateral': collateral,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        # Track equity
        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({
            'date': date,
            'equity': capital + unrealised,
            'cash': capital,
            'open_positions': len(open_trades),
        })

    # Close any remaining
    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['entry_premium'] * 50  # Assume half premium captured
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)

    return _compile_results('Wheel (CSP)', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 2 Backtest: SPX Bull Put Spreads
# ──────────────────────────────────────────────────────────────

def backtest_spx_spreads(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    target_delta: float = 0.12,
    spread_width: float = 50,
    dte: int = 35,
    profit_target: float = 0.50,
    stop_loss_mult: float = 3.0,
    max_risk_pct: float = 0.05,
    entry_days: List[int] = None,  # 0=Mon, 2=Wed, 4=Fri
) -> Dict:
    """Backtest mechanical SPX bull put spreads."""
    entry_days = entry_days or [0, 2, 4]
    trades = []
    equity_curve = []
    capital = initial_capital
    open_trades = []

    for i in range(len(df)):
        row = df.iloc[i]
        date = df.index[i]
        spot = row['spy_close']
        vix = row['vix_close']

        # Monitor open trades
        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining_dte = t['dte'] - days_held

            short_premium = simulate_put_premium(spot, t['short_strike'], max(remaining_dte, 1), vix)
            long_premium = simulate_put_premium(spot, t['long_strike'], max(remaining_dte, 1), vix)
            current_spread_cost = short_premium - long_premium

            entry_credit = t['entry_credit']
            pnl_pct = (entry_credit - current_spread_cost) / entry_credit if entry_credit > 0 else 0

            if remaining_dte <= 0:
                if spot < t['short_strike']:
                    # Max loss
                    pnl = -(t['max_loss_per'])
                elif spot < t['long_strike']:
                    pnl = -(t['short_strike'] - spot) * 100 + entry_credit * 100
                else:
                    pnl = entry_credit * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if pnl_pct >= profit_target:
                pnl = (entry_credit - current_spread_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'profit_target'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if current_spread_cost >= entry_credit * stop_loss_mult:
                pnl = (entry_credit - current_spread_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'stop_loss'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            new_open.append(t)

        open_trades = new_open

        # New entry on MWF
        if hasattr(date, 'weekday'):
            day_of_week = date.weekday()
        else:
            day_of_week = pd.Timestamp(date).weekday()

        if day_of_week in entry_days and len(open_trades) < 6:
            if vix > 40:
                continue  # Pause during extreme volatility
            if vix < 12:
                continue  # Premiums too thin

            otm_pct = target_delta * 0.5
            short_strike = round(spot * (1 - otm_pct), 0)
            long_strike = short_strike - spread_width

            short_p = simulate_put_premium(spot, short_strike, dte, vix)
            long_p = simulate_put_premium(spot, long_strike, dte, vix)
            credit = short_p - long_p

            max_loss = (spread_width - credit) * 100
            collateral = max_loss

            if credit > 0.20 and collateral <= capital * max_risk_pct:
                capital -= collateral
                open_trades.append({
                    'entry_date': date,
                    'symbol': 'SPY',
                    'short_strike': short_strike,
                    'long_strike': long_strike,
                    'dte': dte,
                    'entry_credit': credit,
                    'entry_spot': spot,
                    'entry_vix': vix,
                    'collateral': collateral,
                    'max_loss_per': max_loss,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({
            'date': date,
            'equity': capital + unrealised,
            'cash': capital,
            'open_positions': len(open_trades),
        })

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['entry_credit'] * 50
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)

    return _compile_results('SPX Bull Put Spreads', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 3 Backtest: Iron Condors
# ──────────────────────────────────────────────────────────────

def backtest_iron_condors(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    put_delta: float = 0.12,
    call_delta: float = 0.12,
    wing_width: float = 5,
    dte: int = 35,
    profit_target: float = 0.50,
    stop_loss_mult: float = 2.0,
    max_risk_pct: float = 0.05,
) -> Dict:
    """Backtest iron condor strategy."""
    trades = []
    equity_curve = []
    capital = initial_capital
    open_trades = []

    for i in range(len(df)):
        row = df.iloc[i]
        date = df.index[i]
        spot = row['spy_close']
        vix = row['vix_close']

        # Monitor
        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining = t['dte'] - days_held

            # Current condor value
            put_short_p = simulate_put_premium(spot, t['put_short'], max(remaining, 1), vix)
            put_long_p = simulate_put_premium(spot, t['put_long'], max(remaining, 1), vix)
            call_short_p = simulate_call_premium(spot, t['call_short'], max(remaining, 1), vix)
            call_long_p = simulate_call_premium(spot, t['call_long'], max(remaining, 1), vix)

            current_cost = (put_short_p - put_long_p) + (call_short_p - call_long_p)
            entry_credit = t['total_credit']
            pnl_pct = (entry_credit - current_cost) / entry_credit if entry_credit > 0 else 0

            if remaining <= 0:
                # Check if spot in range
                if t['put_short'] <= spot <= t['call_short']:
                    pnl = entry_credit * 100
                elif spot < t['put_long']:
                    pnl = -(wing_width * 100) + entry_credit * 100
                elif spot > t['call_long']:
                    pnl = -(wing_width * 100) + entry_credit * 100
                else:
                    # Partial loss
                    if spot < t['put_short']:
                        pnl = -((t['put_short'] - spot) * 100) + entry_credit * 100
                    else:
                        pnl = -((spot - t['call_short']) * 100) + entry_credit * 100

                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if pnl_pct >= profit_target:
                pnl = (entry_credit - current_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'profit_target'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if current_cost >= entry_credit * stop_loss_mult:
                pnl = (entry_credit - current_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'stop_loss'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            new_open.append(t)

        open_trades = new_open

        # Entry every 10 days
        if i % 10 == 0 and len(open_trades) < 5:
            if vix < 12 or vix > 35:
                continue

            put_otm = put_delta * 0.5
            call_otm = call_delta * 0.5

            put_short = round(spot * (1 - put_otm), 0)
            put_long = put_short - wing_width
            call_short = round(spot * (1 + call_otm), 0)
            call_long = call_short + wing_width

            ps_p = simulate_put_premium(spot, put_short, dte, vix)
            pl_p = simulate_put_premium(spot, put_long, dte, vix)
            cs_p = simulate_call_premium(spot, call_short, dte, vix)
            cl_p = simulate_call_premium(spot, call_long, dte, vix)

            total_credit = (ps_p - pl_p) + (cs_p - cl_p)

            # 1/3 rule
            if total_credit < wing_width / 3:
                continue

            max_loss = (wing_width - total_credit) * 100
            collateral = max_loss

            if collateral <= capital * max_risk_pct and total_credit > 0.30:
                capital -= collateral
                open_trades.append({
                    'entry_date': date,
                    'symbol': 'SPY',
                    'put_short': put_short,
                    'put_long': put_long,
                    'call_short': call_short,
                    'call_long': call_long,
                    'dte': dte,
                    'total_credit': total_credit,
                    'entry_spot': spot,
                    'entry_vix': vix,
                    'collateral': collateral,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({
            'date': date,
            'equity': capital + unrealised,
            'cash': capital,
            'open_positions': len(open_trades),
        })

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['total_credit'] * 50
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)

    return _compile_results('Iron Condors', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 4 Backtest: VIX-Regime Adaptive
# ──────────────────────────────────────────────────────────────

def backtest_regime_adaptive(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    max_risk_pct: float = 0.05,
) -> Dict:
    """Backtest regime-adaptive credit spreads."""
    trades = []
    equity_curve = []
    capital = initial_capital
    open_trades = []

    # Pre-compute regime features
    df = df.copy()
    df['vix_ma20'] = df['vix_close'].rolling(20).mean()
    vix_high5 = df['vix_close'].rolling(5).max()
    df['vix_pct_from_high5'] = (df['vix_close'] - vix_high5) / vix_high5

    regime_params = {
        'low_vol':  {'delta': 0.08, 'width': 3, 'dte': 30, 'mult': 0.25, 'pt': 0.40, 'enabled': False},
        'normal':   {'delta': 0.12, 'width': 5, 'dte': 35, 'mult': 1.0, 'pt': 0.50, 'enabled': True},
        'high_vol': {'delta': 0.15, 'width': 10, 'dte': 50, 'mult': 1.5, 'pt': 0.60, 'enabled': True},
        'crash':    {'delta': 0, 'width': 0, 'dte': 0, 'mult': 0, 'pt': 0, 'enabled': False},
    }

    for i in range(20, len(df)):
        row = df.iloc[i]
        date = df.index[i]
        spot = row['spy_close']
        vix = row['vix_close']
        vix_ma = row.get('vix_ma20', vix)
        vix_from_high = row.get('vix_pct_from_high5', 0)

        # Classify regime
        if vix < 15:
            regime = 'low_vol'
        elif vix < 22:
            regime = 'normal'
        elif vix < 35:
            regime = 'high_vol'
        else:
            regime = 'crash'

        params = regime_params[regime]

        # Monitor
        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining = t['dte'] - days_held

            short_p = simulate_put_premium(spot, t['short_strike'], max(remaining, 1), vix)
            long_p = simulate_put_premium(spot, t['long_strike'], max(remaining, 1), vix)
            current_cost = short_p - long_p

            entry_credit = t['entry_credit']
            pnl_pct = (entry_credit - current_cost) / entry_credit if entry_credit > 0 else 0

            # Crash regime override: close everything
            if regime == 'crash':
                pnl = (entry_credit - current_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'crash_exit'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if remaining <= 0:
                if spot >= t['short_strike']:
                    pnl = entry_credit * 100
                else:
                    pnl = max(-(t['max_loss']), (entry_credit - (t['short_strike'] - spot)) * 100)
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if pnl_pct >= params['pt']:
                pnl = (entry_credit - current_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'profit_target'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            if current_cost >= entry_credit * 2.0:
                pnl = (entry_credit - current_cost) * 100
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'stop_loss'
                capital += pnl + t['collateral']
                trades.append(t)
                continue

            new_open.append(t)

        open_trades = new_open

        # Entry logic
        if not params['enabled']:
            unrealised = sum(t['collateral'] for t in open_trades)
            equity_curve.append({'date': date, 'equity': capital + unrealised, 'cash': capital, 'open_positions': len(open_trades)})
            continue

        # High vol: require mean reversion
        if regime == 'high_vol':
            if not (pd.notna(vix_from_high) and vix_from_high < -0.10 and vix > vix_ma):
                unrealised = sum(t['collateral'] for t in open_trades)
                equity_curve.append({'date': date, 'equity': capital + unrealised, 'cash': capital, 'open_positions': len(open_trades)})
                continue

        if i % 7 == 0 and len(open_trades) < 8:
            delta = params['delta']
            width = params['width']
            entry_dte = params['dte']
            size_mult = params['mult']

            otm_pct = delta * 0.5
            short_strike = round(spot * (1 - otm_pct), 0)
            long_strike = short_strike - width

            short_p = simulate_put_premium(spot, short_strike, entry_dte, vix)
            long_p = simulate_put_premium(spot, long_strike, entry_dte, vix)
            credit = short_p - long_p

            max_loss = (width - credit) * 100
            collateral = max_loss
            adjusted_risk = capital * max_risk_pct * size_mult

            if credit > 0.15 and collateral <= adjusted_risk and collateral > 0:
                capital -= collateral
                open_trades.append({
                    'entry_date': date,
                    'symbol': 'SPY',
                    'short_strike': short_strike,
                    'long_strike': long_strike,
                    'dte': entry_dte,
                    'entry_credit': credit,
                    'entry_spot': spot,
                    'entry_vix': vix,
                    'collateral': collateral,
                    'max_loss': max_loss,
                    'regime': regime,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({
            'date': date,
            'equity': capital + unrealised,
            'cash': capital,
            'open_positions': len(open_trades),
        })

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['entry_credit'] * 50
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)

    return _compile_results('VIX-Regime Adaptive', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 1b Backtest: Wheel (CSP) WITH Ladder Exits
# ──────────────────────────────────────────────────────────────

def backtest_wheel_ladder(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    target_delta: float = 0.15,
    dte: int = 35,
    max_risk_pct: float = 0.05,
    contracts_per_trade: int = 1,
) -> Dict:
    """Backtest Wheel strategy with ladder exit instead of fixed profit target."""
    import tempfile
    state_file = os.path.join(tempfile.gettempdir(), 'bt_wheel_ladder.json')
    if os.path.exists(state_file):
        os.remove(state_file)
    ladder = LadderExitManager(state_file=state_file)

    trades, equity_curve = [], []
    capital = initial_capital
    open_trades = []
    trade_counter = 0

    for i in range(len(df)):
        row = df.iloc[i]
        date, spot, vix = df.index[i], row['spy_close'], row['vix_close']

        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining_dte = t['dte'] - days_held
            pos_key = t['pos_key']
            current_premium = simulate_put_premium(spot, t['strike'], max(remaining_dte, 1), vix)

            if remaining_dte <= 0:
                if spot < t['strike']:
                    pnl = (t['entry_premium'] - (t['strike'] - spot)) * 100 * t['remaining_qty']
                else:
                    pnl = t['entry_premium'] * 100 * t['remaining_qty']
                t['exit_date'], t['pnl'], t['exit_reason'] = date, pnl, 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue

            result = ladder.check_exit(pos_key, current_premium, remaining_dte=remaining_dte)

            if result['action'] in ('stop_loss', 'sell_all'):
                qty = result['contracts_to_sell']
                pnl = (t['entry_premium'] - current_premium) * 100 * qty
                t['exit_date'], t['pnl'] = date, pnl
                t['exit_reason'] = f"ladder_{result['tier']}"
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue
            elif result['action'] == 'sell_partial':
                qty = result['contracts_to_sell']
                partial_pnl = (t['entry_premium'] - current_premium) * 100 * qty
                t['remaining_qty'] -= qty
                freed = qty * t['per_contract_collateral']
                t['collateral'] -= freed
                capital += partial_pnl + freed
                trades.append({
                    'entry_date': t['entry_date'], 'exit_date': date,
                    'symbol': 'SPY', 'pnl': partial_pnl,
                    'exit_reason': f"ladder_{result['tier']}",
                    'market_condition': t.get('market_condition', 'unknown'),
                })
                ladder.confirm_sell(pos_key, qty, current_premium)
                if t['remaining_qty'] <= 0:
                    capital += t['collateral']
                    ladder.remove_position(pos_key)
                    continue

            new_open.append(t)
        open_trades = new_open

        if i % 7 == 0 and len(open_trades) < 3:
            otm_pct = target_delta * 0.5
            strike = round(spot * (1 - otm_pct), 0)
            premium = simulate_put_premium(spot, strike, dte, vix)
            per_collateral = strike * 100
            total_collateral = per_collateral * contracts_per_trade
            max_risk = capital * max_risk_pct

            if premium > 0.10 and total_collateral <= capital and premium * 3 * 100 * contracts_per_trade <= max_risk:
                trade_counter += 1
                pos_key = f"bt_wheel_{trade_counter}"
                capital -= total_collateral
                ladder.register_position(pos_key, premium, contracts_per_trade, side='short')
                open_trades.append({
                    'entry_date': date, 'symbol': 'SPY', 'strike': strike,
                    'dte': dte, 'entry_premium': premium, 'entry_spot': spot,
                    'entry_vix': vix, 'collateral': total_collateral,
                    'per_contract_collateral': per_collateral,
                    'pos_key': pos_key, 'remaining_qty': contracts_per_trade,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({'date': date, 'equity': capital + unrealised,
                            'cash': capital, 'open_positions': len(open_trades)})

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['entry_premium'] * 50 * t['remaining_qty']
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)
        ladder.remove_position(t['pos_key'])

    if os.path.exists(state_file):
        os.remove(state_file)
    return _compile_results('Wheel + Ladder', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 2b Backtest: SPX Bull Put Spreads WITH Ladder Exits
# ──────────────────────────────────────────────────────────────

def backtest_spx_spreads_ladder(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    target_delta: float = 0.12,
    spread_width: float = 50,
    dte: int = 35,
    max_risk_pct: float = 0.05,
    entry_days: List[int] = None,
    contracts_per_trade: int = 1,
) -> Dict:
    """Backtest SPX bull put spreads with ladder exit management."""
    entry_days = entry_days or [0, 2, 4]
    import tempfile
    state_file = os.path.join(tempfile.gettempdir(), 'bt_spx_ladder.json')
    if os.path.exists(state_file):
        os.remove(state_file)
    ladder = LadderExitManager(state_file=state_file)

    trades, equity_curve = [], []
    capital = initial_capital
    open_trades = []
    trade_counter = 0

    for i in range(len(df)):
        row = df.iloc[i]
        date, spot, vix = df.index[i], row['spy_close'], row['vix_close']

        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining_dte = t['dte'] - days_held
            pos_key = t['pos_key']

            short_p = simulate_put_premium(spot, t['short_strike'], max(remaining_dte, 1), vix)
            long_p = simulate_put_premium(spot, t['long_strike'], max(remaining_dte, 1), vix)
            current_cost = short_p - long_p
            entry_credit = t['entry_credit']

            if remaining_dte <= 0:
                if spot < t['short_strike']:
                    pnl = -(t['max_loss_per']) * t['remaining_qty']
                elif spot < t['long_strike']:
                    pnl = (-(t['short_strike'] - spot) * 100 + entry_credit * 100) * t['remaining_qty']
                else:
                    pnl = entry_credit * 100 * t['remaining_qty']
                t['exit_date'], t['pnl'], t['exit_reason'] = date, pnl, 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue

            result = ladder.check_exit(pos_key, current_cost, remaining_dte=remaining_dte)

            if result['action'] in ('stop_loss', 'sell_all'):
                qty = result['contracts_to_sell']
                pnl = (entry_credit - current_cost) * 100 * qty
                t['exit_date'], t['pnl'] = date, pnl
                t['exit_reason'] = f"ladder_{result['tier']}"
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue
            elif result['action'] == 'sell_partial':
                qty = result['contracts_to_sell']
                partial_pnl = (entry_credit - current_cost) * 100 * qty
                t['remaining_qty'] -= qty
                freed = qty * t['per_contract_collateral']
                t['collateral'] -= freed
                capital += partial_pnl + freed
                trades.append({
                    'entry_date': t['entry_date'], 'exit_date': date,
                    'symbol': 'SPY', 'pnl': partial_pnl,
                    'exit_reason': f"ladder_{result['tier']}",
                    'market_condition': t.get('market_condition', 'unknown'),
                })
                ladder.confirm_sell(pos_key, qty, current_cost)
                if t['remaining_qty'] <= 0:
                    capital += t['collateral']
                    ladder.remove_position(pos_key)
                    continue

            new_open.append(t)
        open_trades = new_open

        if hasattr(date, 'weekday'):
            day_of_week = date.weekday()
        else:
            day_of_week = pd.Timestamp(date).weekday()

        if day_of_week in entry_days and len(open_trades) < 6:
            if vix > 40 or vix < 12:
                unrealised = sum(t['collateral'] for t in open_trades)
                equity_curve.append({'date': date, 'equity': capital + unrealised,
                                    'cash': capital, 'open_positions': len(open_trades)})
                continue

            otm_pct = target_delta * 0.5
            short_strike = round(spot * (1 - otm_pct), 0)
            long_strike = short_strike - spread_width

            short_p = simulate_put_premium(spot, short_strike, dte, vix)
            long_p = simulate_put_premium(spot, long_strike, dte, vix)
            credit = short_p - long_p

            per_max_loss = (spread_width - credit) * 100
            per_collateral = per_max_loss
            total_collateral = per_collateral * contracts_per_trade

            if credit > 0.20 and total_collateral <= capital * max_risk_pct:
                trade_counter += 1
                pos_key = f"bt_spx_{trade_counter}"
                capital -= total_collateral
                ladder.register_position(pos_key, credit, contracts_per_trade, side='short')
                open_trades.append({
                    'entry_date': date, 'symbol': 'SPY',
                    'short_strike': short_strike, 'long_strike': long_strike,
                    'dte': dte, 'entry_credit': credit, 'entry_spot': spot,
                    'entry_vix': vix, 'collateral': total_collateral,
                    'per_contract_collateral': per_collateral,
                    'max_loss_per': per_max_loss,
                    'pos_key': pos_key, 'remaining_qty': contracts_per_trade,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({'date': date, 'equity': capital + unrealised,
                            'cash': capital, 'open_positions': len(open_trades)})

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['entry_credit'] * 50 * t['remaining_qty']
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)
        ladder.remove_position(t['pos_key'])

    if os.path.exists(state_file):
        os.remove(state_file)
    return _compile_results('SPX Spreads + Ladder', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 3b Backtest: Iron Condors WITH Ladder Exits
# ──────────────────────────────────────────────────────────────

def backtest_iron_condors_ladder(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    put_delta: float = 0.12,
    call_delta: float = 0.12,
    wing_width: float = 5,
    dte: int = 35,
    max_risk_pct: float = 0.05,
    contracts_per_trade: int = 3,
) -> Dict:
    """Backtest iron condors with ladder exit management."""
    import tempfile
    state_file = os.path.join(tempfile.gettempdir(), 'bt_ic_ladder.json')
    if os.path.exists(state_file):
        os.remove(state_file)
    ladder = LadderExitManager(state_file=state_file)

    trades, equity_curve = [], []
    capital = initial_capital
    open_trades = []
    trade_counter = 0

    for i in range(len(df)):
        row = df.iloc[i]
        date, spot, vix = df.index[i], row['spy_close'], row['vix_close']

        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining_dte = t['dte'] - days_held
            pos_key = t['pos_key']

            put_short_p = simulate_put_premium(spot, t['put_short'], max(remaining_dte, 1), vix)
            put_long_p = simulate_put_premium(spot, t['put_long'], max(remaining_dte, 1), vix)
            call_short_p = simulate_call_premium(spot, t['call_short'], max(remaining_dte, 1), vix)
            call_long_p = simulate_call_premium(spot, t['call_long'], max(remaining_dte, 1), vix)
            current_cost = (put_short_p - put_long_p) + (call_short_p - call_long_p)
            entry_credit = t['total_credit']

            if remaining_dte <= 0:
                if t['put_short'] <= spot <= t['call_short']:
                    pnl = entry_credit * 100 * t['remaining_qty']
                elif spot < t['put_long']:
                    pnl = (-(wing_width * 100) + entry_credit * 100) * t['remaining_qty']
                elif spot > t['call_long']:
                    pnl = (-(wing_width * 100) + entry_credit * 100) * t['remaining_qty']
                elif spot < t['put_short']:
                    pnl = (-((t['put_short'] - spot) * 100) + entry_credit * 100) * t['remaining_qty']
                else:
                    pnl = (-((spot - t['call_short']) * 100) + entry_credit * 100) * t['remaining_qty']
                t['exit_date'], t['pnl'], t['exit_reason'] = date, pnl, 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue

            result = ladder.check_exit(pos_key, current_cost, remaining_dte=remaining_dte)

            if result['action'] in ('stop_loss', 'sell_all'):
                qty = result['contracts_to_sell']
                pnl = (entry_credit - current_cost) * 100 * qty
                t['exit_date'], t['pnl'] = date, pnl
                t['exit_reason'] = f"ladder_{result['tier']}"
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue
            elif result['action'] == 'sell_partial':
                qty = result['contracts_to_sell']
                partial_pnl = (entry_credit - current_cost) * 100 * qty
                t['remaining_qty'] -= qty
                freed = qty * t['per_contract_collateral']
                t['collateral'] -= freed
                capital += partial_pnl + freed
                trades.append({
                    'entry_date': t['entry_date'], 'exit_date': date,
                    'symbol': 'SPY', 'pnl': partial_pnl,
                    'exit_reason': f"ladder_{result['tier']}",
                    'market_condition': t.get('market_condition', 'unknown'),
                })
                ladder.confirm_sell(pos_key, qty, current_cost)
                if t['remaining_qty'] <= 0:
                    capital += t['collateral']
                    ladder.remove_position(pos_key)
                    continue

            new_open.append(t)
        open_trades = new_open

        if i % 10 == 0 and len(open_trades) < 5:
            if vix < 12 or vix > 35:
                unrealised = sum(t['collateral'] for t in open_trades)
                equity_curve.append({'date': date, 'equity': capital + unrealised,
                                    'cash': capital, 'open_positions': len(open_trades)})
                continue

            put_otm = put_delta * 0.5
            call_otm = call_delta * 0.5
            put_short = round(spot * (1 - put_otm), 0)
            put_long = put_short - wing_width
            call_short = round(spot * (1 + call_otm), 0)
            call_long = call_short + wing_width

            ps_p = simulate_put_premium(spot, put_short, dte, vix)
            pl_p = simulate_put_premium(spot, put_long, dte, vix)
            cs_p = simulate_call_premium(spot, call_short, dte, vix)
            cl_p = simulate_call_premium(spot, call_long, dte, vix)
            total_credit = (ps_p - pl_p) + (cs_p - cl_p)

            if total_credit < wing_width / 3:
                unrealised = sum(t['collateral'] for t in open_trades)
                equity_curve.append({'date': date, 'equity': capital + unrealised,
                                    'cash': capital, 'open_positions': len(open_trades)})
                continue

            per_max_loss = (wing_width - total_credit) * 100
            per_collateral = per_max_loss
            total_collateral = per_collateral * contracts_per_trade

            if total_collateral <= capital * max_risk_pct and total_credit > 0.30:
                trade_counter += 1
                pos_key = f"bt_ic_{trade_counter}"
                capital -= total_collateral
                ladder.register_position(pos_key, total_credit, contracts_per_trade, side='short')
                open_trades.append({
                    'entry_date': date, 'symbol': 'SPY',
                    'put_short': put_short, 'put_long': put_long,
                    'call_short': call_short, 'call_long': call_long,
                    'dte': dte, 'total_credit': total_credit,
                    'entry_spot': spot, 'entry_vix': vix,
                    'collateral': total_collateral,
                    'per_contract_collateral': per_collateral,
                    'pos_key': pos_key, 'remaining_qty': contracts_per_trade,
                    'market_condition': row.get('market_condition', 'unknown'),
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({'date': date, 'equity': capital + unrealised,
                            'cash': capital, 'open_positions': len(open_trades)})

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['total_credit'] * 50 * t['remaining_qty']
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)
        ladder.remove_position(t['pos_key'])

    if os.path.exists(state_file):
        os.remove(state_file)
    return _compile_results('Iron Condors + Ladder', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Strategy 4b Backtest: VIX-Regime Adaptive WITH Ladder Exits
# ──────────────────────────────────────────────────────────────

def backtest_regime_adaptive_ladder(
    df: pd.DataFrame,
    initial_capital: float = 50000,
    max_risk_pct: float = 0.05,
    contracts_per_trade: int = 4,
) -> Dict:
    """
    Backtest regime-adaptive credit spreads WITH ladder exit management.

    Uses the LadderExitManager for tiered profit-taking:
      -17% hard stop → -3% SL at +5% → sell 25% at +10% → sell 25% at +15%
      → trailing stop on remaining 50%.
    """
    import tempfile
    state_file = os.path.join(tempfile.gettempdir(), 'backtest_ladder_state.json')
    # Start fresh
    if os.path.exists(state_file):
        os.remove(state_file)
    ladder = LadderExitManager(state_file=state_file)

    trades = []
    equity_curve = []
    capital = initial_capital
    open_trades = []
    trade_counter = 0

    df = df.copy()
    df['vix_ma20'] = df['vix_close'].rolling(20).mean()
    vix_high5 = df['vix_close'].rolling(5).max()
    df['vix_pct_from_high5'] = (df['vix_close'] - vix_high5) / vix_high5

    regime_params = {
        'low_vol':  {'delta': 0.08, 'width': 3, 'dte': 30, 'mult': 0.25, 'pt': 0.40, 'enabled': False},
        'normal':   {'delta': 0.12, 'width': 5, 'dte': 35, 'mult': 1.0, 'pt': 0.50, 'enabled': True},
        'high_vol': {'delta': 0.15, 'width': 10, 'dte': 50, 'mult': 1.5, 'pt': 0.60, 'enabled': True},
        'crash':    {'delta': 0, 'width': 0, 'dte': 0, 'mult': 0, 'pt': 0, 'enabled': False},
    }

    for i in range(20, len(df)):
        row = df.iloc[i]
        date = df.index[i]
        spot = row['spy_close']
        vix = row['vix_close']
        vix_ma = row.get('vix_ma20', vix)
        vix_from_high = row.get('vix_pct_from_high5', 0)

        if vix < 15:
            regime = 'low_vol'
        elif vix < 22:
            regime = 'normal'
        elif vix < 35:
            regime = 'high_vol'
        else:
            regime = 'crash'

        params = regime_params[regime]

        # Monitor open trades with ladder
        new_open = []
        for t in open_trades:
            days_held = (date - t['entry_date']).days
            remaining = t['dte'] - days_held
            pos_key = t['pos_key']

            short_p = simulate_put_premium(spot, t['short_strike'], max(remaining, 1), vix)
            long_p = simulate_put_premium(spot, t['long_strike'], max(remaining, 1), vix)
            current_cost = short_p - long_p
            entry_credit = t['entry_credit']

            # Crash override
            if regime == 'crash':
                pnl = (entry_credit - current_cost) * 100 * t['remaining_qty']
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'crash_exit'
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue

            # Expiration
            if remaining <= 0:
                if spot >= t['short_strike']:
                    pnl = entry_credit * 100 * t['remaining_qty']
                else:
                    pnl = max(-(t['max_loss']), (entry_credit - (t['short_strike'] - spot)) * 100) * t['remaining_qty']
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = 'expiration'
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue

            # Ladder check
            result = ladder.check_exit(pos_key, current_cost, remaining_dte=remaining)

            if result['action'] == 'stop_loss':
                qty = result['contracts_to_sell']
                pnl = (entry_credit - current_cost) * 100 * qty
                t['exit_date'] = date
                t['pnl'] = pnl
                t['exit_reason'] = f"ladder_stop_{result['tier']}"
                capital += pnl + t['collateral']
                trades.append(t)
                ladder.remove_position(pos_key)
                continue

            elif result['action'] in ('sell_partial', 'sell_all'):
                qty = result['contracts_to_sell']
                partial_pnl = (entry_credit - current_cost) * 100 * qty
                t['remaining_qty'] -= qty
                capital += partial_pnl
                # Record partial as a sub-trade
                trades.append({
                    'entry_date': t['entry_date'],
                    'exit_date': date,
                    'symbol': t['symbol'],
                    'short_strike': t['short_strike'],
                    'long_strike': t['long_strike'],
                    'entry_credit': entry_credit,
                    'pnl': partial_pnl,
                    'exit_reason': f"ladder_{result['tier']}",
                    'market_condition': t.get('market_condition', 'unknown'),
                    'regime': t.get('regime', 'unknown'),
                    'entry_spot': t['entry_spot'],
                    'entry_vix': t['entry_vix'],
                })
                ladder.confirm_sell(pos_key, qty, current_cost)

                if t['remaining_qty'] <= 0:
                    capital += t['collateral']
                    ladder.remove_position(pos_key)
                    continue

            # Still open
            new_open.append(t)

        open_trades = new_open

        # Entry logic
        if not params['enabled']:
            unrealised = sum(t['collateral'] for t in open_trades)
            equity_curve.append({'date': date, 'equity': capital + unrealised, 'cash': capital, 'open_positions': len(open_trades)})
            continue

        if regime == 'high_vol':
            if not (pd.notna(vix_from_high) and vix_from_high < -0.10 and vix > vix_ma):
                unrealised = sum(t['collateral'] for t in open_trades)
                equity_curve.append({'date': date, 'equity': capital + unrealised, 'cash': capital, 'open_positions': len(open_trades)})
                continue

        if i % 7 == 0 and len(open_trades) < 8:
            delta = params['delta']
            width = params['width']
            entry_dte = params['dte']
            size_mult = params['mult']

            otm_pct = delta * 0.5
            short_strike = round(spot * (1 - otm_pct), 0)
            long_strike = short_strike - width

            short_p = simulate_put_premium(spot, short_strike, entry_dte, vix)
            long_p = simulate_put_premium(spot, long_strike, entry_dte, vix)
            credit = short_p - long_p

            max_loss = (width - credit) * 100 * contracts_per_trade
            collateral = max_loss
            adjusted_risk = capital * max_risk_pct * size_mult

            if credit > 0.15 and collateral <= adjusted_risk and collateral > 0:
                trade_counter += 1
                pos_key = f"bt_ladder_{trade_counter}"
                capital -= collateral

                # Register with ladder (short position)
                ladder.register_position(pos_key, credit, contracts_per_trade, side='short')

                open_trades.append({
                    'entry_date': date,
                    'symbol': 'SPY',
                    'short_strike': short_strike,
                    'long_strike': long_strike,
                    'dte': entry_dte,
                    'entry_credit': credit,
                    'entry_spot': spot,
                    'entry_vix': vix,
                    'collateral': collateral,
                    'max_loss': max_loss,
                    'regime': regime,
                    'market_condition': row.get('market_condition', 'unknown'),
                    'pos_key': pos_key,
                    'remaining_qty': contracts_per_trade,
                })

        unrealised = sum(t['collateral'] for t in open_trades)
        equity_curve.append({
            'date': date,
            'equity': capital + unrealised,
            'cash': capital,
            'open_positions': len(open_trades),
        })

    for t in open_trades:
        t['exit_date'] = df.index[-1]
        t['pnl'] = t['entry_credit'] * 50 * t['remaining_qty']
        t['exit_reason'] = 'end_of_backtest'
        trades.append(t)
        ladder.remove_position(t['pos_key'])

    # Cleanup temp file
    if os.path.exists(state_file):
        os.remove(state_file)

    return _compile_results('VIX-Regime + Ladder', trades, equity_curve, initial_capital)


# ──────────────────────────────────────────────────────────────
# Results Compilation
# ──────────────────────────────────────────────────────────────

def _compile_results(
    strategy_name: str,
    trades: List[Dict],
    equity_curve: List[Dict],
    initial_capital: float,
) -> Dict:
    """Compile backtest results into a summary."""
    if not trades:
        return {
            'strategy': strategy_name,
            'total_trades': 0,
            'total_pnl': 0,
            'win_rate': 0,
            'avg_trade_pnl': 0,
            'max_drawdown_pct': 0,
            'sharpe_ratio': 0,
            'annualized_return_pct': 0,
            'trades': [],
            'equity_curve': pd.DataFrame(equity_curve),
            'market_condition_pnl': {},
        }

    total_pnl = sum(t['pnl'] for t in trades)
    winners = [t for t in trades if t['pnl'] > 0]
    losers = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(winners) / len(trades) * 100 if trades else 0
    avg_win = np.mean([t['pnl'] for t in winners]) if winners else 0
    avg_loss = np.mean([t['pnl'] for t in losers]) if losers else 0

    # Equity curve analysis
    eq_df = pd.DataFrame(equity_curve)
    if not eq_df.empty and 'equity' in eq_df.columns:
        peak = eq_df['equity'].expanding().max()
        drawdown = (eq_df['equity'] - peak) / peak
        max_dd = drawdown.min() * 100

        daily_returns = eq_df['equity'].pct_change().dropna()
        sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0

        total_days = len(eq_df)
        ann_return = ((eq_df['equity'].iloc[-1] / initial_capital) ** (252 / max(total_days, 1)) - 1) * 100
    else:
        max_dd = 0
        sharpe = 0
        ann_return = 0

    # P&L by market condition
    condition_pnl = {}
    for t in trades:
        cond = t.get('market_condition', 'unknown')
        if cond not in condition_pnl:
            condition_pnl[cond] = {'pnl': 0, 'count': 0, 'wins': 0}
        condition_pnl[cond]['pnl'] += t['pnl']
        condition_pnl[cond]['count'] += 1
        if t['pnl'] > 0:
            condition_pnl[cond]['wins'] += 1

    # Exit reason breakdown
    exit_reasons = {}
    for t in trades:
        reason = t.get('exit_reason', 'unknown')
        if reason not in exit_reasons:
            exit_reasons[reason] = {'count': 0, 'pnl': 0}
        exit_reasons[reason]['count'] += 1
        exit_reasons[reason]['pnl'] += t['pnl']

    return {
        'strategy': strategy_name,
        'total_trades': len(trades),
        'total_pnl': round(total_pnl, 2),
        'win_rate': round(win_rate, 1),
        'avg_trade_pnl': round(total_pnl / len(trades), 2) if trades else 0,
        'avg_winner': round(avg_win, 2),
        'avg_loser': round(avg_loss, 2),
        'max_drawdown_pct': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 3),
        'annualized_return_pct': round(ann_return, 2),
        'final_equity': round(initial_capital + total_pnl, 2),
        'initial_capital': initial_capital,
        'trades': trades,
        'equity_curve': eq_df,
        'market_condition_pnl': condition_pnl,
        'exit_reasons': exit_reasons,
    }


# ──────────────────────────────────────────────────────────────
# Run All Backtests
# ──────────────────────────────────────────────────────────────

def run_all_backtests(
    initial_capital: float = 50000,
    start: str = None,
    end: str = None,
) -> Dict[str, Dict]:
    """Run all 4 strategy backtests and return results."""
    data = load_historical_data(['SPY'], start=start, end=end)
    if 'SPY' not in data:
        raise ValueError("Could not load SPY data")

    df = data['SPY']
    df = classify_market_conditions(df)

    logger.info(f"Data loaded: {len(df)} days, {df.index[0].date()} → {df.index[-1].date()}")
    logger.info(f"Market conditions: {df['market_condition'].value_counts().to_dict()}")

    results = {}
    results['wheel'] = backtest_wheel(df, initial_capital)
    results['spx_spreads'] = backtest_spx_spreads(df, initial_capital)
    results['iron_condors'] = backtest_iron_condors(df, initial_capital)
    results['regime_adaptive'] = backtest_regime_adaptive(df, initial_capital)
    results['wheel_ladder'] = backtest_wheel_ladder(df, initial_capital)
    results['spx_ladder'] = backtest_spx_spreads_ladder(df, initial_capital)
    results['ic_ladder'] = backtest_iron_condors_ladder(df, initial_capital)
    results['regime_ladder'] = backtest_regime_adaptive_ladder(df, initial_capital)

    return results


def print_comparison(results: Dict[str, Dict]):
    """Print a comparison table of all strategies."""
    print("\n" + "=" * 100)
    print("BACKTEST RESULTS — STRATEGY COMPARISON")
    print("=" * 100)
    print(f"{'Strategy':<25} {'Trades':>7} {'Win%':>7} {'P&L':>10} {'Avg Trade':>10} "
          f"{'MaxDD%':>8} {'Sharpe':>8} {'AnnRet%':>9}")
    print("-" * 100)

    for key, r in results.items():
        print(f"{r['strategy']:<25} {r['total_trades']:>7} {r['win_rate']:>6.1f}% "
              f"${r['total_pnl']:>9,.2f} ${r['avg_trade_pnl']:>9,.2f} "
              f"{r['max_drawdown_pct']:>7.2f}% {r['sharpe_ratio']:>7.3f} "
              f"{r['annualized_return_pct']:>8.2f}%")

    print("=" * 100)

    # Market condition breakdown
    print("\nP&L BY MARKET CONDITION:")
    print("-" * 80)
    print(f"{'Strategy':<25} {'Uptrend':>12} {'Sideways':>12} {'Downtrend':>12} {'Choppy':>12}")
    print("-" * 80)

    for key, r in results.items():
        mc = r.get('market_condition_pnl', {})
        up = mc.get('uptrend', {}).get('pnl', 0)
        sw = mc.get('sideways', {}).get('pnl', 0)
        dn = mc.get('downtrend', {}).get('pnl', 0)
        ch = mc.get('choppy', {}).get('pnl', 0)
        print(f"{r['strategy']:<25} ${up:>10,.2f} ${sw:>10,.2f} ${dn:>10,.2f} ${ch:>10,.2f}")

    print("-" * 80)


def save_results(results: Dict[str, Dict], output_dir: str = 'backtest_results'):
    """Save results to JSON and CSV."""
    os.makedirs(output_dir, exist_ok=True)

    summary = []
    for key, r in results.items():
        row = {k: v for k, v in r.items() if k not in ('trades', 'equity_curve')}
        summary.append(row)

        # Save equity curve
        if isinstance(r.get('equity_curve'), pd.DataFrame) and not r['equity_curve'].empty:
            eq_path = os.path.join(output_dir, f'{key}_equity_curve.csv')
            r['equity_curve'].to_csv(eq_path, index=False)

        # Save trades
        if r.get('trades'):
            trade_rows = []
            for t in r['trades']:
                safe_t = {}
                for tk, tv in t.items():
                    if isinstance(tv, (int, float, str, bool)):
                        safe_t[tk] = tv
                    elif hasattr(tv, 'isoformat'):
                        safe_t[tk] = tv.isoformat()
                    else:
                        safe_t[tk] = str(tv)
                trade_rows.append(safe_t)
            trades_df = pd.DataFrame(trade_rows)
            trades_path = os.path.join(output_dir, f'{key}_trades.csv')
            trades_df.to_csv(trades_path, index=False)

    summary_path = os.path.join(output_dir, 'summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(f"Results saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description='Options Strategy Backtester')
    parser.add_argument('--capital', type=float, default=50000)
    parser.add_argument('--start', default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='backtest_results')
    parser.add_argument('--strategy', default=None, help='Run single strategy')
    parser.add_argument('--multi-stock', action='store_true', help='Run multi-stock comparison')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    if args.multi_stock:
        run_multi_stock_comparison(args.capital, start=args.start, end=args.end)
    else:
        results = run_all_backtests(args.capital, start=args.start, end=args.end)
        print_comparison(results)
        save_results(results, args.output)


# ──────────────────────────────────────────────────────────────
# Multi-Stock Strategy Comparison
# ──────────────────────────────────────────────────────────────

# Best stocks for each strategy based on scanner scoring criteria
STRATEGY_STOCK_MAP = {
    'wheel': {
        'description': 'Cash-Secured Puts + Covered Calls',
        'how_it_works': (
            'Phase A: SELL cash-secured puts at 0.15 delta (5-8% OTM). '
            'Collect premium while waiting. If assigned, own stock at discount.\n'
            '   Phase B: SELL covered calls at 0.30 delta against owned shares. '
            'If called away, keep premium + stock gains. Repeat.\n'
            '   MAKES MONEY: Theta decay — options lose value every day. You sell that time value.'
        ),
        'best_for': 'Stocks you WANT to own at a discount. Moderate IV, uptrend/sideways.',
        'symbols': ['AAPL', 'MSFT', 'AMD', 'JPM', 'NVDA', 'GOOGL'],
        'spread_width': 0,
        'ideal_iv': '25-55',
        'ideal_trend': 'Uptrend or Sideways',
    },
    'spreads': {
        'description': 'Bull Put Credit Spreads (SPX-style)',
        'how_it_works': (
            'SELL a put at ~0.12 delta + BUY a put further OTM (protection).\n'
            '   The short put decays faster than the long put → you keep the credit difference.\n'
            '   MAKES MONEY: Net theta decay between two strikes. Defined risk — max loss = spread width - credit.'
        ),
        'best_for': 'Highly liquid index ETFs. Needs tight bid/ask spreads.',
        'symbols': ['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT', 'AMZN'],
        'spread_width': 5,
        'ideal_iv': '20-45',
        'ideal_trend': 'Uptrend (bull put benefits from rising market)',
    },
    'condors': {
        'description': 'Iron Condors (Sell Both Sides)',
        'how_it_works': (
            'SELL a put spread (bull put) + SELL a call spread (bear call) simultaneously.\n'
            '   Collect credit from BOTH sides. Stock must stay between your short strikes.\n'
            '   MAKES MONEY: Double theta decay. Maximum profit if stock goes nowhere. '
            'Best in LOW volatility, range-bound markets.'
        ),
        'best_for': 'Sideways stocks with moderate IV. Range-bound markets.',
        'symbols': ['SPY', 'QQQ', 'AAPL', 'MSFT', 'JPM', 'JNJ'],
        'spread_width': 5,
        'ideal_iv': '20-60 (sweet spot 30-50)',
        'ideal_trend': 'Sideways / Range-bound',
    },
    'regime': {
        'description': 'VIX-Regime Adaptive ML Strategy',
        'how_it_works': (
            'Uses machine learning (RandomForest) to classify VIX into 4 regimes:\n'
            '   Low Vol (<15):  Stand aside — premiums too thin\n'
            '   Normal (15-22): Bull put spreads, standard sizing\n'
            '   High Vol (22-35): WIDER spreads, 1.5x size — PRIME entry zone\n'
            '   Crash (35+):   Close everything, protect capital\n'
            '   MAKES MONEY: Adapts position sizing to volatility. Sells MORE premium when IV is rich.'
        ),
        'best_for': 'Index ETFs. Thrives during vol spikes then mean-reversion.',
        'symbols': ['SPY', 'QQQ', 'IWM', 'DIA', 'AAPL', 'NVDA'],
        'spread_width': 5,
        'ideal_iv': 'All ranges (adaptive)',
        'ideal_trend': 'Any — strategy adapts',
    },
}


def run_multi_stock_comparison(
    initial_capital: float = 50000,
    start: str = None,
    end: str = None,
):
    """Run each strategy across its best 5-6 stocks and print comparison."""
    # Suppress verbose ladder logging during backtest
    logging.getLogger('LadderExit').setLevel(logging.CRITICAL)

    all_symbols = set()
    for cfg in STRATEGY_STOCK_MAP.values():
        all_symbols.update(cfg['symbols'])

    # Load all data at once
    data = load_historical_data(list(all_symbols), start=start, end=end)

    # Need VIX for regime classification — use SPY's data as reference
    ref_sym = 'SPY' if 'SPY' in data else list(data.keys())[0]
    ref_df = classify_market_conditions(data[ref_sym])

    logger.info(f"\nLoaded {len(data)} symbols, {len(ref_df)} trading days")
    logger.info(f"Period: {ref_df.index[0].date()} → {ref_df.index[-1].date()}")

    # ── PRINT STRATEGY OVERVIEW ──
    print("\n" + "=" * 110)
    print("THE 4 OPTIONS STRATEGIES — WHAT THEY ARE & HOW THEY MAKE MONEY")
    print("=" * 110)

    for key, cfg in STRATEGY_STOCK_MAP.items():
        print(f"\n{'─' * 110}")
        strat_num = {'wheel': '1', 'spreads': '2', 'condors': '3', 'regime': '4'}[key]
        print(f"  STRATEGY {strat_num}: {cfg['description'].upper()}")
        print(f"{'─' * 110}")
        print(f"  How It Works:")
        for line in cfg['how_it_works'].split('\n'):
            print(f"    {line.strip()}")
        print(f"  Best For:    {cfg['best_for']}")
        print(f"  Ideal IV:    {cfg['ideal_iv']}")
        print(f"  Ideal Trend: {cfg['ideal_trend']}")
        print(f"  Best Stocks: {', '.join(cfg['symbols'])}")

    # ── RUN BACKTESTS PER STRATEGY PER STOCK ──
    print("\n\n" + "=" * 110)
    print("MULTI-STOCK BACKTEST RESULTS (with Ladder Exits)")
    print("=" * 110)

    all_results = {}

    for strat_key, cfg in STRATEGY_STOCK_MAP.items():
        strat_num = {'wheel': '1', 'spreads': '2', 'condors': '3', 'regime': '4'}[strat_key]
        print(f"\n{'═' * 110}")
        print(f"  STRATEGY {strat_num}: {cfg['description']}")
        print(f"{'═' * 110}")
        print(f"  {'Symbol':<8} {'Trades':>7} {'Win%':>7} {'P&L':>11} {'Avg Trade':>10} "
              f"{'MaxDD%':>8} {'Sharpe':>8} {'AnnRet%':>9}")
        print(f"  {'─' * 100}")

        strat_results = {}
        for sym in cfg['symbols']:
            if sym not in data:
                print(f"  {sym:<8} {'—':>7} {'—':>7} {'No data':>11}")
                continue

            sym_df = data[sym].copy()
            sym_df = classify_market_conditions(sym_df)

            try:
                if strat_key == 'wheel':
                    r = backtest_wheel_ladder(sym_df, initial_capital, contracts_per_trade=1)
                elif strat_key == 'spreads':
                    r = backtest_spx_spreads_ladder(sym_df, initial_capital,
                                                    spread_width=5, contracts_per_trade=1)
                elif strat_key == 'condors':
                    r = backtest_iron_condors_ladder(sym_df, initial_capital,
                                                     wing_width=5, contracts_per_trade=3)
                elif strat_key == 'regime':
                    r = backtest_regime_adaptive_ladder(sym_df, initial_capital,
                                                        contracts_per_trade=4)

                r['symbol'] = sym
                strat_results[sym] = r

                print(f"  {sym:<8} {r['total_trades']:>7} {r['win_rate']:>6.1f}% "
                      f"${r['total_pnl']:>9,.2f} ${r['avg_trade_pnl']:>9,.2f} "
                      f"{r['max_drawdown_pct']:>7.2f}% {r['sharpe_ratio']:>7.3f} "
                      f"{r['annualized_return_pct']:>8.2f}%")

            except Exception as e:
                print(f"  {sym:<8} ERROR: {e}")

        # Strategy totals
        if strat_results:
            total_trades = sum(r['total_trades'] for r in strat_results.values())
            total_pnl = sum(r['total_pnl'] for r in strat_results.values())
            avg_wr = np.mean([r['win_rate'] for r in strat_results.values() if r['total_trades'] > 0])
            avg_sharpe = np.mean([r['sharpe_ratio'] for r in strat_results.values() if r['total_trades'] > 0])
            print(f"  {'─' * 100}")
            print(f"  {'TOTAL':<8} {total_trades:>7} {avg_wr:>6.1f}% "
                  f"${total_pnl:>9,.2f} {'':>10} "
                  f"{'':>8} {avg_sharpe:>7.3f}")

        all_results[strat_key] = strat_results

    # ── GRAND SUMMARY ──
    print("\n\n" + "=" * 110)
    print("GRAND SUMMARY — BEST STRATEGY PER STOCK")
    print("=" * 110)
    print(f"  {'Symbol':<8} {'Wheel':>10} {'Spreads':>10} {'Condors':>10} {'Regime':>10} {'Best Strategy':>20}")
    print(f"  {'─' * 80}")

    all_symbols_tested = set()
    for sr in all_results.values():
        all_symbols_tested.update(sr.keys())

    for sym in sorted(all_symbols_tested):
        wheel_pnl = all_results.get('wheel', {}).get(sym, {}).get('total_pnl', None)
        spread_pnl = all_results.get('spreads', {}).get(sym, {}).get('total_pnl', None)
        condor_pnl = all_results.get('condors', {}).get(sym, {}).get('total_pnl', None)
        regime_pnl = all_results.get('regime', {}).get(sym, {}).get('total_pnl', None)

        pnl_map = {}
        if wheel_pnl is not None:
            pnl_map['Wheel'] = wheel_pnl
        if spread_pnl is not None:
            pnl_map['Spreads'] = spread_pnl
        if condor_pnl is not None:
            pnl_map['Condors'] = condor_pnl
        if regime_pnl is not None:
            pnl_map['Regime'] = regime_pnl

        best = max(pnl_map, key=pnl_map.get) if pnl_map else '—'

        w = f"${wheel_pnl:>8,.0f}" if wheel_pnl is not None else f"{'—':>9}"
        s = f"${spread_pnl:>8,.0f}" if spread_pnl is not None else f"{'—':>9}"
        c = f"${condor_pnl:>8,.0f}" if condor_pnl is not None else f"{'—':>9}"
        rg = f"${regime_pnl:>8,.0f}" if regime_pnl is not None else f"{'—':>9}"

        print(f"  {sym:<8} {w:>10} {s:>10} {c:>10} {rg:>10} {best:>20}")

    print(f"  {'─' * 80}")

    # ── TOTAL PER STRATEGY ──
    print(f"\n  STRATEGY TOTALS (across all stocks):")
    for strat_key in ['wheel', 'spreads', 'condors', 'regime']:
        sr = all_results.get(strat_key, {})
        t = sum(r['total_pnl'] for r in sr.values())
        n = sum(r['total_trades'] for r in sr.values())
        label = STRATEGY_STOCK_MAP[strat_key]['description']
        print(f"    {label:<45} {n:>4} trades  ${t:>10,.2f}")

    print("=" * 110)


if __name__ == '__main__':
    main()
