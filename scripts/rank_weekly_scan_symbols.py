"""
Weekly High-Conviction Stock Ranker for Rajat Alpha v67 (Version 3.2)
Evaluates scanned symbols under the exact v3.2 swing trading engine:
- Prioritized 8-stage gating
- ATR-adaptive stop loss (1.5x / 2.0x ATR)
- Multi-stage stop stepper
- 4-Tier partial profit exits (5%, 10%, 15%, 30% runner)
- Dynamic structural TES (21 days + up to two 10-day extensions)
Ranks symbols by Institutional Conviction Score and outputs Tier 1 Beasts for config/watchlist.txt
"""

import os
import sys
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WEEKLY_SCAN_SYMBOLS = [
    "CLBK", "IRDM", "CNO", "MET", "NBTB", "S", "HNGE", "HSIC", "KNSA", "NSIT",
    "LFST", "RGS", "ELF", "FROG", "U", "ANET", "CNK", "PAGP", "CHEF", "GEO",
    "GH", "CXW", "IMAX", "NDSN", "NSP", "SN", "CAKE", "TNET", "OSCR", "SNOW",
    "CRBG", "ILMN", "RVMD", "ZBRA", "NOW", "NET", "DAR", "BIIB", "EXPD", "MATX",
    "JOYY", "HAE", "LPG", "GRDN", "EHC", "VRNS", "AMRX", "AAMI", "IOSP", "FFIV",
    "KLAC", "SHOP", "TNK", "MSGS", "APH", "RBRK", "DDOG", "TWLO"
]

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
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI14'] = 100 - (100 / (1 + rs))
    
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - close.shift()).abs(),
        (df['Low'] - close.shift()).abs()
    ], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(window=14).mean()
    df['WEEKLY_EMA21'] = close.ewm(span=105, adjust=False).mean()
    df['MONTHLY_EMA10'] = close.ewm(span=210, adjust=False).mean()
    return df

def detect_pattern(curr, prev):
    c_open, c_close, c_high, c_low = curr['Open'], curr['Close'], curr['High'], curr['Low']
    p_open, p_close = prev['Open'], prev['Close']
    c_body = abs(c_close - c_open)
    c_range = max(c_high - c_low, 0.0001)
    
    if p_close < p_open and c_close > c_open:
        if c_close >= p_open and c_open <= p_close:
            return 'Bullish Engulfing', 1.0
        if c_open < prev['Low'] and c_close > (p_open + p_close) / 2 and c_close < p_open:
            return 'Bullish Piercing', 1.0
    if abs(c_low - prev['Low']) / c_low <= 0.003 and c_close > c_open:
        return 'Tweezer Bottom', 0.8
    lower_wick = min(c_open, c_close) - c_low
    upper_wick = c_high - max(c_open, c_close)
    if lower_wick >= 2.0 * c_body and upper_wick <= 0.20 * c_range and c_body > 0:
        return 'Bullish Hammer', 0.8
    if c_open < p_close and c_close > (p_open + p_close) / 2:
        return 'Upside Reversal', 0.6
    return 'None', 0.0

def calculate_ibd_rs(stock_series, bench_series):
    try:
        if len(stock_series) < 252 or len(bench_series) < 252:
            return 50.0
        p_curr, p_63, p_126, p_189, p_252 = (
            stock_series.iloc[-1], stock_series.iloc[-63],
            stock_series.iloc[-126], stock_series.iloc[-189], stock_series.iloc[-252]
        )
        weighted_perf = (
            0.40 * (p_curr / p_63 - 1) +
            0.20 * (p_63 / p_126 - 1) +
            0.20 * (p_126 / p_189 - 1) +
            0.20 * (p_189 / p_252 - 1)
        )
        bench_perf = (bench_series.iloc[-1] / bench_series.iloc[-252]) - 1.0
        return round(max(1.0, min(99.0, 50.0 + ((weighted_perf - bench_perf) * 150.0))), 1)
    except Exception:
        return 50.0

def evaluate_signal_v32(df, idx, spy_df=None):
    if idx < 25:
        return None
    curr, prev = df.iloc[idx], df.iloc[idx - 1]
    
    # 1. Trend Gating
    if not (curr['EMA21'] >= curr['SMA50'] * 0.975 and curr['SMA50'] > curr['SMA200'] and curr['Close'] > curr['SMA200']):
        return None
    
    # 2. Pullback & Stalling Checks
    lookback = df.iloc[max(0, idx - 20):idx]
    highest_high = lookback['High'].max()
    high_bar = lookback.loc[lookback['High'].idxmax()]
    if (highest_high - high_bar['EMA21']) / high_bar['EMA21'] < 0.05:
        return None
    if (highest_high - curr['Low']) / highest_high < 0.03 and sum(1 for i in range(1, 4) if df.iloc[idx - i]['Close'] < df.iloc[idx - i - 1]['Close']) < 3:
        return None
    
    # 3. Pattern / Touch Validation
    pat_name, pat_score = detect_pattern(curr, prev)
    touch_found = (curr['Low'] <= curr['EMA21'] * 1.025 and curr['Low'] >= curr['EMA21'] * 0.975) or \
                  (curr['Low'] <= curr['SMA50'] * 1.025 and curr['Low'] >= curr['SMA50'] * 0.975)
    if pat_score == 0.0 and not touch_found:
        return None
    
    # 4. Filter Quality (Weekly EMA21 & Upper Wick)
    if curr['Close'] <= curr['WEEKLY_EMA21']:
        return None
    demand_ok = curr['Low'] <= curr['LOW_21'] * 1.035
    c_range = curr['High'] - curr['Low']
    upper_wick = curr['High'] - max(curr['Open'], curr['Close'])
    c_body = abs(curr['Close'] - curr['Open'])
    if c_range > 0 and ((upper_wick / c_range > 0.50) or (upper_wick > 2.0 * c_body and upper_wick / c_range > 0.35)):
        return None
    if (lookback['High'].tail(8).max() - lookback['Low'].tail(8).min()) / lookback['Low'].tail(8).min() < 0.05:
        return None
    if (curr['Open'] - prev['Close']) / prev['Close'] > 0.04:
        return None
    
    # 5. Composite Scoring
    score = (pat_score if pat_score > 0 else 1.0) + 1.0
    if demand_ok: score += 1.0
    if curr['RSI14'] > 50: score += 1.0
    if curr['Close'] > curr['MONTHLY_EMA10']: score += 1.0
    if curr['Volume'] > curr['VOL_SMA21']: score += 1.0
    score += 1.0
    
    if pat_score == 0.0:
        if score < 5.0 or (c_body / c_range if c_range > 0 else 0) < 0.50:
            return None
    elif score < 4.0:
        return None
    
    rs_score = 50.0
    if spy_df is not None:
        rs_score = calculate_ibd_rs(df.iloc[:idx + 1]['Close'], spy_df.loc[:df.index[idx]]['Close'])
    
    atr = curr['ATR14'] if not np.isnan(curr['ATR14']) else (curr['Close'] * 0.04)
    k_atr = 1.5 if score >= 5.0 else 2.0
    init_sl = min(max(curr['Close'] - (k_atr * atr), curr['Close'] * 0.83), curr['Close'] * 0.95)
    sl_type = f'ATR-Adaptive ({k_atr}x, {((init_sl/curr["Close"])-1)*100:.1f}%)' if init_sl > curr['Close'] * 0.83 else 'Fixed (17.0%)'
    
    return {
        'entry_date': df.index[idx],
        'entry_price': curr['Close'],
        'pattern': pat_name if pat_score > 0 else 'Qualified Touch',
        'score': round(score, 1),
        'ibd_rs': rs_score,
        'initial_sl': round(init_sl, 2),
        'sl_type': sl_type,
        'atr': round(atr, 2)
    }

def simulate_trades(df, spy_df, symbol, capital_per_trade=3000.0):
    trades = []
    in_pos = False
    pos = None
    
    for i in range(25, len(df)):
        curr_bar, curr_date = df.iloc[i], df.index[i]
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
                    'tes_status': 'Base 21d',
                    'stepper_milestones': [],
                    'pt1_taken': False,
                    'pt2_taken': False,
                    'pt3_taken': False,
                    'realized_pnl': 0.0
                }
        else:
            pos['bars_held'] += 1
            high, low, close, entry = curr_bar['High'], curr_bar['Low'], curr_bar['Close'], pos['entry_price']
            if high > pos['highest_seen']:
                pos['highest_seen'] = high
            gain = (pos['highest_seen'] - entry) / entry
            
            # Partial Profit Targets
            if not pos['pt1_taken'] and high >= entry * 1.05:
                pos['pt1_taken'] = True
                pos['qty'] -= pos['orig_qty'] * 0.20
                pos['realized_pnl'] += pos['orig_qty'] * 0.20 * (entry * 1.05 - entry)
            if not pos['pt2_taken'] and high >= entry * 1.10:
                pos['pt2_taken'] = True
                pos['qty'] -= pos['orig_qty'] * 0.25
                pos['realized_pnl'] += pos['orig_qty'] * 0.25 * (entry * 1.10 - entry)
            if not pos['pt3_taken'] and high >= entry * 1.15:
                pos['pt3_taken'] = True
                pos['qty'] -= pos['orig_qty'] * 0.25
                pos['realized_pnl'] += pos['orig_qty'] * 0.25 * (entry * 1.15 - entry)
                pos['is_runner'] = True
                pos['tes_status'] = 'Runner (Exempt)'
            
            # Multi-Stage Stop Stepper
            if gain >= 0.05 and pos['sl_stage'] < 1:
                pos['sl_stage'] = 1
                pos['curr_sl'] = max(pos['curr_sl'], entry * 0.96)
                pos['stepper_milestones'].append('Stage 1 (-4%)')
            if gain >= 0.08 and pos['sl_stage'] < 2:
                pos['sl_stage'] = 2
                pos['curr_sl'] = max(pos['curr_sl'], entry * 1.01)
                pos['stepper_milestones'].append('Stage 2 (BE+1%)')
            if gain >= 0.10 and pos['sl_stage'] < 3:
                pos['sl_stage'] = 3
                pos['curr_sl'] = max(pos['curr_sl'], entry * 1.03)
                pos['stepper_milestones'].append('Stage 3 (+3%)')
            if gain >= 0.15 and pos['sl_stage'] < 4:
                pos['sl_stage'] = 4
                pos['curr_sl'] = max(pos['curr_sl'], entry * (1.0 + (gain - 0.10) - 0.05))
                pos['stepper_milestones'].append('Stage 4 (Ratchet)')
            if pos['sl_stage'] >= 4:
                pos['curr_sl'] = max(pos['curr_sl'], entry * (1.0 + (gain - 0.10) - 0.05))
            
            # Exit Conditions
            exit_reason, exit_price = None, None
            if low <= entry * 0.78:
                exit_reason = 'Catastrophic Breaker (-22%)'
                exit_price = entry * 0.78
            elif close <= pos['curr_sl']:
                exit_reason = f'Stop Loss ({"Trailing/Stepper" if pos["sl_stage"] >= 2 else "Initial SL"})'
                exit_price = close
            elif pos['bars_held'] >= (21 + (pos['tes_extensions'] * 10)) and not pos['is_runner']:
                if close >= curr_bar['EMA21'] and close >= entry * 0.95 and pos['tes_extensions'] < 2:
                    pos['tes_extensions'] += 1
                    pos['tes_status'] = f'Extended (+{pos["tes_extensions"]*10}d: >EMA21)'
                else:
                    exit_reason = f'Dynamic TES Expiry ({pos["bars_held"]}d)'
                    exit_price = close
            
            if exit_reason:
                if pos['qty'] > 0:
                    pos['realized_pnl'] += pos['qty'] * (exit_price - entry)
                trades.append({
                    'Symbol': symbol,
                    'Entry Date': pos['entry_date'].strftime('%Y-%m-%d'),
                    'Buy Price': round(pos['entry_price'], 2),
                    'Pattern': pos['pattern'],
                    'Score': pos['score'],
                    'IBD RS': pos['ibd_rs'],
                    'SL Price': round(pos['curr_sl'], 2),
                    'Initial SL': round(pos['initial_sl'], 2),
                    'SL Type': pos['sl_type'],
                    'Stepper Triggered': ' -> '.join(pos['stepper_milestones']) if pos['stepper_milestones'] else 'None (Initial SL)',
                    'TES Status': pos['tes_status'],
                    'Exit Date': curr_date.strftime('%Y-%m-%d'),
                    'Exit Price': round(exit_price, 2),
                    'Exit Reason': exit_reason,
                    'Hold Days': pos['bars_held'],
                    'Realized PnL ($)': round(pos['realized_pnl'], 2),
                    'Return (%)': round((pos['realized_pnl'] / capital_per_trade) * 100.0, 2),
                    'Is Runner': pos['is_runner']
                })
                in_pos = False
                pos = None
    return trades

def main():
    print("=" * 85)
    print(">> WEEKLY HIGH-CONVICTION STOCK RANKING ENGINE (RAJAT ALPHA V67)")
    print("=" * 85)
    unique_symbols = sorted(list(set(WEEKLY_SCAN_SYMBOLS)))
    print(f"Scanning {len(unique_symbols)} unique candidate symbols from weekly filter...")
    
    print("Downloading SPY benchmark...")
    spy_raw = yf.download('SPY', start='2023-01-01', end=datetime.now().strftime('%Y-%m-%d'), progress=False)
    if isinstance(spy_raw.columns, pd.MultiIndex):
        spy_raw.columns = spy_raw.columns.get_level_values(0)
    spy_df = spy_raw.dropna()
    
    all_trades = []
    symbol_stats = []
    
    for idx, sym in enumerate(unique_symbols, 1):
        try:
            print(f"[{idx}/{len(unique_symbols)}] Evaluating {sym}...", end='\r')
            raw = yf.download(sym, start='2023-01-01', end=datetime.now().strftime('%Y-%m-%d'), progress=False)
            if len(raw) < 200:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = calculate_indicators(raw)
            if df is None:
                continue
            trades = simulate_trades(df, spy_df, sym)
            all_trades.extend(trades)
            
            if len(trades) > 0:
                pnls = [t['Realized PnL ($)'] for t in trades]
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]
                n = len(pnls)
                wr = len(wins) / n
                pf = sum(wins) / abs(sum(losses)) if sum(losses) < 0 else 99.0
                exp = np.mean(pnls)
                p90 = np.percentile(pnls, 90)
                p10 = abs(np.percentile(pnls, 10)) if len(losses) > 0 else 1.0
                tail_r = p90 / p10
                
                # Institutional Conviction Formula
                rank_score = (wr * 40.0) + (min(pf, 5.0) * 8.0) + (min(tail_r, 4.0) * 5.0) + (min(exp, 300.0) / 15.0)
                
                tier = "Tier 1 (BEAST)" if rank_score >= 60.0 and wr >= 0.55 else ("Tier 2 (Tradable)" if wr >= 0.45 else "Tier 3 (CHOP - EXCLUDE)")
                
                symbol_stats.append({
                    'Symbol': sym,
                    'Rank Score': round(rank_score, 1),
                    'Tier': tier,
                    'Trades': n,
                    'Win Rate (%)': round(wr * 100, 1),
                    'Profit Factor': round(pf, 2),
                    'Tail Ratio': round(tail_r, 2),
                    'Avg Win ($)': round(np.mean(wins), 1) if wins else 0.0,
                    'Avg Loss ($)': round(np.mean(losses), 1) if losses else 0.0,
                    'Expectancy ($)': round(exp, 1),
                    'Total PnL ($)': round(sum(pnls), 1)
                })
        except Exception as e:
            pass

    print("\n" + "=" * 85)
    stats_df = pd.DataFrame(symbol_stats).sort_values(by='Rank Score', ascending=False).reset_index(drop=True)
    
    print("🏆 TOP 15 HIGH-CONVICTION STOCKS FOR NEXT WEEK (FILTERED FROM SCAN)")
    print("=" * 85)
    print(stats_df.head(15).to_string(index=False))
    
    tier1_beasts = stats_df[stats_df['Tier'] == "Tier 1 (BEAST)"]['Symbol'].tolist()
    print("\n" + "=" * 85)
    print(f"🔥 TIER 1 BEAST STOCKS DETECTED: {len(tier1_beasts)} SYMBOLS")
    print("=" * 85)
    print(",".join(tier1_beasts))
    
    # Save ranked CSV
    stats_df.to_csv("docs/weekly_scanned_symbols_ranked.csv", index=False)
    print("\n📁 Saved complete rankings: docs/weekly_scanned_symbols_ranked.csv")
    
    # Save watchlist
    with open("config/weekly_high_conviction_watchlist.txt", "w") as f:
        f.write(",".join(tier1_beasts) + "\n")
    print("📁 Saved watchlist: config/weekly_high_conviction_watchlist.txt")
    
    # Save trade log
    trades_df = pd.DataFrame(all_trades)
    trades_df.to_csv("docs/weekly_scan_all_trades.csv", index=False)
    print(f"📁 Saved all {len(trades_df)} historical trades: docs/weekly_scan_all_trades.csv")

if __name__ == '__main__':
    main()
