"""
Rajat Alpha v67 (Version 3.2) - Scanned Watchlist Empirical Backtester
Analyzes the user's weekly scanned symbols (21 EMA > 50 SMA > 150 SMA > 200 SMA)
Generates comprehensive trade logs, symbol rankings, and suitability tiers.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure clean ASCII logging for cross-platform compatibility
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# 1. Technical Indicators Calculator
def calculate_indicators(df):
    if len(df) < 200:
        return None
    df = df.copy()
    close = df['Close']
    df['EMA21'] = close.ewm(span=21, adjust=False).mean()
    df['SMA50'] = close.rolling(window=50).mean()
    df['SMA150'] = close.rolling(window=150).mean()
    df['SMA200'] = close.rolling(window=200).mean()
    df['VOL_SMA21'] = df['Volume'].rolling(window=21).mean()
    df['LOW_21'] = df['Low'].rolling(window=21).min()

    # RSI 14
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI14'] = 100 - (100 / (1 + rs))

    # ATR 14
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - close.shift()).abs()
    low_close = (df['Low'] - close.shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(window=14).mean()

    # Weekly Trend Proxy (Resample close to 5-day EMA)
    df['WEEKLY_EMA21'] = close.ewm(span=105, adjust=False).mean()
    df['MONTHLY_EMA10'] = close.ewm(span=210, adjust=False).mean()

    return df

# 2. Candle Pattern & Physics Detector
def detect_pattern(curr, prev):
    c_open, c_close, c_high, c_low = curr['Open'], curr['Close'], curr['High'], curr['Low']
    p_open, p_close = prev['Open'], prev['Close']
    c_body = abs(c_close - c_open)
    c_range = c_high - c_low if (c_high - c_low) > 0.0001 else 0.0001

    # Bullish Engulfing (+1.0)
    if p_close < p_open and c_close > c_open:
        if c_close >= p_open and c_open <= p_close:
            return "Bullish Engulfing", 1.0

    # Bullish Piercing (+1.0)
    if p_close < p_open and c_close > c_open:
        p_mid = (p_open + p_close) / 2
        if c_open < prev['Low'] and c_close > p_mid and c_close < p_open:
            return "Bullish Piercing", 1.0

    # Tweezer Bottom (+0.8)
    if abs(c_low - prev['Low']) / c_low <= 0.003 and c_close > c_open:
        return "Tweezer Bottom", 0.8

    # Bullish Hammer (+0.8)
    lower_wick = min(c_open, c_close) - c_low
    upper_wick = c_high - max(c_open, c_close)
    if (lower_wick >= 2.0 * c_body) and (upper_wick <= 0.20 * c_range) and c_body > 0:
        return "Bullish Hammer", 0.8

    # Upside Reversal (+0.6)
    if c_open < p_close and c_close > ((p_open + p_close) / 2):
        return "Upside Reversal", 0.6

    return "None", 0.0

# 3. IBD Relative Strength Score vs Benchmark
def calculate_ibd_rs(stock_series, benchmark_series):
    try:
        if len(stock_series) < 252 or len(benchmark_series) < 252:
            return 50.0
        # 40% Q4, 20% Q3, 20% Q2, 20% Q1
        p_curr = stock_series.iloc[-1]
        p_63 = stock_series.iloc[-63]
        p_126 = stock_series.iloc[-126]
        p_189 = stock_series.iloc[-189]
        p_252 = stock_series.iloc[-252]

        perf_q4 = (p_curr / p_63) - 1.0
        perf_q3 = (p_63 / p_126) - 1.0
        perf_q2 = (p_126 / p_189) - 1.0
        perf_q1 = (p_189 / p_252) - 1.0
        weighted_perf = (0.40 * perf_q4) + (0.20 * perf_q3) + (0.20 * perf_q2) + (0.20 * perf_q1)

        b_curr = benchmark_series.iloc[-1]
        b_252 = benchmark_series.iloc[-252]
        bench_perf = (b_curr / b_252) - 1.0

        rs_raw = (weighted_perf - bench_perf) * 100.0
        rs_score = max(1.0, min(99.0, 50.0 + (rs_raw * 1.5)))
        return round(rs_score, 1)
    except:
        return 50.0

# 4. Prioritized Signal Evaluator
def evaluate_signal_v32(df, idx, spy_df=None):
    if idx < 25:
        return None

    curr = df.iloc[idx]
    prev = df.iloc[idx - 1]

    # Gate 1 & 1.5: Market Structure
    if not (curr['EMA21'] >= curr['SMA50'] * 0.975 and curr['SMA50'] > curr['SMA200'] and curr['Close'] > curr['SMA200']):
        return None

    # Gate 2: Preceding Impulse Wave & Orderly Pullback
    lookback = df.iloc[max(0, idx - 20):idx]
    highest_high = lookback['High'].max()
    high_idx = lookback['High'].idxmax()
    high_bar = lookback.loc[high_idx]
    
    if (highest_high - high_bar['EMA21']) / high_bar['EMA21'] < 0.05:
        return None  # No +5% impulse above EMA21
    
    pullback_pct = (highest_high - curr['Low']) / highest_high
    lower_closes = sum(1 for i in range(1, 4) if df.iloc[idx - i]['Close'] < df.iloc[idx - i - 1]['Close'])
    if pullback_pct < 0.03 and lower_closes < 3:
        return None  # Not an orderly pullback

    # Gate 3: Pattern OR Touch
    pat_name, pat_score = detect_pattern(curr, prev)
    touch_found = (curr['Low'] <= curr['EMA21'] * 1.025 and curr['Low'] >= curr['EMA21'] * 0.975) or \
                  (curr['Low'] <= curr['SMA50'] * 1.025 and curr['Low'] >= curr['SMA50'] * 0.975)

    if pat_score == 0.0 and not touch_found:
        return None

    # Gate 4: Weekly MTF (Mandatory Prerequisite)
    if curr['Close'] <= curr['WEEKLY_EMA21']:
        return None

    # Gate 5: Demand Zone
    demand_ok = (curr['Low'] <= curr['LOW_21'] * 1.035)

    # Gate 6: Exhaustion Filters (Shooting Star, Stalling, Extension)
    c_range = curr['High'] - curr['Low']
    upper_wick = curr['High'] - max(curr['Open'], curr['Close'])
    c_body = abs(curr['Close'] - curr['Open'])
    if c_range > 0 and ((upper_wick / c_range > 0.50) or (upper_wick > 2.0 * c_body and upper_wick / c_range > 0.35)):
        return None  # Shooting star rejection

    range_8d = (lookback['High'].tail(8).max() - lookback['Low'].tail(8).min()) / lookback['Low'].tail(8).min()
    if range_8d < 0.05:
        return None  # Stalling horizontal churn

    if (curr['Open'] - prev['Close']) / prev['Close'] > 0.04:
        return None  # Extended gap-up

    # Gate 7: Scoring
    score = 0.0
    # 1. Pattern or Touch
    if pat_score > 0:
        score += pat_score
    elif touch_found:
        score += 1.0
    # 2. Weekly MTF (+1.0)
    score += 1.0
    # 3. Demand Zone (+1.0)
    if demand_ok:
        score += 1.0
    # 4. RSI14 > 50 (+1.0)
    if curr['RSI14'] > 50:
        score += 1.0
    # 5. Monthly MTF (+1.0)
    if curr['Close'] > curr['MONTHLY_EMA10']:
        score += 1.0
    # 6. Volume (+1.0)
    if curr['Volume'] > curr['VOL_SMA21']:
        score += 1.0
    # 7. Touch State Freshness (+1.0)
    score += 1.0

    # Touch-Only Dual Gate
    if pat_score == 0.0:
        c_body_ratio = c_body / c_range if c_range > 0 else 0
        close_pos = (curr['Close'] - curr['Low']) / c_range if c_range > 0 else 0
        if score < 5.0 or c_body_ratio < 0.50 or close_pos < 0.67:
            return None

    if score < 4.0:
        return None

    # Informational IBD RS
    rs_score = 50.0
    if spy_df is not None:
        stock_series = df.iloc[:idx+1]['Close']
        bench_series = spy_df.loc[:df.index[idx]]['Close']
        rs_score = calculate_ibd_rs(stock_series, bench_series)

    # Initial Stop Loss Calculation (ATR-Hybrid)
    atr = curr['ATR14'] if not np.isnan(curr['ATR14']) else (curr['Close'] * 0.04)
    k_atr = 1.5 if score >= 5.0 else 2.0
    atr_sl = curr['Close'] - (k_atr * atr)
    hard_sl = curr['Close'] * (1.0 - 0.17)
    floor_sl = curr['Close'] * (1.0 - 0.05)
    
    init_sl = max(atr_sl, hard_sl)
    init_sl = min(init_sl, floor_sl)
    sl_type = f"ATR-Adaptive ({k_atr}x, {((init_sl/curr['Close'])-1)*100:.1f}%)" if init_sl > hard_sl else "Fixed (17.0%)"

    return {
        'entry_date': df.index[idx],
        'entry_price': curr['Close'],
        'pattern': pat_name if pat_score > 0 else "Qualified Touch",
        'score': round(score, 1),
        'ibd_rs': rs_score,
        'initial_sl': round(init_sl, 2),
        'sl_type': sl_type,
        'atr': round(atr, 2)
    }

# 5. Position Simulation with v3.2 Risk & Harvesting
def simulate_trades(df, spy_df, symbol, capital_per_trade=3000.0):
    trades = []
    in_pos = False
    pos = None

    for i in range(25, len(df)):
        curr_bar = df.iloc[i]
        curr_date = df.index[i]

        if not in_pos:
            sig = evaluate_signal_v32(df, i, spy_df)
            if sig:
                in_pos = True
                qty = capital_per_trade / sig['entry_price']
                pos = {
                    'symbol': symbol,
                    'entry_date': sig['entry_date'],
                    'entry_price': sig['entry_price'],
                    'pattern': sig['pattern'],
                    'score': sig['score'],
                    'ibd_rs': sig['ibd_rs'],
                    'initial_sl': sig['initial_sl'],
                    'sl_type': sig['sl_type'],
                    'curr_sl': sig['initial_sl'],
                    'sl_stage': 0,
                    'qty': qty,
                    'orig_qty': qty,
                    'bars_held': 0,
                    'highest_seen': sig['entry_price'],
                    'is_runner': False,
                    'tes_extensions': 0,
                    'tes_status': "Base 21d",
                    'stepper_milestones': [],
                    'pt1_taken': False,
                    'pt2_taken': False,
                    'pt3_taken': False,
                    'realized_pnl': 0.0,
                    'exits': []
                }
        else:
            pos['bars_held'] += 1
            high = curr_bar['High']
            low = curr_bar['Low']
            close = curr_bar['Close']
            entry = pos['entry_price']

            if high > pos['highest_seen']:
                pos['highest_seen'] = high

            # Gain from entry
            high_gain = (pos['highest_seen'] - entry) / entry

            # 4-Tier Profit Exits
            if not pos['pt1_taken'] and high >= entry * 1.05:
                pos['pt1_taken'] = True
                pt_qty = pos['orig_qty'] * 0.20
                pos['qty'] -= pt_qty
                pnl = pt_qty * (entry * 1.05 - entry)
                pos['realized_pnl'] += pnl
                pos['exits'].append(('PT1 (+5%)', curr_date, entry * 1.05, pnl))

            if not pos['pt2_taken'] and high >= entry * 1.10:
                pos['pt2_taken'] = True
                pt_qty = pos['orig_qty'] * 0.25
                pos['qty'] -= pt_qty
                pnl = pt_qty * (entry * 1.10 - entry)
                pos['realized_pnl'] += pnl
                pos['exits'].append(('PT2 (+10%)', curr_date, entry * 1.10, pnl))

            if not pos['pt3_taken'] and high >= entry * 1.15:
                pos['pt3_taken'] = True
                pt_qty = pos['orig_qty'] * 0.25
                pos['qty'] -= pt_qty
                pnl = pt_qty * (entry * 1.15 - entry)
                pos['realized_pnl'] += pnl
                pos['is_runner'] = True
                pos['tes_status'] = "Runner (Exempt)"
                pos['exits'].append(('PT3 (+15%)', curr_date, entry * 1.15, pnl))

            # Multi-Stage Stop Loss Stepper
            if high_gain >= 0.05 and pos['sl_stage'] < 1:
                pos['sl_stage'] = 1
                pos['curr_sl'] = max(pos['curr_sl'], entry * 0.96)
                pos['stepper_milestones'].append("Stage 1 (-4%)")

            if high_gain >= 0.08 and pos['sl_stage'] < 2:
                pos['sl_stage'] = 2
                pos['curr_sl'] = max(pos['curr_sl'], entry * 1.01)
                pos['stepper_milestones'].append("Stage 2 (BE+1%)")

            if high_gain >= 0.10 and pos['sl_stage'] < 3:
                pos['sl_stage'] = 3
                pos['curr_sl'] = max(pos['curr_sl'], entry * 1.03)
                pos['stepper_milestones'].append("Stage 3 (+3%)")

            if high_gain >= 0.15 and pos['sl_stage'] < 4:
                pos['sl_stage'] = 4
                extra_gain = high_gain - 0.10
                ratchet_sl = entry * (1.0 + extra_gain - 0.05)
                pos['curr_sl'] = max(pos['curr_sl'], ratchet_sl)
                pos['stepper_milestones'].append("Stage 4 (Ratchet)")

            if pos['sl_stage'] >= 4:
                extra_gain = high_gain - 0.10
                ratchet_sl = entry * (1.0 + extra_gain - 0.05)
                pos['curr_sl'] = max(pos['curr_sl'], ratchet_sl)

            # Check Stop Loss Exit (Daily Close Confirmation)
            exit_reason = None
            exit_price = None

            # Catastrophic breaker
            if low <= entry * 0.78:
                exit_reason = "Catastrophic Breaker (-22%)"
                exit_price = entry * 0.78
            # Stop loss breach on close
            elif close <= pos['curr_sl']:
                exit_reason = f"Stop Loss ({'Trailing/Stepper' if pos['sl_stage'] >= 2 else 'Initial SL'})"
                exit_price = close
            # Dynamic Structural TES Check
            elif pos['bars_held'] >= (21 + (pos['tes_extensions'] * 10)) and not pos['is_runner']:
                # Minervini Extension: Consolidating above 21 EMA & within 5% of entry
                if close >= curr_bar['EMA21'] and close >= entry * 0.95 and pos['tes_extensions'] < 2:
                    pos['tes_extensions'] += 1
                    pos['tes_status'] = f"Extended (+{pos['tes_extensions']*10}d: >EMA21)"
                else:
                    exit_reason = f"Dynamic TES Expiry ({pos['bars_held']}d)"
                    exit_price = close

            if exit_reason:
                rem_qty = pos['qty']
                if rem_qty > 0:
                    pnl = rem_qty * (exit_price - entry)
                    pos['realized_pnl'] += pnl
                    pos['exits'].append((exit_reason, curr_date, exit_price, pnl))

                total_pnl = pos['realized_pnl']
                pnl_pct = (total_pnl / capital_per_trade) * 100.0

                trades.append({
                    'Symbol': symbol,
                    'Entry Date': pos['entry_date'].strftime('%Y-%m-%d'),
                    'Buy Price': round(pos['entry_price'], 2),
                    'Pattern': pos['pattern'],
                    'Score': pos['score'],
                    'IBD RS': pos['ibd_rs'],
                    'SL Price': pos['curr_sl'],
                    'Initial SL': pos['initial_sl'],
                    'SL Type': pos['sl_type'],
                    'Stepper Triggered': " -> ".join(pos['stepper_milestones']) if pos['stepper_milestones'] else "None (Initial SL)",
                    'TES Status': pos['tes_status'],
                    'Exit Date': curr_date.strftime('%Y-%m-%d'),
                    'Exit Price': round(exit_price, 2),
                    'Exit Reason': exit_reason,
                    'Hold Days': pos['bars_held'],
                    'Realized PnL ($)': round(total_pnl, 2),
                    'Return (%)': round(pnl_pct, 2),
                    'Is Runner': pos['is_runner']
                })

                in_pos = False
                pos = None

    return trades

def run_scanned_universe_audit(csv_path):
    log(f"Reading scan CSV: {csv_path}")
    raw_df = pd.read_csv(csv_path)
    symbols = raw_df['Symbol'].dropna().unique().tolist()
    log(f"Extracted {len(symbols)} symbols from scan universe.")

    # Download SPY benchmark
    log("Downloading SPY benchmark...")
    spy_raw = yf.download('SPY', start='2023-01-01', end='2026-10-18', progress=False)
    if isinstance(spy_raw.columns, pd.MultiIndex):
        spy_raw.columns = spy_raw.columns.get_level_values(0)
    spy_df = spy_raw.dropna()

    all_trades = []
    symbol_stats = []

    log(f"Starting simulation across {len(symbols)} symbols...")
    for idx, sym in enumerate(symbols, 1):
        try:
            raw = yf.download(sym, start='2023-01-01', end='2026-10-18', progress=False)
            if len(raw) < 250:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            
            df = calculate_indicators(raw)
            if df is None:
                continue

            trades = simulate_trades(df, spy_df, sym)
            all_trades.extend(trades)

            # Calculate symbol level stats
            n_trades = len(trades)
            if n_trades > 0:
                wins = sum(1 for t in trades if t['Realized PnL ($)'] > 0)
                win_rate = (wins / n_trades) * 100.0
                tot_pnl = sum(t['Realized PnL ($)'] for t in trades)
                gross_win = sum(t['Realized PnL ($)'] for t in trades if t['Realized PnL ($)'] > 0)
                gross_loss = abs(sum(t['Realized PnL ($)'] for t in trades if t['Realized PnL ($)'] < 0))
                pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
                avg_ret = np.mean([t['Return (%)'] for t in trades])

                # Suitability Ranking Tier
                if win_rate >= 60.0 and pf >= 1.90 and tot_pnl > 500:
                    tier = "TIER 1: PRIME CANDIDATE (Add to Watchlist)"
                elif win_rate >= 50.0 and pf >= 1.25 and tot_pnl > 0:
                    tier = "TIER 2: SECONDARY (Selective)"
                else:
                    tier = "TIER 3: CHOP / AVOID (Do Not Add)"

                symbol_stats.append({
                    'Symbol': sym,
                    'Sector': raw_df.loc[raw_df['Symbol'] == sym, 'Sector'].values[0] if 'Sector' in raw_df.columns else "N/A",
                    'Total Trades': n_trades,
                    'Win Rate (%)': round(win_rate, 1),
                    'Total PnL ($)': round(tot_pnl, 2),
                    'Profit Factor': round(pf, 2),
                    'Avg Return (%)': round(avg_ret, 2),
                    'Suitability Tier': tier
                })
            else:
                symbol_stats.append({
                    'Symbol': sym,
                    'Sector': raw_df.loc[raw_df['Symbol'] == sym, 'Sector'].values[0] if 'Sector' in raw_df.columns else "N/A",
                    'Total Trades': 0,
                    'Win Rate (%)': 0.0,
                    'Total PnL ($)': 0.0,
                    'Profit Factor': 0.0,
                    'Avg Return (%)': 0.0,
                    'Suitability Tier': "NO SIGNALS (Too Strict / Extended)"
                })

        except Exception as e:
            log(f"Error processing {sym}: {e}")

    trades_df = pd.DataFrame(all_trades)
    stats_df = pd.DataFrame(symbol_stats).sort_values(by='Total PnL ($)', ascending=False)

    # Save outputs
    os.makedirs('docs', exist_ok=True)
    trades_path = 'docs/scanned_watchlist_trade_log.csv'
    stats_path = 'docs/scanned_watchlist_ranking.csv'
    trades_df.to_csv(trades_path, index=False)
    stats_df.to_csv(stats_path, index=False)

    log(f"Trade log saved: {trades_path} ({len(trades_df)} total trades)")
    log(f"Ranking report saved: {stats_path} ({len(stats_df)} symbols evaluated)")

    # Print Summary Table
    print("\n" + "=" * 95)
    print("TOP 15 BEST SUITABLE STOCKS TO MOVE INTO WATCHLIST (RANKED BY PNL & PROFIT FACTOR)")
    print("=" * 95)
    top_candidates = stats_df[stats_df['Total Trades'] > 0].head(15)
    print(top_candidates[['Symbol', 'Sector', 'Total Trades', 'Win Rate (%)', 'Total PnL ($)', 'Profit Factor', 'Suitability Tier']].to_string(index=False))

    print("\n" + "=" * 95)
    print("PORTFOLIO AGGREGATE SUMMARY (SCANNED UNIVERSE 2023-2026)")
    print("=" * 95)
    tot_trades = len(trades_df)
    tot_wins = sum(1 for t in all_trades if t['Realized PnL ($)'] > 0)
    win_pct = (tot_wins / tot_trades * 100.0) if tot_trades > 0 else 0.0
    tot_pnl = sum(t['Realized PnL ($)'] for t in all_trades)
    gross_w = sum(t['Realized PnL ($)'] for t in all_trades if t['Realized PnL ($)'] > 0)
    gross_l = abs(sum(t['Realized PnL ($)'] for t in all_trades if t['Realized PnL ($)'] < 0))
    tot_pf = (gross_w / gross_l) if gross_l > 0 else 99.0

    print(f"Total Trades Taken     : {tot_trades}")
    print(f"Total Realized PnL     : +${tot_pnl:,.2f}")
    print(f"Portfolio Win Rate     : {win_pct:.1f}% ({tot_wins}/{tot_trades})")
    print(f"Portfolio Profit Factor: {tot_pf:.2f}")

    # Plot Visual Dashboard
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#0B0F19')

    # Subplot 1: Equity Curve
    ax1 = axes[0, 0]
    ax1.set_facecolor('#111827')
    trades_df_sorted = trades_df.sort_values(by='Exit Date')
    equity = trades_df_sorted['Realized PnL ($)'].cumsum()
    ax1.plot(range(len(equity)), equity, color='#10B981', linewidth=2.0, label='v3.2 Realized PnL')
    ax1.set_title('Cumulative Realized Equity ($) - Scanned Watchlist', color='#E5E7EB', fontsize=11, fontweight='bold')
    ax1.set_xlabel('Trade Sequence', color='#9CA3AF', fontsize=9)
    ax1.set_ylabel('Realized PnL ($)', color='#9CA3AF', fontsize=9)
    ax1.tick_params(colors='#9CA3AF')
    ax1.grid(True, linestyle='--', alpha=0.2, color='#6B7280')

    # Subplot 2: Top 10 Best Symbols vs Worst
    ax2 = axes[0, 1]
    ax2.set_facecolor('#111827')
    active_stats = stats_df[stats_df['Total Trades'] > 0]
    top_plot = pd.concat([active_stats.head(5), active_stats.tail(5)])
    colors_bar = ['#10B981' if p > 0 else '#EF4444' for p in top_plot['Total PnL ($)']]
    ax2.barh(top_plot['Symbol'], top_plot['Total PnL ($)'], color=colors_bar)
    ax2.set_title('Top 5 vs Bottom 5 Symbols by Realized PnL ($)', color='#E5E7EB', fontsize=11, fontweight='bold')
    ax2.set_xlabel('Realized PnL ($)', color='#9CA3AF', fontsize=9)
    ax2.tick_params(colors='#9CA3AF')
    ax2.grid(True, linestyle='--', alpha=0.2, color='#6B7280')

    # Subplot 3: Exit Reasons Breakdown
    ax3 = axes[1, 0]
    ax3.set_facecolor('#111827')
    exit_counts = trades_df['Exit Reason'].value_counts()
    ax3.pie(exit_counts.values, labels=exit_counts.index, autopct='%1.1f%%',
            colors=['#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444', '#EC4899'][:len(exit_counts)],
            textprops={'color': '#E5E7EB', 'fontsize': 8})
    ax3.set_title('Exit Mechanisms Breakdown', color='#E5E7EB', fontsize=11, fontweight='bold')

    # Subplot 4: Trade PnL % Distribution
    ax4 = axes[1, 1]
    ax4.set_facecolor('#111827')
    returns = trades_df['Return (%)']
    ax4.hist(returns, bins=25, color='#3B82F6', edgecolor='#1E3A8A', alpha=0.85)
    ax4.axvline(0, color='#EF4444', linestyle='--', linewidth=1.5)
    ax4.set_title('Trade Return % Distribution', color='#E5E7EB', fontsize=11, fontweight='bold')
    ax4.set_xlabel('Return (%)', color='#9CA3AF', fontsize=9)
    ax4.set_ylabel('Frequency', color='#9CA3AF', fontsize=9)
    ax4.tick_params(colors='#9CA3AF')
    ax4.grid(True, linestyle='--', alpha=0.2, color='#6B7280')

    plt.tight_layout()
    chart_path = 'docs/scanned_watchlist_dashboard.png'
    plt.savefig(chart_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    log(f"Chart saved: {chart_path}")

if __name__ == '__main__':
    csv_file = r"C:\Users\Rajat\Downloads\Up_trend_Price near 50SMA 10_20_50_150_200_2026-10-18_2daf7.csv"
    run_scanned_universe_audit(csv_file)

