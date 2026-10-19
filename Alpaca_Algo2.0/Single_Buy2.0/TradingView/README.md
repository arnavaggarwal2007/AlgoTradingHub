# TradingView Pine Script Suite (`TradingView/`)

This directory contains the production-grade TradingView Pine Script (v6) implementation of the **Rajat Alpha v67 (Version 3.2)** institutional swing trading engine.

---

## Directory Structure

```text
TradingView/
├── README.md                                                        # This Master Architecture & Setup Guide
├── Indicator/
│   └── Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced).pine  # Master v3.2 Indicator (Pine Script v6)
└── Strategy/
    └── (Reserved for Pine Script Strategy backtesting engine)
```

---

## 🏛️ What is in the v3.2 Pine Script Indicator?

The script [`Rajat Alpha v67 Single Buy Enhanced (US - Python-Synced).pine`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/TradingView/Indicator/Rajat%20Alpha%20v67%20Single%20Buy%20Enhanced%20%28US%20-%20Python-Synced%29.pine) is a **1-to-1 visual synchronization** of our Python production trading bot (`rajat_alpha_v67_single.py` v3.2):

### 1. 8-Stage Prioritized Gating System
- **[Gate 0] Broad Market Regime**: SPY and QQQ must both trade above their respective 50 SMAs.
- **[Gate 1 & 1.5] Market Structure**: `50 SMA > 200 SMA`, `Close > 200 SMA`, and `21 EMA >= 50 SMA - 2.5% tolerance`.
- **[Gate 2] Minervini Stage-2 Impulse Wave**: Preceding swing high printed $\ge +5.0\%$ above 21 EMA in the last 20 bars, followed by an orderly $\ge 3\%$ retracement.
- **[Gate 3] 5 Candlestick Reversal Patterns**:
  - Bullish Engulfing (Tier A, +1.0 pt default)
  - Bullish Piercing (Tier A, +1.0 pt default)
  - Tweezer Bottom (Tier B, +0.8 pt default)
  - Bullish Hammer (Tier B, +0.8 pt default)
  - Upside Reversal (Tier C, +0.6 pt default)
- **[Gate 4] Weekly MTF Trend Gate**: Weekly close must be strictly above Weekly 21 EMA (using `barmerge.lookahead_off` to eliminate repainting).
- **[Gate 5] Institutional Demand Zone**: Current daily low within 3.5% of 21-day lowest low.
- **[Gate 6] Exhaustion & Rejection Filters**:
  - Shooting star upper-wick rejection filter ($\ge 50\%$ wick or $\ge 2\times$ body size).
  - Extended stock filter (rejects candles gapping up $> 4\%$).
  - Stalling filter (rejects stocks churning in $< 5\%$ range for 8 days).
- **[Gate 7] Institutional Conviction Scoring**: Enforces mandatory **Score $\ge 4.0$** threshold. Every scoring weight is fully configurable via Inputs!

### 2. IBD-Style Relative Strength Composite Rating (0–100)
Directly mirrors lines 947–988 of `rajat_alpha_v67_single.py`:
- **Factor 1 (25% Weight)**: 1-Month Return vs QQQ (Alpha)
- **Factor 2 (25% Weight)**: 21-Day Up/Down Volume Ratio
- **Factor 3 (20% Weight)**: 21-Day Green vs Red Days Ratio
- **Factor 4 (20% Weight)**: 52-Week High Proximity (252 Trading Days)
- **Telemetry**: Displayed in the Top-Right HUD table (`IBD RS: XX.X/100`), in the live floating price badge, and in all signal tooltips.

### 3. Visual Touch Boxes & Moving Average Interaction
- Detects pullbacks and touches to the **21 EMA**, **50 SMA**, and **200 SMA**.
- Draws small visual rectangles/boxes around the touch bars (Cyan for 21 EMA, Gold for 50 SMA, Purple for 200 SMA).
- **Max 4 Touches Enforced**: Per quantitative specification, touch boxes only display for the first 4 touches ($T1 \to T4$) and cease displaying thereafter.
- **Automatic Trend Reset**: Touch counters automatically reset to zero upon a Golden/Death cross (`50 SMA` crossing `200 SMA`).

### 4. Signal Hierarchy & Tooltip Breakdown
- **`B1 (Score)` [Green Up Label]**: Primary automated swing trade entry (when all 8 gates pass and no position is open).
- **`↑OPP (Score)` [Yellow Arrow]**: Opportunity signal triggered when all criteria pass but an automated B1 position is already active. Ideal for manual discretionary execution!
- **`↓REJ (Reason)` [Red Down Label]**: Visual diagnostics showing the exact gate that disqualified a candidate (e.g. `SHOOTING_STAR`, `GAP>4%`, `STALLING`, `SCORE<4.0`, `MAX_DAILY_TRADES`).
- **Comprehensive Tooltip**: Hovering over any `B1` or `OPP` label displays the complete breakdown of every condition fulfilled, points earned, IBD rating, proposed stop loss, and projected profit targets.

### 5. Multi-Ribbon Visual Indicators at Bottom of Chart
- **Weekly Trend Ribbon (Triangle Up `▲`)**: Lime Green if Weekly Close > Weekly EMA21; Red if below.
- **Monthly Trend Ribbon (Triangle Down `▼`)**: Teal if Monthly Close > Monthly EMA10; Maroon/Red if below.
- **Volume Conviction Ribbon (Diamond `◆`)**: Orange for high-volume entry conviction, Blue for high-volume green candle, Pink for high-volume red candle.

### 6. Dynamic Risk & Exit Suite (v3.2)
- **Hybrid ATR Initial Stop**: $1.5\times$ to $2.5\times$ ATR, bounded between 5% and 17%.
- **Multi-Stage Stop Stepper (Color-Coded Line)**:
  - `Stage 0 (Initial)`: Red line (ATR stop)
  - `Stage 1 (+5% Gain)`: Orange line (tightened to -4% from entry)
  - `Stage 2 (+8% Gain)`: Yellow line (stepped to Break-Even 0.0%)
  - `Stage 3 (+10% Gain)`: Green line (locks in +3% profit)
  - `Stage 4 (+15% Gain)`: Lime line (Runner mode, locks in +10% profit)
- **4-Tier Scaling Targets**:
  - Projected lines at +5% (T1), +10% (T2), +15% (T3), and +20% (T4).
  - Visual badges plotted when each target is hit.
- **Dynamic Structural TES**: 21-day base hold with +10-day extensions when price holds above EMA21 (max 2 extensions).
- **Catastrophic Circuit Breaker**: Immediate exit if low $\le -22\%$.
- **Bar-Close Confirmation**: Stops evaluated on confirmed daily bar closes to avoid intraday wick whipsaws.

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
   - `[Rajat Alpha v3.2] Discretionary Opportunity (OPP)`: Triggers when a candidate setup passes all gates while a trade is running.
   - `[Rajat Alpha v3.2] Trailing Stop Stepped`: Triggers when the stop is raised (-4%, Break-Even, +3%, or +10%).
   - `[Rajat Alpha v3.2] Target 1 Hit (+5%)`: Triggers when scaling out first 20%.
   - `[Rajat Alpha v3.2] Target 2 Hit (+10%)`: Triggers when scaling out next 25%.
   - `[Rajat Alpha v3.2] Runner Mode Triggered (+15%)`: Triggers when entering 30% runner mode.
   - `[Rajat Alpha v3.2] Position Closed`: Triggers on full exit (SL, TES, or Breaker).
