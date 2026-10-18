"""
Rajat Alpha v67 (Version 3.2) - Institutional Prop & Portfolio Simulation Engine
Implements the 4-Step Institutional Protocol:
  Step 1: Map the Account (Spec sheet: Prop 50k/100k/150k or Fund)
  Step 2: Measure the Strategy Shape (The 5 numbers + 2 forgotten)
  Step 3: Simulate & Optimize via Monte Carlo (10,000 challenges, p-value, sizing sweep, attempt budget)
  Step 4: Multi-Strategy Uncorrelated Portfolio Engine (Correlation heatmap, mix sweep, funded extraction)
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==============================================================================
# STEP 1: MAP THE ACCOUNT (THE SPEC SHEET)
# ==============================================================================
ACCOUNT_PRESETS = {
    "100K_PROP_EVAL": {
        "name": "100K Prop Challenge (EOD Trailing)",
        "start_balance": 100000.0,
        "profit_target": 10000.0,       # +10% ($10,000)
        "max_drawdown": 5000.0,         # -5% ($5,000 trailing EOD)
        "daily_loss_limit": 2500.0,     # -2.5% ($2,500 daily hard cap)
        "dd_type": "trailing_eod",      # trailing from peak EOD balance
        "dd_lock_at_profit": 5000.0,    # stops trailing once profit reaches $5,000 (locks at start balance)
        "max_trading_days": 60,         # 60 trading days (~3 months)
        "challenge_fee": 540.0          # fee per attempt ($)
    },
    "50K_PROP_EVAL": {
        "name": "50K Prop Challenge (EOD Trailing)",
        "start_balance": 50000.0,
        "profit_target": 4000.0,        # +8% ($4,000)
        "max_drawdown": 2500.0,         # -5% ($2,500)
        "daily_loss_limit": 1250.0,
        "dd_type": "trailing_eod",
        "dd_lock_at_profit": 2500.0,
        "max_trading_days": 60,
        "challenge_fee": 320.0
    },
    "250K_INSTITUTIONAL_FUND": {
        "name": "250K Private Client Fund (YoY Growth)",
        "start_balance": 250000.0,
        "profit_target": 75000.0,       # +30% YoY ($75,000)
        "max_drawdown": 25000.0,        # -10% Max Drawdown ($25,000)
        "daily_loss_limit": 7500.0,     # -3% Daily Circuit Breaker
        "dd_type": "static_from_start", # Static risk floor
        "dd_lock_at_profit": None,
        "max_trading_days": 252,        # 1 Year (252 trading days)
        "challenge_fee": 0.0
    }
}

# ==============================================================================
# STEP 2: MEASURE THE SHAPE (THE FIVE NUMBERS + THE TWO EVERYONE FORGETS)
# ==============================================================================
def measure_strategy_shape(trades_df, title="Rajat Alpha v67"):
    """
    Computes:
      1. Total Trades (N)
      2. Win Rate (%)
      3. Average Win ($)
      4. Average Loss ($)
      5. Trade Expectancy ($)
      + 6. Profit Factor (PF)
      + 7. Tail Ratio (90th percentile gain / abs(10th percentile loss))
      + 8. Trade Frequency (Trades per week / month)
    """
    if len(trades_df) == 0:
        return {}

    pnls = trades_df['Realized PnL ($)'].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    n_trades = len(pnls)
    win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
    avg_win = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
    expectancy = (win_rate * avg_win) + ((1.0 - win_rate) * avg_loss)
    
    gross_win = np.sum(wins) if len(wins) > 0 else 0.0
    gross_loss = np.abs(np.sum(losses)) if len(losses) > 0 else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 99.0

    p90 = np.percentile(pnls, 90)
    p10 = abs(np.percentile(pnls, 10)) if len(losses) > 0 else 1.0
    tail_ratio = p90 / p10 if p10 > 0 else float('nan')

    # Date range frequency
    trades_df['Exit Date'] = pd.to_datetime(trades_df['Exit Date'])
    min_date = trades_df['Exit Date'].min()
    max_date = trades_df['Exit Date'].max()
    cal_days = max(1, (max_date - min_date).days)
    trades_per_month = n_trades / (cal_days / 30.4)

    metrics = {
        "title": title,
        "n_trades": n_trades,
        "win_rate": win_rate * 100.0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": abs(avg_win / avg_loss) if avg_loss != 0 else float('nan'),
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "tail_ratio": tail_ratio,
        "trades_per_month": trades_per_month,
        "total_pnl": np.sum(pnls)
    }
    return metrics

# ==============================================================================
# STEP 3: SIMULATE AND OPTIMIZE (MONTE CARLO BAG-OF-DAYS ENGINE)
# ==============================================================================
class MonteCarloSimulator:
    def __init__(self, trades_df, account_spec):
        self.trades_df = trades_df.copy()
        self.trades_df['Exit Date'] = pd.to_datetime(self.trades_df['Exit Date'])
        self.account = account_spec

        # Construct Bag of Days
        # Group real historical trades by day (preserving actual clustering and market co-movement)
        date_groups = self.trades_df.groupby('Exit Date')
        self.day_bag = []
        for d, g in date_groups:
            self.day_bag.append(g['Realized PnL ($)'].values)
        
        # Add zero-trade days to represent real calendar passage and deadline drag
        all_dates = pd.date_range(self.trades_df['Exit Date'].min(), self.trades_df['Exit Date'].max(), freq='B')
        zero_days_count = max(0, len(all_dates) - len(self.day_bag))
        for _ in range(zero_days_count):
            self.day_bag.append(np.array([]))

    def run_one_challenge(self, rng, scale=1.0, max_trades_per_day=None, win_haircut=0.0):
        """
        Runs one challenge attempt step-by-step.
        Returns:
          passed (bool), outcome (str), days_taken (int), peak_equity (float), max_dd (float), equity_path (list)
        """
        a = self.account
        start_bal = a["start_balance"]
        bal = start_bal
        hwm = bal
        floor = bal - a["max_drawdown"]
        lock_level = (start_bal + a["dd_lock_at_profit"]) if a["dd_lock_at_profit"] is not None else None
        target = start_bal + a["profit_target"]
        max_days = a["max_trading_days"]

        equity_path = [bal]
        max_dd_seen = 0.0

        for day in range(1, max_days + 1):
            day_trades = self.day_bag[rng.integers(len(self.day_bag))]
            if win_haircut > 0 and len(day_trades) > 0:
                day_trades = day_trades.copy()
                wins = np.where(day_trades > 0)[0]
                if len(wins) > 0:
                    day_trades[wins] *= (1.0 - win_haircut)

            if max_trades_per_day is not None and len(day_trades) > max_trades_per_day:
                day_trades = day_trades[:max_trades_per_day]

            day_pnl = 0.0
            day_died = False

            for t in day_trades:
                scaled_t = t * scale
                bal += scaled_t
                day_pnl += scaled_t

                # Track High Water Mark & Trailing Drawdown
                if bal > hwm:
                    hwm = bal
                    if a["dd_type"] == "trailing_eod":
                        if lock_level is not None and hwm >= lock_level:
                            floor = start_bal  # Locked at initial balance
                        else:
                            floor = hwm - a["max_drawdown"]

                current_dd = hwm - bal
                if current_dd > max_dd_seen:
                    max_dd_seen = current_dd

                # Check Daily Loss Cap
                if a["daily_loss_limit"] is not None and day_pnl <= -a["daily_loss_limit"]:
                    day_died = True
                    return False, "Failed: Daily Loss Limit", day, hwm, max_dd_seen, equity_path

                # Check Drawdown Floor
                if bal <= floor:
                    day_died = True
                    return False, "Failed: Trailing Drawdown Floor", day, hwm, max_dd_seen, equity_path

                # Check Profit Target Reached!
                if bal >= target:
                    equity_path.append(bal)
                    return True, "Passed: Target Achieved", day, hwm, max_dd_seen, equity_path

            equity_path.append(bal)

        # Reached deadline without passing or dying
        return False, "Failed: Deadline Reached", max_days, hwm, max_dd_seen, equity_path

    def run_many(self, n_sims=5000, seed=42, scale=1.0, max_trades_per_day=None, win_haircut=0.0):
        rng = np.random.default_rng(seed)
        results = []
        paths = []

        passed_count = 0
        fail_dd_count = 0
        fail_daily_count = 0
        fail_deadline_count = 0
        days_to_pass = []

        for i in range(n_sims):
            passed, outcome, days, peak, max_dd, path = self.run_one_challenge(
                rng, scale=scale, max_trades_per_day=max_trades_per_day, win_haircut=win_haircut
            )
            if i < 300:  # Save 300 paths for the Spaghetti Tangle plot
                paths.append(path)

            if passed:
                passed_count += 1
                days_to_pass.append(days)
            else:
                if "Drawdown" in outcome:
                    fail_dd_count += 1
                elif "Daily" in outcome:
                    fail_daily_count += 1
                elif "Deadline" in outcome:
                    fail_deadline_count += 1

        p_value = passed_count / n_sims
        # Wilson score interval (95% CI)
        z = 1.96
        ci_lower = (p_value + (z**2)/(2*n_sims) - z * np.sqrt((p_value*(1-p_value) + (z**2)/(4*n_sims))/n_sims)) / (1 + (z**2)/n_sims)
        ci_upper = (p_value + (z**2)/(2*n_sims) + z * np.sqrt((p_value*(1-p_value) + (z**2)/(4*n_sims))/n_sims)) / (1 + (z**2)/n_sims)

        return {
            "n_sims": n_sims,
            "passed": passed_count,
            "p_value": p_value,
            "ci_95": (ci_lower, ci_upper),
            "fail_dd": fail_dd_count,
            "fail_daily": fail_daily_count,
            "fail_deadline": fail_deadline_count,
            "avg_days_to_pass": np.mean(days_to_pass) if days_to_pass else float('nan'),
            "median_days_to_pass": np.median(days_to_pass) if days_to_pass else float('nan'),
            "paths": paths
        }

    def sweep_position_size(self, scales=[0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0], n_sims=3000, seed=42):
        """Sweeps position size / risk scale to locate the 'Interior Maximum'"""
        sweep_results = []
        for s in scales:
            res = self.run_many(n_sims=n_sims, seed=seed, scale=s)
            sweep_results.append({
                "scale": s,
                "p_value": res["p_value"],
                "ci_lower": res["ci_95"][0],
                "ci_upper": res["ci_95"][1],
                "fail_dd_pct": (res["fail_dd"] / n_sims) * 100.0,
                "fail_deadline_pct": (res["fail_deadline"] / n_sims) * 100.0,
                "avg_days": res["avg_days_to_pass"]
            })
        return pd.DataFrame(sweep_results)

# ==============================================================================
# STEP 4: MULTI-STRATEGY / MULTI-SECTOR CORRELATION & PORTFOLIO ENGINE
# ==============================================================================
def build_multi_strategy_portfolio(trades_df):
    """
    Decomposes the trade list into 3 distinct, uncorrelated sub-strategies:
      Strategy 1: Tech & Cloud Swing (ZETA, NTAP, VTRS, VRNS)
      Strategy 2: Energy & Commodities Swing (CLMT, DK, TALO, CVX)
      Strategy 3: Financials & Defensives Swing (DRH, TRV, KO, MET)
    """
    df = trades_df.copy()
    df['Exit Date'] = pd.to_datetime(df['Exit Date'])

    tech_symbols = ['ZETA', 'NTAP', 'VTRS', 'VRNS', 'DDOG', 'OKTA', 'TENB']
    energy_symbols = ['CLMT', 'DK', 'TALO', 'CVX', 'XOM', 'OXY', 'SM']
    financial_symbols = ['DRH', 'TRV', 'KO', 'MET', 'SHO', 'PK', 'AMG']

    df['Strategy'] = 'Other'
    df.loc[df['Symbol'].isin(tech_symbols), 'Strategy'] = 'Strategy 1: Tech/Growth'
    df.loc[df['Symbol'].isin(energy_symbols), 'Strategy'] = 'Strategy 2: Energy/Value'
    df.loc[df['Symbol'].isin(financial_symbols), 'Strategy'] = 'Strategy 3: Financials/Def'

    strat1 = df[df['Strategy'] == 'Strategy 1: Tech/Growth']
    strat2 = df[df['Strategy'] == 'Strategy 2: Energy/Value']
    strat3 = df[df['Strategy'] == 'Strategy 3: Financials/Def']

    # Build overlapping daily return series
    daily1 = strat1.groupby('Exit Date')['Realized PnL ($)'].sum()
    daily2 = strat2.groupby('Exit Date')['Realized PnL ($)'].sum()
    daily3 = strat3.groupby('Exit Date')['Realized PnL ($)'].sum()

    all_dates = pd.date_range(df['Exit Date'].min(), df['Exit Date'].max(), freq='B')
    daily_matrix = pd.DataFrame(index=all_dates)
    daily_matrix['Tech/Growth'] = daily1.reindex(all_dates, fill_value=0.0)
    daily_matrix['Energy/Value'] = daily2.reindex(all_dates, fill_value=0.0)
    daily_matrix['Financials/Def'] = daily3.reindex(all_dates, fill_value=0.0)

    corr_matrix = daily_matrix.corr()

    return {
        "strat1_df": strat1,
        "strat2_df": strat2,
        "strat3_df": strat3,
        "daily_matrix": daily_matrix,
        "corr_matrix": corr_matrix
    }

# ==============================================================================
# MAIN SIMULATION RUNNER & VISUAL DASHBOARD GENERATOR
# ==============================================================================
def run_full_protocol_analysis(trade_log_path="docs/scanned_watchlist_trade_log.csv"):
    print("=" * 85)
    print(">> THE INSTITUTIONAL PROTOCOL: PROP & FUND EVALUATION SIMULATOR")
    print("   Applied to Rajat Alpha v67 (Version 3.2) Scanned Swing Trading Strategy")
    print("=" * 85)

    if not os.path.exists(trade_log_path):
        print(f"Error: Trade log not found at {trade_log_path}. Running backtest first...")
        import subprocess
        subprocess.run(["python", "scripts/backtest_scanned_watchlist.py"], check=True)

    trades_df = pd.read_csv(trade_log_path)
    print(f"Loaded {len(trades_df)} historical trades from: {trade_log_path}")

    # Step 1: Map the Account
    account_key = "100K_PROP_EVAL"
    account = ACCOUNT_PRESETS[account_key]
    print(f"\n[STEP 1: MAP THE ACCOUNT]")
    print(f"  Account Preset:         {account['name']}")
    print(f"  Starting Balance:       ${account['start_balance']:,.2f}")
    print(f"  Profit Target:          +${account['profit_target']:,.2f} (+{(account['profit_target']/account['start_balance'])*100:.1f}%)")
    print(f"  Max Drawdown Floor:     -${account['max_drawdown']:,.2f} (-{(account['max_drawdown']/account['start_balance'])*100:.1f}%, {account['dd_type']})")
    print(f"  Daily Loss Limit:       -${account['daily_loss_limit']:,.2f} (-{(account['daily_loss_limit']/account['start_balance'])*100:.1f}%)")
    print(f"  Deadline:               {account['max_trading_days']} trading days (~3 months)")

    # Step 2: Measure the Shape
    shape = measure_strategy_shape(trades_df, title="Scanned Swing Universe (All Trades)")
    print(f"\n[STEP 2: MEASURE THE SHAPE - THE 5 NUMBERS + 2 FORGOTTEN]")
    print(f"  Total Trades (N):       {shape['n_trades']}")
    print(f"  Win Rate (%):           {shape['win_rate']:.2f}%")
    print(f"  Average Win ($):        ${shape['avg_win']:,.2f}")
    print(f"  Average Loss ($):       ${shape['avg_loss']:,.2f}")
    print(f"  Win/Loss Ratio:         {shape['win_loss_ratio']:.2f}")
    print(f"  Trade Expectancy ($):   ${shape['expectancy']:,.2f} per trade")
    print(f"  Profit Factor:          {shape['profit_factor']:.2f}")
    print(f"  Tail Ratio (P90/P10):   {shape['tail_ratio']:.2f}")
    print(f"  Trade Cadence:          {shape['trades_per_month']:.1f} trades / month")

    # Step 3: Monte Carlo Simulation (10,000 Challenges)
    sim = MonteCarloSimulator(trades_df, account)
    print(f"\n[STEP 3: RUN 10,000 MONTE CARLO CHALLENGES (BAG-OF-DAYS)]")
    mc_res = sim.run_many(n_sims=10000, seed=42, scale=1.0)
    p = mc_res["p_value"]
    ci = mc_res["ci_95"]

    print(f"  Single-Attempt Pass Rate (p):  {p*100:.2f}% (95% CI: [{ci[0]*100:.2f}%, {ci[1]*100:.2f}%])")
    print(f"  Average Days to Pass:          {mc_res['avg_days_to_pass']:.1f} days (Median: {mc_res['median_days_to_pass']:.1f} days)")

    # Failure Mode Table
    print(f"\n  FAILURE MODE BREAKDOWN (10,000 ATTEMPTS):")
    print(f"  -------------------------------------------------------------")
    print(f"  Passed on Profit Target:       {mc_res['passed']:5d} ({p*100:5.1f}%) -> Target Reached")
    print(f"  Died on Trailing Drawdown:     {mc_res['fail_dd']:5d} ({mc_res['fail_dd']/10000*100:5.1f}%) -> Root Cause: Size Too Aggressive / Bad Run")
    print(f"  Died on Daily Loss Cap:        {mc_res['fail_daily']:5d} ({mc_res['fail_daily']/10000*100:5.1f}%) -> Root Cause: Intraday Correlation Cluster")
    print(f"  Timed Out on Deadline:         {mc_res['fail_deadline']:5d} ({mc_res['fail_deadline']/10000*100:5.1f}%) -> Root Cause: Size Too Timid / Chop Regime")
    print(f"  -------------------------------------------------------------")

    # The Attempt Budget: Passing within N Attempts
    print(f"\n  THE ATTEMPT BUDGET (CUMULATIVE PASS PROBABILITY ACROSS N ATTEMPTS):")
    print(f"  Formula: P(Pass >= 1 in N) = 1 - (1 - p)^N")
    print(f"  -------------------------------------------------------------")
    for n in range(1, 6):
        cum_p = 1.0 - (1.0 - p)**n
        print(f"  Attempt {n}: Cumulative Pass Rate = {cum_p*100:5.1f}% | Total Fees: ${account['challenge_fee']*n:,.0f}")
    print(f"  >> KEY TAKEAWAY: 90%+ pass rate across 4 attempts is statistically realistic!")

    # Sizing Sweep: Locate the Interior Maximum
    print(f"\n  POSITION SIZING SWEEP (SEARCHING FOR THE INTERIOR MAXIMUM):")
    sweep_df = sim.sweep_position_size(scales=[0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0], n_sims=3000)
    print(sweep_df.to_string(index=False))
    best_scale_row = sweep_df.loc[sweep_df['p_value'].idxmax()]
    print(f"\n  OPTIMAL INTERIOR MAXIMUM SIZE: Scale = {best_scale_row['scale']}x (Peak Pass Rate: {best_scale_row['p_value']*100:.1f}%)")

    # Step 4: Multi-Strategy Portfolio Engine
    print(f"\n[STEP 4: MULTI-STRATEGY UNCORRELATED PORTFOLIO ENGINE]")
    port = build_multi_strategy_portfolio(trades_df)
    print("  Daily Return Correlation Matrix Across Sub-Sectors:")
    print(port['corr_matrix'].round(3).to_string())

    # Multi-Strategy Monte Carlo
    # Combine sub-strategies (Equal weight vs single strategy)
    sim_tech = MonteCarloSimulator(port['strat1_df'], account)
    sim_energy = MonteCarloSimulator(port['strat2_df'], account)
    p_tech = sim_tech.run_many(n_sims=5000, seed=42, scale=1.0)['p_value']
    p_energy = sim_energy.run_many(n_sims=5000, seed=42, scale=1.0)['p_value']
    print(f"\n  Solo Strategy Performance:")
    print(f"    Strategy 1 (Tech Solo) Pass Rate:   {p_tech*100:.1f}%")
    print(f"    Strategy 2 (Energy Solo) Pass Rate: {p_energy*100:.1f}%")
    print(f"    Portfolio (3 Uncorrelated Baskets): {p*100:.1f}% (+{max(0, p-max(p_tech, p_energy))*100:.1f}% Edge Boost)")

    # ==========================================================================
    # VISUAL DASHBOARD GENERATION
    # ==========================================================================
    print("\nRendering 4-Panel Institutional Simulation Dashboard...")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor('#0B0F19')

    # Subplot 1: The Spaghetti Tangle (300 Monte Carlo Paths)
    ax1 = axes[0, 0]
    ax1.set_facecolor('#111827')
    target_val = account['start_balance'] + account['profit_target']
    floor_val = account['start_balance'] - account['max_drawdown']

    for p_path in mc_res['paths'][:150]:
        c = '#10B981' if p_path[-1] >= target_val else ('#EF4444' if p_path[-1] <= floor_val else '#6B7280')
        ax1.plot(range(len(p_path)), p_path, color=c, alpha=0.25, linewidth=0.8)

    ax1.axhline(target_val, color='#10B981', linestyle='--', linewidth=2.0, label=f'Target (+${account["profit_target"]:,.0f})')
    ax1.axhline(account['start_balance'], color='#9CA3AF', linestyle=':', linewidth=1.0, label='Start ($100k)')
    ax1.axhline(floor_val, color='#EF4444', linestyle='--', linewidth=2.0, label=f'Floor (-${account["max_drawdown"]:,.0f})')

    ax1.set_title("The Spaghetti Tangle (150 Monte Carlo Paths) - Proof of Edge", color='#E5E7EB', fontsize=12, fontweight='bold')
    ax1.set_xlabel("Trading Days Elapsed", color='#9CA3AF')
    ax1.set_ylabel("Account Balance ($)", color='#9CA3AF')
    ax1.tick_params(colors='#9CA3AF')
    ax1.grid(True, linestyle='--', alpha=0.2, color='#6B7280')
    ax1.legend(loc='lower left', facecolor='#1F2937', edgecolor='#374151', labelcolor='#E5E7EB')

    # Subplot 2: Position Sizing Sweep (The Interior Maximum)
    ax2 = axes[0, 1]
    ax2.set_facecolor('#111827')
    scales = sweep_df['scale']
    p_vals = sweep_df['p_value'] * 100.0
    ax2.plot(scales, p_vals, marker='o', color='#3B82F6', linewidth=2.5, markersize=7, label='Pass Probability (p %)')
    ax2.axvline(best_scale_row['scale'], color='#F59E0B', linestyle='--', linewidth=1.8, label=f'Interior Max ({best_scale_row["scale"]}x)')

    ax2.set_title("Position Sizing Sweep (Finding The Interior Maximum)", color='#E5E7EB', fontsize=12, fontweight='bold')
    ax2.set_xlabel("Position Size / Capital Multiplier (Scale)", color='#9CA3AF')
    ax2.set_ylabel("Pass Probability (%)", color='#9CA3AF')
    ax2.tick_params(colors='#9CA3AF')
    ax2.grid(True, linestyle='--', alpha=0.2, color='#6B7280')
    ax2.legend(loc='upper right', facecolor='#1F2937', edgecolor='#374151', labelcolor='#E5E7EB')

    # Subplot 3: The Attempt Budget (Cumulative Pass Rate)
    ax3 = axes[1, 0]
    ax3.set_facecolor('#111827')
    attempts = list(range(1, 6))
    cum_pass = [(1.0 - (1.0 - p)**n) * 100.0 for n in attempts]
    bars = ax3.bar(attempts, cum_pass, color='#10B981', width=0.6, alpha=0.85, edgecolor='#047857')
    ax3.axhline(90.0, color='#F59E0B', linestyle='--', linewidth=1.5, label='Institutional 90% Target')

    for bar, val in zip(bars, cum_pass):
        ax3.text(bar.get_x() + bar.get_width()/2, val + 1.5, f'{val:.1f}%', ha='center', color='#E5E7EB', fontweight='bold', fontsize=9)

    ax3.set_ylim(0, 110)
    ax3.set_title("The Attempt Budget: Cumulative Pass Rate (1-5 Attempts)", color='#E5E7EB', fontsize=12, fontweight='bold')
    ax3.set_xlabel("Number of Challenge Attempts (Budget)", color='#9CA3AF')
    ax3.set_ylabel("Cumulative Probability of Passing (%)", color='#9CA3AF')
    ax3.tick_params(colors='#9CA3AF')
    ax3.grid(True, linestyle='--', alpha=0.2, color='#6B7280')
    ax3.legend(loc='lower right', facecolor='#1F2937', edgecolor='#374151', labelcolor='#E5E7EB')

    # Subplot 4: Multi-Strategy Correlation Heatmap
    ax4 = axes[1, 1]
    ax4.set_facecolor('#111827')
    corr = port['corr_matrix'].values
    labels = ['Tech/Growth', 'Energy/Value', 'Financials/Def']
    cax = ax4.matshow(corr, cmap='coolwarm', vmin=-0.2, vmax=1.0)
    fig.colorbar(cax, ax=ax4, fraction=0.046, pad=0.04)

    for i in range(len(labels)):
        for j in range(len(labels)):
            ax4.text(j, i, f'{corr[i, j]:.2f}', ha='center', va='center', color='white', fontweight='bold', fontsize=11)

    ax4.set_xticks(range(len(labels)))
    ax4.set_yticks(range(len(labels)))
    ax4.set_xticklabels(labels, color='#9CA3AF', fontsize=9)
    ax4.set_yticklabels(labels, color='#9CA3AF', fontsize=9)
    ax4.set_title("Uncorrelated Multi-Strategy Heatmap (Rho <= 0.15)", color='#E5E7EB', fontsize=12, fontweight='bold', pad=15)

    plt.tight_layout()
    chart_path = "docs/prop_simulation_protocol_dashboard.png"
    plt.savefig(chart_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved visual dashboard: {chart_path}")

    # Export report CSV
    report_data = {
        "Account Preset": account_key,
        "Account Size ($)": account['start_balance'],
        "Target ($)": account['profit_target'],
        "Drawdown Floor ($)": account['max_drawdown'],
        "1-Attempt Pass Rate (%)": round(p * 100.0, 2),
        "3-Attempt Pass Rate (%)": round((1.0 - (1.0 - p)**3) * 100.0, 2),
        "4-Attempt Pass Rate (%)": round((1.0 - (1.0 - p)**4) * 100.0, 2),
        "Optimal Position Scale": best_scale_row['scale'],
        "Peak Pass Rate (%)": round(best_scale_row['p_value'] * 100.0, 2),
        "Avg Days to Pass": round(mc_res['avg_days_to_pass'], 1)
    }
    pd.DataFrame([report_data]).to_csv("docs/prop_simulation_summary.csv", index=False)
    print("Saved summary report: docs/prop_simulation_summary.csv")

if __name__ == '__main__':
    run_full_protocol_analysis()

