# 🏛️ Institutional Weekly Swing Trading Screener & Radar (V3.5)

**Architecture**: Senior Quantitative Strategist & Multi-Time US Investing Champion (15+ Years Multi-Cycle Prop Experience)  
**Execution Target**: `Single_Buy2.0` / `rajat_alpha_v67_single.py` Live & Paper Trading Engine  
**Universe Coverage**:
1. **List A (Inside Major Indices)**: S&P 500, Nasdaq 100, Dow 30 (~530 liquid leaders)
2. **List B (Outside Major Indices)**: Broader Market High-Growth Mid-Caps, Russell 1000/2000, and IPO Momentum Leaders (~350+ leaders with Market Cap $\ge \$2\text{B}$)

---

## 1. Executive Summary & Why the Screener Was Redesigned

A generic screener (like a raw TradingView filter) only checks static mathematical conditions at one point in time. In real-world institutional swing trading, **a stock that passes generic criteria may still be completely un-tradeable on Monday**:

1. **The Extension Trap**: 
   - TradingView Rule 6 allows price to be between $0\%$ and $10\%$ above the 50 SMA.
   - If a stock is $9\%$ above the 50 SMA and $6\%$ above the 21 EMA, it passes TradingView's filter!
   - BUT in our live swing trading bot (`Single_Buy2.0`), Gate 2 strictly requires price to be in the pullback zone ($\le 2.5\%$ from 21 EMA or 50 SMA).
   - Therefore, the bot prints `❌ Gate 2 Pullback: FAILED (dist > 2.5%)` and skips it every day. By the time it pulls back 2 weeks later, the weekly list was already regenerated!
2. **The Defense Trap**:
   - Scanning only the S&P 500 or Dow 30 produces slow-moving, low-beta value stocks (e.g., MET, CAH, KO, WST, EG, CI) that lack aggressive institutional markup momentum.
   - The highest-velocity swing trading trades come from high-growth mid-caps, tech leaders, marine shipping, and medical growth outside the mega-cap indices.

**Version 3.5 bridges this gap completely** by introducing **Setup Horizon & Trading Readiness**:
- **Tier 1: TRIGGER-READY (0 to 3 Days / This Week)**: Already resting at the 21 EMA / 50 SMA demand zone ($\le 2.0\%$), ready for bot execution.
- **Tier 2: ON-DECK (1 to 2 Weeks)**: Pulling back towards the 21 EMA ($2.0\% - 4.2\%$), higher swing low ($SL_2 \ge SL_1$) verified, coiling in Volatility Contraction (VCP).
- **Tier 3: BASE FORMATION (2 to 3 Weeks)**: High-conviction Stage 2 leader resting after impulse breakout.

---

## 2. Dual Universe Architecture (Inside vs Outside Indices)

The screener segments candidates into two distinct institutional watchlists:

```
┌────────────────────────────────────────────────────────────────────────┐
│ TOTAL SCREENED UNIVERSE (~850+ US Equities, Market Cap >= $2B)         │
├────────────────────────────────────┬───────────────────────────────────┤
│ LIST A: INSIDE MAJOR INDICES       │ LIST B: OUTSIDE MAJOR INDICES     │
│ • S&P 500 Constituents             │ • High-Growth Mid-Cap Leaders     │
│ • Nasdaq 100 Leaders               │ • Top Russell 1000/2000 Momentum  │
│ • Dow Jones 30 Blue Chips          │ • Marine Shipping & Tankers       │
│                                    │ • MedTech & Biotech High-Flyers   │
│ (Liquid, Lower Volatility Anchors) │ (High-Beta Velocity Alpha Movers) │
└────────────────────────────────────┴───────────────────────────────────┘
```

In Google Colab, you can choose via dropdown:
- `Combined (Indices + Broader Growth)` (Default — scans all ~850+ stocks)
- `Inside Major Indices (S&P 500, Nasdaq 100, Dow 30)`
- `Outside Major Indices (Broader Growth & Mid-Caps)`

---

## 3. The 13 Core TradingView Rules (Exact Quantitative Gating)

Every candidate must satisfy all 13 rules before reaching the senior strategist filters:

| # | Parameter | Formula | Rationale |
|---|---|---|---|
| **1** | **Price Floor** | $\text{Price} \ge \$10.00$ | Eliminates low-float penny stocks and micro-cap churn. |
| **2** | **Market Cap** | $\text{Market Cap} \ge \$2.0\text{B}$ | Institutional liquidity floor; tight bid-ask spreads. |
| **3** | **YTD Performance** | $\text{Perf}_{\text{YTD}} > +8.0\%$ | Eliminates broken laggards; confirms macro bull tailwind. |
| **4** | **Intermediate Momentum** | $\text{EMA}_{21} \ge \text{SMA}_{50}$ | 21 EMA leads medium-term institutional benchmark. |
| **5** | **52W Low Clearance** | $\text{Price} \ge \text{Low}_{52\text{W}} \times 1.15$ | Minervini Stage 2 uptrend confirmation (+15% off low). |
| **6** | **50 SMA Accumulation** | $0.00 \le \frac{\text{Price} - \text{SMA}_{50}}{\text{SMA}_{50}} \le 0.10$ | Price is within 0% to 10% above 50 SMA. Prevents chasing. |
| **7** | **200 SMA Macro Clearance** | $\frac{\text{Price} - \text{SMA}_{200}}{\text{SMA}_{200}} \ge 0.10$ | Price trades $\ge 10\%$ above secular 200 SMA baseline. |
| **8** | **Golden Cross Ribbon** | $\text{SMA}_{50} \ge \text{SMA}_{200}$ | Long-term institutional trend alignment. |
| **9** | **Volume Accumulation** | $\Delta \text{Vol} > +10\%$ | Active buying surge vs prior day OR 21d avg volume. |
| **10** | **Fast Momentum** | $\text{EMA}_{10} \ge \text{EMA}_{21}$ | Fast moving average confirms short-term expansion. |
| **11** | **Liquidity Depth** | $\text{AvgVol}_{100\text{D}} > 250,000$ | Ensures clean fills without moving the tape. |
| **12** | **Intermediate Ribbon** | $\text{SMA}_{150} \ge \text{SMA}_{200}$ | Multi-month trend progression. |
| **13** | **Stage 2 Ribbon Alignment**| $\text{SMA}_{50} \ge \text{SMA}_{150}$ | Completes Weinstein/Minervini stacking: $50 \ge 150 \ge 200$. |

---

## 4. Senior Strategist Enhancements (Trading Readiness Engine)

### A. Setup Horizon Classification
- **Tier 1: TRIGGER-READY (0 to 3 Days / This Week)**
  - Price is within $\le 2.0\%$ of 21 EMA or $\le 2.5\%$ of 50 SMA.
  - In Daily Demand Zone ($\le 3.5\%$ from 21d low) or Weekly Demand Zone.
  - Moving average slopes flat or upward (not declining).
  - Showing reversal candlestick (Hammer, Engulfing, Piercing) or green volume absorption.
  - **Action**: Immediate buy candidate for the live bot this week.
- **Tier 2: ON-DECK (1 to 2 Weeks)**
  - Pulling back towards the 21 EMA ($2.0\% - 4.2\%$).
  - Higher swing low ($SL_2 \ge SL_1$) established with Volatility Contraction Pattern (VCP).
  - **Action**: Place on active radar; prepare limit order as price approaches 21 EMA.
- **Tier 3: BASE FORMATION (2 to 3 Weeks)**
  - Extended $>4.2\%$ above 21 EMA; consolidating near highs awaiting moving average convergence.

### B. Multi-Timeframe Demand Zone & Sell Zone Matrix
- **Daily Demand Zone**: $\text{Low} \le \text{Low}_{21\text{D}} \times 1.035$ (Matches Gate 5 in `Single_Buy2.0`).
- **Weekly Demand Zone**: Weekly close near Weekly 21 EMA ($\pm 3\%$) or $\le \text{Low}_{8\text{W}} \times 1.05$.
- **Monthly Demand Zone**: Monthly close $> \text{Monthly EMA}_{10}$ and resting near support.
- **Overextended / Sell Zone**: Price $> 5\%$ above 21 EMA or Shooting Star rejection with upper wick $>50\%$ of candle range.

### C. 30-Day Swing Pivot Structure Analysis
- Identifies $SL_1, SL_2$ (Swing Lows) and $SH_1, SH_2$ (Swing Highs) with **exact prices and calendar dates**.
- **Higher Swing Lows**: $SL_2 \ge SL_1 \times 0.995$ confirms buyers are stepping in at progressively higher prices.
- **Volatility Contraction Pattern (VCP)**: $(SH_2 - SL_2) \le (SH_1 - SL_1) \times 1.05$ confirms tightening trading range before breakout.

### D. Volume Surge & Pocket Pivot Accumulation
- Detects institutional accumulation: $\text{Volume} > \text{VOL\_SMA21}$ (or $+10\%$ vs prior day) accompanied by a green close ($\text{Close} > \text{Prev Close}$ and $\text{Close} \ge \text{Open}$).
- Tagged as `YES (Green Pocket Pivot)` or `YES (Volume Surge)`.

### E. Automated Trade Execution Plan
- **Suggested Entry**: Current close (Tier 1) or projected 21 EMA level (Tier 2).
- **Initial Stop Loss**: $\text{Entry} - (2.0 \times \text{ATR}_{14})$, bounded between $5.0\%$ and $10.0\%$ max risk.
- **Profit Targets**: Target 1 (+5%), Target 2 (+10%), Target 3 (+15%).
- **Risk/Reward Ratio**: Evaluated to Target 2 (must be $\ge 1.0$, typically $1.5–2.5$).

---

## 5. Visual Candlestick Charts in Google Colab

Version 3.5 renders publication-quality **35-day daily candlestick charts** directly inline in Colab:
- **Candlestick Colors**: Green (`#00e676`) for bullish bars, Red (`#ff5252`) for bearish bars.
- **Moving Average Overlays**:
  - `EMA10` (Cyan `#00e5ff`)
  - `EMA21` (Gold `#ffd700` — Prime Support)
  - `SMA50` (Purple `#e040fb` — Institutional Demand)
  - `SMA200` (Dark Red `#ff1744` dashed — Macro Baseline)
- **Shaded Demand Zone Band**: Translucent emerald band showing Daily Demand Zone ($\le 3.5\%$ from 21d low).
- **Swing Points**: Green markers $\blacktriangle$ for $SL_1, SL_2$ and red markers $\blacktriangledown$ for $SH_1, SH_2$ with price tags.
- **Projected Execution Lines**: Cyan dashed line (Entry), Red dashed line (Stop Loss), Light Green dotted line (Target 1), Gold dotted line (Target 2).
- **Executive Banner**: Displays Symbol, Category (`[INDEX]` or `[BROADER_MARKET]`), Setup Horizon, IQS Score, Star Rating, Demand Zone status, and Risk/Reward.

---

## 6. The 6-Sheet Institutional Excel Workbook

The exported Excel file (`weekly_swing_screener_results.xlsx`) is structured with 6 formatted sheets:

1. **Sheet 1: `Index_Watchlist_Top_Setups`**
   - Top 30 setups from S&P 500, Nasdaq 100, and Dow 30 sorted by IQS Score.
2. **Sheet 2: `Broader_Market_Alpha_Setups`**
   - Top 30 high-growth mid-cap and momentum setups outside major indices.
3. **Sheet 3: `Trigger_Ready_This_Week`**
   - Consolidated Tier 1 setups (already in buy zone $\le 2.0\%$ from 21 EMA/50 SMA, in demand zone, ready for bot execution this week).
4. **Sheet 4: `Multi_Timeframe_Demand_Matrix`**
   - Matrix showing Daily Demand, Weekly Demand, Monthly Demand, Sell Zone status, Volume Surge Tag, and higher low confirmation.
5. **Sheet 5: `All_Screened_Candidates`**
   - Complete quantitative dataset of every passing equity across all 13 rules.
6. **Sheet 6: `Watchlist_TXT_Export`**
   - Clean column containing top symbols ready to copy directly into `config/watchlist.txt`.

---

## 7. How to Run the Screener

### In Google Colab (1-Click Browser Execution)
Notebook: [`Rajat_Alpha_Institutional_Weekly_Screener.ipynb`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/Rajat_Alpha_Institutional_Weekly_Screener.ipynb)

1. Open in [Google Colab](https://colab.research.google.com/).
2. Select your desired universe from the dropdown form.
3. Click **Runtime -> Run all** (`Ctrl + F9`).
4. The notebook runs parallel batch downloads, filters all 13 rules + senior strategist criteria, renders the candlestick charts inline, and **automatically pops up browser download dialogs** for:
   - `weekly_swing_screener_results.xlsx` (6-Sheet Excel Workbook)
   - `watchlist.txt` (Ready to drop into the bot!)

### In Command-Line Interface (Local Python Run)
Script: [`run_institutional_weekly_screener.py`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/scanner/run_institutional_weekly_screener.py)

```bash
# Scan combined universe (~850+ stocks) and export 6-sheet Excel + watchlist.txt
python scripts/scanner/run_institutional_weekly_screener.py --universe combined --output reports/weekly_screener.xlsx --output-txt config/watchlist.txt

# Scan broader market growth leaders and generate candlestick charts
python scripts/scanner/run_institutional_weekly_screener.py --universe broader --output reports/broader_alpha.xlsx --charts --max-charts 15

# Scan major indices and automatically update live bot config
python scripts/scanner/run_institutional_weekly_screener.py --universe indices --update-watchlist --top 25
```

---

## 8. Direct Integration with Backtest Colab

To backtest the newly screened symbols in [`Rajat_Alpha_Institutional_Prop_Protocol.ipynb`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/Rajat_Alpha_Institutional_Prop_Protocol.ipynb) or [`Rajat_Alpha_v67_Colab_Backtest.ipynb`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/Rajat_Alpha_v67_Colab_Backtest.ipynb):
1. Copy the symbol list generated in Step 8 of the Colab notebook:
   ```python
   SCANNED_WATCHLIST = ['AAPL', 'CELH', 'INSW', 'CAKE', 'NVDA', ...]
   ```
2. Paste into the backtest notebook's symbol configuration cell and run all to see simulated historical performance, Sharpe ratio, win rate, and profit factor on this tailored watchlist.
3. Drop `watchlist.txt` directly into `C:\Alpaca_Algo\Alpaca_Algo2.0\Single_Buy2.0\config\watchlist.txt` for live trading!
