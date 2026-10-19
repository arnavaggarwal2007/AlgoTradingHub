# Colab Backtest & Monte Carlo Prop Simulator (`scripts/colab/`)

This directory contains Jupyter notebooks and Python simulation pipelines implementing the **Institutional Prop Firm Protocol** for the Rajat Alpha v67 (Version 3.2) trading strategy.

---

## Key Files

| File | Purpose | Description |
| :--- | :--- | :--- |
| `Rajat_Alpha_Institutional_Prop_Protocol.ipynb` | **Master Google Colab Notebook** | End-to-end 15-cell Colab notebook. Runs the 4-step framework (Map, Measure, Simulate, Operate), multi-strategy correlation, capacity-constrained execution simulation, 10,000-run Monte Carlo simulations, and generates a 5-tab downloadable Excel workbook. |
| `TheInstitutionalProtocol_PropSimulations.ipynb` | **Original Reference Protocol** | Masterclass reference notebook containing the foundational 4-step institutional framework. |
| `Rajat_Alpha_v67_Scanned_Watchlist_Backtest.ipynb` | **Watchlist Backtest Notebook** | Specialized notebook to backtest custom watchlists and export trade logs. |
| `generate_prop_protocol_notebook.py` | **Notebook Generator** | Python script that programmatically compiles `Rajat_Alpha_Institutional_Prop_Protocol.ipynb`, ensuring all 15 cells remain in sync with `rajat_alpha_v67_single.py`. |
| `compare_4_configs_simulation.py` | **4-Configuration Simulator** | Runs local capacity-constrained simulations across 4 risk profiles (Conservative, Target v3.2, Aggressive, Ultra) and builds the 5-tab Excel workbook (`docs/rajat_alpha_4_configs_master_simulation.xlsx`). |
| `backtest_colab_pipeline.py` | **Backtest Pipeline** | Historical simulation engine executing v3.2 trading rules across multiple years of daily market bars. |

---

## The Four-Step Institutional Framework

1. **Step 1: Map the Account**
   - Translate all trading rules into mathematical constraints:
     - Minimum Signal Score: $\ge 4.0$
     - Max Open Positions: 15
     - Daily Execution Limit: 3 trades
     - Risk per Trade: 3% of Equity (max 6% per ticker)
     - Max Portfolio Utilization: 90%
2. **Step 2: Measure the Shape**
   - Calculate statistical parameters from trade history:
     - Win Rate ($P_{win} = 77.8\%$)
     - Profit Factor ($PF = 3.68$)
     - Risk-to-Reward Ratio ($R:R = 1.05$)
     - Expectancy ($E = +\$137.95$ per trade)
3. **Step 3: Simulate & Optimize**
   - 10,000-path Monte Carlo simulation.
   - Evaluates pass probability across 1, 2, 3, and 4 attempts.
   - Proves why a 90% cumulative pass rate across 4 attempts is statistically robust.
4. **Step 4: Operate & Execute**
   - Real-time execution via `rajat_alpha_v67_single.py` with dynamic trailing stop tiers (-4%, break-even, +3%), time-exit stop (21 days), and catastrophic breakers.

---

## 5-Tab Master Excel Workbook

Generated in Cell 15 of the Colab notebook or locally via:
```bash
python scripts/colab/compare_4_configs_simulation.py
```

The output file is saved to `docs/rajat_alpha_4_configs_master_simulation.xlsx` and contains:
- **Tab 1: `Comparison_Summary`**: Metrics comparison of all 4 configurations side-by-side (Final Equity, Total Return %, CAGR %, Sharpe, Max Drawdown %, Executed vs Skipped Trades).
- **Tab 2: `Config_1_Conservative`**: All historical trade setups with execution status (`EXECUTED` vs `SKIPPED (Max Capacity Full)` vs `SKIPPED (Score < Min)`).
- **Tab 3: `Config_2_Target_v3.2`**: Trades for the active production strategy.
- **Tab 4: `Config_3_Aggressive`**: Trades for higher capacity/position sizing.
- **Tab 5: `Config_4_Ultra`**: Trades for unrestricted compounding.

---

## How to Run in Google Colab

1. Open [Google Colab](https://colab.research.google.com).
2. Click **Upload** and select `scripts/colab/Rajat_Alpha_Institutional_Prop_Protocol.ipynb`.
3. In the Colab menu, click **Runtime > Run all**.
4. Cells 1–15 will execute sequentially, rendering all interactive plots, probability distributions, equity curves, and automatically providing direct download buttons for:
   - `rajat_alpha_scanned_trade_log.csv` (complete raw trade log)
   - `rajat_alpha_4_configs_master_simulation.xlsx` (5-tab master workbook)

