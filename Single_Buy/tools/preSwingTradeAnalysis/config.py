"""
config.py — Application-wide constants for Pre-Swing Trade Analysis Dashboard.

All tunable parameters live here so no magic numbers appear in business logic.
Strategy thresholds mirror the values in Single_Buy/config/config.json (v67).
"""
import os
from pathlib import Path

# ─── Paths ─────────────────────────────────────────────────────────────────────
APP_DIR            = Path(__file__).parent
PROJECT_ROOT       = APP_DIR.parent.parent          # …/Single_Buy
WATCHLIST_PATH     = Path(os.environ.get(
    "WATCHLIST_PATH",
    str(PROJECT_ROOT / "config" / "watchlist.txt"),
))
STRATEGY_CFG_PATH  = Path(os.environ.get(
    "STRATEGY_CFG_PATH",
    str(PROJECT_ROOT / "config" / "config.json"),
))

# ─── Application ───────────────────────────────────────────────────────────────
APP_TITLE       = "Pre-Swing Trade Analysis Dashboard"
APP_PORT        = 8050
DEBUG_MODE      = False
APP_VERSION     = "1.0.0"

# ─── Data Fetch ────────────────────────────────────────────────────────────────
DATA_PERIOD             = "2y"       # 2 years → ~500 bars; enough for SMA200 warmup
DATA_INTERVAL           = "1d"
CACHE_TTL_SECONDS       = 900        # 15-minute cache TTL
MAX_FETCH_WORKERS       = 12         # ThreadPoolExecutor size
FETCH_TIMEOUT_SECONDS   = 20         # Per-symbol timeout

# ─── UI Refresh ────────────────────────────────────────────────────────────────
REFRESH_INTERVAL_MS     = 900_000    # 15-minute auto-refresh
WATCHLIST_CHECK_MS      = 3_000      # Check watchlist file every 3 s

# ─── Technical Indicators ──────────────────────────────────────────────────────
EMA21_PERIOD    = 21
SMA50_PERIOD    = 50
SMA200_PERIOD   = 200
RSI_PERIOD      = 14
VOL_SMA_PERIOD  = 21
ATR_PERIOD      = 14
MACD_FAST       = 12
MACD_SLOW       = 26
MACD_SIG        = 9
BB_PERIOD       = 20
BB_STD          = 2.0

# ─── v67 Strategy Parameters (mirror config.json → strategy_params) ────────────
MIN_SIGNAL_SCORE            = 4       # Minimum score to flag as "Buy Setup"
MAX_GAP_PCT                 = 0.04    # 4% max intraday gap-up filter
PULLBACK_PCT                = 0.05    # 5% pullback detection range
MA_TOUCH_THRESHOLD_PCT      = 0.025   # 2.5% price-to-MA proximity for touch
DEMAND_ZONE_MULTIPLIER      = 1.035   # 21-day low × 1.035 = demand zone upper
STALLING_DAYS_LONG          = 8
STALLING_DAYS_SHORT         = 3
STALLING_RANGE_PCT          = 0.05

# ─── Risk Management (mirror config.json → risk_management) ───────────────────
STOP_LOSS_PCT   = 0.17    # Initial stop 17% below entry
TARGET_1_PCT    = 0.10    # First profit target (+10%)  — 1/3 position exit
TARGET_2_PCT    = 0.15    # Second profit target (+15%) — 1/3 position exit
TARGET_3_PCT    = 0.20    # Final target (+20%)         — remaining 1/3 exit

# Dynamic trailing-stop tiers (mirror config.json → risk_management)
TIER1_PROFIT_PCT  = 0.05  # At +5% profit  → tighten SL to 9% below entry
TIER1_SL_PCT      = 0.09  # SL = entry × (1 − 0.09)
TIER2_PROFIT_PCT  = 0.10  # At +10% profit → tighten SL to 1% below entry
TIER2_SL_PCT      = 0.01  # SL = entry × (1 − 0.01)  ← near break-even

INITIAL_CAPITAL = 10_000  # Default backtest starting capital ($)

# ─── Earnings Risk ─────────────────────────────────────────────────────────────
EARNINGS_WARNING_DAYS = 14   # Flag earnings risk if within 14 calendar days

# ─── Market State Thresholds ───────────────────────────────────────────────────
STRONG_MOMENTUM_PCT         = 0.005   # 0.5% avg daily return → "strong" prefix
CHOPPY_VOLATILITY_THRESHOLD = 0.018   # 1.8% daily std → "choppy"

# ─── Market Indices (for overview cards) ───────────────────────────────────────
MARKET_INDICES = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000", "^VIX": "VIX"}

# ─── Color Palette ─────────────────────────────────────────────────────────────
CLR_STRONG_UPTREND   = "#00e676"
CLR_UPTREND          = "#00d4ff"
CLR_PULLBACK         = "#64b5f6"
CLR_SIDEWAYS         = "#8896ac"
CLR_CHOPPY          = "#ff9800"
CLR_DOWNTREND        = "#ef5350"
CLR_STRONG_DOWNTREND = "#b71c1c"

CLR_BG_PRIMARY  = "#0a0e1a"
CLR_BG_CARD     = "#111827"
CLR_BG_HOVER    = "#1a2340"
CLR_ACCENT      = "#00d4ff"
CLR_TEXT_MAIN   = "#e8ecf4"
CLR_TEXT_DIM    = "#8896ac"
CLR_BORDER      = "#1e2d45"

# ─── Chart Settings ────────────────────────────────────────────────────────────
CHART_TEMPLATE  = "plotly_dark"
CHART_BG        = "#0d1117"
CHART_HEIGHT    = 460
CHART_BARS      = 65    # Show last 65 daily bars ≈ 3 calendar months

# ─── News ──────────────────────────────────────────────────────────────────────
NEWS_CACHE_HOURS   = 1     # Refresh news at most once per hour per symbol
NEWS_DISPLAY_COUNT = 8     # Headlines shown per symbol in news feed
