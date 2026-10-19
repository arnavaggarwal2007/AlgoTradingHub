# Configuration Directory (`config/`)

This directory houses all runtime configurations, parameters, and ticker watchlists for the **Rajat Alpha v67 (Version 3.2)** institutional swing trading engine.

---

## Files in this Directory

| File | Purpose | Description |
| :--- | :--- | :--- |
| `config.json` | **Primary System Configuration** | Central configuration file containing Alpaca API settings, paper/live mode flags, risk parameters, profit targets, dynamic trailing stop tiers, position sizing limits, and time-exit stops. |
| `watchlist.txt` | **Active Trading Watchlist** | List of symbols monitored during market hours by `rajat_alpha_v67_single.py`. One symbol per line. |
| `weekly_high_conviction_watchlist.txt` | **Weekly Beast Filter Output** | High-conviction Tier 1 symbols identified by `scripts/scanner/rank_weekly_scan_symbols.py`. Can be copied or merged into `watchlist.txt`. |
| `exclusionlist.txt` | **Global Exclusions** | Symbols blacklisted from algorithmic execution due to corporate actions, extreme illiquidity, or erratic spread behavior. |
| `selllist.txt` | **Priority Force-Sell List** | Symbols flagged for immediate liquidation regardless of stop/target status. |

---

## Key Parameters in `config.json` (v3.2 Institutional Standard)

```json
{
  "trading_rules": {
    "max_open_positions": 15,
    "max_trades_per_stock": 1,
    "max_trades_per_day": 3,
    "min_signal_score": 4.0,
    "per_trade_pct": 0.03,
    "max_allocation_per_stock_pct": 0.06,
    "max_equity_utilization_pct": 0.90
  },
  "risk_management": {
    "stop_loss_pct": 0.17,
    "target_1_pct": 0.05,
    "target_2_pct": 0.10,
    "target_3_pct": 0.15,
    "tier1_profit_pct": 0.05,
    "tier1_sl_pct": 0.04,
    "tier2_profit_pct": 0.10,
    "tier2_sl_pct": 0.00,
    "tier3_profit_pct": 0.15,
    "tier3_sl_pct": -0.03,
    "time_exit_days": 21,
    "catastrophic_stop_pct": 0.22
  }
}
```

---

## Operating Instructions

### Switching Between Paper and Live Trading
In `config.json`:
- For **Paper Trading**: Set `"paper": true` and use your Alpaca Paper API keys and endpoint (`https://paper-api.alpaca.markets`).
- For **Live Trading**: Set `"paper": false` and use your Alpaca Live API keys and endpoint (`https://api.alpaca.markets`).

### Updating Watchlist Symbols
Edit `config/watchlist.txt` with one uppercase ticker per line:
```text
AAPL
MSFT
AMZN
NVDA
```
Or generate high-conviction candidates using the automated scanner:
```bash
python scripts/scanner/rank_weekly_scan_symbols.py
```

