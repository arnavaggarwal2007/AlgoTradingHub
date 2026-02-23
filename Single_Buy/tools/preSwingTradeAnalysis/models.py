"""
models.py — Data models for Pre-Swing Trade Analysis Dashboard.

All domain objects are plain dataclasses.  No framework dependencies here
(Open/Closed principle — add new fields without touching services).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ─── Market State ──────────────────────────────────────────────────────────────

class MarketState(Enum):
    """
    7-state classification of trend/momentum condition.
    Each value carries display metadata so the enum is the single source of truth.
    """
    STRONG_UPTREND   = ("Strong Uptrend",   "#00e676", "🚀", 7)
    UPTREND          = ("Uptrend",           "#00d4ff", "📈", 6)
    PULLBACK_SETUP   = ("Pullback Setup",    "#64b5f6", "🎯", 5)
    SIDEWAYS         = ("Sideways",          "#8896ac", "↔️",  4)
    CHOPPY           = ("Choppy",            "#ff9800", "🌊", 3)
    DOWNTREND        = ("Downtrend",         "#ef5350", "📉", 2)
    STRONG_DOWNTREND = ("Strong Downtrend",  "#b71c1c", "⬇️",  1)

    def __init__(self, label: str, color: str, icon: str, rank: int):
        self.label = label
        self.color = color
        self.icon  = icon
        self.rank  = rank

    @property
    def display(self) -> str:
        return f"{self.icon} {self.label}"


# ─── Sub-models ────────────────────────────────────────────────────────────────

@dataclass
class NewsItem:
    title:        str = ""
    publisher:    str = ""
    link:         str = ""
    published_ts: int = 0      # Unix timestamp
    sentiment:    str = "neutral"   # positive | negative | neutral

    @property
    def sentiment_icon(self) -> str:
        return {"positive": "📈", "negative": "⚠️", "neutral": "📰"}.get(self.sentiment, "📄")


@dataclass
class TechnicalLevels:
    ema21:        float = 0.0
    sma50:        float = 0.0
    sma200:       float = 0.0
    rsi:          float = 0.0
    volume_ratio: float = 0.0
    macd:         float = 0.0
    macd_signal:  float = 0.0
    macd_hist:    float = 0.0
    bb_upper:     float = 0.0
    bb_mid:       float = 0.0
    bb_lower:     float = 0.0
    atr:          float = 0.0
    atr_pct:      float = 0.0
    atr21:        float = 0.0
    vol_sma21:    float = 0.0
    week52_high:  float = 0.0
    week52_low:   float = 0.0


@dataclass
class ScoreBreakdown:
    rsi_bonus:         float = 0.0
    weekly_bonus:      float = 0.0
    monthly_bonus:     float = 0.0
    volume_bonus:      float = 0.0
    demand_zone_bonus: float = 0.0
    touch_bonus:       float = 0.0
    pattern_bonus:     float = 0.0
    total:             float = 0.0
    details:           str   = ""


# ─── Primary Domain Object ─────────────────────────────────────────────────────

@dataclass
class StockSignal:
    # Identity
    symbol:     str
    name:       str = ""
    sector:     str = "Unknown"
    industry:   str = "Unknown"

    # Price
    price:      float = 0.0
    prev_close: float = 0.0
    change_pct: float = 0.0
    volume:     int   = 0
    market_cap: float = 0.0

    # 52-Week
    week52_high:       float = 0.0
    week52_low:        float = 0.0
    pct_from_52w_high: float = 0.0
    pct_in_52w_range:  float = 0.0

    # Classification
    market_state: MarketState = MarketState.SIDEWAYS

    # Indicators
    technicals:      TechnicalLevels = field(default_factory=TechnicalLevels)
    score:           float            = 0.0
    score_breakdown: ScoreBreakdown   = field(default_factory=ScoreBreakdown)

    # Signal
    pattern:     str = ""
    signal_type: str = ""
    touch_count: int = 0

    # Trade Setup
    action:     str   = "Watch"
    entry_zone: str   = ""
    stop_loss:  float = 0.0
    target1:    float = 0.0
    target2:    float = 0.0
    target3:    float = 0.0
    risk_reward: float = 0.0

    # Earnings
    earnings_date:    str  = ""
    earnings_risk:    bool = False
    days_to_earnings: Optional[int] = None

    # News
    news_items:   List[NewsItem] = field(default_factory=list)
    news_summary: str            = ""

    # Context
    breakout_signal:   str   = ""
    weekly_range_pct:  float = 0.0
    monthly_range_pct: float = 0.0
    support_level:     float = 0.0
    resistance_level:  float = 0.0
    weekly_ok:         bool  = False
    monthly_ok:        bool  = False
    is_stalling:       bool  = False

    # Meta
    error:        str = ""
    last_updated: str = ""

    # ── Derived ────────────────────────────────────────────────────────────────

    def grade(self) -> str:
        if self.score >= 5:  return "A+"
        if self.score >= 4:  return "A"
        if self.score >= 3:  return "B"
        if self.score >= 2:  return "C"
        return "D"

    def is_valid(self) -> bool:
        return not self.error and self.price > 0

    # ── Serialisation (for Dash dcc.Store / AG Grid) ───────────────────────────

    def to_row(self) -> Dict[str, Any]:
        """Flat dict representation consumed by AG Grid rowData."""
        ms = self.market_state
        t  = self.technicals
        return {
            "symbol":           self.symbol,
            "name":             self.name,
            "sector":           self.sector,
            "industry":         self.industry,
            "market_state":     ms.display,
            "market_state_raw": ms.label,
            "market_state_rank": ms.rank,
            "state_color":      ms.color,
            "price":            round(self.price, 2),
            "change_pct":       round(self.change_pct, 2),
            "score":            round(self.score, 1),
            "grade":            self.grade(),
            "pattern":          self.pattern,
            "signal_type":      self.signal_type,
            "touch_count":      self.touch_count,
            "rsi":              round(t.rsi, 1),
            "ema21":            round(t.ema21, 2),
            "sma50":            round(t.sma50, 2),
            "sma200":           round(t.sma200, 2),
            "volume_ratio":     round(t.volume_ratio, 2),
            "pct_from_52w_high": round(self.pct_from_52w_high, 1),
            "pct_in_52w_range": round(self.pct_in_52w_range, 1),
            "atr_pct":          round(t.atr_pct, 1),
            "atr21":            round(t.atr21, 2),
            "macd_hist":        round(t.macd_hist, 3),
            "bb_pct":           round(
                ((self.price - t.bb_lower) / (t.bb_upper - t.bb_lower) * 100)
                if t.bb_upper > t.bb_lower else 50, 1
            ),
            "earnings_date":    self.earnings_date,
            "earnings_risk":    "⚠ YES" if self.earnings_risk else "—",
            "days_to_earnings": self.days_to_earnings if self.days_to_earnings is not None else "",
            "action":           self.action,
            "entry_zone":       self.entry_zone,
            "stop_loss":        round(self.stop_loss, 2),
            "target1":          round(self.target1, 2),
            "target2":          round(self.target2, 2),
            "target3":          round(self.target3, 2),
            "risk_reward":      round(self.risk_reward, 2),
            "breakout_signal":  self.breakout_signal,
            "news_summary":     self.news_summary,
            "weekly_ok":        "✓" if self.weekly_ok else "✗",
            "monthly_ok":       "✓" if self.monthly_ok else "✗",
            "score_tooltip":    self.score_breakdown.details,
            "market_cap_b":     round(self.market_cap / 1e9, 1) if self.market_cap else 0,
            "weekly_range_pct": round(self.weekly_range_pct, 1),
            "monthly_range_pct": round(self.monthly_range_pct, 1),
            "support":          round(self.support_level, 2),
            "resistance":       round(self.resistance_level, 2),
            "error":            self.error,
        }
