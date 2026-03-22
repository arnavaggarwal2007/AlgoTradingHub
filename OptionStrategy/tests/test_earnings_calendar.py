"""
================================================================================
UNIT TESTS — Earnings Calendar (earnings_calendar.py)
================================================================================
"""

import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.earnings_calendar import EarningsCalendar


class TestEarningsCalendar:
    def test_manual_dates(self):
        cal = EarningsCalendar(manual_dates={'AAPL': ['2026-04-25']})
        dates = cal.get_earnings_dates('AAPL')
        assert dates == ['2026-04-25']

    def test_no_manual_dates(self):
        cal = EarningsCalendar(manual_dates={})
        dates = cal.get_earnings_dates('AAPL')
        assert dates == []

    def test_has_earnings_within_true(self):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        cal = EarningsCalendar(manual_dates={'AAPL': [tomorrow]})
        assert cal.has_earnings_within('AAPL', days=5) is True

    def test_has_earnings_within_false(self):
        far_future = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        cal = EarningsCalendar(manual_dates={'AAPL': [far_future]})
        assert cal.has_earnings_within('AAPL', days=5) is False

    def test_has_earnings_no_data(self):
        cal = EarningsCalendar(manual_dates={})
        assert cal.has_earnings_within('AAPL', days=5) is False

    def test_safe_expiration_no_conflict(self):
        cal = EarningsCalendar(manual_dates={'AAPL': ['2026-06-01']})
        assert cal.safe_expiration('AAPL', '2026-03-20') is True

    def test_safe_expiration_conflict(self):
        cal = EarningsCalendar(manual_dates={
            'AAPL': [(datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')]
        })
        exp = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        assert cal.safe_expiration('AAPL', exp, buffer_days=5) is False

    def test_safe_expiration_no_data(self):
        cal = EarningsCalendar(manual_dates={})
        assert cal.safe_expiration('UNKNOWN', '2026-03-20') is True

    def test_add_manual_date(self):
        cal = EarningsCalendar(manual_dates={})
        cal.add_manual_date('NVDA', '2026-05-28')
        assert '2026-05-28' in cal.get_earnings_dates('NVDA')

    def test_add_manual_date_no_duplicate(self):
        cal = EarningsCalendar(manual_dates={'NVDA': ['2026-05-28']})
        cal.add_manual_date('NVDA', '2026-05-28')
        assert len(cal.get_earnings_dates('NVDA')) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
