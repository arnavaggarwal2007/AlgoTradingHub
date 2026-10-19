# TradingView Central Repository (`TradingView/`)

This directory is the dedicated TradingView Pine Script repository, organized parallel to `Alpaca_Algo` and `Alpaca_Algo2.0`. It preserves all original, current, and historical versions of Rajat Alpha indicators and backtesting strategies.

---

## Directory Hierarchy

```text
TradingView/
├── README.md                                                             # Master Version History & Setup Guide
├── Indicator/
│   ├── Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced) (Original).pine  # Original User-Shared Baseline
│   └── Rajat Alpha v67 Single Buy v3.2 (Institutional Swing Engine).pine         # Latest Upgraded v3.2 Engine
└── Strategy/
    └── Rajat Alpha v67 Single Buy v3.2 (Institutional Swing Engine) stgy.pine    # Strategy Engine for Strategy Tester
```

---

## 🏛️ Version Index & Preserved Scripts

### 1. Indicators (`TradingView/Indicator/`)
- **`Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced) (Original).pine`**:
  - The original Pine Script indicator shared by the user before v3.2 enhancements.
  - Preserved in its original state for reference, comparison, and legacy execution.
  - Includes: 5-point scoring system, basic touch stars (`*`), weekly ribbon, and top-right HUD table.
- **`Rajat Alpha v67 Single Buy v3.2 (Institutional Swing Engine).pine`**:
  - Fully synchronized with `rajat_alpha_v67_single.py` (v3.2).
  - Includes: 8-stage prioritized gating, 4-factor IBD RS Composite (0–100 rating), moving average touch boxes capped at 4 touches ($T1 \to T4$) with trend resets, configurable scoring weights, discretionary `↑OPP` opportunity signals, bottom multi-ribbons (`▲`, `▼`, `◆`), and detailed tooltips.

### 2. Strategies (`TradingView/Strategy/`)
- **`Rajat Alpha v67 Single Buy v3.2 (Institutional Swing Engine) stgy.pine`**:
  - Built specifically for the **TradingView Strategy Tester** tab.
  - Simulates fills for automated backtesting: Net Profit ($/%), Win Rate %, Profit Factor, Max Drawdown %, and List of Trades.
  - Enforces Single Buy rule (`pyramiding=0`), hybrid ATR initial stop, 4-tier partial scaling (+5%, +10%, +15%, +20%), dynamic stop stepper, structural TES (21d + extensions), and catastrophic circuit breaker (-22%).

---

## 📥 Adding Additional Versions

When you have additional Pine Script versions to preserve:
1. **Indicator versions**: Save them into `TradingView/Indicator/` with a descriptive version tag (e.g. `Rajat Alpha v65.pine`, `Rajat Alpha v66.pine`).
2. **Strategy versions**: Save them into `TradingView/Strategy/` with the `stgy` suffix.
3. Simply share the Pine code in chat or paste it into this folder, and Antigravity will automatically index, validate, and synchronize them with GitHub `AlgoTradingHub`.
