"""
4-Configuration Portfolio Comparator for Rajat Alpha v67 (Version 3.2)
Simulates realistic chronological execution of 4 distinct trading configurations:
- Enforces max open positions limit
- Enforces max trades per day
- Prioritizes by signal score when slots are competitive
- Tracks cash, allocated dollars, equity, and drawdowns
- Exports 4 detailed trade logs with 'Execution Status' (EXECUTED vs SKIPPED)
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CONFIG_PRESETS = {
    "Config 1: Standard Production": {
        "min_score": 4.0,
        "max_open": 5,
        "alloc_pct": 0.20,
        "max_trades_per_day": 3,
        "slippage_pct": 0.0015,
        "desc": "Score >= 4.0, Max 5 Open, 20% Alloc, Max 3/Day"
    },
    "Config 2: High-Conviction Conservative": {
        "min_score": 5.0,
        "max_open": 4,
        "alloc_pct": 0.25,
        "max_trades_per_day": 2,
        "slippage_pct": 0.0015,
        "desc": "Score >= 5.0, Max 4 Open, 25% Alloc, Max 2/Day (Strict Filters)"
    },
    "Config 3: Aggressive Growth": {
        "min_score": 4.0,
        "max_open": 5,
        "alloc_pct": 0.20,
        "max_trades_per_day": 4,
        "slippage_pct": 0.0015,
        "desc": "Score >= 4.0, Max 5 Open, 20% Alloc, Max 4/Day (Fast Turnover)"
    },
    "Config 4: Institutional Prop Spec": {
        "min_score": 4.5,
        "max_open": 6,
        "alloc_pct": 0.15,
        "max_trades_per_day": 2,
        "slippage_pct": 0.0010,
        "desc": "Score >= 4.5, Max 6 Open, 15% Alloc, Low Risk Floor"
    }
}

def simulate_portfolio_config(trades_df, cfg, initial_capital=10000.0):
    min_score = cfg['min_score']
    max_open = cfg['max_open']
    alloc_pct = cfg['alloc_pct']
    max_daily = cfg['max_trades_per_day']
    slippage = cfg['slippage_pct']

    df = trades_df.copy()
    df['Entry Date'] = pd.to_datetime(df['Entry Date'])
    df['Exit Date'] = pd.to_datetime(df['Exit Date'])
    df = df.sort_values(by=['Entry Date', 'Score'], ascending=[True, False]).reset_index(drop=True)

    cash = initial_capital
    active_pos = []
    executed_trades = []
    skipped_trades = []
    equity_history = []
    hwm = initial_capital

    all_dates = sorted(list(set(df['Entry Date'].tolist() + df['Exit Date'].tolist())))

    for d in all_dates:
        # 1. Release exited positions
        still_open = []
        for p in active_pos:
            if p['exit_date'] <= d:
                cash += p['pos_val'] + p['pnl']
                executed_trades.append(p)
            else:
                still_open.append(p)
        active_pos = still_open

        # 2. Process candidate entries on date d
        candidates = df[df['Entry Date'] == d]
        trades_entered_today = 0

        for _, t in candidates.iterrows():
            score = t['Score']
            sym = t['Symbol']
            base_row = t.to_dict()
            if hasattr(base_row.get('Entry Date'), 'strftime'):
                base_row['Entry Date'] = base_row['Entry Date'].strftime('%Y-%m-%d')
            if hasattr(base_row.get('Exit Date'), 'strftime'):
                base_row['Exit Date'] = base_row['Exit Date'].strftime('%Y-%m-%d')

            # Check Score Gate
            if score < min_score:
                rec = dict(base_row)
                rec['Execution Status'] = f'SKIPPED (Score {score} < {min_score})'
                rec['Allocated ($)'] = 0.0
                rec['Realized PnL ($)'] = 0.0
                rec['Ending Equity ($)'] = cash + sum(p['pos_val'] for p in active_pos)
                skipped_trades.append(rec)
                continue

            # Check Max Daily Limit
            if trades_entered_today >= max_daily:
                rec = dict(base_row)
                rec['Execution Status'] = f'SKIPPED (Daily Limit {max_daily} Met)'
                rec['Allocated ($)'] = 0.0
                rec['Realized PnL ($)'] = 0.0
                rec['Ending Equity ($)'] = cash + sum(p['pos_val'] for p in active_pos)
                skipped_trades.append(rec)
                continue

            # Check Max Concurrent Open Positions Limit
            if len(active_pos) >= max_open:
                rec = dict(base_row)
                rec['Execution Status'] = f'SKIPPED (Max Capacity {max_open} Full)'
                rec['Allocated ($)'] = 0.0
                rec['Realized PnL ($)'] = 0.0
                rec['Ending Equity ($)'] = cash + sum(p['pos_val'] for p in active_pos)
                skipped_trades.append(rec)
                continue

            # Check Available Cash
            curr_equity = cash + sum(p['pos_val'] for p in active_pos)
            pos_size = min(curr_equity * alloc_pct, cash)
            if pos_size < 100.0:
                rec = dict(base_row)
                rec['Execution Status'] = 'SKIPPED (Insufficient Cash)'
                rec['Allocated ($)'] = 0.0
                rec['Realized PnL ($)'] = 0.0
                rec['Ending Equity ($)'] = curr_equity
                skipped_trades.append(rec)
                continue

            # Enter Position
            cash -= pos_size
            trades_entered_today += 1
            ret_net = (t['Return (%)'] / 100.0) - slippage
            pnl_dollars = pos_size * ret_net

            rec = dict(base_row)
            rec['Execution Status'] = 'EXECUTED'
            rec['Return (%)'] = round(ret_net * 100.0, 2)
            rec['Allocated ($)'] = round(pos_size, 2)
            rec['Realized PnL ($)'] = round(pnl_dollars, 2)
            rec['Ending Equity ($)'] = round(curr_equity + pnl_dollars, 2)
            # Internal fields for tracking
            rec['pos_val'] = pos_size
            rec['pnl'] = pnl_dollars
            rec['exit_date'] = t['Exit Date']
            active_pos.append(rec)

        # Record daily equity snapshot
        curr_total = cash + sum(p['pos_val'] for p in active_pos)
        if curr_total > hwm:
            hwm = curr_total
        dd = (hwm - curr_total) / hwm
        equity_history.append({
            'Date': d, 'Equity': curr_total, 'Cash': cash,
            'Invested': sum(p['pos_val'] for p in active_pos),
            'Open Positions': len(active_pos), 'Drawdown (%)': dd * 100.0
        })

    # Flush remaining active positions
    for p in active_pos:
        cash += p['pos_val'] + p['pnl']
        executed_trades.append(p)

    final_equity = cash
    total_gain = ((final_equity / initial_capital) - 1.0) * 100.0
    net_profit = final_equity - initial_capital

    eq_df = pd.DataFrame(equity_history)
    max_dd = eq_df['Drawdown (%)'].max() if len(eq_df) > 0 else 0.0

    acc_df = pd.DataFrame(executed_trades)
    skip_df = pd.DataFrame(skipped_trades)

    wins = acc_df[acc_df['pnl'] > 0] if 'pnl' in acc_df.columns else pd.DataFrame()
    losses = acc_df[acc_df['pnl'] < 0] if 'pnl' in acc_df.columns else pd.DataFrame()
    wr = (len(wins) / len(acc_df)) * 100.0 if len(acc_df) > 0 else 0.0
    pf = (wins['pnl'].sum() / abs(losses['pnl'].sum())) if len(losses) > 0 and losses['pnl'].sum() != 0 else 99.0

    days_span = max(1, (df['Exit Date'].max() - df['Entry Date'].min()).days)
    years = max(0.5, days_span / 365.25)
    cagr = (((final_equity / initial_capital) ** (1.0 / years)) - 1.0) * 100.0

    # Build clean master trade log combining executed and skipped with ALL strategy attributes
    combined_log = pd.concat([acc_df, skip_df]).sort_values(by=['Entry Date', 'Score'], ascending=[True, False]).reset_index(drop=True)
    for col in ['pos_val', 'pnl', 'exit_date']:
        if col in combined_log.columns:
            combined_log = combined_log.drop(columns=[col])

    metrics = {
        'Signals in Universe': len(df),
        'Trades Executed': len(acc_df),
        'Trades Skipped': len(skip_df),
        'Execution Rate': f"{(len(acc_df)/len(df))*100:.1f}%",
        'Starting Capital': f"${initial_capital:,.2f}",
        'Ending Equity': f"${final_equity:,.2f}",
        'Net Profit': f"+${net_profit:,.2f}",
        'Total Return': f"+{total_gain:.1f}%",
        'Est. CAGR': f"{cagr:.1f}% / yr",
        'Max Drawdown': f"-{max_dd:.1f}%",
        'Win Rate': f"{wr:.1f}%",
        'Profit Factor': f"{pf:.2f}",
        'equity_df': eq_df,
        'combined_log': combined_log
    }
    return metrics

def run_comparator():
    log_path = "docs/weekly_scan_all_trades.csv"
    if not os.path.exists(log_path):
        log_path = "docs/scanned_watchlist_trade_log.csv"
    if not os.path.exists(log_path):
        print("Error: Trade log not found.")
        return

    trades_df = pd.read_csv(log_path)
    print("=" * 85)
    print(">> MULTI-CONFIGURATION PORTFOLIO COMPARATOR & VISUALIZER")
    print(f"Loaded {len(trades_df)} candidate signals from {log_path}")
    print("=" * 85)

    results = {}
    summary_rows = []

    for name, cfg in CONFIG_PRESETS.items():
        res = simulate_portfolio_config(trades_df, cfg)
        results[name] = res
        summary_rows.append({
            'Configuration': name,
            'Description': cfg['desc'],
            'Signals': res['Signals in Universe'],
            'Executed': res['Trades Executed'],
            'Skipped': res['Trades Skipped'],
            'Ending Equity': res['Ending Equity'],
            'Net Profit': res['Net Profit'],
            'Total Return': res['Total Return'],
            'CAGR': res['Est. CAGR'],
            'Max Drawdown': res['Max Drawdown'],
            'Win Rate': res['Win Rate'],
            'Profit Factor': res['Profit Factor']
        })

    summary_df = pd.DataFrame(summary_rows)
    print("\n" + "=" * 85)
    print("📊 SIDE-BY-SIDE CONFIGURATION PERFORMANCE COMPARISON ($10,000 START)")
    print("=" * 85)
    print(summary_df[['Configuration', 'Executed', 'Skipped', 'Ending Equity', 'Net Profit', 'CAGR', 'Max Drawdown', 'Win Rate', 'Profit Factor']].to_string(index=False))

    summary_df.to_csv("docs/configurations_comparison_summary.csv", index=False)
    print("\n📁 Saved: docs/configurations_comparison_summary.csv")

    # Export individual trade logs with Execution Status (Executed vs Skipped)
    for idx, (name, res) in enumerate(results.items(), 1):
        filename = f"docs/trades_config{idx}_{name.split(':')[1].strip().lower().replace(' ', '_')}.csv"
        res['combined_log'].to_csv(filename, index=False)
        print(f"📁 Saved Config {idx} Log: {filename}")

    # Export Master Multi-Tab Excel Spreadsheet (Tab 1: Comparison, Tabs 2-5: Config Trade Logs)
    excel_path = "docs/rajat_alpha_4_configurations_simulation.xlsx"
    sheet_names = [
        "Config1_Standard",
        "Config2_Conservative",
        "Config3_Aggressive",
        "Config4_PropSpec"
    ]
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Comparison_Summary", index=False)
        pref_cols = [
            'Execution Status', 'Symbol', 'Entry Date', 'Exit Date', 'Buy Price', 'Exit Price',
            'Score', 'Return (%)', 'Allocated ($)', 'Realized PnL ($)', 'Pattern', 'IBD RS',
            'Initial SL', 'SL Price', 'SL Type', 'Stepper Triggered', 'TES Status',
            'Exit Reason', 'Hold Days', 'Is Runner'
        ]
        for (name, res), sname in zip(results.items(), sheet_names):
            clean_log = res['combined_log'].copy()
            rem_cols = [c for c in clean_log.columns if c not in pref_cols and c not in ('pos_val', 'pnl', 'exit_date')]
            ordered_cols = [c for c in pref_cols if c in clean_log.columns] + rem_cols
            clean_log[ordered_cols].to_excel(writer, sheet_name=sname, index=False)
        # Tab 6: Complete Raw Scanned Universe (rajat_alpha_scanned_trade_log.csv)
        trades_df.to_excel(writer, sheet_name="Scanned_Universe_Raw", index=False)
    print(f"📗 Saved Master Multi-Tab Excel Workbook: {excel_path} (6 Tabs including Raw Scanned Universe)")

    # Plot 4 Comparative Curves Overlay
    plt.figure(figsize=(14, 7))
    colors = ['#10B981', '#3B82F6', '#F59E0B', '#8B5CF6']
    for (name, res), c in zip(results.items(), colors):
        eq = res['equity_df']
        plt.plot(eq['Date'], eq['Equity'], label=f"{name} ({res['Total Return']}, Max DD: {res['Max Drawdown']})", color=c, linewidth=2)

    plt.axhline(10000.0, color='#9CA3AF', linestyle=':', label='Start ($10k)')
    plt.title("Comparative Portfolio Equity Compounding (4 Config Presets with Capacity Constraints)", fontsize=13, fontweight='bold')
    plt.xlabel("Date")
    plt.ylabel("Portfolio Balance ($)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left')
    plt.tight_layout()
    plt.savefig("docs/configurations_comparison_chart.png", dpi=200)
    print("🖼️ Saved Chart: docs/configurations_comparison_chart.png")

if __name__ == '__main__':
    run_comparator()

