"""
components/charts.py — Plotly figure builders for the stock detail panel.

Single Responsibility: Only constructs Plotly figures from OHLCV + indicators.
Open/Closed: Add new overlay types without modifying the core builder.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import CHART_BARS, CHART_BG, CHART_HEIGHT, CHART_TEMPLATE, DEMAND_ZONE_MULTIPLIER

# Chart-specific colour constants
_CLR_EMA21     = "#00d4ff"
_CLR_SMA50     = "#ffa500"
_CLR_SMA200    = "#ef5350"

logger = logging.getLogger(__name__)

# Column-name constants produced by pandas_ta (or the fallback path)
_EMA21  = "EMA_21"
_SMA50  = "SMA_50"
_SMA200 = "SMA_200"
_RSI    = "RSI_14"


# ─── Public Builder ────────────────────────────────────────────────────────────

def build_stock_chart(
    symbol:     str,
    df:         pd.DataFrame,
    price:      float = 0.0,
    stop_loss:  float = 0.0,
    target1:    float = 0.0,
    target2:    float = 0.0,
    target3:    float = 0.0,
    pattern:    str   = "",
    signal_type: str  = "",
    action:     str   = "",
) -> go.Figure:
    """
    Two-row Plotly figure:
      Row 1 (70%): Candlestick + EMA21 + SMA50 + SMA200 + Volume overlay
      Row 2 (30%): RSI panel with overbought/oversold bands

    Only the last CHART_BARS daily bars are displayed.
    """
    if df is None or df.empty:
        return _empty_chart(f"{symbol} — No data available")

    # Compute indicators if not already present
    df = _ensure_indicators(df)
    df_plot = df.tail(CHART_BARS).copy()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.70, 0.30],
    )

    # ── Row 1: Candlestick ──────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df_plot.index,
            open=df_plot["Open"],
            high=df_plot["High"],
            low=df_plot["Low"],
            close=df_plot["Close"],
            name="Price",
            increasing_line_color="#00e676",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="rgba(0,230,118,0.9)",
            decreasing_fillcolor="rgba(239,83,80,0.9)",
            showlegend=False,
            whiskerwidth=0.4,
        ),
        row=1, col=1,
    )

    # Moving averages
    _add_line(fig, df_plot, _EMA21,  "EMA 21",  _CLR_EMA21,  1.4, row=1)
    _add_line(fig, df_plot, _SMA50,  "SMA 50",  _CLR_SMA50,  1.4, row=1)
    _add_line(fig, df_plot, _SMA200, "SMA 200", _CLR_SMA200, 1.2, row=1, dash="dot")

    # Volume overlay (secondary y hidden — semi-transparent bars)
    bar_colors = [
        "rgba(0,230,118,0.28)" if c >= o else "rgba(239,83,80,0.28)"
        for c, o in zip(df_plot["Close"], df_plot["Open"])
    ]
    vol_max  = float(df_plot["Volume"].max()) if df_plot["Volume"].max() else 1
    vol_norm = df_plot["Volume"] / vol_max * float(df_plot["High"].max()) * 0.25

    fig.add_trace(
        go.Bar(
            x=df_plot.index,
            y=vol_norm,
            name="Volume",
            marker_color=bar_colors,
            showlegend=False,
        ),
        row=1, col=1,
    )

    # ── Demand Zone band ──────────────────────────────────────────────────────
    _add_demand_zone(fig, df_plot)

    # ── Trade Level Lines (labelled with price + %) ───────────────────────────
    if stop_loss:
        _h_line(fig, stop_loss, "#ff1744", f"❌ SL  ${stop_loss:.2f}  (−17%)",  row=1)
    if target1:
        _h_line(fig, target1,   "#00e676", f"🎯 T1  ${target1:.2f}  (+10%)",  row=1)
    if target2:
        _h_line(fig, target2,   "#69f0ae", f"🎯 T2  ${target2:.2f}  (+15%)",  row=1, dash="dot")
    if target3:
        _h_line(fig, target3,   "#b9f6ca", f"🎯 T3  ${target3:.2f}  (+20%)",  row=1, dash="dot")

    # ── Buy-Setup entry marker ────────────────────────────────────────────────
    if action == "Buy Setup" and not df_plot.empty:
        last_dt  = df_plot.index[-1]
        last_low = float(df_plot["Low"].iloc[-1])
        label    = pattern or signal_type or "Entry"
        fig.add_annotation(
            x=last_dt,
            y=last_low * 0.984,
            text=f"🔺 {label}",
            showarrow=True,
            arrowhead=2,
            arrowcolor="#00e676",
            arrowwidth=2,
            font=dict(size=11, color="#00e676"),
            bgcolor="rgba(0,230,118,0.15)",
            bordercolor="#00e676",
            borderpad=3,
            row=1, col=1,
        )

    # ── Row 2: RSI ─────────────────────────────────────────────────────────────
    if _RSI in df_plot.columns:
        rsi_vals = df_plot[_RSI].fillna(50)
        fig.add_trace(
            go.Scatter(
                x=df_plot.index,
                y=rsi_vals,
                name="RSI 14",
                line=dict(color="#c792ea", width=1.5),
                fill="tozeroy",
                fillcolor="rgba(199,146,234,0.08)",
            ),
            row=2, col=1,
        )
        for level, color, label in [
            (70, "rgba(239,83,80,0.5)",  "OB 70"),
            (50, "rgba(255,255,255,0.15)", "Mid 50"),
            (30, "rgba(0,230,118,0.5)",  "OS 30"),
        ]:
            fig.add_hline(y=level, line_color=color, line_dash="dash",
                          line_width=1, row=2, col=1,
                          annotation_text=label,
                          annotation_position="right",
                          annotation_font_size=10,
                          annotation_font_color=color)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        template=CHART_TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        height=CHART_HEIGHT,
        margin=dict(l=8, r=8, t=36, b=8),
        title=dict(
            text=f"<b>{symbol}</b>",
            font=dict(size=15, color="#e8ecf4"),
            x=0.01,
        ),
        legend=dict(
            orientation="h",
            x=0, y=1.02,
            font=dict(size=10, color="#8896ac"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis_rangeslider_visible=False,
        yaxis=dict(
            gridcolor="#1e2d45",
            zeroline=False,
            tickfont=dict(size=10, color="#8896ac"),
        ),
        yaxis2=dict(
            gridcolor="#1e2d45",
            zeroline=False,
            range=[0, 100],
            tickvals=[30, 50, 70],
            tickfont=dict(size=10, color="#8896ac"),
        ),
        xaxis2=dict(
            gridcolor="#1e2d45",
            tickfont=dict(size=10, color="#8896ac"),
        ),
    )
    return fig


def build_mini_sparkline(symbol: str, df: pd.DataFrame) -> go.Figure:
    """Compact close-price line for tooltips / thumbnails."""
    if df is None or df.empty:
        return _empty_chart("")

    prices = df["Close"].tail(30)
    color  = "#00e676" if prices.iloc[-1] >= prices.iloc[0] else "#ef5350"
    # Convert hex to rgba for fill transparency
    fill_map = {"#00e676": "rgba(0,230,118,0.1)", "#ef5350": "rgba(239,83,80,0.1)"}
    fill_clr = fill_map.get(color, "rgba(200,200,200,0.1)")

    fig = go.Figure(
        go.Scatter(
            y=prices.values,
            mode="lines",
            line=dict(color=color, width=1.5),
            fill="tozeroy",
            fillcolor=fill_clr,
        )
    )
    fig.update_layout(
        template=CHART_TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _add_demand_zone(fig: go.Figure, df: pd.DataFrame) -> None:
    """Shade the v67 demand zone (21-day low to 21-day low × DEMAND_ZONE_MULTIPLIER)."""
    if df.empty or len(df) < 5:
        return
    low21     = float(df["Low"].tail(21).min())
    zone_high = low21 * DEMAND_ZONE_MULTIPLIER
    # Semi-transparent green band
    fig.add_hrect(
        y0=low21, y1=zone_high,
        fillcolor="rgba(0,230,118,0.06)",
        line_width=0,
        row=1, col=1,
    )
    fig.add_hline(
        y=zone_high,
        line_color="rgba(0,230,118,0.35)",
        line_dash="dot",
        line_width=1,
        row=1, col=1,
        annotation_text="Demand Zone",
        annotation_position="right",
        annotation_font_size=9,
        annotation_font_color="rgba(0,230,118,0.6)",
    )


def _add_line(
    fig: go.Figure,
    df:  pd.DataFrame,
    col: str,
    name: str,
    color: str,
    width: float,
    row: int = 1,
    dash: str = "solid",
) -> None:
    if col not in df.columns:
        return
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df[col],
            name=name,
            line=dict(color=color, width=width, dash=dash),
            opacity=0.9,
        ),
        row=row, col=1,
    )


def _h_line(
    fig:   go.Figure,
    level: float,
    color: str,
    label: str,
    row:   int = 1,
    dash:  str = "dash",
) -> None:
    fig.add_hline(
        y=level,
        line_color=color,
        line_dash=dash,
        line_width=1,
        row=row, col=1,
        annotation_text=label,
        annotation_position="right",
        annotation_font_color=color,
        annotation_font_size=10,
    )


def _ensure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add missing MA / RSI columns using pandas if pandas_ta not available."""
    if _EMA21 not in df.columns:
        df[_EMA21] = df["Close"].ewm(span=21, adjust=False).mean()
    if _SMA50 not in df.columns:
        df[_SMA50] = df["Close"].rolling(50).mean()
    if _SMA200 not in df.columns:
        df[_SMA200] = df["Close"].rolling(200).mean()
    if _RSI not in df.columns:
        import numpy as np
        d        = df["Close"].diff()
        gain_avg = d.clip(lower=0).rolling(14).mean()
        loss_avg = (-d).clip(lower=0).rolling(14).mean()
        df[_RSI] = 100 - 100 / (1 + gain_avg / loss_avg.replace(0, np.nan))
    return df


def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message or "No data",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#8896ac"),
    )
    fig.update_layout(
        template=CHART_TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        height=CHART_HEIGHT,
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig
