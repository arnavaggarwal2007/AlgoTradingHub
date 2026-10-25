# 📈 Module 2: Multi-Year Swing Strategy Backtester (`02_swing_backtest/`)

## Overview
This module performs rigorous, walk-forward event-driven backtesting of the **Rajat Alpha V67 (Version 3.2)** swing strategy over 5 years (2021–2026).

---

## 🎯 Core Features
1. **Position Sizing Methodology Comparison**:
   - **Approach 1**: Fixed 3% Capital Allocation per trade.
   - **Approach 2**: Risk-Based Equal Risk Contribution (e.g. 2% account equity risk adjusted by ATR stop distance).
2. **Execution Realism**:
   - Market orders vs SOEE Midpoint limit orders.
   - Hybrid ATR stop loss bounded between 5% and 10%.
   - 4-Tier partial profit taking: +5% (PT1), +10% (PT2), +15% (PT3), and Runner Mode.
   - Dynamic 21-day Time Exit Stop (TES).
3. **Comprehensive Performance Metrics**:
   - Total Return (%), CAGR (%), Max Drawdown (%), Sharpe Ratio, Win Rate (%), and Profit Factor.

---

## ⚡ Execution
- **In Colab**: Upload `Rajat_Alpha_v67_Colab_Backtest.ipynb` and click **Runtime > Run all**.
- **Locally via CLI**:
  ```bash
  python scripts/colab/backtest_colab_pipeline.py
  ```
