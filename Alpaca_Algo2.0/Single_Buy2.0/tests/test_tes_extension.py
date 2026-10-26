import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from rajat_alpha_v67_single import (
    PositionManager,
    ConfigManager,
    PositionDatabase
)

@pytest.fixture
def mock_db():
    db = MagicMock(spec=PositionDatabase)
    db.get_days_held.return_value = 25  # Default: held for 25 days (>= base 21)
    db.grant_tes_extension.return_value = None
    return db

@pytest.fixture
def mock_config():
    cfg = MagicMock(spec=ConfigManager)
    cfg.get.side_effect = lambda group, key, default=None: {
        ('risk_management', 'max_hold_days'): 21,
        ('risk_management', 'tes_base_days'): 21,
        ('risk_management', 'tes_extension_days'): 10,
        ('risk_management', 'max_tes_extensions'): 2,
        ('risk_management', 'tes_max_extensions'): 2,
        ('risk_management', 'enable_dynamic_tes_extension'): True,
        ('first_hour_guard', 'suppress_sl'): True,
    }.get((group, key), default)
    return cfg

@pytest.fixture
def mock_trading_client():
    return MagicMock()

@pytest.fixture
def mock_data_fetcher():
    return MagicMock()

@pytest.fixture
def position_manager(mock_trading_client, mock_config, mock_db, mock_data_fetcher):
    return PositionManager(mock_trading_client, mock_config, mock_db, mock_data_fetcher)

def create_raw_daily_bars(n_bars=30, base_price=100.0, trend=0.5):
    """Generates raw daily bars from Alpaca (WITHOUT technical indicators like EMA21)"""
    dates = [datetime.now() - timedelta(days=n_bars - i) for i in range(n_bars)]
    closes = [base_price + (i * trend) for i in range(n_bars)]
    df = pd.DataFrame({
        'open': closes,
        'high': [c + 1.0 for c in closes],
        'low': [c - 1.0 for c in closes],
        'close': closes,
        'volume': [1000000] * n_bars,
        'trade_count': [5000] * n_bars,
        'vwap': closes
    }, index=dates)
    return df

class TestDynamicStructuralTES:
    
    def test_raw_bars_without_ema21_holding_above_ema(self, position_manager, mock_db):
        """
        FORENSIC REPRODUCTION:
        df contains raw Alpaca columns (NO 'EMA21').
        Price is trending upwards, holding firmly above 21 EMA.
        Verifies dynamic EMA21 calculation, extension granted, no KeyError, returns False.
        """
        raw_df = create_raw_daily_bars(n_bars=30, base_price=100.0, trend=1.0)
        assert 'EMA21' not in raw_df.columns, "Ensure EMA21 is NOT precalculated"
        
        position = {
            'id': 1,
            'symbol': 'ECPG',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        # Must NOT raise KeyError: 'EMA21'
        result = position_manager.check_time_exit(position, raw_df)
        
        # Holding above 21 EMA -> extension granted -> False (do not exit)
        assert result is False
        mock_db.grant_tes_extension.assert_called_once()
        assert position.get('tes_extensions_count') == 1

    def test_raw_bars_without_ema21_breaking_below_ema(self, position_manager, mock_db):
        """
        df contains raw Alpaca columns (NO 'EMA21').
        Price broke sharply below 21 EMA on the last bar.
        Verifies dynamic EMA21 calculation, no extension granted, returns True (TES exit triggered).
        """
        raw_df = create_raw_daily_bars(n_bars=30, base_price=100.0, trend=1.0)
        # Drop last bar close well below EMA21
        raw_df.iloc[-1, raw_df.columns.get_loc('close')] = 80.0
        assert 'EMA21' not in raw_df.columns
        
        position = {
            'id': 2,
            'symbol': 'ECPG',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        result = position_manager.check_time_exit(position, raw_df)
        assert result is True
        mock_db.grant_tes_extension.assert_not_called()

    def test_precalculated_ema21_respected(self, position_manager, mock_db):
        """Precalculated EMA21 is respected and not overwritten incorrectly"""
        raw_df = create_raw_daily_bars(n_bars=30, base_price=100.0, trend=1.0)
        raw_df['EMA21'] = 110.0  # Last close is ~129, so close > EMA21
        
        position = {
            'id': 3,
            'symbol': 'TIGO',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        result = position_manager.check_time_exit(position, raw_df)
        assert result is False
        mock_db.grant_tes_extension.assert_called_once()

    def test_none_df_handled_gracefully(self, position_manager, mock_db):
        """If df is None and data_fetcher returns None, safely returns True without crash"""
        position_manager.data_fetcher.get_daily_bars.return_value = None
        position = {
            'id': 4,
            'symbol': 'XYZ',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        result = position_manager.check_time_exit(position, None)
        assert result is True
        mock_db.grant_tes_extension.assert_not_called()

    def test_insufficient_bars_handled_gracefully(self, position_manager, mock_db):
        """If df has fewer than 21 bars (e.g. 10 bars), safely returns True without crash"""
        short_df = create_raw_daily_bars(n_bars=10, base_price=50.0)
        position = {
            'id': 5,
            'symbol': 'NEWIPO',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        result = position_manager.check_time_exit(position, short_df)
        assert result is True
        mock_db.grant_tes_extension.assert_not_called()

    def test_days_held_less_than_limit(self, position_manager, mock_db):
        """If position held fewer than 21 days, returns False immediately without touching df"""
        mock_db.get_days_held.return_value = 10  # 10 days < 21
        position = {
            'id': 6,
            'symbol': 'TIGO',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        # Even with None df or malformed df, it returns False immediately
        result = position_manager.check_time_exit(position, None)
        assert result is False

    def test_runner_mode_exempt_from_tes(self, position_manager, mock_db):
        """Runners (is_runner=1) are 100% exempt from TES, returning False immediately"""
        mock_db.get_days_held.return_value = 99  # Held 99 days
        position = {
            'id': 7,
            'symbol': 'RUNNER',
            'is_runner': 1,
            'tes_extensions_count': 0
        }
        
        result = position_manager.check_time_exit(position, None)
        assert result is False

    def test_max_extensions_cap_enforced(self, position_manager, mock_db):
        """Once max extensions (2) are reached and effective limit (41d) is crossed, triggers exit"""
        mock_db.get_days_held.return_value = 45  # Held 45 days > 21 + (2 * 10) = 41
        raw_df = create_raw_daily_bars(n_bars=30, base_price=100.0, trend=1.0)
        position = {
            'id': 8,
            'symbol': 'MATURE',
            'is_runner': 0,
            'tes_extensions_count': 2  # Already at max 2
        }
        
        result = position_manager.check_time_exit(position, raw_df)
        assert result is True
        mock_db.grant_tes_extension.assert_not_called()

    def test_nan_in_ema21_handled_safely(self, position_manager, mock_db):
        """If EMA21 is NaN on the last bar, does not crash and handles safely"""
        raw_df = create_raw_daily_bars(n_bars=30, base_price=100.0, trend=1.0)
        raw_df['EMA21'] = np.nan
        
        position = {
            'id': 9,
            'symbol': 'NANTEST',
            'is_runner': 0,
            'tes_extensions_count': 0
        }
        
        # When EMA21 is NaN, the code recalculates via ta.ema or ewm
        result = position_manager.check_time_exit(position, raw_df)
        # Recalculated cleanly and granted extension since trend > 0
        assert result is False
        mock_db.grant_tes_extension.assert_called_once()
