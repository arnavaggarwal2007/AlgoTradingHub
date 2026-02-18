"""
================================================================================
RAJAT ALPHA V67 - ALPACA ALGORITHMIC TRADING BOT
================================================================================

STRATEGY: Single Buy Entry with Dynamic Trailing Stop Loss and Partial Exits
BASED ON: Rajat Alpha v67 Strategy Single Buy (PineScript)
PLATFORM: Alpaca Trading API
VERSION: 1.0
DATE: January 11, 2026

CORE LOGIC:
1. Entry Requirements (ALL MUST BE TRUE):
   - Market Structure: 50 SMA > 200 SMA AND 21 EMA > 50 SMA
   - Pullback Detection: Price near 21 EMA or 50 SMA after downtrend
   - Pattern Confirmation: Engulfing/Piercing/Tweezer (MANDATORY)
   - Multi-Timeframe: Weekly close > Weekly EMA21 AND Monthly close > Monthly EMA10
   - Maturity Filter: Stock traded >= 200 days
   - Stalling Filter: Not in sideways consolidation (5% range over 8 days)
   - Volume Check: Above 21-day average
   - Scoring: 0-5 base score + touch bonuses

2. Exit Management:
   - Dynamic Trailing Stop Loss (3-tier): 17% → 9% @ +5% profit → 1% @ +10% profit
   - Partial Exits: 1/3 Rule (33.3% @ 10%, 33.3% @ 15%, 33.4% @ 20%)
   - Time Exit Signal (TES): Max hold days (default 21)
   - FIFO: First In First Out selling

3. Risk Management:
   - Position Sizing: Configurable (% of equity or fixed dollar amount)
   - Max Loss Per Trade: Configurable ($ or %)
   - Max Open Positions: Configurable (default 2 for single buy system)
   - Stop Loss: Closing basis (configurable)

4. Execution Schedule:
   - Run every 2 minutes until last hour of trading
   - Run every 1 minute in last hour
   - Buy only in last hour (configurable 15-minute timeframe)
   - Sell executes anytime when target hit

REQUIREMENTS:
- Python 3.8+
- alpaca-py
- pandas
- pandas-ta
- sqlite3
- pytz

================================================================================
"""

import json
import time
import math
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd
import pandas_ta as ta
import pytz

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame

# ================================================================================
# LOGGING SETUP
# ================================================================================

import json
import logging
from datetime import datetime
from pythonjsonlogger import jsonlogger

class ComplianceJSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for compliance and audit logging"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add compliance-required fields
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Add trading-specific context if available
        if hasattr(record, 'symbol'):
            log_record['symbol'] = record.symbol
        if hasattr(record, 'trade_id'):
            log_record['trade_id'] = record.trade_id
        if hasattr(record, 'order_id'):
            log_record['order_id'] = record.order_id
        if hasattr(record, 'pnl'):
            log_record['pnl'] = record.pnl

# Setup structured logging
logger = logging.getLogger('rajat_alpha_v67')
logger.setLevel(logging.INFO)

# Console handler with human-readable format
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler with JSON format for compliance
file_handler = logging.FileHandler('logs/rajat_alpha_v67.log')
json_formatter = ComplianceJSONFormatter(
    '%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(line)s %(message)s'
)
file_handler.setFormatter(json_formatter)
logger.addHandler(file_handler)

# Separate audit log for critical events
audit_handler = logging.FileHandler('logs/audit.log')
audit_handler.setLevel(logging.WARNING)  # Only warnings and above
audit_handler.setFormatter(json_formatter)
logger.addHandler(audit_handler)

# ================================================================================
# DATABASE SETUP (Position Tracking)
# ================================================================================

class PositionDatabase:
    """
    SQLite database to track:
    - Entry prices, dates, quantities
    - Partial exit tracking
    - FIFO queue management
    - TES (Time Exit Signal) monitoring
    """
    
    def __init__(self, db_path='db/positions.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                remaining_qty INTEGER NOT NULL,
                stop_loss REAL NOT NULL,
                status TEXT DEFAULT 'OPEN',
                exit_date TEXT,
                exit_price REAL,
                profit_loss_pct REAL,
                exit_reason TEXT,
                score REAL,
                pattern TEXT DEFAULT 'Unknown',
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def add_position(self, symbol: str, entry_price: float, quantity: int, 
                     stop_loss: float, score: float, pattern: str = 'Unknown') -> int:
        """Add new position to database with pattern tracking"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, quantity, 
                                   remaining_qty, stop_loss, score, pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, datetime.now().isoformat(), entry_price, quantity, 
              quantity, stop_loss, score, pattern))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open positions (FIFO order)"""
        cursor = self.conn.cursor()
        if symbol:
            cursor.execute('''
                SELECT * FROM positions 
                WHERE symbol = ? AND status = 'OPEN'
                ORDER BY entry_date ASC
            ''', (symbol,))
        else:
            cursor.execute('''
                SELECT * FROM positions 
                WHERE status = 'OPEN'
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
        """Update trailing stop loss"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE positions SET stop_loss = ? WHERE id = ?
        ''', (new_stop_loss, position_id))
        self.conn.commit()
    
    def add_partial_exit(self, position_id: int, quantity: int, exit_price: float,
                        profit_target: str, profit_pct: float):
        """Record partial exit"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO partial_exits (position_id, exit_date, quantity, 
                                       exit_price, profit_target, profit_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (position_id, datetime.now().isoformat(), quantity, exit_price,
              profit_target, profit_pct))
        
        # Update remaining quantity
        cursor.execute('''
            UPDATE positions 
            SET remaining_qty = remaining_qty - ?
            WHERE id = ?
        ''', (quantity, position_id))
        self.conn.commit()
    
    def close_position(self, position_id: int, exit_price: float, exit_reason: str):
        """Close position completely"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT entry_price, remaining_qty FROM positions WHERE id = ?
        ''', (position_id,))
        entry_price, remaining_qty = cursor.fetchone()
        
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
        """Calculate days held for TES check"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT entry_date FROM positions WHERE id = ?
        ''', (position_id,))
        entry_date_str = cursor.fetchone()[0]
        entry_date = datetime.fromisoformat(entry_date_str)
        return (datetime.now() - entry_date).days
    
    def count_trades_today(self) -> int:
        """
        Count total trades executed today (opened positions)
        
        Used by: Feature #1 - Max Trades Per Day Limit
        
        Returns:
            int: Number of trades (positions) opened today
            
        Note:
            - Counts both successful and failed trade attempts
            - Resets automatically at midnight (date comparison)
            - Thread-safe via SQLite
        """
        today_date = datetime.now().date().isoformat()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM positions 
            WHERE date(entry_date) = ?
        ''', (today_date,))
        return cursor.fetchone()[0]
    
    def was_traded_today(self, symbol: str) -> bool:
        """
        Check if a specific symbol was traded today (has open positions)
        
        Used by: Feature #2 - Same-Day Protection
        
        Args:
            symbol: Stock ticker symbol to check
            
        Returns:
            bool: True if symbol has open positions from today, False otherwise
            
        Note:
            - Only checks OPEN positions (not closed ones)
            - Uses entry_date to determine if position was opened today
            - Thread-safe via SQLite
        """
        today_date = datetime.now().date().isoformat()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM positions 
            WHERE symbol = ? AND status = 'OPEN' AND date(entry_date) = ?
        ''', (symbol, today_date))
        count = cursor.fetchone()[0]
        return count > 0
    
    def log_signal(self, symbol: str, signal_details: Dict, executed: bool):
        """
        Log signal to history for analysis and debugging
        ONLY stores signals with valid scores > 0

        Used by: Feature #4 - Signal History Tracking

        Args:
            symbol: Stock ticker symbol
            signal_details: Dict containing signal data (score, pattern, price, reason)
            executed: True if trade was executed, False if signal detected but not traded

        Database Table:
            signal_history (see create_tables() for schema)

        Query Examples:
            - Today's signals: WHERE signal_date = date('now')
            - Missed opportunities: WHERE executed = 0 AND score >= 4
            - Pattern analysis: GROUP BY pattern
        """
        score = signal_details.get('score', 0)

        # Only log signals with valid scores > 0
        if score <= 0:
            logger.debug(f"[{symbol}] Skipping signal logging - invalid score: {score}")
            return

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO signal_history (symbol, signal_date, score, pattern, price, reason, executed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, datetime.now().date().isoformat(), score,
              signal_details.get('pattern', 'None'), signal_details.get('price', 0),
              signal_details.get('reason', ''), executed))
        self.conn.commit()

        logger.debug(f"[{symbol}] Signal logged to history (Score: {score}, Executed: {executed})")
    
    def get_performance_by_score(self) -> List[Dict]:
        """
        Analyze performance grouped by entry score
        
        Returns:
            List of dicts with: score, trades, win_rate, avg_pl, avg_win, avg_loss, max_pl, min_pl
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                score,
                COUNT(*) as trades,
                ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
                ROUND(AVG(profit_loss_pct), 2) as avg_pl,
                ROUND(AVG(CASE WHEN profit_loss_pct > 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_win,
                ROUND(AVG(CASE WHEN profit_loss_pct < 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_loss,
                ROUND(MAX(profit_loss_pct), 2) as max_pl,
                ROUND(MIN(profit_loss_pct), 2) as min_pl
            FROM positions 
            WHERE status = 'CLOSED'
            GROUP BY score
            ORDER BY score DESC
        ''')
        columns = ['score', 'trades', 'win_rate', 'avg_pl', 'avg_win', 'avg_loss', 'max_pl', 'min_pl']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_performance_by_pattern(self) -> List[Dict]:
        """
        Analyze performance grouped by entry pattern
        
        Returns:
            List of dicts with: pattern, trades, win_rate, avg_pl, avg_win, avg_loss
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                pattern,
                COUNT(*) as trades,
                ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
                ROUND(AVG(profit_loss_pct), 2) as avg_pl,
                ROUND(AVG(CASE WHEN profit_loss_pct > 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_win,
                ROUND(AVG(CASE WHEN profit_loss_pct < 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_loss
            FROM positions 
            WHERE status = 'CLOSED'
            GROUP BY pattern
            ORDER BY win_rate DESC
        ''')
        columns = ['pattern', 'trades', 'win_rate', 'avg_pl', 'avg_win', 'avg_loss']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_performance_by_score_and_pattern(self) -> List[Dict]:
        """
        Cross-tabulation of score x pattern performance
        
        Returns:
            List of dicts with: score, pattern, trades, win_rate, avg_pl
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                score,
                pattern,
                COUNT(*) as trades,
                ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
                ROUND(AVG(profit_loss_pct), 2) as avg_pl
            FROM positions 
            WHERE status = 'CLOSED'
            GROUP BY score, pattern
            ORDER BY score DESC, win_rate DESC
        ''')
        columns = ['score', 'pattern', 'trades', 'win_rate', 'avg_pl']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

# ================================================================================
# CONFIGURATION MANAGER
# ================================================================================

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        self.validate_config()
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_path} not found!")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
    
    def validate_config(self):
        """Validate required configuration keys and value ranges"""
        # Required sections
        required_sections = [
            'api', 'trading_rules', 'strategy_params', 
            'risk_management', 'profit_taking', 'execution_schedule'
        ]
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # API validation
        api_keys = ['key_id', 'secret_key', 'base_url']
        for key in api_keys:
            if key not in self.config['api']:
                raise ValueError(f"Missing API configuration: {key}")
            if not self.config['api'][key]:
                raise ValueError(f"Empty API configuration: {key}")
        
        # Trading rules validation
        trading_rules = self.config['trading_rules']
        if trading_rules.get('max_open_positions', 0) <= 0:
            raise ValueError("max_open_positions must be > 0")
        if trading_rules.get('max_trades_per_day', 0) <= 0:
            raise ValueError("max_trades_per_day must be > 0")
        if not (0 <= trading_rules.get('min_signal_score', 0) <= 5):
            raise ValueError("min_signal_score must be between 0 and 5")
        
        # Strategy params validation
        strategy = self.config['strategy_params']
        if strategy.get('min_listing_days', 0) < 30:
            raise ValueError("min_listing_days must be >= 30")
        if strategy.get('sma_fast', 0) <= 0 or strategy.get('sma_slow', 0) <= 0:
            raise ValueError("SMA periods must be > 0")
        if strategy.get('sma_fast', 0) >= strategy.get('sma_slow', 0):
            raise ValueError("sma_fast must be < sma_slow")
        
        # Risk management validation
        risk = self.config['risk_management']
        if not (0 < risk.get('initial_stop_loss_pct', 0) < 1):
            raise ValueError("initial_stop_loss_pct must be between 0 and 1")
        if risk.get('max_hold_days', 0) <= 0:
            raise ValueError("max_hold_days must be > 0")
        
        # Profit taking validation
        profit = self.config['profit_taking']
        if profit.get('enable_partial_exits', False):
            targets = [profit.get(f'target_{i}_pct', 0) for i in range(1, 4)]
            quantities = [profit.get(f'target_{i}_qty', 0) for i in range(1, 4)]
            
            # Check ascending profit targets
            if not all(targets[i] < targets[i+1] for i in range(len(targets)-1)):
                raise ValueError("Profit targets must be in ascending order")
            
            # Check quantities sum to ~1.0
            total_qty = sum(quantities)
            if not (0.99 <= total_qty <= 1.01):
                raise ValueError(f"Profit target quantities must sum to 1.0, got {total_qty}")
        
        # Execution schedule validation
        exec_sched = self.config['execution_schedule']
        if exec_sched.get('signal_monitoring_minutes', 0) <= 0:
            raise ValueError("signal_monitoring_minutes must be > 0")
        if exec_sched.get('default_interval_seconds', 0) <= 0:
            raise ValueError("default_interval_seconds must be > 0")
        if exec_sched.get('last_hour_interval_seconds', 0) <= 0:
            raise ValueError("last_hour_interval_seconds must be > 0")
        
        # Time format validation
        import re
        time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
        for time_key in ['buy_window_start_time', 'buy_window_end_time']:
            if time_key in exec_sched:
                if not time_pattern.match(exec_sched[time_key]):
                    raise ValueError(f"Invalid time format for {time_key}: {exec_sched[time_key]}")
        
        logger.info("Configuration validation passed - all parameters within acceptable ranges")
    
    def get(self, section, key, default=None):
        """Get configuration value"""
        section_data = self.config.get(section)
        if section_data is None:
            return default
        return section_data.get(key, default)

# ================================================================================
# MARKET DATA FETCHER
# ================================================================================

class MarketDataFetcher:
    """Handles all market data retrieval and caching"""
    
    def __init__(self, data_client: StockHistoricalDataClient):
        self.data_client = data_client
        self.cache = {}
        self.cache_expiry = {}
    
    def get_daily_bars(self, symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch daily bars with caching"""
        cache_key = f"{symbol}_daily"
        
        # Check cache (5-minute expiry)
        if cache_key in self.cache:
            if datetime.now() < self.cache_expiry[cache_key]:
                return self.cache[cache_key]
        
        try:
            start_date = datetime.now() - timedelta(days=days)
            params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_date
            )
            bars = self.data_client.get_stock_bars(params)
            
            if not bars.data.get(symbol):
                logger.warning(f"No data returned for {symbol}")
                return None
            
            df = bars.df.loc[symbol].copy()
            
            # Cache for 5 minutes
            self.cache[cache_key] = df
            self.cache_expiry[cache_key] = datetime.now() + timedelta(minutes=5)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching daily bars for {symbol}: {e}")
            return None
    
    def get_weekly_bars(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """Aggregate daily bars to weekly"""
        logic = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        return df_daily.resample('W-FRI').agg(logic)
    
    def get_monthly_bars(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """Aggregate daily bars to monthly"""
        logic = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        return df_daily.resample('ME').agg(logic)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get latest price"""
        try:
            params = StockLatestBarRequest(symbol_or_symbols=symbol)
            bars = self.data_client.get_stock_latest_bar(params)
            return float(bars[symbol].close)
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

# ================================================================================
# PATTERN RECOGNITION
# ================================================================================

class PatternDetector:
    """Detects explosive bullish candle patterns"""
    
    @staticmethod
    def is_engulfing(df: pd.DataFrame) -> bool:
        """
        Engulfing Pattern:
        - Today's close >= yesterday's open
        - Yesterday was red candle
        """
        if len(df) < 2:
            return False
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_green = curr['close'] > curr['open']
        prev_is_red = prev['close'] < prev['open']
        
        return is_green and (curr['close'] >= prev['open']) and prev_is_red
    
    @staticmethod
    def is_piercing(df: pd.DataFrame) -> bool:
        """Piercing Pattern with Explosive Body"""
        if len(df) < 2:
            return False
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_green = curr['close'] > curr['open']
        prev_is_red = prev['close'] < prev['open']
        
        midpoint = (prev['open'] + prev['close']) / 2
        is_classic_piercing = (curr['close'] > midpoint) and \
                             (curr['close'] < prev['open']) and \
                             prev_is_red
        
        # Check explosive body
        candle_range = curr['high'] - curr['low']
        body_size = curr['close'] - curr['open']
        is_explosive = (body_size / candle_range) >= 0.40 if candle_range > 0 else False
        
        return is_green and is_classic_piercing and is_explosive
    
    @staticmethod
    def is_tweezer_bottom(df: pd.DataFrame) -> bool:
        """
        Tweezer Bottom:
        - Today's low within 0.2% of yesterday's low
        - Yesterday was red candle
        """
        if len(df) < 2:
            return False
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_green = curr['close'] > curr['open']
        prev_is_red = prev['close'] < prev['open']
        
        low_match = abs(curr['low'] - prev['low']) <= (curr['low'] * 0.002)
        
        return is_green and low_match and prev_is_red
    
    @classmethod
    def has_pattern(cls, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check for ANY explosive pattern (MANDATORY for entry)
        Returns: (pattern_found, pattern_name)
        """
        if cls.is_engulfing(df):
            return True, "Engulfing"
        if cls.is_piercing(df):
            return True, "Piercing"
        if cls.is_tweezer_bottom(df):
            return True, "Tweezer"
        return False, "None"

# ================================================================================
# STRATEGY ANALYZER (Core Rajat Alpha v67 Logic)
# ================================================================================

class RajatAlphaAnalyzer:
    """
    Implements complete Rajat Alpha v67 strategy logic
    """
    
    def __init__(self, config: ConfigManager, data_fetcher: MarketDataFetcher):
        self.config = config
        self.data_fetcher = data_fetcher
        
        # Touch tracking variables
        self.new_trend = True
        self.touch_ema21_count = 0
        self.touch_sma50_count = 0
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all required technical indicators"""
        df['SMA50'] = ta.sma(df['close'], length=50)
        df['SMA200'] = ta.sma(df['close'], length=200)
        df['EMA21'] = ta.ema(df['close'], length=21)
        df['VOL_SMA21'] = ta.sma(df['volume'], length=21)
        df['RSI14'] = ta.rsi(df['close'], length=14)
        return df
    
    def update_touch_tracking(self, df: pd.DataFrame):
        """
        Update touch tracking for bonus scoring
        - Reset on new trend (SMA50 crosses above SMA200)
        - Increment counters on EMA21/SMA50 touches
        """
        if len(df) < 2:
            return
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Check for new trend (SMA50 crosses above SMA200)
        if (prev['SMA50'] <= prev['SMA200']) and (curr['SMA50'] > curr['SMA200']):
            self.new_trend = True
            self.touch_ema21_count = 0
            self.touch_sma50_count = 0
            logger.debug("New trend detected - touch counters reset")
        else:
            self.new_trend = False
        
        # Check for EMA21 touch (price within 2.5% of EMA21)
        if curr['EMA21'] > 0:
            ema_dist = abs(curr['close'] - curr['EMA21']) / curr['EMA21']
            if ema_dist <= self.config.get('strategy_params', 'ma_touch_threshold_pct'):
                self.touch_ema21_count += 1
                logger.debug(f"EMA21 touch detected (count: {self.touch_ema21_count})")
        
        # Check for SMA50 touch (price within 2.5% of SMA50)
        if curr['SMA50'] > 0:
            sma_dist = abs(curr['close'] - curr['SMA50']) / curr['SMA50']
            if sma_dist <= self.config.get('strategy_params', 'ma_touch_threshold_pct'):
                self.touch_sma50_count += 1
                logger.debug(f"SMA50 touch detected (count: {self.touch_sma50_count})")
        
        # Cap touch counts at 3 (no signals after 3rd touch)
        if self.touch_ema21_count > 3:
            self.touch_ema21_count = 3
        if self.touch_sma50_count > 3:
            self.touch_sma50_count = 3
    
    def check_market_structure(self, df: pd.DataFrame) -> bool:
        """
        Requirement: 50 SMA > 200 SMA AND 21 EMA >= 50 SMA * (1 - ema_tolerance_pct)
        Allows EMA21 to be up to ema_tolerance_pct (2.5%) below SMA50 for flexibility
        """
        curr = df.iloc[-1]
        
        if pd.isna(curr['SMA50']) or pd.isna(curr['SMA200']) or pd.isna(curr['EMA21']):
            return False
        
        # Get EMA tolerance from config (default 2.5%)
        ema_tolerance_pct = self.config.get('strategy_params', 'ema_tolerance_pct', 0.025)
        
        # Relaxed EMA condition: EMA21 can be up to tolerance_pct below SMA50
        ema_threshold = curr['SMA50'] * (1 - ema_tolerance_pct)
        
        return (curr['SMA50'] > curr['SMA200']) and (curr['EMA21'] >= ema_threshold)
    
    def check_touch_based_signal(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Touch-Based Signal Detection:
        - Stock touches EMA21 or SMA50 (within ma_touch_threshold_pct)
        - After touching, forms green candle with >40% body
        - Touch must have stayed for at least touch_min_stay_days
        - Look back up to touch_lookback_months for qualifying touches
        
        Returns: (signal_found, signal_type)
        """
        if len(df) < 30:  # Need minimum data
            return False, "insufficient_data"
        
        # Get touch parameters from config
        touch_threshold_pct = self.config.get('strategy_params', 'ma_touch_threshold_pct', 0.025)
        min_body_pct = self.config.get('strategy_params', 'touch_min_body_pct', 0.40)
        min_stay_days = self.config.get('strategy_params', 'touch_min_stay_days', 5)
        lookback_months = self.config.get('strategy_params', 'touch_lookback_months', 2)
        
        # Calculate lookback period (approximately months * 21 trading days)
        lookback_days = lookback_months * 21
        lookback_window = min(lookback_days, len(df) - 1)  # Don't exceed available data
        
        # Check recent candles for touch + green candle pattern
        for i in range(-lookback_window, 0):  # Look backwards from current candle
            curr_candle = df.iloc[i]
            
            # Check if this candle touched EMA21 or SMA50
            ema21_dist = abs(curr_candle['close'] - curr_candle['EMA21']) / curr_candle['EMA21'] if curr_candle['EMA21'] > 0 else 1.0
            sma50_dist = abs(curr_candle['close'] - curr_candle['SMA50']) / curr_candle['SMA50'] if curr_candle['SMA50'] > 0 else 1.0
            
            touched_ema21 = ema21_dist <= touch_threshold_pct
            touched_sma50 = sma50_dist <= touch_threshold_pct
            
            if touched_ema21 or touched_sma50:
                # Check if touch stayed for minimum days
                touch_stay_count = 0
                for j in range(i, min(i + min_stay_days, 0)):  # Check next min_stay_days
                    check_candle = df.iloc[j]
                    check_ema_dist = abs(check_candle['close'] - check_candle['EMA21']) / check_candle['EMA21'] if check_candle['EMA21'] > 0 else 1.0
                    check_sma_dist = abs(check_candle['close'] - check_candle['SMA50']) / check_candle['SMA50'] if check_candle['SMA50'] > 0 else 1.0
                    
                    if check_ema_dist <= touch_threshold_pct or check_sma_dist <= touch_threshold_pct:
                        touch_stay_count += 1
                
                if touch_stay_count >= min_stay_days:
                    # Check for green candle with sufficient body after touch
                    # Look at the next candle after the touch period
                    next_candle_idx = i + min_stay_days
                    if next_candle_idx <= 0 and abs(next_candle_idx) < len(df):  # Ensure we have data for the next candle
                        next_candle = df.iloc[next_candle_idx]
                        
                        # Check if it's a green candle (close > open)
                        is_green = next_candle['close'] > next_candle['open']
                        
                        if is_green:
                            # Check body size (>40% of total range)
                            body_size = abs(next_candle['close'] - next_candle['open'])
                            total_range = next_candle['high'] - next_candle['low']
                            
                            if total_range > 0:
                                body_pct = body_size / total_range
                                if body_pct > min_body_pct:
                                    signal_type = "EMA21_Touch" if touched_ema21 else "SMA50_Touch"
                                    return True, signal_type
        
        return False, "no_touch_signal"
    
    def check_multitimeframe_confirmation(self, df_daily: pd.DataFrame, 
                                     df_weekly: pd.DataFrame, 
                                     df_monthly: pd.DataFrame) -> Tuple[bool, bool]:
        """
        Weekly: close > Weekly EMA21
        Monthly: close > Monthly EMA10
        """
        # Calculate weekly/monthly indicators
        df_weekly['EMA21'] = ta.ema(df_weekly['close'], length=21)
        df_monthly['EMA10'] = ta.ema(df_monthly['close'], length=10)
        
        curr_w = df_weekly.iloc[-1]
        curr_m = df_monthly.iloc[-1]
        
        weekly_ok = curr_w['close'] > curr_w['EMA21'] if not pd.isna(curr_w['EMA21']) else False
        monthly_ok = curr_m['close'] > curr_m['EMA10'] if not pd.isna(curr_m['EMA10']) else False
        
        return weekly_ok, monthly_ok
    
    def check_pullback(self, df: pd.DataFrame) -> bool:
        """
        Pullback Detection:
        - Price near 21 EMA or 50 SMA (within 2.5%)
        - Recent pullback (highest high in last 4 bars > current high)
        - Downtrend confirmation: at least 2 of last 4 bars close < EMA21
        - Pattern hit: explosive pattern detected (passed as parameter)
        """
        pullback_days = self.config.get('strategy_params', 'pullback_days')
        curr = df.iloc[-1]
        
        # Near MA check
        dist_ema21 = abs(curr['close'] - curr['EMA21']) / curr['EMA21'] if curr['EMA21'] > 0 else 1.0
        dist_sma50 = abs(curr['close'] - curr['SMA50']) / curr['SMA50'] if curr['SMA50'] > 0 else 1.0
        near_ma = (dist_ema21 <= self.config.get('strategy_params', 'ma_touch_threshold_pct')) or (dist_sma50 <= self.config.get('strategy_params', 'ma_touch_threshold_pct'))
        
        # Pullback check
        if len(df) < pullback_days + 1:
            return False
        
        recent_high = df['high'].iloc[-(pullback_days+1):-1].max()
        is_pullback = recent_high > curr['high']
        
        # Downtrend count: bars where close < EMA21 in last 4 bars
        downtrend_window = min(4, len(df))
        downtrend_count = sum(1 for i in range(-downtrend_window, 0) 
                             if df.iloc[i]['close'] < df.iloc[i]['EMA21'])
        
        # Require at least 2 downtrend bars for confirmation
        downtrend_confirmed = downtrend_count >= 2
        
        return bool(near_ma and is_pullback and downtrend_confirmed)
    
    def check_stalling(self, df: pd.DataFrame, stalling_days_long: int = None, stalling_days_short: int = None) -> bool:
        """
        Stalling Filter:
        - Reject if long-term range <= threshold (stalling_days_long)
        - UNLESS short-term range also <= threshold (recent consolidation)
        """
        if stalling_days_long is None:
            stalling_days_long = self.config.get('strategy_params', 'stalling_days_long')
        if stalling_days_short is None:
            stalling_days_short = self.config.get('strategy_params', 'stalling_days_short')
        
        stalling_range_pct = self.config.get('strategy_params', 'stalling_range_pct')
        
        if len(df) < stalling_days_long:
            return False  # Not enough data, assume no stalling
        
        # Long-term check
        window_long = df.iloc[-stalling_days_long:]
        range_long = window_long['high'].max() - window_long['low'].min()
        avg_price_long = (window_long['high'].max() + window_long['low'].min()) / 2
        
        if avg_price_long == 0:
            return False
        
        range_pct_long = (range_long / avg_price_long) * 100
        is_stalling_long = range_pct_long <= stalling_range_pct
        
        # Short-term check
        window_short = df.iloc[-stalling_days_short:]
        range_short = window_short['high'].max() - window_short['low'].min()
        avg_price_short = (window_short['high'].max() + window_short['low'].min()) / 2
        
        if avg_price_short == 0:
            return False
        
        range_pct_short = (range_short / avg_price_short) * 100
        is_consolidating = range_pct_short <= stalling_range_pct
        
        # Stalling detected if long-term choppy but NOT recent consolidation
        return is_stalling_long and not is_consolidating
    
    def check_extended_stock(self, df: pd.DataFrame, current_price: float) -> Tuple[bool, float]:
        """
        Check if stock is extended (gapped up beyond threshold from previous close)
        
        Used by: Feature #3 - Extended Stock Filter
        
        Purpose:
            Prevents buying stocks that have already "run away" with large gaps.
            Focuses strategy on pullback entries, not breakout entries.
            
        Args:
            df: Daily OHLCV dataframe with historical prices
            current_price: Current market price of the stock
            
        Returns:
            Tuple[bool, float]: (is_extended, gap_percentage)
                - is_extended: True if gap > max_gap_pct threshold
                - gap_percentage: Actual gap as decimal (0.05 = 5%)
                
        Example:
            Previous close: $100
            Current price: $105.50
            Gap = (105.50 - 100) / 100 = 0.055 (5.5%)
            If max_gap_pct = 0.04 (4%), returns (True, 0.055)
            
        Configuration:
            strategy_params.enable_extended_filter: Enable/disable feature
            strategy_params.max_gap_pct: Maximum allowed gap (default: 0.04 = 4%)
            strategy_params.lookback_for_gap: Days to look back (default: 1)
        """
        if len(df) < 2:
            return False, 0.0
        
        lookback = self.config.get('strategy_params', 'lookback_for_gap')
        prev_close = df.iloc[-(lookback + 1)]['close']
        gap_pct = (current_price - prev_close) / prev_close
        
        max_gap_pct = self.config.get('strategy_params', 'max_gap_pct')
        is_extended = gap_pct > max_gap_pct
        
        return is_extended, gap_pct
    
    def calculate_score(self, df: pd.DataFrame, symbol: str, weekly_ok: bool, monthly_ok: bool, pattern_found: bool = False, touch_signal_found: bool = False) -> float:
        """
        Scoring System (0-5 + bonuses):
        1. RSI Momentum Filter (>50 indicates bullish momentum) (+1)
        2. Weekly OK (+1)
        3. Monthly OK (+1)
        4. Volume > 21-day average (+1)
        5. Price in Demand Zone (3.5% above 21-day low) (+1)
        BONUSES:
        - EMA21 Touch: 1st (+1.0), 2nd (+0.5), 3rd (0.0)
        - SMA50 Touch: 1st (+1.0), 2nd (+0.5), 3rd (0.0)
        - Bullish pattern on touch signal (+1.0)
        """
        curr = df.iloc[-1]
        score = 0
        
        # 1. RSI Momentum Filter (>50 indicates bullish momentum)
        try:
            rsi_value = curr['RSI14']
            if not pd.isna(rsi_value) and rsi_value > 50:
                score += 1
                logger.debug(f"[{symbol}] RSI momentum: {rsi_value:.1f} > 50 (bullish)")
            else:
                logger.debug(f"[{symbol}] RSI momentum: {rsi_value:.1f} <= 50 (neutral/bearish)")
        except Exception as e:
            logger.warning(f"[{symbol}] Error calculating RSI: {e}")
        
        # 2. Weekly OK (checked separately)
        if weekly_ok:
            score += 1
        # 3. Monthly OK (checked separately)
        if monthly_ok:
            score += 1

        # 4. Volume above average
        if curr['volume'] > curr['VOL_SMA21']:
            score += 1
        
        # 5. Demand Zone (within 3.5% of 21-day low)
        low_21 = df['low'].iloc[-21:].min()
        dz_threshold = low_21 * 1.035
        if curr['low'] <= dz_threshold:
            score += 1
        
        # BONUSES: Touch bonuses with 1st/2nd/3rd differentiation
        if self.touch_ema21_count == 1:
            score += 1.0  # 1st touch = 1 point
        elif self.touch_ema21_count == 2:
            score += 0.5  # 2nd touch = 0.5 points
        # 3rd touch = 0 points, 4th+ ignored
        
        if self.touch_sma50_count == 1:
            score += 1.0  # 1st touch = 1 point
        elif self.touch_sma50_count == 2:
            score += 0.5  # 2nd touch = 0.5 points
        # 3rd touch = 0 points, 4th+ ignored
        
        # Extra +1 for bullish patterns on touch signals
        if touch_signal_found and pattern_found:
            score += 1.0
        
        return score
    
    def analyze_entry_signal(self, symbol: str) -> Tuple[bool, Dict]:
        """
        COMPLETE ENTRY ANALYSIS
        Returns: (signal_valid, signal_details)
        """
        result = {
            'symbol': symbol,
            'signal': False,
            'reason': '',
            'score': 0,
            'pattern': 'None',
            'signal_types': [],
            'price': 0,
            'checks': {}
        }
        
        # Get market data
        df_daily = self.data_fetcher.get_daily_bars(symbol, days=365)
        if df_daily is None or len(df_daily) < self.config.get('strategy_params', 'min_listing_days'):
            result['reason'] = "Insufficient data or immature stock"
            return False, result
        
        # Calculate indicators
        df_daily = self.calculate_indicators(df_daily)
        df_weekly = self.data_fetcher.get_weekly_bars(df_daily)
        df_monthly = self.data_fetcher.get_monthly_bars(df_daily)
        
        # Update touch tracking
        self.update_touch_tracking(df_daily)
        
        # CHECK 1: Market Structure
        structure_ok = self.check_market_structure(df_daily)
        result['checks']['market_structure'] = structure_ok
        if not structure_ok:
            result['reason'] = "Market structure not bullish (50 SMA > 200 SMA, 21 EMA > 50 SMA required)"
            logger.info(f"[{symbol}] ❌ Market Structure: FAILED - SMA50: {df_daily.iloc[-1]['SMA50']:.2f}, SMA200: {df_daily.iloc[-1]['SMA200']:.2f}, EMA21: {df_daily.iloc[-1]['EMA21']:.2f}")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Market Structure: PASSED - Bullish alignment confirmed")
        
        # CHECK 2: Multi-Timeframe Confirmation
        weekly_ok, monthly_ok = self.check_multitimeframe_confirmation(df_daily, df_weekly, df_monthly)
        result['checks']['weekly_ok'] = weekly_ok
        result['checks']['monthly_ok'] = monthly_ok
        if not (weekly_ok and monthly_ok):
            result['reason'] = f"MTF failed (Weekly: {weekly_ok}, Monthly: {monthly_ok})"
            logger.info(f"[{symbol}] ❌ MTF Confirmation: FAILED - Weekly close > EMA21: {weekly_ok}, Monthly close > EMA10: {monthly_ok}")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ MTF Confirmation: PASSED - Both weekly and monthly aligned")
        
        # CHECK 3: Pullback
        pullback_ok = self.check_pullback(df_daily)
        result['checks']['pullback'] = pullback_ok
        if not pullback_ok:
            result['reason'] = "No valid pullback to key moving averages"
            logger.info(f"[{symbol}] ❌ Pullback: FAILED - No recent pullback detected near EMA21/SMA50")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Pullback: PASSED - Valid pullback confirmed with downtrend")
        
        # CHECK 4: Pattern Recognition OR Touch-Based Signal (MANDATORY - either/or)
        pattern_found, pattern_name = PatternDetector.has_pattern(df_daily)
        touch_signal_found, touch_signal_type = self.check_touch_based_signal(df_daily)
        
        # Accept either pattern signal OR touch-based signal
        signal_type = None
        if pattern_found:
            signal_type = f"Pattern_{pattern_name}"
        elif touch_signal_found:
            signal_type = f"Touch_{touch_signal_type}"
        
        result['pattern'] = pattern_name if pattern_found else touch_signal_type
        result['checks']['pattern'] = pattern_found
        result['checks']['touch_signal'] = touch_signal_found
        
        if not (pattern_found or touch_signal_found):
            result['reason'] = "No explosive bullish pattern OR qualifying touch-based signal detected"
            logger.info(f"[{symbol}] ❌ Signal Check: FAILED - No pattern (Engulfing/Piercing/Tweezer) OR touch signal detected")
            return False, result
        else:
            detected_parts = []
            if pattern_found:
                detected_parts.append(f"Pattern: {pattern_name}")
            if touch_signal_found:
                detected_parts.append(f"Touch: {touch_signal_type}")
            signal_description = " + ".join(detected_parts)
            logger.info(f"[{symbol}] ✅ Signal Check: PASSED - {signal_description} detected")
        
        # Set ALL applicable signal types - a signal can qualify for multiple types simultaneously
        # e.g. a stock with Engulfing pattern + EMA21 touch qualifies as BOTH 'swing' and '21Touch'
        signal_types = []
        if pattern_found:
            signal_types.append('swing')
        if touch_signal_found:
            if touch_signal_type == "EMA21_Touch":
                signal_types.append('21Touch')
            elif touch_signal_type == "SMA50_Touch":
                signal_types.append('50Touch')

        result['signal_types'] = signal_types
        result['pattern'] = '+'.join(signal_types) if signal_types else 'None'

        # CHECK 5: Stalling Filter (apply to BOTH swing and touch signals)
        # Use touch-specific stalling parameters for touch signals
        if touch_signal_found:
            stalling_days_long = self.config.get('strategy_params', 'touch_stalling_days_long', 3)
            stalling_days_short = self.config.get('strategy_params', 'touch_stalling_days_short', 1)
        else:
            stalling_days_long = self.config.get('strategy_params', 'stalling_days_long', 8)
            stalling_days_short = self.config.get('strategy_params', 'stalling_days_short', 3)
        
        is_stalling = self.check_stalling(df_daily, stalling_days_long, stalling_days_short)
        result['checks']['stalling'] = is_stalling
        if is_stalling:
            result['reason'] = "Stock is stalling (sideways consolidation)"
            logger.info(f"[{symbol}] ❌ Stalling Filter: FAILED - Detected sideways consolidation")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Stalling Filter: PASSED - No consolidation detected")
        
        # Get current price
        current_price = self.data_fetcher.get_current_price(symbol)
        result['price'] = current_price
        
        # CHECK 6: Extended Stock Filter (gap up >4%)
        if self.config.get('strategy_params', 'enable_extended_filter'):
            is_extended, gap_pct = self.check_extended_stock(df_daily, current_price)
            result['checks']['extended_stock'] = is_extended
            result['gap_pct'] = gap_pct * 100
            
            if is_extended:
                result['reason'] = f"Stock is EXTENDED - Gap up {gap_pct*100:.2f}% (max allowed: {self.config.get('strategy_params', 'max_gap_pct')*100:.1f}%)"
                logger.warning(f"[{symbol}] {result['reason']}")
                return False, result
        else:
            logger.info(f"[{symbol}] Extended Filter: DISABLED")
        
        # CHECK 6.5: GREEN CANDLE FILTER (MANDATORY)
        # Stock must be green today (current price > yesterday's close)
        current_price = self.data_fetcher.get_current_price(symbol)
        prev_close = df_daily.iloc[-2]['close']
        is_green_today = current_price > prev_close
        
        result['checks']['green_candle'] = is_green_today
        result['current_price'] = current_price
        result['prev_close'] = prev_close
        
        if not is_green_today:
            result['reason'] = f'Stock is RED today (${current_price:.2f} <= ${prev_close:.2f}) - only green stocks allowed'
            logger.info(f'[{symbol}]  GREEN CANDLE FILTER: FAILED - Current: ${current_price:.2f}, Previous Close: ${prev_close:.2f}')
            return False, result
        else:
            logger.info(f'[{symbol}]  GREEN CANDLE FILTER: PASSED - Green today (${current_price:.2f} > ${prev_close:.2f})')

        # Calculate Score
        score = self.calculate_score(df_daily, symbol, weekly_ok, monthly_ok, pattern_found, touch_signal_found)
        result['score'] = score
        
        # CHECK 7: Minimum Score Requirement
        min_score = self.config.get('strategy_params', 'min_signal_score')
        if score < min_score:
            result['reason'] = f"Score too low: {score}/5 (minimum required: {min_score})"
            logger.info(f"[{symbol}] ❌ Score Check: FAILED - Score {score:.1f} < {min_score} minimum")
            return False, result
        else:
            logger.info(f"[{symbol}] ✅ Score Check: PASSED - Score {score:.1f}/5 meets minimum {min_score}")
        
        # Get current price
        current_price = self.data_fetcher.get_current_price(symbol)
        result['price'] = current_price
        
        # ALL CHECKS PASSED
        result['signal'] = True
        signal_description = " + ".join(
            ([f"Pattern:{pattern_name}"] if pattern_found else []) +
            ([f"Touch:{touch_signal_type}"] if touch_signal_found else [])
        )
        result['reason'] = f"VALID BUY SIGNAL - Types:{'+'.join(result['signal_types'])} Score:{score}/5, {signal_description}"
        
        logger.info(f"[{symbol}] 🎯 VALID BUY SIGNAL DETECTED! Types: {result['signal_types']}", extra={'symbol': symbol, 'score': score, 'pattern': result['pattern']})
        logger.info(f"[{symbol}]   Score: {score:.1f}/5 | {signal_description} | Price: ${current_price:.2f}", extra={'symbol': symbol})
        logger.info(f"[{symbol}]   Touch Bonuses: EMA21 count={self.touch_ema21_count}, SMA50 count={self.touch_sma50_count}", extra={'symbol': symbol})
        return True, result

# ================================================================================
# SIGNAL QUEUE (Smart Execution)
# ================================================================================

# ================================================================================
# POSITION MANAGER (Execution & Risk Management)
# ================================================================================

class PositionManager:
    """
    Manages position sizing, entry execution, partial exits, and stop loss
    """
    
    def __init__(self, trading_client: TradingClient, config: ConfigManager, 
                 db: PositionDatabase, data_fetcher: MarketDataFetcher):
        self.trading_client = trading_client
        self.config = config
        self.db = db
        self.data_fetcher = data_fetcher
    
    def calculate_position_size(self, symbol: str, current_price: float) -> Tuple[int, float]:
        """
        Simple position sizing: 3% per trade, max 6% per stock, configurable, with cash check.
        """
        # Get account equity
        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
        except Exception as e:
            logger.error(f"Failed to get account equity: {e}")
            return 0, 0.0

        # Configurable: 3% per trade, 6% max per stock
        trade_pct = self.config.get('trading_rules', 'per_trade_pct', 0.03)  # Each trade: configurable % of equity
        max_allocation_per_stock_pct = self.config.get('trading_rules', 'max_allocation_per_stock_pct', 0.06)  # Max 6% per stock (configurable)

        # Calculate current allocation for this stock
        open_positions = self.db.get_open_positions(symbol=symbol)
        current_allocation = sum(pos['entry_price'] * pos['remaining_qty'] for pos in open_positions)
        current_allocation_pct = current_allocation / equity if equity > 0 else 0

        # Remaining allocation for this stock
        remaining_pct = max(0, max_allocation_per_stock_pct - current_allocation_pct)

        # Limit trade size to min(configured %, remaining for stock)
        effective_trade_pct = min(trade_pct, remaining_pct)

        if effective_trade_pct <= 0:
            logger.warning(f"[{symbol}] Per-stock allocation limit reached ({current_allocation_pct*100:.1f}% / {max_allocation_per_stock_pct*100:.1f}%), cannot add more")
            return 0, 0.0

        trade_amount = equity * effective_trade_pct

        # Check overall utilization limit
        total_current_allocation = sum(pos['entry_price'] * pos['remaining_qty'] for pos in self.db.get_open_positions())
        projected_utilization_pct = (total_current_allocation + trade_amount) / equity
        max_utilization_pct = self.config.get('trading_rules', 'max_equity_utilization_pct', 0.90)

        if projected_utilization_pct > max_utilization_pct:
            logger.warning(f"[{symbol}] Overall utilization limit reached ({projected_utilization_pct*100:.1f}% / {max_utilization_pct*100:.1f}%), reducing trade size")
            available_pct = max_utilization_pct - (total_current_allocation / equity)
            trade_amount = equity * min(effective_trade_pct, available_pct)
            if trade_amount <= 0:
                return 0, 0.0

        # Calculate shares
        shares = int(trade_amount / current_price)
        actual_amount = shares * current_price

        if shares <= 0:
            logger.warning(f"[{symbol}] Trade size too small after limits")
            return 0, 0.0

        logger.info(f"[{symbol}] Simple sizing: {shares} shares @ ${current_price:.2f} = ${actual_amount:.2f} ({effective_trade_pct*100:.1f}% of equity, stock total: {(current_allocation_pct + (actual_amount / equity))*100:.1f}%)")
        return shares, actual_amount
    
    def execute_buy(self, symbol: str, signal_details: Dict) -> bool:
        """
        Execute buy order and record in database
        """
        current_price = signal_details['price']
        score = signal_details['score']
        
        # Calculate position size
        shares, trade_amount = self.calculate_position_size(symbol, current_price)
        
        if shares <= 0:
            logger.warning(f"[{symbol}] Position size too small (0 shares), skipping")
            return False
        
        # Calculate initial stop loss
        initial_sl_pct = self.config.get('risk_management', 'initial_stop_loss_pct')
        stop_loss = current_price * (1 - initial_sl_pct)
        
        logger.info(f"[{symbol}] Executing BUY: {shares} shares @ ${current_price:.2f} (Total: ${trade_amount:.2f})")
        logger.info(f"[{symbol}] Initial Stop Loss: ${stop_loss:.2f} ({initial_sl_pct*100:.1f}% below entry)")
        
        try:
            # Submit market order
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            order = self.trading_client.submit_order(order_request)
            
            logger.info(f"[{symbol}] Order submitted successfully (ID: {order.id})", extra={'symbol': symbol, 'order_id': order.id})
            
            # Extract pattern/signal type from signal details
            pattern_type = signal_details.get('pattern', 'Unknown')
            
            # Record in database
            position_id = self.db.add_position(
                symbol=symbol,
                entry_price=current_price,
                quantity=shares,
                stop_loss=stop_loss,
                score=score,
                pattern=pattern_type
            )
            
            logger.info(f"[{symbol}] Position recorded in database (Position ID: {position_id}, Pattern: {pattern_type})", extra={'symbol': symbol, 'order_id': order.id, 'position_id': position_id})
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] Order execution failed: {e}")
            return False
    
    def update_trailing_stop_loss(self, position: Dict, current_price: float):
        """
        Update dynamic trailing stop loss (3-tier system)
        """
        entry_price = position['entry_price']
        current_sl = position['stop_loss']
        position_id = position['id']
        
        # Calculate profit percentage
        profit_pct = (current_price - entry_price) / entry_price
        
        # Determine what SL should be based on profit tier
        tier1_profit = self.config.get('risk_management', 'tier_1_profit_pct')
        tier2_profit = self.config.get('risk_management', 'tier_2_profit_pct')
        tier1_sl = self.config.get('risk_management', 'tier_1_stop_loss_pct')
        tier2_sl = self.config.get('risk_management', 'tier_2_stop_loss_pct')
        initial_sl = self.config.get('risk_management', 'initial_stop_loss_pct')
        
        if profit_pct >= tier2_profit:  # >= 10% profit
            new_sl_pct = tier2_sl  # 1% below entry (near breakeven)
        elif profit_pct >= tier1_profit:  # >= 5% profit
            new_sl_pct = tier1_sl  # 9% below entry
        else:
            new_sl_pct = initial_sl  # 17% below entry
        
        new_sl = entry_price * (1 - new_sl_pct)
        
        # Only update if new SL is higher (trailing up)
        if new_sl > current_sl:
            self.db.update_stop_loss(position_id, new_sl)
            logger.info(f"[{position['symbol']}] Trailing SL updated: ${current_sl:.2f} → ${new_sl:.2f} (Profit: {profit_pct*100:.2f}%)")
    
    def check_partial_exit_targets(self, position: Dict, current_price: float) -> List[Tuple[str, int, float]]:
        """
        Check if partial profit targets are hit
        Returns: [(target_name, quantity_to_sell, target_price)]
        """
        if not self.config.get('profit_taking', 'enable_partial_exits'):
            return []
        
        entry_price = position['entry_price']
        remaining_qty = position['remaining_qty']
        
        exits_to_execute = []
        
        # Get profit targets from config
        targets = [
            ('PT1', self.config.get('profit_taking', 'target_1_pct'), 
             self.config.get('profit_taking', 'target_1_qty')),
            ('PT2', self.config.get('profit_taking', 'target_2_pct'), 
             self.config.get('profit_taking', 'target_2_qty')),
            ('PT3', self.config.get('profit_taking', 'target_3_pct'), 
             self.config.get('profit_taking', 'target_3_qty'))
        ]
        
        # Check each target
        for target_name, target_pct, target_qty_pct in targets:
            target_price = entry_price * (1 + target_pct)
            
            if current_price >= target_price:
                # Check if we've already taken this target
                cursor = self.db.conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM partial_exits 
                    WHERE position_id = ? AND profit_target = ?
                ''', (position['id'], target_name))
                already_taken = cursor.fetchone()[0] > 0
                
                if not already_taken and remaining_qty > 0:
                    qty_to_sell = int(remaining_qty * target_qty_pct)
                    if qty_to_sell > 0:
                        exits_to_execute.append((target_name, qty_to_sell, target_price))
        
        return exits_to_execute
    
    def execute_partial_exit(self, position: Dict, target_name: str, 
                            quantity: int, current_price: float):
        """Execute partial exit order"""
        symbol = position['symbol']
        
        # CRITICAL SAFEGUARD: Check if we have enough shares to sell
        if quantity > position['remaining_qty']:
            logger.error(f"[{symbol}] Cannot execute partial exit - trying to sell {quantity} shares but only {position['remaining_qty']} remaining")
            return
        
        if quantity <= 0:
            logger.warning(f"[{symbol}] Cannot execute partial exit - invalid quantity {quantity}")
            return
        
        logger.info(f"[{symbol}] Executing Partial Exit {target_name}: {quantity} shares @ ${current_price:.2f}")
        
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = self.trading_client.submit_order(order_request)
            
            # Record partial exit
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            self.db.add_partial_exit(
                position_id=position['id'],
                quantity=quantity,
                exit_price=current_price,
                profit_target=target_name,
                profit_pct=profit_pct
            )
            
            logger.info(f"[{symbol}] {target_name} executed successfully (+{profit_pct:.2f}%)")
            
        except Exception as e:
            logger.error(f"[{symbol}] Partial exit failed: {e}")
    
    def execute_full_exit(self, position: Dict, current_price: float, reason: str):
        """Execute full position exit (FIFO)"""
        symbol = position['symbol']
        remaining_qty = position['remaining_qty']
        
        # CRITICAL SAFEGUARD: Check if position still has shares to sell
        if remaining_qty <= 0:
            logger.warning(f"[{symbol}] Cannot execute full exit - position already fully exited (remaining_qty={remaining_qty})")
            return
        
        logger.info(f"[{symbol}] Executing FULL EXIT: {remaining_qty} shares @ ${current_price:.2f} (Reason: {reason})")
        
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=remaining_qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = self.trading_client.submit_order(order_request)
            
            # Close position in database
            self.db.close_position(
                position_id=position['id'],
                exit_price=current_price,
                exit_reason=reason
            )
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            logger.info(f"[{symbol}] Position CLOSED (P/L: {profit_pct:+.2f}%)", extra={'symbol': symbol, 'pnl': profit_pct, 'exit_reason': reason})
            
        except Exception as e:
            logger.error(f"[{symbol}] Full exit failed: {e}")
    
    def check_stop_loss(self, position: Dict, current_price: float) -> bool:
        """
        Check if stop loss triggered
        Uses CLOSING PRICE (configurable)
        """
        stop_loss = position['stop_loss']
        stop_loss_mode = self.config.get('risk_management', 'stop_loss_mode')
        
        if stop_loss_mode == 'closing_basis':
            # Trigger only on current price (closing basis)
            return current_price <= stop_loss
        elif stop_loss_mode == 'intraday_basis':
            # Would need intraday low data (not implemented in current version)
            # For simplicity, using current price
            return current_price <= stop_loss
        else:
            return current_price <= stop_loss
    
    def check_time_exit(self, position: Dict) -> bool:
        """Check if Time Exit Signal (TES) triggered"""
        max_hold_days = self.config.get('risk_management', 'max_hold_days')
        days_held = self.db.get_days_held(position['id'])
        return days_held >= max_hold_days

# ================================================================================
# SIGNAL QUEUE (Smart Execution with Waiting Period)
# ================================================================================

class SignalQueue:
    """
    Manages detected signals during monitoring period with re-validation
    Collects signals, waits 15 minutes, re-validates, executes top N
    """

    def __init__(self, monitoring_minutes: int = 1, top_n: int = 5):
        self.signals = {}  # {symbol: {signal_details, first_seen, last_validated, revalidation_count}}
        self.monitoring_minutes = monitoring_minutes
        self.top_n = top_n
        self.window_start_time = None

    def add_signal(self, symbol: str, signal_details: Dict):
        """Add or update signal in queue with timestamp tracking"""
        now = datetime.now()

        if self.window_start_time is None:
            self.window_start_time = now

        if symbol not in self.signals:
            self.signals[symbol] = {
                'details': signal_details,
                'first_seen': now,
                'last_validated': now,
                'revalidation_count': 1
            }
            logger.info(f"[{symbol}] Added to signal queue (Score: {signal_details['score']:.1f})")
        else:
            # Update existing signal with fresh details
            self.signals[symbol]['last_validated'] = now
            self.signals[symbol]['revalidation_count'] += 1
            self.signals[symbol]['details'] = signal_details  # Update with latest
            logger.info(f"[{symbol}] Signal updated in queue ({self.signals[symbol]['revalidation_count']} validations)")

    def is_window_complete(self) -> bool:
        """Check if 15-minute monitoring window is complete"""
        if self.window_start_time is None:
            return False

        elapsed = (datetime.now() - self.window_start_time).total_seconds() / 60
        return elapsed >= self.monitoring_minutes

    def get_top_signals(self, analyzer) -> List[Tuple[str, Dict]]:
        """
        Re-validate all signals and return top N that are still valid
        Returns: [(symbol, signal_details), ...] sorted by score descending with tie-breaking
        """
        validated_signals = []

        for symbol, signal_data in self.signals.items():
            # CRITICAL: Re-validate signal before execution
            signal_valid, signal_details = analyzer.analyze_entry_signal(symbol)

            if signal_valid:
                # Signal still valid after monitoring period
                signal_details['persistence_score'] = signal_data['revalidation_count']
                validated_signals.append((symbol, signal_details))
                logger.info(f"[{symbol}] ✅ Signal STILL VALID after {self.monitoring_minutes}min monitoring (Score: {signal_details['score']:.1f}, Validations: {signal_data['revalidation_count']})")
            else:
                logger.warning(f"[{symbol}] ❌ Signal EXPIRED during monitoring - {signal_details['reason']}")

        # Sort by score descending with tie-breaking preferences
        validated_signals = self._sort_with_tie_breaking(validated_signals, analyzer)

        # Return top N
        return validated_signals[:self.top_n]

    def _sort_with_tie_breaking(self, signals: List[Tuple[str, Dict]], analyzer) -> List[Tuple[str, Dict]]:
        """
        Sort signals by score descending, with tie-breaking preferences when scores are equal

        Tie-breaking preferences (in order of priority):
        1. Stock is green today (price > yesterday's close)
        2. First 21EMA touch with bullish patterns (engulfing, tweezer, piercing)
        3. Explosive current candle (>40% body)
        4. First 50SMA touch with pattern building
        5. Touch signals with patterns in demand zone
        """
        def get_tie_breaking_priority(signal_tuple):
            symbol, signal_details = signal_tuple
            priority_score = 0

            try:
                # Get current market data for tie-breaking evaluation
                df_daily = analyzer.data_fetcher.get_daily_bars(symbol, days=30)
                if df_daily is None or len(df_daily) < 2:
                    return (signal_details['score'], priority_score)

                current_price = analyzer.data_fetcher.get_current_price(symbol)
                if current_price is None:
                    return (signal_details['score'], priority_score)

                # Preference 1: Stock is green today (price > yesterday's close)
                prev_close = df_daily.iloc[-2]['close']
                if current_price > prev_close:
                    priority_score += 1000  # Highest priority
                    logger.debug(f"[{symbol}] Tie-breaker +1000: Green today (${current_price:.2f} > ${prev_close:.2f})")

                # Get current candle data
                current_candle = df_daily.iloc[-1]

                # Preference 2: First 21EMA touch with specific patterns
                ema21_touch = analyzer.touch_ema21_count > 0
                signal_types = signal_details.get('signal_types', [signal_details.get('pattern', '')])
                has_required_pattern = 'swing' in signal_types  # swing signals are pattern-based (Engulfing, Piercing, Tweezer)

                if ema21_touch and has_required_pattern:
                    # Check if current candle is explosive (>40% body)
                    body_size = abs(current_candle['close'] - current_candle['open'])
                    total_range = current_candle['high'] - current_candle['low']
                    if total_range > 0 and (body_size / total_range) > 0.40:
                        priority_score += 800  # Second highest
                        logger.debug(f"[{symbol}] Tie-breaker +800: 21EMA touch + explosive pattern ({pattern_type})")

                # Preference 3: Explosive current candle (>40% body)
                elif total_range > 0 and (body_size / total_range) > 0.40:
                    priority_score += 600  # Third priority
                    logger.debug(f"[{symbol}] Tie-breaker +600: Explosive current candle ({body_size/total_range:.1%})")

                # Preference 4: First 50SMA touch with pattern building
                sma50_touch = analyzer.touch_sma50_count > 0
                if sma50_touch and has_required_pattern:
                    priority_score += 400  # Fourth priority
                    logger.debug(f"[{symbol}] Tie-breaker +400: 50SMA touch + pattern ({pattern_type})")

                # Preference 5: Touch signals with patterns in demand zone
                # Check if current price is in demand zone (within 3.5% of 21-day low)
                low_21 = df_daily['low'].iloc[-21:].min()
                dz_threshold = low_21 * 1.035
                in_demand_zone = current_price <= dz_threshold

                touch_signal = 'Touch' in str(signal_details.get('pattern', ''))
                if touch_signal and in_demand_zone:
                    priority_score += 200  # Fifth priority
                    logger.debug(f"[{symbol}] Tie-breaker +200: Touch signal + pattern + demand zone")

            except Exception as e:
                logger.warning(f"[{symbol}] Error calculating tie-breaking priority: {e}")

            return (signal_details['score'], priority_score)

        # Sort by score descending, then by tie-breaking priority descending
        signals.sort(key=get_tie_breaking_priority, reverse=True)

        # Log the final ranking
        logger.info("Signal ranking with tie-breaking applied:")
        for i, (symbol, signal_details) in enumerate(signals[:self.top_n], 1):
            score = signal_details['score']
            logger.info(f"  #{i}: {symbol} (Score: {score})")

        return signals

    def reset(self):
        """Clear queue after execution"""
        self.signals = {}
        self.window_start_time = None

    def get_queue_status(self) -> Dict:
        """Get current queue status for logging"""
        return {
            'signals_queued': len(self.signals),
            'window_start': self.window_start_time.isoformat() if self.window_start_time else None,
            'minutes_elapsed': (datetime.now() - self.window_start_time).total_seconds() / 60 if self.window_start_time else 0,
            'window_complete': self.is_window_complete()
        }

# ================================================================================
# TRADING BOT ORCHESTRATOR
# ================================================================================

class RajatAlphaTradingBot:
    """
    Main trading bot orchestrator
    """
    
    def __init__(self, config_path='config/config.json'):
        # Load configuration
        self.config = ConfigManager(config_path)
        
        # Initialize database
        self.db = PositionDatabase()
        
        # Initialize Alpaca clients
        api_key = self.config.get('api', 'key_id')
        secret_key = self.config.get('api', 'secret_key')
        base_url = self.config.get('api', 'base_url')
        self.is_paper = 'paper' in base_url
        
        self.trading_client = TradingClient(api_key, secret_key, paper=self.is_paper)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
        
        # Initialize components
        self.data_fetcher = MarketDataFetcher(self.data_client)
        self.analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        self.position_manager = PositionManager(
            self.trading_client, self.config, self.db, self.data_fetcher
        )
        
        # Signal queue for 1-minute waiting period with re-validation
        self.signal_queue = SignalQueue(
            monitoring_minutes=self.config.get('execution_schedule', 'signal_monitoring_minutes'),  # 1-minute waiting period
            top_n=self.config.get('execution_schedule', 'top_n_trades')  # Execute top N valid signals
        )
        self.last_execution_time = None  # Track when we last executed signals
        
        logger.info("=" * 80)
        logger.info("RAJAT ALPHA V67 TRADING BOT INITIALIZED")
        logger.info(f"Mode: {'PAPER TRADING' if self.is_paper else 'LIVE TRADING'}")
        logger.info("=" * 80)
    
    def get_watchlist(self) -> List[str]:
        """Load watchlist from file and apply exclusions"""
        watchlist_file = self.config.get('trading_rules', 'watchlist_file')
        try:
            with open(watchlist_file, 'r') as f:
                symbols = [line.strip().upper() for line in f if line.strip()]
            logger.info(f"Watchlist loaded: {len(symbols)} symbols")
            
            # Apply exclusion list
            exclusion_file = self.config.get('trading_rules', 'exclusion_file')
            if exclusion_file:
                try:
                    with open(exclusion_file, 'r') as f:
                        exclusions = set(line.strip().upper() for line in f if line.strip())
                    
                    if exclusions:
                        original_count = len(symbols)
                        symbols = [s for s in symbols if s not in exclusions]
                        excluded_count = original_count - len(symbols)
                        
                        if excluded_count > 0:
                            if self.config.get('trading_rules', 'log_excluded_symbols'):
                                excluded_symbols = [s for s in symbols if s in exclusions]
                                logger.info(f"Excluded {excluded_count} symbols: {', '.join(list(exclusions)[:10])}{'...' if len(exclusions) > 10 else ''}")
                            else:
                                logger.info(f"Excluded {excluded_count} symbols from watchlist")
                except FileNotFoundError:
                    logger.warning(f"Exclusion file {exclusion_file} not found, proceeding without exclusions")
                except Exception as e:
                    logger.error(f"Error loading exclusion file: {e}")
            
            logger.info(f"Active watchlist: {len(symbols)} symbols")
            return symbols
        except FileNotFoundError:
            logger.error(f"Watchlist file {watchlist_file} not found!")
            return []
    
    def get_sell_watchlist(self) -> Optional[List[str]]:
        """Load sell watchlist from file - if empty/missing, monitor all positions"""
        sell_watchlist_file = self.config.get('trading_rules', 'sell_watchlist_file')
        
        if not sell_watchlist_file:
            logger.debug("No sell watchlist configured, monitoring all positions")
            return None
            
        try:
            with open(sell_watchlist_file, 'r') as f:
                symbols = [line.strip().upper() for line in f if line.strip() and not line.strip().startswith('#')]
            
            if not symbols:
                logger.debug("Sell watchlist empty, monitoring all positions")
                return None
                
            logger.debug(f"Sell watchlist loaded: {len(symbols)} symbols - {', '.join(symbols)}")
            return symbols
            
        except FileNotFoundError:
            logger.debug(f"Sell watchlist file {sell_watchlist_file} not found, monitoring all positions")
            return None
        except Exception as e:
            logger.warning(f"Error loading sell watchlist: {e}, monitoring all positions")
            return None
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        # Weekend check
        if now.weekday() > 4:
            return False
        
        # Market hours: 9:30 AM - 4:00 PM EST
        market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_start <= now <= market_end
    
    def is_buy_window(self) -> bool:
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        # Use direct start/end times from config (hour-based)
        buy_window_start = self.config.get('execution_schedule', 'buy_window_start_time')
        buy_window_end = self.config.get('execution_schedule', 'buy_window_end_time')
        
        start_h, start_m = map(int, buy_window_start.split(':'))
        end_h, end_m = map(int, buy_window_end.split(':'))
        
        start_time = now.replace(hour=start_h, minute=start_m, second=0)
        end_time = now.replace(hour=end_h, minute=end_m, second=0)
        
        in_window = start_time <= now <= end_time
        
        if in_window:
            logger.debug(f"In buy window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        
        return in_window
    
    def get_scan_interval(self) -> int:
        """Get scan interval based on time of day"""
        if self.is_buy_window():
            # Last hour: scan every 1 minute
            return self.config.get('execution_schedule', 'last_hour_interval_seconds')
        else:
            # Rest of day: scan every 2 minutes
            return self.config.get('execution_schedule', 'default_interval_seconds')
    
    def run_sell_guardian(self):
        """
        SELL GUARDIAN: Monitors positions for exit conditions
        Can be filtered by sell_watchlist_file - if provided, only monitors those symbols
        """
        logger.info("--- SELL GUARDIAN: Monitoring Positions ---")
        
        open_positions = self.db.get_open_positions()
        
        if not open_positions:
            logger.info("No open positions to monitor")
            return
        
        # Get sell watchlist filter (optional)
        sell_watchlist = self.get_sell_watchlist()
        
        # Filter positions if sell watchlist is provided
        if sell_watchlist is not None:
            filtered_positions = [p for p in open_positions if p['symbol'] in sell_watchlist]
            skipped_count = len(open_positions) - len(filtered_positions)
            
            if skipped_count > 0:
                skipped_symbols = [p['symbol'] for p in open_positions if p['symbol'] not in sell_watchlist]
                logger.info(f"Sell filtering: Monitoring {len(filtered_positions)} positions, skipping {skipped_count} positions ({', '.join(skipped_symbols[:3])}{'...' if len(skipped_symbols) > 3 else ''})")
            
            positions_to_monitor = filtered_positions
        else:
            positions_to_monitor = open_positions
            logger.debug(f"Monitoring all {len(positions_to_monitor)} positions (no sell filter)")
        
        if not positions_to_monitor:
            logger.info("No positions match sell watchlist criteria")
            return
        
        for position in positions_to_monitor:
            symbol = position['symbol']
            
            # Get current price
            current_price = self.data_fetcher.get_current_price(symbol)
            if current_price is None:
                logger.warning(f"[{symbol}] Could not fetch current price, skipping")
                continue
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            logger.info(f"[{symbol}] Position ID {position['id']} | P/L: {profit_pct:+.2f}% | Remaining: {position['remaining_qty']} shares")
            
            # 1. Check Stop Loss (Priority 1 - most important)
            if self.position_manager.check_stop_loss(position, current_price):
                logger.warning(f"[{symbol}] STOP LOSS TRIGGERED at ${current_price:.2f}")
                self.position_manager.execute_full_exit(position, current_price, "Stop Loss")
                continue
            
            # 2. Check Time Exit Signal (TES)
            if self.position_manager.check_time_exit(position):
                logger.warning(f"[{symbol}] TIME EXIT SIGNAL (TES) triggered")
                self.position_manager.execute_full_exit(position, current_price, "TES")
                continue
            
            # 3. Update Trailing Stop Loss
            self.position_manager.update_trailing_stop_loss(position, current_price)
            
            # 4. Check Partial Profit Targets
            partial_exits = self.position_manager.check_partial_exit_targets(position, current_price)
            if partial_exits:
                for target_name, quantity, target_price in partial_exits:
                    self.position_manager.execute_partial_exit(
                        position, target_name, quantity, current_price
                    )
                
                # CRITICAL FIX: Reload position after partial exits to get updated remaining_qty
                # This prevents overselling if stop loss or other exits trigger in next iteration
                refreshed_position = self.db.get_position_by_id(position['id'])
                if refreshed_position and refreshed_position['remaining_qty'] == 0:
                    logger.info(f"[{symbol}] Position fully exited via partial exits")
                    continue
    
    def run_buy_hunter(self):
        """
        BUY HUNTER: Collects signals during 15-minute window, then re-validates and executes top N
        """
        if not self.is_buy_window():
            logger.info("BUY HUNTER: Outside buy window, skipping scan")
            return

        logger.info("--- BUY HUNTER: Signal Collection Phase ---")

        # Check if we should execute queued signals
        if self.signal_queue.is_window_complete():
            logger.info("🎯 MONITORING WINDOW COMPLETE - Executing Re-validated Signals")
            self._execute_queued_signals()
            return

        # COLLECTION PHASE: Scan watchlist and collect signals
        queue_status = self.signal_queue.get_queue_status()
        logger.info(f"Signal Queue Status: {queue_status['signals_queued']} signals, {queue_status['minutes_elapsed']:.1f}min elapsed")

        # Check daily trade limit
        max_trades_per_day = self.config.get('trading_rules', 'max_trades_per_day')
        trades_today = self.db.count_trades_today()

        if trades_today >= max_trades_per_day:
            logger.info(f"Daily trade limit reached ({trades_today}/{max_trades_per_day}), no new signal collection")
            return

        # Get watchlist
        portfolio_mode = self.config.get('trading_rules', 'portfolio_mode')

        if portfolio_mode == 'watchlist_only':
            watchlist = self.get_watchlist()
        elif portfolio_mode == 'specific_stocks':
            watchlist = self.config.get('trading_rules', 'specific_stocks')
        else:
            watchlist = self.get_watchlist()

        # Collect signals (don't execute yet)
        new_signals_found = 0

        for symbol in watchlist:
            try:
                signal_valid, signal_details = self.analyzer.analyze_entry_signal(symbol)

                # Log signal to history (whether executed or not)
                self.db.log_signal(symbol, signal_details, False)

                if signal_valid:
                    # Check if at least one of the signal's applicable types is enabled
                    # A signal can qualify for multiple types (e.g. swing+21Touch)
                    # It executes if ANY of its types is enabled
                    signal_types = signal_details.get('signal_types', [signal_details.get('pattern', '')])
                    enable_21touch = self.config.get('trading_rules', 'enable_21touch_signals', True)
                    enable_50touch = self.config.get('trading_rules', 'enable_50touch_signals', True)
                    enable_swing = self.config.get('trading_rules', 'enable_swing_signals', True)
                    enabled_map = {'swing': enable_swing, '21Touch': enable_21touch, '50Touch': enable_50touch}
                    if not any(enabled_map.get(st, False) for st in signal_types):
                        logger.info(f"[{symbol}] Signal filtered out - none of its signal types {signal_types} are enabled")
                        continue
                    
                    # Add to queue instead of executing immediately
                    self.signal_queue.add_signal(symbol, signal_details)
                    new_signals_found += 1
                    logger.info(f"[{symbol}] 📊 SIGNAL COLLECTED (Score: {signal_details['score']:.1f}) - Will re-validate in {self.signal_queue.monitoring_minutes} minutes")

            except Exception as e:
                logger.error(f"[{symbol}] Analysis error: {e}")
                continue

        if new_signals_found > 0:
            logger.info(f"✅ Collected {new_signals_found} new signals. Total in queue: {len(self.signal_queue.signals)}")
            logger.info(f"⏰ Waiting {self.signal_queue.monitoring_minutes} minutes for re-validation before execution...")
        else:
            logger.info("📊 No new signals found in this scan")
    
    def _execute_queued_signals(self):
        """
        PRIVATE METHOD: Execute top N re-validated signals from queue
        Called when 15-minute monitoring window completes
        """
        logger.info("--- SIGNAL EXECUTION: Re-validation & Execution Phase ---")

        # Get top N re-validated signals
        signals_to_execute = self.signal_queue.get_top_signals(self.analyzer)

        if not signals_to_execute:
            logger.info("❌ No signals survived re-validation - queue cleared")
            self.signal_queue.reset()
            return

        logger.info(f"🎯 Executing {len(signals_to_execute)} re-validated signals (top by score)")

        # Check current position limits
        open_positions = self.db.get_open_positions()
        max_positions = self.config.get('trading_rules', 'max_open_positions')
        available_slots = max_positions - len(open_positions)

        # Check daily limits
        max_trades_per_day = self.config.get('trading_rules', 'max_trades_per_day')
        trades_today = self.db.count_trades_today()
        available_daily_slots = max_trades_per_day - trades_today

        # Final execution limit
        final_slots = min(available_slots, available_daily_slots, len(signals_to_execute))

        if final_slots <= 0:
            logger.warning(f"No execution slots available (Positions: {len(open_positions)}/{max_positions}, Daily: {trades_today}/{max_trades_per_day})")
            self.signal_queue.reset()
            return

        executed_count = 0

        for symbol, signal_details in signals_to_execute[:final_slots]:
            score = signal_details['score']

            # SAME-DAY PROTECTION CHECK
            enable_same_day_protection = self.config.get('trading_rules', 'prevent_same_day_reentry')
            if enable_same_day_protection and self.db.was_traded_today(symbol):
                logger.info(f"[{symbol}] ⚠️ SAME-DAY PROTECTION: Already traded {symbol} today, skipping")
                continue

            # Check daily limit before executing
            if self.db.count_trades_today() >= max_trades_per_day:
                logger.info(f"Daily trade limit reached ({max_trades_per_day}), stopping execution")
                break

            # Check per-stock limit
            symbol_positions = self.db.get_open_positions(symbol=symbol)
            max_trades_per_stock = self.config.get('trading_rules', 'max_trades_per_stock')

            if len(symbol_positions) >= max_trades_per_stock:
                logger.info(f"[{symbol}] Max trades per stock reached ({len(symbol_positions)}/{max_trades_per_stock}), skipping")
                continue

            # Execute the trade
            success = self.position_manager.execute_buy(symbol, signal_details)

            if success:
                # Log executed signal
                self.db.log_signal(symbol, signal_details, True)
                executed_count += 1
                logger.info(f"[{symbol}] ✅ RE-VALIDATED SIGNAL EXECUTED (Rank: {signals_to_execute.index((symbol, signal_details)) + 1}, Score: {score:.1f})")

        logger.info(f"🎯 Execution complete: {executed_count}/{len(signals_to_execute)} signals executed")

        # Reset queue for next monitoring window
        self.signal_queue.reset()
        self.last_execution_time = datetime.now()
    
    def run(self):
        """Main execution loop with signal queue management"""
        logger.info("Starting main execution loop...")
        
        while True:
            try:
                if self.is_market_open():
                    # 1. Always run Sell Guardian (monitors exits)
                    self.run_sell_guardian()
                    
                    # 2. Run Buy Hunter (signal collection or execution)
                    self.run_buy_hunter()
                    
                    # 3. Dynamic sleep interval based on queue status
                    interval = self._get_dynamic_scan_interval()
                    logger.info(f"Next scan in {interval} seconds...\n")
                    time.sleep(interval)
                    
                else:
                    logger.info("Market closed. Sleeping for 5 minutes...")
                    time.sleep(300)
                    
            except KeyboardInterrupt:
                logger.info("Bot stopped by user (Ctrl+C)")
                break
            except Exception as e:
                logger.error(f"CRITICAL ERROR in main loop: {e}", exc_info=True)
                logger.info("Sleeping 60 seconds before retry...")
                time.sleep(60)
    
    def _get_dynamic_scan_interval(self):
        base_interval = self.get_scan_interval()
        if self.signal_queue.is_window_complete() and len(self.signal_queue.signals) > 0:
            logger.info("Queue ready for execution - scanning immediately")
            return 1
        return base_interval
# ================================================================================

if __name__ == "__main__":
    bot = RajatAlphaTradingBot(config_path='config/config.json')
    bot.run()
