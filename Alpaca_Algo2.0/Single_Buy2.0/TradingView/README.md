# TradingView Pine Script Suite (`TradingView/`)

This directory contains TradingView Pine Script (v6) implementations of the **Rajat Alpha v67 (Version 3.2)** institutional swing trading engine.

---

## Directory Structure

```text
TradingView/
├── README.md                                    # This Master Guide
├── Indicator/
│   └── Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced).pine  # Master v3.2 Indicator
└── Strategy/
    └── (Reserved for Pine Script Strategy backtesting engine)
```

---

## 🏛️ What is in the v3.2 Pine Script Indicator?

The updated script [`Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced).pine`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/TradingView/Indicator/Rajat%20Alpha%20v67%20Single%20Buy%20Enhanced%20%28US%20-%20Python-Synced%29.pine) is a **1-to-1 visual synchronization** of our Python production trading bot (`rajat_alpha_v67_single.py` v3.2):

### 1. 8-Stage Prioritized Gating System
- **Gate 1 & 1.5: Market Structure**: `50 SMA > 200 SMA`, `Close > 200 SMA`, and `21 EMA >= 50 SMA - 2.5%`.
- **Gate 2: Minervini Stage-2 Impulse Wave**: Verifies preceding swing high printed $\ge +5.0\%$ above 21 EMA in the last 20 bars, followed by an orderly retracement.
- **Gate 3: 5 Candlestick Reversal Patterns**:
  - Bullish Engulfing (Tier A, +1.0 pt)
  - Bullish Piercing (Tier A, +1.0 pt)
  - Tweezer Bottom (Tier B, +0.8 pt)
  - Bullish Hammer (Tier B, +0.8 pt)
  - Upside Reversal (Tier C, +0.6 pt)
- **Gate 4: Weekly MTF Trend Gate**: Weekly close must be strictly above Weekly 21 EMA.
- **Gate 5: Institutional Demand Zone**: Current daily low within 3.5% of 21-day lowest low.
- **Gate 6: Exhaustion Filters**:
  - Shooting star upper-wick rejection filter ($\ge 50\%$ wick or $\ge 2\times$ body size).
  - Extended stock filter (rejects candles gapping up $> 4\%$).
  - Stalling filter (rejects stocks churning in $< 5\%$ range for 8 days).
- **Gate 7: Institutional Conviction Scoring**: Enforces mandatory **Score $\ge 4.0$** threshold.

### 2. Dynamic Risk & Profit Suite (v3.2)
- **Hybrid ATR Initial Stop**: $1.5\times$ to $2.0\times$ ATR, bounded between 5% and 17%.
- **Multi-Stage Stop Stepper (Color-Coded Line)**:
  - `Stage 0 (Initial)`: Red line (ATR stop)
  - `Stage 1 (+5% Gain)`: Orange line (tightened to -4% from entry)
  - `Stage 2 (+8% Gain)`: Yellow line (stepped to Break-Even 0.0%)
  - `Stage 3 (+10% Gain)`: Green line (locks in +3% profit)
  - `Stage 4 (+15% Gain)`: Lime line (Runner mode, locks in +10% profit)
- **4-Tier Scaling Targets**:
  - Projected lines at +5% (T1), +10% (T2), and +15% (T3).
  - Visual badges plotted when each target is hit.
- **Dynamic Structural TES**: 21-day base hold with +10-day extensions when price holds above EMA21.
- **Catastrophic Circuit Breaker**: Immediate exit if low $\le -22\%$.

---

## 📋 How to Install in TradingView

1. Open [TradingView](https://www.tradingview.com) and open any daily chart (e.g. `AAPL`, `NVDA`, `ECPG`).
2. At the bottom of the screen, click on the **Pine Editor** tab.
3. Click **Open > New indicator**, or clear the existing template.
4. Copy the entire contents of [`Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced).pine`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/TradingView/Indicator/Rajat%20Alpha%20v67%20Single%20Buy%20Enhanced%20%28US%20-%20Python-Synced%29.pine) and paste it into the editor.
5. Click **Save** and name it `Rajat Alpha v67 Single Buy (v3.2)`.
6. Click **Add to chart**.

---

## 🔔 Setting Up TradingView Native Alerts

You can configure TradingView alerts on any stock or watchlist:
1. Right-click on the chart and select **Add Alert...**.
2. Under **Condition**, select `Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced v3.2)`.
3. Choose one of the built-in alert conditions:
   - `[Rajat Alpha v3.2] Buy Signal (B1)`: Triggers when a new high-conviction trade is executed.
   - `[Rajat Alpha v3.2] Trailing Stop Stepped`: Triggers when the stop is raised (-4%, Break-Even, +3%, or +10%).
   - `[Rajat Alpha v3.2] Target 1 Hit (+5%)`: Triggers when scaling out first 20%.
   - `[Rajat Alpha v3.2] Target 2 Hit (+10%)`: Triggers when scaling out next 25%.
   - `[Rajat Alpha v3.2] Runner Mode Triggered (+15%)`: Triggers when entering 30% runner mode.
   - `[Rajat Alpha v3.2] Position Closed`: Triggers on full exit (SL, TES, or Breaker).
