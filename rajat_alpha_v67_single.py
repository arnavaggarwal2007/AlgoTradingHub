"""
================================================================================
RAJAT ALPHA V67 - ALPACA ALGORITHMIC TRADING BOT (INSTITUTIONAL UPGRADE V3.2)
================================================================================

STRATEGY: Multi-Timeframe Institutional Momentum & Pullback Swing Engine
PLATFORM: Alpaca Trading API (Paper & Live Trading Support)
VERSION: 3.2 (Production Institutional Grade)
DATE: October 17, 2026

CORE STRATEGY & RISK MANAGEMENT LOGIC:
1. Signal Generation Pipeline (7 Sequential Gating Checks):
   - Check 1: Market Structure (50 SMA > 200 SMA, 21 EMA >= 50 SMA - 2.5% tolerance)
   - Check 2: Multi-Timeframe Alignment (Weekly Close > Weekly EMA21, Monthly Close > Monthly EMA10)
   - Check 3: Preceding Impulse Wave & Orderly Retracement (Swing High >= 5% above EMA21, retracing >= 3%)
   - Check 4: Pattern Confirmation (Engulfing, Piercing, Tweezer, Hammer, Upside Reversal) OR Qualified Touch
   - Check 5: Stalling Filter (Rejects horizontal consolidation churn)
   - Check 6: Extended Stock Filter (Gap up < 4%, Green session required)
   - Check 6.5: Shooting Star Rejection Filter (Upper wick > 50% of range indicates supply distribution)
   - Check 7: Conviction Score (RSI>50, MTF, Volume, Demand Zone, Touch Bonuses, RS Bonus >= 4.0)
   - Special: Touch-Only Dual Gate (Requires Score >= 5.0 AND Bullish Candle Confirmation)

2. Risk Management & Execution Architecture:
   - Initial Stop Loss: Hybrid ATR-adaptive SL (1.5x - 2.5x ATR, capped at 17%, floored at 5%)
   - Stop Loss Stepper: User-Fixed or ATR-Proportional (-4% @ +5% gain, BE @ +8% gain, +3% @ +10% gain, +1% ratchet)
   - Closing-Basis Protection: Stop losses evaluated on confirmed daily close (15:55-16:00 ET)
   - First-Hour Volatility Guard: Suppresses loss-exits during morning noise (09:30-10:30 ET) when market down
   - Partial Exits: 4-Tier Ladder (20% @ +5%, 25% @ +10%, 25% @ +15%, 30% Runner with 1:1 Trailing Stop)
   - Runner Mode: Position exempt from TES holding limits; rides major multi-week institutional markups
   - Dynamic Structural TES Engine: Grants 10-day extensions for maturing consolidations holding > EMA21
   - Smart Order Execution Engine (SOEE): Midpoint limit order pegging to eliminate the Jobbing Disadvantage

================================================================================
"""

import json
import time
import math
import sqlite3
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
import pandas_ta as ta
import pytz

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, 
    LimitOrderRequest, 
    GetOrdersRequest, 
    ReplaceOrderRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus, OrderType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest, 
    StockLatestBarRequest, 
    StockLatestQuoteRequest
)
from alpaca.data.timeframe import TimeFrame

# ================================================================================
# COMPLIANCE LOGGING SETUP
# ================================================================================

from pythonjsonlogger import jsonlogger

class ComplianceJSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for compliance and audit logging"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        if hasattr(record, 'symbol'):
            log_record['symbol'] = record.symbol
        if hasattr(record, 'trade_id'):
            log_record['trade_id'] = record.trade_id
        if hasattr(record, 'order_id'):
            log_record['order_id'] = record.order_id
        if hasattr(record, 'pnl'):
            log_record['pnl'] = record.pnl

logger = logging.getLogger('rajat_alpha_v67')
logger.setLevel(logging.INFO)

os.makedirs('logs', exist_ok=True)
os.makedirs('db', exist_ok=True)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('logs/rajat_alpha_v67.log')
json_formatter = ComplianceJSONFormatter(
    '%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(line)s %(message)s'
)
file_handler.setFormatter(json_formatter)
logger.addHandler(file_handler)

audit_handler = logging.FileHandler('logs/audit.log')
audit_handler.setLevel(logging.WARNING)
audit_handler.setFormatter(json_formatter)
logger.addHandler(audit_handler)

# ================================================================================
# NETWORK & API RESILIENCE DECORATOR
# ================================================================================

def with_api_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator to retry transient network and API failures with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Permanent failure in {func.__name__} after {max_retries} attempts: {e}")
                        return None
                    logger.warning(f"Transient error in {func.__name__} (attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    delay *= 2
            return None
        return wrapper
    return decorator

# ================================================================================
# DATABASE SETUP (Position Tracking & Persistence)
# ================================================================================

class PositionDatabase:
    """
    SQLite database to track:
    - Entry prices, initial stops, trailing stops, quantities
    - Four-tier partial exits and runner status
    - Dynamic TES extensions and structural health checks
    - Manual position override synchronization
    """
    
    def __init__(self, db_path='db/positions.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Positions table with complete institutional schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                remaining_qty INTEGER NOT NULL,
                stop_loss REAL NOT NULL,
                initial_stop_loss REAL,
                status TEXT DEFAULT 'OPEN',
                exit_date TEXT,
                exit_price REAL,
                profit_loss_pct REAL,
                exit_reason TEXT,
                score REAL,
                pattern TEXT DEFAULT 'Unknown',
                highest_price_seen REAL,
                sl_stage INTEGER DEFAULT 0,
                is_runner BOOLEAN DEFAULT 0,
                tes_extensions_count INTEGER DEFAULT 0,
                last_tes_evaluation TEXT,
                rs_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Partial exits table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partial_exits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                exit_date TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                exit_price REAL NOT NULL,
                profit_target TEXT,
                profit_pct REAL,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        ''')
        
        # Signal history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                score REAL,
                pattern TEXT,
                price REAL,
                reason TEXT,
                executed BOOLEAN DEFAULT 0,
                rs_score REAL,
                candle_pattern TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Manual overrides sync table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                override_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                position_id INTEGER,
                action TEXT NOT NULL,
                exit_price REAL,
                quantity INTEGER,
                exit_reason TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def add_position(self, symbol: str, entry_price: float, quantity: int, 
                     stop_loss: float, score: float, pattern: str = 'Unknown',
                     initial_stop_loss: Optional[float] = None,
                     rs_score: Optional[float] = None) -> int:
        """Add new position to database with institutional metrics"""
        cursor = self.conn.cursor()
        init_sl = initial_stop_loss if initial_stop_loss is not None else stop_loss
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, quantity, 
                                   remaining_qty, stop_loss, initial_stop_loss,
                                   score, pattern, highest_price_seen, sl_stage, 
                                   is_runner, tes_extensions_count, rs_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
        ''', (symbol, datetime.now().isoformat(), entry_price, quantity, 
              quantity, stop_loss, init_sl, score, pattern, entry_price, rs_score))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open positions (FIFO order) guarding against 0-quantity ghost records"""
        cursor = self.conn.cursor()
        if symbol:
            cursor.execute('''
                SELECT * FROM positions 
                WHERE symbol = ? AND status = 'OPEN' AND remaining_qty > 0
                ORDER BY entry_date ASC
            ''', (symbol,))
        else:
            cursor.execute('''
                SELECT * FROM positions 
                WHERE status = 'OPEN' AND remaining_qty > 0
                ORDER BY entry_date ASC
            ''')
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_position_by_id(self, position_id: int) -> Optional[Dict]:
        """Get a specific position by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM positions WHERE id = ?', (position_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    
    def update_stop_loss(self, position_id: int, new_stop_loss: float):
        """Update stop loss for a position (backward compatibility)"""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE positions SET stop_loss = ? WHERE id = ?', (new_stop_loss, position_id))
        self.conn.commit()

    def update_stop_loss_stepper(self, position_id: int, new_stop_loss: float, 
                                highest_price: float, sl_stage: int):
        """Update trailing stop loss with highest price and stage tracking"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE positions 
            SET stop_loss = ?, highest_price_seen = ?, sl_stage = ? 
            WHERE id = ?
        ''', (new_stop_loss, highest_price, sl_stage, position_id))
        self.conn.commit()
    
    def set_runner_mode(self, position_id: int):
        """Mark position as runner after Target 3 (exempt from TES)"""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE positions SET is_runner = 1 WHERE id = ?', (position_id,))
        self.conn.commit()
        
    def grant_tes_extension(self, position_id: int, reason_notes: str):
        """Grant dynamic 10-day structural extension for maturing setup"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE positions 
            SET tes_extensions_count = COALESCE(tes_extensions_count, 0) + 1,
                last_tes_evaluation = ?
            WHERE id = ?
        ''', (f"{datetime.now().isoformat()}: {reason_notes}", position_id))
        self.conn.commit()
    
    def add_partial_exit(self, position_id: int, quantity: int, exit_price: float,
                         profit_target: str, profit_pct: float):
        """Record partial exit and decrement remaining quantity"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO partial_exits (position_id, exit_date, quantity, 
                                       exit_price, profit_target, profit_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (position_id, datetime.now().isoformat(), quantity, exit_price,
              profit_target, profit_pct))
        
        cursor.execute('''
            UPDATE positions 
            SET remaining_qty = remaining_qty - ?
            WHERE id = ?
        ''', (quantity, position_id))
        self.conn.commit()
    
    def close_position(self, position_id: int, exit_price: float, exit_reason: str):
        """Close position completely in SQLite database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT entry_price, remaining_qty FROM positions WHERE id = ?
        ''', (position_id,))
        row = cursor.fetchone()
        if not row:
            return
        entry_price, remaining_qty = row
        
        profit_loss_pct = (exit_price - entry_price) / entry_price * 100
        
        cursor.execute('''
            UPDATE positions 
            SET status = 'CLOSED', 
                exit_date = ?,
                exit_price = ?,
                profit_loss_pct = ?,
                exit_reason = ?,
                remaining_qty = 0
            WHERE id = ?
        ''', (datetime.now().isoformat(), exit_price, profit_loss_pct, 
              exit_reason, position_id))
        self.conn.commit()
    
    def get_days_held(self, position_id: int) -> int:
        """Calculate business days held for TES check"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT entry_date FROM positions WHERE id = ?', (position_id,))
        row = cursor.fetchone()
        if not row:
            return 0
        entry_date_str = row[0]
        try:
            entry_date = datetime.fromisoformat(entry_date_str.split('T')[0])
            today = datetime.now()
            day_diff = (today - entry_date).days
            # Approximate trading days
            return int(day_diff * (5/7))
        except Exception:
            return 0
    
    def log_signal(self, symbol: str, signal_details: Dict, executed: bool = False):
        """Log detected signal to signal_history table"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO signal_history (symbol, signal_date, score, pattern, 
                                        price, reason, executed, rs_score, candle_pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, datetime.now().isoformat(), signal_details.get('score', 0),
              signal_details.get('pattern', 'None'), signal_details.get('price', 0),
              signal_details.get('reason', ''), 1 if executed else 0,
              signal_details.get('rs_score'), signal_details.get('candle_pattern')))
        self.conn.commit()
    
    def count_trades_today(self) -> int:
        """Count new positions created today"""
        cursor = self.conn.cursor()
        today_start = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM positions 
            WHERE entry_date LIKE ?
        ''', (f"{today_start}%",))
        return cursor.fetchone()[0]
    
    def was_traded_today(self, symbol: str) -> bool:
        """Check if symbol was already traded today (same-day re-entry prevention)"""
        cursor = self.conn.cursor()
        today_start = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM positions 
            WHERE symbol = ? AND entry_date LIKE ?
        ''', (symbol, f"{today_start}%"))
        return cursor.fetchone()[0] > 0
    
    def record_processed_override(self, override_id: str, symbol: str, position_id: Optional[int],
                                  action: str, exit_price: Optional[float] = None, 
                                  quantity: Optional[int] = None, exit_reason: Optional[str] = None):
        """Record processed manual override from config"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO processed_overrides 
            (override_id, symbol, position_id, action, exit_price, quantity, exit_reason, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (override_id, symbol, position_id, action, exit_price, quantity, exit_reason))
        self.conn.commit()

    def is_override_processed(self, override_id: str) -> bool:
        """Check if override was already processed"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM processed_overrides WHERE override_id = ?', (override_id,))
        return cursor.fetchone()[0] > 0

# ================================================================================
# CONFIGURATION MANAGER
# ================================================================================

class ConfigManager:
    """Loads and safely navigates json configuration"""
    
    def __init__(self, config_path='config/config.json'):
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading configuration from {self.config_path}: {e}")
            raise
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.config.get(section, {}).get(key, default)

# ================================================================================
# MARKET DATA FETCHER (With API Resilience & Midpoint Quotes)
# ================================================================================

class MarketDataFetcher:
    """Handles all market data retrieval, retry caching, and quote fetching"""
    
    def __init__(self, data_client: StockHistoricalDataClient):
        self.data_client = data_client
        self.cache = {}
        self.cache_expiry = {}
        self.last_valid_price = {}
    
    @with_api_retry(max_retries=3, base_delay=1.0)
    def get_daily_bars(self, symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch daily bars with caching"""
        cache_key = f"{symbol}_daily"
        if cache_key in self.cache:
            if datetime.now() < self.cache_expiry[cache_key]:
                return self.cache[cache_key]
        
        start_date = datetime.now() - timedelta(days=days)
        params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start_date
        )
        bars = self.data_client.get_stock_bars(params)
        
        if not bars.data.get(symbol):
            logger.warning(f"No daily bars returned for {symbol}")
            return None
        
        df = bars.df.loc[symbol].copy()
        self.cache[cache_key] = df
        self.cache_expiry[cache_key] = datetime.now() + timedelta(minutes=5)
        return df
    
    def get_weekly_bars(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """Aggregate daily bars to weekly"""
        logic = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        return df_daily.resample('W-FRI').agg(logic)
    
    def get_monthly_bars(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """Aggregate daily bars to monthly"""
        logic = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        return df_daily.resample('ME').agg(logic)
    
    @with_api_retry(max_retries=3, base_delay=0.5)
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get latest price with fallback to last valid price"""
        try:
            params = StockLatestBarRequest(symbol_or_symbols=symbol)
            bars = self.data_client.get_stock_latest_bar(params)
            if symbol in bars and bars[symbol] is not None:
                price = float(bars[symbol].close)
                self.last_valid_price[symbol] = price
                return price
        except Exception as e:
            logger.warning(f"[{symbol}] Failed to fetch latest bar: {e}")
        
        return self.last_valid_price.get(symbol)

    @with_api_retry(max_retries=3, base_delay=0.5)
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch current bid, ask, and midpoint quote for Smart Order Execution Engine"""
        try:
            params = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(params)
            if symbol in quotes and quotes[symbol] is not None:
                quote = quotes[symbol]
                bp = float(quote.bid_price)
                ap = float(quote.ask_price)
                if bp > 0 and ap > 0:
                    mid = round((bp + ap) / 2.0, 2)
                    spread = round(ap - bp, 2)
                    return {'bid': bp, 'ask': ap, 'mid': mid, 'spread': spread}
        except Exception as e:
            logger.warning(f"[{symbol}] Failed to fetch live quote: {e}")
        return None

# ================================================================================
# PATTERN DETECTOR (Expanded Bullish Reversals & Bearish Rejection)
# ================================================================================

class PatternDetector:
    """Candlestick recognition: Tiered Bullish Reversals and Bearish Rejections"""
    
    @staticmethod
    def is_engulfing(df: pd.DataFrame) -> bool:
        if len(df) < 2: return False
        curr, prev = df.iloc[-1], df.iloc[-2]
        is_green = curr['close'] > curr['open']
        prev_is_red = prev['close'] < prev['open']
        return is_green and (curr['close'] >= prev['open']) and prev_is_red
    
    @staticmethod
    def is_piercing(df: pd.DataFrame) -> bool:
        if len(df) < 2: return False
        curr, prev = df.iloc[-1], df.iloc[-2]
        is_green = curr['close'] > curr['open']
        prev_is_red = prev['close'] < prev['open']
        midpoint = (prev['open'] + prev['close']) / 2.0
        is_classic = (curr['close'] > midpoint) and (curr['close'] < prev['open']) and prev_is_red
        candle_range = curr['high'] - curr['low']
        body_size = curr['close'] - curr['open']
        is_explosive = (body_size / candle_range) >= 0.40 if candle_range > 0 else False
        return is_green and is_classic and is_explosive
    
    @staticmethod
    def is_tweezer_bottom(df: pd.DataFrame) -> bool:
        if len(df) < 2: return False
        curr, prev = df.iloc[-1], df.iloc[-2]
        is_green = curr['close'] > curr['open']
        prev_is_red = prev['close'] < prev['open']
        low_match = abs(curr['low'] - prev['low']) <= (curr['low'] * 0.002)
        return is_green and low_match and prev_is_red

    @staticmethod
    def is_hammer(df: pd.DataFrame) -> bool:
        """
        Bullish Hammer: Long lower shadow (>= 2x body), minimal upper shadow (<= 20% range).
        Prior candle must be red or indecisive.
        """
        if len(df) < 2: return False
        curr, prev = df.iloc[-1], df.iloc[-2]
        body = abs(curr['close'] - curr['open'])
        total_range = curr['high'] - curr['low']
        lower_wick = min(curr['close'], curr['open']) - curr['low']
        upper_wick = curr['high'] - max(curr['close'], curr['open'])
        
        if total_range <= 0.0001: return False
        prev_red = prev['close'] <= prev['open'] or (prev['high'] - prev['close']) > (prev['close'] - prev['low'])
        is_long_lower = lower_wick >= (2.0 * body)
        is_small_upper = (upper_wick / total_range) <= 0.20
        is_green_or_tight = curr['close'] >= curr['open'] or (body / total_range) <= 0.15
        return prev_red and is_long_lower and is_small_upper and is_green_or_tight

    @staticmethod
    def is_upside_reversal(df: pd.DataFrame) -> bool:
        """
        Upside Reversal: Opens below prior low, closes above prior bar midpoint. Green today.
        """
        if len(df) < 2: return False
        curr, prev = df.iloc[-1], df.iloc[-2]
        prev_body = prev['open'] - prev['close']
        if prev_body <= 0: return False  # Prior day must be red
        prev_midpoint = prev['close'] + (prev_body * 0.5)
        opened_weak = curr['open'] <= prev['close'] * 1.002
        closed_strong = curr['close'] > prev_midpoint
        is_green = curr['close'] > curr['open']
        return opened_weak and closed_strong and is_green

    @staticmethod
    def is_shooting_star(candle: pd.Series, max_upper_wick_ratio: float = 0.50, max_wick_to_body_ratio: float = 2.0) -> bool:
        """
        Shooting Star Bearish Rejection: Upper shadow represents >50% of the daily range
        or >2x body size, proving institutional seller dominance.
        """
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        upper_wick = candle['high'] - max(candle['close'], candle['open'])
        
        if total_range <= 0.0001: return False
        upper_wick_ratio = upper_wick / total_range
        wick_to_body = upper_wick / body if body > 0 else float('inf')
        
        if upper_wick_ratio > max_upper_wick_ratio:
            return True
        if wick_to_body > max_wick_to_body_ratio and (upper_wick / total_range) > 0.35:
            return True
        return False
    
    @classmethod
    def has_pattern(cls, df: pd.DataFrame, pattern_config: Optional[Dict] = None) -> Any:
        """
        Evaluates enabled candlestick patterns against tiered institutional weights.
        If pattern_config is None, returns legacy (has_pattern: bool, pattern_name: str).
        If pattern_config is provided, returns (has_pattern, pattern_name, tier, score_weight).
        """
        cfg = pattern_config.get('enabled_patterns', {}) if isinstance(pattern_config, dict) else {}
        is_legacy = (pattern_config is None)
        
        def is_enabled(name):
            if is_legacy:
                return True
            return cfg.get(name, {}).get('enable', True)
            
        def get_meta(name, def_tier, def_weight):
            return cfg.get(name, {}).get('tier', def_tier), cfg.get(name, {}).get('score_weight', def_weight)

        if is_enabled('Engulfing') and cls.is_engulfing(df):
            tier, weight = get_meta('Engulfing', 'A', 1.0)
            return (True, "Engulfing") if is_legacy else (True, "Engulfing", tier, weight)
            
        if is_enabled('Piercing') and cls.is_piercing(df):
            tier, weight = get_meta('Piercing', 'A', 1.0)
            return (True, "Piercing") if is_legacy else (True, "Piercing", tier, weight)
            
        if is_enabled('Tweezer') and cls.is_tweezer_bottom(df):
            tier, weight = get_meta('Tweezer', 'B', 0.8)
            return (True, "Tweezer") if is_legacy else (True, "Tweezer", tier, weight)
            
        if is_enabled('Hammer') and cls.is_hammer(df):
            tier, weight = get_meta('Hammer', 'B', 0.8)
            return (True, "Hammer") if is_legacy else (True, "Hammer", tier, weight)
            
        if is_enabled('UpsideReversal') and cls.is_upside_reversal(df):
            tier, weight = get_meta('UpsideReversal', 'C', 0.6)
            return (True, "UpsideReversal") if is_legacy else (True, "UpsideReversal", tier, weight)
            
        return (False, "None") if is_legacy else (False, "None", "None", 0.0)

# ================================================================================
# STRATEGY ANALYZER (Primary Signal Generation Engine)
# ================================================================================

class RajatAlphaAnalyzer:
    """
    Core signal generation engine:
    - 7 Sequential gating checks
    - Isolated per-symbol touch state machine with impulse wave reset
    - Preceding impulse-pullback validation
    - Regime-adaptive moving average slope validation
    - IBD-style Relative Strength Composite
    """
    
    def __init__(self, config: ConfigManager, data_fetcher: MarketDataFetcher):
        self.config = config
        self.data_fetcher = data_fetcher
        
        # Per-symbol isolated touch tracking state dictionary
        self.symbol_touch_state = defaultdict(lambda: {
            'ema21_count': 0,
            'sma50_count': 0,
            'last_swing_high': 0.0,
            'last_sma50_touch_bar': -999
        })
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators including ATR14"""
        df['SMA50'] = ta.sma(df['close'], length=50)
        df['SMA200'] = ta.sma(df['close'], length=200)
        df['EMA21'] = ta.ema(df['close'], length=21)
        df['VOL_SMA21'] = ta.sma(df['volume'], length=21)
        df['RSI14'] = ta.rsi(df['close'], length=14)
        df['ATR14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def update_touch_tracking(self, symbol: str, df: pd.DataFrame):
        """
        Isolated touch state machine per symbol with impulse wave reset:
        - Resets when a new 20-bar high >= 5% above EMA21 is printed
        - Tracks EMA21 and SMA50 touches without cross-ticker contamination
        """
        if len(df) < 25:
            return
        
        state = self.symbol_touch_state[symbol]
        curr = df.iloc[-1]
        
        # 1. Impulse Wave Reset Check: New 20-bar high >= 5% above 21 EMA
        recent_20_high = df['high'].iloc[-21:-1].max() if len(df) > 1 else None
        curr_ema21 = curr.get('EMA21')
        
        if pd.notna(curr_ema21) and curr_ema21 > 0 and pd.notna(recent_20_high) and recent_20_high >= (curr_ema21 * 1.05):
            if recent_20_high > state['last_swing_high']:
                state['last_swing_high'] = recent_20_high
                state['ema21_count'] = 0
                state['sma50_count'] = 0
                logger.debug(f"[{symbol}] Impulse wave confirmed (High: ${recent_20_high:.2f} >= 5% above EMA21). Touch counters reset.")
        
        # 2. Golden Cross Reset Check (SMA50 crosses above SMA200)
        if len(df) >= 2:
            prev = df.iloc[-2]
            p_s50 = prev.get('SMA50')
            p_s200 = prev.get('SMA200')
            c_s50 = curr.get('SMA50')
            c_s200 = curr.get('SMA200')
            if pd.notna(p_s50) and pd.notna(p_s200) and pd.notna(c_s50) and pd.notna(c_s200):
                if (p_s50 <= p_s200) and (c_s50 > c_s200):
                    state['ema21_count'] = 0
                    state['sma50_count'] = 0
                    logger.debug(f"[{symbol}] Golden Cross detected. Touch counters reset.")
        
        # 3. Touch updates
        touch_threshold = self.config.get('strategy_params', 'ma_touch_threshold_pct', 0.025)
        c_ema21 = curr.get('EMA21')
        if pd.notna(c_ema21) and c_ema21 > 0:
            if (abs(curr['close'] - c_ema21) / c_ema21) <= touch_threshold:
                state['ema21_count'] = min(3, state['ema21_count'] + 1)
                
        c_sma50 = curr.get('SMA50')
        if pd.notna(c_sma50) and c_sma50 > 0:
            if (abs(curr['close'] - c_sma50) / c_sma50) <= touch_threshold:
                state['sma50_count'] = min(3, state['sma50_count'] + 1)
                state['last_sma50_touch_bar'] = len(df) - 1
    
    def check_market_regime(self) -> bool:
        """Verify broad market regime (SPY & QQQ > 50 SMA)"""
        if not self.config.get('market_regime', 'enable_index_gate', True):
            return True
            
        index_symbols = self.config.get('market_regime', 'index_symbols', ["SPY", "QQQ"])
        for idx_sym in index_symbols:
            df_idx = self.data_fetcher.get_daily_bars(idx_sym, days=250)
            if df_idx is not None and len(df_idx) >= 50:
                sma50 = ta.sma(df_idx['close'], length=50).iloc[-1]
                last_close = df_idx['close'].iloc[-1]
                if last_close < sma50:
                    logger.info(f"Market Regime Gate: {idx_sym} (${last_close:.2f}) < 50 SMA (${sma50:.2f}). Market gate active.")
                    return False
        return True

    def check_ma_slopes(self, symbol: str, df: pd.DataFrame) -> bool:
        """Regime-adaptive moving average slope validation"""
        if not self.config.get('ma_slope_validation', 'enable', True):
            return True
            
        regime_symbol = self.config.get('ma_slope_validation', 'regime_index_symbol', 'SPY')
        df_spy = self.data_fetcher.get_daily_bars(regime_symbol, days=250)
        
        # Determine regime
        is_bull_regime = True
        if df_spy is not None and len(df_spy) >= 200:
            spy_close = df_spy['close'].iloc[-1]
            spy_sma50 = ta.sma(df_spy['close'], length=50).iloc[-1]
            spy_sma200 = ta.sma(df_spy['close'], length=200).iloc[-1]
            is_bull_regime = spy_close > spy_sma50 and spy_sma50 > spy_sma200
        
        # In bull markets, slope check is disabled (loose enough to find trades)
        if is_bull_regime and not self.config.get('ma_slope_validation', 'bull_regime_enforce', False):
            return True
            
        # In choppy or bear markets, enforce 50 SMA non-negative slope
        if len(df) >= 10:
            sma50_today = df['SMA50'].iloc[-1]
            sma50_5d_ago = df['SMA50'].iloc[-6]
            if sma50_today < sma50_5d_ago:
                logger.info(f"[{symbol}] ❌ MA Slope Check: FAILED - 50 SMA sloping downwards in non-bull regime.")
                return False
                
        return True

    def check_market_structure(self, df: pd.DataFrame) -> bool:
        """50 SMA > 200 SMA and 21 EMA >= 50 SMA - 2.5% tolerance"""
        curr = df.iloc[-1]
        if pd.isna(curr['SMA50']) or pd.isna(curr['SMA200']) or pd.isna(curr['EMA21']):
            return False
        ema_tolerance = self.config.get('strategy_params', 'ema_tolerance_pct', 0.025)
        ema_threshold = curr['SMA50'] * (1 - ema_tolerance)
        return (curr['SMA50'] > curr['SMA200']) and (curr['EMA21'] >= ema_threshold)
    
    def check_multitimeframe_confirmation(self, df_daily: pd.DataFrame, 
                                          df_weekly: pd.DataFrame, 
                                          df_monthly: pd.DataFrame) -> Tuple[bool, bool]:
        """Weekly close > Weekly EMA21 AND Monthly close > Monthly EMA10"""
        df_weekly['EMA21'] = ta.ema(df_weekly['close'], length=21)
        df_monthly['EMA10'] = ta.ema(df_monthly['close'], length=10)
        
        curr_w = df_weekly.iloc[-1]
        curr_m = df_monthly.iloc[-1]
        weekly_ok = curr_w['close'] > curr_w['EMA21'] if not pd.isna(curr_w['EMA21']) else False
        monthly_ok = curr_m['close'] > curr_m['EMA10'] if not pd.isna(curr_m['EMA10']) else False
        return weekly_ok, monthly_ok
    
    def check_pullback(self, df: pd.DataFrame) -> bool:
        """
        Pullback Detection with Preceding Impulse Validator:
        1. Within 20 bars, price printed an impulse swing high >= 5% above EMA21.
        2. Retraced >= 3% from impulse high OR 3 consecutive lower closes.
        3. Near EMA21 or SMA50 within tolerance.
        """
        curr = df.iloc[-1]
        threshold = self.config.get('strategy_params', 'ma_touch_threshold_pct', 0.025)
        
        dist_ema21 = abs(curr['close'] - curr['EMA21']) / curr['EMA21'] if curr['EMA21'] > 0 else 1.0
        dist_sma50 = abs(curr['close'] - curr['SMA50']) / curr['SMA50'] if curr['SMA50'] > 0 else 1.0
        near_ma = (dist_ema21 <= threshold) or (dist_sma50 <= threshold)
        if not near_ma:
            return False

        enable_impulse = False
        cfg_val = self.config.get('pullback_validation', 'enable_impulse_validation', False)
        if cfg_val is True:
            enable_impulse = True
            
        if not enable_impulse or len(df) < 10:
            # Fallback legacy pullback: high was higher in past 5 bars
            recent_high = df['high'].iloc[-5:-1].max() if len(df) >= 5 else df['high'].iloc[:-1].max()
            return bool(recent_high > curr['high'])
            
        raw_lb = self.config.get('pullback_validation', 'impulse_lookback_bars', 20)
        try:
            lb_int = int(raw_lb)
            if lb_int <= 1:
                lb_int = 20
        except Exception:
            lb_int = 20
            
        lookback = min(lb_int, len(df) - 1)
        impulse_slice = df.iloc[-lookback:-1]
        swing_high = impulse_slice['high'].max()
        
        # Check swing high was >= 5% above EMA21 at that time
        idx_high = impulse_slice['high'].idxmax()
        ema_at_high = df.loc[idx_high, 'EMA21']
        if pd.isna(ema_at_high) or ema_at_high <= 0 or (swing_high < ema_at_high * 1.05):
            return False  # No prior markup wave
            
        # Check orderly retracement
        min_decline = self.config.get('pullback_validation', 'min_pullback_decline_pct', 0.03)
        has_declined = False
        try:
            min_decline_float = float(min_decline)
            has_declined = (swing_high - curr['low']) / swing_high >= min_decline_float
        except Exception:
            pass
        
        consec_lower = sum(1 for i in range(-3, 0) if df.iloc[i]['close'] < df.iloc[i-1]['close']) >= 2
        return bool(has_declined or consec_lower)

    def check_stalling(self, df: pd.DataFrame, stalling_days_long: int = 8, stalling_days_short: int = 3) -> bool:
        """Rejects horizontal consolidation churn"""
        if len(df) < max(stalling_days_long, stalling_days_short) + 1:
            return False
        range_pct = self.config.get('strategy_params', 'stalling_range_pct', 5.0)
        
        long_slice = df.iloc[-(stalling_days_long+1):-1]
        long_range = (long_slice['high'].max() - long_slice['low'].min()) / long_slice['low'].min() * 100
        
        if long_range <= range_pct:
            short_slice = df.iloc[-(stalling_days_short+1):-1]
            short_range = (short_slice['high'].max() - short_slice['low'].min()) / short_slice['low'].min() * 100
            return short_range > range_pct
        return False

    def check_extended_stock(self, df: pd.DataFrame, current_price: float) -> Tuple[bool, float]:
        """Check for gap up extension"""
        if len(df) < 2: return False, 0.0
        prev_close = df.iloc[-2]['close']
        gap_pct = (current_price - prev_close) / prev_close
        max_gap = self.config.get('strategy_params', 'max_gap_pct', 0.04)
        return gap_pct > max_gap, gap_pct

    def check_touch_based_signal(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for qualified moving average touch"""
        if len(df) < 20: return False, "insufficient_data"
        curr = df.iloc[-1]
        threshold = self.config.get('strategy_params', 'ma_touch_threshold_pct', 0.025)
        
        touched_ema21 = abs(curr['close'] - curr['EMA21']) / curr['EMA21'] <= threshold if curr['EMA21'] > 0 else False
        touched_sma50 = abs(curr['close'] - curr['SMA50']) / curr['SMA50'] <= threshold if curr['SMA50'] > 0 else False
        
        if touched_ema21 and self.config.get('trading_rules', 'enable_21touch_signals', True):
            return True, "EMA21_Touch"
        if touched_sma50 and self.config.get('trading_rules', 'enable_50touch_signals', True):
            # 50 SMA Institutional qualification: Volume Contraction
            if curr['volume'] <= curr['VOL_SMA21']:
                return True, "SMA50_Touch"
        return False, "no_touch"

    def calculate_rs_composite(self, symbol: str, df: pd.DataFrame) -> float:
        """
        Calculates IBD-style 0-100 Relative Strength Composite:
        1. 1-mo alpha vs QQQ (25%)
        2. Up/Down volume ratio (20%)
        3. Green/Red day ratio (15%)
        4. 52-week high proximity (15%)
        5. 4-week momentum (10%)
        6. Earnings quality (10%)
        7. Fund sponsorship (5%)
        """
        try:
            df_qqq = self.data_fetcher.get_daily_bars("QQQ", days=60)
            if df_qqq is None or len(df) < 22:
                return 50.0  # Neutral
                
            # Factor 1: 1-mo price return vs QQQ
            stock_ret = (df['close'].iloc[-1] - df['close'].iloc[-21]) / df['close'].iloc[-21]
            qqq_ret = (df_qqq['close'].iloc[-1] - df_qqq['close'].iloc[-21]) / df_qqq['close'].iloc[-21]
            alpha = (1.0 + stock_ret) / (1.0 + qqq_ret)
            score_1 = max(0, min(100, (alpha - 0.90) / 0.30 * 100))
            
            # Factor 2: Up/Down Volume (21-day)
            slice_21 = df.iloc[-21:]
            up_vol = slice_21[slice_21['close'] > slice_21['open']]['volume'].sum()
            dn_vol = max(1, slice_21[slice_21['close'] < slice_21['open']]['volume'].sum())
            ud_ratio = up_vol / dn_vol
            score_2 = max(0, min(100, (ud_ratio - 0.70) / 1.0 * 100))
            
            # Factor 3: Green vs Red Days
            green_days = sum(slice_21['close'] > slice_21['open'])
            red_days = max(1, sum(slice_21['close'] < slice_21['open']))
            score_3 = max(0, min(100, (green_days / red_days - 0.60) / 0.80 * 100))
            
            # Factor 4: 52-Week High Proximity
            high_252 = df['high'].max()
            dist_52 = (high_252 - df['close'].iloc[-1]) / high_252
            score_4 = max(0, min(100, (1.0 - (dist_52 / 0.20)) * 100))
            
            # Composite calculation
            rs_score = (score_1 * 0.35) + (score_2 * 0.25) + (score_3 * 0.20) + (score_4 * 0.20)
            return round(rs_score, 1)
        except Exception:
            return 50.0

    def calculate_score(self, df: pd.DataFrame, symbol: str, weekly_ok: bool, 
                        monthly_ok: bool, pattern_found: bool, touch_found: bool,
                        pattern_weight: float = 1.0, rs_score: float = 50.0) -> float:
        """Computes comprehensive score across technicals, MTF, volume, touch, and RS"""
        curr = df.iloc[-1]
        score = 0.0
        
        # 1. RSI Momentum (>50)
        rsi_val = curr.get('RSI14')
        if not pd.isna(rsi_val) and rsi_val > 50:
            score += 1.0
            
        # 2 & 3. MTF
        if weekly_ok: score += 1.0
        if monthly_ok: score += 1.0
        
        # 4. Volume above 21-day average
        if curr['volume'] > curr.get('VOL_SMA21', 0):
            score += 1.0
            
        # 5. Demand Zone (within 3.5% of 21-day low)
        low_21 = df['low'].iloc[-21:].min()
        if curr['low'] <= (low_21 * 1.035):
            score += 1.0
            
        # Pattern score weight
        if pattern_found:
            score += pattern_weight
            
        # Isolated Touch state bonuses
        state = self.symbol_touch_state[symbol]
        if state['ema21_count'] == 1: score += 1.0
        elif state['ema21_count'] == 2: score += 0.5
        
        if state['sma50_count'] == 1: score += 1.0
        elif state['sma50_count'] == 2: score += 0.5
        
        # RS composite bonus
        if self.config.get('relative_strength', 'enable', False) and rs_score >= 70.0:
            score += self.config.get('relative_strength', 'rs_score_bonus_points', 0.5)
            
        return round(score, 1)

    def analyze_entry_signal(self, symbol: str) -> Tuple[bool, Dict]:
        """Full 7-gate entry signal analysis"""
        result = {
            'symbol': symbol,
            'signal': False,
            'reason': '',
            'score': 0.0,
            'pattern': 'None',
            'signal_types': [],
            'price': 0.0,
            'checks': {},
            'rs_score': 50.0,
            'candle_pattern': 'None'
        }
        
        df_daily = self.data_fetcher.get_daily_bars(symbol, days=365)
        if df_daily is None or len(df_daily) < self.config.get('strategy_params', 'min_listing_days', 200):
            result['reason'] = "Insufficient historical bars or immature listing"
            return False, result
            
        df_daily = self.calculate_indicators(df_daily)
        df_weekly = self.data_fetcher.get_weekly_bars(df_daily)
        df_monthly = self.data_fetcher.get_monthly_bars(df_daily)
        
        self.update_touch_tracking(symbol, df_daily)
        
        # GATE 0: Broad Market Regime Gate
        if not self.check_market_regime():
            result['reason'] = "Broad market regime not bullish (SPY/QQQ < 50 SMA)"
            return False, result

        # GATE 1: Market Structure
        structure_ok = self.check_market_structure(df_daily)
        result['checks']['market_structure'] = structure_ok
        if not structure_ok:
            result['reason'] = "Market structure failed (50 SMA > 200 SMA required)"
            return False, result

        # GATE 1.5: Regime-Adaptive MA Slope
        if not self.check_ma_slopes(symbol, df_daily):
            result['reason'] = "50 SMA slope negative in non-bull regime"
            return False, result

        # GATE 2: Multi-Timeframe Confirmation
        weekly_ok, monthly_ok = self.check_multitimeframe_confirmation(df_daily, df_weekly, df_monthly)
        result['checks']['weekly_ok'] = weekly_ok
        result['checks']['monthly_ok'] = monthly_ok
        if not (weekly_ok and monthly_ok):
            result['reason'] = f"MTF failed (Weekly: {weekly_ok}, Monthly: {monthly_ok})"
            return False, result

        # GATE 3: Preceding Impulse & Orderly Retracement
        pullback_ok = self.check_pullback(df_daily)
        result['checks']['pullback'] = pullback_ok
        if not pullback_ok:
            result['reason'] = "No valid preceding impulse and pullback sequence"
            return False, result

        # GATE 4: Candlestick Pattern OR Touch Signal
        pattern_cfg = self.config.get('pattern_config', {})
        pat_found, pat_name, pat_tier, pat_weight = PatternDetector.has_pattern(df_daily, pattern_cfg)
        touch_found, touch_type = self.check_touch_based_signal(df_daily)
        
        if not (pat_found or touch_found):
            result['reason'] = "No recognized reversal pattern or qualified touch"
            return False, result

        result['checks']['pattern'] = pat_found
        result['checks']['touch_signal'] = touch_found
        result['candle_pattern'] = pat_name

        # GATE 5: Stalling Filter
        if self.check_stalling(df_daily):
            result['reason'] = "Stock is in horizontal sideways consolidation"
            return False, result

        # GATE 6: Extended Stock Filter (Gap > 4%)
        curr_price = self.data_fetcher.get_current_price(symbol)
        if curr_price is None:
            result['reason'] = "Unable to fetch live price"
            return False, result
            
        if self.config.get('strategy_params', 'enable_extended_filter', True):
            is_ext, gap_pct = self.check_extended_stock(df_daily, curr_price)
            if is_ext:
                result['reason'] = f"Stock is EXTENDED (Gap up {gap_pct*100:.2f}%)"
                return False, result

        # GATE 6.5: Green Session Confirmation
        prev_close = df_daily.iloc[-2]['close']
        if curr_price <= prev_close:
            result['reason'] = f"Stock is RED today (${curr_price:.2f} <= ${prev_close:.2f})"
            return False, result

        # GATE 6.75: Shooting Star Rejection Filter (MANDATORY)
        curr_candle = df_daily.iloc[-1]
        max_wick = self.config.get('candle_quality', 'max_upper_wick_ratio', 0.50)
        max_w2b = self.config.get('candle_quality', 'max_wick_to_body_ratio', 2.0)
        if PatternDetector.is_shooting_star(curr_candle, max_wick, max_w2b):
            result['reason'] = "Shooting star rejection: Upper wick indicates heavy seller distribution"
            logger.info(f"[{symbol}] ❌ SHOOTING STAR REJECTED: Upper shadow spans >50% of range.")
            return False, result

        # Calculate IBD Relative Strength
        rs_score = self.calculate_rs_composite(symbol, df_daily)
        result['rs_score'] = rs_score
        if self.config.get('relative_strength', 'enable', False):
            min_rs = self.config.get('relative_strength', 'min_rs_rating', 40.0)
            if rs_score < min_rs:
                result['reason'] = f"Relative Strength rating too low: {rs_score:.1f} < {min_rs}"
                return False, result

        # GATE 7: Scoring & Touch-Only Dual Gate
        score = self.calculate_score(df_daily, symbol, weekly_ok, monthly_ok, pat_found, touch_found, pat_weight, rs_score)
        result['score'] = score
        
        # Touch-Only Dual Gate: If no pattern, require higher score bar + bullish body
        if not pat_found and touch_found:
            min_touch_score = self.config.get('trading_rules', 'min_touch_only_score', 5.0)
            if score < min_touch_score:
                result['reason'] = f"Touch-only score {score:.1f} below required {min_touch_score}"
                return False, result
                
            body_size = abs(curr_candle['close'] - curr_candle['open'])
            total_range = curr_candle['high'] - curr_candle['low']
            body_ratio = body_size / total_range if total_range > 0 else 0
            close_pos = (curr_candle['close'] - curr_candle['low']) / total_range if total_range > 0 else 0
            
            if body_ratio < 0.50 or close_pos < 0.67:
                result['reason'] = "Touch-only candle failed bullish conviction confirmation"
                return False, result

        min_score = self.config.get('strategy_params', 'min_signal_score', 4.0)
        if score < min_score:
            result['reason'] = f"Score {score:.1f} below minimum {min_score}"
            return False, result

        # Valid Signal
        signal_types = []
        if pat_found: signal_types.append('swing')
        if touch_found:
            signal_types.append('21Touch' if touch_type == "EMA21_Touch" else '50Touch')
            
        result['signal'] = True
        result['signal_types'] = signal_types
        result['pattern'] = '+'.join(signal_types) if signal_types else 'Touch-Only'
        result['price'] = curr_price
        result['reason'] = f"VALID BUY SIGNAL - Types:{result['pattern']} Score:{score:.1f} RS:{rs_score:.1f}"
        return True, result

# ================================================================================
# POSITION MANAGER (Execution, ATR Stop Loss, 4-Tier Exits, SOEE, Runner Mode)
# ================================================================================

class PositionManager:
    """Manages position sizing, SOEE smart routing, ATR trailing stops, and multi-tier exits"""
    
    def __init__(self, trading_client: TradingClient, config: ConfigManager, 
                 db: PositionDatabase, data_fetcher: MarketDataFetcher):
        self.trading_client = trading_client
        self.config = config
        self.db = db
        self.data_fetcher = data_fetcher

    def calculate_position_size(self, symbol: str, current_price: float) -> Tuple[int, float]:
        """
        Calculates position sizing:
        - 3% per trade (configurable)
        - Max 6% per stock (configurable)
        - Enforces max_equity_utilization_pct (e.g. 90%)
        - Capital conservation mode if utilization > 70% of max
        """
        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
        except Exception as e:
            logger.error(f"Failed to get account equity: {e}")
            return 0, 0.0

        trade_pct = self.config.get('trading_rules', 'per_trade_pct', 0.03)
        max_allocation_per_stock_pct = self.config.get('trading_rules', 'max_allocation_per_stock_pct', 0.06)

        # Calculate current allocation for this stock
        open_positions = self.db.get_open_positions(symbol=symbol)
        current_allocation = sum(pos['entry_price'] * pos['remaining_qty'] for pos in open_positions)
        current_allocation_pct = current_allocation / equity if equity > 0 else 0

        # Remaining allocation for this stock
        remaining_pct = max(0.0, max_allocation_per_stock_pct - current_allocation_pct)
        effective_trade_pct = min(trade_pct, remaining_pct)

        if effective_trade_pct <= 0:
            logger.warning(f"[{symbol}] Per-stock allocation limit reached ({current_allocation_pct*100:.1f}% / {max_allocation_per_stock_pct*100:.1f}%), cannot add more")
            return 0, 0.0

        # Total portfolio allocation
        total_open = self.db.get_open_positions()
        total_current_allocation = sum(pos['entry_price'] * pos['remaining_qty'] for pos in total_open)
        max_utilization_pct = self.config.get('trading_rules', 'max_equity_utilization_pct', 0.90)

        # Capital conservation mode check (if enabled and utilization >= 70% of max limit)
        if self.config.get('trading_rules', 'capital_conservation_mode', False):
            if (total_current_allocation / equity) >= (max_utilization_pct * 0.70):
                effective_trade_pct = effective_trade_pct * 0.5  # Half position size in conservation mode

        trade_amount = equity * effective_trade_pct
        projected_utilization_pct = (total_current_allocation + trade_amount) / equity

        if projected_utilization_pct > max_utilization_pct:
            available_pct = max_utilization_pct - (total_current_allocation / equity)
            if available_pct <= 0.001:
                logger.warning(f"[{symbol}] Overall utilization limit reached ({projected_utilization_pct*100:.1f}% / {max_utilization_pct*100:.1f}%), blocking trade")
                return 0, 0.0
            trade_amount = equity * min(effective_trade_pct, available_pct)

        shares = int(trade_amount / current_price)
        actual_amount = shares * current_price
        if shares <= 0:
            logger.warning(f"[{symbol}] Trade size too small after limits")
            return 0, 0.0

        return shares, actual_amount

    def calculate_stop_loss(self, symbol: str, entry_price: float, score: float, df: Optional[pd.DataFrame] = None) -> float:
        """
        Calculates Hybrid ATR-adaptive initial stop loss:
        - Higher conviction (score >= 5): 1.5x ATR
        - Standard (score 4): 2.0x ATR
        - Lower (score <= 3.5): 2.5x ATR
        - Capped at 17% maximum risk, floored at 5% minimum risk
        """
        max_pct = self.config.get('risk_management', 'max_initial_sl_pct', 0.17)
        min_pct = self.config.get('risk_management', 'min_initial_sl_pct', 0.05)
        
        atr = None
        if df is not None and 'ATR14' in df and not pd.isna(df['ATR14'].iloc[-1]):
            atr = float(df['ATR14'].iloc[-1])
            
        if atr is not None and atr > 0:
            k = 1.5 if score >= 5.0 else (2.0 if score >= 4.0 else 2.5)
            atr_sl = entry_price - (k * atr)
            max_sl = entry_price * (1.0 - max_pct)
            min_sl = entry_price * (1.0 - min_pct)
            initial_sl = max(atr_sl, max_sl)
            initial_sl = min(initial_sl, min_sl)
            return round(initial_sl, 4)
            
        # Fallback to fixed 17%
        return round(entry_price * (1.0 - max_pct), 4)

    def execute_buy(self, symbol: str, signal_details: Dict) -> bool:
        """
        Executes buy order via Smart Order Execution Engine (SOEE) Midpoint Limit Order
        or Market Order depending on configuration
        """
        current_price = signal_details['price']
        shares, target_val = self.calculate_position_size(symbol, current_price)
        score = signal_details.get('score', 4.0)
        
        df_daily = self.data_fetcher.get_daily_bars(symbol, days=50)
        stop_loss = self.calculate_stop_loss(symbol, current_price, score, df_daily)
        
        use_smart_soee = self.config.get('execution_schedule', 'enable_smart_execution', True)
        quote = self.data_fetcher.get_latest_quote(symbol) if use_smart_soee else None
        
        try:
            if quote and quote['mid'] > 0:
                limit_px = quote['mid']
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    limit_price=limit_px,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
                logger.info(f"[{symbol}] SOEE Midpoint Limit Order submitted: {shares} shares @ ${limit_px:.2f} (Spread: ${quote['spread']:.2f})")
            else:
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
                logger.info(f"[{symbol}] Market Buy Order submitted: {shares} shares @ ~${current_price:.2f}")

            order = self.trading_client.submit_order(order_request)
            
            position_id = self.db.add_position(
                symbol=symbol,
                entry_price=current_price,
                quantity=shares,
                stop_loss=stop_loss,
                score=score,
                pattern=signal_details.get('pattern', 'Unknown'),
                initial_stop_loss=stop_loss,
                rs_score=signal_details.get('rs_score', 50.0)
            )
            logger.info(f"[{symbol}] Position established in DB (ID: {position_id}, SL: ${stop_loss:.2f})")
            return True
        except Exception as e:
            logger.error(f"[{symbol}] Buy execution failed: {e}")
            return False

    def update_trailing_stop_loss(self, position: Dict, current_price: float):
        """
        Dual-mode multi-stage stop loss stepper:
        - Gain >= +5%: SL moves to -4% below entry
        - Gain >= +8%: SL moves to Breakeven (0.0%)
        - Gain >= +10%: SL moves to +3% above entry
        - Above +10%: Ratchets +1.0% for every additional +1.0% price gain
        - Monotonic Guarantee: Stop loss never decreases
        """
        entry_price = position['entry_price']
        current_sl = position['stop_loss']
        position_id = position['id']
        profit_pct = (current_price - entry_price) / entry_price
        
        highest_price = max(position.get('highest_price_seen') or entry_price, current_price)
        target_sl = current_sl
        new_stage = position.get('sl_stage', 0)
        
        stepper_mode = self.config.get('risk_management', 'stepper_mode', 'user_fixed')
        
        if stepper_mode == 'user_fixed':
            if profit_pct >= 0.10:
                ratchet = 0.03 + (profit_pct - 0.10)
                target_sl = entry_price * (1.0 + ratchet)
                new_stage = 3
            elif profit_pct >= 0.08:
                target_sl = entry_price
                new_stage = 2
            elif profit_pct >= 0.05:
                target_sl = entry_price * (1.0 - 0.04)
                new_stage = 1
        else:
            # ATR proportional stepper
            init_sl = position.get('initial_stop_loss') or (entry_price * 0.83)
            risk_d = entry_price - init_sl
            if profit_pct >= 0.10:
                target_sl = entry_price + (risk_d * 0.18) + (entry_price * (profit_pct - 0.10))
                new_stage = 3
            elif profit_pct >= 0.08:
                target_sl = entry_price
                new_stage = 2
            elif profit_pct >= 0.05:
                target_sl = entry_price - (risk_d * 0.25)
                new_stage = 1

        if target_sl > current_sl:
            self.db.update_stop_loss_stepper(position_id, round(target_sl, 4), round(highest_price, 4), new_stage)
            logger.info(f"[{position['symbol']}] Trailing SL stepped: ${current_sl:.2f} → ${target_sl:.2f} (Profit: {profit_pct*100:+.2f}%, Stage {new_stage})")

    def check_stop_loss(self, position: Dict, current_price: float, 
                        is_closing_window: bool = False, 
                        is_first_hour_suppressed: bool = False) -> bool:
        """
        True Daily Closing-Basis Stop Loss Check:
        - Catastrophic Breaker: -22% total loss or -10% stock gap triggers immediately anytime.
        - First-Hour Guard: Suppresses regular stops between 09:30-10:30 ET when market open down.
        - True Closing Basis: Evaluates confirmed daily close at 15:55-16:00 ET.
        """
        entry_price = position['entry_price']
        stop_loss = position['stop_loss']
        
        # 1. Emergency Catastrophic Breakers (Always active)
        cat_pct = self.config.get('first_hour_guard', 'catastrophic_override_pct', -0.22)
        if (current_price - entry_price) / entry_price <= cat_pct:
            logger.warning(f"[{position['symbol']}] 🚨 CATASTROPHIC BREAKER TRIGGERED: P/L <= {cat_pct*100:.1f}%")
            return True
            
        # 2. First-Hour Volatility Guard Suppression
        if is_first_hour_suppressed:
            return False
            
        # 3. True Closing Basis Check
        eval_mode = self.config.get('risk_management', 'stop_loss_evaluation', 'daily_close_confirmed')
        if eval_mode == 'daily_close_confirmed':
            if not is_closing_window:
                return False  # Intraday wicks do not trigger exit
            return current_price <= stop_loss
            
        # Default tick evaluation
        return current_price <= stop_loss

    def check_partial_exit_targets(self, position: Dict, current_price: float) -> List[Tuple[str, int, float]]:
        """
        Four-Tier Partial Exit Ladder:
        - PT1 (+5%): Sell 20%
        - PT2 (+10%): Sell 25%
        - PT3 (+15%): Sell 25%
        - Remaining 30%: Enters Runner Mode
        """
        if not self.config.get('profit_taking', 'enable_partial_exits', True):
            return []
            
        entry_price = position['entry_price']
        remaining_qty = position['remaining_qty']
        orig_qty = position['quantity']
        exits_to_execute = []
        
        targets = [
            ('PT1', self.config.get('profit_taking', 'target_1_pct', 0.05), self.config.get('profit_taking', 'target_1_qty', 0.20)),
            ('PT2', self.config.get('profit_taking', 'target_2_pct', 0.10), self.config.get('profit_taking', 'target_2_qty', 0.25)),
            ('PT3', self.config.get('profit_taking', 'target_3_pct', 0.15), self.config.get('profit_taking', 'target_3_qty', 0.25))
        ]
        
        cursor = self.db.conn.cursor()
        for t_name, t_pct, t_qty_pct in targets:
            t_price = round(entry_price * (1.0 + t_pct), 4)
            if current_price >= (t_price - 0.0001):
                cursor.execute('SELECT COUNT(*) FROM partial_exits WHERE position_id = ? AND profit_target = ?', (position['id'], t_name))
                if cursor.fetchone()[0] == 0 and remaining_qty > 0:
                    qty_to_sell = int(orig_qty * t_qty_pct)
                    qty_to_sell = min(qty_to_sell, remaining_qty)
                    if qty_to_sell > 0:
                        exits_to_execute.append((t_name, qty_to_sell, t_price))
                        remaining_qty -= qty_to_sell
                        
        return exits_to_execute

    def execute_partial_exit(self, position: Dict, target_name: str, quantity: int, current_price: float):
        """Execute partial exit and activate runner mode if PT3 reached"""
        symbol = position['symbol']
        if quantity > position['remaining_qty'] or quantity <= 0:
            return
            
        logger.info(f"[{symbol}] Executing Partial Exit {target_name}: {quantity} shares @ ${current_price:.2f}")
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            self.trading_client.submit_order(order_request)
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            self.db.add_partial_exit(position['id'], quantity, current_price, target_name, profit_pct)
            
            # Check if Target 3 executed -> Activate Runner Mode
            if target_name == 'PT3':
                self.db.set_runner_mode(position['id'])
                logger.info(f"[{symbol}] 🚀 RUNNER MODE ACTIVATED: Remaining 30% position exempt from TES; trailing 1:1.")
                
            # Bug 1 Guard: Clean close if remaining is 0
            refreshed = self.db.get_position_by_id(position['id'])
            if refreshed and refreshed['remaining_qty'] <= 0:
                self.db.close_position(position['id'], current_price, "Partial Exits Complete")
                logger.info(f"[{symbol}] Position cleanly closed in DB after partial exits.")
        except Exception as e:
            logger.error(f"[{symbol}] Partial exit {target_name} failed: {e}")

    def execute_full_exit(self, position: Dict, current_price: float, reason: str):
        """Execute full position exit and close in database"""
        symbol = position['symbol']
        remaining = position['remaining_qty']
        if remaining <= 0:
            return
            
        logger.info(f"[{symbol}] Executing FULL EXIT: {remaining} shares @ ${current_price:.2f} (Reason: {reason})")
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=remaining,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            self.trading_client.submit_order(order_request)
            self.db.close_position(position['id'], current_price, reason)
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            logger.info(f"[{symbol}] Position CLOSED in DB (P/L: {profit_pct:+.2f}%)")
        except Exception as e:
            logger.error(f"[{symbol}] Full exit failed: {e}")

    def check_time_exit(self, position: Dict, df: Optional[pd.DataFrame] = None) -> bool:
        """
        Dynamic Structural TES Engine (Minervini/Ryan consolidation extension):
        - Runners (is_runner=1) are completely exempt from TES.
        - If days held >= max_hold_days, checks if position is holding constructively > EMA21.
        - Grants 10-day extension if setup is healthy instead of dumping into dead money.
        """
        if position.get('is_runner', 0) == 1:
            return False
            
        max_hold_days = self.config.get('risk_management', 'max_hold_days', 21)
        days_held = self.db.get_days_held(position['id'])
        
        if days_held < max_hold_days:
            return False
            
        # Check dynamic structural extension
        if self.config.get('risk_management', 'enable_dynamic_tes_extension', True):
            max_ext = self.config.get('risk_management', 'max_tes_extensions', 2)
            cur_ext = position.get('tes_extensions_count', 0)
            
            if cur_ext < max_ext and df is not None and len(df) >= 21:
                curr_close = df['close'].iloc[-1]
                ema21 = df['EMA21'].iloc[-1]
                
                # If price is holding above 21 EMA constructively, extend!
                if curr_close >= (ema21 * 0.99):
                    self.db.grant_tes_extension(position['id'], "Constructive base holding >= 21 EMA")
                    logger.info(f"[{position['symbol']}] 🎯 DYNAMIC TES EXTENSION GRANTED (+10 days): Maturing base above EMA21.")
                    return False
                    
        return True

# ================================================================================
# SIGNAL QUEUE (Monitoring Window & Priority Tie-Breaking)
# ================================================================================

class SignalQueue:
    """Manages signal staging, 30-min monitoring, and multi-factor priority sorting"""
    
    def __init__(self, monitoring_minutes: int = 30, top_n: int = 5):
        self.monitoring_minutes = monitoring_minutes
        self.top_n = top_n
        self.signals = {}
        self.window_start_time = None
    
    def add_signal(self, symbol: str, signal_details: Dict):
        if not self.signals:
            self.window_start_time = datetime.now()
        self.signals[symbol] = signal_details
    
    def is_window_complete(self) -> bool:
        if not self.window_start_time: return False
        elapsed = (datetime.now() - self.window_start_time).total_seconds() / 60
        return elapsed >= self.monitoring_minutes
    
    def get_top_signals(self, analyzer: RajatAlphaAnalyzer) -> List[Tuple[str, Dict]]:
        valid_signals = []
        for symbol, details in self.signals.items():
            valid, updated_details = analyzer.analyze_entry_signal(symbol)
            if valid:
                valid_signals.append((symbol, updated_details))
                
        # Sort by Score DESC, RS Score DESC
        valid_signals.sort(key=lambda x: (x[1].get('score', 0), x[1].get('rs_score', 0)), reverse=True)
        return valid_signals[:self.top_n]
    
    def reset(self):
        self.signals = {}
        self.window_start_time = None

# ================================================================================
# TRADING BOT ORCHESTRATOR
# ================================================================================

class RajatAlphaTradingBot:
    """Master orchestrator for Sell Guardian, Buy Hunter, and Manual Overrides"""
    
    def __init__(self, config_path='config/config.json'):
        self.config = ConfigManager(config_path)
        self.db = PositionDatabase()
        
        api_key = self.config.get('api', 'key_id')
        secret_key = self.config.get('api', 'secret_key')
        base_url = self.config.get('api', 'base_url')
        self.is_paper = 'paper' in base_url
        
        self.trading_client = TradingClient(api_key, secret_key, paper=self.is_paper)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
        
        self.data_fetcher = MarketDataFetcher(self.data_client)
        self.analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        self.position_manager = PositionManager(self.trading_client, self.config, self.db, self.data_fetcher)
        
        self.signal_queue = SignalQueue(
            monitoring_minutes=self.config.get('execution_schedule', 'signal_monitoring_minutes', 30),
            top_n=self.config.get('execution_schedule', 'top_n_trades', 5)
        )
        
        logger.info("=" * 80)
        logger.info("RAJAT ALPHA V67 TRADING BOT INITIALIZED (VERSION 3.2)")
        logger.info(f"Mode: {'PAPER TRADING' if self.is_paper else 'LIVE TRADING'}")
        logger.info("=" * 80)

    def is_market_open(self) -> bool:
        now = datetime.now(pytz.timezone('US/Eastern'))
        if now.weekday() > 4: return False
        market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_start <= now <= market_end

    def is_closing_window(self) -> bool:
        now = datetime.now(pytz.timezone('US/Eastern'))
        return now.hour == 15 and now.minute >= 55

    def is_first_hour(self) -> bool:
        now = datetime.now(pytz.timezone('US/Eastern'))
        return (now.hour == 9 and now.minute >= 30) or (now.hour == 10 and now.minute < 30)

    def is_market_opening_down(self) -> bool:
        """Check if SPY opened below yesterday's close"""
        df_spy = self.data_fetcher.get_daily_bars('SPY', days=5)
        if df_spy is not None and len(df_spy) >= 2:
            prev_close = df_spy['close'].iloc[-2]
            curr_price = self.data_fetcher.get_current_price('SPY')
            if curr_price and curr_price < prev_close:
                return True
        return False

    def is_buy_window(self) -> bool:
        now = datetime.now(pytz.timezone('US/Eastern'))
        start_str = self.config.get('execution_schedule', 'buy_window_start_time', '14:30')
        end_str = self.config.get('execution_schedule', 'buy_window_end_time', '15:59')
        sh, sm = map(int, start_str.split(':'))
        eh, em = map(int, end_str.split(':'))
        start = now.replace(hour=sh, minute=sm, second=0)
        end = now.replace(hour=eh, minute=em, second=0)
        return start <= now <= end

    def process_manual_overrides(self):
        """Processes manual force-close overrides from config.json cleanly in SQLite"""
        overrides = self.config.get('manual_position_overrides', [])
        for item in overrides:
            if not isinstance(item, dict): continue
            override_id = str(item.get('position_id') or item.get('symbol'))
            if item.get('processed', False) or self.db.is_override_processed(override_id):
                continue
                
            symbol = item.get('symbol')
            pos_id = item.get('position_id')
            action = item.get('action', 'FORCE_CLOSE')
            exit_px = item.get('exit_price') or self.data_fetcher.get_current_price(symbol) or 0.0
            reason = item.get('exit_reason', 'Manual Position Override')
            
            # Match position
            pos = self.db.get_position_by_id(pos_id) if pos_id else (self.db.get_open_positions(symbol)[0] if self.db.get_open_positions(symbol) else None)
            if pos:
                self.db.close_position(pos['id'], exit_px, reason)
                self.db.record_processed_override(override_id, symbol, pos['id'], action, exit_px, pos['remaining_qty'], reason)
                logger.info(f"[MANUAL OVERRIDE] Position {pos['id']} ({symbol}) cleanly closed in DB at ${exit_px:.2f} ({reason})")

    def run_sell_guardian(self):
        """Monitors open positions for stop-loss, profit-taking, and structural TES"""
        open_positions = self.db.get_open_positions()
        if not open_positions: return
        
        is_first_hour = self.is_first_hour()
        market_down = self.is_market_opening_down() if is_first_hour else False
        suppress_first_hour = is_first_hour and market_down and self.config.get('first_hour_guard', 'suppress_sl', True)
        is_closing = self.is_closing_window()
        
        for position in open_positions:
            symbol = position['symbol']
            curr_price = self.data_fetcher.get_current_price(symbol)
            if curr_price is None: continue
            
            # 1. Update Trailing Stop Stepper
            self.position_manager.update_trailing_stop_loss(position, current_price=curr_price)
            
            # 2. Check Stop Loss (Respects Closing-Basis & First-Hour Guard)
            if self.position_manager.check_stop_loss(position, curr_price, is_closing_window=is_closing, is_first_hour_suppressed=suppress_first_hour):
                logger.warning(f"[{symbol}] STOP LOSS TRIGGERED at ${curr_price:.2f}")
                self.position_manager.execute_full_exit(position, curr_price, "Stop Loss")
                continue
                
            # 3. Check 4-Tier Partial Exits & Runner Mode
            partial_exits = self.position_manager.check_partial_exit_targets(position, curr_price)
            for t_name, qty, t_price in partial_exits:
                self.position_manager.execute_partial_exit(position, t_name, qty, curr_price)
                
            # 4. Check Dynamic Structural TES
            df_sym = self.data_fetcher.get_daily_bars(symbol, days=40)
            if not suppress_first_hour and self.position_manager.check_time_exit(position, df_sym):
                logger.warning(f"[{symbol}] TIME EXIT SIGNAL (TES) triggered")
                self.position_manager.execute_full_exit(position, curr_price, "TES")
                continue

    def run_buy_hunter(self):
        """Scans watchlist during buy window and manages signal queue"""
        if not self.is_buy_window(): return
        
        if self.signal_queue.is_window_complete():
            top_signals = self.signal_queue.get_top_signals(self.analyzer)
            open_positions = self.db.get_open_positions()
            max_positions = self.config.get('trading_rules', 'max_open_positions', 15)
            avail = max(0, max_positions - len(open_positions))
            
            for symbol, details in top_signals[:avail]:
                if self.config.get('trading_rules', 'prevent_same_day_reentry', True) and self.db.was_traded_today(symbol):
                    continue
                if self.position_manager.execute_buy(symbol, details):
                    self.db.log_signal(symbol, details, executed=True)
                    
            self.signal_queue.reset()
            return
            
        # Collection Phase
        watchlist_file = self.config.get('trading_rules', 'watchlist_file', 'config/watchlist.txt')
        if not os.path.exists(watchlist_file): return
        with open(watchlist_file, 'r') as f:
            symbols = [line.strip().upper() for line in f if line.strip()]
            
        for symbol in symbols:
            valid, details = self.analyzer.analyze_entry_signal(symbol)
            if valid:
                self.signal_queue.add_signal(symbol, details)
                logger.info(f"[{symbol}] Staged in Buy Queue: Score {details.get('score')}/5")

    def run(self):
        """Master execution loop"""
        logger.info("Starting master execution loop...")
        while True:
            try:
                self.process_manual_overrides()
                if self.is_market_open():
                    self.run_sell_guardian()
                    self.run_buy_hunter()
                    interval = 60 if self.is_buy_window() else 120
                    time.sleep(interval)
                else:
                    logger.info("Market closed. Sleeping 5 minutes...")
                    time.sleep(300)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    bot = RajatAlphaTradingBot(config_path='config/config.json')
    bot.run()
