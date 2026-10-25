# 🏛️ Institutional Weekly Swing Trading Screener & Watchlist Generator

**Architecture**: Senior Quantitative Strategist & Multi-Time US Investing Champion  
**Target Universe**: S&P 500, Nasdaq 100, Dow Jones Industrial Average (Dow 30), and Institutional Liquid Leaders  
**Delivery Formats**: 
1. Interactive Google Colab Notebook: [`Rajat_Alpha_Institutional_Weekly_Screener.ipynb`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/Rajat_Alpha_Institutional_Weekly_Screener.ipynb)
2. Production Command-Line Screener: [`run_institutional_weekly_screener.py`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/scanner/run_institutional_weekly_screener.py)
3. Multi-Sheet Institutional Excel Workbook: (`.xlsx` with Top Watchlist, All Candidates, and Direct `config/watchlist.txt` copy sheet)

---

## 1. Executive Strategy Summary

In multi-million-dollar swing trading operations, **asset selection accounts for over 70% of outperformance**. A robust trading system does not trade random symbols or lagging cyclicals; it hunts for high-velocity institutional leaders emerging from sound consolidation bases with upward moving average momentum.

This institutional engine filters thousands of US-listed equities across major market benchmarks down to the top 15–25 highest-conviction swing trading candidates for the upcoming week. It combines:
1. **The Exact 13 TradingView Screener Rules** requested for structural trend, volume expansion, and moving average stacking.
2. **Mark Minervini Stage 2 Trend Template Criteria** (52-week high clearance and base breakout readiness).
3. **Institutional Moving Average Slopes & Curvature** (rejecting downward-pointing averages, favoring flat/turning and strongly upward trajectories).
4. **Precision Buy Zone Classification** (21 EMA prime zone, 50 SMA institutional demand zone, and Dual Convergence Sweet Spots).
5. **30-Day Swing Structure Analyzer** (verifying at least two swing highs and two swing lows, requiring Higher Swing Lows $SL_2 \ge SL_1$ and Volatility Contraction Pattern / VCP).
6. **Institutional Quality Score (IQS: 0–100)** and 5-Star Setup Rating to mathematically prioritize equal-scoring setups.
7. **Automated Trade Execution Plan** calculating exact Suggested Entry, ATR-based Stop Loss (bounded between 5% and 10%), Multi-Tier Profit Targets (+5%, +10%, +15%), and Risk/Reward Ratios.

---

## 2. Quantitative Screening Criteria Breakdown

### Part A: The 13 Core TradingView Screener Rules

Every candidate must pass 100% of the following 13 institutional gating filters:

| # | Screener Parameter | Quantitative Formula | Strategic Rationale |
|---|---|---|---|
| **1** | **Price Floor** | $\text{Price} \ge \$10.00$ | Eliminates low-float penny stocks and highly erratic micro-caps subject to retail pump-and-dumps. |
| **2** | **Market Capitalization** | $\text{Market Cap} \ge \$2.0\text{ Billion}$ | Guarantees mid-to-mega cap institutional liquidity, ensuring tight bid-ask spreads and minimal slippage. |
| **3** | **YTD Performance** | $\text{Perf}_{\text{YTD}} > +8.0\%$ | Eliminates lagging, structurally broken names and confirms macro trend leadership relative to risk-free yield. |
| **4** | **Intermediate Momentum** | $\text{EMA}_{21} \ge \text{SMA}_{50}$ | Verifies intermediate momentum is accelerating above the medium-term institutional benchmark. |
| **5** | **52-Week Low Clearance** | $\text{Price} \ge \text{Low}_{52\text{W}} \times 1.15$ | Asset must be at least +15% above its 52-week low, confirming Stage 1 accumulation is complete and Stage 2 uptrend is live. |
| **6** | **50 SMA Proximity Window** | $0.00 \le \frac{\text{Price} - \text{SMA}_{50}}{\text{SMA}_{50}} \le 0.10$ | Price is between 0% and 10% above its 50-day moving average. Prevents chasing vertically overextended stocks (>10% above SMA50) while ensuring price has not broken below institutional support. |
| **7** | **200 SMA Clearance** | $\frac{\text{Price} - \text{SMA}_{200}}{\text{SMA}_{200}} \ge 0.10$ | Price must be at least +10% above its 200-day moving average, guaranteeing genuine long-term bull market structure. |
| **8** | **Golden Cross Structure** | $\text{SMA}_{50} \ge \text{SMA}_{200}$ | Long-term institutional trend alignment. Protects against death crosses and secular bear phases. |
| **9** | **Volume Accumulation Surge** | $\Delta \text{Vol} > +10\%$ | Current volume must exceed prior-day volume by >10% OR exceed the 21-day volume average by >10%, confirming active institutional buying interest. |
| **10** | **Short-Term Momentum** | $\text{EMA}_{10} \ge \text{EMA}_{21}$ | Ensures fast momentum is accelerating above intermediate trend ribbon. |
| **11** | **Liquidity Depth** | $\text{AvgVol}_{100\text{D}} > 250,000 \text{ shares}$ | Ensures sufficient institutional liquidity to execute multi-thousand-share swing positions without moving the tape. |
| **12** | **Long-Term Ribbon Alignment** | $\text{SMA}_{150} \ge \text{SMA}_{200}$ | Long-term intermediate moving average confirms the cyclical bull market trend. |
| **13** | **Stage 2 Structural Stacking** | $\text{SMA}_{50} \ge \text{SMA}_{150}$ | Completes perfect Stan Weinstein / Mark Minervini moving average stacking: $\text{SMA}_{50} \ge \text{SMA}_{150} \ge \text{SMA}_{200}$. |

---

### Part B: Senior Strategist Enhancements (The Champion's Edge)

Passing the 13 basic filters provides a list of healthy stocks, but **not all passing stocks are actionable buy setups today**. To transform raw candidates into a high-win-rate swing trading watchlist, the engine applies 5 proprietary algorithmic overlays:

#### 1. Minervini 52-Week High Proximity Rule
$$\text{Distance from 52W High} = \frac{\text{High}_{52\text{W}} - \text{Price}}{\text{High}_{52\text{W}}} \le 25\%$$
- **Rationale**: True market leaders trade within 25% of their 52-week highs. Stocks down 40%–60% from their highs face relentless overhead supply from trapped retail bagholders eager to break even.

#### 2. Moving Average Slope & Curvature Verification
Moving averages must not be pointing downward:
- **21 EMA 5-Day Slope**:
  $$\text{Slope}_{\text{EMA21}} = \frac{\text{EMA21}_{t} - \text{EMA21}_{t-5}}{\text{EMA21}_{t-5}} \times 100$$
  - `Strongly Upward` ($\ge +1.5\%$): Maximum score.
  - `Upward` ($0.0\%$ to $+1.5\%$): Bullish expansion.
  - `Flat / Curving Up` ($-0.2\%$ to $0.0\%$): Valid base hook.
  - `Downward` ($< -0.2\%$): Penalized.
- **50 SMA 10-Day Slope**:
  $$\text{Slope}_{\text{SMA50}} = \frac{\text{SMA50}_{t} - \text{SMA50}_{t-10}}{\text{SMA50}_{t-10}} \times 100$$
  - Must be flat ($\ge -0.2\%$) or upward ($\ge 0.0\%$), never declining.

#### 3. Precision Buy Zone Classification
Identifies where the stock sits relative to key institutional re-test areas:
- **Dual Convergence Sweet Spot**: Price within $\le 2.5\%$ of 21 EMA **and** $\le 3.5\%$ of 50 SMA. (Highest probability setup).
- **21 EMA Prime Zone**: Price within $\le 2.5\%$ of 21 EMA.
- **50 SMA Demand Zone**: Price within $\le 3.5\%$ of 50 SMA.
- **Upper Pullback Zone**: Price within $\le 4.5\%$ of 21 EMA.
- **Extended**: Price $> 4.5\%$ above 21 EMA (Valid company, but wait for pullback).

#### 4. 30-Day Swing Pivot Structure Analysis
Analyzes 3-bar local pivots across the past 30 trading days:
- Identifies at least 2 swing highs ($SH_1, SH_2$) and 2 swing lows ($SL_1, SL_2$).
- **Higher Swing Lows**: $SL_2 \ge SL_1 \times 0.995$ confirms institutions are defending pullbacks at progressively higher price levels.
- **Volatility Contraction Pattern (VCP)**: $(SH_2 - SL_2) \le (SH_1 - SL_1) \times 1.05$ confirms price volatility is coiling tightly before explosive trend resumption.

#### 5. Institutional Quality Score (IQS: 0–100) & Star Rating
All passing candidates are objectively scored and ranked across 5 pillars:
1. **Trend Ribbon & Slopes (30 Pts)**: Perfect EMA10 > EMA21 > SMA50 > SMA150 > SMA200 alignment + positive slopes.
2. **Buy Zone Geometry (25 Pts)**: Dual convergence sweet spot (25 pts) or 21 EMA / 50 SMA prime zone (18–20 pts).
3. **30-Day Swing Structure & Contraction (20 Pts)**: Higher lows (12 pts) + VCP contraction (8 pts).
4. **Volume Profile & Accumulation (15 Pts)**: Relative Volume $\text{RVOL} \ge 1.5$ (10 pts) + Green close today (5 pts).
5. **IBD Relative Strength Composite & High Proximity (10 Pts)**: $\text{RS} \ge 80$ (6 pts) + within 25% of 52w high (4 pts).

**Tiers**:
- ⭐⭐⭐⭐⭐ **Grade A+ Elite (IQS 90–100)**: PRIME BUY SETUP (Immediate execution).
- ⭐⭐⭐⭐ **Grade A High Conviction (IQS 80–89)**: HIGH WATCHLIST PRIORITY.
- ⭐⭐⭐ **Grade B+ Setup Developing (IQS 70–79)**: ACCUMULATION WATCH.
- ⭐⭐ **Grade B Secondary Watch (IQS < 70)**: MONITOR FOR BASING.

---

## 3. How to Run the Screener

### Option A: Google Colab Notebook (1-Click Cloud Execution)
Notebook file: [`Rajat_Alpha_Institutional_Weekly_Screener.ipynb`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/Rajat_Alpha_Institutional_Weekly_Screener.ipynb)

1. Open [Google Colab](https://colab.research.google.com/) and upload `Rajat_Alpha_Institutional_Weekly_Screener.ipynb`.
2. Select your desired universe from the interactive form dropdown:
   - `Combined (S&P 500 + Nasdaq 100 + Dow 30)` (Recommended - scans ~600 liquid leaders)
   - `Nasdaq 100` (Tech & High-Growth leaders)
   - `S&P 500` (Broad market institutional leaders)
   - `Dow 30` (Mega-cap blue chips)
   - `Liquid Leaders (Top 120)` (Fastest scan - ~15 seconds)
3. Click **Runtime -> Run all** (or press `Ctrl + F9`).
4. The notebook automatically:
   - Installs dependencies (`yfinance`, `openpyxl`, `tqdm`).
   - Fetches live market data in parallel multi-threaded chunks.
   - Evaluates all 13 rules + senior strategist filters.
   - Displays a clean visual dashboard of the top 20 ranked candidates.
   - Prompts a 1-click automatic download of your formatted `.xlsx` workbook!

---

### Option B: Command-Line Interface (Local Python Run)
Script file: [`run_institutional_weekly_screener.py`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/scanner/run_institutional_weekly_screener.py)

Open PowerShell or terminal in the repository root:

```bash
# Scan combined universe and export Excel report
python scripts/scanner/run_institutional_weekly_screener.py --universe combined --output reports/weekly_swing_screener_results.xlsx

# Scan Nasdaq 100 and automatically update config/watchlist.txt with top 20 picks
python scripts/scanner/run_institutional_weekly_screener.py --universe nasdaq100 --output reports/nasdaq_watchlist.xlsx --update-watchlist --top 20

# Fast check on Dow 30 blue chips
python scripts/scanner/run_institutional_weekly_screener.py --universe dow30 --output reports/dow30_watchlist.xlsx
```

#### CLI Arguments:
- `--universe`: Choices: `combined` (default), `sp500`, `nasdaq100`, `dow30`, `liquid_leaders`.
- `--output`: Filepath for the generated `.xlsx` workbook (default: `weekly_swing_screener_results.xlsx`).
- `--top`: Number of top-ranked candidates to include in the primary watchlist sheet (default: `25`).
- `--update-watchlist`: If passed, automatically updates `config/watchlist.txt` with the top symbols.

---

## 4. Multi-Sheet Formatted Excel Workbook Output

The exported `.xlsx` file is styled with institutional executive formatting (navy/gold headers, auto-adjusted columns, zebra borders, and conditional color highlights):

```
┌────────────────────────────────────────────────────────────────────────┐
│ weekly_swing_screener_results.xlsx                                     │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ Sheet 1:                 │ Sheet 2:             │ Sheet 3:             │
│ Top_Watchlist_Next_Week  │ All_Screened_Cand... │ Watchlist_TXT_Export │
└──────────────────────────┴──────────────────────┴──────────────────────┘
```

1. **Sheet 1: `Top_Watchlist_Next_Week`**
   - Contains the top 20–25 highest-scoring setups sorted strictly by IQS Score descending.
   - Displays: Rank, Ticker, Last Close, IQS Score (0–100), Star Rating, Action Verdict, Buy Zone, 21 EMA / 50 SMA Proximity, Slopes, 30-Day Higher Lows ($SL_2 \ge SL_1$), VCP Contraction, **Suggested Entry, Initial Stop Loss, Risk %, Profit Targets 1/2/3, and Risk/Reward Ratio**.
2. **Sheet 2: `All_Screened_Candidates`**
   - Comprehensive quantitative dataset containing every single asset that passed the 13 TradingView criteria.
   - Includes full 52w range metrics, 100-day volume, relative volume (RVOL), and IBD RS composite.
3. **Sheet 3: `Watchlist_TXT_Export`**
   - Clean single column containing the top symbol names ready to copy-paste directly into `config/watchlist.txt` for live bot trading or feed into Colab backtesting pipelines.

---

## 5. Integrating with Backtesting & Live Trading

To immediately backtest or trade the newly screened symbols:
1. Open Sheet 3 (`Watchlist_TXT_Export`) of your generated Excel file.
2. Copy the symbols into `config/watchlist.txt` (or run with `--update-watchlist`).
3. Run the Colab backtester: [`Rajat_Alpha_v67_Colab_Backtest.ipynb`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/scripts/colab/Rajat_Alpha_v67_Colab_Backtest.ipynb) to verify historical portfolio performance, win rate, and profit factor on this tailored universe.
4. Launch the live or paper trading bot in `Single_Buy2.0` with confidence knowing every ticker represents an institutional-grade Stage 2 leader in an active demand zone.
