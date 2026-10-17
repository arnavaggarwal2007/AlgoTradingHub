"""
orchestrator.py — Analysis pipeline that wires all services together.

Single Responsibility : Orchestrates data flow: fetch → analyse → score → news.
Dependency Inversion  : All services injected via constructor.
Interface Segregation : Exposes only run_all() and run_one().
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from config import STOP_LOSS_PCT, TARGET_1_PCT, TARGET_2_PCT
from models import StockSignal
from services.data_fetcher    import MarketDataFetcher
from services.news_service    import NewsService
from services.signal_scorer   import SignalScorer
from services.technical_analyzer import TechnicalAnalyzer

logger = logging.getLogger(__name__)


class AnalysisOrchestrator:
    """
    Runs the full analysis pipeline for one or many symbols and returns
    a list of StockSignal objects ready for the dashboard.
    """

    def __init__(self) -> None:
        self._fetcher   = MarketDataFetcher()
        self._analyzer  = TechnicalAnalyzer()
        self._scorer    = SignalScorer()
        self._news_svc  = NewsService()

    # ── Public API ─────────────────────────────────────────────────────────────

    def run_all(self, symbols: List[str], force: bool = False) -> List[StockSignal]:
        """Analyse all symbols in parallel and return sorted signal list."""
        raw_data = self._fetcher.fetch_many(symbols, force=force)

        signals: List[StockSignal] = []
        for sym in symbols:
            df, info, news, cal = raw_data.get(sym, (pd.DataFrame(), {}, [], None))
            sig = self._build_signal(sym, df, info, news, cal)
            signals.append(sig)

        # Sort: Buy Setup first, then by score desc
        signals.sort(key=lambda s: (
            0 if s.action == "Buy Setup" else
            1 if s.action == "Watch"     else
            2 if s.action == "Wait"      else 3,
            -s.score,
            s.symbol,
        ))
        return signals

    def run_one(self, symbol: str, force: bool = False) -> StockSignal:
        df, info, news, cal = self._fetcher.fetch_one(symbol, force=force)
        return self._build_signal(symbol, df, info, news, cal)

    def get_cached_df(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._fetcher.get_cached_df(symbol)

    def cache_size(self) -> int:
        return self._fetcher.cache_size

    # ── Pipeline ───────────────────────────────────────────────────────────────

    def _build_signal(
        self,
        symbol:   str,
        df:       pd.DataFrame,
        info:     dict,
        raw_news: list,
        calendar,
    ) -> StockSignal:
        sig = StockSignal(symbol=symbol)

        if df is None or df.empty:
            sig.error = "No data"
            return sig

        try:
            # ── Identity (from yfinance info) ──────────────────────────────────
            sig.name       = info.get("longName", info.get("shortName", symbol))
            sig.sector     = info.get("sector",   "Unknown")
            sig.industry   = info.get("industry", "Unknown")
            sig.market_cap = float(info.get("marketCap", 0) or 0)

            # ── Price ──────────────────────────────────────────────────────────
            sig.price      = float(df["Close"].iloc[-1])
            sig.prev_close = float(df["Close"].iloc[-2]) if len(df) > 1 else sig.price
            sig.change_pct = (
                (sig.price - sig.prev_close) / sig.prev_close * 100
                if sig.prev_close else 0.0
            )
            sig.volume = int(df["Volume"].iloc[-1])

            # ── 52-Week ────────────────────────────────────────────────────────
            tail252 = df["Close"].tail(252)
            sig.week52_high = float(tail252.max())
            sig.week52_low  = float(tail252.min())
            rng = sig.week52_high - sig.week52_low
            sig.pct_from_52w_high = (
                (sig.price - sig.week52_high) / sig.week52_high * 100
                if sig.week52_high else 0.0
            )
            sig.pct_in_52w_range = (
                (sig.price - sig.week52_low) / rng * 100
                if rng else 0.0
            )

            # ── Technical Analysis ─────────────────────────────────────────────
            state, levels, extras = self._analyzer.analyze(df)
            sig.market_state    = state
            sig.technicals      = levels
            sig.weekly_ok       = extras.get("weekly_ok",       False)
            sig.monthly_ok      = extras.get("monthly_ok",      False)
            sig.breakout_signal = extras.get("breakout_signal", "")
            sig.weekly_range_pct  = extras.get("weekly_range_pct",  0.0)
            sig.monthly_range_pct = extras.get("monthly_range_pct", 0.0)
            sig.support_level   = extras.get("support",         0.0)
            sig.resistance_level = extras.get("resistance",     0.0)
            sig.is_stalling     = extras.get("is_stalling",     False)
            sig.pattern         = extras.get("pattern",         "")
            sig.signal_type     = extras.get("touch_signal",    "")
            sig.touch_count     = extras.get("touch_count",     0)

            # ── Signal Scoring ─────────────────────────────────────────────────
            score, breakdown, action = self._scorer.score(
                df           = df,
                t            = levels,
                market_state = state,
                weekly_ok    = sig.weekly_ok,
                monthly_ok   = sig.monthly_ok,
                pattern      = sig.pattern,
                touch_signal = sig.signal_type,
                touch_count  = sig.touch_count,
                is_stalling  = sig.is_stalling,
            )
            sig.score           = score
            sig.score_breakdown = breakdown
            sig.action          = action

            # ── Trade Levels ───────────────────────────────────────────────────
            entry_zone, stop, t1, t2, t3, rrr = self._scorer.compute_levels(sig.price, levels)
            sig.entry_zone  = entry_zone
            sig.stop_loss   = stop
            sig.target1     = t1
            sig.target2     = t2
            sig.target3     = t3
            sig.risk_reward = rrr

            # ── News & Earnings ────────────────────────────────────────────────
            sig.news_items  = self._news_svc.process(symbol, raw_news)
            sig.news_summary = self._news_svc.build_summary(sig.news_items)

            earn_date, earn_risk, days = self._news_svc.extract_earnings(calendar)
            sig.earnings_date    = earn_date
            sig.earnings_risk    = earn_risk
            sig.days_to_earnings = days

            sig.last_updated = datetime.now().strftime("%H:%M:%S")

        except Exception as exc:
            logger.error("%s analysis failed: %s", symbol, exc, exc_info=True)
            sig.error = str(exc)

        return sig
