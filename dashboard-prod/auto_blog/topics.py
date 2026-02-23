"""
auto_blog/topics.py

A curated bank of blog topics targeting high-traffic, low-competition
trading keywords that align with the Pre-Swing Trade dashboard.

Topics rotate weekly — Tuesdays and Fridays.
Each topic has:
  - SEO keyword
  - Structured sections (for the AI prompt)
  - Affiliate link slots
  - Category (WordPress category)
  - Target audience
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BlogTopic:
    title: str
    keyword: str
    secondary_keywords: List[str]
    sections: List[str]
    category: str
    audience: str = "intermediate swing traders"
    tone: str = "educational and actionable"
    section_4: Optional[str] = None
    affiliate_links: List[dict] = field(default_factory=list)


# ─── Topic Bank ───────────────────────────────────────────────────────────────

TOPIC_BANK: List[BlogTopic] = [

    # ── Technical Analysis ──
    BlogTopic(
        title="How to Use EMA 21 for Swing Trade Entries in 2025",
        keyword="EMA 21 swing trading",
        secondary_keywords=["exponential moving average", "swing trade entry", "ema crossover", "technical analysis stocks"],
        sections=["What Is EMA 21 and Why Traders Use It",
                  "How to Identify EMA 21 Touch Setups",
                  "Entry, Target, and Stop-Loss Rules",
                  "Backtesting EMA 21 Setups"],
        category="Technical Analysis",
        section_4="Backtesting EMA 21 Setups",
        affiliate_links=[{"placeholder": "BROKER_LINK_1", "url": "", "anchor_text": "Try Interactive Brokers"}],
    ),

    BlogTopic(
        title="SMA 50 vs EMA 21: Which Moving Average Should Swing Traders Use?",
        keyword="SMA 50 swing trading",
        secondary_keywords=["moving average comparison", "50-day moving average", "best MA for swing trading"],
        sections=["Understanding SMA vs EMA",
                  "When SMA 50 Signals a Buy",
                  "Real Trade Examples from 2024-2025"],
        category="Technical Analysis",
    ),

    BlogTopic(
        title="Demand Zone Trading: How to Buy Near Support for Maximum Reward",
        keyword="demand zone trading strategy",
        secondary_keywords=["support zone stocks", "supply demand trading", "buying at support", "reversal signals"],
        sections=["What Are Demand Zones?",
                  "How to Identify High-Probability Demand Zones",
                  "Risk Management at Demand Zones"],
        category="Technical Analysis",
    ),

    BlogTopic(
        title="RSI Divergence: The Setup Most Retail Traders Miss",
        keyword="RSI divergence swing trading",
        secondary_keywords=["relative strength index", "hidden divergence", "bullish divergence stocks", "rsi strategy"],
        sections=["Regular vs Hidden Divergence",
                  "How to Scan for RSI Divergence Setups",
                  "Entry and Exit Rules"],
        category="Technical Analysis",
    ),

    BlogTopic(
        title="Candlestick Patterns That Actually Work: A 2025 Backtested Guide",
        keyword="candlestick patterns swing trading",
        secondary_keywords=["engulfing candle", "morning star pattern", "piercing pattern", "bullish candles"],
        sections=["Top 5 Bullish Candlestick Patterns",
                  "Backtested Win Rates for Each",
                  "How to Filter for High-Quality Setups"],
        category="Technical Analysis",
    ),

    # ── Strategy ──
    BlogTopic(
        title="Swing Trading vs Day Trading: Which Is Better for Passive Income?",
        keyword="swing trading vs day trading",
        secondary_keywords=["passive income trading", "trading strategies 2025", "time commitment trading"],
        sections=["Time Commitment: Day vs Swing",
                  "Risk Profile and Capital Requirements",
                  "Why Swing Trading Suits Part-Time Traders"],
        category="Strategy",
    ),

    BlogTopic(
        title="The 3-Tier Profit-Taking System: How to Never Leave Money on the Table",
        keyword="profit taking strategy swing trading",
        secondary_keywords=["partial profits", "trailing stop loss", "scale out trading", "T1 T2 T3 targets"],
        sections=["Why Most Traders Exit Too Early or Too Late",
                  "The T1/T2/T3 Partial Exit System",
                  "Trailing Stop-Loss After T1"],
        category="Strategy",
    ),

    BlogTopic(
        title="Position Sizing for Swing Traders: Risk 1%, Win Big",
        keyword="position sizing swing trading",
        secondary_keywords=["risk management stocks", "1% rule trading", "trading capital allocation", "Kelly criterion"],
        sections=["The 1% Risk Rule Explained",
                  "How to Calculate Position Size",
                  "Compounding Returns with Consistent Sizing"],
        category="Risk Management",
    ),

    BlogTopic(
        title="How to Build a Swing Trading Watchlist: 5-Step Screening Process",
        keyword="swing trading watchlist",
        secondary_keywords=["stock screener", "swing trade setup", "watchlist criteria", "momentum stocks 2025"],
        sections=["Criteria for a High-Quality Watchlist",
                  "Using Scanners to Filter 5000+ Stocks",
                  "How the Pre-Swing Dashboard Automates This"],
        category="Strategy",
    ),

    BlogTopic(
        title="Understanding Market States: When to Trade and When to Stay Out",
        keyword="market state trading",
        secondary_keywords=["trending market", "sideways market", "choppy market trading", "market conditions"],
        sections=["7 Market States Every Trader Should Know",
                  "How to Identify the Current State",
                  "Adjusting Strategy for Each State"],
        category="Strategy",
    ),

    # ── Algorithmic / Automated ──
    BlogTopic(
        title="Algorithmic Swing Trading: Can a System Beat Manual Analysis?",
        keyword="algorithmic swing trading",
        secondary_keywords=["automated trading", "trading algorithm", "system trading", "backtesting strategy"],
        sections=["What Makes a Good Trading Algorithm",
                  "Backtesting vs Forward Testing",
                  "How the v67 Algorithm Was Designed"],
        category="Algorithmic Trading",
    ),

    BlogTopic(
        title="Stock Backtesting 101: How to Validate a Strategy Before Risking Money",
        keyword="stock backtesting strategy",
        secondary_keywords=["backtest trading strategy", "historical data testing", "strategy validation", "walk forward testing"],
        sections=["What Backtesting Is and Is Not",
                  "Common Backtesting Pitfalls",
                  "How to Read a Backtest Equity Curve"],
        category="Algorithmic Trading",
    ),

    BlogTopic(
        title="yFinance Python Tutorial: Pull Stock Data and Build Your Own Screener",
        keyword="yfinance python stock data",
        secondary_keywords=["python stock screener", "yfinance tutorial", "free stock api", "pandas stock analysis"],
        sections=["Getting Started with yFinance",
                  "Downloading OHLCV Data for 100+ Stocks",
                  "Building a Simple Moving Average Scanner"],
        category="Python & Coding",
        audience="Python developers interested in trading",
        tone="technical and educational",
    ),

    # ── Education ──
    BlogTopic(
        title="What Is a Pre-Swing Trade Setup? A Beginner's Complete Guide",
        keyword="pre-swing trade setup",
        secondary_keywords=["swing trade setup guide", "before entering a trade", "trade preparation checklist"],
        sections=["Definition: What Is a Pre-Swing Setup",
                  "5 Criteria Before Entering Any Trade",
                  "Common Mistakes Beginners Make"],
        category="Beginner Guide",
        audience="beginner retail traders",
        tone="simple, encouraging, educational",
    ),

    BlogTopic(
        title="Top 5 Free Stock Screeners for Swing Traders in 2025",
        keyword="free stock screener swing trading",
        secondary_keywords=["finviz free", "tradingview screener", "best stock scanner", "stock screener comparison"],
        sections=["What to Look for in a Screener",
                  "Top 5 Free Options Compared",
                  "How Our Dashboard Compares"],
        category="Tools & Resources",
    ),

    # ── Passive Income ──
    BlogTopic(
        title="Can Trading Really Generate Passive Income? A Realistic 2025 Guide",
        keyword="passive income trading stocks",
        secondary_keywords=["stock trading income", "semi-passive income", "systematic trading income", "trading as side income"],
        sections=["The Truth About Trading as Passive Income",
                  "Semi-Automated Trading: The Sweet Spot",
                  "Realistic Income Expectations by Capital Size"],
        category="Passive Income",
    ),

    BlogTopic(
        title="How I Built a Stock Scanning System That Saves 3 Hours a Day",
        keyword="stock scanning system",
        secondary_keywords=["automate stock scanning", "daily routine trading", "trading productivity", "pre-market preparation"],
        sections=["The Old Way: Manual Chart Review",
                  "The New Way: Automated Signal Dashboard",
                  "My Morning Routine with the Dashboard"],
        category="Passive Income",
        tone="personal, case-study style",
    ),
]


# ─── Scheduler ────────────────────────────────────────────────────────────────

def get_scheduled_topic() -> BlogTopic:
    """
    Returns the topic scheduled for today's posting.

    Posts are scheduled Tuesdays (day=1) and Fridays (day=4).
    Uses week-of-year and day-of-week to deterministically pick a topic.
    This way the same week always gets the same topics.
    """
    today = datetime.date.today()
    week  = today.isocalendar()[1]  # ISO week number: 1-52
    day   = today.weekday()         # Monday=0, Friday=4

    # Alternate between two topics per week
    # Tuesday picks even-indexed topics; Friday picks odd-indexed
    if day == 1:   # Tuesday
        idx = (week * 2) % len(TOPIC_BANK)
    else:          # Friday (or manual run)
        idx = (week * 2 + 1) % len(TOPIC_BANK)

    return TOPIC_BANK[idx]


def get_all_topics() -> List[BlogTopic]:
    return TOPIC_BANK
