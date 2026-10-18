#!/usr/bin/env python3
"""
================================================================================
RAJAT ALPHA V67 - INSTITUTIONAL VECTORIZED & EVENT-DRIVEN BACKTEST PIPELINE
================================================================================
Target Environment: Google Colab / Local Python 3.10+
Dependencies: yfinance, pandas, numpy, tabulate, matplotlib

DESCRIPTION:
Backtests the complete Rajat Alpha v67 Version 3.2 Strategy over 5 years (2021-2026)
comparing the Old v67 Baseline (Market orders, 17% fixed SL, no candle/impulse filters)
against the New v3.2 Institutional Engine (SOEE Midpoint, Hybrid ATR SL, Impulse validator,
Shooting Star filter, 4-tier partial exits, Dynamic TES, Runner mode).

USAGE IN GOOGLE COLAB:
1. Open Google Colab (https://colab.research.google.com)
2. Run cell: !pip install yfinance pandas numpy tabulate matplotlib
3. Upload or paste this script and execute: python backtest_colab_pipeline.py
================================================================================
"""

import sys
import os
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    os.system("pip install yfinance")
    import yfinance as yf

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    print("Installing matplotlib...")
    os.system("pip install matplotlib")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

# ----------------------------------------------------------------------
# 1. WATCHLIST DEFINITION (Institutional Core + Benchmarks)
# ----------------------------------------------------------------------
DEFAULT_WATCHLIST = [
    "AAPL", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "TSLA", "CATY", "WSBC", "CLMT"
]
EXTENDED_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "AMD",
    "NFLX", "ADBE", "CRM", "QCOM", "TXN", "INTU", "AMAT", "BKNG", "ISRG", "LRCX",
    "MU", "PANW", "SNPS", "CDNS", "CRWD", "KLAC", "NXPI", "MELI", "MAR", "FTNT",
    "MRVL", "ABNB", "ORCL", "NOW", "PLTR", "ANET", "UBER", "DASH", "SMCI", "ARM",
    "DELL", "APP", "CRDO", "AXGN", "DUOL", "IOT", "MDB", "DDOG", "ZS", "NET"
]
BENCHMARK_SYMBOLS = ["SPY", "QQQ"]

def calculate_ibd_rs(df_slice: pd.DataFrame, qqq_slice: pd.DataFrame) -> float:
    """Calculates 0-100 Relative Strength rating vs QQQ"""
    if len(df_slice) < 22 or len(qqq_slice) < 22:
        return 50.0
    stock_ret = (df_slice['Close'].iloc[-1] - df_slice['Close'].iloc[-21]) / df_slice['Close'].iloc[-21]
    qqq_ret = (qqq_slice['Close'].iloc[-1] - qqq_slice['Close'].iloc[-21]) / qqq_slice['Close'].iloc[-21]
    alpha = (1.0 + stock_ret) / (1.0 + qqq_ret)
    score_1 = max(0, min(100, (alpha - 0.90) / 0.30 * 100))
    
    slice_21 = df_slice.iloc[-21:]
    up_vol = slice_21[slice_21['Close'] > slice_21['Open']]['Volume'].sum()
    dn_vol = max(1, slice_21[slice_21['Close'] < slice_21['Open']]['Volume'].sum())
    ud_ratio = up_vol / dn_vol
    score_2 = max(0, min(100, (ud_ratio - 0.70) / 1.0 * 100))
    
    green_days = sum(slice_21['Close'] > slice_21['Open'])
    red_days = max(1, sum(slice_21['Close'] < slice_21['Open']))
    score_3 = max(0, min(100, (green_days / red_days - 0.60) / 0.80 * 100))
    
    high_252 = df_slice['High'].max()
    dist_52 = (high_252 - df_slice['Close'].iloc[-1]) / high_252
    score_4 = max(0, min(100, (1.0 - (dist_52 / 0.20)) * 100))
    
    return round((score_1 * 0.35) + (score_2 * 0.25) + (score_3 * 0.20) + (score_4 * 0.20), 1)

# ----------------------------------------------------------------------
# 2. INDICATOR & FEATURE CALCULATION ENGINE
# ----------------------------------------------------------------------
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Moving Averages
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # ATR 14
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(window=14).mean()
    
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI14'] = 100 - (100 / (1 + rs))
    df['RSI14'] = df['RSI14'].fillna(50)
    
    # Volume SMA21
    df['VOL_SMA21'] = df['Volume'].rolling(window=21).mean()
    return df

def calculate_weekly_monthly_alignment(df_daily: pd.DataFrame) -> Tuple[bool, bool]:
    """Calculates weekly EMA21 and monthly EMA10 alignment"""
    if len(df_daily) < 150:
        return False, False
        
    # Resample to weekly
    df_w = df_daily.resample('W-FRI').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
    }).dropna()
    df_w['EMA21'] = df_w['Close'].ewm(span=21, adjust=False).mean()
    weekly_ok = (df_w['Close'].iloc[-1] > df_w['EMA21'].iloc[-1]) if len(df_w) > 22 else False
    
    # Resample to monthly
    df_m = df_daily.resample('ME').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
    }).dropna()
    df_m['EMA10'] = df_m['Close'].ewm(span=10, adjust=False).mean()
    monthly_ok = (df_m['Close'].iloc[-1] > df_m['EMA10'].iloc[-1]) if len(df_m) > 11 else False
    
    return weekly_ok, monthly_ok

# ----------------------------------------------------------------------
# 3. REVERSAL PATTERNS & REJECTION FILTERS
# ----------------------------------------------------------------------
def is_shooting_star(candle: pd.Series) -> bool:
    body = abs(candle['Close'] - candle['Open'])
    total_range = candle['High'] - candle['Low']
    if total_range <= 0: return False
    upper_wick = candle['High'] - max(candle['Open'], candle['Close'])
    return (upper_wick / total_range) > 0.50

def detect_candlestick_pattern(df_slice: pd.DataFrame) -> Tuple[bool, str, float]:
    """Detects Engulfing, Piercing, Tweezer, Hammer, Upside Reversal"""
    if len(df_slice) < 2:
        return False, "None", 0.0
    c1 = df_slice.iloc[-2]
    c2 = df_slice.iloc[-1]
    
    # 1. Bullish Engulfing
    if c1['Close'] < c1['Open'] and c2['Close'] > c2['Open']:
        if c2['Open'] <= c1['Close'] and c2['Close'] >= c1['Open']:
            return True, "Engulfing", 1.0
            
    # 2. Bullish Piercing
    if c1['Close'] < c1['Open'] and c2['Close'] > c2['Open']:
        midpoint1 = (c1['Open'] + c1['Close']) / 2.0
        if c2['Open'] < c1['Close'] and c2['Close'] > midpoint1 and c2['Close'] < c1['Open']:
            return True, "Piercing", 1.0
            
    # 3. Tweezer Bottom
    if c1['Close'] < c1['Open'] and c2['Close'] > c2['Open']:
        if abs(c1['Low'] - c2['Low']) / c1['Close'] <= 0.003:
            return True, "Tweezer", 0.8
            
    # 4. Hammer
    body = abs(c2['Close'] - c2['Open'])
    total_range = c2['High'] - c2['Low']
    if total_range > 0 and (c2['Low'] < min(c2['Open'], c2['Close'])):
        lower_wick = min(c2['Open'], c2['Close']) - c2['Low']
        upper_wick = c2['High'] - max(c2['Open'], c2['Close'])
        if lower_wick >= 2.0 * body and upper_wick <= 0.20 * total_range:
            return True, "Hammer", 0.8
            
    # 5. Upside Reversal
    if c1['Close'] < c1['Open'] and c2['Close'] > c2['Open']:
        midpoint = (c1['Open'] + c1['Close']) / 2.0
        if c2['Open'] <= c1['Close'] and c2['Close'] > midpoint:
            return True, "UpsideReversal", 0.6
            
    return False, "None", 0.0

# ----------------------------------------------------------------------
# 4. SIGNAL GENERATOR (7 GATES)
# ----------------------------------------------------------------------
def evaluate_signal_v32(df: pd.DataFrame, i: int, qqq_df: pd.DataFrame) -> Tuple[bool, Dict]:
    """
    Evaluates bar i for v3.2 Institutional criteria with restructured sequence:
    1. Market Structure (SMA50 > SMA200, EMA21 >= SMA50 - 2.5%)
    2. Valid Impulse & Pullback Sequence
    3. Reversal Candlestick Pattern OR Qualified Touch
    4. Weekly Confirmation (Weekly Close > Weekly EMA21)
    5. Demand Zone Proximity Check
    6. Stalling & Shooting Star Rejection Filters
    7. IBD RS Calculation (Informational)
    8. Scoring (out of 7.0) & Touch-Only Dual Gate
    """
    if i < 200:
        return False, {}
        
    df_window = df.iloc[:i+1]
    curr = df_window.iloc[-1]
    
    # Gate 1: Market Structure
    if pd.isna(curr['SMA50']) or pd.isna(curr['SMA200']) or pd.isna(curr['EMA21']):
        return False, {}
    if curr['SMA50'] <= curr['SMA200']:
        return False, {}
    if curr['EMA21'] < (curr['SMA50'] * 0.975):
        return False, {}
        
    # Gate 2: Preceding Impulse Wave & Orderly Retracement (First criteria: valid pullback)
    impulse_lookback = min(20, len(df_window) - 1)
    slice_impulse = df_window.iloc[-impulse_lookback:-1]
    swing_high = slice_impulse['High'].max()
    idx_high = slice_impulse['High'].idxmax()
    ema_at_high = df_window.loc[idx_high, 'EMA21']
    if swing_high < ema_at_high * 1.05:
        return False, {}  # No prior markup wave
    if (swing_high - curr['Low']) / swing_high < 0.03:
        return False, {}  # Inadequate retracement
        
    # Gate 3: Candlestick Pattern OR Qualified Touch (Pattern formation after pullback)
    pat_found, pat_name, pat_weight = detect_candlestick_pattern(df_window)
    dist_ema21 = abs(curr['Close'] - curr['EMA21']) / curr['EMA21']
    dist_sma50 = abs(curr['Close'] - curr['SMA50']) / curr['SMA50']
    touch_found = (dist_ema21 <= 0.025) or (dist_sma50 <= 0.025)
    
    if not (pat_found or touch_found):
        return False, {}  # No recognized pattern or touch after pullback
        
    # Gate 4: Weekly MTF Confirmation
    weekly_ok, monthly_ok = calculate_weekly_monthly_alignment(df_window)
    if not weekly_ok:
        return False, {}  # Weekly close must be above EMA21
        
    # Gate 5: Demand Zone Proximity Check
    low_21 = df_window['Low'].iloc[-21:].min()
    in_demand_zone = curr['Low'] <= low_21 * 1.035
    
    # Gate 6: Stalling & Shooting Star Rejection Filters
    high_8 = df_window['High'].iloc[-8:].max()
    low_8 = df_window['Low'].iloc[-8:].min()
    if (high_8 - low_8) / low_8 < 0.05:
        return False, {}  # Horizontal churning
        
    if is_shooting_star(curr):
        return False, {}  # Heavy upper wick rejection
        
    # Green session check
    if len(df_window) >= 2 and curr['Close'] <= df_window.iloc[-2]['Close']:
        return False, {}  # Red day rejection
        
    # Calculate IBD RS (0-100) — Informational only
    rs_score = 50.0
    if qqq_df is not None:
        qqq_slice = qqq_df.loc[:curr.name]
        rs_score = calculate_ibd_rs(df_window, qqq_slice)
        
    # Gate 7: Scoring (out of 7.0)
    score = 0.0
    if pat_found: score += pat_weight
    if weekly_ok: score += 1.0
    if in_demand_zone: score += 1.0
    if curr['RSI14'] > 50: score += 1.0
    if monthly_ok: score += 1.0
    if curr['Volume'] > curr['VOL_SMA21']: score += 1.0
    if touch_found: score += 1.0
    
    # Touch-only check requires >= 5.0 and bullish candle body
    if not pat_found and touch_found:
        body = abs(curr['Close'] - curr['Open'])
        rng = curr['High'] - curr['Low']
        if score < 5.0 or (body / rng if rng > 0 else 0) < 0.50:
            return False, {}
    elif score < 4.0:
        return False, {}
        
    return True, {
        'price': curr['Close'],
        'atr': curr['ATR14'],
        'score': round(score, 1),
        'rs_score': rs_score,
        'pattern': pat_name if pat_found else "Touch-Only"
    }

# ----------------------------------------------------------------------
# 5. SIMULATION ENGINES: BASELINE VS INSTITUTIONAL
# ----------------------------------------------------------------------
class Trade:
    def __init__(self, symbol: str, entry_date, entry_price: float, initial_sl: float, 
                 shares: int, is_v32: bool = True):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.stop_loss = initial_sl
        self.initial_sl = initial_sl
        self.orig_shares = shares
        self.remaining_shares = shares
        self.is_v32 = is_v32
        
        self.sl_stage = 0
        self.is_runner = False
        self.bars_held = 0
        self.max_hold_bars = 21
        self.realized_pnl = 0.0
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = ""
        self.partial_exits = set()

def run_backtest_simulation(all_data: Dict[str, pd.DataFrame], qqq_df: pd.DataFrame, 
                            mode: str = "v32") -> List[Trade]:
    """
    Simulates portfolio trading:
    - Mode 'baseline': Old v67 (Market orders with 0.30% slippage, 17% fixed SL, 21d fixed TES, 2-tier exit)
    - Mode 'v32': New v3.2 (SOEE Midpoint with 0.05% slippage, Hybrid ATR SL, 4-tier exits, Dynamic TES, Runner mode)
    """
    closed_trades: List[Trade] = []
    open_trades: List[Trade] = []
    
    # Generate unified trading calendar
    all_dates = sorted(list(set.union(*[set(df.index) for df in all_data.values()])))
    
    for dt in all_dates:
        # 1. Update Open Positions
        surviving_trades = []
        for t in open_trades:
            df = all_data[t.symbol]
            if dt not in df.index:
                surviving_trades.append(t)
                continue
                
            bar = df.loc[dt]
            t.bars_held += 1
            close_px = bar['Close']
            low_px = bar['Low']
            high_px = bar['High']
            
            # --- V32 LOGIC ---
            if mode == "v32":
                # Multi-stage trailing SL (with Stage 2 +1% and Stage 3 +5% extension ratchet)
                gain_pct = (high_px - t.entry_price) / t.entry_price
                if gain_pct >= 0.15:
                    ratchet = 0.10 + (gain_pct - 0.15)
                    t.stop_loss = max(t.stop_loss, t.entry_price * (1.0 + ratchet))
                    t.sl_stage = 4
                elif gain_pct >= 0.10:
                    t.stop_loss = max(t.stop_loss, t.entry_price * 1.03)
                    t.sl_stage = 3
                elif gain_pct >= 0.08:
                    t.stop_loss = max(t.stop_loss, t.entry_price * 1.01) # +1% above entry price
                    t.sl_stage = 2
                elif gain_pct >= 0.05:
                    t.stop_loss = max(t.stop_loss, t.entry_price * 0.96)
                    t.sl_stage = 1
                    
                # 4-Tier Partial Exits
                if 'PT1' not in t.partial_exits and high_px >= t.entry_price * 1.05:
                    qty = int(t.orig_shares * 0.20)
                    t.realized_pnl += qty * (t.entry_price * 1.05 - t.entry_price)
                    t.remaining_shares -= qty
                    t.partial_exits.add('PT1')
                    
                if 'PT2' not in t.partial_exits and high_px >= t.entry_price * 1.10:
                    qty = int(t.orig_shares * 0.25)
                    t.realized_pnl += qty * (t.entry_price * 1.10 - t.entry_price)
                    t.remaining_shares -= qty
                    t.partial_exits.add('PT2')
                    
                if 'PT3' not in t.partial_exits and high_px >= t.entry_price * 1.15:
                    qty = int(t.orig_shares * 0.25)
                    t.realized_pnl += qty * (t.entry_price * 1.15 - t.entry_price)
                    t.remaining_shares -= qty
                    t.partial_exits.add('PT3')
                    t.is_runner = True  # Remaining 30% enters runner mode
                    
                # Dynamic TES Evaluation (checks effective limit)
                effective_limit = t.max_hold_bars
                if t.bars_held >= effective_limit and not t.is_runner:
                    # Grant 10-day extension if consolidating constructively above EMA21
                    if t.sl_stage < 2 and close_px > bar['EMA21'] and (close_px - t.entry_price)/t.entry_price > -0.05:
                        t.max_hold_bars += 10
                    else:
                        # TES Exit at confirmed close
                        slippage = 0.0005 # SOEE
                        t.exit_price = close_px * (1.0 - slippage)
                        t.realized_pnl += t.remaining_shares * (t.exit_price - t.entry_price)
                        t.exit_date = dt
                        t.exit_reason = "Dynamic TES"
                        closed_trades.append(t)
                        continue
                        
                # True Closing-Basis Stop Loss Check
                if close_px <= t.stop_loss:
                    slippage = 0.0005
                    t.exit_price = min(close_px, t.stop_loss) * (1.0 - slippage)
                    t.realized_pnl += t.remaining_shares * (t.exit_price - t.entry_price)
                    t.exit_date = dt
                    t.exit_reason = "Trailing SL"
                    closed_trades.append(t)
                    continue

            # --- BASELINE OLD V67 LOGIC ---
            else:
                # Intraday tick stop loss trigger (vulnerable to intra-day wicks)
                if low_px <= t.stop_loss:
                    slippage = 0.0035 # Market order jobbing disadvantage
                    t.exit_price = t.stop_loss * (1.0 - slippage)
                    t.realized_pnl = t.orig_shares * (t.exit_price - t.entry_price)
                    t.exit_date = dt
                    t.exit_reason = "Stop Loss"
                    closed_trades.append(t)
                    continue
                    
                # Fixed 21-day TES
                if t.bars_held >= 21:
                    slippage = 0.0035
                    t.exit_price = close_px * (1.0 - slippage)
                    t.realized_pnl = t.orig_shares * (t.exit_price - t.entry_price)
                    t.exit_date = dt
                    t.exit_reason = "TES 21d"
                    closed_trades.append(t)
                    continue

            surviving_trades.append(t)
        open_trades = surviving_trades

        # 2. Check New Buy Signals
        for sym, df in all_data.items():
            if dt not in df.index:
                continue
            idx = df.index.get_loc(dt)
            if mode == "v32":
                sig_valid, details = evaluate_signal_v32(df, idx, qqq_df)
                if sig_valid and len(open_trades) < 15:
                    entry_px = details['price'] * 1.0005 # SOEE Midpoint
                    # Hybrid ATR initial stop
                    atr = details['atr']
                    init_sl = entry_px - (2.0 * atr) if atr > 0 else entry_px * 0.83
                    init_sl = max(entry_px * 0.83, min(entry_px * 0.95, init_sl))
                    
                    # Position Sizing: Fixed fractional risk vs fixed allocation
                    # Method: Risk 0.5% equity ($500) per trade based on SL distance
                    dollar_risk = 500.0
                    risk_per_share = max(0.50, entry_px - init_sl)
                    shares = max(1, int(dollar_risk / risk_per_share))
                    # Bound to max 6% allocation ($6,000)
                    shares = min(shares, max(1, int(6000.0 / entry_px)))
                    open_trades.append(Trade(sym, dt, entry_px, init_sl, shares, is_v32=True))
            else:
                # Old baseline: looser entry, 17% fixed SL, market order slippage
                if idx >= 200:
                    c = df.iloc[idx]
                    if c['SMA50'] > c['SMA200'] and c['Close'] > c['EMA21']:
                        entry_px = c['Close'] * 1.0035 # Market order crossing spread
                        init_sl = entry_px * 0.83      # Fixed 17% stop
                        shares = max(1, int(3000.0 / entry_px))
                        if len(open_trades) < 15:
                            open_trades.append(Trade(sym, dt, entry_px, init_sl, shares, is_v32=False))
                            
    return closed_trades

# ----------------------------------------------------------------------
# 6. PERFORMANCE REPORT & VISUALIZATION DASHBOARD
# ----------------------------------------------------------------------
def generate_performance_metrics(trades: List[Trade], title: str) -> Dict:
    if not trades:
        print(f"[{title}] No completed trades.")
        return {}
        
    pnls = [t.realized_pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    total_pnl = sum(pnls)
    win_rate = (len(wins) / len(trades)) * 100 if trades else 0.0
    profit_factor = (sum(wins) / abs(sum(losses))) if sum(losses) != 0 else float('inf')
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)
    
    # Drawdown
    equity_curve = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity_curve)
    drawdown = peak - equity_curve
    max_dd = np.max(drawdown) if len(drawdown) > 0 else 0.0
    
    print("\n" + "="*70)
    print(f" [REPORT] {title} PERFORMANCE AUDIT")
    print("="*70)
    print(f" Total Trades Executed:       {len(trades)}")
    print(f" Win Rate:                     {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
    print(f" Total Realized P/L:          ${total_pnl:,.2f}")
    print(f" Profit Factor:                {profit_factor:.2f}")
    print(f" Average Winning Trade:       ${avg_win:,.2f}")
    print(f" Average Losing Trade:        ${avg_loss:,.2f}")
    print(f" Win/Loss Ratio:               {abs(avg_win / avg_loss):.2f}" if avg_loss != 0 else "N/A")
    print(f" Trade Expectancy:            ${expectancy:,.2f} per trade")
    print(f" Maximum Equity Drawdown:     ${max_dd:,.2f}")
    print("="*70)
    
    return {
        'trades': len(trades),
        'win_rate': win_rate,
        'wins': len(wins),
        'losses': len(losses),
        'total_pnl': total_pnl,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'expectancy': expectancy,
        'max_dd': max_dd
    }

def plot_backtest_dashboard(v32_trades: List[Trade], baseline_trades: Optional[List[Trade]] = None, save_path: str = "v32_backtest_dashboard.png"):
    """
    Renders a comprehensive 4-panel visual dashboard:
    1. Cumulative Equity Curve ($): New v3.2 Institutional vs Old Baseline
    2. Trade Outcome Breakdown (Pie Chart): Wins vs Losses
    3. Exit Reasons Breakdown (Pie Chart): Profit Targets, Runner, TES, Stop Loss
    4. Trade P/L (%) Distribution Histogram / Bar Chart
    """
    if not v32_trades:
        print("No trades to plot.")
        return
        
    try:
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Rajat Alpha v67 (Version 3.2) Institutional Backtest Dashboard", fontsize=18, fontweight='bold', y=0.98)
        
        # 1. CUMULATIVE EQUITY CURVE
        ax1 = axes[0, 0]
        v32_pnl = np.cumsum([t.realized_pnl for t in v32_trades])
        ax1.plot(range(1, len(v32_pnl) + 1), v32_pnl, label="v3.2 Institutional (SOEE + Hybrid ATR)", color='#10b981', linewidth=2.5)
        
        if baseline_trades:
            base_pnl = np.cumsum([t.realized_pnl for t in baseline_trades])
            ax1.plot(range(1, len(base_pnl) + 1), base_pnl, label="Old Baseline (Market Orders + 17% SL)", color='#ef4444', linewidth=1.8, linestyle='--')
            
        ax1.set_title("Cumulative Equity Curve ($)", fontsize=14, fontweight='bold')
        ax1.set_xlabel("Trade Sequence Number")
        ax1.set_ylabel("Net Realized Profit / Loss ($)")
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc="upper left")
        
        # 2. WIN / LOSS PIE CHART
        ax2 = axes[0, 1]
        wins = sum(1 for t in v32_trades if t.realized_pnl > 0)
        losses = sum(1 for t in v32_trades if t.realized_pnl <= 0)
        
        pie_labels = [f"Wins ({wins})", f"Losses ({losses})"]
        pie_colors = ['#10b981', '#f43f5e']
        ax2.pie([wins, losses], labels=pie_labels, colors=pie_colors, autopct='%1.1f%%',
                startangle=140, explode=(0.06, 0), textprops={'fontsize': 12, 'weight': 'bold'})
        ax2.set_title("Win Rate Distribution", fontsize=14, fontweight='bold')
        
        # 3. EXIT REASONS PIE CHART
        ax3 = axes[1, 0]
        reason_counts = {}
        for t in v32_trades:
            r = t.exit_reason or "Unknown"
            if "PT" in r or "Target" in r: r = "Profit Targets"
            elif "Runner" in r: r = "Runner Exit"
            elif "TES" in r or "Time" in r: r = "Dynamic TES"
            elif "Stop Loss" in r or "SL" in r: r = "Stop Loss"
            reason_counts[r] = reason_counts.get(r, 0) + 1
            
        reason_labels = [f"{k} ({v})" for k, v in reason_counts.items()]
        colors_exit = ['#0ea5e9', '#8b5cf6', '#f59e0b', '#ec4899', '#64748b']
        ax3.pie(reason_counts.values(), labels=reason_labels, colors=colors_exit[:len(reason_counts)], 
                autopct='%1.1f%%', startangle=110, textprops={'fontsize': 11})
        ax3.set_title("Trade Exit Mechanisms", fontsize=14, fontweight='bold')
        
        # 4. TRADE P/L (%) DISTRIBUTION
        ax4 = axes[1, 1]
        trade_pnl_pcts = [((t.realized_pnl / (t.orig_shares * t.entry_price)) * 100) if (t.orig_shares * t.entry_price) > 0 else 0 for t in v32_trades]
        bar_colors = ['#10b981' if p >= 0 else '#f43f5e' for p in trade_pnl_pcts]
        ax4.bar(range(1, len(trade_pnl_pcts) + 1), trade_pnl_pcts, color=bar_colors, width=0.8, alpha=0.85)
        ax4.axhline(0, color='black', linewidth=0.8, linestyle='--')
        ax4.set_title("Trade Return Distribution (%)", fontsize=14, fontweight='bold')
        ax4.set_xlabel("Trade Sequence Number")
        ax4.set_ylabel("P/L % per Trade")
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        print(f"\n[DASHBOARD] Successfully saved to: {save_path}")
        
        # Show interactive plot if running inside Jupyter / Google Colab
        if 'ipykernel' in sys.modules or 'google.colab' in sys.modules:
            plt.show()
        else:
            plt.close()
    except Exception as e:
        print(f"Visualization note: Could not render interactive plot: {e}")

# ----------------------------------------------------------------------
# 7. MAIN EXECUTION PIPELINE
# ----------------------------------------------------------------------
def main(tickers: Optional[List[str]] = None, lookback_years: int = 3):
    watchlist = tickers if tickers else DEFAULT_WATCHLIST
    print("=" * 80)
    print(">> RAJAT ALPHA V67 (VERSION 3.2) - INSTITUTIONAL BACKTEST RUNNER")
    print("=" * 80)
    print(f"Loading {len(watchlist)} institutional stocks across {lookback_years} years...")
    print(f"Watchlist: {', '.join(watchlist)}")
    
    start_date = (datetime.now() - timedelta(days=lookback_years*365)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Download Benchmark
    print("Fetching QQQ benchmark...")
    qqq_df = yf.download("QQQ", start=start_date, end=end_date, progress=False)
    if isinstance(qqq_df.columns, pd.MultiIndex):
        qqq_df.columns = qqq_df.columns.get_level_values(0)
    qqq_df = calculate_indicators(qqq_df)
    
    # Download Universe Data
    all_data = {}
    for sym in watchlist:
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False)
            if df is not None and len(df) > 200:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                all_data[sym] = calculate_indicators(df)
        except Exception:
            continue
            
    print(f"Successfully processed indicators for {len(all_data)} tickers.")
    
    # Run Baseline Simulation
    print("\n[1/2] Running Old v67 Baseline Simulation...")
    baseline_trades = run_backtest_simulation(all_data, qqq_df, mode="baseline")
    m_base = generate_performance_metrics(baseline_trades, "OLD V67 BASELINE (MARKET ORDERS & FIXED 17% SL)")
    
    # Run Institutional v3.2 Simulation
    print("\n[2/2] Running New v3.2 Institutional Simulation...")
    v32_trades = run_backtest_simulation(all_data, qqq_df, mode="v32")
    m_v32 = generate_performance_metrics(v32_trades, "NEW V3.2 INSTITUTIONAL (SOEE & HYBRID ATR)")
    
    # Comparison Table
    if m_base and m_v32:
        print("\n" + "="*80)
        print("== STRATEGY UPGRADE COMPARISON TABLE ==")
        print("="*80)
        print(f"{'Performance Metric':<30} | {'Old Baseline':<20} | {'New v3.2 Institutional':<20}")
        print("-" * 76)
        print(f"{'Total Trades':<30} | {m_base['trades']:<20} | {m_v32['trades']:<20}")
        print(f"{'Win Rate (%)':<30} | {m_base['win_rate']:<19.1f}% | {m_v32['win_rate']:<19.1f}%")
        print(f"{'Total Realized P/L ($)':<30} | ${m_base['total_pnl']:<19,.2f} | ${m_v32['total_pnl']:<19,.2f}")
        print(f"{'Profit Factor':<30} | {m_base['profit_factor']:<20.2f} | {m_v32['profit_factor']:<20.2f}")
        print(f"{'Average Win ($)':<30} | ${m_base['avg_win']:<19,.2f} | ${m_v32['avg_win']:<19,.2f}")
        print(f"{'Average Loss ($)':<30} | ${m_base['avg_loss']:<19,.2f} | ${m_v32['avg_loss']:<19,.2f}")
        print(f"{'Trade Expectancy ($)':<30} | ${m_base['expectancy']:<19,.2f} | ${m_v32['expectancy']:<19,.2f}")
        print(f"{'Maximum Drawdown ($)':<30} | ${m_base['max_dd']:<19,.2f} | ${m_v32['max_dd']:<19,.2f}")
        print("="*80)
        
    # Plot Visual Dashboard
    print("\nGenerating visual performance charts...")
    plot_backtest_dashboard(v32_trades, baseline_trades, save_path="v32_backtest_dashboard.png")

if __name__ == "__main__":
    main()

