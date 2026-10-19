# Scripts Directory (`scripts/`)

This directory organizes all utility, backtesting, database maintenance, screening, and reporting scripts for **Rajat Alpha v67**.

Following SOLID principles and clean separation of concerns, all scripts are divided into specialized subdirectories:

---

## Subdirectory Structure

```text
scripts/
├── colab/          # Google Colab notebooks, generators, and institutional Monte Carlo simulators
├── db/             # Database queries, reconciliations, account audits, and maintenance tools
├── scanner/        # Weekly stock screening, technical ranking, and live signal monitoring
└── reporting/      # Executive PDF reporting and publication-grade exports
```

---

## Subdirectory Overview & Quick Reference

### 1. `scripts/colab/` — Institutional Backtesting & Monte Carlo Prop Simulator
Houses all Google Colab `.ipynb` notebooks and local backtest engines.
- `Rajat_Alpha_Institutional_Prop_Protocol.ipynb`: Master 15-cell Google Colab notebook implementing the 4-step framework (Map, Measure, Simulate, Operate), 10,000-run Monte Carlo simulations, capacity-constrained portfolio simulations, and 5-tab downloadable Excel workbook.
- `generate_prop_protocol_notebook.py`: Automated generator that synchronizes the latest v3.2 bot rules into the Colab notebook.
- `compare_4_configs_simulation.py`: Simulates 4 risk profiles ($10k capital, 15 max slots, score gating) and builds the multi-tab comparative spreadsheet.

### 2. `scripts/db/` — Database Operations & Broker Reconciliation
Handles the SQLite database lifecycle and reconciles open positions with Alpaca.
- `check_positions.py`: Verifies all open positions between SQLite and Alpaca API.
- `check_account_status.py`: Health check of Alpaca buying power, equity, and day trade limits.
- `db_manager.py`: Command-line interface to inspect tables, open/closed positions, and signals.
- `cleanup_db.py`: Database integrity verifier and VACUUM optimizer.
- `upgrade_db.py`: Migration utility for database schema updates.

### 3. `scripts/scanner/` — Weekly Screening & Signals
Screens candidate stocks and monitors real-time market signals.
- `rank_weekly_scan_symbols.py`: Evaluates scanned symbols against v3.2 swing criteria and outputs Tier 1 "Beast" stocks for the weekly watchlist.
- `signal_dashboard.py`: Interactive terminal dashboard for monitoring real-time signals.

### 4. `scripts/reporting/` — Executive Summary Reports
- `generate_executive_pdf.py`: Compiles the 2-page publication-grade PDF executive summary (`docs/Rajat_Alpha_v67_Executive_Summary.pdf`).

---

For detailed documentation, commands, and options for each subsystem, please refer to the README inside each respective folder:
- [scripts/colab/README.md](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/README.md)
- [scripts/db/README.md](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/db/README.md)
- [scripts/scanner/README.md](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/scanner/README.md)
- [scripts/reporting/README.md](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/reporting/README.md)
