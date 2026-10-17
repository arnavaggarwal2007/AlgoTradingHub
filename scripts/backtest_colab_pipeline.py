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

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    os.system("pip install yfinance")
    import yfinance as yf

# ----------------------------------------------------------------------
# 1. WATCHLIST DEFINITION (Institutional 94-Ticker Core + Benchmarks)
# ----------------------------------------------------------------------
DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "AMD",
    "NFLX", "ADBE", "CRM", "QCOM", "TXN", "INTU", "AMAT", "BKNG", "ISRG", "LRCX",
    "MU", "PANW", "SNPS", "CDNS", "CRWD", "KLAC", "NXPI", "MELI", "MAR", "FTNT",
    "MRVL", "ABNB", "ORCL", "NOW", "PLTR", "ANET", "UBER", "DASH", "SMCI", "ARM",
    "DELL", "APP", "CRDO", "AXGN", "DUOL", "IOT", "MDB", "DDOG", "ZS", "NET"
]
BENCHMARK_SYMBOLS = ["SPY", "QQQ"]

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
    """Evaluates bar i for v3.2 Institutional criteria"""
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
        
    # Gate 2: MTF Alignment
    weekly_ok, monthly_ok = calculate_weekly_monthly_alignment(df_window)
    if not (weekly_ok and monthly_ok):
        return False, {}
        
    # Gate 3: Impulse Wave & Orderly Retracement
    impulse_lookback = min(20, len(df_window) - 1)
    slice_impulse = df_window.iloc[-impulse_lookback:-1]
    swing_high = slice_impulse['High'].max()
    idx_high = slice_impulse['High'].idxmax()
    ema_at_high = df_window.loc[idx_high, 'EMA21']
    if swing_high < ema_at_high * 1.05:
        return False, {}  # No prior markup
    if (swing_high - curr['Low']) / swing_high < 0.03:
        return False, {}  # Inadequate retracement
        
    # Gate 4: Candlestick Pattern OR Qualified Touch
    pat_found, pat_name, pat_weight = detect_candlestick_pattern(df_window)
    dist_ema21 = abs(curr['Close'] - curr['EMA21']) / curr['EMA21']
    dist_sma50 = abs(curr['Close'] - curr['SMA50']) / curr['SMA50']
    touch_found = (dist_ema21 <= 0.025) or (dist_sma50 <= 0.025)
    
    if not (pat_found or touch_found):
        return False, {}
        
    # Gate 5: Stalling Filter
    high_8 = df_window['High'].iloc[-8:].max()
    low_8 = df_window['Low'].iloc[-8:].min()
    if (high_8 - low_8) / low_8 < 0.05:
        return False, {}  # Horizontal churning
        
    # Gate 6: Shooting Star Rejection Filter
    if is_shooting_star(curr):
        return False, {}
        
    # Gate 7: Scoring
    score = 0.0
    if curr['RSI14'] > 50: score += 1.0
    if weekly_ok: score += 0.5
    if monthly_ok: score += 0.5
    if curr['Volume'] > curr['VOL_SMA21']: score += 0.5
    low_21 = df_window['Low'].iloc[-21:].min()
    if curr['Low'] <= low_21 * 1.035: score += 1.0
    if pat_found: score += pat_weight
    
    # Touch-only check requires >= 5.0 and bullish body
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
        'score': score,
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
                # Multi-stage trailing SL
                gain_pct = (high_px - t.entry_price) / t.entry_price
                if gain_pct >= 0.10:
                    t.stop_loss = max(t.stop_loss, t.entry_price * (1.03 + (gain_pct - 0.10)))
                    t.sl_stage = 3
                elif gain_pct >= 0.08:
                    t.stop_loss = max(t.stop_loss, t.entry_price)
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
                    
                # Dynamic TES Evaluation
                if t.bars_held >= t.max_hold_bars and not t.is_runner:
                    # Grant 10-day extension if consolidating above EMA21
                    if close_px > bar['EMA21'] and (close_px - t.entry_price)/t.entry_price > -0.05:
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
                    shares = max(1, int(3000.0 / entry_px))
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
# 6. PERFORMANCE REPORT GENERATOR
# ----------------------------------------------------------------------
def generate_performance_metrics(trades: List[Trade], title: str):
    if not trades:
        print(f"[{title}] No completed trades.")
        return
        
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
    print(f" 📊 {title} PERFORMANCE AUDIT (5-YEAR RETROSPECTIVE)")
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

# ----------------------------------------------------------------------
# 7. MAIN EXECUTION PIPELINE
# ----------------------------------------------------------------------
def main():
    print("🚀 Initializing Rajat Alpha v67 5-Year Institutional Backtest...")
    print(f"Loading {len(DEFAULT_WATCHLIST)} institutional growth stocks...")
    
    start_date = (datetime.now() - timedelta(days=5*365)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Download Benchmark
    print("Fetching QQQ benchmark...")
    qqq_df = yf.download("QQQ", start=start_date, end=end_date, progress=False)
    if isinstance(qqq_df.columns, pd.MultiIndex):
        qqq_df.columns = qqq_df.columns.get_level_values(0)
    qqq_df = calculate_indicators(qqq_df)
    
    # Download Universe Data
    all_data = {}
    for sym in DEFAULT_WATCHLIST:
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False)
            if df is not None and len(df) > 250:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                all_data[sym] = calculate_indicators(df)
        except Exception as e:
            continue
            
    print(f"Successfully processed indicators for {len(all_data)} tickers.")
    
    # Run Baseline Simulation
    print("\n[1/2] Running Old v67 Baseline Simulation...")
    baseline_trades = run_backtest_simulation(all_data, qqq_df, mode="baseline")
    generate_performance_metrics(baseline_trades, "OLD V67 BASELINE (MARKET ORDERS & FIXED 17% SL)")
    
    # Run Institutional v3.2 Simulation
    print("\n[2/2] Running New v3.2 Institutional Simulation...")
    v32_trades = run_backtest_simulation(all_data, qqq_df, mode="v32")
    generate_performance_metrics(v32_trades, "NEW V3.2 INSTITUTIONAL (SOEE & HYBRID ATR)")

if __name__ == "__main__":
    main()
