"""
app.py — Pre-Swing Trade Analysis Dashboard
============================================
Institutional-grade swing-trade screener built on SOLID principles.

Run
---
    python app.py

Then open http://localhost:8050 in your browser.

Architecture
------------
  orchestrator.py   → coordinates all services
  services/         → watchlist, data, technical analysis, scoring, news
  components/       → Plotly chart builders
  models.py         → domain objects (StockSignal, MarketState …)
  config.py         → all tunable constants
  assets/           → CSS + AG Grid JS functions
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import dash
import dash_ag_grid as dag
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import pandas as pd
from dash import (Input, Output, State, callback_context, dcc, html,
                  no_update)

from components.charts import build_stock_chart
from config import (
    APP_TITLE, APP_PORT, DEBUG_MODE, APP_VERSION,
    WATCHLIST_PATH, WATCHLIST_CHECK_MS, REFRESH_INTERVAL_MS,
    MARKET_INDICES, INITIAL_CAPITAL,
    TARGET_1_PCT, TARGET_2_PCT, TARGET_3_PCT, STOP_LOSS_PCT,
    CLR_BG_PRIMARY, CLR_BG_CARD, CLR_ACCENT, CLR_BORDER, CLR_TEXT_DIM, CLR_TEXT_MAIN,
)
from models import MarketState, StockSignal
from orchestrator import AnalysisOrchestrator
from services.backtest_service import BacktestEngine
from services.watchlist import WatchlistService

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dashboard")

# ─── Singletons ────────────────────────────────────────────────────────────────
orchestrator    = AnalysisOrchestrator()
watchlist_svc   = WatchlistService(WATCHLIST_PATH)
_backtest_engine = BacktestEngine()

# Shared mutable state (protected by lock)
_lock               = threading.Lock()
_signals:  List[StockSignal] = []
_wl_changed_flag            = False          # set by background watcher


def _on_watchlist_change(new_symbols: List[str]) -> None:
    global _wl_changed_flag
    with _lock:
        _wl_changed_flag = True
    logger.info("Watchlist file changed — %d symbols queued for refresh", len(new_symbols))


# Start the file watcher (daemon thread — dies with main process)
watchlist_svc.load()
watchlist_svc.watch(_on_watchlist_change, interval=WATCHLIST_CHECK_MS / 1000)

# ─── AG Grid Column Definitions ────────────────────────────────────────────────

_TOOLTIP_MAP = {
    "symbol":          "Ticker symbol. Click row to open detail chart.",
    "market_state":    "7-state trend classification: Strong Uptrend / Uptrend / Pullback Setup / Sideways / Choppy / Downtrend / Strong Downtrend",
    "score":           "v67 Entry Score (0–9). Components: RSI>50 +1, Weekly OK +1, Monthly OK +1, Volume +1, Demand Zone +1, EMA21 1st-touch +1, SMA50 1st-touch +1, 2nd-touch +0.5, Pattern-on-touch +1. ⚠ Score ≥ 4 is NECESSARY but NOT SUFFICIENT — Buy Setup also requires an active EMA21/SMA50 touch OR a bullish candlestick pattern.",
    "grade":           "Score grade: A+ (≥5), A (≥4), B (≥3), C (≥2), D (<2). Grade reflects score only; Action also requires a touch/pattern signal.",
    "pattern":         "Candlestick reversal pattern detected on the latest bar (v67 PatternDetector): Engulfing, Piercing, Tweezer Bottom, Morning Star",
    "signal_type":     "Touch signal detected: EMA21_Touch or SMA50_Touch.",
    "rsi":             "RSI-14. >70 = overbought (orange), 50–70 = bullish (green), <30 = oversold.",
    "volume_ratio":    "Today's volume ÷ 21-day average volume. ≥2× = strong volume surge.",
    "pct_from_52w_high": "% distance from the 52-week closing high. Negative = below 52W high.",
    "atr_pct":         "Average True Range as % of price (14-day). Represents typical daily volatility.",
    "macd_hist":       "MACD histogram (fast 12, slow 26, signal 9). Positive = bullish momentum.",
    "earnings_risk":   "⚠ YES = earnings within 14 calendar days. Avoid new entries ahead of earnings.",
    "action":          "Buy Setup = score ≥ 4 AND (EMA21/SMA50 touch OR candlestick pattern). A score of 5/A+ with NO touch and NO pattern correctly shows 'Watch' — this is v67 behaviour. | Watch = score ≥ 3 or stalling. | Wait = score ≥ 2. | Avoid = broken structure / score < 2.",
    "breakout_signal": "Technical breakout context: 52W High, 13W High, BB Breakout, MA Crossover, Volume Surge.",
    "weekly_ok":       "✓ = weekly close > weekly EMA21 (multi-timeframe alignment).",
    "monthly_ok":      "✓ = monthly close > monthly EMA10 (long-term trend confirmation).",
    "entry_zone":      "Suggested entry price range based on nearest MA support.",
    "stop_loss":       "Initial stop loss (17% below entry per v67 risk management).",
    "target1":         "First profit target (+10%).",
    "risk_reward":     "Risk/reward ratio: (Target1 - Entry) / (Entry - Stop).",
    "atr21":           "21-Day ATR ($): avg daily True Range (max of H−L, |H−PrevClose|, |L−PrevClose|) over 21 sessions. Dollar amount a stock typically moves per day — useful for position sizing and stop placement.",
    "weekly_range_pct": "5-bar price range %: (5-day High − 5-day Low) / 5-day Low × 100. Wide W-Range on a bounce = strong momentum. Narrow = consolidation.",
}

COLUMN_DEFS = [
    # ── Pinned Left ────────────────────────────────────────────────────────────
    {
        "field": "symbol", "headerName": "Symbol", "width": 85, "pinned": "left",
        "cellStyle": {"function": "dagfuncs.symbolStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["symbol"],
        "tooltipField": "name",
    },
    {
        "field": "name", "headerName": "Company", "width": 180,
        "tooltipField": "industry",
    },
    {
        "field": "sector", "headerName": "Sector", "width": 120,
        "filter": True, "hide": True,
    },
    {
        "field": "industry", "headerName": "Industry", "width": 150, "filter": True,
        "tooltipField": "sector",
    },

    # ── Market State ──────────────────────────────────────────────────────────
    {
        "field": "market_state", "headerName": "State", "width": 155,
        "cellStyle": {"function": "dagfuncs.stateStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["market_state"],
        "filter": True,
    },

    # ── Price (pinned left, next to Symbol) ─────────────────────────────────────
    {
        "field": "price", "headerName": "Price", "width": 82, "pinned": "left",
        "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
        "type": "numericColumn",
    },
    # ── Scrollable Middle ────────────────────────────────────────────────────────
    {
        "field": "change_pct", "headerName": "Chg%", "width": 76,
        "cellStyle": {"function": "dagfuncs.changeStyle(params)"},
        "valueFormatter": {"function": "(params.value >= 0 ? '+' : '') + d3.format('.2f')(params.value) + '%'"},
        "type": "numericColumn",
    },

    # ── Grade (scrollable) ──────────────────────────────────────────────────────
    {
        "field": "grade", "headerName": "Grade", "width": 68,
        "cellStyle": {"function": "dagfuncs.gradeStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["grade"],
    },

    # ── Indicators ────────────────────────────────────────────────────────────
    {
        "field": "rsi", "headerName": "RSI", "width": 70,
        "cellStyle": {"function": "dagfuncs.rsiStyle(params)"},
        "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
        "headerTooltip": _TOOLTIP_MAP["rsi"],
        "type": "numericColumn",
    },
    {
        "field": "ema21", "headerName": "EMA 21", "width": 88,
        "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
        "cellStyle": {"color": "#00d4ff"},
        "type": "numericColumn",
    },
    {
        "field": "sma50", "headerName": "SMA 50", "width": 88,
        "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
        "cellStyle": {"color": "#ffa500"},
        "type": "numericColumn",
    },
    {
        "field": "volume_ratio", "headerName": "Vol/Avg", "width": 82,
        "cellStyle": {"function": "dagfuncs.volStyle(params)"},
        "valueFormatter": {"function": "d3.format('.2f')(params.value) + 'x'"},
        "headerTooltip": _TOOLTIP_MAP["volume_ratio"],
        "type": "numericColumn",
    },
    {
        "field": "pct_from_52w_high", "headerName": "52W %", "width": 80,
        "cellStyle": {"function": "dagfuncs.pos52wStyle(params)"},
        "valueFormatter": {"function": "d3.format('+.1f')(params.value) + '%'"},
        "headerTooltip": _TOOLTIP_MAP["pct_from_52w_high"],
        "type": "numericColumn",
    },
    {
        "field": "atr_pct", "headerName": "ATR%", "width": 72,
        "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
        "headerTooltip": _TOOLTIP_MAP["atr_pct"],
        "cellStyle": {"color": "#8896ac"},
        "type": "numericColumn",
    },
    {
        "field": "atr21", "headerName": "ATR 21$", "width": 82,
        "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
        "headerTooltip": _TOOLTIP_MAP["atr21"],
        "cellStyle": {"color": "#8896ac"},
        "type": "numericColumn",
    },

    # ── Multi-Timeframe ───────────────────────────────────────────────────────
    {
        "field": "weekly_ok", "headerName": "W-TF", "width": 62,
        "cellStyle": {"function": "dagfuncs.mtfStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["weekly_ok"],
    },
    {
        "field": "monthly_ok", "headerName": "M-TF", "width": 62,
        "cellStyle": {"function": "dagfuncs.mtfStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["monthly_ok"],
    },

    # ── Breakout ──────────────────────────────────────────────────────────────
    {
        "field": "breakout_signal", "headerName": "Breakout", "width": 160,
        "cellStyle": {"function": "dagfuncs.breakoutStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["breakout_signal"],
    },

    # ── Range ─────────────────────────────────────────────────────────────────
    {
        "field": "weekly_range_pct", "headerName": "W-Range%", "width": 88,
        "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
        "cellStyle": {"color": "#8896ac"},
        "type": "numericColumn",
    },

    # ── Earnings ──────────────────────────────────────────────────────────────
    {
        "field": "earnings_date", "headerName": "Earnings", "width": 90,
        "cellStyle": {"color": "#8896ac"},
        "headerTooltip": _TOOLTIP_MAP["earnings_risk"],
    },
    {
        "field": "earnings_risk", "headerName": "⚠ Risk", "width": 76,
        "cellStyle": {"function": "dagfuncs.earningsStyle(params)"},
    },

    # ── Trade Setup ───────────────────────────────────────────────────────────
    {
        "field": "entry_zone", "headerName": "Entry Zone", "width": 120,
        "cellStyle": {"color": "#64b5f6"},
        "headerTooltip": _TOOLTIP_MAP["entry_zone"],
    },
    {
        "field": "stop_loss", "headerName": "Stop", "width": 80,
        "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
        "cellStyle": {"color": "#ef5350"},
        "headerTooltip": _TOOLTIP_MAP["stop_loss"],
        "type": "numericColumn",
    },
    {
        "field": "target1", "headerName": "T1", "width": 80,
        "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
        "cellStyle": {"color": "#00e676"},
        "headerTooltip": _TOOLTIP_MAP["target1"],
        "type": "numericColumn",
    },
    {
        "field": "risk_reward", "headerName": "R:R", "width": 64,
        "valueFormatter": {"function": "d3.format('.2f')(params.value)"},
        "cellStyle": {"color": "#ffd54f"},
        "headerTooltip": _TOOLTIP_MAP["risk_reward"],
        "type": "numericColumn",
    },

    # ── Pinned Right: Score · Pattern · Signal · Action ─────────────────────────
    {
        "field": "score", "headerName": "Score", "width": 74, "pinned": "right",
        "cellStyle": {"function": "dagfuncs.scoreStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["score"],
        "tooltipField": "score_tooltip",
        "type": "numericColumn",
        "sort": "desc",
    },
    {
        "field": "pattern", "headerName": "Pattern", "width": 120, "pinned": "right",
        "headerTooltip": _TOOLTIP_MAP["pattern"],
        "cellStyle": {"color": "#ffd54f"},
        "filter": True,
    },
    {
        "field": "signal_type", "headerName": "Signal", "width": 105, "pinned": "right",
        "headerTooltip": _TOOLTIP_MAP["signal_type"],
        "cellStyle": {"color": "#64b5f6"},
        "filter": True,
    },
    {
        "field": "action", "headerName": "Action", "width": 105, "pinned": "right",
        "cellStyle": {"function": "dagfuncs.actionStyle(params)"},
        "headerTooltip": _TOOLTIP_MAP["action"],
        "filter": True,
    },
]

# ─── Dash App ──────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        dbc.icons.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    title=APP_TITLE,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True,
)
server = app.server   # For gunicorn / production deployment


# ─── Layout Helpers ────────────────────────────────────────────────────────────

def _overview_card(card_id: str, label: str, value: str, subtext: str = "",
                   value_color: str = "#e8ecf4") -> dbc.Col:
    return dbc.Col(
        html.Div([
            html.Div(label, className="card-label"),
            html.Div(value, id=card_id, className="card-value", style={"color": value_color}),
            html.Div(subtext, className="card-subtext"),
        ], className="overview-card"),
        xs=6, sm=4, md=2,
    )


def _filter_dropdown(filter_id: str, placeholder: str, options: list,
                     multi: bool = True, width: int = 2) -> dbc.Col:
    return dbc.Col(
        dcc.Dropdown(
            id=filter_id,
            options=options,
            placeholder=placeholder,
            multi=multi,
            clearable=True,
            style={
                "backgroundColor": CLR_BG_CARD,
                "borderColor": CLR_BORDER,
                "color": "#e8ecf4",
                "fontSize": "12px",
            },
        ),
        md=width,
    )


def _help_modal() -> dbc.Modal:
    return dbc.Modal([
        dbc.ModalHeader(
            dbc.ModalTitle(f"📖 Dashboard Documentation — {APP_TITLE} v{APP_VERSION}"),
            close_button=True,
        ),
        dbc.ModalBody([
            # Overview
            html.H6("OVERVIEW"),
            html.P(
                "This dashboard screens the weekly watchlist through the v67 swing-trade algorithm. "
                "Stocks are ranked by entry signal score, filtered by market state, industry, and "
                "earnings risk, and displayed in a sortable AG Grid table with an integrated "
                "candlestick chart and live news feed.",
                style={"fontSize": "12px", "color": "#8896ac"}
            ),

            # Market States
            html.H6("7-STATE MARKET CLASSIFICATION"),
            html.Table([
                html.Thead(html.Tr([html.Th("State"), html.Th("Criteria"), html.Th("Typical Action")])),
                html.Tbody([
                    html.Tr([html.Td("🚀 Strong Uptrend"),   html.Td("SMA50>200, EMA21>50, Price>EMA21, RSI>55, positive momentum"), html.Td("Ride trend, add on dips")]),
                    html.Tr([html.Td("📈 Uptrend"),           html.Td("SMA50>200, EMA21>50, Price>EMA21"),                           html.Td("Swing-buy pullbacks")]),
                    html.Tr([html.Td("🎯 Pullback Setup"),    html.Td("Uptrend structure intact, price near EMA21 or SMA50"),        html.Td("PRIME entry zone — watch for pattern")]),
                    html.Tr([html.Td("↔️ Sideways"),           html.Td("No directional bias, price oscillating around MAs"),          html.Td("Wait for direction")]),
                    html.Tr([html.Td("🌊 Choppy"),             html.Td("High volatility (>1.8% daily std), no clear structure"),      html.Td("Avoid new entries")]),
                    html.Tr([html.Td("📉 Downtrend"),          html.Td("SMA50<200 or Price<SMA50"),                                   html.Td("Do not buy")]),
                    html.Tr([html.Td("⬇️ Strong Downtrend"),   html.Td("All MAs bearish, accelerating downside, RSI<40"),             html.Td("Avoid")]),
                ]),
            ], className="table table-sm table-dark", style={"fontSize": "11px"}),

            # Scoring
            html.H6("SCORING SYSTEM (mirrors v67)"),
            html.Table([
                html.Thead(html.Tr([html.Th("Component"), html.Th("Points")])),
                html.Tbody([
                    html.Tr([html.Td("RSI-14 > 50"),                      html.Td("+1.0")]),
                    html.Tr([html.Td("Weekly Close > Weekly EMA21"),      html.Td("+1.0")]),
                    html.Tr([html.Td("Monthly Close > Monthly EMA10"),    html.Td("+1.0")]),
                    html.Tr([html.Td("Volume > 21-day Average"),          html.Td("+1.0")]),
                    html.Tr([html.Td("Price in Demand Zone (21d low × 1.035)"), html.Td("+1.0")]),
                    html.Tr([html.Td("EMA21 1st Touch"),                  html.Td("+1.0")]),
                    html.Tr([html.Td("SMA50 1st Touch"),                  html.Td("+1.0")]),
                    html.Tr([html.Td("EMA21 / SMA50 2nd Touch"),          html.Td("+0.5")]),
                    html.Tr([html.Td("Bullish Pattern ON Touch"),         html.Td("+1.0")]),
                    html.Tr([html.Td("Min score for Buy Setup"),          html.Td("≥ 4")]),
                ]),
            ], className="table table-sm table-dark", style={"fontSize": "11px"}),

            # Actions
            html.H6("ACTION LABELS"),
            html.Ul([
                html.Li([html.Span("Buy Setup", style={"color": "#00e676", "fontWeight": "700"}), " — Score ≥ 4 + touch/pattern signal + market structure OK"]),
                html.Li([html.Span("Watch",     style={"color": "#00d4ff"}), " — Score ≥ 3 or stalling. Setup developing."]),
                html.Li([html.Span("Wait",      style={"color": "#ff9800"}), " — Score ≥ 2. Not ready yet."]),
                html.Li([html.Span("Avoid",     style={"color": "#ef5350"}), " — Market structure broken or score < 2."]),
            ], style={"fontSize": "12px"}),

            # Watchlist
            html.H6("WATCHLIST AUTO-REFRESH"),
            html.P(
                f"The dashboard watches {WATCHLIST_PATH} every 3 seconds. "
                "When you save a new watchlist, the page detects the change and prompts a re-scan automatically. "
                "You can also click 🔄 Refresh manually at any time.",
                style={"fontSize": "12px", "color": "#8896ac"}
            ),

            # Tips
            html.H6("TIPS"),
            html.Ul([
                html.Li("Sort the Score column descending to see the best setups first."),
                html.Li("Filter Action = 'Buy Setup' and State = 'Pullback Setup' for prime entries."),
                html.Li("Turn on Earnings Filter to hide stocks with imminent earnings risk."),
                html.Li("Click any row to load the 120-day chart with MAs and RSI."),
                html.Li("Hover over column headers for definitions."),
            ], style={"fontSize": "12px"}),
        ]),
        dbc.ModalFooter(
            dbc.Button("Close", id="help-modal-close", className="btn-sm btn-secondary")
        ),
    ], id="help-modal", size="xl", scrollable=True, is_open=False)


# ─── Main Layout ───────────────────────────────────────────────────────────────

app.layout = dbc.Container([

    # ── Hidden stores & intervals ────────────────────────────────────────────
    dcc.Store(id="signals-store",          storage_type="memory"),
    dcc.Store(id="wl-changed-store",       storage_type="memory", data=False),
    dcc.Store(id="index-store",            storage_type="memory"),
    dcc.Store(id="earnings-only-store",    storage_type="memory", data=False),
    dcc.Store(id="bt-symbol-store",        storage_type="memory", data=[]),   # symbol(s) sent from Screener
    dcc.Store(id="bt-result-store",        storage_type="memory"),             # serialisable backtest result
    dcc.Store(id="theme-store",            storage_type="local",  data="dark"), # persisted theme preference
    dcc.Interval(id="auto-refresh",        interval=REFRESH_INTERVAL_MS, n_intervals=0),
    dcc.Interval(id="watchlist-check",     interval=WATCHLIST_CHECK_MS,  n_intervals=0),

    # ── Navbar ────────────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Span("📊 ", style={"fontSize": "18px"}),
                html.Span(APP_TITLE, style={
                    "fontSize": "15px", "fontWeight": "700",
                    "color": CLR_ACCENT, "letterSpacing": "0.3px",
                }),
                html.Span(f" v{APP_VERSION}", style={"fontSize": "10px", "color": CLR_TEXT_DIM, "marginLeft": "6px"}),
            ]),
        ], md=5, className="d-flex align-items-center"),

        dbc.Col([
            html.Div([
                html.Span(id="watchlist-indicator", style={"fontSize": "11px", "marginRight": "12px"}),
                html.Span(id="last-refresh-text", className="last-refresh me-3"),
                html.Span(id="loading-indicator", style={"marginRight": "8px"}),
                dbc.Button("🔄 Refresh",  id="refresh-btn",      className="btn-refresh me-2", n_clicks=0),
                dbc.Button("🌙 Dark",     id="theme-toggle-btn",  className="btn-help me-2",    n_clicks=0),
                dbc.Button("❓ Help",     id="help-btn",          className="btn-help",          n_clicks=0),
            ], className="d-flex align-items-center justify-content-end"),
        ], md=7),
    ], className="mb-2 mt-2 g-0",
       style={"background": "#06090f", "padding": "10px 20px",
              "borderBottom": f"1px solid {CLR_BORDER}", "borderRadius": "0"}),

    # ── Watchlist-changed alert ───────────────────────────────────────────────
    dbc.Alert(
        "📋 Watchlist file updated — click 🔄 Refresh to re-scan.",
        id="wl-changed-alert",
        color="info",
        dismissable=True,
        is_open=False,
        style={"fontSize": "12px", "marginBottom": "6px", "marginTop": "4px"},
    ),

    # ── Auto-refresh next-tick countdown label ──────────────────────────────
    html.Div(id="next-refresh-hint", style={
        "fontSize": "10px", "color": CLR_TEXT_DIM, "textAlign": "right",
        "paddingRight": "20px", "marginBottom": "4px",
    }),

    # ── Buy Setup Signal Alert ────────────────────────────────────────────────
    dbc.Alert(
        id="signal-alert",
        is_open=False,
        dismissable=True,
        color="success",
        style={"fontSize": "12px", "marginBottom": "6px"},
    ),

    # ── Tabs ──────────────────────────────────────────────────────────────────
    dbc.Tabs([

        # ─────────────────────────────────────────────────────────────────────
        # TAB 1 · Screener
        # ─────────────────────────────────────────────────────────────────────
        dbc.Tab(label="📊 Screener", tab_id="tab-screener", children=[

    # ── Overview Cards ────────────────────────────────────────────────────────
    dbc.Row([
        _overview_card("spy-state",       "S&P 500 (SPY)",   "—",  "Loading…"),
        _overview_card("qqq-state",       "Nasdaq (QQQ)",    "—",  "Loading…"),
        _overview_card("iwm-state",       "Russell (IWM)",   "—",  "Loading…"),
        dbc.Col(
            html.Div([
                html.Div("VIX", className="card-label"),
                html.Div("—", id="vix-card", className="card-value", style={"color": "#ff9800"}),
                html.Div(id="vix-subtext", className="card-subtext",
                         style={"color": CLR_TEXT_DIM, "fontSize": "10px"}),
                dbc.Tooltip(
                    [
                        html.Div("📊 CBOE Volatility Index (VIX)", style={"fontWeight": "700", "marginBottom": "6px"}),
                        html.Table([
                            html.Thead(html.Tr([html.Th("VIX Level"), html.Th("Regime"), html.Th("Swing Implication")])),
                            html.Tbody([
                                html.Tr([html.Td("< 15"),    html.Td("😴 Complacency"), html.Td("Low volatility — decent for entries")]),
                                html.Tr([html.Td("15 – 20"), html.Td("✅ Normal"),        html.Td("Best conditions for swing trades")]),
                                html.Tr([html.Td("20 – 30"), html.Td("⚠️ Elevated"),      html.Td("Widen stops; be selective")]),
                                html.Tr([html.Td("30 – 40"), html.Td("🚨 High Fear"),     html.Td("Wait for flush + reversal signal")]),
                                html.Tr([html.Td("> 40"),    html.Td("💥 Extreme Fear"), html.Td("Potential contrarian BUY — high risk")]),
                            ]),
                        ], className="table table-sm", style={"fontSize": "11px", "color": "#e8ecf4"}),
                    ],
                    target="vix-card-wrapper",
                    placement="bottom",
                    style={"maxWidth": "420px"},
                ),
            ], id="vix-card-wrapper", className="overview-card",
               style={"cursor": "help"}),
            xs=6, sm=4, md=2,
        ),
        dbc.Col(
            html.Div([
                html.Div("Buy Setups", className="card-label"),
                html.Div("—", id="setup-count", className="card-value", style={"color": "#00e676"}),
                html.Div("Score ≥ 4 · click to filter", className="card-subtext"),
            ], id="setup-count-btn", className="overview-card",
               n_clicks=0, style={"cursor": "pointer", "userSelect": "none"}),
            xs=6, sm=4, md=2,
        ),
        dbc.Col(
            html.Div([
                html.Div("Earn Risk", className="card-label"),
                html.Div("—", id="earnings-count", className="card-value", style={"color": "#ff9800"}),
                html.Div("Within 14d · click to filter", className="card-subtext"),
            ], id="earnings-count-btn", className="overview-card",
               n_clicks=0, style={"cursor": "pointer", "userSelect": "none"}),
            xs=6, sm=4, md=2,
        ),
    ], className="mb-2 g-2"),

    # ── Filter Bar ────────────────────────────────────────────────────────────
    dbc.Row([
        _filter_dropdown(
            "industry-filter", "Filter Industry…",
            options=[],   # populated by callback
            width=3,
        ),
        _filter_dropdown(
            "state-filter", "Filter Market State…",
            options=[{"label": ms.display, "value": ms.label} for ms in MarketState],
            width=3,
        ),
        _filter_dropdown(
            "action-filter", "Filter Action…",
            options=[
                {"label": "🟢 Buy Setup", "value": "Buy Setup"},
                {"label": "🔵 Watch",     "value": "Watch"},
                {"label": "🟡 Wait",      "value": "Wait"},
                {"label": "🔴 Avoid",     "value": "Avoid"},
            ],
            width=2,
        ),
        dbc.Col([
            html.Div([
                html.Label("Min Score", style={"fontSize": "11px", "color": CLR_TEXT_DIM, "marginBottom": "2px"}),
                dcc.Slider(
                    id="score-filter",
                    min=0, max=7, step=0.5, value=0,
                    marks={i: {"label": str(i), "style": {"color": CLR_TEXT_DIM, "fontSize": "10px"}} for i in range(8)},
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
            ]),
        ], md=2),
        dbc.Col([
            dbc.Checklist(
                id="earnings-filter",
                options=[{"label": "Hide Earnings Risk", "value": "hide"}],
                value=[],
                switch=True,
                style={"fontSize": "12px", "paddingTop": "18px"},
            ),
        ], md=1),
        dbc.Col([
            dbc.Input(
                id="search-filter",
                placeholder="🔍 Symbol / Company…",
                type="text",
                debounce=True,
                style={
                    "backgroundColor": CLR_BG_CARD, "borderColor": CLR_BORDER,
                    "color": "#e8ecf4", "fontSize": "12px",
                },
            ),
        ], md=1),
    ], className="filter-bar mb-2 g-2"),

    # ── Main Content ──────────────────────────────────────────────────────────
    dbc.Row([

        # ── Summary Table (AG Grid) ────────────────────────────────────────
        dbc.Col([
            dcc.Loading(
                dag.AgGrid(
                    id="main-grid",
                    rowData=[],
                    columnDefs=COLUMN_DEFS,
                    defaultColDef={
                        "resizable":    True,
                        "sortable":     True,
                        "filter":       False,
                        "minWidth":     60,
                        "tooltipComponent": "agTooltipComponent",
                    },
                    dashGridOptions={
                        "pagination":              True,
                        "paginationPageSize":      30,
                        "rowSelection":            "single",
                        "animateRows":             True,
                        "enableCellTextSelection": True,
                        "suppressRowClickSelection": False,
                        "suppressCellFocus":       False,
                        "getRowStyle":             {"function": "dagfuncs.rowStyle(params)"},
                        "tooltipShowDelay":        300,
                        "tooltipHideDelay":        4000,
                    },
                    className="ag-theme-alpine-dark",
                    style={"height": "540px"},
                    columnSizeOptions={"skipHeader": False},
                ),
                type="circle",
                color=CLR_ACCENT,
            ),
        ], md=8),

        # ── Stock Detail Panel ─────────────────────────────────────────────
        dbc.Col([
            html.Div([
                html.Div([
                    html.Div(id="detail-header", className="detail-header",
                             style={"display": "inline-block", "verticalAlign": "middle"}),
                    dbc.Button(
                        "🔬 Backtest ↗",
                        id="send-to-backtest-btn",
                        size="sm",
                        color="info",
                        outline=True,
                        n_clicks=0,
                        style={"fontSize": "10px", "padding": "2px 8px",
                               "marginLeft": "10px", "verticalAlign": "middle",
                               "display": "none"},
                        className="ms-2",
                    ),
                ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"}),
                dcc.Graph(
                    id="detail-chart",
                    config={"displayModeBar": False},
                    style={"height": f"{460}px"},
                ),
                html.Div(id="detail-stats", style={"marginTop": "8px"}),
            ], className="detail-panel"),
        ], md=4),

    ], className="g-2 mb-2"),

    # ── News Feed ─────────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div([
                    html.Span("📰 NEWS FEED", style={
                        "fontSize": "11px", "fontWeight": "700", "color": CLR_ACCENT,
                        "letterSpacing": "0.8px", "textTransform": "uppercase",
                    }),
                    html.Span(" — latest headlines across all watched stocks",
                              style={"fontSize": "10px", "color": CLR_TEXT_DIM}),
                ], style={"marginBottom": "8px"}),
                html.Div(id="news-feed-content"),
            ], className="news-feed"),
        ]),
    ], className="mb-4"),

        ]),  # end Tab 1 children / dbc.Tab "📊 Screener"

        # ─────────────────────────────────────────────────────────────────────
        # TAB 2 · Backtest
        # ─────────────────────────────────────────────────────────────────────
        dbc.Tab(label="🔬 Backtest (1Y)", tab_id="tab-backtest", children=[

            # ── Header bar ───────────────────────────────────────────────────
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("📅 1-YEAR WALK-FORWARD BACKTEST", style={
                            "fontSize": "12px", "fontWeight": "700", "color": CLR_ACCENT,
                            "letterSpacing": "0.8px",
                        }),
                        html.Span(
                            " — v67 replayed on daily closes (no look-ahead bias)"
                            "  ·  Exits: 1/3 @ T1 +10%  ·  1/3 @ T2 +15%  ·  1/3 @ T3 +20%  ·  SL −17%  ·  TES 21d",
                            style={"fontSize": "10px", "color": CLR_TEXT_DIM},
                        ),
                    ], style={"padding": "8px 0 4px 0"}),
                ]),
            ]),

            # ── Controls row ─────────────────────────────────────────────────
            dbc.Row([
                # Symbol multi-select (pre-filled from Screener or watchlist)
                dbc.Col([
                    html.Div("Symbols", style={"fontSize": "10px", "color": CLR_TEXT_DIM, "marginBottom": "3px"}),
                    dcc.Dropdown(
                        id="bt-symbol-dropdown",
                        options=[],          # populated by callback from watchlist
                        multi=True,
                        placeholder="All watchlist symbols  (or pick specific ones)…",
                        style={
                            "backgroundColor": CLR_BG_CARD,
                            "borderColor": CLR_BORDER,
                            "fontSize": "12px",
                        },
                    ),
                ], md=5),

                # Strategy selector
                dbc.Col([
                    html.Div("Strategy", style={"fontSize": "10px", "color": CLR_TEXT_DIM, "marginBottom": "3px"}),
                    dcc.Dropdown(
                        id="bt-strategy-dropdown",
                        options=[
                            {"label": "📊 All Signals  (EMA21 + SMA50 + Pattern)", "value": "all"},
                            {"label": "📈 EMA21 Touch Only",                        "value": "ema21"},
                            {"label": "📉 SMA50 Touch Only",                        "value": "sma50"},
                            {"label": "🕯️ Pattern Only  (Engulfing / Piercing / Tweezer)", "value": "pattern"},
                        ],
                        value="all",
                        clearable=False,
                        style={
                            "backgroundColor": CLR_BG_CARD,
                            "borderColor": CLR_BORDER,
                            "fontSize": "12px",
                        },
                    ),
                ], md=3),

                # Capital input
                dbc.Col([
                    html.Div("Capital ($)", style={"fontSize": "10px", "color": CLR_TEXT_DIM, "marginBottom": "3px"}),
                    dbc.Input(
                        id="bt-capital-input",
                        type="number",
                        value=INITIAL_CAPITAL,
                        min=1_000,
                        step=1_000,
                        debounce=True,
                        style={
                            "backgroundColor": CLR_BG_CARD,
                            "borderColor": CLR_BORDER,
                            "color": CLR_TEXT_MAIN,
                            "fontSize": "12px",
                            "height": "36px",
                        },
                    ),
                ], md=2),

                # Run button
                dbc.Col([
                    html.Div("\u00a0", style={"fontSize": "10px", "marginBottom": "3px"}),
                    dbc.Button(
                        "▶ Run Backtest",
                        id="run-backtest-btn",
                        className="btn-refresh",
                        n_clicks=0,
                    ),
                ], md=2),

                # Status
                dbc.Col([
                    html.Div(id="backtest-status",
                             style={"fontSize": "11px", "color": CLR_TEXT_DIM, "paddingTop": "24px"}),
                ], md=1),
            ], className="mb-3 g-2"),

            dcc.Loading(id="bt-loading", children=[

                # ── KPI cards ─────────────────────────────────────────────────
                dbc.Row(id="backtest-kpis", className="mb-2 g-2"),

                # ── Benchmark comparison row ───────────────────────────────────
                dbc.Row([
                    dbc.Col([
                        html.Div("📊 Strategy vs Benchmarks (1-Year % Return)",
                                 style={"fontSize": "11px", "fontWeight": "700",
                                        "color": CLR_ACCENT, "marginBottom": "6px"}),
                        dcc.Graph(
                            id="benchmark-bar-chart",
                            config={"displayModeBar": False},
                            style={"height": "120px"},
                            figure=go.Figure(layout=go.Layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                margin=dict(l=10, r=10, t=4, b=10),
                            )),
                        ),
                    ]),
                ], className="mb-2"),

                # ── Equity curve + exit donut ──────────────────────────────────
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(
                            id="equity-curve-chart",
                            config={"displayModeBar": False},
                            style={"height": "240px"},
                            figure=go.Figure(layout=go.Layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                            )),
                        ),
                    ], md=8),
                    dbc.Col([
                        dcc.Graph(
                            id="exit-reason-chart",
                            config={"displayModeBar": False},
                            style={"height": "240px"},
                            figure=go.Figure(layout=go.Layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                            )),
                        ),
                    ], md=4),
                ], className="mb-2 g-2"),

                # ── Per-symbol candle chart ────────────────────────────────────
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span("🕯️ Symbol Chart — click a trade row below to view",
                                      style={"fontSize": "11px", "fontWeight": "700",
                                             "color": CLR_ACCENT}),
                            html.Span(id="bt-chart-symbol-label",
                                      style={"fontSize": "11px", "color": CLR_TEXT_DIM,
                                             "marginLeft": "8px"}),
                        ], style={"marginBottom": "4px"}),
                        dcc.Graph(
                            id="bt-symbol-chart",
                            config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d","select2d"]},
                            style={"height": "380px"},
                            figure=go.Figure(layout=go.Layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                annotations=[dict(
                                    text="Run backtest then click a trade row to view its chart",
                                    x=0.5, y=0.5, xref="paper", yref="paper",
                                    showarrow=False,
                                    font=dict(color=CLR_TEXT_DIM, size=12),
                                )],
                            )),
                        ),
                    ]),
                ], className="mb-2"),

                # ── Trade history grid ─────────────────────────────────────────
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span("📋 Trade History", style={"fontSize": "11px", "fontWeight": "700", "color": CLR_ACCENT}),
                            html.Span("  — click any row to view its chart & exit breakdown",
                                      style={"fontSize": "10px", "color": CLR_TEXT_DIM}),
                        ], style={"marginBottom": "4px"}),
                        # ── Exit breakdown detail bar (shown on row select) ─────
                        html.Div(id="bt-exit-detail", style={"marginBottom": "6px"}),
                        dag.AgGrid(
                            id="backtest-grid",
                            rowData=[],
                            columnDefs=[
                                {"field": "symbol",       "headerName": "Symbol",    "width": 88,
                                 "pinned": "left",
                                 "cellStyle": {"color": "#00d4ff", "fontWeight": "700"}},
                                {"field": "entry_date",   "headerName": "Entry",     "width": 98},
                                {"field": "exit_date",    "headerName": "Exit",      "width": 98},
                                {"field": "hold_days",    "headerName": "Days",      "width": 58,
                                 "type": "numericColumn"},
                                {"field": "entry_price",  "headerName": "Entry $",   "width": 82,
                                 "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
                                 "type": "numericColumn"},
                                {"field": "exit_price",   "headerName": "Exit $",    "width": 82,
                                 "valueFormatter": {"function": "'$' + d3.format(',.2f')(params.value)"},
                                 "type": "numericColumn"},
                                {"field": "pnl_pct",      "headerName": "P&L %",     "width": 78,
                                 "cellStyle": {"function": "params.value > 0 ? {color:'#00e676',fontWeight:'700'} : {color:'#ef5350',fontWeight:'700'}"},
                                 "valueFormatter": {"function": "(params.value >= 0 ? '+' : '') + d3.format('.2f')(params.value) + '%'"},
                                 "sort": "desc", "type": "numericColumn"},
                                {"field": "exit_reason",  "headerName": "Exit",      "width": 58,
                                 "cellStyle": {"function": "({'T3':'#b9f6ca','SL':'#ef5350','TES':'#ff9800'}[params.value]) ? {color:({'T3':'#b9f6ca','SL':'#ef5350','TES':'#ff9800'}[params.value]),fontWeight:'700'} : {color:'#69f0ae',fontWeight:'700'}"}},
                                {"field": "t1_hit",       "headerName": "T1",        "width": 46,
                                 "cellStyle": {"function": "params.value === '\u2713' ? {color:'#69f0ae',fontWeight:'700'} : {color:'#8896ac'}"}},
                                {"field": "t2_hit",       "headerName": "T2",        "width": 46,
                                 "cellStyle": {"function": "params.value === '\u2713' ? {color:'#00e676',fontWeight:'700'} : {color:'#8896ac'}"}},
                                {"field": "t3_hit",       "headerName": "T3",        "width": 46,
                                 "cellStyle": {"function": "params.value === '\u2713' ? {color:'#b9f6ca',fontWeight:'700'} : {color:'#8896ac'}"}},
                                {"field": "capital_before","headerName": "Cap Bef $", "width": 96,
                                 "valueFormatter": {"function": "'$' + d3.format(',.0f')(params.value)"},
                                 "cellStyle": {"color": "#8896ac"}, "type": "numericColumn"},
                                {"field": "capital_after", "headerName": "Cap Aft $", "width": 96,
                                 "valueFormatter": {"function": "'$' + d3.format(',.0f')(params.value)"},
                                 "cellStyle": {"function": "params.value >= params.data.capital_before ? {color:'#00e676',fontWeight:'700'} : {color:'#ef5350',fontWeight:'700'}"},
                                 "type": "numericColumn"},
                                {"field": "capital_pnl",  "headerName": "Cap P&L $", "width": 92,
                                 "valueFormatter": {"function": "(params.value >= 0 ? '+$' : '-$') + d3.format(',.0f')(Math.abs(params.value))"},
                                 "cellStyle": {"function": "params.value >= 0 ? {color:'#00e676'} : {color:'#ef5350'}"},
                                 "type": "numericColumn"},
                                {"field": "score",        "headerName": "Score",     "width": 62,
                                 "type": "numericColumn"},
                                {"field": "pattern",      "headerName": "Pattern",   "width": 108,
                                 "cellStyle": {"color": "#ffd54f"}},
                                {"field": "signal_type",  "headerName": "Signal",    "width": 105,
                                 "cellStyle": {"color": "#64b5f6"}},
                                {"field": "max_drawdown_pct", "headerName": "MaxDD%","width": 74,
                                 "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
                                 "cellStyle": {"color": "#ef5350"}, "type": "numericColumn"},
                            ],
                            defaultColDef={"resizable": True, "sortable": True},
                            dashGridOptions={
                                "pagination": True,
                                "paginationPageSize": 20,
                                "rowSelection": "single",
                                "animateRows": True,
                                "rowStyle": {"cursor": "pointer"},
                            },
                            className="ag-theme-alpine-dark",
                            style={"height": "360px"},
                        ),
                    ]),
                ], className="mb-2"),

                # ── Per-symbol summary grid ────────────────────────────────────
                dbc.Row([
                    dbc.Col([
                        html.Div("📋 Per-Symbol Summary",
                                 style={"fontSize": "11px", "fontWeight": "700",
                                        "color": CLR_ACCENT, "marginBottom": "4px"}),
                        dag.AgGrid(
                            id="backtest-symbol-grid",
                            rowData=[],
                            columnDefs=[
                                {"field": "symbol",        "headerName": "Symbol",     "width": 88,
                                 "pinned": "left",
                                 "cellStyle": {"color": "#00d4ff"}},
                                {"field": "total_trades",  "headerName": "Trades",     "width": 70,
                                 "type": "numericColumn"},
                                {"field": "win_rate",      "headerName": "Win %",      "width": 72,
                                 "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
                                 "cellStyle": {"function": "params.value >= 60 ? {color:'#00e676'} : params.value >= 40 ? {color:'#ff9800'} : {color:'#ef5350'}"},
                                 "type": "numericColumn"},
                                {"field": "avg_pnl_pct",   "headerName": "Avg P&L%",   "width": 84,
                                 "valueFormatter": {"function": "(params.value >= 0 ? '+' : '') + d3.format('.2f')(params.value) + '%'"},
                                 "cellStyle": {"function": "params.value >= 0 ? {color:'#00e676'} : {color:'#ef5350'}"},
                                 "type": "numericColumn"},
                                {"field": "total_pnl_pct", "headerName": "Total P&L%", "width": 90,
                                 "valueFormatter": {"function": "(params.value >= 0 ? '+' : '') + d3.format('.1f')(params.value) + '%'"},
                                 "cellStyle": {"function": "params.value >= 0 ? {color:'#00e676',fontWeight:'700'} : {color:'#ef5350',fontWeight:'700'}"},
                                 "type": "numericColumn"},
                                {"field": "avg_win_pct",   "headerName": "Avg Win%",   "width": 80,
                                 "valueFormatter": {"function": "'+' + d3.format('.2f')(params.value) + '%'"},
                                 "cellStyle": {"color": "#00e676"}, "type": "numericColumn"},
                                {"field": "avg_loss_pct",  "headerName": "Avg Loss%",  "width": 82,
                                 "valueFormatter": {"function": "d3.format('.2f')(params.value) + '%'"},
                                 "cellStyle": {"color": "#ef5350"}, "type": "numericColumn"},
                                {"field": "t1_hit_rate",   "headerName": "T1 Hit%",    "width": 74,
                                 "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
                                 "type": "numericColumn"},
                                {"field": "t3_hit_rate",   "headerName": "T3 Hit%",    "width": 74,
                                 "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
                                 "type": "numericColumn"},
                                {"field": "sl_rate",       "headerName": "SL Rate%",   "width": 78,
                                 "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
                                 "cellStyle": {"color": "#ef5350"}, "type": "numericColumn"},
                                {"field": "avg_hold_days", "headerName": "Avg Hold",   "width": 76,
                                 "type": "numericColumn"},
                            ],
                            defaultColDef={"resizable": True, "sortable": True},
                            dashGridOptions={"pagination": True, "paginationPageSize": 20},
                            className="ag-theme-alpine-dark",
                            style={"height": "320px"},
                        ),
                    ]),
                ]),

            ], type="circle", color=CLR_ACCENT),

        ]),  # end Tab 2

    ], id="main-tabs", active_tab="tab-screener",
       style={"marginTop": "8px"}),

    # ── Help Modal ────────────────────────────────────────────────────────────
    _help_modal(),

], fluid=True, style={"backgroundColor": CLR_BG_PRIMARY, "minHeight": "100vh", "padding": "0 12px"})


# ─── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("wl-changed-store", "data"),
    Input("watchlist-check",  "n_intervals"),
    prevent_initial_call=True,
)
def poll_watchlist_change(n: int):
    """
    Checks the background flag set by the watchlist file watcher.
    Returns True only when the file actually changed; otherwise no_update
    so downstream callbacks are NOT triggered on every tick.
    """
    global _wl_changed_flag
    with _lock:
        changed = _wl_changed_flag
    if changed:
        return True
    return no_update   # ← critical: don't push a store update every 3 s


@app.callback(
    Output("wl-changed-alert", "is_open"),
    Input("wl-changed-store",  "data"),
    prevent_initial_call=True,
)
def show_watchlist_alert(changed: bool) -> bool:
    return bool(changed)


_INDEX_SYMBOLS = list(MARKET_INDICES.keys())  # ["SPY", "QQQ", "IWM", "^VIX"]


@app.callback(
    [
        Output("signals-store",       "data"),
        Output("last-refresh-text",   "children"),
        Output("loading-indicator",   "children"),
        Output("watchlist-indicator", "children"),
        Output("index-store",         "data"),
    ],
    [
        Input("auto-refresh",         "n_intervals"),
        Input("refresh-btn",          "n_clicks"),
        Input("wl-changed-store",     "data"),   # only fires when wl_changed=True (see poll_watchlist_change)
    ],
    prevent_initial_call=False,
)
def refresh_data(n_intervals: int, n_clicks: int, wl_changed) -> Tuple:
    """
    Main data pipeline: load watchlist → run analysis → store results.

    Triggers:
      • auto-refresh interval  (every 15 min)
      • Refresh button click
      • wl-changed-store = True  (watchlist file modified)
    """
    global _signals, _wl_changed_flag

    triggered = callback_context.triggered_id if callback_context.triggered else None
    force     = triggered in ("refresh-btn", None)

    # Reload watchlist when the file changed or on a forced refresh
    if wl_changed or force:
        watchlist_svc.load()
        with _lock:
            _wl_changed_flag = False

    symbols = watchlist_svc.get_symbols()
    if not symbols:
        return no_update, "No watchlist symbols", "", "⚠ No watchlist", no_update

    logger.info("Running analysis for %d symbols (force=%s)", len(symbols), force)

    try:
        new_signals = orchestrator.run_all(symbols, force=force)
        with _lock:
            _signals = new_signals

        rows = [s.to_row() for s in new_signals]
        ts   = datetime.now().strftime("%H:%M:%S")
        wl_info = html.Span([
            html.I(className="bi bi-list-check me-1"),
            f"{len(symbols)} symbols | updated {ts}",
        ], className="watchlist-ok")

        # ── Fetch index data (SPY / QQQ / IWM / ^VIX) ─────────────────────
        index_data: Dict[str, Any] = {}
        try:
            idx_signals = orchestrator.run_all(_INDEX_SYMBOLS, force=False)
            for sig in idx_signals:
                index_data[sig.symbol] = {
                    "price":        sig.price,
                    "change_pct":   sig.change_pct,
                    "market_state": sig.market_state.display,
                }
        except Exception as idx_exc:
            logger.warning("Index data fetch failed: %s", idx_exc)

        return (
            rows,
            f"Last refresh: {ts}",
            "",           # clear spinner
            wl_info,
            index_data,
        )

    except Exception as exc:
        logger.error("refresh_data failed: %s", exc, exc_info=True)
        return (
            no_update,
            f"Error: {exc}",
            "⚠",
            "⚠ Error scanning watchlist",
            no_update,
        )


@app.callback(
    [
        Output("main-grid",       "rowData"),
        Output("industry-filter", "options"),
        Output("setup-count",     "children"),
        Output("earnings-count",  "children"),
    ],
    [
        Input("signals-store",       "data"),
        Input("industry-filter",     "value"),
        Input("state-filter",        "value"),
        Input("action-filter",       "value"),
        Input("score-filter",        "value"),
        Input("earnings-filter",     "value"),
        Input("search-filter",       "value"),
        Input("earnings-only-store", "data"),
    ],
)
def update_grid(
    rows:          Optional[List[Dict]],
    industries:    Optional[List[str]],
    states:        Optional[List[str]],
    actions:       Optional[List[str]],
    min_score:     float,
    hide_earn:     List[str],
    search_q:      Optional[str],
    earnings_only: bool,
) -> Tuple:
    """Apply filters to the stored rows and populate KPI count cards."""
    if not rows:
        return [], [], "—", "—"

    # ── Build industry options from current data ────────────────────────────
    all_industries = sorted({r["industry"] for r in rows if r.get("industry") and r["industry"] != "Unknown"})
    industry_opts  = [{"label": i, "value": i} for i in all_industries]

    # ── Apply filters ──────────────────────────────────────────────────────
    filtered = rows

    if industries:
        filtered = [r for r in filtered if r.get("industry") in industries]

    if states:
        filtered = [r for r in filtered if any(s in r.get("market_state_raw", "") for s in states)]

    if actions:
        filtered = [r for r in filtered if r.get("action") in actions]

    if min_score and min_score > 0:
        filtered = [r for r in filtered if float(r.get("score", 0)) >= min_score]

    if "hide" in (hide_earn or []):
        filtered = [r for r in filtered if r.get("earnings_risk") != "⚠ YES"]

    if earnings_only:
        filtered = [r for r in filtered if r.get("earnings_risk") == "⚠ YES"]

    if search_q:
        q = search_q.upper().strip()
        filtered = [
            r for r in filtered
            if q in r.get("symbol", "").upper()
            or q in r.get("name", "").upper()
        ]

    # ── KPI counts (from full unfiltered dataset) ─────────────────────────
    setup_count  = sum(1 for r in rows if r.get("action") == "Buy Setup")
    earnings_cnt = sum(1 for r in rows if r.get("earnings_risk") == "⚠ YES")

    return (
        filtered,
        industry_opts,
        str(setup_count),
        str(earnings_cnt),
    )


@app.callback(
    [
        Output("detail-header", "children"),
        Output("detail-chart",  "figure"),
        Output("detail-stats",  "children"),
        Output("news-feed-content", "children", allow_duplicate=True),
    ],
    Input("main-grid", "selectedRows"),
    prevent_initial_call=True,
)
def update_detail_panel(selected: Optional[List[Dict]]) -> Tuple:
    """Render chart + news when a row is selected in the grid."""
    if not selected:
        placeholder = html.Div(
            "← Click a row to view chart, indicators, and news",
            style={"color": CLR_TEXT_DIM, "fontSize": "12px", "padding": "16px 0"},
        )
        from components.charts import _empty_chart
        return placeholder, _empty_chart("Select a stock to view chart"), html.Div(), html.Div()

    row    = selected[0]
    symbol = row.get("symbol", "")
    name   = row.get("name",   symbol)
    action = row.get("action", "Watch")
    state  = row.get("market_state", "")

    action_colors = {
        "Buy Setup": "#00e676", "Watch": "#00d4ff",
        "Wait": "#ff9800", "Avoid": "#ef5350",
    }
    action_color = action_colors.get(action, "#8896ac")

    # Header
    header = html.Div([
        html.Span(symbol, className="detail-symbol"),
        html.Span(f"  {name}", className="detail-name"),
        html.Br(),
        html.Span(state,  style={"fontSize": "12px", "color": row.get("state_color", "#8896ac")}),
        html.Span("  "),
        html.Span(action, style={"fontSize": "11px", "fontWeight": "700", "color": action_color,
                                  "border": f"1px solid {action_color}", "borderRadius": "3px",
                                  "padding": "1px 7px"}),
    ])

    # Chart
    df = orchestrator.get_cached_df(symbol)
    fig = build_stock_chart(
        symbol      = symbol,
        df          = df,
        price       = float(row.get("price",     0)),
        stop_loss   = float(row.get("stop_loss", 0)),
        target1     = float(row.get("target1",   0)),
        target2     = float(row.get("target2",   0)),
        target3     = float(row.get("target3",   0)),
        pattern     = row.get("pattern",     ""),
        signal_type = row.get("signal_type", ""),
        action      = row.get("action",      ""),
    )

    # Quick stats strip
    stats = dbc.Row([
        dbc.Col(_stat("Score",     row.get("score", "—"),        "#00d4ff"), width=2),
        dbc.Col(_stat("RSI",       row.get("rsi",   "—"),        "#c792ea"), width=2),
        dbc.Col(_stat("Vol/Avg",   f"{row.get('volume_ratio','—')}x", "#ffd54f"), width=2),
        dbc.Col(_stat("Entry",     row.get("entry_zone", "—"),   "#64b5f6"), width=3),
        dbc.Col(_stat("52W%",      f"{row.get('pct_from_52w_high','—')}%", "#8896ac"), width=2),
        dbc.Col(_stat("R:R",       row.get("risk_reward", "—"),  "#00e676"), width=1),
    ], className="g-1"),

    # Score breakdown
    score_detail = html.Div(
        row.get("score_tooltip", ""),
        style={"fontSize": "10px", "color": CLR_TEXT_DIM, "marginTop": "6px",
               "borderTop": f"1px solid {CLR_BORDER}", "paddingTop": "6px"},
    )

    detail_stats = html.Div([stats[0], score_detail])

    # News feed for this stock
    news_html = _build_news_panel(symbol, row)

    return header, fig, detail_stats, news_html


def _stat(label: str, value, color: str) -> html.Div:
    return html.Div([
        html.Div(label, className="stat-label"),
        html.Div(str(value), className="stat-value", style={"color": color}),
    ])


def _build_news_panel(symbol: str, row: Dict) -> html.Div:
    """Render the aggregated news feed from cached signals."""
    with _lock:
        signals_snapshot = list(_signals)

    news_elements = []

    # Get full news for selected symbol first
    selected_sig = next((s for s in signals_snapshot if s.symbol == symbol), None)
    if selected_sig and selected_sig.news_items:
        news_elements.append(
            html.Div(
                html.Span(f"🔍 {symbol} — {len(selected_sig.news_items)} headlines",
                          style={"color": CLR_ACCENT, "fontSize": "11px", "fontWeight": "700"}),
                style={"marginBottom": "6px"},
            )
        )
        for item in selected_sig.news_items[:6]:
            news_elements.append(_news_card(item))

    # Top news from Buy Setup stocks
    setups = [s for s in signals_snapshot if s.action == "Buy Setup" and s.symbol != symbol][:5]
    if setups:
        news_elements.append(html.Hr(style={"borderColor": CLR_BORDER, "margin": "8px 0"}))
        news_elements.append(
            html.Div("📊 OTHER BUY SETUPS",
                     style={"fontSize": "10px", "color": CLR_TEXT_DIM, "marginBottom": "6px",
                            "textTransform": "uppercase", "letterSpacing": "0.6px"})
        )
        for sig in setups:
            for item in sig.news_items[:2]:
                news_elements.append(_news_card(item, prefix=f"[{sig.symbol}] "))

    return html.Div(news_elements or [html.Div("No news available", style={"color": CLR_TEXT_DIM, "fontSize": "12px"})])


def _news_card(item, prefix: str = "") -> html.Div:
    from datetime import datetime as dt
    ts_str = ""
    if item.published_ts:
        try:
            ts_str = dt.fromtimestamp(item.published_ts).strftime("%b %d %H:%M")
        except Exception:
            pass

    return html.Div([
        html.A(
            f"{item.sentiment_icon} {prefix}{item.title}",
            href=item.link,
            target="_blank",
            className="news-title",
            style={"color": {
                "positive": "#00e676",
                "negative": "#ef5350",
                "neutral":  "#e8ecf4",
            }.get(item.sentiment, "#e8ecf4"), "textDecoration": "none"},
        ),
        html.Div(f"{item.publisher}  ·  {ts_str}", className="news-meta"),
    ], className=f"news-item {item.sentiment}")


@app.callback(
    [
        Output("spy-state",  "children"),
        Output("qqq-state",  "children"),
        Output("iwm-state",  "children"),
        Output("vix-card",   "children"),
    ],
    Input("index-store", "data"),
)
def update_index_cards(index_data: Optional[Dict]) -> Tuple:
    """Populate SPY / QQQ / IWM / VIX overview cards from index-store."""
    if not index_data:
        return "—", "—", "—", "—"

    def _fmt(sym: str) -> str:
        d = index_data.get(sym)
        if not d:
            return "—"
        price = d.get("price", 0)
        chg   = d.get("change_pct", 0)
        sign  = "+" if chg >= 0 else ""
        return f"${price:,.2f}  {sign}{chg:.1f}%"

    return _fmt("SPY"), _fmt("QQQ"), _fmt("IWM"), _fmt("^VIX")


@app.callback(
    Output("action-filter",     "value"),
    Input("setup-count-btn",    "n_clicks"),
    State("action-filter",      "value"),
    prevent_initial_call=True,
)
def filter_by_setup(n: int, current_val) -> list:
    """Toggle Buy Setup filter when the setup-count KPI card is clicked."""
    if not n:
        return no_update
    # Toggle: if already filtering on Buy Setup only, clear it
    if current_val == ["Buy Setup"]:
        return []
    return ["Buy Setup"]


@app.callback(
    Output("earnings-only-store",  "data"),
    Input("earnings-count-btn",    "n_clicks"),
    State("earnings-only-store",   "data"),
    prevent_initial_call=True,
)
def toggle_earnings_filter(n: int, current: bool) -> bool:
    """Toggle show-only-earnings-risk filter when the earnings KPI card is clicked."""
    if not n:
        return no_update
    return not bool(current)


@app.callback(
    Output("news-feed-content", "children", allow_duplicate=True),
    Input("signals-store", "data"),
    prevent_initial_call='initial_duplicate',
)
def populate_news_on_load(rows: Optional[List[Dict]]) -> html.Div:
    """Populate the news feed with Buy Setup headlines when data first loads.

    Fires whenever signals-store is refreshed so the panel is always current.
    When the user selects a row, update_detail_panel overwrites this output
    with stock-specific news (allow_duplicate=True on both outputs).
    """
    with _lock:
        signals_snapshot = list(_signals)

    if not signals_snapshot:
        return html.Div("Data loading…", style={"color": CLR_TEXT_DIM, "fontSize": "12px"})

    # ── Buy Setup stocks first, then watched stocks ────────────────────────
    setups   = [s for s in signals_snapshot if s.action == "Buy Setup"]
    watchall = [s for s in signals_snapshot if s.action != "Buy Setup"]

    news_elements: list = []
    seen_links: set = set()

    def _add_items(sig_list, max_stocks: int, items_each: int) -> None:
        for sig in sig_list[:max_stocks]:
            for item in sig.news_items[:items_each]:
                if item.link in seen_links:
                    continue
                seen_links.add(item.link)
                news_elements.append(_news_card(item, prefix=f"[{sig.symbol}] "))

    _add_items(setups,   max_stocks=8,  items_each=2)

    if not news_elements:
        _add_items(watchall, max_stocks=6, items_each=2)

    if not news_elements:
        return html.Div("No news available", style={"color": CLR_TEXT_DIM, "fontSize": "12px"})

    count  = len(setups)
    header = html.Div([
        html.Span(
            f"📊 Buy Setup Headlines — {count} setup{'s' if count != 1 else ''}",
            style={"color": CLR_ACCENT, "fontSize": "11px", "fontWeight": "700"},
        ),
        html.Span(
            " · click a row to view stock-specific news",
            style={"fontSize": "10px", "color": CLR_TEXT_DIM},
        ),
    ], style={"marginBottom": "8px"})

    return html.Div([header] + news_elements)


@app.callback(
    Output("help-modal", "is_open"),
    [Input("help-btn",         "n_clicks"),
     Input("help-modal-close", "n_clicks")],
    State("help-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_help_modal(open_clicks: int, close_clicks: int, is_open: bool) -> bool:
    return not is_open


# ─── New Feature Callbacks ─────────────────────────────────────────────────────

@app.callback(
    Output("next-refresh-hint", "children"),
    Input("auto-refresh", "n_intervals"),
    prevent_initial_call=False,
)
def update_next_refresh_hint(n: int) -> str:
    """Show approximate time until next auto-refresh."""
    interval_ms = 900_000  # 15 min
    elapsed_ms  = (n or 0) * interval_ms
    next_ms     = interval_ms - (elapsed_ms % interval_ms) if n else interval_ms
    mins        = max(1, round(next_ms / 60_000))
    return f"⏱ Next auto-refresh in ~{mins} min"


@app.callback(
    Output("signal-alert", "children"),
    Output("signal-alert", "is_open"),
    Input("signals-store", "data"),
    prevent_initial_call=True,
)
def show_signal_alert(data):
    """Flash a banner when new Buy Setup signals are present."""
    if not data:
        return "", False
    rows   = data if isinstance(data, list) else []
    setups = [r for r in rows if r.get("action") == "Buy Setup"]
    if not setups:
        return "", False
    tickers = " · ".join(r["symbol"] for r in setups[:12])
    return (
        f"🚨 {len(setups)} BUY SETUP SIGNAL{'S' if len(setups) != 1 else ''} TRIGGERED: {tickers}"
        f"  —  score ≥ 4, pattern/touch confirmed",
        True,
    )


@app.callback(
    Output("vix-subtext", "children"),
    Input("index-store", "data"),
    prevent_initial_call=False,
)
def update_vix_subtext(data):
    """Show VIX fear interpretation below the VIX card."""
    if not data:
        return ""
    vix_data = data.get("^VIX", {})
    price    = float(vix_data.get("price", 0) or 0)
    if price <= 0:
        return ""
    if price < 15:
        label, color = "😴 Complacent", "#ff9800"
    elif price < 20:
        label, color = "✅ Normal — ideal swing entry", "#00e676"
    elif price < 30:
        label, color = "⚠️ Elevated — widen stops", "#ffeb3b"
    elif price < 40:
        label, color = "🚨 High Fear — wait for flush", "#ef5350"
    else:
        label, color = "💥 Extreme Fear — watch only", "#b71c1c"
    return html.Span(label, style={"fontSize": "10px", "color": color})


@app.callback(
    Output("backtest-kpis",        "children"),
    Output("equity-curve-chart",   "figure"),
    Output("exit-reason-chart",    "figure"),
    Output("backtest-grid",        "rowData"),
    Output("backtest-symbol-grid", "rowData"),
    Output("backtest-status",      "children"),
    Output("benchmark-bar-chart",  "figure"),
    Output("bt-result-store",      "data"),
    Input("run-backtest-btn",      "n_clicks"),
    State("bt-symbol-dropdown",    "value"),
    State("bt-strategy-dropdown",  "value"),
    State("bt-capital-input",      "value"),
    prevent_initial_call=True,
)
def run_backtest(n_clicks: int, selected_symbols, strategy: str, capital):
    """Run 1-year walk-forward backtest against selected symbols + strategy."""
    import traceback
    import datetime as _dt

    strategy = strategy or "all"

    def _empty_fig(title=""):
        return go.Figure(layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=CLR_TEXT_DIM),
            title=dict(text=title, font=dict(size=10, color=CLR_TEXT_DIM)),
            margin=dict(l=40, r=10, t=30, b=20),
        ))

    try:
        all_symbols = watchlist_svc.get_symbols()
        symbols     = selected_symbols if selected_symbols else all_symbols
        if not symbols:
            return [], _empty_fig(), _empty_fig(), [], [], "⚠️ Watchlist is empty.", _empty_fig(), None

        import yfinance as yf
        end_dt   = _dt.date.today()
        start_dt = end_dt - _dt.timedelta(days=420)   # buffer for indicator warmup
        dfs      = {}

        # Bulk download all symbols in a single HTTP request (much faster than 1-by-1)
        try:
            raw_bulk = yf.download(
                symbols,
                start=start_dt.isoformat(),
                end=end_dt.isoformat(),
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
            )
            if raw_bulk is not None and not raw_bulk.empty:
                if len(symbols) == 1:
                    sym = symbols[0]
                    df = raw_bulk.copy()
                    if df.index.tzinfo is not None:
                        df.index = df.index.tz_localize(None)
                    df.columns = [c.title() if c.islower() else c for c in df.columns]
                    if len(df) >= 60:
                        dfs[sym] = df
                else:
                    for sym in symbols:
                        try:
                            if sym in raw_bulk.columns.get_level_values(0):
                                df = raw_bulk[sym].copy().dropna(how="all")
                                if df.index.tzinfo is not None:
                                    df.index = df.index.tz_localize(None)
                                df.columns = [c.title() if c.islower() else c for c in df.columns]
                                if len(df) >= 60:
                                    dfs[sym] = df
                        except Exception:
                            pass
        except Exception as bulk_exc:
            logger.warning("Bulk backtest download failed, falling back to per-symbol: %s", bulk_exc)

        # Fallback: per-symbol download for any that failed in bulk
        missing = [s for s in symbols if s not in dfs]
        for sym in missing:
            try:
                raw = yf.download(sym, start=start_dt.isoformat(), end=end_dt.isoformat(),
                                  progress=False, auto_adjust=True, multi_level_index=False)
                if raw is not None and len(raw) >= 60:
                    raw.index = raw.index.tz_localize(None) if raw.index.tzinfo else raw.index
                    raw.columns = [c.title() if c.islower() else c for c in raw.columns]
                    dfs[sym] = raw
            except Exception as e:
                logger.warning("yfinance download failed for %s: %s", sym, e)

        if not dfs:
            return [], _empty_fig(), _empty_fig(), [], [], "⚠️ Could not fetch price data.", _empty_fig(), None

        result = _backtest_engine.run_portfolio(dfs, lookback_days=365, strategy=strategy)

        # ── Capital tracking per trade ────────────────────────────────────
        initial_capital = float(capital or INITIAL_CAPITAL)
        cap_current     = initial_capital
        sorted_trades   = sorted(result.all_trades, key=lambda t: t.entry_date)
        cap_map: dict   = {}           # (symbol, entry_date) -> (before, after)
        for tr in sorted_trades:
            cb = round(cap_current, 2)
            cap_current = round(cap_current * (1 + tr.pnl_pct / 100), 2)
            cap_map[(tr.symbol, tr.entry_date)] = (cb, round(cap_current, 2))
        final_capital = cap_current

        # Annualized return
        annualized_return = 0.0
        testing_days = 0
        if sorted_trades:
            try:
                s_d = _dt.date.fromisoformat(sorted_trades[0].entry_date[:10])
                e_d = _dt.date.fromisoformat(sorted_trades[-1].exit_date[:10])
                testing_days = (e_d - s_d).days
                if testing_days > 0:
                    total_ret = (final_capital - initial_capital) / initial_capital
                    annualized_return = ((1 + total_ret) ** (365.0 / testing_days) - 1) * 100
            except Exception:
                pass

        # ── KPI cards ──────────────────────────────────────────────────────
        def _kpi(label, value, color=CLR_TEXT_MAIN):
            return dbc.Col(html.Div([
                html.Div(label, style={"fontSize": "10px", "color": CLR_TEXT_DIM, "letterSpacing": "0.6px"}),
                html.Div(value, style={"fontSize": "18px", "fontWeight": "700", "color": color}),
            ], className="overview-card"), md=2)

        wr_c   = "#00e676" if result.win_rate  >= 55 else "#ff9800" if result.win_rate  >= 40 else "#ef5350"
        pnl_c  = "#00e676" if result.avg_pnl_pct >= 0 else "#ef5350"
        cap_c  = "#00e676" if final_capital >= initial_capital else "#ef5350"
        ann_c  = "#00e676" if annualized_return >= 0 else "#ef5350"
        kpis = [
            _kpi("Trades",       str(result.total_trades)),
            _kpi("Win Rate",     f"{result.win_rate:.1f}%",           wr_c),
            _kpi("Avg P&L",      f"{result.avg_pnl_pct:+.2f}%",      pnl_c),
            _kpi("Initial Cap",  f"${initial_capital:,.0f}",          CLR_TEXT_MAIN),
            _kpi("Final Capital",f"${final_capital:,.0f}",            cap_c),
            _kpi("Annualized",   f"{annualized_return:+.1f}%",        ann_c),
            _kpi("Best Trade",   f"{result.best_trade_pct:+.1f}%",    "#00e676"),
            _kpi("Worst Trade",  f"{result.worst_trade_pct:+.1f}%",   "#ef5350"),
        ]

        # ── Equity curve ───────────────────────────────────────────────────
        eq_fig = go.Figure()
        if result.equity_curve:
            dates  = [p["date"] for p in result.equity_curve]
            equity = [p["equity"] for p in result.equity_curve]
            eq_fig.add_trace(go.Scatter(
                x=dates, y=equity, mode="lines",
                line=dict(color=CLR_ACCENT, width=2),
                fill="tozeroy", fillcolor="rgba(0,212,255,0.07)",
                name=f"Strategy (${initial_capital:,.0f} start)",
            ))
            eq_fig.add_hline(y=initial_capital, line=dict(color=CLR_TEXT_DIM, dash="dot", width=1))
        eq_fig.update_layout(
            title=dict(text=f"Portfolio Equity Curve  (sequential compounding, ${initial_capital:,.0f} start)",
                       font=dict(size=10, color=CLR_TEXT_DIM)),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=CLR_TEXT_MAIN, size=10),
            xaxis=dict(showgrid=False, color=CLR_TEXT_DIM),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)",
                       tickprefix="$", color=CLR_TEXT_DIM),
            margin=dict(l=55, r=10, t=30, b=30),
            showlegend=False,
        )

        # ── Exit reason donut ──────────────────────────────────────────────
        reason_counts: dict = {}
        for tr in result.all_trades:
            reason_counts[tr.exit_reason] = reason_counts.get(tr.exit_reason, 0) + 1
        reason_colors = {"T1": "#69f0ae", "T2": "#00e676", "T3": "#b9f6ca",
                         "SL": "#ef5350", "TES": "#ff9800"}
        er_fig = go.Figure(go.Pie(
            labels=list(reason_counts.keys()),
            values=list(reason_counts.values()),
            hole=0.52,
            marker_colors=[reason_colors.get(k, CLR_TEXT_DIM) for k in reason_counts],
            textfont=dict(size=11),
        ))
        er_fig.update_layout(
            title=dict(text="Exit Breakdown", font=dict(size=10, color=CLR_TEXT_DIM)),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=CLR_TEXT_MAIN),
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
        )

        # ── Benchmark comparison bar ────────────────────────────────────────
        bench_returns = {}
        bench_syms    = {"SPY": "S&P 500", "QQQ": "NASDAQ", "DIA": "DOW", "IWM": "RUSSELL"}
        for bsym, blabel in bench_syms.items():
            try:
                bdf = yf.download(bsym, start=start_dt.isoformat(), end=end_dt.isoformat(),
                                  progress=False, auto_adjust=True, multi_level_index=False)
                if bdf is not None and len(bdf) >= 2:
                    # 1-year return = last close / close 252 sessions ago
                    closes = bdf["Close"] if "Close" in bdf.columns else bdf.iloc[:, 0]
                    yr_ago = closes.iloc[max(0, len(closes) - 252)]
                    now    = closes.iloc[-1]
                    bench_returns[blabel] = round((float(now) - float(yr_ago)) / float(yr_ago) * 100, 1)
            except Exception:
                pass

        strat_label = f"Strategy ({strategy.upper()})"
        bar_names   = list(bench_returns.keys()) + [strat_label]
        bar_vals    = list(bench_returns.values()) + [round(result.total_pnl_pct, 1)]
        bar_colors  = [
            "#00e676" if v >= 0 else "#ef5350"
            for v in bar_vals[:-1]
        ] + [CLR_ACCENT]

        bm_fig = go.Figure(go.Bar(
            x=bar_names, y=bar_vals,
            marker_color=bar_colors,
            text=[f"{v:+.1f}%" for v in bar_vals],
            textposition="outside",
            textfont=dict(size=11, color=CLR_TEXT_MAIN),
        ))
        bm_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=CLR_TEXT_MAIN, size=10),
            xaxis=dict(showgrid=False, color=CLR_TEXT_DIM),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)",
                       ticksuffix="%", color=CLR_TEXT_DIM, zeroline=True,
                       zerolinecolor="rgba(255,255,255,0.2)"),
            margin=dict(l=45, r=10, t=10, b=30),
            showlegend=False,
        )

        # ── Trade row data (with capital tracking + exit breakdown) ──────
        def _exit_legs(tr) -> list:
            """Build partial-exit sub-rows for the exit detail breakdown."""
            ep  = tr.entry_price
            cb  = cap_map.get((tr.symbol, tr.entry_date), (initial_capital, initial_capital))[0]
            legs = []
            if tr.t1_exit or tr.exit_reason == "T3":
                legs.append({"leg": "T1  ⅓ sell", "price": round(ep * (1 + TARGET_1_PCT), 2),
                              "pct": f"+{TARGET_1_PCT*100:.0f}%",
                              "capital_pnl": round(cb / 3 * TARGET_1_PCT, 2)})
            if tr.t2_exit or tr.exit_reason == "T3":
                legs.append({"leg": "T2  ⅓ sell", "price": round(ep * (1 + TARGET_2_PCT), 2),
                              "pct": f"+{TARGET_2_PCT*100:.0f}%",
                              "capital_pnl": round(cb / 3 * TARGET_2_PCT, 2)})
            if tr.exit_reason == "T3":
                legs.append({"leg": "T3  ⅓ sell", "price": round(ep * (1 + TARGET_3_PCT), 2),
                              "pct": f"+{TARGET_3_PCT*100:.0f}%",
                              "capital_pnl": round(cb / 3 * TARGET_3_PCT, 2)})
            elif tr.exit_reason == "SL":
                sl_frac_lbl = "⅓ left" if (tr.t1_exit and tr.t2_exit) else ("⅔ left" if tr.t1_exit else "full pos")
                sl_cap_frac = 1/3 if (tr.t1_exit and tr.t2_exit) else (2/3 if tr.t1_exit else 1.0)
                legs.append({"leg": f"SL  {sl_frac_lbl}", "price": round(ep * (1 - STOP_LOSS_PCT), 2),
                              "pct": f"-{STOP_LOSS_PCT*100:.0f}%",
                              "capital_pnl": round(cb * sl_cap_frac * (-STOP_LOSS_PCT), 2)})
            elif tr.exit_reason == "TES":
                tes_frac_lbl = "⅓ left" if (tr.t1_exit and tr.t2_exit) else ("⅔ left" if tr.t1_exit else "full pos")
                tes_cap_frac = 1/3 if (tr.t1_exit and tr.t2_exit) else (2/3 if tr.t1_exit else 1.0)
                tes_pct = tr.exit_price / ep - 1
                legs.append({"leg": f"TES {tes_frac_lbl}", "price": round(tr.exit_price, 2),
                              "pct": f"{tes_pct*100:+.1f}%",
                              "capital_pnl": round(cb * tes_cap_frac * tes_pct, 2)})
            return legs

        trade_rows = []
        for tr in result.all_trades:
            cb, ca = cap_map.get((tr.symbol, tr.entry_date), (initial_capital, initial_capital))
            trade_rows.append({
                "symbol":           tr.symbol,
                "entry_date":       str(tr.entry_date)[:10],
                "exit_date":        str(tr.exit_date)[:10],
                "hold_days":        tr.hold_days,
                "entry_price":      round(tr.entry_price, 2),
                "exit_price":       round(tr.exit_price,  2),
                "pnl_pct":          round(tr.pnl_pct, 2),
                "exit_reason":      tr.exit_reason,
                "score":            tr.score,
                "pattern":          tr.pattern,
                "signal_type":      tr.signal_type,
                "t1_hit":           "✓" if tr.t1_exit else "·",
                "t2_hit":           "✓" if tr.t2_exit else "·",
                "t3_hit":           "✓" if tr.t3_exit else "·",
                "max_drawdown_pct": round(tr.max_drawdown_pct, 1),
                "capital_before":   cb,
                "capital_after":    ca,
                "capital_pnl":      round(ca - cb, 2),
                "exit_legs":        _exit_legs(tr),   # stored in bt_store; ignored by grid
            })

        # ── Per-symbol summary ─────────────────────────────────────────────
        sym_rows = [
            {
                "symbol":        s.symbol,
                "total_trades":  s.total_trades,
                "win_rate":      round(s.win_rate, 1),
                "avg_pnl_pct":   round(s.avg_pnl_pct, 2),
                "total_pnl_pct": round(s.total_pnl_pct, 1),
                "avg_win_pct":   round(s.avg_win_pct,  2),
                "avg_loss_pct":  round(s.avg_loss_pct, 2),
                "t1_hit_rate":   round(s.t1_hit_rate,  1),
                "t3_hit_rate":   round(s.t3_hit_rate,  1),
                "sl_rate":       round(s.sl_rate,       1),
                "avg_hold_days": round(s.avg_hold_days, 1),
            }
            for s in result.per_symbol
        ]

        # Serialise minimal data needed for the per-trade chart callback
        bt_store = {
            "trade_rows":       trade_rows,   # includes exit_legs and capital info
            "initial_capital":  initial_capital,
            "dfs_json":   {sym: df.tail(300).to_json(date_format="iso", orient="split")
                           for sym, df in dfs.items()},
        }

        from services.backtest_service import STRATEGY_LABELS
        strat_name = STRATEGY_LABELS.get(strategy, strategy)
        cap_delta  = final_capital - initial_capital
        cap_sign   = "+" if cap_delta >= 0 else ""
        status = (
            f"✅ {strat_name} — {result.total_trades} trades · "
            f"{result.win_rate:.0f}% win rate · "
            f"${initial_capital:,.0f}→${final_capital:,.0f} ({cap_sign}{cap_delta:,.0f}) · "
            f"Annualized {annualized_return:+.1f}%"
        )
        return kpis, eq_fig, er_fig, trade_rows, sym_rows, status, bm_fig, bt_store

    except Exception as exc:
        logger.error("Backtest error: %s\n%s", exc, traceback.format_exc())
        ef = go.Figure(layout=go.Layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"))
        return [], ef, ef, [], [], f"❌ Error: {exc}", ef, None


@app.callback(
    Output("bt-symbol-chart",        "figure"),
    Output("bt-chart-symbol-label",  "children"),
    Output("bt-exit-detail",         "children"),
    Input("backtest-grid",           "selectedRows"),
    State("bt-result-store",         "data"),
    prevent_initial_call=True,
)
def update_bt_symbol_chart(selected_rows, bt_store):
    """Show 1-year OHLCV candle chart + exit breakdown for the selected trade."""
    def _empty():
        return go.Figure(layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=CLR_TEXT_DIM),
            annotations=[dict(text="Click a trade row to view chart",
                              x=0.5, y=0.5, xref="paper", yref="paper",
                              showarrow=False, font=dict(color=CLR_TEXT_DIM, size=12))],
        ))

    if not selected_rows or not bt_store:
        return _empty(), "", ""

    trade = selected_rows[0]
    symbol = trade.get("symbol", "")
    dfs_json = (bt_store or {}).get("dfs_json", {})
    if symbol not in dfs_json:
        return _empty(), f"— no data for {symbol}", ""

    import io
    df = pd.read_json(io.StringIO(dfs_json[symbol]), orient="split")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # EMA21 and SMA50 (recompute on full available window for accuracy)
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()

    # Restrict chart to last ~300 bars for display
    df = df.tail(300)
    dates = df.index
    fig   = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=dates,
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name=symbol,
        increasing_line_color="#00e676", decreasing_line_color="#ef5350",
        increasing_fillcolor="#00e676",  decreasing_fillcolor="#ef5350",
        line=dict(width=0.8),
    ))

    # EMA21
    fig.add_trace(go.Scatter(
        x=dates, y=df["EMA21"], mode="lines",
        line=dict(color="#00d4ff", width=1.2),
        name="EMA21", opacity=0.85,
    ))

    # SMA50
    fig.add_trace(go.Scatter(
        x=dates, y=df["SMA50"], mode="lines",
        line=dict(color="#ffa500", width=1.2),
        name="SMA50", opacity=0.85,
    ))

    entry_date  = trade.get("entry_date", "")
    exit_date   = trade.get("exit_date",  "")
    entry_price = float(trade.get("entry_price", 0) or 0)
    exit_price  = float(trade.get("exit_price",  0) or 0)
    exit_reason = trade.get("exit_reason", "")
    pnl_pct     = float(trade.get("pnl_pct", 0) or 0)
    cap_before  = float(trade.get("capital_before", 0) or 0)
    cap_after   = float(trade.get("capital_after",  0) or 0)

    if entry_price > 0:
        sl  = round(entry_price * (1 - STOP_LOSS_PCT), 2)
        t1  = round(entry_price * (1 + TARGET_1_PCT),  2)
        t2  = round(entry_price * (1 + TARGET_2_PCT),  2)
        t3  = round(entry_price * (1 + TARGET_3_PCT),  2)

        exit_color_map = {"T3": "#b9f6ca", "SL": "#ef5350", "TES": "#ff9800"}
        exit_color = exit_color_map.get(exit_reason, "#69f0ae")

        for lv, col, lname, ldash in [
            (sl, "#ef5350", f"SL\u2212{STOP_LOSS_PCT*100:.0f}%", "dash"),
            (t1, "#69f0ae", f"T1+{TARGET_1_PCT*100:.0f}%", "dot"),
            (t2, "#00e676", f"T2+{TARGET_2_PCT*100:.0f}%", "dot"),
            (t3, "#b9f6ca", f"T3+{TARGET_3_PCT*100:.0f}%", "dot"),
        ]:
            fig.add_hline(y=lv, line=dict(color=col, width=0.9, dash=ldash),
                          annotation_text=lname,
                          annotation_font=dict(size=9, color=col),
                          annotation_position="right")

        # Entry marker
        fig.add_trace(go.Scatter(
            x=[entry_date], y=[entry_price],
            mode="markers+text",
            marker=dict(symbol="triangle-up", color="#00d4ff", size=13),
            text=["BUY"], textposition="bottom center",
            textfont=dict(size=9, color="#00d4ff"),
            name="Entry", showlegend=False,
        ))

        # Exit marker
        if exit_price > 0:
            fig.add_trace(go.Scatter(
                x=[exit_date], y=[exit_price],
                mode="markers+text",
                marker=dict(symbol="triangle-down", color=exit_color, size=13),
                text=[exit_reason], textposition="top center",
                textfont=dict(size=9, color=exit_color),
                name="Exit", showlegend=False,
            ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CLR_TEXT_MAIN, size=10),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False), color=CLR_TEXT_DIM),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", color=CLR_TEXT_DIM),
        margin=dict(l=55, r=90, t=30, b=30),
        legend=dict(orientation="h", font=dict(size=9), bgcolor="rgba(0,0,0,0)", x=0, y=1.05),
        hovermode="x unified",
    )

    pnl_col = "#00e676" if pnl_pct >= 0 else "#ef5350"
    label   = (f"  {symbol}  ·  Entry {entry_date} @ ${entry_price:.2f}"
               f"  →  Exit {exit_date} @ ${exit_price:.2f}  ·  "
               f"P&L {pnl_pct:+.2f}%  ·  {exit_reason}")

    # ── Exit breakdown bar ────────────────────────────────────────────────
    exit_legs = trade.get("exit_legs", [])
    leg_colors = {"T1": "#69f0ae", "T2": "#00e676", "T3": "#b9f6ca",
                  "SL": "#ef5350", "TE": "#ff9800"}

    pills = []
    for leg in exit_legs:
        key    = leg["leg"][:2].strip()
        col    = leg_colors.get(key, CLR_TEXT_DIM)
        cp     = leg.get("capital_pnl", 0)
        cp_str = f"  {'+' if cp>=0 else ''}{cp:,.0f}$"
        pills.append(html.Span([
            html.Span(leg["leg"], style={"fontWeight": "700"}),
            html.Span(f" @${leg['price']:.2f}  {leg['pct']}", style={"color": CLR_TEXT_DIM}),
            html.Span(cp_str, style={"fontWeight": "600"}),
        ], style={
            "color": col,
            "border": f"1px solid {col}",
            "borderRadius": "4px",
            "padding": "2px 8px",
            "marginRight": "6px",
            "fontSize": "11px",
            "display": "inline-block",
            "verticalAlign": "middle",
        }))

    cap_delta = round(cap_after - cap_before, 0)
    cap_col   = "#00e676" if cap_delta >= 0 else "#ef5350"
    exit_detail = html.Div([
        html.Span(f"📋 {symbol} exits:  ",
                  style={"fontSize": "11px", "fontWeight": "700", "color": CLR_ACCENT,
                         "marginRight": "6px", "verticalAlign": "middle"}),
        *pills,
        html.Span("  │  ", style={"color": CLR_BORDER, "margin": "0 6px"}),
        html.Span([
            html.Span("Capital: ", style={"color": CLR_TEXT_DIM, "fontSize": "11px"}),
            html.Span(f"${cap_before:,.0f}", style={"color": CLR_TEXT_MAIN, "fontSize": "11px"}),
            html.Span(" → ", style={"color": CLR_TEXT_DIM, "fontSize": "11px"}),
            html.Span(f"${cap_after:,.0f}", style={"color": cap_col, "fontWeight": "700", "fontSize": "11px"}),
            html.Span(f"  ({'+' if cap_delta>=0 else ''}{cap_delta:,.0f}$)",
                      style={"color": cap_col, "fontSize": "11px"}),
        ]),
    ], style={
        "padding": "7px 12px",
        "backgroundColor": CLR_BG_CARD,
        "border": f"1px solid {CLR_BORDER}",
        "borderRadius": "4px",
        "marginBottom": "6px",
        "flexWrap": "wrap",
    }) if exit_legs else ""

    return fig, html.Span(label, style={"color": pnl_col}), exit_detail


@app.callback(
    Output("bt-symbol-dropdown", "options"),
    Input("signals-store", "data"),
    prevent_initial_call=False,
)
def populate_bt_symbol_dropdown(_):
    """Keep the backtest symbol dropdown populated from the current watchlist."""
    syms = watchlist_svc.get_symbols()
    return [{"label": s, "value": s} for s in sorted(syms)]


@app.callback(
    Output("bt-symbol-dropdown", "value"),
    Output("main-tabs",          "active_tab"),
    Output("send-to-backtest-btn", "style"),
    Input("send-to-backtest-btn", "n_clicks"),
    Input("main-grid",           "selectedRows"),
    State("bt-symbol-dropdown",  "value"),
    prevent_initial_call=True,
)
def handle_send_to_backtest(btn_clicks, selected_rows, current_bt_syms):
    """
    Two triggers:
    1. Row selected in main-grid → show the 'Backtest ↗' button (reveal it).
    2. Button clicked → switch to Backtest tab with that symbol pre-selected.
    """
    from dash import ctx
    trigger   = ctx.triggered_id
    btn_style = {"fontSize": "10px", "padding": "2px 8px",
                 "marginLeft": "10px", "verticalAlign": "middle"}

    if trigger == "main-grid":
        if not selected_rows:
            return current_bt_syms, "tab-screener", {**btn_style, "display": "none"}
        return current_bt_syms, "tab-screener", {**btn_style, "display": "inline-block"}

    if trigger == "send-to-backtest-btn" and btn_clicks and selected_rows:
        symbol = selected_rows[0].get("symbol", "")
        if symbol:
            return [symbol], "tab-backtest", {**btn_style, "display": "inline-block"}

    return current_bt_syms, "tab-screener", {**btn_style, "display": "none"}


# ─── Theme Toggle ──────────────────────────────────────────────────────────────

@app.callback(
    Output("theme-store",       "data"),
    Output("theme-toggle-btn",  "children"),
    Input("theme-toggle-btn",   "n_clicks"),
    State("theme-store",        "data"),
    prevent_initial_call=True,
)
def cycle_theme(n_clicks, current_theme):
    """Cycle dark → dim → light → dark and update button label."""
    order   = ["dark", "dim", "light"]
    labels  = {"dark": "🌙 Dark", "dim": "🌓 Dim", "light": "☀️ Light"}
    idx     = order.index(current_theme) if current_theme in order else 0
    nxt     = order[(idx + 1) % len(order)]
    return nxt, labels[nxt]


app.clientside_callback(
    """
    function(theme) {
        var themes = ['theme-dark', 'theme-dim', 'theme-light'];
        document.body.classList.remove.apply(document.body.classList, themes);
        document.body.classList.add('theme-' + (theme || 'dark'));
        return window.dash_clientside.no_update;
    }
    """,
    Output("theme-store", "id"),   # dummy — just triggers side-effect
    Input("theme-store",  "data"),
)


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting %s on http://localhost:%d", APP_TITLE, APP_PORT)
    logger.info("Watchlist: %s (%d symbols)", WATCHLIST_PATH, len(watchlist_svc.get_symbols()))
    app.run(host="0.0.0.0", port=APP_PORT, debug=DEBUG_MODE)
