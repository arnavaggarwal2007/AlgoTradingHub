# Analysis & Diagnostic Tools Directory (`tools/`)

This directory provides interactive dashboards, diagnostic analyzers, and market scanning tools for **Rajat Alpha v67 (Version 3.2)**.

---

## Tool Catalog

| Tool | Type | Purpose | Description |
| :--- | :--- | :--- | :--- |
| `stock_analyzer.py` | CLI | **Live Position & Signal Inspection** | Dumps current open positions from SQLite, checks last 24h signals, today's trade count, and validates trading rules from `config/config.json`. |
| `benchmark_analyzer.py` | CLI | **Market Data & API Connectivity Check** | Connects to Alpaca API, fetches daily bars for SPY and QQQ, validates column structure, and tests calculation latency. |
| `watchlist_analyzer.py` | CLI | **Batch Watchlist Scanner** | Scans every symbol in `config/watchlist.txt` against the v3.2 entry filters and prints passing vs failing symbols. |
| `log_analyzer.py` | CLI | **Log Diagnostics & Error Auditor** | Parses `logs/rajat_alpha_v67.log`, summarizes error/warning counts, trades executed, and signal patterns over configurable date ranges. |
| `log_dashboard.py` | Web UI | **Interactive Log Dashboard** | Flask web interface running at `http://localhost:5001` with interactive date range pickers, visual error summaries, and CSV exports. |
| `preSwingTradeAnalysis/` | Web App | **Pre-Swing Trade Analysis Dash App** | Comprehensive interactive Dash web application with multi-timeframe charts, backtest simulation, news sentiment, and signal scoring. |

---

## Tool Execution Guide

### 1. Inspect Current Open Positions & Limits
```bash
python tools/stock_analyzer.py
```
*Outputs current open positions, entry prices, quantities, signal scores, and active risk limits.*

### 2. Verify Alpaca Data Feed Connectivity (SPY / QQQ)
```bash
python tools/benchmark_analyzer.py
```
*Verifies market data connection, date ranges, and latest bar prices.*

### 3. Analyze Entire Watchlist for Buy Signals
```bash
python tools/watchlist_analyzer.py
```

### 4. Audit Recent Bot Runtime Logs
```bash
# Analyze last 7 days of logs
python tools/log_analyzer.py --days 7

# Export log errors to CSV
python tools/log_analyzer.py --days 14 --csv docs/log_errors.csv
```

### 5. Launch the Web Log Dashboard
```bash
python tools/log_dashboard.py
# Open your browser at http://localhost:5001
```

### 6. Launch the Pre-Swing Trade Analysis Dashboard
```bash
python tools/preSwingTradeAnalysis/app.py
# Open your browser at http://localhost:8050
```

To run unit tests for the Pre-Swing Trade Analysis suite:
```bash
python -m pytest tools/preSwingTradeAnalysis/tests/test_backtest_service.py
```
