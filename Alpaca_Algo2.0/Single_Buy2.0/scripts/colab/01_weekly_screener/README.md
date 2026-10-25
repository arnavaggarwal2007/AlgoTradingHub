# 🔍 Module 1: Institutional Weekly Swing Trading Radar & Screener (`01_weekly_screener/`)

## Overview
This module scans the broader US equity market (~850+ liquid equities across S&P 500, Nasdaq 100, Dow 30, and high-growth mid-caps) applying your **13 TradingView core trend rules** and evaluating setups for **immediate live bot compatibility**.

---

## 🎯 Key Capabilities
1. **Configurable Watchlist Size**: Default is **50 symbols**, configurable via `top_watchlist_count` slider in Step 2.
2. **5-Tier Letter Grade Rating**: Every candidate is scored (0–100 IQS) and rated:
   - **Grade A+ (IQS >= 90)**: Trigger-Ready (0–3d) inside the 21 EMA/50 SMA buy zone (<=2.0%) with daily & weekly demand confirmed.
   - **Grade A (IQS 80–89)**: On-Deck (1–2w) pulling back (2.0%–4.2%) with higher lows ($SL_2 \ge SL_1$).
   - **Grade B+ (IQS 70–79)**: Base Formation (2–3w) extended momentum leader coiling.
   - **Grade B (IQS 60–69)**: Standard Swing Watch.
   - **Grade B- (IQS < 60)**: Secondary Reserve.
3. **Dual Segmented Universes**:
   - `[INDEX]`: Inside major indices (S&P 500, Nasdaq 100, Dow 30).
   - `[BROADER_MARKET]`: High-growth momentum mid-caps ($Market Cap \ge $2B) outside major indices.
4. **Interactive Candlestick Visualizer**:
   - Automatically renders Top 10 charts.
   - Interactive dropdown widget allows selecting and charting any candidate on demand.
5. **Multi-Timeframe Demand Matrix**: Daily, Weekly, and Monthly demand zone classification.
6. **Volume Pocket Pivot Flag**: Detects institutional accumulation on positive close.
7. **Two Swing Highs & Lows with Dates**: Pinpoints $SL_1, SL_2, SH_1, SH_2$ and verifies VCP contraction.

---

## 📥 Generated Artifacts
- `weekly_swing_screener_results.xlsx` (6 formatted sheets)
- `watchlist.txt` (top 50 symbols ready for `Single_Buy2.0`)
