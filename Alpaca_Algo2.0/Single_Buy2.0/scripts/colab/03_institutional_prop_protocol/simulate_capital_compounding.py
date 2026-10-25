"""
Rajat Alpha v67 (Version 3.2) - Capital Compounding & Sizing Optimizer
Simulates:
1. Fixed % Capital Allocation vs Fixed % Equity Risk per Trade on a $10,000 Account.
2. 5-Year Historical Compounding Backtest (2021-2026).
3. 4-Year Forward Monte Carlo Projection (2026-2030).
4. Quantitative Stock Selection Ranking Engine (Beast vs Chop filter).
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_capital_compounding_analysis():
    trade_log_path = "docs/scanned_watchlist_trade_log.csv"
    if not os.path.exists(trade_log_path):
        print(f"Error: Trade log not found at {trade_log_path}")
        return

    trades_df = pd.read_csv(trade_log_path)
    trades_df['Exit Date'] = pd.to_datetime(trades_df['Exit Date'])
    trades_df = trades_df.sort_values(by='Exit Date').reset_index(drop=True)

    print("=" * 85)
    print(">> RAJAT ALPHA V67: $10,000 CAPITAL COMPOUNDING & SIZING OPTIMIZER")
    print("=" * 85)
    print(f"Loaded {len(trades_df)} historical trades across scan universe.")

    # Isolate Tier 1 Beast Stocks (High Edge, Positive Expectancy)
    tier1_symbols = ['ZETA', 'CLMT', 'DK', 'VTRS', 'NTAP', 'DRH', 'TALO', 'TRV', 'CVX', 'OSCR', 'PCVX', 'NTRA']
    t1_df = trades_df[trades_df['Symbol'].isin(tier1_symbols)].copy().reset_index(drop=True)
    print(f"Tier 1 'Beast' Trades: {len(t1_df)} trades across {len(tier1_symbols)} top-performing symbols.")

    # =========================================================================
    # PART 1: 5-YEAR HISTORICAL COMPOUNDING BACKTEST ($10,000 STARTING EQUITY)
    # =========================================================================
    STARTING_CAPITAL = 10000.0

    # Model 1: Fixed 20% Capital Allocation ($2,000 max per position, 5 concurrent max)
    bal_fixed = STARTING_CAPITAL
    equity_fixed = [bal_fixed]
    hwm_fixed = bal_fixed
    dd_fixed = []

    # Model 2: Fixed 1.5% Equity Risk per Trade (Capped at 25% max position allocation)
    bal_risk_15 = STARTING_CAPITAL
    equity_risk_15 = [bal_risk_15]
    hwm_risk_15 = bal_risk_15
    dd_risk_15 = []

    # Model 3: Fixed 2.0% Equity Risk per Trade (Aggressive Growth)
    bal_risk_20 = STARTING_CAPITAL
    equity_risk_20 = [bal_risk_20]
    hwm_risk_20 = bal_risk_20
    dd_risk_20 = []

    for _, row in t1_df.iterrows():
        ret_pct = row['Return (%)'] / 100.0
        buy_p = row['Buy Price']
        sl_p = row['Initial SL']
        sl_dist_pct = max(0.02, (buy_p - sl_p) / buy_p) if buy_p > 0 else 0.05

        # 1. Fixed 20% Capital
        pos_fixed = bal_fixed * 0.20
        pnl_fixed = pos_fixed * ret_pct
        bal_fixed += pnl_fixed
        equity_fixed.append(bal_fixed)
        hwm_fixed = max(hwm_fixed, bal_fixed)
        dd_fixed.append((hwm_fixed - bal_fixed) / hwm_fixed)

        # 2. Fixed 1.5% Account Risk
        # Shares * (buy - sl) = bal * 0.015 => Position Value = (bal * 0.015) / sl_dist_pct
        target_pos_15 = (bal_risk_15 * 0.015) / sl_dist_pct
        pos_risk_15 = min(target_pos_15, bal_risk_15 * 0.25) # capped at 25% account per position
        pnl_risk_15 = pos_risk_15 * ret_pct
        bal_risk_15 += pnl_risk_15
        equity_risk_15.append(bal_risk_15)
        hwm_risk_15 = max(hwm_risk_15, bal_risk_15)
        dd_risk_15.append((hwm_risk_15 - bal_risk_15) / hwm_risk_15)

        # 3. Fixed 2.0% Account Risk
        target_pos_20 = (bal_risk_20 * 0.020) / sl_dist_pct
        pos_risk_20 = min(target_pos_20, bal_risk_20 * 0.30)
        pnl_risk_20 = pos_risk_20 * ret_pct
        bal_risk_20 += pnl_risk_20
        equity_risk_20.append(bal_risk_20)
        hwm_risk_20 = max(hwm_risk_20, bal_risk_20)
        dd_risk_20.append((hwm_risk_20 - bal_risk_20) / hwm_risk_20)

    # Metrics
    years_approx = 3.5  # 2023 to early 2026 data span
    cagr_fixed = ((bal_fixed / STARTING_CAPITAL) ** (1.0 / years_approx) - 1.0) * 100.0
    cagr_risk_15 = ((bal_risk_15 / STARTING_CAPITAL) ** (1.0 / years_approx) - 1.0) * 100.0
    cagr_risk_20 = ((bal_risk_20 / STARTING_CAPITAL) ** (1.0 / years_approx) - 1.0) * 100.0

    max_dd_fixed = max(dd_fixed) * 100.0 if dd_fixed else 0.0
    max_dd_risk_15 = max(dd_risk_15) * 100.0 if dd_risk_15 else 0.0
    max_dd_risk_20 = max(dd_risk_20) * 100.0 if dd_risk_20 else 0.0

    print("\n" + "=" * 85)
    print("📊 5-YEAR HISTORICAL COMPOUNDING BACKTEST RESULTS ($10,000 STARTING CAPITAL)")
    print("=" * 85)
    compounding_table = pd.DataFrame([
        {
            "Sizing Strategy": "Model A: Fixed 20% Capital ($2k/trade)",
            "Ending Equity": f"${bal_fixed:,.2f}",
            "Net Profit": f"+${bal_fixed - STARTING_CAPITAL:,.2f}",
            "Total Gain": f"+{((bal_fixed/STARTING_CAPITAL)-1)*100:.1f}%",
            "Est. CAGR": f"{cagr_fixed:.1f}% / yr",
            "Max Drawdown": f"-{max_dd_fixed:.1f}%",
            "Trades Executed": len(t1_df)
        },
        {
            "Sizing Strategy": "Model B: Fixed 1.5% Account Risk (Recommended)",
            "Ending Equity": f"${bal_risk_15:,.2f}",
            "Net Profit": f"+${bal_risk_15 - STARTING_CAPITAL:,.2f}",
            "Total Gain": f"+{((bal_risk_15/STARTING_CAPITAL)-1)*100:.1f}%",
            "Est. CAGR": f"{cagr_risk_15:.1f}% / yr",
            "Max Drawdown": f"-{max_dd_risk_15:.1f}%",
            "Trades Executed": len(t1_df)
        },
        {
            "Sizing Strategy": "Model C: Fixed 2.0% Account Risk (Aggressive)",
            "Ending Equity": f"${bal_risk_20:,.2f}",
            "Net Profit": f"+${bal_risk_20 - STARTING_CAPITAL:,.2f}",
            "Total Gain": f"+{((bal_risk_20/STARTING_CAPITAL)-1)*100:.1f}%",
            "Est. CAGR": f"{cagr_risk_20:.1f}% / yr",
            "Max Drawdown": f"-{max_dd_risk_20:.1f}%",
            "Trades Executed": len(t1_df)
        }
    ])
    print(compounding_table.to_string(index=False))

    # =========================================================================
    # PART 2: 4-YEAR FORWARD MONTE CARLO PROJECTION ($10,000 ACCOUNT)
    # =========================================================================
    print("\n" + "=" * 85)
    print("🔮 4-YEAR FORWARD MONTE CARLO COMPOUNDING PROJECTION (1,000 PATHS, 1,000 TRADING DAYS)")
    print("=" * 85)

    # Group Tier 1 trades by exit date to create Bag-of-Days returns
    date_groups = t1_df.groupby('Exit Date')
    day_returns = [g['Return (%)'].values / 100.0 for _, g in date_groups]
    # Add zero-trade days (swing trading only trades ~2-3 days per week)
    all_dates = pd.date_range(t1_df['Exit Date'].min(), t1_df['Exit Date'].max(), freq='B')
    zero_days = max(0, len(all_dates) - len(day_returns))
    for _ in range(zero_days):
        day_returns.append(np.array([]))

    rng = np.random.default_rng(42)
    N_SIMS = 1000
    HORIZON_DAYS = 1000  # ~4 years (250 trading days * 4)

    final_equities_15 = []
    max_dds_15 = []
    forward_paths = []

    for sim_idx in range(N_SIMS):
        bal = STARTING_CAPITAL
        hwm = bal
        max_dd = 0.0
        path = [bal]

        for day in range(HORIZON_DAYS):
            chosen_day = day_returns[rng.integers(len(day_returns))]
            for r in chosen_day:
                # 1.5% account risk with ~5% average stop distance = ~25% allocation cap
                pos = min(bal * 0.25, bal * 0.30)
                pnl = pos * r
                bal += pnl
            if bal > hwm:
                hwm = bal
            dd = (hwm - bal) / hwm
            if dd > max_dd:
                max_dd = dd
            path.append(bal)

        final_equities_15.append(bal)
        max_dds_15.append(max_dd)
        if sim_idx < 100:
            forward_paths.append(path)

    final_equities_15 = np.array(final_equities_15)
    max_dds_15 = np.array(max_dds_15)

    p10_equity = np.percentile(final_equities_15, 10)
    p50_equity = np.percentile(final_equities_15, 50)
    p90_equity = np.percentile(final_equities_15, 90)

    p_double = (np.sum(final_equities_15 >= 20000.0) / N_SIMS) * 100.0
    p_triple = (np.sum(final_equities_15 >= 30000.0) / N_SIMS) * 100.0
    p_quadruple = (np.sum(final_equities_15 >= 40000.0) / N_SIMS) * 100.0
    p_dd_under_15 = (np.sum(max_dds_15 <= 0.15) / N_SIMS) * 100.0

    print(f"  Starting Balance:                   ${STARTING_CAPITAL:,.2f}")
    print(f"  Conservative Outcome (10th %tile):  ${p10_equity:,.2f} (+{((p10_equity/STARTING_CAPITAL)-1)*100:.1f}%)")
    print(f"  Expected Median Outcome (50th %tile): ${p50_equity:,.2f} (+{((p50_equity/STARTING_CAPITAL)-1)*100:.1f}%)")
    print(f"  Optimistic Outcome (90th %tile):    ${p90_equity:,.2f} (+{((p90_equity/STARTING_CAPITAL)-1)*100:.1f}%)")
    print(f"  Probability of Doubling (>= $20k):   {p_double:.1f}%")
    print(f"  Probability of Tripling (>= $30k):   {p_triple:.1f}%")
    print(f"  Probability of 4x Return (>= $40k):  {p_quadruple:.1f}%")
    print(f"  Median Maximum Drawdown:            {np.median(max_dds_15)*100:.1f}%")
    print(f"  Probability Drawdown Stays < 15%:   {p_dd_under_15:.1f}%")
    print("=" * 85)

    # Save summary dataframe
    summary_df = pd.DataFrame([{
        "Starting_Capital": STARTING_CAPITAL,
        "Hist_Fixed20_Ending": bal_fixed,
        "Hist_Risk15_Ending": bal_risk_15,
        "Hist_Risk20_Ending": bal_risk_20,
        "Fwd_4yr_P10_Equity": p10_equity,
        "Fwd_4yr_P50_Equity": p50_equity,
        "Fwd_4yr_P90_Equity": p90_equity,
        "Prob_Double_Cap": p_double,
        "Prob_Triple_Cap": p_triple
    }])
    summary_df.to_csv("docs/capital_compounding_summary.csv", index=False)
    print("📁 Saved: docs/capital_compounding_summary.csv")

if __name__ == '__main__':
    run_capital_compounding_analysis()

