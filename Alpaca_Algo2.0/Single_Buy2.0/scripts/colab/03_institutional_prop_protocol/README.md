# 🎲 Module 3: Institutional Prop Protocol & Monte Carlo Risk Engine (`03_institutional_prop_protocol/`)

## Overview
Implements the **Institutional Prop Firm Protocol** designed for quantitative multi-million dollar prop firm challenges and high-capacity account compounding.

---

## 🎯 The 4-Step Institutional Framework
1. **Step 1: Map the Account**: Translates institutional rules into hard mathematical constraints (Min Signal Score >= 4.0, Max 15 Positions, 3 Trades/Day limit, Max 90% Utilization).
2. **Step 2: Measure the Shape**: Empirical trade expectancy ($Win Rate pprox 77.8\%$, $PF pprox 3.68$, $E pprox +\$137.95$).
3. **Step 3: Simulate & Optimize**: 10,000-path Monte Carlo simulations evaluating single-attempt vs 4-attempt cumulative pass probabilities and risk of drawdown breach.
4. **Step 4: Operate & Execute**: Real-time execution guidelines for `Single_Buy2.0`.

---

## 📥 Artifacts Generated
- `docs/rajat_alpha_4_configs_master_simulation.xlsx` (5-tab master comparison across Conservative, Target v3.2, Aggressive, Ultra configurations).
- `rajat_alpha_scanned_trade_log.csv` (Complete simulated trade history).
