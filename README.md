# AlgoTradingHub - Master Quantitative Trading Repository

Welcome to **AlgoTradingHub**, the central repository housing algorithmic trading systems, execution bots, options engines, and institutional swing trading architectures.

---

## 🏛️ Repository Ecosystems

This repository is structured into two parallel ecosystems:

```text
AlgoTradingHub/
├── README.md                      # Master Repository Index
├── .gitignore                     # Repository-Wide Exclusion Rules
│
├── Alpaca_Algo/                   # Multi-Strategy Trading Ecosystem (v1.0)
│   ├── OptionStrategy/            # SPX spreads, Iron Condors, and Wheel Strategy
│   ├── Single_Buy/                # Foundational single-instrument execution bot
│   ├── Single_Buy_Real_Money/     # Real-money deployment configuration
│   ├── Dual_Buy/                  # Multi-instrument dual execution engine
│   ├── Etrade_Algo/               # E*TRADE broker integration module
│   ├── dashboard-prod/            # Production monitoring dashboard
│   ├── docs/                      # Strategy documentation and research
│   └── utils/                     # Shared algorithmic utilities
│
└── Alpaca_Algo2.0/                # Institutional Quantitative Architecture (v3.2)
    └── Single_Buy2.0/             # Institutional Swing Trading Engine (v3.2)
        ├── rajat_alpha_v67_single.py # Core Strategy Engine & Execution Bot
        ├── README.md              # Complete Institutional Architecture Guide
        ├── requirements.txt       # Production Dependencies
        ├── config/                # Gating rules, risk parameters, and watchlists
        ├── db/                    # Active production SQLite database ledger
        ├── backup/                # Cold historical backups (db and logs)
        ├── logs/                  # Active runtime and audit compliance logs
        ├── scripts/               # Colab notebooks, DB CLI tools, scanner, reports
        ├── docs/                  # Backtest reports, guides, executive PDFs, Excel
        ├── tools/                 # Diagnostics, log analyzers, Dash web app
        ├── enterprise_features/   # Value at Risk (VaR) calculator & UI dashboard
        └── tests/                 # Automated test suite (28/28 passing tests)
```

---

## 🚀 Ecosystem Overview

### 1. `Alpaca_Algo/` — Multi-Strategy Ecosystem
Contains production-tested algorithms across equities and options:
- **`OptionStrategy/`**: SPX Mechanical Spreads, Iron Condor Income, Wheel Premium Engine, and Regime-Adaptive Option Bots.
- **`Single_Buy/`**: Baseline single-symbol automated trading bot on Alpaca.
- **`Dual_Buy/`**: Concurrent dual-asset execution engine.
- **`Etrade_Algo/`**: E*TRADE broker integration and order router.
- **`dashboard-prod/`**: Real-time production monitoring web interface.

### 2. `Alpaca_Algo2.0/` — Institutional Quantitative Upgrade (v3.2)
Contains the institutional upgrade of the single-buy swing trading system:
- **8-Stage Prioritized Signal Gating**: Market regime, structure, impulse wave, candlestick reversal patterns, weekly MTF alignment, demand zone proximity, and exhaustion filters.
- **Dynamic Risk & Profit Suite**: Hybrid ATR-adaptive stops, multi-stage trailing stop stepper (-4% $\to$ break-even $\to$ +3%), 4-tier profit harvesting (+5%, +10%, +15%, 30% runner mode), and dynamic structural TES.
- **Institutional Prop Framework**: Complete 4-step framework (Map, Measure, Simulate, Operate), 10,000-run Monte Carlo simulations, capacity-constrained portfolio simulations, and master 5-tab Excel reporting.
- **SOLID Directory Architecture**: Full separation of concerns across `config/`, `db/`, `backup/`, `logs/`, `scripts/`, `docs/`, `tools/`, and `tests/`.

---

## 🛠️ Quickstart

To run the upgraded **Rajat Alpha v67 (Version 3.2)**:
```bash
cd Alpaca_Algo2.0/Single_Buy2.0
python -m unittest discover tests       # Verify 28/28 unit tests
python rajat_alpha_v67_single.py        # Launch swing trading bot
```

To run the **Options Strategy Suite**:
```bash
cd Alpaca_Algo/OptionStrategy
python dashboard.py                     # Launch options dashboard
```

---
*Maintained by Quantitative Engineering Team. Licensed for Private Client Algorithmic Trading.*
