"""
services/data_fetcher.py — Market data retrieval with TTL cache.

Single Responsibility: Downloads OHLCV bars + ticker metadata from yfinance.
Open/Closed: Override `fetch_one` in a subclass to swap the data provider.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from config import (
    CACHE_TTL_SECONDS,
    DATA_INTERVAL,
    DATA_PERIOD,
    FETCH_TIMEOUT_SECONDS,
    MAX_FETCH_WORKERS,
    NEWS_CACHE_HOURS,
)

logger = logging.getLogger(__name__)

# Type alias for the per-symbol result tuple
RawData = Tuple[pd.DataFrame, dict, list]


# ─── Cache Entry ───────────────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    df:           pd.DataFrame
    info:         dict
    news:         list
    calendar:     Optional[dict]
    created:      float = field(default_factory=time.time)
    news_fetched: float = field(default_factory=time.time)  # separate news timestamp

    def is_expired(self, ttl: float) -> bool:
        return (time.time() - self.created) > ttl

    def news_is_stale(self) -> bool:
        """News is refreshed at most once per NEWS_CACHE_HOURS."""
        return (time.time() - self.news_fetched) > (NEWS_CACHE_HOURS * 3600)


# ─── Fetcher ───────────────────────────────────────────────────────────────────

class MarketDataFetcher:
    """
    Downloads daily OHLCV data for one or many symbols, caching results for
    `CACHE_TTL_SECONDS` seconds to avoid redundant API calls.
    """

    def __init__(self, ttl: int = CACHE_TTL_SECONDS) -> None:
        self._cache: Dict[str, _CacheEntry] = {}
        self._ttl = ttl

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch_one(
        self,
        symbol: str,
        force: bool = False,
    ) -> Tuple[pd.DataFrame, dict, list, Optional[dict]]:
        """
        Returns (daily_df, info_dict, news_list, calendar_dict).

        *daily_df* columns: Open, High, Low, Close, Volume (tz-naive NYC time).
        Returns empty DataFrame on failure (never raises).
        """
        if not force and symbol in self._cache:
            entry = self._cache[symbol]
            if not entry.is_expired(self._ttl):
                return entry.df, entry.info, entry.news, entry.calendar

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                period=DATA_PERIOD,
                interval=DATA_INTERVAL,
                auto_adjust=True,
                timeout=FETCH_TIMEOUT_SECONDS,
            )
            if df.empty:
                logger.warning("%s: empty data returned (possibly delisted) — caching as error", symbol)
                error_entry = _CacheEntry(df=pd.DataFrame(), info={}, news=[], calendar=None,
                                          created=time.time() - (self._ttl - 300))
                self._cache[symbol] = error_entry
                return pd.DataFrame(), {}, [], None

            if df.index.tzinfo is not None:
                df.index = df.index.tz_convert("America/New_York").tz_localize(None)

            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

            info     = ticker.info or {}
            calendar = None
            try:
                calendar = ticker.calendar
                if hasattr(calendar, "to_dict"):
                    calendar = calendar.to_dict()
            except Exception:
                pass

            # ── News: only fetch if not cached or stale (1-hour TTL) ──────────────
            existing = self._cache.get(symbol)
            if existing and not existing.news_is_stale():
                news           = existing.news
                news_ts        = existing.news_fetched
            else:
                try:
                    news = ticker.news or []
                    logger.debug("%s: fetched %d news items", symbol, len(news))
                except Exception:
                    news = []
                news_ts = time.time()

            entry = _CacheEntry(
                df=df, info=info, news=news, calendar=calendar,
                news_fetched=news_ts,
            )
            self._cache[symbol] = entry
            return df, info, news, calendar

        except Exception as exc:
            logger.error("%s: fetch failed — %s", symbol, exc)
            # Cache failures so a broken/delisted symbol doesn't block every refresh.
            error_entry = _CacheEntry(df=pd.DataFrame(), info={}, news=[], calendar=None,
                                      created=time.time() - (self._ttl - 300))
            self._cache[symbol] = error_entry
            return pd.DataFrame(), {}, [], None

    def fetch_many(
        self,
        symbols: List[str],
        force: bool = False,
    ) -> Dict[str, Tuple[pd.DataFrame, dict, list, Optional[dict]]]:
        """
        Parallel fetch for a list of symbols.  Returns a dict keyed by symbol.

        Phase 1: Bulk-download OHLCV for all uncached symbols in a single
                 yf.download() call (one HTTP request for all tickers).
        Phase 2: Parallel per-symbol metadata (info, news, calendar) via threads.
        """
        results: Dict[str, Tuple] = {}

        # Serve fresh cache hits immediately
        to_fetch = []
        for sym in symbols:
            if not force and sym in self._cache and not self._cache[sym].is_expired(self._ttl):
                e = self._cache[sym]
                results[sym] = (e.df, e.info, e.news, e.calendar)
            else:
                to_fetch.append(sym)

        if not to_fetch:
            return results

        logger.info("Fetching %d symbols (workers=%d)", len(to_fetch), MAX_FETCH_WORKERS)

        # ── Phase 1: Bulk OHLCV download (single HTTP batch) ─────────────────
        bulk_dfs: Dict[str, pd.DataFrame] = {}
        try:
            raw = yf.download(
                to_fetch,
                period=DATA_PERIOD,
                interval=DATA_INTERVAL,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                timeout=FETCH_TIMEOUT_SECONDS,
            )
            if raw is not None and not raw.empty:
                if len(to_fetch) == 1:
                    # Single symbol: no multi-level columns
                    sym = to_fetch[0]
                    df = raw.copy()
                    if df.index.tzinfo is not None:
                        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
                    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                    if cols:
                        bulk_dfs[sym] = df[cols].dropna()
                else:
                    for sym in to_fetch:
                        try:
                            if sym in raw.columns.get_level_values(0):
                                df = raw[sym].copy()
                                df = df.dropna(how="all")
                                if df.index.tzinfo is not None:
                                    df.index = df.index.tz_convert("America/New_York").tz_localize(None)
                                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                                if cols and not df[cols].dropna().empty:
                                    bulk_dfs[sym] = df[cols].dropna()
                        except Exception as e:
                            logger.debug("%s: bulk parse failed — %s", sym, e)
            logger.info("Bulk download returned data for %d/%d symbols", len(bulk_dfs), len(to_fetch))
        except Exception as exc:
            logger.warning("Bulk download failed, falling back to per-symbol: %s", exc)

        # ── Phase 2: Parallel per-symbol metadata ────────────────────────────
        def _fetch_metadata(sym: str) -> Tuple[str, pd.DataFrame, dict, list, Optional[dict]]:
            """Fetch info/news/calendar; use bulk OHLCV if available."""
            df = bulk_dfs.get(sym)
            if df is None or df.empty:
                # Fallback: individual download
                return (sym, *self.fetch_one(sym, force=True))

            try:
                ticker = yf.Ticker(sym)
                info = ticker.info or {}

                calendar = None
                try:
                    calendar = ticker.calendar
                    if hasattr(calendar, "to_dict"):
                        calendar = calendar.to_dict()
                except Exception:
                    pass

                existing = self._cache.get(sym)
                if existing and not existing.news_is_stale():
                    news    = existing.news
                    news_ts = existing.news_fetched
                else:
                    try:
                        news = ticker.news or []
                    except Exception:
                        news = []
                    news_ts = time.time()

                entry = _CacheEntry(
                    df=df, info=info, news=news, calendar=calendar,
                    news_fetched=news_ts,
                )
                self._cache[sym] = entry
                return sym, df, info, news, calendar
            except Exception as exc:
                logger.error("%s: metadata fetch failed — %s", sym, exc)
                return sym, df, {}, [], None

        with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as executor:
            futures = {executor.submit(_fetch_metadata, sym): sym for sym in to_fetch}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    s, df, info, news, cal = future.result(timeout=FETCH_TIMEOUT_SECONDS + 10)
                    results[s] = (df, info, news, cal)
                except Exception as exc:
                    logger.error("%s: parallel fetch failed — %s", sym, exc)
                    results[sym] = (pd.DataFrame(), {}, [], None)

        return results

    def get_cached_df(self, symbol: str) -> Optional[pd.DataFrame]:
        """Return the cached DataFrame for a symbol (for charting)."""
        entry = self._cache.get(symbol)
        if entry and not entry.is_expired(self._ttl):
            return entry.df
        return None

    def clear(self) -> None:
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)
