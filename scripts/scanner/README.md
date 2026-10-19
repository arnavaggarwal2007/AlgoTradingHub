# Scanner & Real-Time Monitoring Scripts (`scripts/scanner/`)

This directory contains screening algorithms, technical ranking engines, and live signal monitoring dashboards for **Rajat Alpha v67**.

---

## Available Scripts

| Script | Purpose | Description |
| :--- | :--- | :--- |
| `rank_weekly_scan_symbols.py` | **Weekly High-Conviction Stock Ranker** | Downloads 2-year daily bars for scanned symbols, simulates the exact v3.2 swing trading strategy (8-stage gating, ATR stops, trailing steppers, 4-tier exits), and calculates Institutional Conviction Scores to identify Tier 1 "Beast" stocks. |
| `signal_dashboard.py` | **Live Signal Terminal Dashboard** | Monitors real-time signals generated throughout the trading day, displaying scores, patterns, and execution decisions in an auto-refreshing terminal interface. |

---

## Weekly High-Conviction Stock Ranker (`rank_weekly_scan_symbols.py`)

### What it does:
1. Evaluates all tickers in the scanner candidate pool against the institutional v3.2 rules:
   - Volume filter: $\ge 500,000$ daily shares
   - Price range: $\$10.00 \le \text{Price} \le \$500.00$
   - Trend filter: Price $> \text{SMA50} > \text{SMA200}$
   - Pullback filter: RSI(14) between 40 and 65, Price within 2.5% of EMA21
   - Gap filter: Intraday gap $< 4\%$
2. Performs full historical trade reconstruction for each ticker.
3. Computes the **Conviction Score**:
   $$\text{Conviction Score} = \text{Win Rate} \times \text{Profit Factor} \times \sqrt{\text{Total Trades}}$$
4. Classifies tickers into tiers:
   - **Tier 1 (BEAST)**: Score $\ge 20.0$, Win Rate $\ge 70\%$, Profit Factor $\ge 2.5$.
   - **Tier 2 (STRONG)**: Score $\ge 12.0$, Win Rate $\ge 60\%$.
   - **Tier 3 (MODERATE)**: Valid setups with standard returns.
   - **Tier 4 (AVOID)**: Erratic volatility or low win rates.
5. Exports:
   - `docs/weekly_scanned_symbols_ranked.csv` (complete ranked metrics table)
   - `config/weekly_high_conviction_watchlist.txt` (Tier 1 tickers ready for active trading)
   - `docs/weekly_scan_all_trades.csv` (detailed trade log)

### How to Run:
```bash
python scripts/scanner/rank_weekly_scan_symbols.py
```

---

## Live Signal Dashboard (`signal_dashboard.py`)

### Usage:
```bash
# View today's signals
python scripts/scanner/signal_dashboard.py

# View signals from a specific date
python scripts/scanner/signal_dashboard.py --date 2026-10-16

# Watch mode (auto-refreshes terminal every 60 seconds during market hours)
python scripts/scanner/signal_dashboard.py --watch
```

