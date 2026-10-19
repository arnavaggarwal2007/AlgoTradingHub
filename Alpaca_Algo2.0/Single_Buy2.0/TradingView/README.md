# TradingView Pine Script Suite (`TradingView/`)

This directory contains the production-grade TradingView Pine Script (v6) implementations of the **Rajat Alpha v67 Single Buy (Version 3.2)** institutional swing trading engine.

Both the **Indicator** and the **Strategy** are 100% synchronized with the Python institutional trading engine (`rajat_alpha_v67_single.py` v3.2).

---

## Directory Structure

```text
TradingView/
├── README.md                                                             # Master Architecture & Setup Guide
├── Indicator/
│   └── Rajat Alpha v67 Single Buy v3.2 (Institutional Swing Engine).pine  # Visual Indicator & Alerts Engine
└── Strategy/
    └── Rajat Alpha v67 Single Buy Strategy v3.2.pine                     # Strategy Engine for Strategy Tester
```

---

## 🏛️ 1. Indicator vs. Strategy: When to Use Which?

| Capability | Indicator (`TradingView/Indicator/`) | Strategy (`TradingView/Strategy/`) |
| :--- | :--- | :--- |
| **Primary Use Case** | Visual chart overlays, interactive HUD tables, live alerts, manual discretionary trading | Quantitative backtesting, performance metrics, simulated order fills |
| **TradingView Execution** | `indicator(...)` mode | `strategy(...)` mode |
| **Strategy Tester Tab** | No (Visual only) | **Yes**: Instant Backtest Net Profit, Win Rate %, Profit Factor, Max Drawdown |
| **HUD Dashboard Table** | Yes (Top-right live performance table) | Yes (Top-right live performance table) |
| **Gate Rejection Stats** | Yes (Top-left gate rejection audit table) | Integrated in trade log comments |
| **Discretionary Signals** | Plots `B1`, `↑OPP` (opportunity), `↓REJ` | Executes `B1` orders, plots `↑OPP` for manual trades |
| **Alert Conditions** | 7 Native TradingView Alert conditions | Strategy alert orders |

---

## 🔬 2. Strategy & Indicator Architecture (v3.2)

### A. 8-Stage Prioritized Gating System
1. **[Gate 0] Broad Market Regime**: SPY and QQQ must both trade above their respective 50 SMAs.
2. **[Gate 1 & 1.5] Market Structure**: `50 SMA > 200 SMA`, `Close > 200 SMA`, and `21 EMA >= 50 SMA - 2.5% tolerance`.
3. **[Gate 2] Minervini Stage-2 Impulse Wave**: Preceding swing high printed $\ge +5.0\%$ above 21 EMA in the last 20 bars, followed by an orderly $\ge 3\%$ retracement.
4. **[Gate 3] 5 Candlestick Reversal Patterns**:
   - Bullish Engulfing (Tier A, +1.0 pt default)
   - Bullish Piercing (Tier A, +1.0 pt default)
   - Tweezer Bottom (Tier B, +0.8 pt default)
   - Bullish Hammer (Tier B, +0.8 pt default)
   - Upside Reversal (Tier C, +0.6 pt default)
5. **[Gate 4] Weekly MTF Trend Gate**: Weekly close must be strictly above Weekly 21 EMA (using `barmerge.lookahead_off` to eliminate repainting).
6. **[Gate 5] Institutional Demand Zone**: Current daily low within 3.5% of 21-day lowest low.
7. **[Gate 6] Exhaustion & Rejection Filters**:
   - Shooting star upper-wick rejection filter ($\ge 50\%$ wick or $\ge 2\times$ body size).
   - Extended stock filter (rejects candles gapping up $> 4\%$).
   - Stalling filter (rejects stocks churning in $< 5\%$ range for 8 days).
8. **[Gate 7] Institutional Conviction Scoring**: Enforces mandatory **Score $\ge 4.0$** threshold. Every scoring weight is fully configurable via Inputs!

### B. IBD-Style Relative Strength Composite Rating (0–100)
Directly mirrors lines 947–988 of `rajat_alpha_v67_single.py`:
- **Factor 1 (25% Weight)**: 1-Month Return vs QQQ (Alpha)
- **Factor 2 (25% Weight)**: 21-Day Up/Down Volume Ratio
- **Factor 3 (20% Weight)**: 21-Day Green vs Red Days Ratio
- **Factor 4 (20% Weight)**: 52-Week High Proximity (252 Trading Days)
- **Telemetry**: Displayed in the Top-Right HUD table (`IBD RS: XX.X/100`), in the live floating price badge, and in all signal tooltips.

### C. Visual Touch Boxes & Moving Average Interaction
- Detects pullbacks and touches to the **21 EMA**, **50 SMA**, and **200 SMA**.
- Draws small visual rectangles/boxes around the touch bars (Cyan for 21 EMA, Gold for 50 SMA, Purple for 200 SMA).
- **Max 4 Touches Enforced**: Per quantitative specification, touch boxes only display for the first 4 touches ($T1 \to T4$) and cease displaying thereafter.
- **Automatic Trend Reset**: Touch counters automatically reset to zero upon a Golden/Death cross (`50 SMA` crossing `200 SMA`).

### D. Dynamic Risk & Exit Suite (v3.2)
- **Hybrid ATR Initial Stop**: $1.5\times$ to $2.5\times$ ATR, bounded between 5% and 17%.
- **Multi-Stage Stop Stepper (Color-Coded Line)**:
  - `Stage 0 (Initial)`: Red line (ATR stop)
  - `Stage 1 (+5% Gain)`: Orange line (tightened to -4% from entry)
  - `Stage 2 (+8% Gain)`: Yellow line (stepped to Break-Even 0.0%)
  - `Stage 3 (+10% Gain)`: Green line (locks in +3% profit)
  - `Stage 4 (+15% Gain)`: Lime line (Runner mode, locks in +10% profit)
- **4-Tier Scaling Targets**:
  - `Target 1 (+5%)`: Scales out 20% of position
  - `Target 2 (+10%)`: Scales out 25% of position
  - `Target 3 (+15%)`: Scales out 25% of position (leaves 30% runner)
  - `Target 4 (+20%)`: Final target for runner
- **Dynamic Structural TES**: 21-day base hold with +10-day extensions when price holds above EMA21 (max 2 extensions).
- **Catastrophic Circuit Breaker**: Immediate exit if low $\le -22\%$.
- **Bar-Close Confirmation**: Evaluated on confirmed daily bar closes to avoid intraday wick whipsaws.

---

## 📋 How to Install & Use in TradingView

### Option 1: Running the Visual Indicator (`Indicator/`)
1. Open [TradingView](https://www.tradingview.com) on any daily stock chart (e.g., `AAPL`, `NVDA`, `ECPG`).
2. Click on the **Pine Editor** tab at the bottom.
3. Open [`TradingView/Indicator/Rajat Alpha v67 Single Buy v3.2 (Institutional Swing Engine).pine`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/TradingView/Indicator/Rajat%20Alpha%20v67%20Single%20Buy%20v3.2%20%28Institutional%20Swing%20Engine%29.pine).
4. Copy and paste the entire code into the Pine Editor.
5. Click **Save** and **Add to chart**.
6. Enjoy live HUD dashboard telemetry, B1/OPP/REJ signals, visual touch boxes, and configure alerts.

### Option 2: Running the Backtesting Strategy (`Strategy/`)
1. In the Pine Editor, open a new tab.
2. Open [`TradingView/Strategy/Rajat Alpha v67 Single Buy Strategy v3.2.pine`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/TradingView/Strategy/Rajat%20Alpha%20v67%20Single%20Buy%20Strategy%20v3.2.pine).
3. Copy and paste the strategy code into the Pine Editor.
4. Click **Save** and **Add to chart**.
5. Switch to the **Strategy Tester** tab at the bottom to inspect:
   - **Net Profit & Percentage Gain**
   - **Win Rate % and Profit Factor**
   - **Max Drawdown %**
   - **List of Trades** with exact entry/exit timestamps, partial fills (+5%, +10%, +15%, +20%), and stop executions.

---

## 🔔 Native Alert Triggers

The Indicator script provides 7 pre-configured alerts:
1. `[Rajat Alpha v3.2] Buy Signal (B1)`: High-conviction entry executed.
2. `[Rajat Alpha v3.2] Discretionary Opportunity (OPP)`: Setup qualified while position active (manual trading).
3. `[Rajat Alpha v3.2] Trailing Stop Stepped`: SL raised (-4%, Break-Even, +3%, or +10%).
4. `[Rajat Alpha v3.2] Target 1 Hit (+5%)`: First 20% scale-out.
5. `[Rajat Alpha v3.2] Target 2 Hit (+10%)`: Second 25% scale-out.
6. `[Rajat Alpha v3.2] Runner Mode Triggered (+15%)`: Third 25% scale-out, enters runner mode.
7. `[Rajat Alpha v3.2] Position Closed`: Full exit (SL, TES, or Breaker).
