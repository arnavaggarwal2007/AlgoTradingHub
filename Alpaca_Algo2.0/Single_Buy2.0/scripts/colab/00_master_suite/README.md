# 🏛️ Module 0: Master Quantitative Trading Suite (`00_master_suite/`)

## Overview
The **Master Quantitative Trading Suite** (`Rajat_Alpha_Master_Trading_Suite.ipynb`) serves as the **mission control landing page and unified execution bridge** for the entire Rajat Alpha quantitative swing trading ecosystem.

It allows you to:
1. **Run the Entire Ecosystem End-to-End**: Automatically pipe output from the **Weekly Screener** into the **Swing Strategy Backtester**, and pass empirical trade statistics directly into the **Institutional Prop Monte Carlo Risk Simulator**.
2. **Run Any Module Standalone**: Toggle execution modes using interactive `#@param` widgets to run the screener, backtester, or prop simulator independently.
3. **1-Click Artifact Packaging**: Download `watchlist.txt` (top 50 symbols ready for `Single_Buy2.0`), `weekly_swing_screener_results.xlsx` (6 formatted sheets), and `pipeline_trade_log.csv` directly from your browser.

---

## ⚡ Execution Instructions in Google Colab
1. Open [Google Colab](https://colab.research.google.com).
2. Click **Upload** and select `Rajat_Alpha_Master_Trading_Suite.ipynb`.
3. Select your desired execution mode in Step 2:
   - `Full End-to-End Pipeline (Screener -> Backtest -> Monte Carlo)`
   - `Module 1 Only: Weekly Screener & Dynamic Watchlist`
   - `Module 2 Only: Strategy Backtest on Custom / Scanned Watchlist`
   - `Module 3 Only: Institutional Prop Monte Carlo & Capacity Sizing`
4. Click **Runtime > Run all** (`Ctrl + F9`).
5. Step 5 displays the Top 10 candlestick charts with an interactive dropdown inspector for on-demand charting of all identified tickers.
