# Pre-Swing Trade Analysis Dashboard

Institutional-grade pre-market swing trade screener built on SOLID principles.
Screens every symbol in your weekly watchlist through the v67 entry algorithm
and presents results in an interactive, filterable dashboard.

---

## Quick Start

```bash
# 1. Install dependencies
cd C:\Alpaca_Algo\Single_Buy\tools\preSwingTradeAnalysis
pip install -r requirements.txt

# 2. Launch
python app.py

# 3. Open browser → http://localhost:8050
```

---

## Features

| Feature | Detail |
|---------|--------|
| **7-State Market Classification** | Strong Uptrend 🚀 / Uptrend 📈 / Pullback Setup 🎯 / Sideways ↔️ / Choppy 🌊 / Downtrend 📉 / Strong Downtrend ⬇️ |
| **v67 Signal Scoring** | Mirrors the production algorithm: RSI, multi-timeframe, volume, demand zone, touch bonuses, pattern bonus |
| **Pattern Detection** | Engulfing, Piercing, Tweezer Bottom, Morning Star |
| **Breakout Alerts** | 52W High, 13W High, BB Breakout, EMA21×SMA50 Crossover, Volume Surge |
| **Earnings Risk Flag** | Auto-flags any stock with earnings within 14 calendar days |
| **News Feed** | Latest headlines per stock with positive/negative/neutral sentiment colouring |
| **Industry Filter** | Filter the table by sector/industry group |
| **Watchlist Auto-Refresh** | File watcher detects changes to `watchlist.txt` and shows a refresh prompt |
| **AG Grid Table** | Sortable, filterable, column tooltips, Buy Setup row highlight |
| **Interactive Chart** | 120-day candlestick + EMA21 + SMA50 + SMA200 + Volume + RSI + trade levels |
| **Score Breakdown Tooltip** | Hover Score column to see individual component contributions |

---

## File Structure

```
preSwingTradeAnalysis/
├── app.py                   ← Entry point. Dash layout + all callbacks.
├── orchestrator.py          ← Wires all services into the analysis pipeline.
├── config.py                ← All constants (mirrors v67 config.json params).
├── models.py                ← Domain objects: StockSignal, MarketState, etc.
├── requirements.txt
├── README.md
│
├── services/
│   ├── watchlist.py         ← Load watchlist.txt + file-change detection.
│   ├── data_fetcher.py      ← yfinance download with 15-min TTL cache.
│   ├── technical_analyzer.py← EMA/SMA/RSI/MACD/BB/ATR, 7-state classifier, patterns.
│   ├── signal_scorer.py     ← v67 entry scoring + action label.
│   └── news_service.py      ← News fetch, sentiment, earnings date.
│
├── components/
│   └── charts.py            ← Plotly candlestick + indicator chart builder.
│
└── assets/
    ├── dashAgGridFunctions.js ← Cell-style JS functions for AG Grid.
    └── custom.css            ← Dark theme overrides.
```

---

## How Scoring Works

Scoring mirrors `rajat_alpha_v67_single.py` exactly:

| Component | Points |
|-----------|--------|
| RSI-14 > 50 | +1.0 |
| Weekly Close > Weekly EMA21 | +1.0 |
| Monthly Close > Monthly EMA10 | +1.0 |
| Volume > 21-day Average | +1.0 |
| Price in Demand Zone (21d low × 1.035) | +1.0 |
| EMA21 1st Touch | +1.0 |
| SMA50 1st Touch | +1.0 |
| EMA21 / SMA50 2nd Touch | +0.5 |
| Bullish Pattern ON a Touch Signal | +1.0 |
| **Minimum for Buy Setup** | **≥ 4** |

---

## Watchlist Management

The watchlist is read from `C:\Alpaca_Algo\Single_Buy\config\watchlist.txt`.  
Update it any time — the dashboard polls the file every **3 seconds** and
shows a blue banner when a change is detected.  Click **🔄 Refresh** to re-scan.

One symbol per line. Lines starting with `#` or `//` are ignored.

---

## Dashboard Tips

- Sort the **Score** column descending for the best setups at the top.
- Combine **Action = Buy Setup** + **State = Pullback Setup** for prime entries.
- Enable **Hide Earnings Risk** before a busy earnings week.
- Click any row to load the 120-day chart with EMA21, SMA50, SMA200, RSI.
- Hover **column headers** for full definitions.
- Hover the **Score cell** to see the individual component breakdown.
- Data refreshes automatically every **15 minutes** or click 🔄 manually.
- Chart shows stop-loss (red), Target 1 (green), Target 2 (dashed green).

---

## Configuration

All tunable parameters live in `config.py`:

```python
MIN_SIGNAL_SCORE    = 4       # Score threshold for "Buy Setup"
STOP_LOSS_PCT       = 0.17    # 17% initial stop-loss
TARGET_1_PCT        = 0.10    # +10% first target
EARNINGS_WARNING_DAYS = 14    # Flag earnings risk window
CACHE_TTL_SECONDS   = 900     # 15-minute data cache
CHART_BARS          = 120     # Bar count shown in chart
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `dash` | Web framework |
| `dash-bootstrap-components` | Bootstrap dark theme (Cyborg) |
| `dash-ag-grid` | Institutional-grade data grid |
| `yfinance` | Free market data (OHLCV + news + earnings) |
| `pandas` + `pandas-ta` | Data frames + technical indicators |
| `plotly` | Interactive charts |

---

*Built for institutional use. All signals are informational only and do not constitute investment advice.*
