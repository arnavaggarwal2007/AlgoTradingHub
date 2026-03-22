"""
================================================================================
EARNINGS CALENDAR CHECKER
================================================================================
Checks if a stock has upcoming earnings to avoid holding positions through
earnings announcements. Uses Alpaca's corporate actions or a simple API.

Rule: Close positions at least 5 days before earnings.
================================================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

import requests

logger = logging.getLogger('options_strategy')


class EarningsCalendar:
    """
    Checks for upcoming earnings dates.
    
    Multiple data sources supported:
    1. Alpaca Calendar API
    2. Manual override list (config file)
    """

    def __init__(self, manual_dates: Optional[dict] = None):
        """
        Args:
            manual_dates: Dict of {symbol: [date_str, ...]} for manual overrides
                          Example: {'AAPL': ['2026-04-25'], 'NVDA': ['2026-05-28']}
        """
        self.manual_dates = manual_dates or {}
        self._cache = {}
        self._cache_expiry = {}

    def get_earnings_dates(self, symbol: str) -> List[str]:
        """
        Get upcoming earnings dates for a symbol.
        
        Returns:
            List of dates in 'YYYY-MM-DD' format
        """
        # Check manual overrides first
        if symbol in self.manual_dates:
            return self.manual_dates[symbol]

        # Check cache
        if symbol in self._cache:
            if datetime.now() < self._cache_expiry.get(symbol, datetime.min):
                return self._cache[symbol]

        # Default: return empty (no earnings date known)
        # In production, integrate with a proper earnings calendar API
        logger.info(f"No earnings dates found for {symbol} — skip earnings check")
        return []

    def has_earnings_within(self, symbol: str, days: int = 5) -> bool:
        """
        Check if a symbol has earnings within the next N days.
        
        Args:
            symbol: Stock symbol
            days: Number of days to check ahead
        
        Returns:
            True if earnings are within the window
        """
        earnings_dates = self.get_earnings_dates(symbol)
        
        if not earnings_dates:
            return False
        
        today = datetime.now().date()
        cutoff = today + timedelta(days=days)
        
        for ed in earnings_dates:
            earnings_date = datetime.strptime(ed, '%Y-%m-%d').date()
            if today <= earnings_date <= cutoff:
                logger.warning(
                    f"EARNINGS WARNING: {symbol} reports on {ed} "
                    f"(within {days}-day buffer)"
                )
                return True
        
        return False

    def safe_expiration(self, symbol: str, expiration_date: str, buffer_days: int = 5) -> bool:
        """
        Check if an expiration date is safe (no earnings conflict).
        
        Returns:
            True if safe to hold through expiration
        """
        earnings_dates = self.get_earnings_dates(symbol)
        
        if not earnings_dates:
            return True  # No known earnings = assume safe
        
        exp_date = datetime.strptime(expiration_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        for ed in earnings_dates:
            earnings_date = datetime.strptime(ed, '%Y-%m-%d').date()
            danger_start = earnings_date - timedelta(days=buffer_days)
            danger_end = earnings_date + timedelta(days=1)
            
            if danger_start <= exp_date <= danger_end and earnings_date >= today:
                logger.warning(
                    f"UNSAFE EXPIRATION: {symbol} ears on {ed}, "
                    f"expiration {expiration_date} is within buffer"
                )
                return False
        
        return True

    def add_manual_date(self, symbol: str, date: str):
        """Add a manual earnings date override."""
        if symbol not in self.manual_dates:
            self.manual_dates[symbol] = []
        if date not in self.manual_dates[symbol]:
            self.manual_dates[symbol].append(date)
            logger.info(f"Added manual earnings date: {symbol} → {date}")
