"""
services/news_service.py — Fetches, classifies, and summarises news items.

Single Responsibility: Only processes raw yfinance news payloads.
No data fetching here — raw_news and calendar are passed in from data_fetcher.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pandas as pd

from config import EARNINGS_WARNING_DAYS
from models import NewsItem

logger = logging.getLogger(__name__)

# ─── Sentiment Lexicon ─────────────────────────────────────────────────────────

_POSITIVE = frozenset({
    "beat", "beats", "topped", "exceeds", "exceed", "upgrade", "upgrades",
    "raised", "raises", "growth", "soar", "soars", "surge", "surges", "record",
    "strong", "profit", "profits", "gain", "gains", "outperform", "outperforms",
    "boost", "rose", "rise", "rises", "tops", "above", "positive", "recovery",
    "expands", "expansion", "buy", "overweight", "bull", "bullish",
    "breakthrough", "acquisition", "acquires", "dividend", "higher", "outlook",
})

_NEGATIVE = frozenset({
    "miss", "misses", "missed", "below", "downgrade", "downgrades", "cuts",
    "cut", "loss", "losses", "bear", "bearish", "drop", "drops", "weak",
    "concern", "concerns", "risk", "risks", "decline", "declines", "fall",
    "falls", "disappoint", "disappoints", "disappointing", "warning", "warn",
    "layoff", "layoffs", "restructure", "investigation", "recall", "debt",
    "sell", "reduce", "underperform", "overvalued", "headwinds", "tariff",
    "slowdown", "fraud", "lawsuit",
})

_EARNINGS_KEYWORDS = frozenset({
    "earnings", "quarterly", "results", "revenue", "eps", "guidance",
    "fiscal", "quarter", "profit", "outlook", "forecast",
})


class NewsService:
    """
    Processes raw yfinance news dicts into typed NewsItem objects and
    produces a one-line summary for the dashboard table cell.
    """

    # ── Public API ─────────────────────────────────────────────────────────────

    def process(self, symbol: str, raw_news: list) -> List[NewsItem]:
        """Convert raw yfinance news dicts → typed NewsItem list (most recent first).

        Handles two yfinance payload schemas:
          Legacy  : {title, publisher, link, providerPublishTime, ...}
          Modern  : {content: {title, provider: {displayName}, canonicalUrl: {url}, pubDate, ...}}
        """
        items: List[NewsItem] = []
        for item in raw_news[:15]:
            try:
                # ── Modern yfinance (0.2.50+) wraps everything in 'content' ──
                content  = item.get("content") or {}

                title     = (item.get("title")
                             or content.get("title", ""))
                publisher = (item.get("publisher")
                             or content.get("provider", {}).get("displayName", ""))
                link      = (item.get("link")
                             or content.get("canonicalUrl", {}).get("url", "")
                             or content.get("clickThroughUrl", {}).get("url", ""))

                # Timestamp: unix int (legacy) or ISO string (modern)
                raw_ts = (item.get("providerPublishTime")
                          or content.get("pubDate", ""))
                if isinstance(raw_ts, str) and raw_ts:
                    try:
                        ts = int(datetime.fromisoformat(
                            raw_ts.replace("Z", "+00:00")
                        ).timestamp())
                    except Exception:
                        ts = 0
                else:
                    ts = int(raw_ts) if raw_ts else 0

                if not title:
                    continue

                items.append(NewsItem(
                    title        = title,
                    publisher    = publisher,
                    link         = link,
                    published_ts = ts,
                    sentiment    = self._classify(title),
                ))
            except Exception as exc:
                logger.debug("%s news parse error: %s", symbol, exc)

        items.sort(key=lambda n: n.published_ts, reverse=True)
        return items

    def build_summary(self, items: List[NewsItem]) -> str:
        """One-line cell summary: surfacing negative first, then positive."""
        if not items:
            return "No recent news"

        neg = [i for i in items if i.sentiment == "negative"]
        pos = [i for i in items if i.sentiment == "positive"]
        top = (neg[:2] + pos[:1]) or items[:2]

        parts = [f"{h.sentiment_icon} {h.title[:70]}" for h in top]
        return "  |  ".join(parts)

    def extract_earnings(
        self,
        calendar_data,
        window_days: int = EARNINGS_WARNING_DAYS,
    ) -> Tuple[str, bool, Optional[int]]:
        """
        Parse yfinance calendar into (date_str, is_risk_flag, days_to_earnings).

        Handles both DataFrame and dict forms returned by ticker.calendar.
        """
        if calendar_data is None:
            return "", False, None

        earnings_ts = None

        try:
            # ── DataFrame form ─────────────────────────────────────────────────
            if isinstance(calendar_data, pd.DataFrame):
                for col in ("Earnings Date", "earnings_date"):
                    if col in calendar_data.columns:
                        earnings_ts = calendar_data[col].iloc[0]
                        break
                if earnings_ts is None and len(calendar_data.columns) > 0:
                    earnings_ts = calendar_data.iloc[0, 0]

            # ── Dict form ──────────────────────────────────────────────────────
            elif isinstance(calendar_data, dict):
                for key in ("Earnings Date", "earnings_date", "earningsDate"):
                    val = calendar_data.get(key)
                    if val:
                        earnings_ts = val[0] if isinstance(val, list) else val
                        break

            if earnings_ts is None:
                return "", False, None

            earnings_dt = pd.Timestamp(earnings_ts)
            now         = pd.Timestamp.now()
            delta_days  = (earnings_dt - now).days

            date_str = earnings_dt.strftime("%b %d")
            is_risk  = 0 <= delta_days <= window_days

            return date_str, is_risk, int(delta_days) if delta_days >= 0 else None

        except Exception as exc:
            logger.debug("Earnings parse error: %s", exc)
            return "", False, None

    # ── Internal ───────────────────────────────────────────────────────────────

    def _classify(self, text: str) -> str:
        words = set(text.lower().split())
        pos   = len(words & _POSITIVE)
        neg   = len(words & _NEGATIVE)
        if neg > pos:  return "negative"
        if pos > neg:  return "positive"
        return "neutral"
