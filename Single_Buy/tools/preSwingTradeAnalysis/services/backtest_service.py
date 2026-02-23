"""services/backtest_service.py — Walk-forward backtest of the v67 swing-trading strategy.

Logic mirrors rajat_alpha_v67_single.py exactly:
  Entry    : score >= 4 AND (touch_signal OR pattern) AND green-candle day
  Trailing : SL starts at -17%; tightens to -9% at +5% intraday high;
             tightens to -1% (near break-even) at +10% intraday high
  SL check : CLOSING price (closing_basis); execution at NEXT day's open
  Targets  : checked against INTRADAY HIGH; partial exits at T1/T2/T3 price
  Exit 1   : +10% (T1) — close 1/3 position at T1 target price
  Exit 2   : +15% (T2) — close 1/3 position at T2 target price
  Exit 3   : +20% (T3) — close final 1/3 position at T3 target price
  TES      : 21 calendar days max hold (configurable)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import (
    DEMAND_ZONE_MULTIPLIER,
    EMA21_PERIOD,
    MA_TOUCH_THRESHOLD_PCT,
    MIN_SIGNAL_SCORE,
    SMA50_PERIOD,
    SMA200_PERIOD,
    STOP_LOSS_PCT,
    TARGET_1_PCT,
    TARGET_2_PCT,
    TARGET_3_PCT,
    TIER1_PROFIT_PCT,
    TIER1_SL_PCT,
    TIER2_PROFIT_PCT,
    TIER2_SL_PCT,
    VOL_SMA_PERIOD,
)

logger = logging.getLogger(__name__)

# Strategy identifiers
STRATEGY_ALL     = "all"      # EMA21 Touch OR SMA50 Touch OR Pattern
STRATEGY_EMA21   = "ema21"    # EMA21 Touch entries only
STRATEGY_SMA50   = "sma50"    # SMA50 Touch entries only
STRATEGY_PATTERN = "pattern"  # Candlestick-pattern entries only

STRATEGY_LABELS = {
    STRATEGY_ALL:     "All Signals (EMA21 + SMA50 + Pattern)",
    STRATEGY_EMA21:   "EMA21 Touch Only",
    STRATEGY_SMA50:   "SMA50 Touch Only",
    STRATEGY_PATTERN: "Pattern Only (Engulfing / Piercing / Tweezer)",
}

# ─── Result Models ─────────────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    symbol:         str
    entry_date:     str
    entry_price:    float
    exit_date:      str       = ""
    exit_price:     float     = 0.0
    exit_reason:    str       = ""      # T1/T2/T3/SL/TES
    pnl_pct:        float     = 0.0     # overall realised P&L %
    score:          float     = 0.0
    pattern:        str       = ""
    signal_type:    str       = ""
    # Partial exits
    t1_exit:        bool      = False
    t2_exit:        bool      = False
    t3_exit:        bool      = False
    sl_hit:         bool      = False
    tes_exit:       bool      = False
    hold_days:      int       = 0
    max_drawdown_pct: float   = 0.0

    @property
    def is_winner(self) -> bool:
        return self.pnl_pct > 0


@dataclass
class BacktestSummary:
    symbol:         str
    total_trades:   int     = 0
    win_trades:     int     = 0
    loss_trades:    int     = 0
    win_rate:       float   = 0.0
    avg_pnl_pct:    float   = 0.0
    avg_win_pct:    float   = 0.0
    avg_loss_pct:   float   = 0.0
    max_win_pct:    float   = 0.0
    max_loss_pct:   float   = 0.0
    total_pnl_pct:  float   = 0.0
    avg_hold_days:  float   = 0.0
    t1_hit_rate:    float   = 0.0
    t2_hit_rate:    float   = 0.0
    t3_hit_rate:    float   = 0.0
    sl_rate:        float   = 0.0
    trades:         List[BacktestTrade] = field(default_factory=list)


@dataclass
class PortfolioBacktestResult:
    total_trades:   int     = 0
    win_trades:     int     = 0
    win_rate:       float   = 0.0
    avg_pnl_pct:    float   = 0.0
    total_pnl_pct:  float   = 0.0
    best_trade:     str     = ""
    worst_trade:    str     = ""
    best_trade_pct: float   = 0.0   # alias used by callback
    worst_trade_pct:float   = 0.0
    best_pnl:       float   = 0.0
    worst_pnl:      float   = 0.0
    strategy:       str     = STRATEGY_ALL
    per_symbol:     List[BacktestSummary] = field(default_factory=list)
    all_trades:     List[BacktestTrade]   = field(default_factory=list)
    equity_curve:   List[Dict]            = field(default_factory=list)  # [{date, equity}]


# ─── Core Engine ───────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Walk-forward backtest over 1 year of daily OHLCV.

    Usage
    -----
        engine = BacktestEngine()
        result = engine.run_portfolio({"AAPL": df_aapl, "MSFT": df_msft})
    """

    MAX_HOLD_DAYS = 21

    def __init__(self) -> None:
        pass

    # ── Portfolio ──────────────────────────────────────────────────────────────

    def run_portfolio(
        self,
        symbol_dfs: Dict[str, pd.DataFrame],
        lookback_days: int = 365,
        strategy: str = STRATEGY_ALL,
    ) -> PortfolioBacktestResult:
        """Run backtest for every symbol and aggregate results."""
        result = PortfolioBacktestResult(strategy=strategy)

        for symbol, df in symbol_dfs.items():
            if df is None or df.empty:
                continue
            try:
                summary = self.run_symbol(symbol, df, lookback_days, strategy=strategy)
                if summary.total_trades == 0:
                    continue
                result.per_symbol.append(summary)
                result.all_trades.extend(summary.trades)
            except Exception as exc:
                logger.warning("Backtest error for %s: %s", symbol, exc)

        if not result.all_trades:
            return result

        # Aggregate stats
        result.total_trades = len(result.all_trades)
        result.win_trades   = sum(1 for t in result.all_trades if t.is_winner)
        result.win_rate     = round(result.win_trades / result.total_trades * 100, 1)
        pnls                = [t.pnl_pct for t in result.all_trades]
        result.avg_pnl_pct  = round(float(np.mean(pnls)), 2)
        result.total_pnl_pct = round(float(np.sum(pnls)), 2)

        best  = max(result.all_trades, key=lambda t: t.pnl_pct)
        worst = min(result.all_trades, key=lambda t: t.pnl_pct)
        result.best_trade    = f"{best.symbol}  {best.entry_date}"
        result.best_trade_pct = best.pnl_pct
        result.best_pnl      = best.pnl_pct
        result.worst_trade   = f"{worst.symbol}  {worst.entry_date}"
        result.worst_trade_pct = worst.pnl_pct
        result.worst_pnl     = worst.pnl_pct

        # Equity curve (equal-weight, compound $1 per trade)
        result.equity_curve = self._equity_curve(result.all_trades)

        return result

    # ── Symbol ─────────────────────────────────────────────────────────────────

    def run_symbol(
        self,
        symbol:         str,
        df:             pd.DataFrame,
        lookback_days:  int = 365,
        strategy:       str = STRATEGY_ALL,
    ) -> "BacktestSummary":
        """Simulate all v67 trades for one symbol over the look-back period.

        Key execution model (mirrors rajat_alpha_v67_single.py):
          - Entry      : signal on bar i → entered at that bar's CLOSE
          - Targets    : checked against intraday HIGH → filled at target price
          - SL check   : closing price (closing_basis)
          - SL execute : NEXT BAR open (represents next-day market open fill)
          - Trailing SL: updated using intraday HIGH; tiers are +5% and +10%
                         relative to entry (NOT relative to T1/T2 partial exits)
        """
        df = df.copy()
        df = self._add_indicators(df)

        # Restrict to the recent look-back window; keep earlier bars for indicator warmup
        cutoff   = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
        df_window = df[df.index >= cutoff].copy()
        n         = len(df_window)

        trades: List[BacktestTrade] = []
        in_trade          = False
        entry_price       = 0.0
        entry_date        = ""
        score_at_entry    = 0.0
        pattern_at_entry  = ""
        signal_at_entry   = ""
        stop_level        = 0.0
        t1_level          = 0.0
        t2_level          = 0.0
        t3_level          = 0.0
        t1_hit = t2_hit   = False
        entry_idx         = 0
        min_low_during    = np.inf
        sl_triggered      = False   # SL hit on close → execute next open

        for i in range(50, n):  # need 50-bar warmup for indicators
            row       = df_window.iloc[i]
            close     = float(row["Close"])
            high      = float(row["High"])
            low       = float(row["Low"])
            date_str  = str(df_window.index[i].date())

            # ── Handle deferred SL execution (triggered on previous bar's close) ─
            if sl_triggered:
                # Execute at today's open (next bar after the closing SL trigger)
                open_price  = float(row["Open"])
                exit_price  = open_price
                exit_reason = "SL"
                # Compute weighted P&L for partial-exit scenario
                pnl = self._compute_pnl(
                    exit_price, entry_price, t1_hit, t2_hit, t1_level, t2_level
                )
                max_dd = round((min_low_during - entry_price) / entry_price * 100, 2)
                trades.append(BacktestTrade(
                    symbol           = symbol,
                    entry_date       = entry_date,
                    entry_price      = round(entry_price, 2),
                    exit_date        = date_str,
                    exit_price       = round(exit_price, 2),
                    exit_reason      = exit_reason,
                    pnl_pct          = pnl,
                    score            = score_at_entry,
                    pattern          = pattern_at_entry,
                    signal_type      = signal_at_entry,
                    t1_exit          = t1_hit,
                    t2_exit          = t2_hit,
                    t3_exit          = False,
                    sl_hit           = True,
                    tes_exit         = False,
                    hold_days        = i - entry_idx,
                    max_drawdown_pct = max_dd,
                ))
                in_trade     = False
                sl_triggered = False
                # Do NOT skip checking entry — position is gone, check today too

            if not in_trade:
                # ── Check entry ────────────────────────────────────────────
                sig, score, pattern, signal_type = self._check_entry(df_window, i, strategy=strategy)
                if sig:
                    in_trade          = True
                    entry_price       = close            # enter at today's close
                    entry_date        = date_str
                    score_at_entry    = score
                    pattern_at_entry  = pattern
                    signal_at_entry   = signal_type
                    stop_level        = round(entry_price * (1 - STOP_LOSS_PCT), 4)
                    t1_level          = round(entry_price * (1 + TARGET_1_PCT), 4)
                    t2_level          = round(entry_price * (1 + TARGET_2_PCT), 4)
                    t3_level          = round(entry_price * (1 + TARGET_3_PCT), 4)
                    t1_hit = t2_hit   = False
                    sl_triggered      = False
                    entry_idx         = i
                    min_low_during    = low
            else:
                # ── Manage open position ───────────────────────────────────
                min_low_during = min(min_low_during, low)
                hold_days      = i - entry_idx

                # 1. Update trailing SL based on intraday high (ratchets up only)
                #    Tiers are relative to entry price, triggered by intraday profit
                profit_at_high = (high - entry_price) / entry_price
                if profit_at_high >= TIER2_PROFIT_PCT:        # +10% intraday
                    new_sl = entry_price * (1 - TIER2_SL_PCT)  # 1% below entry
                elif profit_at_high >= TIER1_PROFIT_PCT:      # +5% intraday
                    new_sl = entry_price * (1 - TIER1_SL_PCT)  # 9% below entry
                else:
                    new_sl = entry_price * (1 - STOP_LOSS_PCT) # 17% below entry
                stop_level = max(stop_level, round(new_sl, 4))

                # 2. Check profit targets against INTRADAY HIGH (executed at target price)
                exit_reason = ""
                exit_price  = close

                if high >= t3_level and t1_hit and t2_hit:
                    exit_reason = "T3"
                    exit_price  = t3_level
                elif high >= t2_level and t1_hit and not t2_hit:
                    t2_hit = True       # partial exit at T2; stay open for T3
                elif high >= t1_level and not t1_hit:
                    t1_hit = True       # partial exit at T1; stay open for T2

                # 3. Check SL on CLOSING price (closing_basis → execute next open)
                if not exit_reason and close <= stop_level:
                    if i + 1 < n:
                        # Defer SL execution to next bar's open
                        sl_triggered = True
                    else:
                        # Last bar — close at today's close (no next-open available)
                        exit_reason = "SL"
                        exit_price  = close

                # 4. Time Exit Signal
                if not exit_reason and not sl_triggered and hold_days >= self.MAX_HOLD_DAYS:
                    exit_reason = "TES"
                    exit_price  = close

                if exit_reason and exit_reason != "SL_deferred":
                    pnl = self._compute_pnl(
                        exit_price, entry_price, t1_hit, t2_hit, t1_level, t2_level,
                        exit_reason, t3_level
                    )
                    max_dd = round((min_low_during - entry_price) / entry_price * 100, 2)
                    trades.append(BacktestTrade(
                        symbol           = symbol,
                        entry_date       = entry_date,
                        entry_price      = round(entry_price, 2),
                        exit_date        = date_str,
                        exit_price       = round(exit_price, 2),
                        exit_reason      = exit_reason,
                        pnl_pct          = pnl,
                        score            = score_at_entry,
                        pattern          = pattern_at_entry,
                        signal_type      = signal_at_entry,
                        t1_exit          = t1_hit,
                        t2_exit          = t2_hit,
                        t3_exit          = exit_reason == "T3",
                        sl_hit           = exit_reason == "SL",
                        tes_exit         = exit_reason == "TES",
                        hold_days        = hold_days,
                        max_drawdown_pct = max_dd,
                    ))
                    in_trade     = False
                    sl_triggered = False

        return self._summarise(symbol, trades)

    # ── P&L Helper ─────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_pnl(
        exit_price:   float,
        entry_price:  float,
        t1_hit:       bool,
        t2_hit:       bool,
        t1_level:     float,
        t2_level:     float,
        exit_reason:  str   = "",
        t3_level:     float = 0.0,
    ) -> float:
        """Weighted P&L accounting for partial 1/3 exits at T1, T2, T3."""
        ep = entry_price
        if exit_reason == "T3":
            # All three thirds exited at each target
            pnl = (
                (t1_level - ep) / ep * (1 / 3)
                + (t2_level - ep) / ep * (1 / 3)
                + (t3_level - ep) / ep * (1 / 3)
            ) * 100
        elif t1_hit and t2_hit:
            # T1 + T2 already banked, final third exits now
            pnl = (
                (t1_level  - ep) / ep * (1 / 3)
                + (t2_level - ep) / ep * (1 / 3)
                + (exit_price - ep) / ep * (1 / 3)
            ) * 100
        elif t1_hit:
            # Only T1 banked, two thirds exit now
            pnl = (
                (t1_level   - ep) / ep * (1 / 3)
                + (exit_price - ep) / ep * (2 / 3)
            ) * 100
        else:
            # Full position exits at exit_price
            pnl = (exit_price - ep) / ep * 100
        return round(pnl, 2)

    # ── Entry Conditions ───────────────────────────────────────────────────────

    def _check_entry(
        self, df: pd.DataFrame, i: int, strategy: str = STRATEGY_ALL
    ) -> Tuple[bool, float, str, str]:
        """
        Returns (signal, score, pattern, signal_type).
        Mirrors v67 logic: market structure + pullback/touch + score >= 4 + green.
        strategy: 'all' | 'ema21' | 'sma50' | 'pattern'
        """
        row = df.iloc[i]
        close = float(row["Close"])

        # Market structure: SMA50 > SMA200 and EMA21 >= SMA50 * 0.975
        sma50  = float(row.get("SMA50",  0) or 0)
        sma200 = float(row.get("SMA200", 0) or 0)
        ema21  = float(row.get("EMA21",  0) or 0)
        if sma50 <= sma200 or ema21 < sma50 * 0.975:
            return False, 0, "", ""

        # Green candle
        if close <= float(df.iloc[i - 1]["Close"]):
            return False, 0, "", ""

        # Touch signal
        signal_type = ""
        ema_dist = abs(close - ema21) / ema21 if ema21 > 0 else 1.0
        sma_dist = abs(close - sma50) / sma50 if sma50 > 0 else 1.0
        is_ema_touch = ema_dist <= MA_TOUCH_THRESHOLD_PCT
        is_sma_touch = sma_dist <= MA_TOUCH_THRESHOLD_PCT
        if is_ema_touch:
            signal_type = "EMA21_Touch"
        elif is_sma_touch:
            signal_type = "SMA50_Touch"

        # Pattern
        pattern = self._detect_pattern(df, i)

        # Apply strategy filter
        if strategy == STRATEGY_EMA21:
            if not is_ema_touch:
                return False, 0, "", ""
        elif strategy == STRATEGY_SMA50:
            if not is_sma_touch:
                return False, 0, "", ""
        elif strategy == STRATEGY_PATTERN:
            if not pattern:
                return False, 0, "", ""
        else:  # STRATEGY_ALL
            if not signal_type and not pattern:
                return False, 0, "", ""

        # Score
        score = self._compute_score(df, i, row)
        if score < MIN_SIGNAL_SCORE:
            return False, score, pattern, signal_type

        return True, score, pattern, signal_type

    def _detect_pattern(self, df: pd.DataFrame, i: int) -> str:
        """Lightweight pattern check (Engulfing, Piercing, Tweezer)."""
        if i < 1:
            return ""
        curr = df.iloc[i]
        prev = df.iloc[i - 1]
        c_o, c_c = float(curr["Open"]), float(curr["Close"])
        p_o, p_c = float(prev["Open"]), float(prev["Close"])

        is_green   = c_c > c_o
        prev_red   = p_c < p_o
        if not (is_green and prev_red):
            return ""

        # Engulfing
        if c_c >= p_o:
            return "Engulfing"

        # Piercing
        midpoint = (p_o + p_c) / 2
        if c_c > midpoint:
            rng = float(curr["High"]) - float(curr["Low"])
            body = c_c - c_o
            if rng > 0 and body / rng >= 0.40:
                return "Piercing"

        # Tweezer Bottom
        low_diff = abs(float(curr["Low"]) - float(prev["Low"]))
        if low_diff <= float(curr["Low"]) * 0.002:
            return "Tweezer"

        return ""

    def _compute_score(self, df: pd.DataFrame, i: int, row) -> float:
        """Simplified v67 score (base 5 components, no touch-count bonuses)."""
        score = 0.0
        close = float(row["Close"])

        rsi = float(row.get("RSI14", 0) or 0)
        if rsi > 50:
            score += 1

        w_ema21 = float(row.get("W_EMA21", 0) or 0)
        w_close = float(row.get("W_Close", 0) or 0)
        if w_ema21 > 0 and w_close > w_ema21:
            score += 1

        m_ema10 = float(row.get("M_EMA10", 0) or 0)
        m_close = float(row.get("M_Close", 0) or 0)
        if m_ema10 > 0 and m_close > m_ema10:
            score += 1

        vol     = float(row.get("Volume",   0) or 0)
        vol_sma = float(row.get("VOL_SMA21", 0) or 0)
        if vol_sma > 0 and vol > vol_sma:
            score += 1

        # Demand zone
        low21 = float(df["Low"].iloc[max(0, i - 21):i].min())
        if low21 > 0 and close <= low21 * DEMAND_ZONE_MULTIPLIER:
            score += 1

        # Touch bonus: always grant +1 if near MA (simplified, 1st touch only)
        ema21 = float(row.get("EMA21", 0) or 0)
        sma50 = float(row.get("SMA50", 0) or 0)
        ema_d = abs(close - ema21) / ema21 if ema21 > 0 else 1.0
        sma_d = abs(close - sma50) / sma50 if sma50 > 0 else 1.0
        if ema_d <= MA_TOUCH_THRESHOLD_PCT or sma_d <= MA_TOUCH_THRESHOLD_PCT:
            score += 1

        return score

    # ── Indicators ─────────────────────────────────────────────────────────────

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["EMA21"]    = df["Close"].ewm(span=EMA21_PERIOD, adjust=False).mean()
        df["SMA50"]    = df["Close"].rolling(SMA50_PERIOD).mean()
        df["SMA200"]   = df["Close"].rolling(SMA200_PERIOD).mean()
        df["VOL_SMA21"] = df["Volume"].rolling(VOL_SMA_PERIOD).mean()

        # RSI (14-period)
        delta = df["Close"].diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta).clip(lower=0).rolling(14).mean()
        df["RSI14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

        # Weekly close and weekly EMA21 (approximate via 5-day window)
        df["W_Close"] = df["Close"].rolling(5).mean()
        df["W_EMA21"] = df["W_Close"].ewm(span=21, adjust=False).mean()

        # Monthly close and monthly EMA10 (approximate via 21-day window)
        df["M_Close"] = df["Close"].rolling(21).mean()
        df["M_EMA10"] = df["M_Close"].ewm(span=10, adjust=False).mean()

        return df

    # ── Summary ────────────────────────────────────────────────────────────────

    def _summarise(self, symbol: str, trades: List[BacktestTrade]) -> BacktestSummary:
        s = BacktestSummary(symbol=symbol, trades=trades)
        if not trades:
            return s

        s.total_trades = len(trades)
        pnls     = [t.pnl_pct for t in trades]
        winners  = [t for t in trades if t.is_winner]
        losers   = [t for t in trades if not t.is_winner]

        s.win_trades   = len(winners)
        s.loss_trades  = len(losers)
        s.win_rate     = round(len(winners) / len(trades) * 100, 1)
        s.avg_pnl_pct  = round(float(np.mean(pnls)), 2)
        s.total_pnl_pct = round(float(np.sum(pnls)), 2)
        s.avg_win_pct  = round(float(np.mean([t.pnl_pct for t in winners])), 2) if winners else 0.0
        s.avg_loss_pct = round(float(np.mean([t.pnl_pct for t in losers])),  2) if losers  else 0.0
        s.max_win_pct  = round(max(pnls), 2)
        s.max_loss_pct = round(min(pnls), 2)
        s.avg_hold_days = round(float(np.mean([t.hold_days for t in trades])), 1)
        s.t1_hit_rate  = round(sum(1 for t in trades if t.t1_exit) / len(trades) * 100, 1)
        s.t2_hit_rate  = round(sum(1 for t in trades if t.t2_exit) / len(trades) * 100, 1)
        s.t3_hit_rate  = round(sum(1 for t in trades if t.t3_exit) / len(trades) * 100, 1)
        s.sl_rate      = round(sum(1 for t in trades if t.sl_hit)  / len(trades) * 100, 1)
        return s

    # ── Equity Curve ───────────────────────────────────────────────────────────

    def _equity_curve(self, trades: List[BacktestTrade]) -> List[Dict]:
        """Simulated $10k portfolio,  1 trade at a time, equal size."""
        if not trades:
            return []
        sorted_trades = sorted(trades, key=lambda t: t.entry_date)
        equity = 10_000.0
        curve  = [{"date": sorted_trades[0].entry_date, "equity": round(equity, 2)}]
        for t in sorted_trades:
            equity *= (1 + t.pnl_pct / 100)
            curve.append({"date": t.exit_date, "equity": round(equity, 2)})
        return curve
