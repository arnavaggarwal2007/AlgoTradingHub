"""
Portfolio Execution Simulator & Visualizer for Rajat Alpha v67 (Version 3.2)
Simulates realistic portfolio constraints on any downloaded trade log CSV:
- Enforces MAX CONCURRENT OPEN POSITIONS limit (if slots are full, trades are rejected/skipped).
- Tracks daily cash, invested capital, equity curve, and peak-to-trough drawdowns.
- Generates high-resolution dashboard (PNG) and interactive standalone visual HTML report.
"""

import os
import sys
import argparse
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def parse_args():
    parser = argparse.ArgumentParser(description="Realistic Portfolio Execution Simulator with Max Open Constraints")
    parser.add_argument("--input", type=str, default="C:/Users/Rajat/Downloads/rajat_alpha_scanned_trade_log.csv", help="Path to trade log CSV")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial Starting Capital ($)")
    parser.add_argument("--max-open", type=int, default=5, help="Maximum concurrent open positions allowed")
    parser.add_argument("--alloc-pct", type=float, default=0.20, help="Allocation % per position (e.g. 0.20 for 20%)")
    parser.add_argument("--slippage-pct", type=float, default=0.0015, help="Execution friction / slippage per trade (0.15%)")
    parser.add_argument("--output-prefix", type=str, default="docs/portfolio_constrained", help="Output file prefix")
    return parser.parse_args()

def run_simulation(args):
    csv_path = args.input
    if not os.path.exists(csv_path):
        # Fallback to local docs if downloads path not found
        fallback = "docs/scanned_watchlist_trade_log.csv"
        if os.path.exists(fallback):
            print(f"File {csv_path} not found. Using local fallback: {fallback}")
            csv_path = fallback
        else:
            print(f"Error: Trade log CSV not found at {csv_path}")
            return

    print("=" * 85)
    print(">> REALISTIC PORTFOLIO EXECUTION SIMULATOR (WITH MAX OPEN CAPACITY CONSTRAINT)")
    print("=" * 85)
    print(f"  Input Trade Log:         {csv_path}")
    print(f"  Starting Capital:        ${args.capital:,.2f}")
    print(f"  Max Concurrent Open:     {args.max_open} positions")
    print(f"  Position Allocation:     {args.alloc_pct * 100:.1f}% per trade (Max ${args.capital * args.alloc_pct:,.2f} initially)")
    print(f"  Execution Friction:      {args.slippage_pct * 100:.2f}% per round trip")
    print("=" * 85)

    df = pd.read_csv(csv_path)
    df['Entry Date'] = pd.to_datetime(df['Entry Date'])
    df['Exit Date'] = pd.to_datetime(df['Exit Date'])
    # Sort chronologically by Entry Date
    df = df.sort_values(by=['Entry Date', 'Score'], ascending=[True, False]).reset_index(drop=True)

    cash = args.capital
    portfolio_equity = args.capital
    active_positions = []  # list of dicts: {symbol, entry_date, exit_date, pos_value, ret_pct, pnl}

    accepted_trades = []
    skipped_trades = []
    daily_equity_history = []
    hwm = args.capital
    drawdowns = []

    # Get chronological unique calendar days
    all_trade_dates = sorted(list(set(df['Entry Date'].tolist() + df['Exit Date'].tolist())))

    for date in all_trade_dates:
        # 1. Close any active positions that exit on or before this date
        still_open = []
        for pos in active_positions:
            if pos['exit_date'] <= date:
                # Close trade and return cash + realized PnL
                cash += pos['pos_value'] + pos['realized_pnl']
                accepted_trades.append(pos)
            else:
                still_open.append(pos)
        active_positions = still_open

        # 2. Process new trades that want to enter on this date
        candidates_today = df[df['Entry Date'] == date]
        for _, trade in candidates_today.iterrows():
            # Check portfolio capacity
            if len(active_positions) >= args.max_open:
                # Capacity full! Must skip trade
                skipped_trades.append({
                    'Symbol': trade['Symbol'],
                    'Date': date.strftime('%Y-%m-%d'),
                    'Potential Return (%)': trade['Return (%)'],
                    'Score': trade['Score'],
                    'Reason': f"Portfolio Full ({len(active_positions)}/{args.max_open} Open)"
                })
                continue

            # Capacity available! Take trade
            # Dynamic position sizing based on current portfolio equity
            curr_equity = cash + sum(p['pos_value'] for p in active_positions)
            target_pos_size = curr_equity * args.alloc_pct
            actual_pos_size = min(target_pos_size, cash)  # capped by available cash

            if actual_pos_size < 100.0:
                skipped_trades.append({
                    'Symbol': trade['Symbol'],
                    'Date': date.strftime('%Y-%m-%d'),
                    'Potential Return (%)': trade['Return (%)'],
                    'Score': trade['Score'],
                    'Reason': "Insufficient Cash"
                })
                continue

            # Deduct cash
            cash -= actual_pos_size
            ret_net = (trade['Return (%)'] / 100.0) - args.slippage_pct
            pnl_dollars = actual_pos_size * ret_net

            active_positions.append({
                'symbol': trade['Symbol'],
                'entry_date': trade['Entry Date'],
                'exit_date': trade['Exit Date'],
                'pos_value': actual_pos_size,
                'return_pct': ret_net * 100.0,
                'realized_pnl': pnl_dollars,
                'score': trade['Score'],
                'pattern': trade['Pattern'],
                'exit_reason': trade['Exit Reason'],
                'hold_days': trade['Hold Days']
            })

        # Record daily equity snapshot
        curr_total = cash + sum(p['pos_value'] for p in active_positions)
        if curr_total > hwm:
            hwm = curr_total
        dd = (hwm - curr_total) / hwm
        drawdowns.append(dd)
        daily_equity_history.append({
            'Date': date,
            'Total Equity': curr_total,
            'Cash': cash,
            'Invested': sum(p['pos_value'] for p in active_positions),
            'Open Positions': len(active_positions),
            'Drawdown (%)': dd * 100.0
        })

    # Flush any remaining open positions
    for pos in active_positions:
        cash += pos['pos_value'] + pos['realized_pnl']
        accepted_trades.append(pos)
    active_positions = []

    final_equity = cash
    total_gain = ((final_equity / args.capital) - 1.0) * 100.0
    net_profit = final_equity - args.capital
    max_dd = max(drawdowns) * 100.0 if drawdowns else 0.0

    acc_df = pd.DataFrame(accepted_trades)
    skip_df = pd.DataFrame(skipped_trades)
    eq_df = pd.DataFrame(daily_equity_history)

    wins = acc_df[acc_df['realized_pnl'] > 0]
    losses = acc_df[acc_df['realized_pnl'] < 0]
    wr = (len(wins) / len(acc_df)) * 100.0 if len(acc_df) > 0 else 0.0
    pf = (wins['realized_pnl'].sum() / abs(losses['realized_pnl'].sum())) if len(losses) > 0 and losses['realized_pnl'].sum() != 0 else 99.0

    days_span = max(1, (df['Exit Date'].max() - df['Entry Date'].min()).days)
    years = days_span / 365.25
    cagr = (((final_equity / args.capital) ** (1.0 / max(years, 0.5))) - 1.0) * 100.0

    print("\n" + "=" * 85)
    print("📊 REALISTIC PORTFOLIO PERFORMANCE METRICS (CAPITAL CONSTRAINED)")
    print("=" * 85)
    print(f"  Total Trades in Log:           {len(df)}")
    print(f"  Accepted Trades Executed:      {len(acc_df)} ({len(acc_df)/len(df)*100:.1f}%)")
    print(f"  Skipped (Capacity Full):       {len(skip_df)} ({len(skip_df)/len(df)*100:.1f}%)")
    print(f"  Starting Capital:              ${args.capital:,.2f}")
    print(f"  Ending Account Equity:         ${final_equity:,.2f}")
    print(f"  Net Realized Profit:           +${net_profit:,.2f} (+{total_gain:.1f}%)")
    print(f"  Compound Annual Growth (CAGR): {cagr:.1f}% / year")
    print(f"  Peak-to-Trough Max Drawdown:   -{max_dd:.1f}%")
    print(f"  Constrained Win Rate:          {wr:.1f}% ({len(wins)} Wins / {len(losses)} Losses)")
    print(f"  Constrained Profit Factor:     {pf:.2f}")
    print(f"  Average Days Held per Trade:   {acc_df['hold_days'].mean():.1f} days")
    print("=" * 85)

    # =========================================================================
    # RENDER 4-PANEL DASHBOARD
    # =========================================================================
    os.makedirs(os.path.dirname(args.output_prefix), exist_ok=True)
    png_path = f"{args.output_prefix}_dashboard.png"

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.patch.set_facecolor('#0F172A')

    # Subplot 1: Equity Growth Curve
    ax1 = axes[0, 0]
    ax1.set_facecolor('#1E293B')
    ax1.plot(eq_df['Date'], eq_df['Total Equity'], color='#10B981', linewidth=2.5, label='Portfolio Equity ($)')
    ax1.plot(eq_df['Date'], eq_df['Cash'], color='#64748B', linestyle=':', label='Free Cash ($)')
    ax1.set_title(f"Realistic Portfolio Equity ($10k Start, Max {args.max_open} Positions)", color='#F8FAFC', fontsize=12, fontweight='bold')
    ax1.set_ylabel("Account Balance ($)", color='#94A3B8')
    ax1.tick_params(colors='#94A3B8')
    ax1.grid(True, linestyle='--', alpha=0.2, color='#64748B')
    ax1.legend(facecolor='#0F172A', edgecolor='#334155', labelcolor='#F8FAFC')

    # Subplot 2: Concurrent Active Positions
    ax2 = axes[0, 1]
    ax2.set_facecolor('#1E293B')
    ax2.plot(eq_df['Date'], eq_df['Open Positions'], color='#38BDF8', linewidth=1.8)
    ax2.axhline(args.max_open, color='#EF4444', linestyle='--', linewidth=1.5, label=f'Max Cap Ceiling ({args.max_open})')
    ax2.set_title("Concurrent Active Open Positions (Slot Utilization)", color='#F8FAFC', fontsize=12, fontweight='bold')
    ax2.set_ylabel("Open Positions Count", color='#94A3B8')
    ax2.tick_params(colors='#94A3B8')
    ax2.grid(True, linestyle='--', alpha=0.2, color='#64748B')
    ax2.legend(facecolor='#0F172A', edgecolor='#334155', labelcolor='#F8FAFC')

    # Subplot 3: Underwater Drawdown
    ax3 = axes[1, 0]
    ax3.set_facecolor('#1E293B')
    ax3.fill_between(eq_df['Date'], -eq_df['Drawdown (%)'], 0, color='#EF4444', alpha=0.4)
    ax3.plot(eq_df['Date'], -eq_df['Drawdown (%)'], color='#EF4444', linewidth=1.5)
    ax3.set_title(f"Peak-to-Trough Drawdown (Max: -{max_dd:.1f}%)", color='#F8FAFC', fontsize=12, fontweight='bold')
    ax3.set_ylabel("Drawdown (%)", color='#94A3B8')
    ax3.tick_params(colors='#94A3B8')
    ax3.grid(True, linestyle='--', alpha=0.2, color='#64748B')

    # Subplot 4: P&L Distribution
    ax4 = axes[1, 1]
    ax4.set_facecolor('#1E293B')
    pnl_vals = acc_df['realized_pnl'].values
    ax4.hist(pnl_vals, bins=25, color='#38BDF8', edgecolor='#0369A1', alpha=0.85)
    ax4.axvline(0, color='#EF4444', linestyle='--')
    ax4.axvline(np.mean(pnl_vals), color='#10B981', linewidth=2, label=f"Avg Gain (+${np.mean(pnl_vals):.1f})")
    ax4.set_title("Executed Realized P&L Distribution", color='#F8FAFC', fontsize=12, fontweight='bold')
    ax4.set_xlabel("Realized P&L ($)", color='#94A3B8')
    ax4.set_ylabel("Frequency", color='#94A3B8')
    ax4.tick_params(colors='#94A3B8')
    ax4.grid(True, linestyle='--', alpha=0.2, color='#64748B')
    ax4.legend(facecolor='#0F172A', edgecolor='#334155', labelcolor='#F8FAFC')

    plt.tight_layout()
    plt.savefig(png_path, dpi=200, facecolor=fig.get_facecolor())
    plt.close()
    print(f"\n🖼️ Saved High-Resolution Dashboard: {png_path}")

    # =========================================================================
    # GENERATE STANDALONE HTML REPORT
    # =========================================================================
    html_path = f"{args.output_prefix}_report.html"
    top_winners = acc_df.sort_values(by='realized_pnl', ascending=False).head(8)
    top_losers = acc_df.sort_values(by='realized_pnl', ascending=True).head(5)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Rajat Alpha v67 - Portfolio Execution Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0B0F19; color: #E2E8F0; margin: 0; padding: 25px; }}
  h1, h2, h3 {{ color: #38BDF8; margin-bottom: 8px; }}
  .kpi-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 25px 0; }}
  .kpi-card {{ background: #1E293B; padding: 18px; border-radius: 10px; border-left: 4px solid #38BDF8; }}
  .kpi-label {{ font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; }}
  .kpi-value {{ font-size: 24px; font-weight: bold; margin-top: 6px; color: #F8FAFC; }}
  .kpi-sub {{ font-size: 12px; color: #10B981; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: #1E293B; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; font-size: 13px; }}
  th {{ background: #0F172A; color: #38BDF8; font-weight: 600; }}
  tr:hover {{ background: #334155; }}
  .badge-win {{ color: #10B981; font-weight: bold; }}
  .badge-loss {{ color: #EF4444; font-weight: bold; }}
  .img-box {{ margin: 25px 0; text-align: center; }}
  .img-box img {{ max-width: 100%; border-radius: 8px; border: 1px solid #334155; }}
</style>
</head>
<body>
<h1>🏛️ Rajat Alpha v67: Portfolio Execution & Compounding Report</h1>
<p style="color: #94A3B8;">Realistic Backtest Simulation Enforcing Max Concurrent Position Capacity & Daily Rebalance</p>

<div class="kpi-container">
  <div class="kpi-card">
    <div class="kpi-label">Final Equity</div>
    <div class="kpi-value">${final_equity:,.2f}</div>
    <div class="kpi-sub">+{total_gain:.1f}% Total Net Gain</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Annualized Return (CAGR)</div>
    <div class="kpi-value">{cagr:.1f}% / yr</div>
    <div class="kpi-sub">Compound Growth</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Peak Drawdown</div>
    <div class="kpi-value" style="color: #F87171;">-{max_dd:.1f}%</div>
    <div class="kpi-sub">Risk Floor Intact</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Win Rate / PF</div>
    <div class="kpi-value">{wr:.1f}%</div>
    <div class="kpi-sub">Profit Factor: {pf:.2f}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Trade Execution Ratio</div>
    <div class="kpi-value">{len(acc_df)} / {len(df)}</div>
    <div class="kpi-sub">{len(skip_df)} Skipped (Capacity Full)</div>
  </div>
</div>

<div class="img-box">
  <img src="{os.path.basename(png_path)}" alt="Portfolio Performance Dashboard">
</div>

<h2>🏆 Top Performing Executed Trades</h2>
<table>
  <thead>
    <tr>
      <th>Symbol</th><th>Entry Date</th><th>Exit Date</th><th>Hold Days</th><th>Return (%)</th><th>Realized PnL ($)</th><th>Exit Reason</th>
    </tr>
  </thead>
  <tbody>
"""
    for _, r in top_winners.iterrows():
        html_content += f"""    <tr>
      <td><b>{r['symbol']}</b></td>
      <td>{r['entry_date'].strftime('%Y-%m-%d')}</td>
      <td>{r['exit_date'].strftime('%Y-%m-%d')}</td>
      <td>{r['hold_days']}</td>
      <td class="badge-win">+{r['return_pct']:.2f}%</td>
      <td class="badge-win">+${r['realized_pnl']:,.2f}</td>
      <td>{r['exit_reason']}</td>
    </tr>\n"""

    html_content += """  </tbody>
</table>

<h2 style="margin-top: 30px;">🛡️ Largest Mitigated Losses (Trailing Stepper Protection)</h2>
<table>
  <thead>
    <tr>
      <th>Symbol</th><th>Entry Date</th><th>Exit Date</th><th>Hold Days</th><th>Return (%)</th><th>Realized PnL ($)</th><th>Exit Reason</th>
    </tr>
  </thead>
  <tbody>
"""
    for _, r in top_losers.iterrows():
        html_content += f"""    <tr>
      <td><b>{r['symbol']}</b></td>
      <td>{r['entry_date'].strftime('%Y-%m-%d')}</td>
      <td>{r['exit_date'].strftime('%Y-%m-%d')}</td>
      <td>{r['hold_days']}</td>
      <td class="badge-loss">{r['return_pct']:.2f}%</td>
      <td class="badge-loss">-${abs(r['realized_pnl']):,.2f}</td>
      <td>{r['exit_reason']}</td>
    </tr>\n"""

    html_content += """  </tbody>
</table>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"📄 Saved Standalone Interactive HTML Report: {html_path}")

    # Export execution summary CSV
    acc_df.to_csv(f"{args.output_prefix}_accepted_trades.csv", index=False)
    skip_df.to_csv(f"{args.output_prefix}_skipped_trades.csv", index=False)
    print(f"📁 Saved accepted trades: {args.output_prefix}_accepted_trades.csv")
    print(f"📁 Saved skipped trades: {args.output_prefix}_skipped_trades.csv")

if __name__ == '__main__':
    args = parse_args()
    run_simulation(args)

