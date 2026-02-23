"""
services/technical_analyzer.py — Indicator computation & market-state classification.

Single Responsibility : Derives all technical levels from OHLCV data.
Open / Closed         : Add indicators in _compute_indicators without editing
                        the callers (_determine_market_state, _detect_pattern …).
Liskov Substitution   : Subclasses can override individual detection methods.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta  # type: ignore
    _HAS_TA = True
except ImportError:
    _HAS_TA = False

from config import (
    CHOPPY_VOLATILITY_THRESHOLD,
    DEMAND_ZONE_MULTIPLIER,
    MA_TOUCH_THRESHOLD_PCT,
    STALLING_DAYS_LONG,
    STALLING_RANGE_PCT,
    STRONG_MOMENTUM_PCT,
)
from models import MarketState, TechnicalLevels

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Accepts a raw daily OHLCV DataFrame and returns all technical analysis
    results needed by SignalScorer and the dashboard.
    """

    # ── Entry Point ────────────────────────────────────────────────────────────

    def analyze(
        self, df: pd.DataFrame
    ) -> Tuple[MarketState, TechnicalLevels, Dict]:
        """
        Returns
        -------
        (market_state, tech_levels, extras)

        extras keys: pattern, breakout_signal, weekly_ok, monthly_ok,
                     touch_signal, touch_count, weekly_range_pct,
                     monthly_range_pct, support, resistance, is_stalling
        """
        if df is None or len(df) < 60:
            logger.debug("Insufficient bars for analysis (%d)", len(df) if df is not None else 0)
            return MarketState.SIDEWAYS, TechnicalLevels(), {}

        df = self._compute_indicators(df.copy())
        levels = self._extract_levels(df)

        weekly_df  = self._resample(df, "W-FRI", "EMA_21_W",  21,  kind="ema")
        monthly_df = self._resample(df, "ME",    "EMA_10_M",  10,  kind="ema")
        weekly_ok  = self._check_above_ma(weekly_df,  "EMA_21_W")
        monthly_ok = self._check_above_ma(monthly_df, "EMA_10_M")

        market_state  = self._determine_market_state(df, levels)
        pattern       = self._detect_pattern(df)
        breakout      = self._detect_breakout(df, levels)
        touch_info    = self._detect_touch(df, levels)
        range_data    = self._range_data(df)
        support, res  = self._support_resistance(df)
        is_stalling   = self._is_stalling(df)

        extras = {
            "pattern":          pattern,
            "breakout_signal":  breakout,
            "weekly_ok":        weekly_ok,
            "monthly_ok":       monthly_ok,
            "touch_signal":     touch_info["signal"],
            "touch_count":      touch_info["count"],
            "weekly_range_pct": range_data["weekly"],
            "monthly_range_pct": range_data["monthly"],
            "support":          support,
            "resistance":       res,
            "is_stalling":      is_stalling,
        }
        return market_state, levels, extras

    # ── Indicator Computation ─────────────────────────────────────────────────

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if _HAS_TA:
            df.ta.ema(length=21,  append=True)
            df.ta.sma(length=50,  append=True)
            df.ta.sma(length=200, append=True)
            df.ta.rsi(length=14,  append=True)
            df.ta.atr(length=14,  append=True)
            df.ta.atr(length=21,  append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            df.ta.bbands(length=20, std=2, append=True)
        else:
            # Fallback using pure pandas when pandas_ta is unavailable
            df["EMA_21"]   = df["Close"].ewm(span=21,  adjust=False).mean()
            df["SMA_50"]   = df["Close"].rolling(50).mean()
            df["SMA_200"]  = df["Close"].rolling(200).mean()
            d = df["Close"].diff()
            gain_avg = d.clip(lower=0).rolling(14).mean()
            loss_avg = (-d).clip(lower=0).rolling(14).mean()
            df["RSI_14"]   = 100 - 100 / (1 + gain_avg / loss_avg.replace(0, np.nan))
            # True Range for ATR (proper: max of three ranges)
            prev_close = df["Close"].shift(1)
            tr = pd.concat([
                df["High"] - df["Low"],
                (df["High"] - prev_close).abs(),
                (df["Low"]  - prev_close).abs(),
            ], axis=1).max(axis=1)
            df["ATRr_14"]  = tr.rolling(14).mean()
            df["ATRr_21"]  = tr.rolling(21).mean()
            # Simple MACD
            ema12 = df["Close"].ewm(span=12, adjust=False).mean()
            ema26 = df["Close"].ewm(span=26, adjust=False).mean()
            df["MACD_12_26_9"]  = ema12 - ema26
            df["MACDs_12_26_9"] = df["MACD_12_26_9"].ewm(span=9, adjust=False).mean()
            df["MACDh_12_26_9"] = df["MACD_12_26_9"] - df["MACDs_12_26_9"]
            # BB
            mid = df["Close"].rolling(20).mean()
            std = df["Close"].rolling(20).std()
            df["BBU_20_2.0"] = mid + 2 * std
            df["BBM_20_2.0"] = mid
            df["BBL_20_2.0"] = mid - 2 * std

        df["VOL_SMA_21"] = df["Volume"].rolling(21).mean()
        return df

    def _extract_levels(self, df: pd.DataFrame) -> TechnicalLevels:
        t = TechnicalLevels()
        last = df.iloc[-1]

        def _col(prefix: str) -> Optional[str]:
            return next((c for c in df.columns if c.startswith(prefix)), None)

        t.ema21  = _safe(df, "EMA_21")
        t.sma50  = _safe(df, "SMA_50")
        t.sma200 = _safe(df, "SMA_200")
        t.rsi    = _safe(df, "RSI_14", default=50.0)
        t.atr    = _safe(df, "ATRr_14")
        t.atr21  = _safe(df, "ATRr_21")

        price = float(last["Close"])
        t.atr_pct = (t.atr / price * 100) if (t.atr and price) else 0.0

        vsma = _safe(df, "VOL_SMA_21", default=1.0)
        t.vol_sma21    = vsma
        t.volume_ratio = float(last["Volume"]) / vsma if vsma else 1.0

        # MACD (pandas_ta names: MACD_12_26_9, MACDh_, MACDs_)
        mc  = _col("MACD_12_26_9") or _col("MACD_")
        mch = _col("MACDh_")
        mcs = _col("MACDs_")
        if mc:  t.macd        = _safe(df, mc)
        if mch: t.macd_hist   = _safe(df, mch)
        if mcs: t.macd_signal = _safe(df, mcs)

        # BB
        bbu = _col("BBU_")
        bbm = _col("BBM_")
        bbl = _col("BBL_")
        if bbu: t.bb_upper = _safe(df, bbu)
        if bbm: t.bb_mid   = _safe(df, bbm)
        if bbl: t.bb_lower = _safe(df, bbl)

        # 52-week from rolling 252 trading days
        tail = df["Close"].tail(252)
        t.week52_high = float(tail.max())
        t.week52_low  = float(tail.min())

        return t

    # ── Multi-Timeframe ───────────────────────────────────────────────────────

    def _resample(
        self, df: pd.DataFrame, rule: str, ma_col: str, period: int, kind: str = "ema"
    ) -> pd.DataFrame:
        resampled = df.resample(rule).agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        ).dropna()
        if kind == "ema":
            resampled[ma_col] = resampled["Close"].ewm(span=period, adjust=False).mean()
        else:
            resampled[ma_col] = resampled["Close"].rolling(period).mean()
        return resampled

    def _check_above_ma(self, df: pd.DataFrame, ma_col: str) -> bool:
        if df is None or len(df) < 5 or ma_col not in df.columns:
            return False
        return float(df["Close"].iloc[-1]) > float(df[ma_col].iloc[-1])

    # ── Market State (7 states) ───────────────────────────────────────────────

    def _determine_market_state(
        self, df: pd.DataFrame, t: TechnicalLevels
    ) -> MarketState:
        price = float(df["Close"].iloc[-1])

        if not all([t.ema21, t.sma50, t.sma200]):
            return MarketState.SIDEWAYS

        sma50_above_200 = t.sma50  > t.sma200
        ema21_above_50  = t.ema21  > t.sma50
        price_above_21  = price    > t.ema21
        price_above_50  = price    > t.sma50
        price_above_200 = price    > t.sma200

        recent    = df["Close"].tail(10).pct_change().dropna()
        momentum  = float(recent.mean())
        volatility = float(recent.std())

        # ──────────────────────────────────────────────────────────────────────
        # 1. Strong Uptrend: full MA stack + positive momentum + RSI confirms
        if sma50_above_200 and ema21_above_50 and price_above_21 and t.rsi > 55:
            if momentum > STRONG_MOMENTUM_PCT:
                return MarketState.STRONG_UPTREND
            return MarketState.UPTREND

        # 2. Pullback Setup: uptrend structure intact, price pulling toward key MA
        if sma50_above_200 and price_above_200:
            near_ema21 = abs(price - t.ema21) / t.ema21 <= MA_TOUCH_THRESHOLD_PCT
            near_sma50 = abs(price - t.sma50) / t.sma50 <= MA_TOUCH_THRESHOLD_PCT
            below_21_above_50 = (price < t.ema21) and (price > t.sma50 * 0.97)
            if near_ema21 or near_sma50 or below_21_above_50:
                return MarketState.PULLBACK_SETUP
            if price_above_21:
                return MarketState.UPTREND

        # 3. Choppy: high vol, no clear trend structure
        if volatility > CHOPPY_VOLATILITY_THRESHOLD and not sma50_above_200:
            return MarketState.CHOPPY

        # 4. Strong Downtrend
        if not price_above_200 and not sma50_above_200 and momentum < -STRONG_MOMENTUM_PCT:
            return MarketState.STRONG_DOWNTREND

        # 5. Downtrend
        if not sma50_above_200 or not price_above_50:
            return MarketState.DOWNTREND

        return MarketState.SIDEWAYS

    # ── Pattern Detection (mirrors v67 PatternDetector) ───────────────────────

    def _detect_pattern(self, df: pd.DataFrame) -> str:
        if len(df) < 3:
            return ""
        if self._is_engulfing(df):      return "Engulfing"
        if self._is_piercing(df):       return "Piercing"
        if self._is_tweezer_bottom(df): return "Tweezer Bottom"
        if self._is_morning_star(df):   return "Morning Star"
        return ""

    def _is_engulfing(self, df: pd.DataFrame) -> bool:
        c, p = df.iloc[-1], df.iloc[-2]
        if not (c["Close"] > c["Open"] and p["Close"] < p["Open"]):
            return False
        return c["Open"] <= p["Close"] and c["Close"] >= p["Open"]

    def _is_piercing(self, df: pd.DataFrame) -> bool:
        c, p = df.iloc[-1], df.iloc[-2]
        if not (c["Close"] > c["Open"] and p["Close"] < p["Open"]):
            return False
        mid = (p["Open"] + p["Close"]) / 2
        return c["Open"] < p["Close"] and c["Close"] > mid and c["Close"] < p["Open"]

    def _is_tweezer_bottom(self, df: pd.DataFrame) -> bool:
        c, p = df.iloc[-1], df.iloc[-2]
        if p["Low"] <= 0:
            return False
        return (
            abs(c["Low"] - p["Low"]) / p["Low"] < 0.003
            and c["Close"] > c["Open"]
        )

    def _is_morning_star(self, df: pd.DataFrame) -> bool:
        if len(df) < 3:
            return False
        c, m, pp = df.iloc[-1], df.iloc[-2], df.iloc[-3]
        big_red    = pp["Close"] < pp["Open"] and (pp["Open"] - pp["Close"]) > (pp["High"] - pp["Low"]) * 0.6
        small_body = abs(m["Close"] - m["Open"]) < (pp["Open"] - pp["Close"]) * 0.4
        green_recover = c["Close"] > c["Open"] and c["Close"] > (pp["Open"] + pp["Close"]) / 2
        return big_red and small_body and green_recover

    # ── Touch Signal ──────────────────────────────────────────────────────────

    def _detect_touch(self, df: pd.DataFrame, t: TechnicalLevels) -> Dict:
        price = float(df["Close"].iloc[-1])
        thresh = MA_TOUCH_THRESHOLD_PCT

        if t.ema21 and abs(price - t.ema21) / t.ema21 <= thresh:
            cnt = self._count_touches(df, "EMA_21", thresh)
            return {"signal": "EMA21_Touch", "count": cnt}

        if t.sma50 and abs(price - t.sma50) / t.sma50 <= thresh:
            cnt = self._count_touches(df, "SMA_50", thresh)
            return {"signal": "SMA50_Touch", "count": cnt}

        return {"signal": "", "count": 0}

    def _count_touches(self, df: pd.DataFrame, ma_col: str, thresh: float) -> int:
        if ma_col not in df.columns:
            return 0
        recent  = df.tail(40)
        prices  = recent["Close"].values
        ma_vals = recent[ma_col].fillna(0).values

        touches, in_touch = 0, False
        for px, ma in zip(prices, ma_vals):
            if ma == 0:
                continue
            if abs(px - ma) / ma <= thresh:
                if not in_touch:
                    touches  += 1
                    in_touch  = True
            else:
                in_touch = False
        return touches

    # ── Breakout Detection ────────────────────────────────────────────────────

    def _detect_breakout(self, df: pd.DataFrame, t: TechnicalLevels) -> str:
        price     = float(df["Close"].iloc[-1])
        vol_surge = t.volume_ratio >= 2.0
        suffix    = " + Vol Surge" if vol_surge else ""

        if t.week52_high and price >= t.week52_high * 0.99:
            return f"52W High Breakout{suffix}"

        three_mo_high = float(df["Close"].tail(65).max())
        if price >= three_mo_high * 0.99:
            return f"13W High{suffix}"

        if t.bb_upper and price > t.bb_upper:
            return "BB Upper Breakout"

        if "EMA_21" in df.columns and "SMA_50" in df.columns and len(df) > 2:
            prev_21 = float(df["EMA_21"].iloc[-2])
            prev_50 = float(df["SMA_50"].iloc[-2])
            if prev_21 < prev_50 and t.ema21 > t.sma50:
                return "EMA21 × SMA50 Crossover"

        if vol_surge:
            return "Volume Surge"

        return ""

    # ── Stalling ──────────────────────────────────────────────────────────────

    def _is_stalling(self, df: pd.DataFrame) -> bool:
        window = df["Close"].tail(STALLING_DAYS_LONG)
        if len(window) < STALLING_DAYS_LONG:
            return False
        rng = (window.max() - window.min()) / window.min()
        return bool(rng < STALLING_RANGE_PCT)

    # ── Range Analytics ───────────────────────────────────────────────────────

    def _range_data(self, df: pd.DataFrame) -> Dict:
        def _pct_range(sub: pd.DataFrame) -> float:
            lo = float(sub["Low"].min())
            if lo == 0:
                return 0.0
            return round((float(sub["High"].max()) - lo) / lo * 100, 2)

        return {
            "weekly":  _pct_range(df.tail(5)),
            "monthly": _pct_range(df.tail(21)),
        }

    # ── Support / Resistance ──────────────────────────────────────────────────

    def _support_resistance(self, df: pd.DataFrame) -> Tuple[float, float]:
        recent = df.tail(60)
        return (
            round(float(recent["Low"].nsmallest(5).mean()),  2),
            round(float(recent["High"].nlargest(5).mean()),  2),
        )


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _safe(df: pd.DataFrame, col: str, default: float = 0.0) -> float:
    """Return the last non-NaN value in *col*, or *default*."""
    if col not in df.columns:
        return default
    val = df[col].dropna()
    return float(val.iloc[-1]) if not val.empty else default
