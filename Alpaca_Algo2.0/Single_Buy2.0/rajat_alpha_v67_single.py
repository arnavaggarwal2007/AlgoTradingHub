"""
================================================================================
RAJAT ALPHA V67 - ALPACA ALGORITHMIC TRADING BOT (INSTITUTIONAL UPGRADE V3.2)
================================================================================

STRATEGY: Multi-Timeframe Institutional Momentum & Pullback Swing Engine
PLATFORM: Alpaca Trading API (Paper & Live Trading Support)
VERSION: 3.2 (Production Institutional Grade)
DATE: October 17, 2026

CORE STRATEGY & RISK MANAGEMENT LOGIC:
1. Signal Generation Pipeline (Prioritized Institutional Cascade):
   - Gate 0: Market Regime Gate (SPY & QQQ > 50 SMA when enabled)
   - Gate 1 & 1.5: Market Structure & Regime-Adaptive Slope (EMA21 > SMA50 > SMA200, Close > SMA200)
   - Gate 2: Preceding Impulse Wave & Orderly Retracement (Swing High >= 5% above EMA21 within 20 bars, retracing >= 3%)
   - Gate 3: Pattern Confirmation (Engulfing, Piercing, Tweezer, Hammer, Upside Reversal) OR Qualified Touch
   - Gate 4: Weekly MTF Trend Gate (Weekly Close > Weekly EMA21; mandatory prerequisite)
   - Gate 5: Demand Zone Proximity (Low <= 21-day Low * 1.035)
   - Gate 6: Exhaustion Filters (Shooting Star Rejection, Stalling < 5% 8d range, Extension Gap > 4%)
   - Informational: IBD-Style RS Composite Rating (0–100) displayed in console/audit logs and DB (not added to score)
   - Gate 7: Conviction Score (Total out of 7.0: Pattern + Weekly + Demand + RSI>50 + Monthly + Volume + Touch State >= 4.0)
   - Special: Touch-Only Dual Gate (Requires Score >= 5.0 AND Bullish Real Body >= 50% closing in upper third)

2. Risk Management & Execution Architecture:
   - Initial Stop Loss: Hybrid ATR-adaptive SL (1.5x - 2.5x ATR, capped at 17%, floored at 5%)
   - Multi-Stage Stop Loss Stepper:
     * Stage 1 (+5% Gain): SL moves to -4.0% below entry (cuts open risk from -17% to -4%)
     * Stage 2 (+8% Gain): SL moves to +1.0% above buy price (locks in guaranteed positive exit)
     * Stage 3 (+10% Gain): SL locks in +3.0% net profit
     * Stage 4 / Ratchet (+15% Gain = +5% above Stage 3): SL moves to Stage 3 level (+10%) and ratchets +1% for each +1% advance
     * Adaptive Hybrid Stepper: Automatically routes high-ATR stocks (>3.5%) to ATR breathing room and low-ATR stocks to fixed milestones
     * Monotonic Guarantee: Stop loss mathematically never steps backward
   - True Closing-Basis Protection: Stop losses evaluated on confirmed daily close (15:55-16:00 ET)
   - First-Hour Volatility Guard: Suppresses loss exits during opening morning noise (09:30-10:30 ET) when market index is down
   - 4-Tier Partial Exits: 20% @ +5%, 25% @ +10%, 25% @ +15%, 30% Runner
   - Runner Mode Protocol: Position exempt from TES holding limits; trails 1:1 indefinitely
   - Dynamic Structural TES Engine: 21-day base hold; grants +10-day extensions if consolidating >= 21 EMA (up to 41 days max)
   - Smart Order Execution Engine (SOEE): Midpoint limit order pegging to eliminate the Jobbing Disadvantage (-0.40% to -0.80% round-trip)
   - Fast 1-Line Manual Overrides via config/selllist.txt (e.g. 'AAPL', 'AAPL:SL:145.50', 'AAPL:TES:10') without modifying config.json

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
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus, OrderType, OrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.enums import DataFeed
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

file_handler = logging.FileHandler('logs/rajat_alpha_v67.log', encoding='utf-8')
json_formatter = ComplianceJSONFormatter(
    '%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(line)s %(message)s'
)
file_handler.setFormatter(json_formatter)
logger.addHandler(file_handler)

audit_handler = logging.FileHandler('logs/audit.log', encoding='utf-8')
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
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
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
        
        # Ensure quantitative analytics columns exist (Safe Auto-Migration)
        for tbl, col, col_type in [
            ("positions", "cps", "REAL"),
            ("positions", "rvol", "REAL"),
            ("positions", "candle_pattern", "TEXT"),
            ("signal_history", "cps", "REAL"),
            ("signal_history", "rvol", "REAL")
        ]:
            try:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        self.conn.commit()
    
    def add_position(self, symbol: str, entry_price: float, quantity: int, 
                     stop_loss: float, score: float, pattern: str = 'Unknown',
                     initial_stop_loss: Optional[float] = None,
                     rs_score: Optional[float] = None,
                     cps: Optional[float] = None,
                     rvol: Optional[float] = None,
                     candle_pattern: Optional[str] = None) -> int:
        """Add new position to database with institutional metrics"""
        cursor = self.conn.cursor()
        init_sl = initial_stop_loss if initial_stop_loss is not None else stop_loss
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, quantity, 
                                   remaining_qty, stop_loss, initial_stop_loss,
                                   score, pattern, highest_price_seen, sl_stage, 
                                   is_runner, tes_extensions_count, rs_score,
                                   cps, rvol, candle_pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?)
        ''', (symbol, datetime.now().isoformat(), entry_price, quantity, 
              quantity, stop_loss, init_sl, score, pattern, entry_price, rs_score,
              cps, rvol, candle_pattern))
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
            SET remaining_qty = max(0, remaining_qty - ?)
            WHERE id = ?
        ''', (quantity, position_id))
        
        # Auto-close position if remaining quantity reaches 0 (Prevents zero-share ghost records)
        cursor.execute('''
            UPDATE positions 
            SET status = 'CLOSED', 
                exit_date = ?,
                exit_price = ?,
                exit_reason = 'Partial Exits Complete'
            WHERE id = ? AND remaining_qty <= 0
        ''', (datetime.now().isoformat(), exit_price, position_id))
        self.conn.commit()

    def update_position_status(self, position_id: int, status: str, exit_reason: Optional[str] = None):
        """Update status and optional exit reason for a position (used for reconciliation)"""
        cursor = self.conn.cursor()
        if exit_reason:
            cursor.execute('''
                UPDATE positions 
                SET status = ?, exit_reason = ?, exit_date = ?
                WHERE id = ?
            ''', (status, exit_reason, datetime.now().isoformat(), position_id))
        else:
            cursor.execute('''
                UPDATE positions 
                SET status = ?
                WHERE id = ?
            ''', (status, position_id))
        self.conn.commit()

    def update_position_quantity(self, position_id: int, new_qty: int):
        """Update remaining_qty to reconcile with actual broker quantity"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE positions 
            SET remaining_qty = ?
            WHERE id = ?
        ''', (new_qty, position_id))
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
                                        price, reason, executed, rs_score, candle_pattern,
                                        cps, rvol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, datetime.now().isoformat(), signal_details.get('score', 0),
              signal_details.get('pattern', 'None'), signal_details.get('price', 0),
              signal_details.get('reason', ''), 1 if executed else 0,
              signal_details.get('rs_score'), signal_details.get('candle_pattern'),
              signal_details.get('cps'), signal_details.get('rvol')))
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
    
    def get(self, *args, **kwargs) -> Any:
        """
        Flexible configuration getter:
          get(top_level_key, default=None)
          get(section, key, default=None)
        """
        default = kwargs.get('default', None)
        if len(args) == 1:
            return self.config.get(args[0], default)
        elif len(args) == 2:
            section, second = args
            if section in self.config:
                val = self.config[section]
                if isinstance(val, dict) and isinstance(second, str) and second in val:
                    return val[second]
                if not isinstance(val, dict) or not isinstance(second, str):
                    return val
                return second
            return second
        elif len(args) >= 3:
            section, key, default_val = args[0], args[1], args[2]
            sec = self.config.get(section, {})
            if isinstance(sec, dict):
                return sec.get(key, default_val)
            return default_val
        return default

    def __getitem__(self, item):
        return self.config[item]

    def __setitem__(self, key, value):
        self.config[key] = value

    def __contains__(self, item):
        return item in self.config

# ================================================================================
# MARKET DATA FETCHER (With API Resilience & Midpoint Quotes)
# ================================================================================

class MarketDataFetcher:
    """Handles all market data retrieval, retry caching, and quote fetching"""
    
    def __init__(self, data_client: StockHistoricalDataClient, feed: str = 'sip'):
        self.data_client = data_client
        self.feed = feed or 'sip'
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
    
    @with_api_retry(max_retries=3, base_delay=1.0)
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get latest price with retry, quote fallback, and cached price fallback"""
        # 1. Attempt latest trade bar
        try:
            params = StockLatestBarRequest(symbol_or_symbols=symbol)
            bars = self.data_client.get_stock_latest_bar(params)
            if symbol in bars and bars[symbol] is not None:
                price = float(bars[symbol].close)
                self.last_valid_price[symbol] = price
                return price
        except Exception as e:
            logger.warning(f"[{symbol}] Direct bar query encounter: {e}. Attempting midpoint quote fallback...")
            # Fallback to quote
            quote = self.get_latest_quote(symbol)
            if quote and quote.get('mid'):
                mid = float(quote['mid'])
                self.last_valid_price[symbol] = mid
                return mid
            if symbol in self.last_valid_price:
                return self.last_valid_price[symbol]
            raise e
        
        # 2. Try quote fallback if bar was empty/None
        quote = self.get_latest_quote(symbol)
        if quote and quote.get('mid'):
            mid = float(quote['mid'])
            self.last_valid_price[symbol] = mid
            return mid
            
        return self.last_valid_price.get(symbol)

    @with_api_retry(max_retries=3, base_delay=1.0)
    def get_latest_quote(self, symbol: str, current_price: Optional[float] = None) -> Optional[Dict]:
        """Fetch current bid, ask, and midpoint quote with SIP consolidated preference and sanitization"""
        try:
            quote = None
            # 1. Attempt SIP Consolidated feed first
            try:
                feed_choice = DataFeed.SIP if self.feed == 'sip' else DataFeed.IEX
                params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=feed_choice)
                quotes = self.data_client.get_stock_latest_quote(params)
                if symbol in quotes and quotes[symbol] is not None:
                    quote = quotes[symbol]
            except Exception:
                # 2. Fallback to IEX if SIP is unpermitted
                try:
                    params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
                    quotes = self.data_client.get_stock_latest_quote(params)
                    if symbol in quotes and quotes[symbol] is not None:
                        quote = quotes[symbol]
                except Exception:
                    pass

            if quote is not None:
                bp = float(quote.bid_price)
                ap = float(quote.ask_price)
                if bp > 0 and ap > 0 and ap >= bp:
                    mid = round((bp + ap) / 2.0, 2)
                    spread = round(ap - bp, 2)
                    
                    # Sanity guard against fragmented illiquid book quotes
                    if current_price and current_price > 0:
                        dev_pct = abs(mid - current_price) / current_price
                        spread_pct = spread / mid if mid > 0 else 0
                        if dev_pct > 0.02 or spread_pct > 0.03:
                            logger.warning(
                                f"[{symbol}] Distorted book detected: Mid ${mid:.2f} vs Market ${current_price:.2f} "
                                f"({dev_pct*100:.1f}% dev, Spread: ${spread:.2f} | {spread_pct*100:.1f}%). Rejecting quote."
                            )
                            return None
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
        
        # 30-Minute Market Regime Cache
        self._regime_cache_time = None
        self._regime_cache_value = True
    
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
        """Verify broad market regime (SPY & QQQ > configured SMA) with 30-minute caching"""
        enable_gate = self.config.get('market_regime', 'enable_index_gate', True)
        above_sma_req = self.config.get('market_regime', 'index_above_sma_required',
                        self.config.get('market_regime', 'index_above_sma50_required', True))
        if not (enable_gate and above_sma_req):
            return True
            
        now = datetime.now()
        if self._regime_cache_time and (now - self._regime_cache_time).total_seconds() < 1800:
            return self._regime_cache_value
            
        index_symbols = self.config.get('market_regime', 'index_symbols', ["SPY", "QQQ"])
        ma_period = int(self.config.get('market_regime', 'index_ma_period', 50))
        is_bullish = True
        eval_notes = []
        # Ensure sufficient calendar days to cover weekends and market holidays
        calendar_days = max(365, int(ma_period * 1.5) + 60)
        for idx_sym in index_symbols:
            df_idx = self.data_fetcher.get_daily_bars(idx_sym, days=calendar_days)
            if df_idx is not None and len(df_idx) >= ma_period:
                sma_val = ta.sma(df_idx['close'], length=ma_period).iloc[-1]
                last_close = df_idx['close'].iloc[-1]
                eval_notes.append(f"{idx_sym}: ${last_close:.2f} ({ma_period} SMA: ${sma_val:.2f})")
                if last_close < sma_val:
                    is_bullish = False
        
        self._regime_cache_time = now
        self._regime_cache_value = is_bullish
        
        notes_str = " | ".join(eval_notes) if eval_notes else "Indices checked"
        if not is_bullish:
            logger.info(f"[MARKET REGIME] Gate ACTIVE (Defensive Mode): {notes_str}. New buys suspended.")
        else:
            logger.info(f"[MARKET REGIME] Market Bullish: {notes_str}. Normal trading enabled.")
            
        return is_bullish

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
                        pattern_weight: float = 1.0, rs_score: float = 50.0,
                        in_demand_zone: bool = False) -> float:
        """
        Computes comprehensive score across technicals, MTF, volume, touch, and pattern.
        Note: IBD RS is kept for informational logging, queue tie-break, and DB storage, 
        and is NOT added to the numerical score calculation.
        """
        curr = df.iloc[-1]
        score = 0.0
        
        # 1. Pattern score weight (Engulfing: 1.0, Piercing: 1.0, Hammer: 0.8, Tweezer: 0.8, UpsideReversal: 0.6)
        if pattern_found:
            score += pattern_weight
            
        # 2. Weekly MTF confirmation
        if weekly_ok: 
            score += 1.0
            
        # 3. Demand Zone Proximity (within 3.5% of 21-day low)
        low_21 = df['low'].iloc[-21:].min() if len(df) >= 21 else curr['low']
        if in_demand_zone or (curr['low'] <= low_21 * 1.035):
            score += 1.0
            
        # 4. RSI Momentum (>50)
        rsi_val = curr.get('RSI14')
        if not pd.isna(rsi_val) and rsi_val > 50:
            score += 1.0
            
        # 5. Monthly MTF confirmation
        if monthly_ok: 
            score += 1.0
        
        # 6. Volume above 21-day average
        if curr['volume'] > curr.get('VOL_SMA21', 0):
            score += 1.0
            
        # 7. Isolated Touch state bonuses
        state = self.symbol_touch_state.get(symbol, {'ema21_count': 0, 'sma50_count': 0})
        if state['ema21_count'] == 1: score += 1.0
        elif state['ema21_count'] == 2: score += 0.5
        
        if state['sma50_count'] == 1: score += 1.0
        elif state['sma50_count'] == 2: score += 0.5
            
        return round(score, 1)

    def analyze_entry_signal(self, symbol: str) -> Tuple[bool, Dict]:
        """
        Full Institutional Entry Signal Analysis with prioritized Gate Sequence:
        GATE 0: Broad Market Regime Gate (SPY & QQQ > 50 SMA)
        GATE 1: Market Structure (50 SMA > 200 SMA, 21 EMA >= 50 SMA - 2.5% tolerance)
        GATE 1.5: Regime-Adaptive MA Slope
        GATE 2: Preceding Impulse & Orderly Pullback Sequence
        GATE 3: Reversal Candlestick Pattern OR Qualified Touch
        GATE 4: Weekly Multi-Timeframe Confirmation (Close > Weekly EMA21)
        GATE 5: Demand Zone Proximity Check
        GATE 6: Stalling, Extension, Green Session & Shooting Star Rejection Filters
        GATE 7: Comprehensive Scoring (out of 7.0) & Touch-Only Dual Gate
        """
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
        ma_period = int(self.config.get('market_regime', 'index_ma_period', 50))
        if not self.check_market_regime():
            result['reason'] = f"Broad market regime not bullish (SPY/QQQ < {ma_period} SMA)"
            logger.info(f"[{symbol}] ❌ Gate 0 Market Regime: FAILED (SPY/QQQ < SMA{ma_period})")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 0 Market Regime: PASSED - Broad market bullish (SPY/QQQ > {ma_period} SMA)")

        # GATE 1: Market Structure
        structure_ok = self.check_market_structure(df_daily)
        result['checks']['market_structure'] = structure_ok
        if not structure_ok:
            result['reason'] = "Market structure failed (50 SMA > 200 SMA required)"
            logger.info(f"[{symbol}] ❌ Gate 1 Market Structure: FAILED (SMA50 <= SMA200)")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 1 Market Structure: PASSED - Bullish alignment confirmed")

        # GATE 1.5: Regime-Adaptive MA Slope
        if not self.check_ma_slopes(symbol, df_daily):
            result['reason'] = "50 SMA slope negative in non-bull regime"
            logger.info(f"[{symbol}] ❌ Gate 1.5 MA Slope: FAILED (SMA50 downward slope)")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 1.5 MA Slope: PASSED - Moving average slope verified")

        # GATE 2: Preceding Impulse & Orderly Retracement (First criteria: valid pullback)
        pullback_ok = self.check_pullback(df_daily)
        result['checks']['pullback'] = pullback_ok
        if not pullback_ok:
            result['reason'] = "No valid preceding impulse and pullback sequence"
            logger.info(f"[{symbol}] ❌ Gate 2 Pullback: FAILED (No valid impulse + pullback near MAs)")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 2 Pullback: PASSED - Valid pullback confirmed with downtrend")

        # GATE 3: Candlestick Pattern OR Qualified Touch (Pattern formation after pullback)
        pattern_cfg = self.config.get('pattern_config', {})
        pat_found, pat_name, pat_tier, pat_weight = PatternDetector.has_pattern(df_daily, pattern_cfg)
        touch_found, touch_type = self.check_touch_based_signal(df_daily)
        
        if not (pat_found or touch_found):
            result['reason'] = "No recognized reversal pattern or qualified touch after pullback"
            logger.info(f"[{symbol}] ❌ Gate 3 Setup Pattern/Touch: FAILED (No qualifying pattern or touch)")
            return False, result
        else:
            sig_parts = []
            if pat_found: sig_parts.append(f"Pattern: {pat_name}")
            if touch_found: sig_parts.append(f"Touch: {touch_type}")
            logger.info(f"[{symbol}] ✅ Gate 3 Signal Check: PASSED - {' + '.join(sig_parts)} detected")

        result['checks']['pattern'] = pat_found
        result['checks']['touch_signal'] = touch_found
        result['candle_pattern'] = pat_name

        # GATE 4: Weekly Multi-Timeframe Confirmation
        weekly_ok, monthly_ok = self.check_multitimeframe_confirmation(df_daily, df_weekly, df_monthly)
        result['checks']['weekly_ok'] = weekly_ok
        result['checks']['monthly_ok'] = monthly_ok
        if not weekly_ok:
            result['reason'] = "Weekly MTF failed (Weekly Close <= Weekly EMA21)"
            logger.info(f"[{symbol}] ❌ Gate 4 Weekly MTF: FAILED (Weekly Close <= Weekly EMA21)")
            return False, result
        else:
            mtf_desc = "Both weekly and monthly aligned" if monthly_ok else "Weekly alignment confirmed"
            logger.info(f"[{symbol}] ✅ Gate 4 MTF Confirmation: PASSED - {mtf_desc}")

        # GATE 5: Demand Zone Proximity Check
        curr_candle = df_daily.iloc[-1]
        low_21 = df_daily['low'].iloc[-21:].min() if len(df_daily) >= 21 else curr_candle['low']
        in_demand_zone = curr_candle['low'] <= (low_21 * 1.035)
        result['checks']['demand_zone'] = in_demand_zone
        if in_demand_zone:
            logger.info(f"[{symbol}] ✅ Gate 5 Demand Zone: PASSED - In institutional demand zone (<= 3.5% above 21d low)")

        # GATE 6: Stalling Filter
        if self.check_stalling(df_daily):
            result['reason'] = "Stock is in horizontal sideways consolidation"
            logger.info(f"[{symbol}] ❌ Gate 6 Stalling: FAILED (Horizontal consolidation detected)")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 6 Stalling Filter: PASSED - No consolidation detected")

        # GATE 6.25: Extended Stock Filter (Gap > 4%)
        curr_price = self.data_fetcher.get_current_price(symbol)
        if curr_price is None:
            curr_price = float(df_daily.iloc[-1]['close'])
            
        if self.config.get('strategy_params', 'enable_extended_filter', True):
            is_ext, gap_pct = self.check_extended_stock(df_daily, curr_price)
            if is_ext:
                result['reason'] = f"Stock is EXTENDED (Gap up {gap_pct*100:.2f}%)"
                logger.info(f"[{symbol}] ❌ Gate 6.25 Extended: FAILED (Gap up {gap_pct*100:.2f}%)")
                return False, result
            else:
                logger.info(f"[{symbol}] ✅ Gate 6.25 Extended Filter: PASSED - Gap within allowed threshold ({gap_pct*100:.2f}%)")

        # GATE 6.5: Green Session Confirmation with Absorption Reversal Exemption
        prev_close = df_daily.iloc[-2]['close']
        if curr_price <= prev_close:
            c_range = curr_candle['high'] - curr_candle['low']
            lower_wick = min(curr_candle['close'], curr_candle['open']) - curr_candle['low']
            wick_ratio = lower_wick / c_range if c_range > 0 else 0.0
            close_pos = (curr_candle['close'] - curr_candle['low']) / c_range if c_range > 0 else 0.0
            within_1pct = curr_price >= (prev_close * 0.99)
            
            # Buyer absorption reversal: long lower wick >= 55% of range, closes in upper 30% of range (close_pos >= 0.70), within 1% of prev close
            is_absorption = (wick_ratio >= 0.55 and close_pos >= 0.70 and within_1pct)
            
            if is_absorption:
                logger.info(f"[{symbol}] 🛡️ Gate 6.5 Absorption Reversal Active: Session slightly red (${curr_price:.2f} <= ${prev_close:.2f}), "
                            f"but buyer absorption verified (Lower wick: {wick_ratio*100:.1f}%, Close pos: {close_pos*100:.1f}%). "
                            f"Passing with partial conviction (weight=0.5).")
                pat_weight = 0.5
                if not pat_found:
                    pat_found = True
                    result['candle_pattern'] = 'Absorption Hammer'
                else:
                    result['candle_pattern'] = f"{result['candle_pattern']} (Absorption)"
            else:
                result['reason'] = f"Stock is RED today (${curr_price:.2f} <= ${prev_close:.2f})"
                logger.info(f"[{symbol}] ❌ Gate 6.5 Green Candle: FAILED (RED today: ${curr_price:.2f} <= ${prev_close:.2f})")
                return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 6.5 GREEN CANDLE FILTER: PASSED - Green today (${curr_price:.2f} > ${prev_close:.2f})")

        # GATE 6.75: Shooting Star Rejection Filter (MANDATORY)
        max_wick = self.config.get('candle_quality', 'max_upper_wick_ratio', 0.50)
        max_w2b = self.config.get('candle_quality', 'max_wick_to_body_ratio', 2.0)
        if PatternDetector.is_shooting_star(curr_candle, max_wick, max_w2b):
            result['reason'] = "Shooting star rejection: Upper wick indicates heavy seller distribution"
            logger.info(f"[{symbol}] ❌ Gate 6.75 Shooting Star: FAILED (Upper shadow spans >50% of range)")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 6.75 Shooting Star Filter: PASSED - No excessive upper wick rejection")

        # Compute IBD Relative Strength Composite (0-100) — Informational & Tie-Breaker
        rs_score = self.calculate_rs_composite(symbol, df_daily)
        result['rs_score'] = rs_score

        # Optional Hard RS cutoff if explicitly configured
        if self.config.get('relative_strength', 'enable', False):
            min_rs = self.config.get('relative_strength', 'min_rs_rating', 40.0)
            if rs_score < min_rs:
                result['reason'] = f"Relative Strength rating too low: {rs_score:.1f} < {min_rs}"
                logger.info(f"[{symbol}] ❌ RS Rating Filter: FAILED ({rs_score:.1f} < {min_rs})")
                return False, result

        # GATE 7: Scoring & Touch-Only Dual Gate
        score = self.calculate_score(df_daily, symbol, weekly_ok, monthly_ok, pat_found, touch_found, pat_weight, rs_score, in_demand_zone=in_demand_zone)
        result['score'] = score
        min_score = self.config.get('strategy_params', 'min_signal_score', 4.0)
        
        # Touch-Only Dual Gate: If no pattern, require higher score bar + bullish body
        if not pat_found and touch_found:
            min_touch_score = self.config.get('trading_rules', 'min_touch_only_score', min_score)
            if score < min_touch_score:
                result['reason'] = f"Touch-only score {score:.1f} below required {min_touch_score}"
                logger.info(f"[{symbol}] ❌ Gate 7 Touch Score: FAILED ({score:.1f} < {min_touch_score})")
                return False, result
                
            body_size = abs(curr_candle['close'] - curr_candle['open'])
            total_range = curr_candle['high'] - curr_candle['low']
            body_ratio = body_size / total_range if total_range > 0 else 0
            close_pos = (curr_candle['close'] - curr_candle['low']) / total_range if total_range > 0 else 0
            
            if body_ratio < 0.50 or close_pos < 0.67:
                result['reason'] = "Touch-only candle failed bullish conviction confirmation"
                logger.info(f"[{symbol}] ❌ Gate 7 Touch Conviction: FAILED (Weak candle body or close position)")
                return False, result

        if score < min_score:
            result['reason'] = f"Score {score:.1f} below minimum {min_score}"
            logger.info(f"[{symbol}] ❌ Gate 7 Minimum Score: FAILED (Score {score:.1f} < {min_score})")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Gate 7 Score Check: PASSED - Score {score:.1f}/7.0 meets minimum {min_score} (RS: {rs_score:.1f})")

        # Valid Signal
        signal_types = []
        if pat_found: signal_types.append('swing')
        if touch_found:
            signal_types.append('21Touch' if touch_type == "EMA21_Touch" else '50Touch')
            
        # Multi-factor metrics for Institutional Composite Priority Scoring (CPS)
        vol_sma21 = float(df_daily['volume'].iloc[-21:].mean()) if len(df_daily) >= 21 else float(df_daily['volume'].mean())
        curr_vol = float(curr_candle['volume'])
        rvol = round(curr_vol / vol_sma21, 2) if vol_sma21 > 0 else 1.0

        ema21_col = 'EMA21' if 'EMA21' in df_daily.columns else ('ema_21' if 'ema_21' in df_daily.columns else 'ema21')
        sma50_col = 'SMA50' if 'SMA50' in df_daily.columns else ('sma_50' if 'sma_50' in df_daily.columns else 'sma50')
        ema21_series = df_daily[ema21_col]
        sma50_series = df_daily[sma50_col]

        ema21_now = float(ema21_series.iloc[-1])
        ema21_prev5 = float(ema21_series.iloc[-6]) if len(df_daily) >= 6 else float(ema21_series.iloc[0])
        slope_21_pct = round(((ema21_now - ema21_prev5) / ema21_prev5) * 100.0, 2) if ema21_prev5 > 0 else 0.0

        sma50_now = float(sma50_series.iloc[-1])
        sma50_prev20 = float(sma50_series.iloc[-21]) if len(df_daily) >= 21 else float(sma50_series.iloc[0])
        slope_50_pct = round(((sma50_now - sma50_prev20) / sma50_prev20) * 100.0, 2) if sma50_prev20 > 0 else 0.0

        dist_to_ema21_pct = round(abs(curr_price - ema21_now) / ema21_now * 100.0, 2) if ema21_now > 0 else 0.0
        dollar_volume = float(curr_price * vol_sma21)
        candle_weight = float(pat_weight) if pat_found else 0.40

        result['signal'] = True
        result['signal_types'] = signal_types
        result['pattern'] = '+'.join(signal_types) if signal_types else 'Touch-Only'
        result['price'] = curr_price
        result['rvol'] = rvol
        result['slope_21_pct'] = slope_21_pct
        result['slope_50_pct'] = slope_50_pct
        result['dist_to_ema21_pct'] = dist_to_ema21_pct
        result['dollar_volume'] = dollar_volume
        result['candle_weight'] = candle_weight
        result['reason'] = f"VALID BUY SIGNAL - Types:{result['pattern']} Score:{score:.1f} RS:{rs_score:.1f}"
        logger.info(f"[{symbol}] 🎯 FULL CRITERIA MET: Pattern: {result['pattern']} | Score: {score:.1f}/7.0 | IBD RS: {rs_score:.1f}/100 (Informational) | Price: ${curr_price:.2f}")
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
        self.daily_sl_steps = []
        self.daily_buys = []
        self.daily_exits = []

    def calculate_position_size(self, symbol: str, current_price: float, stop_loss: Optional[float] = None) -> Tuple[int, float]:
        """
        Calculates position sizing according to configured sizing_mode:
        
        1. 'capital_pct' (Default / Institutional Baseline):
           - Sized by percent of account equity per trade (e.g. 3.0%)
           - trade_amount = equity * per_trade_pct
           - shares = trade_amount / current_price
           
        2. 'risk_based' (Equal Risk Contribution / Volatility Parity):
           - Sized by target dollar risk per trade divided by distance to Stop Loss
           - dollar_risk = fixed_risk_dollars if > 0 else (equity * risk_per_trade_pct)
           - delta_sl = current_price - stop_loss
           - shares = int(dollar_risk / delta_sl)
           
        Institutional Guardrails Enforced Across Both Modes:
        - Max per-stock allocation cap (e.g. max 6% of equity in any single ticker)
        - Remaining stock headroom deduction if ticker already held
        - Portfolio max equity utilization limit (e.g. 90%)
        - Capital conservation mode (halves sizing if portfolio utilization >= 70% of max limit)
        - Division-by-zero / minimum delta SL protection (floored at min_initial_sl_pct)
        - Minimum shares sanity checks (returns 0 if cannot afford 1 share)
        """
        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
        except Exception as e:
            logger.error(f"Failed to get account equity: {e}")
            return 0, 0.0

        if equity <= 0 or current_price <= 0:
            logger.warning(f"[{symbol}] Invalid equity (${equity}) or current price (${current_price})")
            return 0, 0.0

        sizing_mode = str(self.config.get('trading_rules', 'sizing_mode', 'capital_pct')).lower()
        max_allocation_per_stock_pct = float(self.config.get('trading_rules', 'max_allocation_per_stock_pct', 0.06))
        max_utilization_pct = float(self.config.get('trading_rules', 'max_equity_utilization_pct', 0.90))

        # 1. Calculate current allocation for this stock
        open_positions = self.db.get_open_positions(symbol=symbol)
        current_allocation = sum(pos['entry_price'] * pos['remaining_qty'] for pos in open_positions)
        current_allocation_pct = current_allocation / equity if equity > 0 else 0.0

        # Remaining allocation headroom for this stock in dollars and percentage
        max_stock_capital_allowed = round(max(0.0, (equity * max_allocation_per_stock_pct) - current_allocation), 2)
        remaining_pct = max_stock_capital_allowed / equity if equity > 0 else 0.0
        if max_stock_capital_allowed < current_price:
            logger.warning(f"[{symbol}] Per-stock allocation limit reached ({current_allocation_pct*100:.1f}% / {max_allocation_per_stock_pct*100:.1f}%), cannot add more")
            return 0, 0.0

        # 2. Portfolio-level total allocation & utilization
        total_open = self.db.get_open_positions()
        total_current_allocation = sum(pos['entry_price'] * pos['remaining_qty'] for pos in total_open)
        available_portfolio_capital = round(max(0.0, (equity * max_utilization_pct) - total_current_allocation), 2)

        if available_portfolio_capital < current_price:
            logger.warning(f"[{symbol}] Overall utilization limit reached ({total_current_allocation/equity*100:.1f}% / {max_utilization_pct*100:.1f}%), blocking trade")
            return 0, 0.0

        # 3. Sizing logic based on configured mode
        if sizing_mode == 'risk_based':
            # Target dollar risk: either fixed dollar amount (e.g. $500) or equity percentage (e.g. 0.5%)
            fixed_dollars = float(self.config.get('trading_rules', 'fixed_risk_dollars', 0.0))
            risk_pct = float(self.config.get('trading_rules', 'risk_per_trade_pct', 0.005))
            dollar_risk = fixed_dollars if fixed_dollars > 0 else (equity * risk_pct)

            # Determine risk distance per share (delta_sl = current_price - stop_loss)
            min_sl_pct = float(self.config.get('risk_management', 'min_initial_sl_pct', 0.05))
            if stop_loss is None or stop_loss >= current_price or (current_price - stop_loss) <= 0:
                delta_sl = current_price * min_sl_pct
                logger.info(f"[{symbol}] Stop loss not provided or invalid (${stop_loss}); using {min_sl_pct*100:.1f}% risk distance (${delta_sl:.2f})")
            else:
                delta_sl = current_price - stop_loss

            # Ensure minimum delta_sl floor to prevent division by near-zero
            min_floor_dist = max(0.10, current_price * 0.005)
            delta_sl = max(delta_sl, min_floor_dist)

            raw_shares = int(dollar_risk / delta_sl)
            trade_amount = raw_shares * current_price

            # Capital conservation mode check (halves size if utilization >= 70% of max limit)
            if self.config.get('trading_rules', 'capital_conservation_mode', False):
                if (total_current_allocation / equity) >= (max_utilization_pct * 0.70):
                    trade_amount = trade_amount * 0.5
                    logger.info(f"[{symbol}] Capital conservation mode active: Risk-based trade allocation halved")

            # Apply stock allocation ceiling (cannot exceed remaining per-stock limit)
            if trade_amount > max_stock_capital_allowed:
                trade_amount = max_stock_capital_allowed

            # Apply portfolio headroom ceiling
            if trade_amount > available_portfolio_capital:
                trade_amount = available_portfolio_capital

            shares = int((trade_amount + 1e-4) / current_price)
            actual_amount = shares * current_price

            if shares <= 0:
                logger.warning(f"[{symbol}] Risk-based shares resulted in 0 after applying caps")
                return 0, 0.0

            logger.info(f"[{symbol}] Position Sizing [RISK-BASED]: Target Risk=${dollar_risk:.2f}, SL Dist=${delta_sl:.2f} ({(delta_sl/current_price)*100:.1f}%), Raw Shares={raw_shares} -> Final Shares={shares} (${actual_amount:.2f}, {actual_amount/equity*100:.1f}% equity)")
            return shares, actual_amount

        else:
            # Standard Capital % Allocation (Default 3% per trade)
            trade_pct = float(self.config.get('trading_rules', 'per_trade_pct', 0.03))
            effective_trade_pct = min(trade_pct, remaining_pct)

            # Capital conservation mode check
            if self.config.get('trading_rules', 'capital_conservation_mode', False):
                if (total_current_allocation / equity) >= (max_utilization_pct * 0.70):
                    effective_trade_pct = effective_trade_pct * 0.5

            trade_amount = equity * effective_trade_pct
            projected_utilization_pct = (total_current_allocation + trade_amount) / equity

            if projected_utilization_pct > max_utilization_pct:
                available_pct = max_utilization_pct - (total_current_allocation / equity)
                if available_pct <= 0.001:
                    logger.warning(f"[{symbol}] Overall utilization limit reached ({projected_utilization_pct*100:.1f}% / {max_utilization_pct*100:.1f}%), blocking trade")
                    return 0, 0.0
                trade_amount = equity * min(effective_trade_pct, available_pct)

            shares = int((trade_amount + 1e-4) / current_price)
            actual_amount = shares * current_price
            if shares <= 0:
                logger.warning(f"[{symbol}] Trade size too small after limits")
                return 0, 0.0

            logger.info(f"[{symbol}] Position Sizing [CAPITAL %]: Allocation={effective_trade_pct*100:.1f}%, Shares={shares} (${actual_amount:.2f})")
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

    def _extract_filled_qty(self, order_obj: Any) -> int:
        """Safely extract filled quantity from an order object, handling mocks and None."""
        if order_obj is None:
            return 0
        raw_qty = getattr(order_obj, 'filled_qty', None)
        if raw_qty is None:
            return 0
        if isinstance(raw_qty, (int, float)):
            return int(raw_qty)
        if isinstance(raw_qty, str):
            try:
                return int(float(raw_qty))
            except (ValueError, TypeError):
                return 0
        return 0

    def _get_broker_remaining_qty(self, symbol: str) -> Optional[int]:
        """Safely get actual remaining open position qty from broker, handling mocks and 404s."""
        try:
            broker_pos = self.trading_client.get_open_position(symbol)
            raw_qty = getattr(broker_pos, 'qty', None)
            if isinstance(raw_qty, (int, float)):
                return int(raw_qty)
            if isinstance(raw_qty, str):
                try:
                    return int(float(raw_qty))
                except (ValueError, TypeError):
                    pass
        except Exception as be:
            err_str = str(be).lower()
            if '404' in err_str or 'position does not exist' in err_str or 'not found' in err_str:
                return 0
        return None

    def _submit_sell_order_with_reconciliation(self, order_req: Any, position: Dict, current_price: float, reason: str) -> Tuple[Optional[Any], int]:
        """
        Submits a sell order. If rejected due to 'insufficient qty' (e.g. fast market partial fill),
        queries broker for actual available shares, reconciles DB remaining_qty, and resubmits
        for the true remaining quantity to prevent order desynchronization loops.
        Returns (order_obj_or_None, updated_remaining_qty).
        """
        symbol = position['symbol']
        pos_id = position['id']
        try:
            order = self.trading_client.submit_order(order_req)
            return order, order_req.qty
        except Exception as e:
            err_msg = str(e).lower()
            if 'insufficient qty' in err_msg or '403' in err_msg:
                logger.warning(f"[{symbol}] Order submission rejected for qty={order_req.qty} ('{e}'). Verifying broker position...")
                broker_qty = self._get_broker_remaining_qty(symbol)
                if broker_qty is not None:
                    if broker_qty <= 0:
                        logger.info(f"[{symbol}] Broker confirms 0 shares open. Position was already filled on broker.")
                        self.db.update_position_quantity(pos_id, 0)
                        position['remaining_qty'] = 0
                        self.db.close_position(pos_id, current_price, reason)
                        return None, 0
                    elif broker_qty < order_req.qty:
                        logger.warning(f"[{symbol}] Auto-reconciling qty from {order_req.qty} down to actual broker qty {broker_qty}...")
                        self.db.update_position_quantity(pos_id, broker_qty)
                        position['remaining_qty'] = broker_qty
                        order_req.qty = broker_qty
                        try:
                            order = self.trading_client.submit_order(order_req)
                            logger.info(f"[{symbol}] Successfully resubmitted reconciled order for {broker_qty} shares.")
                            return order, broker_qty
                        except Exception as re_e:
                            logger.error(f"[{symbol}] Resubmission failed for reconciled qty {broker_qty}: {re_e}")
                            return None, broker_qty
            logger.error(f"[{symbol}] Sell order submission failed: {e}")
            return None, order_req.qty

    def _wait_for_order_fill(self, order_id: Any, symbol: str, timeout_seconds: int = 15, poll_interval: float = 1.0) -> Tuple[bool, Optional[Any]]:
        """
        Polls Alpaca trading client until order reaches FILLED or terminal state.
        Returns (is_filled, filled_order_obj).
        """
        start_time = time.time()
        oid = str(order_id)
        last_status = None
        while time.time() - start_time < timeout_seconds:
            try:
                order = self.trading_client.get_order_by_id(oid)
                last_status = getattr(order, 'status', None)
                status_val = last_status.value if hasattr(last_status, 'value') else str(last_status)
                
                if status_val == 'filled' or last_status == OrderStatus.FILLED:
                    logger.info(f"[{symbol}] ✅ BROKER FILL CONFIRMED: Order ID {oid} filled {order.filled_qty} shares @ ${float(order.filled_avg_price or 0):.2f}")
                    return True, order
                    
                if status_val in ['canceled', 'expired', 'rejected']:
                    logger.warning(f"[{symbol}] Broker order {oid} reached terminal state: {status_val}")
                    return False, order
            except Exception as e:
                logger.warning(f"[{symbol}] Error polling order status for ID {oid}: {e}")
                
            time.sleep(poll_interval)
            
        logger.warning(f"[{symbol}] Order fill polling timed out after {timeout_seconds}s (Last status: {last_status})")
        return False, None

    def execute_buy(self, symbol: str, signal_details: Dict) -> bool:
        """
        Executes buy order via 3-Step Smart Order Execution Engine (SOEE) Escalation Ladder
        or Market Order, with strict Broker Fill Confirmation before any database persistence.
        """
        current_price = signal_details['price']
        score = signal_details.get('score', 4.0)
        
        df_daily = self.data_fetcher.get_daily_bars(symbol, days=50)
        stop_loss = self.calculate_stop_loss(symbol, current_price, score, df_daily)
        shares, target_val = self.calculate_position_size(symbol, current_price, stop_loss)
        
        if shares <= 0:
            logger.warning(f"[{symbol}] Calculated position size is 0 shares, aborting buy execution")
            return False
            
        use_smart_soee = self.config.get('execution_schedule', 'enable_smart_execution', True)
        quote = self.data_fetcher.get_latest_quote(symbol, current_price=current_price) if use_smart_soee else None
        
        step_timeout = int(self.config.get('execution_schedule', 'soee_step_timeout_seconds', 15))
        filled_order = None
        
        try:
            if use_smart_soee and quote and quote.get('mid', 0) > 0 and quote.get('spread', 0) > 0:
                mid_px = quote['mid']
                spread = quote['spread']
                ask_px = quote['ask']
                
                # --- STEP 1: Passive Midpoint Peg ---
                logger.info(f"[{symbol}] [SOEE Step 1] Submitting Midpoint Limit Buy: {shares} shares @ ${mid_px:.2f} (Spread: ${spread:.2f})")
                req1 = LimitOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    limit_price=mid_px,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
                ord1 = self.trading_client.submit_order(req1)
                is_filled, ord1_status = self._wait_for_order_fill(ord1.id, symbol, timeout_seconds=step_timeout)
                
                if is_filled and ord1_status:
                    filled_order = ord1_status
                else:
                    # Cancel Step 1 order
                    try:
                        self.trading_client.cancel_order_by_id(ord1.id)
                        logger.info(f"[{symbol}] [SOEE Step 1] Unfilled after {step_timeout}s. Cancelled order ID {ord1.id}.")
                    except Exception as ce:
                        logger.warning(f"[{symbol}] Error cancelling Step 1 order: {ce}")
                    time.sleep(1.0)
                    
                    # --- STEP 2: Marketable Step-Up ---
                    step2_px = round(min(ask_px, mid_px + (spread * 0.25)), 2)
                    logger.info(f"[{symbol}] [SOEE Step 2] Submitting Stepped-Up Limit Buy: {shares} shares @ ${step2_px:.2f}")
                    req2 = LimitOrderRequest(
                        symbol=symbol,
                        qty=shares,
                        limit_price=step2_px,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )
                    ord2 = self.trading_client.submit_order(req2)
                    is_filled2, ord2_status = self._wait_for_order_fill(ord2.id, symbol, timeout_seconds=step_timeout)
                    
                    if is_filled2 and ord2_status:
                        filled_order = ord2_status
                    else:
                        # Cancel Step 2 order
                        try:
                            self.trading_client.cancel_order_by_id(ord2.id)
                            logger.info(f"[{symbol}] [SOEE Step 2] Unfilled after {step_timeout}s. Cancelled order ID {ord2.id}.")
                        except Exception as ce:
                            logger.warning(f"[{symbol}] Error cancelling Step 2 order: {ce}")
                        time.sleep(1.0)
                        
                        # --- STEP 3: Fallback Market Order or Clean Abort ---
                        allow_mkt = self.config.get('execution_schedule', 'soee_allow_market_fallback', True)
                        spread_pct = spread / current_price if current_price > 0 else 0.0
                        if allow_mkt and spread_pct <= 0.0020:
                            logger.info(f"[{symbol}] [SOEE Step 3] Tight spread ({spread_pct*100:.2f}%). Submitting Market Order fallback: {shares} shares.")
                            req3 = MarketOrderRequest(
                                symbol=symbol,
                                qty=shares,
                                side=OrderSide.BUY,
                                time_in_force=TimeInForce.DAY
                            )
                            ord3 = self.trading_client.submit_order(req3)
                            is_filled3, ord3_status = self._wait_for_order_fill(ord3.id, symbol, timeout_seconds=10)
                            if is_filled3 and ord3_status:
                                filled_order = ord3_status
                        else:
                            logger.warning(f"[{symbol}] [SOEE] Order escalation completed without fill. Spread {spread_pct*100:.2f}% too wide for market order. Cleanly aborting buy with zero DB entry.")
                            return False
            else:
                # Direct Market Order if SOEE is disabled or quote is unavailable
                logger.info(f"[{symbol}] Market Buy Order submitted: {shares} shares @ ~${current_price:.2f}")
                ord_mkt = self.trading_client.submit_order(MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                ))
                is_mkt_filled, ord_mkt_status = self._wait_for_order_fill(ord_mkt.id, symbol, timeout_seconds=15)
                if is_mkt_filled and ord_mkt_status:
                    filled_order = ord_mkt_status
                else:
                    logger.warning(f"[{symbol}] Market Buy Order not confirmed filled. Cleanly aborting buy with zero DB entry.")
                    return False
                    
            if not filled_order:
                logger.warning(f"[{symbol}] Buy execution failed: No filled order received from Alpaca. Zero DB entry.")
                return False
                
            # Extract actual filled average price and filled quantity from Alpaca
            actual_fill_price = float(getattr(filled_order, 'filled_avg_price', None) or current_price)
            actual_fill_qty = int(getattr(filled_order, 'filled_qty', None) or shares)
            
            position_id = self.db.add_position(
                symbol=symbol,
                entry_price=actual_fill_price,
                quantity=actual_fill_qty,
                stop_loss=stop_loss,
                score=score,
                pattern=signal_details.get('pattern', 'Unknown'),
                initial_stop_loss=stop_loss,
                rs_score=signal_details.get('rs_score', 50.0),
                cps=signal_details.get('cps'),
                rvol=signal_details.get('rvol'),
                candle_pattern=signal_details.get('candle_pattern')
            )
            self.daily_buys.append({
                'symbol': symbol,
                'price': actual_fill_price,
                'shares': actual_fill_qty,
                'stop_loss': stop_loss,
                'pattern': signal_details.get('pattern', 'Unknown'),
                'score': score,
                'rs_score': signal_details.get('rs_score', 50.0),
                'time': datetime.now().strftime('%H:%M:%S ET')
            })
            logger.info(f"[{symbol}] ✅ CONFIRMED BROKER FILL: {actual_fill_qty} shares @ ${actual_fill_price:.2f}. Established in DB (ID: {position_id}, SL: ${stop_loss:.2f})")
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
        
        stepper_mode = str(self.config.get('risk_management', 'stepper_mode', 'user_fixed')).lower()
        
        # Adaptive ATR Hybrid Mode: chooses user_fixed vs atr_proportional dynamically
        if stepper_mode == 'adaptive_atr_hybrid':
            init_sl = position.get('initial_stop_loss') or (entry_price * 0.83)
            init_risk_pct = (entry_price - init_sl) / entry_price if entry_price > 0 else 0.17
            # High-volatility stock (>8% initial stop distance) gets ATR breathing room; low-vol gets fixed milestones
            active_mode = 'atr_proportional' if init_risk_pct > 0.08 else 'user_fixed'
        else:
            active_mode = stepper_mode

        # Configurable Stage Thresholds
        s1_gain = self.config.get('risk_management', 'stepper_stage_1_gain', 0.05)
        s1_sl_pct = self.config.get('risk_management', 'stepper_stage_1_sl_pct', -0.04)
        s2_gain = self.config.get('risk_management', 'stepper_stage_2_gain', 0.08)
        s2_sl_pct = self.config.get('risk_management', 'stepper_stage_2_sl_pct', 0.01) # +1.0% above entry
        s3_gain = self.config.get('risk_management', 'stepper_stage_3_gain', 0.10)
        s3_sl_pct = self.config.get('risk_management', 'stepper_stage_3_sl_pct', 0.03) # +3.0% locked in
        s3_extension_ratchet_gain = s3_gain + 0.05 # +5% above Stage 3 (e.g. +15% total gain)

        if active_mode == 'user_fixed':
            # Stage 3 Extension Ratchet: If price moves +5% above Stage 3, SL moves to Stage 3 level (+10%) and ratchets 1:1
            if profit_pct >= (s3_extension_ratchet_gain - 0.0001):
                ratchet = s3_gain + (profit_pct - s3_extension_ratchet_gain)
                target_sl = entry_price * (1.0 + ratchet)
                new_stage = 4
            elif profit_pct >= (s3_gain - 0.0001):
                # Stage 3: Lock in Stage 3 profit (+3% or configured s3_sl_pct)
                target_sl = entry_price * (1.0 + s3_sl_pct)
                new_stage = 3
            elif profit_pct >= (s2_gain - 0.0001):
                # Stage 2: Move SL to +1% higher than buy price (locks in net positive profit)
                target_sl = entry_price * (1.0 + s2_sl_pct)
                new_stage = 2
            elif profit_pct >= (s1_gain - 0.0001):
                # Stage 1: Move SL to -4% below entry (cuts risk from -17% to -4%)
                target_sl = entry_price * (1.0 + s1_sl_pct)
                new_stage = 1
        else:
            # ATR Proportional Stepper (Volatility Normalized)
            init_sl = position.get('initial_stop_loss') or (entry_price * 0.83)
            risk_d = entry_price - init_sl
            if profit_pct >= (s3_extension_ratchet_gain - 0.0001):
                ratchet_pts = s3_gain + (profit_pct - s3_extension_ratchet_gain)
                target_sl = entry_price * (1.0 + ratchet_pts)
                new_stage = 4
            elif profit_pct >= (s3_gain - 0.0001):
                target_sl = entry_price + (risk_d * 0.20)
                new_stage = 3
            elif profit_pct >= (s2_gain - 0.0001):
                target_sl = entry_price * (1.0 + s2_sl_pct) # Also guarantees +1% above entry
                new_stage = 2
            elif profit_pct >= (s1_gain - 0.0001):
                target_sl = entry_price - (risk_d * 0.25)
                new_stage = 1

        if target_sl > (current_sl + 0.005):
            self.db.update_stop_loss_stepper(position_id, round(target_sl, 4), round(highest_price, 4), new_stage)
            position['stop_loss'] = round(target_sl, 4)
            position['sl_stage'] = new_stage
            position['highest_price_seen'] = round(highest_price, 4)
            self.daily_sl_steps.append({
                'symbol': position['symbol'],
                'old_sl': current_sl,
                'new_sl': target_sl,
                'profit_pct': profit_pct * 100,
                'stage': new_stage,
                'highest_price': highest_price,
                'time': datetime.now().strftime('%H:%M:%S ET')
            })
            logger.info(f"[{position['symbol']}] Trailing SL stepped: ${current_sl:.2f} -> ${target_sl:.2f} (Profit: {profit_pct*100:+.2f}%, Stage {new_stage})")

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
        """
        Execute partial exit using strict Broker Fill Confirmation Handshake:
        Submits SOEE 3-step limit ladder (Midpoint Peg -> Stepped-Down Limit -> Guarded Market fallback) ->
        only records in DB upon confirmed broker execution with actual filled price and filled quantity.
        Zero unconstrained market dumping into distorted/illiquid books.
        """
        symbol = position['symbol']
        if quantity > position['remaining_qty'] or quantity <= 0:
            return
            
        logger.info(f"[{symbol}] Executing Partial Exit {target_name}: {quantity} shares @ ${current_price:.2f}")
        try:
            use_smart_soee = self.config.get('execution_schedule', 'enable_smart_execution', True)
            quote = self.data_fetcher.get_latest_quote(symbol, current_price=current_price) if use_smart_soee else None
            step_timeout = int(self.config.get('execution_schedule', 'soee_step_timeout_seconds', 15))
            filled_order = None
            
            if quote and quote.get('mid', 0) > 0 and quote.get('spread', 0) > 0:
                # --- STEP 1: Midpoint Limit Sell ---
                limit_px = round(quote['mid'], 2)
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    limit_price=limit_px,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                logger.info(f"[{symbol}] [SOEE Partial Exit Step 1] Midpoint Limit Sell: {quantity} shares @ ${limit_px:.2f} (Spread: ${quote['spread']:.2f})")
                ord1 = self.trading_client.submit_order(order_request)
                is_filled1, ord1_status = self._wait_for_order_fill(ord1.id, symbol, timeout_seconds=step_timeout)
                
                if is_filled1 and ord1_status:
                    filled_order = ord1_status
                else:
                    # Cancel Step 1 unfilled limit order
                    try:
                        self.trading_client.cancel_order_by_id(ord1.id)
                        logger.info(f"[{symbol}] [SOEE Partial Exit Step 1] Unfilled after {step_timeout}s. Cancelled order ID {ord1.id}.")
                    except Exception as ce:
                        logger.warning(f"[{symbol}] Error cancelling partial exit limit sell: {ce}")
                    time.sleep(1.0)
                    
                    # Post-cancellation partial fill accounting
                    try:
                        ord1_latest = self.trading_client.get_order_by_id(ord1.id)
                    except Exception:
                        ord1_latest = ord1_status
                    part_filled1 = self._extract_filled_qty(ord1_latest)
                    if part_filled1 > 0:
                        part1_px = float(getattr(ord1_latest, 'filled_avg_price', None) or current_price)
                        p1_pct = (part1_px - position['entry_price']) / position['entry_price'] * 100
                        self.db.add_partial_exit(position['id'], part_filled1, part1_px, target_name, p1_pct)
                        quantity = max(0, quantity - part_filled1)
                        position['remaining_qty'] = max(0, position['remaining_qty'] - part_filled1)
                        logger.info(f"[{symbol}] [SOEE Partial Exit Step 1] Partial fill: {part_filled1} shares filled. Remaining target: {quantity} shares.")
                        if quantity <= 0:
                            filled_order = ord1_latest
                    
                    # --- STEP 2: Stepped-Down Marketable Limit Sell ---
                    step2_px = round(max(quote['bid'], quote['mid'] - (quote['spread'] * 0.25)), 2)
                    logger.info(f"[{symbol}] [SOEE Partial Exit Step 2] Submitting Stepped-Down Limit Sell: {quantity} shares @ ${step2_px:.2f}")
                    req2 = LimitOrderRequest(
                        symbol=symbol,
                        qty=quantity,
                        limit_price=step2_px,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )
                    ord2 = self.trading_client.submit_order(req2)
                    is_filled2, ord2_status = self._wait_for_order_fill(ord2.id, symbol, timeout_seconds=step_timeout)
                    
                    if is_filled2 and ord2_status:
                        filled_order = ord2_status
                    else:
                        # Cancel Step 2 unfilled limit order
                        try:
                            self.trading_client.cancel_order_by_id(ord2.id)
                            logger.info(f"[{symbol}] [SOEE Partial Exit Step 2] Unfilled after {step_timeout}s. Cancelled order ID {ord2.id}.")
                        except Exception as ce:
                            logger.warning(f"[{symbol}] Error cancelling Step 2 order: {ce}")
                        time.sleep(1.0)
                        
                        # Post-cancellation partial fill accounting
                        try:
                            ord2_latest = self.trading_client.get_order_by_id(ord2.id)
                        except Exception:
                            ord2_latest = ord2_status
                        part_filled2 = self._extract_filled_qty(ord2_latest)
                        if part_filled2 > 0:
                            part2_px = float(getattr(ord2_latest, 'filled_avg_price', None) or current_price)
                            p2_pct = (part2_px - position['entry_price']) / position['entry_price'] * 100
                            self.db.add_partial_exit(position['id'], part_filled2, part2_px, target_name, p2_pct)
                            quantity = max(0, quantity - part_filled2)
                            position['remaining_qty'] = max(0, position['remaining_qty'] - part_filled2)
                            logger.info(f"[{symbol}] [SOEE Partial Exit Step 2] Partial fill: {part_filled2} shares filled. Remaining target: {quantity} shares.")
                            if quantity <= 0:
                                filled_order = ord2_latest
                        
                        # --- STEP 3: Guarded Market Sell Fallback ---
                        allow_mkt = self.config.get('execution_schedule', 'soee_allow_market_fallback', True)
                        spread_pct = quote['spread'] / current_price if current_price > 0 else 0.0
                        if allow_mkt and spread_pct <= 0.0025:
                            logger.info(f"[{symbol}] [SOEE Partial Exit Step 3] Tight spread ({spread_pct*100:.2f}%). Submitting Market Order fallback: {quantity} shares.")
                            mkt_ord = self.trading_client.submit_order(MarketOrderRequest(
                                symbol=symbol,
                                qty=quantity,
                                side=OrderSide.SELL,
                                time_in_force=TimeInForce.DAY
                            ))
                            is_mkt_filled, mkt_status = self._wait_for_order_fill(mkt_ord.id, symbol, timeout_seconds=15)
                            if is_mkt_filled and mkt_status:
                                filled_order = mkt_status
                        else:
                            logger.warning(
                                f"[{symbol}] [SOEE Partial Exit] Spread {spread_pct*100:.2f}% too wide for market fallback. "
                                f"Cleanly aborting partial exit for this cycle with zero DB modification to prevent adverse slippage."
                            )
                            return
            else:
                # Quote is unavailable or book is distorted (e.g. spread > 3% or dev > 2%)
                if use_smart_soee:
                    # STEP 1: Pegged Limit Sell at current market price (NEVER unconstrained market dump)
                    peg_px = round(current_price, 2)
                    logger.info(f"[{symbol}] [SOEE Partial Exit Pegged] Quote unavailable/distorted. Submitting Pegged Limit Sell: {quantity} shares @ ${peg_px:.2f}")
                    req_peg = LimitOrderRequest(
                        symbol=symbol,
                        qty=quantity,
                        limit_price=peg_px,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )
                    ord_peg = self.trading_client.submit_order(req_peg)
                    is_peg_filled, peg_status = self._wait_for_order_fill(ord_peg.id, symbol, timeout_seconds=step_timeout)
                    
                    if is_peg_filled and peg_status:
                        filled_order = peg_status
                    else:
                        try:
                            self.trading_client.cancel_order_by_id(ord_peg.id)
                            logger.info(f"[{symbol}] [SOEE Partial Exit Pegged] Unfilled after {step_timeout}s. Cancelled order ID {ord_peg.id}.")
                        except Exception:
                            pass
                        time.sleep(1.0)
                        
                        # STEP 2: Concession Limit Sell capped at 0.2% below market
                        conc_px = round(current_price * 0.998, 2)
                        logger.info(f"[{symbol}] [SOEE Partial Exit Concession] Submitting Concession Limit Sell: {quantity} shares @ ${conc_px:.2f}")
                        req_conc = LimitOrderRequest(
                            symbol=symbol,
                            qty=quantity,
                            limit_price=conc_px,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.DAY
                        )
                        ord_conc = self.trading_client.submit_order(req_conc)
                        is_conc_filled, conc_status = self._wait_for_order_fill(ord_conc.id, symbol, timeout_seconds=step_timeout)
                        
                        if is_conc_filled and conc_status:
                            filled_order = conc_status
                        else:
                            try:
                                self.trading_client.cancel_order_by_id(ord_conc.id)
                                logger.info(f"[{symbol}] [SOEE Partial Exit Concession] Unfilled after {step_timeout}s. Cancelled order ID {ord_conc.id}.")
                            except Exception:
                                pass
                            logger.warning(f"[{symbol}] [SOEE Partial Exit] Distorted/unquoted book limit sells unfilled. Cleanly aborting partial exit with zero DB modification.")
                            return
                else:
                    # SOEE disabled: Standard market sell
                    logger.info(f"[{symbol}] Market Sell submitted (SOEE disabled): {quantity} shares @ ~${current_price:.2f}")
                    mkt_ord = self.trading_client.submit_order(MarketOrderRequest(
                        symbol=symbol,
                        qty=quantity,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    ))
                    is_mkt_filled, mkt_status = self._wait_for_order_fill(mkt_ord.id, symbol, timeout_seconds=15)
                    if is_mkt_filled and mkt_status:
                        filled_order = mkt_status
                        
            if not filled_order:
                logger.warning(f"[{symbol}] Partial exit {target_name} failed: No confirmed broker fill from Alpaca. Zero DB modification.")
                return

            actual_exit_px = float(getattr(filled_order, 'filled_avg_price', None) or current_price)
            actual_exit_qty = int(getattr(filled_order, 'filled_qty', None) or quantity)
            
            profit_pct = (actual_exit_px - position['entry_price']) / position['entry_price'] * 100
            self.db.add_partial_exit(position['id'], actual_exit_qty, actual_exit_px, target_name, profit_pct)
            self.daily_exits.append({
                'symbol': symbol,
                'exit_type': f'Partial {target_name}',
                'qty': actual_exit_qty,
                'exit_price': actual_exit_px,
                'profit_pct': profit_pct,
                'reason': f'Profit Target {target_name}',
                'time': datetime.now().strftime('%H:%M:%S ET')
            })
            logger.info(f"[{symbol}] ✅ CONFIRMED BROKER PARTIAL EXIT: {actual_exit_qty} shares @ ${actual_exit_px:.2f} ({target_name}, P/L: {profit_pct:+.2f}%)")
            
            # Check if Target 3 executed -> Activate Runner Mode
            if target_name == 'PT3':
                self.db.set_runner_mode(position['id'])
                logger.info(f"[{symbol}] 🚀 RUNNER MODE ACTIVATED: Remaining position exempt from TES; trailing 1:1.")
                
            # Clean close if remaining is 0
            refreshed = self.db.get_position_by_id(position['id'])
            if refreshed and refreshed['remaining_qty'] <= 0:
                self.db.close_position(position['id'], actual_exit_px, "Partial Exits Complete")
                logger.info(f"[{symbol}] Position cleanly closed in DB after partial exits.")
        except Exception as e:
            logger.error(f"[{symbol}] Partial exit {target_name} failed: {e}", exc_info=True)

    def execute_full_exit(self, position: Dict, current_price: float, reason: str) -> bool:
        """
        Execute full position exit and close in database using strict Broker Fill Confirmation Handshake.
        Standard exits (Stop Loss, TES, Manual Exits) utilize the 3-Step SOEE Limit Ladder:
        - Step 1: Passive Midpoint Peg (or current_price limit if unquoted/distorted)
        - Step 2: Stepped-Down Marketable Limit (or 0.2% concession limit)
        - Step 3: Guarded Market Order (if spread <= 0.25%) OR Defensive Marketable Limit (0.5% cap)
        Only Catastrophic Breakers bypass the ladder for immediate Emergency Market Sell.
        
        Hardened with Real-Time Broker Synchronization:
        - Detects partial fills on cancelled orders and decrements remaining shares.
        - Synchronizes with broker open positions to eliminate 403 'insufficient qty' rejections.
        - Auto-reconciles and completes remaining quantity under heavy selling pressure.
        """
        symbol = position['symbol']
        remaining = position['remaining_qty']
        if remaining <= 0:
            return False
            
        logger.info(f"[{symbol}] Executing FULL EXIT: {remaining} shares @ ${current_price:.2f} (Reason: {reason})")
        try:
            use_smart_soee = self.config.get('execution_schedule', 'enable_smart_execution', True)
            is_emergency = reason in ['Catastrophic Breaker', 'EMERGENCY_SELL']
            quote = self.data_fetcher.get_latest_quote(symbol, current_price=current_price) if (use_smart_soee and not is_emergency) else None
            step_timeout = int(self.config.get('execution_schedule', 'soee_step_timeout_seconds', 15))
            filled_ord = None
            is_filled = False
            
            if is_emergency or not use_smart_soee:
                # Emergency Catastrophic Breaker or SOEE Disabled: Direct Market Order
                order_desc = "Emergency Market Sell" if is_emergency else "Market Sell (SOEE disabled)"
                logger.warning(f"[{symbol}] {order_desc} submitted: {remaining} shares @ ~${current_price:.2f}")
                mkt_req = MarketOrderRequest(
                    symbol=symbol,
                    qty=remaining,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                mkt_ord, remaining = self._submit_sell_order_with_reconciliation(mkt_req, position, current_price, reason)
                if mkt_ord:
                    is_filled, filled_ord = self._wait_for_order_fill(mkt_ord.id, symbol, timeout_seconds=15)
                elif remaining <= 0:
                    return True
            elif quote and quote.get('mid', 0) > 0 and quote.get('spread', 0) > 0:
                # --- STEP 1: Passive Midpoint Limit Sell ---
                limit_px = round(quote['mid'], 2)
                ord1_req = LimitOrderRequest(
                    symbol=symbol,
                    qty=remaining,
                    limit_price=limit_px,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                logger.info(f"[{symbol}] [SOEE Full Exit Step 1] Midpoint Limit Sell: {remaining} shares @ ${limit_px:.2f} (Spread: ${quote['spread']:.2f})")
                ord1, remaining = self._submit_sell_order_with_reconciliation(ord1_req, position, current_price, reason)
                if ord1 is None and remaining <= 0:
                    return True
                
                is_filled1 = False
                ord1_status = None
                if ord1:
                    is_filled1, ord1_status = self._wait_for_order_fill(ord1.id, symbol, timeout_seconds=step_timeout)
                
                if is_filled1 and ord1_status:
                    filled_ord = ord1_status
                    is_filled = True
                else:
                    # Cancel Step 1 unfilled limit order
                    if ord1:
                        try:
                            self.trading_client.cancel_order_by_id(ord1.id)
                            logger.info(f"[{symbol}] [SOEE Full Exit Step 1] Unfilled after {step_timeout}s. Cancelled order ID {ord1.id}.")
                        except Exception as ce:
                            logger.warning(f"[{symbol}] Error cancelling Step 1 limit order: {ce}")
                        time.sleep(1.0)
                        
                        # Check partial fill post-cancellation
                        try:
                            ord1_latest = self.trading_client.get_order_by_id(ord1.id)
                        except Exception:
                            ord1_latest = ord1_status
                        part_filled = self._extract_filled_qty(ord1_latest)
                        if part_filled > 0:
                            remaining = max(0, remaining - part_filled)
                            self.db.update_position_quantity(position['id'], remaining)
                            position['remaining_qty'] = remaining
                            logger.info(f"[{symbol}] [SOEE Full Exit Step 1] Partial fill detected: {part_filled} shares filled. Remaining: {remaining} shares.")
                            if remaining <= 0:
                                filled_ord = ord1_latest or ord1_status
                                is_filled = True

                    # Verify actual broker position before Step 2
                    if not is_filled:
                        broker_remaining = self._get_broker_remaining_qty(symbol)
                        if broker_remaining is not None:
                            if broker_remaining <= 0:
                                logger.info(f"[{symbol}] [SOEE Full Exit Step 1] Broker confirms 0 shares open. Position fully exited.")
                                remaining = 0
                                self.db.update_position_quantity(position['id'], 0)
                                position['remaining_qty'] = 0
                                is_filled = True
                            elif broker_remaining < remaining:
                                logger.warning(f"[{symbol}] [SOEE Sync] Broker position has {broker_remaining} shares, local had {remaining}. Synchronizing.")
                                remaining = broker_remaining
                                self.db.update_position_quantity(position['id'], remaining)
                                position['remaining_qty'] = remaining

                    if not is_filled and remaining > 0:
                        # --- STEP 2: Stepped-Down Marketable Limit Sell ---
                        step2_px = round(max(quote['bid'], quote['mid'] - (quote['spread'] * 0.25)), 2)
                        logger.info(f"[{symbol}] [SOEE Full Exit Step 2] Submitting Stepped-Down Limit Sell: {remaining} shares @ ${step2_px:.2f}")
                        ord2_req = LimitOrderRequest(
                            symbol=symbol,
                            qty=remaining,
                            limit_price=step2_px,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.DAY
                        )
                        ord2, remaining = self._submit_sell_order_with_reconciliation(ord2_req, position, current_price, reason)
                        if ord2 is None and remaining <= 0:
                            return True

                        is_filled2 = False
                        ord2_status = None
                        if ord2:
                            is_filled2, ord2_status = self._wait_for_order_fill(ord2.id, symbol, timeout_seconds=step_timeout)
                        
                        if is_filled2 and ord2_status:
                            filled_ord = ord2_status
                            is_filled = True
                        else:
                            # Cancel Step 2 unfilled limit order
                            if ord2:
                                try:
                                    self.trading_client.cancel_order_by_id(ord2.id)
                                    logger.info(f"[{symbol}] [SOEE Full Exit Step 2] Unfilled after {step_timeout}s. Cancelled order ID {ord2.id}.")
                                except Exception as ce:
                                    logger.warning(f"[{symbol}] Error cancelling Step 2 limit order: {ce}")
                                time.sleep(1.0)
                                
                                try:
                                    ord2_latest = self.trading_client.get_order_by_id(ord2.id)
                                except Exception:
                                    ord2_latest = ord2_status
                                part_filled2 = self._extract_filled_qty(ord2_latest)
                                if part_filled2 > 0:
                                    remaining = max(0, remaining - part_filled2)
                                    self.db.update_position_quantity(position['id'], remaining)
                                    position['remaining_qty'] = remaining
                                    logger.info(f"[{symbol}] [SOEE Full Exit Step 2] Partial fill detected: {part_filled2} shares filled. Remaining: {remaining} shares.")
                                    if remaining <= 0:
                                        filled_ord = ord2_latest or ord2_status
                                        is_filled = True

                            # Verify actual broker position before Step 3
                            if not is_filled:
                                broker_remaining = self._get_broker_remaining_qty(symbol)
                                if broker_remaining is not None:
                                    if broker_remaining <= 0:
                                        logger.info(f"[{symbol}] [SOEE Full Exit Step 2] Broker confirms 0 shares open. Position fully exited.")
                                        remaining = 0
                                        self.db.update_position_quantity(position['id'], 0)
                                        position['remaining_qty'] = 0
                                        is_filled = True
                                    elif broker_remaining < remaining:
                                        logger.warning(f"[{symbol}] [SOEE Sync] Broker position has {broker_remaining} shares, local had {remaining}. Synchronizing.")
                                        remaining = broker_remaining
                                        self.db.update_position_quantity(position['id'], remaining)
                                        position['remaining_qty'] = remaining

                            if not is_filled and remaining > 0:
                                # --- STEP 3: Guarded Market Order OR Defensive Marketable Limit ---
                                allow_mkt = self.config.get('execution_schedule', 'soee_allow_market_fallback', True)
                                spread_pct = quote['spread'] / current_price if current_price > 0 else 0.0
                                if allow_mkt and spread_pct <= 0.0025:
                                    logger.info(f"[{symbol}] [SOEE Full Exit Step 3] Tight spread ({spread_pct*100:.2f}%). Submitting Market Order fallback: {remaining} shares.")
                                    mkt_req = MarketOrderRequest(
                                        symbol=symbol,
                                        qty=remaining,
                                        side=OrderSide.SELL,
                                        time_in_force=TimeInForce.DAY
                                    )
                                    mkt_ord, remaining = self._submit_sell_order_with_reconciliation(mkt_req, position, current_price, reason)
                                    if mkt_ord:
                                        is_mkt_filled, mkt_status = self._wait_for_order_fill(mkt_ord.id, symbol, timeout_seconds=15)
                                        if is_mkt_filled and mkt_status:
                                            filled_ord = mkt_status
                                            is_filled = True
                                    elif remaining <= 0:
                                        return True
                                else:
                                    # Spread is wide (> 0.25%): Defensive Marketable Limit capped at 0.5% concession
                                    defensive_px = round(current_price * 0.995, 2)
                                    logger.warning(
                                        f"[{symbol}] [SOEE Full Exit Step 3] Spread {spread_pct*100:.2f}% exceeds 0.25% market threshold. "
                                        f"Submitting Defensive Marketable Limit Sell: {remaining} shares @ ${defensive_px:.2f} (0.5% cap) to prevent slippage."
                                    )
                                    lim3_req = LimitOrderRequest(
                                        symbol=symbol,
                                        qty=remaining,
                                        limit_price=defensive_px,
                                        side=OrderSide.SELL,
                                        time_in_force=TimeInForce.DAY
                                    )
                                    lim3_ord, remaining = self._submit_sell_order_with_reconciliation(lim3_req, position, current_price, reason)
                                    if lim3_ord:
                                        is_lim3_filled, lim3_status = self._wait_for_order_fill(lim3_ord.id, symbol, timeout_seconds=15)
                                        if is_lim3_filled and lim3_status:
                                            filled_ord = lim3_status
                                            is_filled = True
                                        else:
                                            try:
                                                self.trading_client.cancel_order_by_id(lim3_ord.id)
                                                logger.info(f"[{symbol}] [SOEE Full Exit Step 3] Defensive limit unfilled. Cancelled order ID {lim3_ord.id}.")
                                            except Exception:
                                                pass
                                            try:
                                                lim3_latest = self.trading_client.get_order_by_id(lim3_ord.id)
                                            except Exception:
                                                lim3_latest = lim3_status
                                            part_filled3 = self._extract_filled_qty(lim3_latest)
                                            if part_filled3 > 0:
                                                remaining = max(0, remaining - part_filled3)
                                                self.db.update_position_quantity(position['id'], remaining)
                                                position['remaining_qty'] = remaining
                                                if remaining <= 0:
                                                    filled_ord = lim3_latest or lim3_status
                                                    is_filled = True
                                    elif remaining <= 0:
                                        return True
            else:
                # Quote is unavailable or book is distorted: Use Pegged / Concession Limit Orders
                peg_px = round(current_price, 2)
                logger.info(f"[{symbol}] [SOEE Full Exit Pegged] Quote unavailable/distorted. Submitting Pegged Limit Sell: {remaining} shares @ ${peg_px:.2f}")
                req_peg = LimitOrderRequest(
                    symbol=symbol,
                    qty=remaining,
                    limit_price=peg_px,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                ord_peg, remaining = self._submit_sell_order_with_reconciliation(req_peg, position, current_price, reason)
                if ord_peg is None and remaining <= 0:
                    return True
                
                is_peg_filled = False
                peg_status = None
                if ord_peg:
                    is_peg_filled, peg_status = self._wait_for_order_fill(ord_peg.id, symbol, timeout_seconds=step_timeout)
                
                if is_peg_filled and peg_status:
                    filled_ord = peg_status
                    is_filled = True
                else:
                    if ord_peg:
                        try:
                            self.trading_client.cancel_order_by_id(ord_peg.id)
                            logger.info(f"[{symbol}] [SOEE Full Exit Pegged] Unfilled after {step_timeout}s. Cancelled order ID {ord_peg.id}.")
                        except Exception:
                            pass
                        time.sleep(1.0)
                        
                        try:
                            peg_latest = self.trading_client.get_order_by_id(ord_peg.id)
                        except Exception:
                            peg_latest = peg_status
                        part_peg = self._extract_filled_qty(peg_latest)
                        if part_peg > 0:
                            remaining = max(0, remaining - part_peg)
                            self.db.update_position_quantity(position['id'], remaining)
                            position['remaining_qty'] = remaining
                            if remaining <= 0:
                                filled_ord = peg_latest or peg_status
                                is_filled = True
                    
                    if not is_filled:
                        broker_remaining = self._get_broker_remaining_qty(symbol)
                        if broker_remaining is not None:
                            if broker_remaining <= 0:
                                remaining = 0
                                self.db.update_position_quantity(position['id'], 0)
                                position['remaining_qty'] = 0
                                is_filled = True
                            elif broker_remaining < remaining:
                                remaining = broker_remaining
                                self.db.update_position_quantity(position['id'], remaining)
                                position['remaining_qty'] = remaining
                    
                    if not is_filled and remaining > 0:
                        # Concession Limit Sell capped at 0.5% below market
                        conc_px = round(current_price * 0.995, 2)
                        logger.info(f"[{symbol}] [SOEE Full Exit Concession] Submitting Defensive Concession Limit Sell: {remaining} shares @ ${conc_px:.2f}")
                        req_conc = LimitOrderRequest(
                            symbol=symbol,
                            qty=remaining,
                            limit_price=conc_px,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.DAY
                        )
                        ord_conc, remaining = self._submit_sell_order_with_reconciliation(req_conc, position, current_price, reason)
                        if ord_conc is None and remaining <= 0:
                            return True
                        
                        is_conc_filled = False
                        conc_status = None
                        if ord_conc:
                            is_conc_filled, conc_status = self._wait_for_order_fill(ord_conc.id, symbol, timeout_seconds=step_timeout)
                        
                        if is_conc_filled and conc_status:
                            filled_ord = conc_status
                            is_filled = True
                        else:
                            if ord_conc:
                                try:
                                    self.trading_client.cancel_order_by_id(ord_conc.id)
                                    logger.info(f"[{symbol}] [SOEE Full Exit Concession] Unfilled after {step_timeout}s. Cancelled order ID {ord_conc.id}.")
                                except Exception:
                                    pass
                                try:
                                    conc_latest = self.trading_client.get_order_by_id(ord_conc.id)
                                except Exception:
                                    conc_latest = conc_status
                                part_conc = self._extract_filled_qty(conc_latest)
                                if part_conc > 0:
                                    remaining = max(0, remaining - part_conc)
                                    self.db.update_position_quantity(position['id'], remaining)
                                    position['remaining_qty'] = remaining
                                    if remaining <= 0:
                                        filled_ord = conc_latest or conc_status
                                        is_filled = True
                            if not is_filled:
                                logger.warning(f"[{symbol}] [SOEE Full Exit] Distorted/unquoted book limit sells unfilled. Retaining DB position open for retry.")
                    
            if not filled_ord or not is_filled:
                logger.critical(
                    f"[{symbol}] 🚨 FULL EXIT FAILED: Order not confirmed filled on Alpaca broker! "
                    f"Retaining position in DB as OPEN so Sell Guardian can retry next cycle without orphaning shares."
                )
                return False

            actual_exit_px = float(getattr(filled_ord, 'filled_avg_price', None) or current_price)
            self.db.close_position(position['id'], actual_exit_px, reason)
            profit_pct = (actual_exit_px - position['entry_price']) / position['entry_price'] * 100
            self.daily_exits.append({
                'symbol': symbol,
                'exit_type': 'Full Exit',
                'qty': position.get('quantity', remaining),
                'exit_price': actual_exit_px,
                'profit_pct': profit_pct,
                'reason': reason,
                'time': datetime.now().strftime('%H:%M:%S ET')
            })
            logger.info(f"[{symbol}] ✅ CONFIRMED BROKER EXIT: Position CLOSED in DB (Exit: ${actual_exit_px:.2f}, P/L: {profit_pct:+.2f}%)")
            return True
        except Exception as e:
            logger.error(f"[{symbol}] Full exit failed: {e}", exc_info=True)
            return False

    def check_time_exit(self, position: Dict, df: Optional[pd.DataFrame] = None) -> bool:
        """
        Dynamic Structural TES Engine (Minervini/Ryan consolidation extension):
        - Runners (is_runner=1) are completely exempt from TES.
        - Base holding period: max_hold_days (e.g. 21, 31, etc.)
        - Effective limit: max_hold_days + (cur_ext * tes_extension_days)
        - If days held >= effective limit:
            - If eligible for extension (cur_ext < max_ext) and holding constructively >= 21 EMA:
                grants dynamic extension (+10 days).
            - Otherwise: returns True (time exit triggered).
        """
        if position.get('is_runner', 0) == 1:
            return False
            
        base_days = self.config.get('risk_management', 'max_hold_days')
        if base_days is None:
            base_days = self.config.get('risk_management', 'tes_base_days', 21)
        ext_days = self.config.get('risk_management', 'tes_extension_days', 10)
        max_ext = self.config.get('risk_management', 'max_tes_extensions')
        if max_ext is None:
            max_ext = self.config.get('risk_management', 'tes_max_extensions', 2)
        cur_ext = position.get('tes_extensions_count')
        if cur_ext is None:
            cur_ext = position.get('tes_extensions', 0)
        
        effective_limit = base_days + (cur_ext * ext_days)
        days_held = self.db.get_days_held(position['id'])
        
        if days_held < effective_limit:
            return False
            
        # Check dynamic structural extension
        if self.config.get('risk_management', 'enable_dynamic_tes_extension', True) and cur_ext < max_ext:
            # If df is None, attempt to fetch daily bars if data_fetcher is available
            if df is None and hasattr(self, 'data_fetcher') and self.data_fetcher:
                try:
                    df = self.data_fetcher.get_daily_bars(position['symbol'], days=60)
                except Exception as e:
                    logger.debug(f"[{position.get('symbol')}] Could not fetch daily bars for TES: {e}")

            if df is not None and len(df) >= 21 and 'close' in df.columns:
                try:
                    curr_close = float(df['close'].iloc[-1])
                    
                    # Ensure EMA21 is available, calculating dynamically if missing or NaN
                    if 'EMA21' not in df.columns or pd.isna(df['EMA21'].iloc[-1]):
                        try:
                            ema_series = ta.ema(df['close'], length=21)
                            if ema_series is not None and not ema_series.empty:
                                df['EMA21'] = ema_series
                            else:
                                df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
                        except Exception:
                            df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
                    
                    ema21_val = df['EMA21'].iloc[-1]
                    if not pd.isna(ema21_val) and ema21_val > 0:
                        ema21 = float(ema21_val)
                        # If price is holding above 21 EMA constructively (within 1% tolerance), extend!
                        if curr_close >= (ema21 * 0.99):
                            new_ext = cur_ext + 1
                            reason = f"Constructive base holding >= 21 EMA (Extension {new_ext}/{max_ext})"
                            self.db.grant_tes_extension(position['id'], reason)
                            position['tes_extensions_count'] = new_ext
                            logger.info(f"[{position['symbol']}] 🎯 DYNAMIC TES EXTENSION {new_ext}/{max_ext} GRANTED (+{ext_days} days to {effective_limit + ext_days} days): Maturing base above EMA21.")
                            return False
                except Exception as e:
                    logger.error(f"[{position.get('symbol')}] Error evaluating dynamic TES extension: {e}")
                    
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
    
    def is_window_complete(self, force_cutoff: bool = False) -> bool:
        if not self.window_start_time: return False
        if force_cutoff: return True
        elapsed = (datetime.now() - self.window_start_time).total_seconds() / 60
        return elapsed >= self.monitoring_minutes
    
    def get_queue_status(self) -> Dict:
        elapsed = (datetime.now() - self.window_start_time).total_seconds() / 60 if self.window_start_time else 0.0
        return {
            'signals_queued': len(self.signals),
            'minutes_elapsed': elapsed,
            'symbols': list(self.signals.keys())
        }
    
    @staticmethod
    def calculate_composite_priority_score(details: Dict) -> float:
        """
        Calculates Institutional Composite Priority Score (CPS) for deterministic candidate ranking:
        CPS = (Base_Score_Norm * 0.30) + 
              (Candle_Weight * 0.25) + 
              (RVol_Score * 0.20) + 
              (MA_Momentum_Score * 0.15) + 
              (RS_Score_Norm * 0.10)
        """
        raw_score = float(details.get('score', 4.0))
        base_score_norm = min(1.0, max(0.0, (raw_score - 4.0) / 3.0)) # 4.0 -> 0.0, 7.0 -> 1.0
        
        candle_weight = float(details.get('candle_weight', 0.40))
        
        rvol = float(details.get('rvol', 1.0))
        if rvol >= 2.0:
            rvol_score = 1.0
        elif rvol >= 1.5:
            rvol_score = 0.8
        elif rvol >= 1.0:
            rvol_score = 0.5
        else:
            rvol_score = max(0.0, rvol * 0.5)
            
        slope_21 = float(details.get('slope_21_pct', 0.0))
        slope_50 = float(details.get('slope_50_pct', 0.0))
        dist_21 = float(details.get('dist_to_ema21_pct', 0.0))
        
        ma_score = 0.5
        if slope_21 > 0:
            ma_score += 0.25
        if slope_50 >= 0:
            ma_score += 0.15
        else:
            ma_score -= 0.20
        if dist_21 <= 1.5:
            ma_score += 0.10
        elif dist_21 > 3.0:
            ma_score -= 0.10
        ma_score = min(1.0, max(0.0, ma_score))
        
        rs_raw = float(details.get('rs_score', 50.0))
        rs_norm = min(1.0, max(0.0, rs_raw / 100.0))
        
        cps = (base_score_norm * 0.30) + (candle_weight * 0.25) + (rvol_score * 0.20) + (ma_score * 0.15) + (rs_norm * 0.10)
        return round(cps, 4)

    def get_top_signals(self, analyzer: RajatAlphaAnalyzer) -> List[Tuple[str, Dict]]:
        valid_signals = []
        for symbol, details in self.signals.items():
            valid, updated_details = analyzer.analyze_entry_signal(symbol)
            if valid:
                updated_details['cps'] = self.calculate_composite_priority_score(updated_details)
                valid_signals.append((symbol, updated_details))
                
        # Institutional Multi-Tier Deterministic Sort:
        # 1. Composite Priority Score (CPS) DESC
        # 2. Base Score DESC
        # 3. IBD RS Composite DESC
        # 4. Average Daily Dollar Volume DESC (Absolute Liquidity)
        valid_signals.sort(
            key=lambda x: (
                x[1].get('score', 0.0),        # 1. Primary: Conviction Score (e.g. 5.0 > 4.5 > 4.0)
                x[1].get('cps', 0.0),          # 2. Secondary: Institutional CPS breaks ties on equal score
                x[1].get('rs_score', 0.0),     # 3. Tertiary: IBD RS Rating
                x[1].get('dollar_volume', 0.0) # 4. Quaternary: Dollar Volume Liquidity
            ),
            reverse=True
        )
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
        
        feed_pref = self.config.get('execution_schedule', 'data_feed', 'sip')
        self.trading_client = TradingClient(api_key, secret_key, paper=self.is_paper)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
        
        self.data_fetcher = MarketDataFetcher(self.data_client, feed=feed_pref)
        self.analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        self.position_manager = PositionManager(self.trading_client, self.config, self.db, self.data_fetcher)
        
        self.signal_queue = SignalQueue(
            monitoring_minutes=self.config.get('execution_schedule', 'signal_monitoring_minutes', 30),
            top_n=self.config.get('execution_schedule', 'top_n_trades', 5)
        )
        
        self.last_portfolio_table_time = 0.0
        self.portfolio_table_interval_seconds = 600  # 10 minutes
        self.daily_snapshot_done = False
        
        logger.info("=" * 80)
        logger.info("RAJAT ALPHA V67 TRADING BOT INITIALIZED (VERSION 3.2)")
        logger.info(f"Mode: {'PAPER TRADING' if self.is_paper else 'LIVE TRADING'}")
        logger.info("=" * 80)
        
        # Initial Startup Broker State Reconciliation
        if self.config.get('execution_schedule', 'enable_broker_reconciliation', True):
            logger.info("⚡ Performing Initial Startup Broker Position Reconciliation...")
            self.reconcile_positions_with_broker()

    def is_market_open(self) -> bool:
        """
        Timezone-neutral market hours check:
        Primary: Queries live Alpaca Broker clock (100% immune to DST shifts, local host timezones, and holidays).
        Fallback: Evaluates US/Eastern wall-clock (9:30 - 16:00 ET) with automatic pytz EST/EDT transitions.
        """
        try:
            clock = self.trading_client.get_clock()
            if clock and hasattr(clock, 'is_open'):
                return bool(clock.is_open)
        except Exception as e:
            logger.debug(f"Could not query Alpaca clock: {e}. Falling back to US/Eastern wall-clock.")
            
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
        """Check if SPY opened below yesterday's close with robust multi-layer fallback"""
        try:
            df_spy = self.data_fetcher.get_daily_bars('SPY', days=5)
            if df_spy is not None and len(df_spy) >= 2:
                prev_close = float(df_spy['close'].iloc[-2])
                curr_price = self.data_fetcher.get_current_price('SPY')
                if curr_price is None:
                    # Fallback to the latest available close in df_spy
                    curr_price = float(df_spy['close'].iloc[-1])
                is_down = curr_price < prev_close
                logger.info(f"[FIRST-HOUR GUARD] SPY Price: ${curr_price:.2f} vs Prev Close: ${prev_close:.2f} -> Market Open Down: {is_down}")
                return is_down
        except Exception as e:
            logger.warning(f"[FIRST-HOUR GUARD] Failed to evaluate SPY open direction: {e}. Defaulting to False (Normal stops).")
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

    def load_exclusion_list(self) -> set:
        """
        Loads excluded ticker symbols from exclusion file (default: config/exclusionlist.txt).
        Returns a set of uppercase ticker symbols.
        Lines beginning with '#' or empty lines are ignored.
        """
        exclusion_file = self.config.get('trading_rules', 'exclusion_file', 'config/exclusionlist.txt')
        exclusions = set()
        if exclusion_file and os.path.exists(exclusion_file):
            try:
                with open(exclusion_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            sym = line.split('#')[0].strip().upper()
                            if sym:
                                exclusions.add(sym)
                if exclusions and self.config.get('trading_rules', 'log_excluded_symbols', True):
                    logger.info(f"📋 Exclusion list loaded: {len(exclusions)} symbols ({', '.join(sorted(exclusions)[:10])}{'...' if len(exclusions) > 10 else ''})")
            except Exception as e:
                logger.error(f"Error loading exclusion file {exclusion_file}: {e}")
        return exclusions

    def process_manual_overrides(self):
        """
        Processes manual position overrides from:
        1. config/selllist.txt (Fast 1-line format: 'AAPL', 'AAPL:SL:145.50', 'AAPL:TES:10')
        2. config.json 'manual_position_overrides' (JSON array)
        Actions: 'FORCE_SELL', 'UPDATE_STOP_LOSS', 'EXTEND_TES'.
        """
        # Collect overrides from:
        # 1. config/selllist.txt (Fast, clean 1-line emergency overrides)
        # 2. config.json "manual_position_overrides" (Optional JSON array)
        overrides = []
        
        # 1. Parse selllist.txt
        selllist_path = self.config.get('trading_rules', 'sell_watchlist_file', 'config/selllist.txt')
        if os.path.exists(selllist_path):
            try:
                with open(selllist_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = [p.strip() for p in line.split(':')]
                        sym = parts[0].upper()
                        act = parts[1].upper() if len(parts) > 1 else 'FORCE_SELL'
                        param = parts[2].strip() if len(parts) > 2 else None
                        
                        entry = {'symbol': sym, 'action': act}
                        if act in ['SL', 'UPDATE_STOP_LOSS', 'STOP_LOSS'] and param:
                            entry['action'] = 'UPDATE_STOP_LOSS'
                            try:
                                entry['new_stop_loss'] = float(param)
                            except ValueError:
                                pass
                        elif act in ['TES', 'EXTEND_TES'] and param:
                            entry['action'] = 'EXTEND_TES'
                            try:
                                entry['extend_days'] = int(param)
                            except ValueError:
                                pass
                        elif act in ['FORCE_SELL', 'SELL', 'EXIT', 'FORCE_CLOSE']:
                            entry['action'] = 'FORCE_SELL'
                            if param:
                                entry['exit_reason'] = param
                        overrides.append(entry)
            except Exception as e:
                logger.error(f"Error parsing {selllist_path}: {e}")

        # 2. Append JSON overrides from config.json (if present)
        cfg_overrides = self.config.get('manual_position_overrides', [])
        if isinstance(cfg_overrides, list):
            overrides.extend(cfg_overrides)

        for item in overrides:
            if not isinstance(item, dict): 
                continue
                
            symbol = item.get('symbol')
            pos_id = item.get('position_id')
            action = str(item.get('action', 'FORCE_SELL')).upper()
            override_id = str(pos_id or symbol) + "_" + action
            
            if item.get('processed', False) or self.db.is_override_processed(override_id):
                continue
                
            # Target specific position
            pos = None
            if pos_id:
                pos = self.db.get_position_by_id(pos_id)
            elif symbol:
                open_syms = self.db.get_open_positions(symbol)
                pos = open_syms[0] if open_syms else None
                
            if not pos:
                continue
                
            current_px = self.data_fetcher.get_current_price(pos['symbol']) or pos['entry_price']
            reason = item.get('exit_reason') or item.get('reason') or f"Manual Override: {action}"
            
            if action in ['FORCE_SELL', 'FORCE_CLOSE']:
                logger.info(f"[MANUAL OVERRIDE] Triggering live full exit for {pos['symbol']} (Position ID {pos['id']})")
                self.position_manager.execute_full_exit(pos, current_px, reason)
                self.db.record_processed_override(override_id, pos['symbol'], pos['id'], action, current_px, pos['remaining_qty'], reason)
                logger.info(f"[MANUAL OVERRIDE] Successfully executed and recorded {action} for {pos['symbol']} at ${current_px:.2f}")
                
            elif action == 'UPDATE_STOP_LOSS':
                new_sl = item.get('new_stop_loss') or item.get('stop_loss')
                if new_sl is not None:
                    new_sl_val = float(new_sl)
                    self.db.update_stop_loss(pos['id'], new_sl_val)
                    self.db.record_processed_override(override_id, pos['symbol'], pos['id'], action, new_sl_val, pos['remaining_qty'], reason)
                    logger.info(f"[MANUAL OVERRIDE] Position {pos['id']} ({pos['symbol']}) Stop Loss manually updated to ${new_sl_val:.2f}")
                    
            elif action == 'EXTEND_TES':
                ext_days = item.get('extend_days', 10)
                reason_note = f"Manual TES extension (+{ext_days} days): {reason}"
                self.db.grant_tes_extension(pos['id'], reason_note)
                self.db.record_processed_override(override_id, pos['symbol'], pos['id'], action, current_px, pos['remaining_qty'], reason_note)
                logger.info(f"[MANUAL OVERRIDE] Position {pos['id']} ({pos['symbol']}) TES extended (+{ext_days} days)")

    def reconcile_positions_with_broker(self) -> int:
        """
        Reconciles local SQLite positions against live Alpaca broker positions.
        Single Source of Truth (SSOT) is always Alpaca Broker.
        Detects and safely resolves:
        1. Phantom positions in DB where Alpaca holds 0 shares (prevents naked short selling).
        2. Zero-quantity positions still marked 'OPEN'.
        3. Quantity mismatches between DB and broker.
        Returns number of reconciled discrepancies.
        """
        discrepancies = 0
        try:
            alpaca_positions = self.trading_client.get_all_positions()
            broker_map = {}
            for p in alpaca_positions:
                try:
                    broker_map[p.symbol] = float(p.qty)
                except Exception:
                    pass
                    
            db_positions = self.db.get_open_positions()
            
            for pos in db_positions:
                sym = pos['symbol']
                pos_id = pos['id']
                db_qty = pos['remaining_qty']
                broker_qty = broker_map.get(sym, 0.0)
                
                # Check 1: Ghost Position (DB has OPEN, but Alpaca holds 0 shares)
                if broker_qty <= 0:
                    discrepancies += 1
                    logger.critical(
                        f"[{sym}] 🚨 PHANTOM GHOST POSITION DETECTED! DB records {db_qty} shares OPEN (ID: {pos_id}), "
                        f"but Alpaca account holds 0 shares! Reconciling to prevent unintended naked short sale."
                    )
                    self.db.update_position_status(
                        pos_id, 
                        'CANCELLED_UNFILLED', 
                        exit_reason='Reconciled: No Broker Position'
                    )
                # Check 2: Quantity mismatch (partial fill or manual adjustment outside bot)
                elif broker_qty < db_qty:
                    discrepancies += 1
                    logger.warning(
                        f"[{sym}] Position quantity mismatch: DB records {db_qty} shares, "
                        f"Alpaca holds {broker_qty} shares. Adjusting DB remaining_qty to match broker."
                    )
                    self.db.update_position_quantity(pos_id, int(broker_qty))
                    
            if discrepancies > 0:
                logger.info(f"🛡️ Broker Reconciliation Complete: Resolved {discrepancies} position discrepancies.")
        except Exception as e:
            logger.error(f"Broker position reconciliation check failed: {e}")
        return discrepancies

    def run_sell_guardian(self):
        """Monitors open positions for stop-loss, profit-taking, and structural TES"""
        open_positions = self.db.get_open_positions()
        et_now = datetime.now(pytz.timezone('US/Eastern')).strftime('%H:%M:%S ET')
        
        if not open_positions:
            logger.info(f"🛡️ SELL GUARDIAN: No open positions to monitor ({et_now}).")
            return
            
        exclusions = self.load_exclusion_list()
        if exclusions:
            excluded_positions = [p for p in open_positions if p['symbol'] in exclusions]
            if excluded_positions:
                for ep in excluded_positions:
                    logger.info(f"[{ep['symbol']}] 🚫 Excluded via exclusionlist.txt — skipping all Sell Guardian monitoring (SL, TES, partial exits).")
                open_positions = [p for p in open_positions if p['symbol'] not in exclusions]
                if not open_positions:
                    logger.info(f"🛡️ SELL GUARDIAN: All open positions are excluded via exclusionlist.txt ({et_now}).")
                    return
        
        is_first_hour = self.is_first_hour()
        market_down = self.is_market_opening_down() if is_first_hour else False
        suppress_first_hour = is_first_hour and market_down and self.config.get('first_hour_guard', 'suppress_sl', True)
        is_closing = self.is_closing_window()
        
        if is_first_hour:
            guard_status = "⚠️ ENGAGED (Regular Stops Suppressed)" if suppress_first_hour else "✅ NORMAL (Index Up / Catastrophic Active)"
            logger.info(f"[FIRST-HOUR GUARD] 09:30-10:30 ET Status: {guard_status}")
            
        pos_summaries = []
        for position in open_positions:
            symbol = position['symbol']
            try:
                curr_price = self.data_fetcher.get_current_price(symbol)
                if curr_price is None:
                    logger.warning(f"[{symbol}] Could not fetch current price, skipping cycle check.")
                    continue
                
                profit_pct = (curr_price - position['entry_price']) / position['entry_price'] * 100.0
                stage_str = f"Stage {position.get('sl_stage', 0)}" + (" [RUNNER]" if position.get('is_runner') else "")
                peak_price = max(position.get('highest_price_seen') or curr_price, curr_price)
                
                pos_summaries.append({
                    'symbol': symbol,
                    'entry': position['entry_price'],
                    'curr': curr_price,
                    'qty': position['remaining_qty'],
                    'pl_pct': profit_pct,
                    'sl': position['stop_loss'],
                    'stage': stage_str,
                    'peak': peak_price,
                    'is_runner': position.get('is_runner', 0)
                })
                
                # 1. Update Trailing Stop Stepper
                self.position_manager.update_trailing_stop_loss(position, current_price=curr_price)
                
                # 2. Check Stop Loss (Respects Closing-Basis & First-Hour Guard)
                if self.position_manager.check_stop_loss(position, curr_price, is_closing_window=is_closing, is_first_hour_suppressed=suppress_first_hour):
                    cat_pct = self.config.get('first_hour_guard', 'catastrophic_override_pct', -0.22)
                    is_cat = (curr_price - position['entry_price']) / position['entry_price'] <= cat_pct
                    exit_reason = "Catastrophic Breaker" if is_cat else "Stop Loss"
                    logger.warning(f"[{symbol}] 🚨 {exit_reason.upper()} TRIGGERED at ${curr_price:.2f}")
                    self.position_manager.execute_full_exit(position, curr_price, exit_reason)
                    continue
                    
                # 3. Check 4-Tier Partial Exits & Runner Mode
                partial_exits = self.position_manager.check_partial_exit_targets(position, curr_price)
                for t_name, qty, t_price in partial_exits:
                    self.position_manager.execute_partial_exit(position, t_name, qty, curr_price)
                    
                # 4. Check Dynamic Structural TES
                df_sym = self.data_fetcher.get_daily_bars(symbol, days=60)
                if df_sym is not None and len(df_sym) >= 21:
                    try:
                        df_sym = self.analyzer.calculate_indicators(df_sym)
                    except Exception as e:
                        logger.debug(f"[{symbol}] Indicator calculation on daily bars: {e}")
                        
                if not suppress_first_hour and self.position_manager.check_time_exit(position, df_sym):
                    logger.warning(f"[{symbol}] ⏰ TIME EXIT SIGNAL (TES) triggered")
                    self.position_manager.execute_full_exit(position, curr_price, "TES")
                    continue
            except Exception as e:
                logger.error(f"[{symbol}] Error processing position in Sell Guardian: {e}", exc_info=True)
                continue
                
        # Structured Logging: Full Portfolio Table every 10-15 minutes; clean 1-line Heartbeat otherwise
        now_ts = time.time()
        show_table = (now_ts - self.last_portfolio_table_time) >= self.portfolio_table_interval_seconds
        
        if show_table and pos_summaries:
            self.last_portfolio_table_time = now_ts
            table_lines = [
                "=" * 98,
                f"🛡️ PORTFOLIO HEALTH MONITOR ({len(pos_summaries)} Active Positions | {et_now})",
                "-" * 98,
                f"{'Symbol':<7} | {'Buy Rate':>9} | {'Curr Price':>10} | {'Qty':>5} | {'P/L (%)':>8} | {'Stop Loss':>10} | {'Stage':>10} | {'Peak':>9} | {'Runner'}",
                "-" * 98
            ]
            tot_cost = sum(p['entry'] * p['qty'] for p in pos_summaries)
            tot_val = sum(p['curr'] * p['qty'] for p in pos_summaries)
            tot_pl = tot_val - tot_cost
            tot_pl_pct = (tot_pl / tot_cost * 100.0) if tot_cost > 0 else 0.0
            
            for p in sorted(pos_summaries, key=lambda x: x['pl_pct'], reverse=True):
                runner_tag = "YES" if p['is_runner'] else "NO"
                table_lines.append(
                    f"{p['symbol']:<7} | ${p['entry']:>8.2f} | ${p['curr']:>9.2f} | {p['qty']:>5} | {p['pl_pct']:>+7.2f}% | ${p['sl']:>9.2f} | {p['stage']:>10} | ${p['peak']:>8.2f} | {runner_tag:^6}"
                )
            table_lines.append("-" * 98)
            table_lines.append(f"Portfolio Value: ${tot_val:,.2f} | Cost Basis: ${tot_cost:,.2f} | Total Unrealized P/L: ${tot_pl:+,.2f} ({tot_pl_pct:+.2f}%)")
            table_lines.append("=" * 98)
            logger.info("\n" + "\n".join(table_lines))
        elif pos_summaries:
            top_pos = max(pos_summaries, key=lambda x: x['pl_pct'])
            avg_pl = sum(x['pl_pct'] for x in pos_summaries) / len(pos_summaries)
            logger.info(f"💓 [PORTFOLIO HEARTBEAT] {len(pos_summaries)} positions monitored | Top Mover: {top_pos['symbol']} ({top_pos['pl_pct']:+.2f}%) | Avg P/L: {avg_pl:+.2f}% | All stops healthy ({et_now})")

    def run_buy_hunter(self):
        """Scans watchlist during buy window and manages signal queue"""
        now_et = datetime.now(pytz.timezone('US/Eastern'))
        start_str = self.config.get('execution_schedule', 'buy_window_start_time', '14:30')
        end_str = self.config.get('execution_schedule', 'buy_window_end_time', '15:59')
        
        if not self.is_buy_window():
            logger.info(f"⏳ BUY HUNTER: Outside Buy Window ({start_str} - {end_str} ET | Current: {now_et.strftime('%H:%M:%S ET')})")
            return
        
        is_closing = self.is_closing_window()
        if self.signal_queue.is_window_complete(force_cutoff=is_closing):
            logger.info("=" * 80)
            logger.info("🎯 BUY HUNTER: 30-Minute Monitoring Window Complete - Executing Ranked Signals")
            logger.info("=" * 80)
            
            top_signals = self.signal_queue.get_top_signals(self.analyzer)
            open_positions = self.db.get_open_positions()
            max_positions = self.config.get('trading_rules', 'max_open_positions', 15)
            pos_avail = max(0, max_positions - len(open_positions))
            
            # Enforce max_trades_per_day
            trades_today = self.db.count_trades_today()
            max_trades_per_day = self.config.get('trading_rules', 'max_trades_per_day', 3)
            daily_remaining = max(0, max_trades_per_day - trades_today)
            avail = min(pos_avail, daily_remaining)
            
            logger.info(f"Daily Trades Executed: {trades_today}/{max_trades_per_day} | Open Positions: {len(open_positions)}/{max_positions} | Available Slots: {avail}")
            
            if top_signals:
                logger.info("Ranked Candidates in Buy Window (Sorted by Score DESC, IBD RS DESC):")
                for idx, (sym, det) in enumerate(top_signals, 1):
                    selected = (idx <= avail)
                    status_tag = "✅ SELECTED FOR POSITION" if selected else "⚠️ SKIPPED (Limit Reached)"
                    logger.info(f"  {idx}. [{sym}] CPS: {det.get('cps', 0.0):.4f} | Score: {det.get('score')}/7.0 | Candle: {det.get('candle_pattern')} (wt: {det.get('candle_weight', 0.4):.2f}) | RVol: {det.get('rvol', 1.0):.1f}x | Slopes: {det.get('slope_21_pct', 0.0):+.1f}%/{det.get('slope_50_pct', 0.0):+.1f}% | IBD RS: {det.get('rs_score'):.1f} | Price: ${det.get('price'):.2f} -> {status_tag}")
            else:
                logger.info("No candidates maintained qualified status upon 30-min revalidation.")
            
            executed_count = 0
            exclusions = self.load_exclusion_list()
            for symbol, details in top_signals:
                if executed_count >= avail:
                    break
                if symbol in exclusions:
                    logger.warning(f"[{symbol}] Skipped buy execution: Symbol in exclusionlist.txt.")
                    continue
                if self.config.get('trading_rules', 'prevent_same_day_reentry', True) and self.db.was_traded_today(symbol):
                    logger.warning(f"[{symbol}] Skipped buy execution: Traded earlier today (prevent_same_day_reentry).")
                    continue
                if self.position_manager.execute_buy(symbol, details):
                    self.db.log_signal(symbol, details, executed=True)
                    logger.info(f"[{symbol}] 🚀 Order placed and position established in portfolio.")
                    executed_count += 1
                    
            self.signal_queue.reset()
            return
            
        # Collection Phase
        watchlist_file = self.config.get('trading_rules', 'watchlist_file', 'config/watchlist.txt')
        if not os.path.exists(watchlist_file):
            logger.warning(f"Watchlist file not found: {watchlist_file}")
            return
            
        with open(watchlist_file, 'r') as f:
            symbols = [line.strip().upper() for line in f if line.strip() and not line.strip().startswith('#')]

        exclusions = self.load_exclusion_list()
        if exclusions:
            original_count = len(symbols)
            symbols = [s for s in symbols if s not in exclusions]
            excluded_count = original_count - len(symbols)
            if excluded_count > 0:
                logger.info(f"🚫 Excluded {excluded_count} symbols from Buy Hunter watchlist via exclusionlist.txt.")
            
        # Check capacity before scanning
        trades_today = self.db.count_trades_today()
        max_trades_per_day = self.config.get('trading_rules', 'max_trades_per_day', 3)
        open_positions = self.db.get_open_positions()
        max_positions = self.config.get('trading_rules', 'max_open_positions', 15)
        
        q_stat = self.signal_queue.get_queue_status()
        logger.info("=" * 80)
        logger.info(f"🎯 BUY HUNTER: Watchlist Scan & Candidate Staging ({len(symbols)} Watchlist Symbols)")
        logger.info(f"Portfolio Slots: {len(open_positions)}/{max_positions} | Trades Today: {trades_today}/{max_trades_per_day} | Queue: {q_stat['signals_queued']} staged ({q_stat['minutes_elapsed']:.1f}m/{self.signal_queue.monitoring_minutes}m)")
        logger.info("=" * 80)
        
        if trades_today >= max_trades_per_day:
            logger.info(f"Daily trade limit reached ({trades_today}/{max_trades_per_day}), skipping candidate collection.")
            return
            
        if len(open_positions) >= max_positions:
            logger.info(f"Maximum open positions reached ({len(open_positions)}/{max_positions}), skipping candidate collection.")
            return
            
        new_staged = 0
        for symbol in symbols:
            # Check per-stock limit
            existing = self.db.get_open_positions(symbol=symbol)
            max_per_stock = self.config.get('trading_rules', 'max_trades_per_stock', 1)
            if len(existing) >= max_per_stock:
                logger.info(f"[{symbol}] ℹ️ Already holding maximum open position ({len(existing)}/{max_per_stock}), skipping scan.")
                continue
                
            try:
                valid, details = self.analyzer.analyze_entry_signal(symbol)
                self.db.log_signal(symbol, details, executed=False)
                if valid:
                    self.signal_queue.add_signal(symbol, details)
                    new_staged += 1
                    logger.info(f"[{symbol}] 📥 STAGED IN BUY QUEUE: Score {details.get('score')}/7.0 | IBD RS: {details.get('rs_score'):.1f} | Pattern: {details.get('pattern')} | Price: ${details.get('price'):.2f}")
            except Exception as e:
                logger.error(f"[{symbol}] Error analyzing symbol in Buy Hunter: {e}", exc_info=True)
                continue
                
        logger.info(f"Buy Hunter scan complete: {new_staged} new candidates staged. Total queue: {len(self.signal_queue.signals)} candidates (re-validates in {self.signal_queue.monitoring_minutes} min).")
        if self.signal_queue.signals:
            logger.info("📋 CURRENT STAGED CANDIDATE QUEUE (Awaiting 30-Min Re-Validation):")
            for q_sym, q_det in self.signal_queue.signals.items():
                logger.info(f"   • {q_sym:<6} | Score: {q_det.get('score', 0):.1f}/7.0 | RS: {q_det.get('rs_score', 0):.1f} | Pattern: {q_det.get('pattern', 'N/A')} | Price: ${q_det.get('price', 0):.2f}")

    def generate_daily_market_close_snapshot(self):
        """
        Compiles and records an Executive End-of-Day (EOD) Market Close Snapshot:
        - Daily buys, sells, SL triggers, and trailing SL steppers
        - Signal Funnel & Gate rejection metrics
        - Closing portfolio status
        - Outputs to console/rajat_alpha_v67.log and appends to logs/daily_snapshot.log
        """
        now_et = datetime.now(pytz.timezone('US/Eastern'))
        today_str = now_et.strftime('%Y-%m-%d')
        time_str = now_et.strftime('%H:%M:%S ET')
        mode_str = "PAPER TRADING" if self.is_paper else "LIVE TRADING"
        
        cursor = self.db.conn.cursor()
        
        # 1. Buys Executed Today
        cursor.execute('''
            SELECT symbol, entry_price, quantity, stop_loss, pattern, score, rs_score, entry_date
            FROM positions
            WHERE entry_date LIKE ?
        ''', (f"{today_str}%",))
        buys_rows = cursor.fetchall()
        
        # 2. Exits Executed Today
        cursor.execute('''
            SELECT symbol, entry_price, exit_price, quantity, profit_loss_pct, exit_reason, exit_date
            FROM positions
            WHERE status = 'CLOSED' AND exit_date LIKE ?
        ''', (f"{today_str}%",))
        full_exits = cursor.fetchall()
        
        cursor.execute('''
            SELECT p.symbol, pe.profit_target, pe.quantity, pe.exit_price, pe.profit_pct, pe.exit_date
            FROM partial_exits pe
            JOIN positions p ON pe.position_id = p.id
            WHERE pe.exit_date LIKE ?
        ''', (f"{today_str}%",))
        partial_exits = cursor.fetchall()
        
        # 3. Trailing SL Steppers
        sl_steps = self.position_manager.daily_sl_steps
        
        # 4. Signal Funnel & Gate Rejections Today
        cursor.execute('''
            SELECT symbol, score, pattern, price, reason, executed, rs_score, candle_pattern
            FROM signal_history
            WHERE signal_date LIKE ?
        ''', (f"{today_str}%",))
        sig_rows = cursor.fetchall()
        
        gate_counts = {
            'gate_0_regime': 0,
            'gate_1_structure': 0,
            'gate_1_5_slope': 0,
            'gate_2_pullback': 0,
            'gate_3_pattern': 0,
            'gate_4_weekly': 0,
            'gate_6_stalling': 0,
            'gate_6_25_extended': 0,
            'gate_6_5_red_candle': 0,
            'gate_6_75_shooting_star': 0,
            'gate_7_score': 0,
            'valid_signals': 0
        }
        
        for row in sig_rows:
            reason = str(row[4] or "")
            if "Gate 0" in reason or "Market Regime" in reason or "SPY" in reason:
                gate_counts['gate_0_regime'] += 1
            elif "Gate 1 " in reason or "Market structure" in reason or "50 SMA > 200 SMA" in reason:
                gate_counts['gate_1_structure'] += 1
            elif "Gate 1.5" in reason or "slope" in reason:
                gate_counts['gate_1_5_slope'] += 1
            elif "Gate 2" in reason or "pullback" in reason or "impulse" in reason:
                gate_counts['gate_2_pullback'] += 1
            elif "Gate 3" in reason or "reversal pattern" in reason or "qualifying pattern" in reason:
                gate_counts['gate_3_pattern'] += 1
            elif "Gate 4" in reason or "Weekly MTF" in reason:
                gate_counts['gate_4_weekly'] += 1
            elif "Gate 6 " in reason or "Stalling" in reason or "consolidation" in reason:
                gate_counts['gate_6_stalling'] += 1
            elif "Gate 6.25" in reason or "EXTENDED" in reason or "Gap up" in reason:
                gate_counts['gate_6_25_extended'] += 1
            elif "Gate 6.5" in reason or "RED today" in reason:
                gate_counts['gate_6_5_red_candle'] += 1
            elif "Gate 6.75" in reason or "Shooting star" in reason:
                gate_counts['gate_6_75_shooting_star'] += 1
            elif "Gate 7" in reason or "Score" in reason or "Touch-only" in reason:
                gate_counts['gate_7_score'] += 1
            
            if "VALID BUY SIGNAL" in reason or row[5] == 1:
                gate_counts['valid_signals'] += 1
        
        # 5. Open Positions Health
        open_positions = self.db.get_open_positions()
        
        # Build Report
        sep = "=" * 110
        sub_sep = "-" * 110
        lines = [
            sep,
            f"🏁 RAJAT ALPHA V67 — END-OF-DAY MARKET CLOSE EXECUTIVE SNAPSHOT",
            f"Date: {today_str} | Generated: {time_str} | Trading Mode: {mode_str}",
            sep,
            "",
            "1. DAILY ACTION METRICS",
            sub_sep,
            f"  • New Buys Executed Today        : {len(buys_rows)}",
            f"  • Full Exits Executed Today      : {len(full_exits)}",
            f"  • Partial Profit Targets Hit     : {len(partial_exits)}",
            f"  • Trailing Stop Stepper Advances : {len(sl_steps)}",
            f"  • Active Open Positions Monitored: {len(open_positions)}",
            ""
        ]
        
        lines.append("2. EXECUTION & TRADES SUMMARY")
        lines.append(sub_sep)
        lines.append("[BUYS EXECUTED TODAY]")
        if buys_rows:
            for b in buys_rows:
                sym_b = str(b[0] or "")
                px_b = float(b[1]) if b[1] is not None else 0.0
                qty_b = int(b[2]) if b[2] is not None else 0
                sl_b = float(b[3]) if b[3] is not None else 0.0
                pat_b = str(b[4] or "Unknown")
                score_b = f"{b[5]:.1f}" if b[5] is not None else "4.0"
                rs_b = f"{b[6]:.1f}" if b[6] is not None else "50.0"
                lines.append(f"  • {sym_b:<6} | Qty: {qty_b:>4} | Price: ${px_b:>8.2f} | SL: ${sl_b:>8.2f} | Pattern: {pat_b} | Score: {score_b} | RS: {rs_b}")
        else:
            lines.append("  (No new positions established today)")
            
        lines.append("")
        lines.append("[EXITS & PROFIT TAKING TODAY]")
        if full_exits or partial_exits:
            for fe in full_exits:
                sym_fe = str(fe[0] or "")
                entry_fe = float(fe[1]) if fe[1] is not None else 0.0
                exit_fe = float(fe[2]) if fe[2] is not None else 0.0
                qty_fe = int(fe[3]) if fe[3] is not None else 0
                pnl_fe = float(fe[4]) if fe[4] is not None else 0.0
                reason_fe = str(fe[5] or "Exit")
                lines.append(f"  • {sym_fe:<6} | FULL EXIT ({reason_fe}) | Qty: {qty_fe} @ ${exit_fe:.2f} (Entry: ${entry_fe:.2f}) | P/L: {pnl_fe:+.2f}%")
            for pe in partial_exits:
                sym_pe = str(pe[0] or "")
                pt_pe = str(pe[1] or "PT")
                qty_pe = int(pe[2]) if pe[2] is not None else 0
                exit_pe = float(pe[3]) if pe[3] is not None else 0.0
                pnl_pe = float(pe[4]) if pe[4] is not None else 0.0
                lines.append(f"  • {sym_pe:<6} | PARTIAL EXIT {pt_pe} | Qty: {qty_pe} @ ${exit_pe:.2f} | Profit: {pnl_pe:+.2f}%")
        else:
            lines.append("  (No positions exited today)")
            
        lines.append("")
        lines.append("[TRAILING STOP STEPPER ADVANCES TODAY]")
        if sl_steps:
            for s in sl_steps:
                lines.append(f"  • {s['symbol']:<6} | ${s['old_sl']:.2f} -> ${s['new_sl']:.2f} | Stage {s['stage']} | Profit: {s['profit_pct']:+.2f}% | High: ${s['highest_price']:.2f} ({s['time']})")
        else:
            lines.append("  (No trailing stop steppers advanced today)")
            
        total_scanned = len(sig_rows)
        ma_period_cfg = int(self.config.get('market_regime', 'index_ma_period', 50))
        lines.append("")
        lines.append("3. SIGNAL GENERATION & GATE FUNNEL SUMMARY")
        lines.append(sub_sep)
        lines.append(f"  • Watchlist Signal Evaluations: {total_scanned}")
        lines.append(f"    ├─ Failed Gate 0 (Market Regime SPY/QQQ < {ma_period_cfg} SMA)    : {gate_counts['gate_0_regime']}")
        lines.append(f"    ├─ Failed Gate 1 (Market Structure 50 > 200 SMA)       : {gate_counts['gate_1_structure']}")
        lines.append(f"    ├─ Failed Gate 1.5 (MA Slope Downward)                 : {gate_counts['gate_1_5_slope']}")
        lines.append(f"    ├─ Failed Gate 2 (Preceding Pullback & Impulse)        : {gate_counts['gate_2_pullback']}")
        lines.append(f"    ├─ Failed Gate 3 (Candlestick Pattern / Touch)         : {gate_counts['gate_3_pattern']}")
        lines.append(f"    ├─ Failed Gate 4 (Weekly MTF Alignment)                : {gate_counts['gate_4_weekly']}")
        lines.append(f"    ├─ Failed Gate 6 (Stalling / Horizontal Churning)      : {gate_counts['gate_6_stalling']}")
        lines.append(f"    ├─ Failed Gate 6.25 (Extended Stock Gap > 4%)          : {gate_counts['gate_6_25_extended']}")
        lines.append(f"    ├─ Failed Gate 6.5 (Red Session / Lack of Absorption)  : {gate_counts['gate_6_5_red_candle']}")
        lines.append(f"    ├─ Failed Gate 6.75 (Shooting Star Upper Wick Reject)  : {gate_counts['gate_6_75_shooting_star']}")
        lines.append(f"    └─ Failed Gate 7 (Score < Min Threshold / Touch Gate)  : {gate_counts['gate_7_score']}")
        lines.append(f"  • Valid Signals (Passed All Gates)                      : {gate_counts['valid_signals']}")
        q_stat = self.signal_queue.get_queue_status()
        lines.append(f"  • Staged Candidates in Queue                            : {q_stat['signals_queued']}")
        lines.append(f"  • Buys Executed Today                                   : {len(buys_rows)}")
        
        lines.append("")
        lines.append(f"4. CLOSING OPEN PORTFOLIO HEALTH ({len(open_positions)} Open Positions)")
        lines.append(sub_sep)
        if open_positions:
            lines.append(f"{'Symbol':<7} | {'Buy Rate':>9} | {'Curr Price':>10} | {'Qty':>5} | {'P/L (%)':>8} | {'Stop Loss':>10} | {'Stage':>10} | {'Peak':>9} | {'Runner'}")
            lines.append(sub_sep)
            tot_cost = 0.0
            tot_val = 0.0
            for pos in open_positions:
                px = self.data_fetcher.get_current_price(pos['symbol']) or pos['entry_price']
                pl_pct = (px - pos['entry_price']) / pos['entry_price'] * 100
                stg = f"Stage {pos.get('sl_stage', 0)}"
                pk = max(pos.get('highest_price_seen') or px, px)
                runner_str = "YES" if pos.get('is_runner') else "NO"
                lines.append(f"{pos['symbol']:<7} | ${pos['entry_price']:>8.2f} | ${px:>9.2f} | {pos['remaining_qty']:>5} | {pl_pct:>+7.2f}% | ${pos['stop_loss']:>9.2f} | {stg:>10} | ${pk:>8.2f} | {runner_str:^6}")
                tot_cost += pos['entry_price'] * pos['remaining_qty']
                tot_val += px * pos['remaining_qty']
            tot_pl = tot_val - tot_cost
            tot_pl_pct = (tot_pl / tot_cost * 100) if tot_cost > 0 else 0.0
            lines.append(sub_sep)
            lines.append(f"Portfolio Cost: ${tot_cost:,.2f} | Current Value: ${tot_val:,.2f} | Unrealized P/L: ${tot_pl:+,.2f} ({tot_pl_pct:+.2f}%)")
        else:
            lines.append("  (No open positions currently in portfolio)")
        lines.append(sep)
        
        report_text = "\n" + "\n".join(lines) + "\n"
        
        # Log to primary logger
        logger.info(report_text)
        
        # Append single clean entry to logs/daily_snapshot.log
        snapshot_dir = 'logs'
        os.makedirs(snapshot_dir, exist_ok=True)
        snapshot_file = os.path.join(snapshot_dir, 'daily_snapshot.log')
        try:
            with open(snapshot_file, 'a', encoding='utf-8') as f:
                f.write(report_text + "\n")
            logger.info(f"📁 Daily Executive Snapshot saved to {snapshot_file}")
        except Exception as e:
            logger.error(f"Failed to write snapshot to {snapshot_file}: {e}")

    def run(self):
        """Master execution loop"""
        logger.info("Starting master execution loop...")
        while True:
            try:
                self.process_manual_overrides()
                if self.is_market_open():
                    # Reset snapshot flag at beginning of active trading day
                    if self.daily_snapshot_done:
                        self.daily_snapshot_done = False
                        self.position_manager.daily_sl_steps.clear()
                        self.position_manager.daily_buys.clear()
                        self.position_manager.daily_exits.clear()
                        logger.info("🔔 Market Open Transition: Performing Opening Bell Broker Position Reconciliation...")
                        if self.config.get('execution_schedule', 'enable_broker_reconciliation', True):
                            self.reconcile_positions_with_broker()
                        
                    self.run_sell_guardian()
                    self.run_buy_hunter()
                    interval = 60 if self.is_buy_window() else 120
                    logger.info(f"--- Cycle complete. Next portfolio monitor scan in {interval}s ---")
                    time.sleep(interval)
                else:
                    now_et = datetime.now(pytz.timezone('US/Eastern'))
                    if not self.daily_snapshot_done and now_et.weekday() <= 4 and now_et.hour >= 16:
                        logger.info("🔔 Market Close Transition: Performing End-of-Day Broker Position Reconciliation...")
                        if self.config.get('execution_schedule', 'enable_broker_reconciliation', True):
                            self.reconcile_positions_with_broker()
                        self.generate_daily_market_close_snapshot()
                        self.daily_snapshot_done = True
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
