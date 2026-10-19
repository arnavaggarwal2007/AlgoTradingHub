"""
================================================================================
RAJAT ALPHA V67 - ALPACA DUAL BUY ALGORITHMIC TRADING BOT
================================================================================

STRATEGY: Dual Buy Entry (B1 + B2) with Dynamic Trailing Stop Loss and Partial Exits
BASED ON: Rajat Alpha v67 Strategy (PineScript - Dual Buy Version)
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

2. DUAL POSITION SYSTEM:
   - **B1 (Primary Buy)**: Enters when NO B1 position active, any valid signal
   - **B2 (High-Score Buy)**: Enters when B1 active AND score >= score_b2_min (default 3)
   - **OPP (Opportunity)**: Visual signal when B1 active but score < B2 min (no entry)
   - Allows up to 2 positions simultaneously (1 B1 + 1 B2)
   - Independent stop loss and profit targets for each position
   - Separate TES (Time Exit Signal) days for B1 and B2

3. Exit Management:
   - Dynamic Trailing Stop Loss (3-tier): 17% → 9% @ +5% profit → 1% @ +10% profit
   - Partial Exits: 1/3 Rule (33.3% @ 10%, 33.3% @ 15%, 33.4% @ 20%)
   - Time Exit Signal (TES): Max hold days (separate for B1 and B2)
   - FIFO: First In First Out selling within each position type

4. Risk Management:
   - Position Sizing: Configurable per position type (B1 and B2)
   - Max Loss Per Trade: Configurable ($ or %)
   - Max Open Positions: 2 B1 + 2 B2 (configurable)
   - Stop Loss: Closing basis (configurable)

5. Execution Schedule:
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
from datetime import datetime, timedelta, timezone
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
# LOGGING SETUP (Enhanced with Compliance Features)
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
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
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
logger = logging.getLogger('rajat_alpha_v67_dual')
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
file_handler = logging.FileHandler('rajat_alpha_v67_dual.log')
json_formatter = ComplianceJSONFormatter(
    '%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(line)s %(message)s'
)
file_handler.setFormatter(json_formatter)
logger.addHandler(file_handler)

# Separate audit log for critical events
audit_handler = logging.FileHandler('audit_dual.log')
audit_handler.setLevel(logging.WARNING)  # Only warnings and above
audit_handler.setFormatter(json_formatter)
logger.addHandler(audit_handler)

# ================================================================================
# DATABASE SETUP (Position Tracking with B1/B2 Support)
# ================================================================================

class PositionDatabase:
    """
    SQLite database to track:
    - Entry prices, dates, quantities
    - Position type (B1 or B2)
    - Partial exit tracking
    - FIFO queue management per position type
    - TES (Time Exit Signal) monitoring
    """
    
    def __init__(self, db_path='db/positions_dual.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Positions table with position_type column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                position_type TEXT NOT NULL,
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
    
    def add_position(self, symbol: str, position_type: str, entry_price: float, 
                     quantity: int, stop_loss: float, score: float, pattern: str = 'Unknown') -> int:
        """Add new position to database with pattern tracking"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, position_type, entry_date, entry_price, 
                                   quantity, remaining_qty, stop_loss, score, pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, position_type, datetime.now().isoformat(), entry_price, 
              quantity, quantity, stop_loss, score, pattern))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_open_positions(self, symbol: Optional[str] = None, 
                          position_type: Optional[str] = None) -> List[Dict]:
        """Get all open positions (FIFO order), optionally filtered by symbol and/or type"""
        cursor = self.conn.cursor()
        
        query = 'SELECT * FROM positions WHERE status = ?'
        params = ['OPEN']
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        
        if position_type:
            query += ' AND position_type = ?'
            params.append(position_type)
        
        query += ' ORDER BY entry_date ASC'
        
        cursor.execute(query, params)
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def has_active_position(self, symbol: str, position_type: str) -> bool:
        """Check if there's an active position for this symbol and type"""
        positions = self.get_open_positions(symbol=symbol, position_type=position_type)
        return len(positions) > 0
    
    def count_active_positions_by_type(self, position_type: str) -> int:
        """Count total active positions of a specific type"""
        positions = self.get_open_positions(position_type=position_type)
        return len(positions)
    
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
    
    def was_traded_today(self, symbol: str, position_type: str = None) -> bool:
        """Check if stock was already traded today (any position type or specific type)"""
        today_date = datetime.now().date().isoformat()
        cursor = self.conn.cursor()
        
        if position_type:
            # Check specific position type
            cursor.execute('''
                SELECT COUNT(*) FROM positions 
                WHERE symbol = ? AND position_type = ? AND date(entry_date) = ?
            ''', (symbol, position_type, today_date))
        else:
            # Check any position type
            cursor.execute('''
                SELECT COUNT(*) FROM positions 
                WHERE symbol = ? AND date(entry_date) = ?
            ''', (symbol, today_date))
        
        count = cursor.fetchone()[0]
        return count > 0
    
    def count_trades_today(self) -> int:
        """
        Count total trades executed today (all position types: B1 + B2)
        
        Used by: Feature #1 - Max Trades Per Day Limit
        
        Returns:
            int: Total number of trades (B1 + B2) opened today
            
        Note:
            - Dual Buy: Counts both B1 and B2 positions
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
    
    def log_signal(self, symbol: str, signal_details: Dict, executed: bool):
        """
        Log signal to history for analysis and debugging
        
        Used by: Feature #4 - Signal History Tracking
        
        Args:
            symbol: Stock ticker symbol
            signal_details: Dict containing signal data (score, pattern, price, reason)
            executed: True if trade was executed (B1 or B2), False otherwise
            
        Database Table:
            signal_history (see create_tables() for schema)
            
        Dual Buy Note:
            - Does NOT track which position type (B1/B2) was used
            - To determine B1/B2, query positions table separately
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO signal_history (symbol, signal_date, score, pattern, price, reason, executed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, datetime.now().date().isoformat(), signal_details.get('score', 0),
              signal_details.get('pattern', 'None'), signal_details.get('price', 0),
              signal_details.get('reason', ''), executed))
        self.conn.commit()
    
    def get_performance_by_score(self, position_type: Optional[str] = None) -> List[Dict]:
        """
        Analyze performance grouped by entry score (optionally filtered by position type)
        
        Args:
            position_type: Filter by 'B1' or 'B2', or None for all positions
        
        Returns:
            List of dicts with: score, trades, win_rate, avg_pl, avg_win, avg_loss, max_pl, min_pl
        """
        cursor = self.conn.cursor()
        where_clause = "WHERE status = 'CLOSED'"
        params = []
        
        if position_type:
            where_clause += " AND position_type = ?"
            params.append(position_type)
        
        cursor.execute(f'''
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
            {where_clause}
            GROUP BY score
            ORDER BY score DESC
        ''', params)
        columns = ['score', 'trades', 'win_rate', 'avg_pl', 'avg_win', 'avg_loss', 'max_pl', 'min_pl']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_performance_by_pattern(self, position_type: Optional[str] = None) -> List[Dict]:
        """
        Analyze performance grouped by entry pattern (optionally filtered by position type)
        
        Args:
            position_type: Filter by 'B1' or 'B2', or None for all positions
        
        Returns:
            List of dicts with: pattern, trades, win_rate, avg_pl, avg_win, avg_loss
        """
        cursor = self.conn.cursor()
        where_clause = "WHERE status = 'CLOSED'"
        params = []
        
        if position_type:
            where_clause += " AND position_type = ?"
            params.append(position_type)
        
        cursor.execute(f'''
            SELECT 
                pattern,
                COUNT(*) as trades,
                ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
                ROUND(AVG(profit_loss_pct), 2) as avg_pl,
                ROUND(AVG(CASE WHEN profit_loss_pct > 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_win,
                ROUND(AVG(CASE WHEN profit_loss_pct < 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_loss
            FROM positions 
            {where_clause}
            GROUP BY pattern
            ORDER BY win_rate DESC
        ''', params)
        columns = ['pattern', 'trades', 'win_rate', 'avg_pl', 'avg_win', 'avg_loss']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_performance_by_score_and_pattern(self, position_type: Optional[str] = None) -> List[Dict]:
        """
        Cross-tabulation of score × pattern performance (optionally filtered by position type)
        
        Args:
            position_type: Filter by 'B1' or 'B2', or None for all positions
        
        Returns:
            List of dicts with: score, pattern, trades, win_rate, avg_pl
        """
        cursor = self.conn.cursor()
        where_clause = "WHERE status = 'CLOSED'"
        params = []
        
        if position_type:
            where_clause += " AND position_type = ?"
            params.append(position_type)
        
        cursor.execute(f'''
            SELECT 
                score,
                pattern,
                COUNT(*) as trades,
                ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
                ROUND(AVG(profit_loss_pct), 2) as avg_pl
            FROM positions 
            {where_clause}
            GROUP BY score, pattern
            ORDER BY score DESC, win_rate DESC
        ''', params)
        columns = ['score', 'pattern', 'trades', 'win_rate', 'avg_pl']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_performance_by_position_type(self) -> List[Dict]:
        """
        Compare B1 vs B2 performance
        
        Returns:
            List of dicts with: position_type, trades, win_rate, avg_pl, avg_win, avg_loss
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                position_type,
                COUNT(*) as trades,
                ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
                ROUND(AVG(profit_loss_pct), 2) as avg_pl,
                ROUND(AVG(CASE WHEN profit_loss_pct > 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_win,
                ROUND(AVG(CASE WHEN profit_loss_pct < 0 THEN profit_loss_pct ELSE NULL END), 2) as avg_loss
            FROM positions 
            WHERE status = 'CLOSED'
            GROUP BY position_type
            ORDER BY position_type
        ''')
        columns = ['position_type', 'trades', 'win_rate', 'avg_pl', 'avg_win', 'avg_loss']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

# ================================================================================
# CONFIGURATION MANAGER
# ================================================================================

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path='config_dual.json'):
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
        required_keys = [
            'api', 'trading_rules', 'strategy_params', 
            'risk_management', 'profit_taking', 'execution_schedule'
        ]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required configuration section: {key}")
        
        # Validate dual buy specific settings
        if not self.config['trading_rules'].get('max_positions_b1'):
            logger.warning("Missing max_positions_b1 - using default 2")
        if not self.config['trading_rules'].get('max_positions_b2'):
            logger.warning("Missing max_positions_b2 - using default 2")
        
        # Validate API
        api_keys = ['key_id', 'secret_key', 'base_url']
        for key in api_keys:
            if key not in self.config['api']:
                raise ValueError(f"Missing API configuration: {key}")
            if not self.config['api'][key]:
                raise ValueError(f"Empty API configuration: {key}")
        
        # Validate trading rules
        trading_rules = self.config['trading_rules']
        if trading_rules.get('max_daily_buys', 0) <= 0:
            raise ValueError("max_daily_buys must be > 0")
        if not (0 <= trading_rules.get('min_signal_score', 0) <= 5):
            raise ValueError("min_signal_score must be between 0 and 5")
        
        # Validate strategy params
        strategy = self.config['strategy_params']
        if strategy.get('min_listing_days', 0) < 30:
            raise ValueError("min_listing_days must be >= 30")
        if strategy.get('sma_fast', 0) <= 0 or strategy.get('sma_slow', 0) <= 0:
            raise ValueError("SMA periods must be > 0")
        if strategy.get('sma_fast', 0) >= strategy.get('sma_slow', 0):
            raise ValueError("sma_fast must be < sma_slow")
        
        # Validate risk management
        risk = self.config['risk_management']
        if not (0 < risk.get('initial_stop_loss_pct', 0) < 1):
            raise ValueError("initial_stop_loss_pct must be between 0 and 1")
        # Note: max_hold_days validation removed for dual buy - uses tes_days_b1/tes_days_b2 instead
        
        # Validate profit taking
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
        
        # Validate execution schedule
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
    
    def get(self, *keys, default=None):
        """Get nested configuration value"""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
            if value is None:
                return default
        return value

# ================================================================================
# MARKET DATA FETCHER (Same as Single Buy)
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
# PATTERN RECOGNITION (Same as Single Buy)
# ================================================================================

class PatternDetector:
    """Detects explosive bullish candle patterns"""
    
    @staticmethod
    def is_engulfing(df: pd.DataFrame) -> bool:
        """Engulfing Pattern"""
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
        
        candle_range = curr['high'] - curr['low']
        body_size = curr['close'] - curr['open']
        is_explosive = (body_size / candle_range) >= 0.40 if candle_range > 0 else False
        
        return is_green and is_classic_piercing and is_explosive
    
    @staticmethod
    def is_tweezer_bottom(df: pd.DataFrame) -> bool:
        """Tweezer Bottom"""
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
        """Check for ANY explosive pattern (MANDATORY for entry)"""
        if cls.is_engulfing(df):
            return True, "Engulfing"
        if cls.is_piercing(df):
            return True, "Piercing"
        if cls.is_tweezer_bottom(df):
            return True, "Tweezer"
        return False, "None"

# ================================================================================
# STRATEGY ANALYZER (Same core logic as Single Buy)
# ================================================================================

class RajatAlphaAnalyzer:
    """
    Rajat Alpha V67 Signal Analyzer
    
    Implements the complete PineScript-inspired trading strategy logic including:
    - Market structure analysis (SMA50 > SMA200, EMA21 > SMA50)
    - Multi-timeframe confirmation (weekly/monthly)
    - Pullback detection with moving average proximity
    - Pattern recognition (engulfing, piercing, tweezer bottom)
    - Stalling filters to avoid overextended stocks
    - Extended stock gap filters
    - Comprehensive scoring system (0-5 + touch bonuses)
    - Touch tracking for bonus scoring
    
    The analyzer processes daily, weekly, and monthly data to generate
    entry signals with detailed reasoning and scoring.
    """
    
    def __init__(self, config: ConfigManager, data_fetcher: MarketDataFetcher):
        """
        Initialize the analyzer with configuration and data access.
        
        Args:
            config: Configuration manager with strategy parameters
            data_fetcher: Data fetcher for historical and real-time market data
        """
        self.config = config
        self.data_fetcher = data_fetcher
        
        # Touch tracking variables for bonus scoring
        # Reset when new trend detected, increment on MA touches
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
        Update touch tracking counters for bonus scoring.
        
        Touch tracking rewards stocks that repeatedly test support levels.
        Counters are reset when a new trend begins (SMA50 crosses above SMA200).
        Increments occur when price comes within 2.5% of EMA21 or SMA50.
        
        Args:
            df: Daily OHLCV dataframe with calculated indicators
            
        Logic:
        - Reset: SMA50 crosses above SMA200 (new bullish trend)
        - EMA21 Touch: |price - EMA21| / EMA21 <= 2.5%
        - SMA50 Touch: |price - SMA50| / SMA50 <= 2.5%
        """
        if len(df) < 2:
            return
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Check for new trend (SMA50 crosses above SMA200) - RESET FIRST
        if (prev['SMA50'] <= prev['SMA200']) and (curr['SMA50'] > curr['SMA200']):
            self.new_trend = True
            self.touch_ema21_count = 0
            self.touch_sma50_count = 0
            logger.debug("New trend detected - touch counters reset")
        else:
            self.new_trend = False
            
            # Only increment counters if not a new trend
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
    
    def check_market_structure(self, df: pd.DataFrame) -> bool:
        """
        Validate bullish market structure.
        
        Requires:
        - SMA50 > SMA200 (primary uptrend)
        - EMA21 > SMA50 (short-term momentum)
        
        This ensures we're only trading stocks in established uptrends
        with positive short-term momentum.
        
        Args:
            df: Daily OHLCV dataframe with SMA50, SMA200, EMA21
            
        Returns:
            bool: True if market structure is bullish
        """
        curr = df.iloc[-1]
        
        if pd.isna(curr['SMA50']) or pd.isna(curr['SMA200']) or pd.isna(curr['EMA21']):
            return False
        
        return (curr['SMA50'] > curr['SMA200']) and (curr['EMA21'] > curr['SMA50'])
    
    def check_multitimeframe_confirmation(self, df_daily: pd.DataFrame, 
                                          df_weekly: pd.DataFrame, 
                                          df_monthly: pd.DataFrame) -> Tuple[bool, bool]:
        """
        Check multi-timeframe confirmation for institutional alignment.
        
        Weekly: Close > EMA21 (21-period) - confirms intermediate-term strength
        Monthly: Close > EMA10 (10-period) - confirms long-term trend
        
        Args:
            df_daily: Daily OHLCV data
            df_weekly: Weekly aggregated data
            df_monthly: Monthly aggregated data
            
        Returns:
            Tuple[bool, bool]: (weekly_ok, monthly_ok)
        """
        df_weekly['EMA21'] = ta.ema(df_weekly['close'], length=21)
        df_monthly['EMA10'] = ta.ema(df_monthly['close'], length=10)
        
        curr_w = df_weekly.iloc[-1]
        curr_m = df_monthly.iloc[-1]
        
        weekly_ok = curr_w['close'] > curr_w['EMA21'] if not pd.isna(curr_w['EMA21']) else False
        monthly_ok = curr_m['close'] > curr_m['EMA10'] if not pd.isna(curr_m['EMA10']) else False
        
        return weekly_ok, monthly_ok
    
    def check_pullback(self, df: pd.DataFrame) -> bool:
        """
        Detect valid pullbacks to support levels in uptrending stocks.
        
        A valid pullback requires:
        1. Price near key moving averages (EMA21 or SMA50 within 2.5%)
        2. Recent higher high (made a new high in last pullback_days)
        
        This identifies stocks that have pulled back to support in ongoing uptrends,
        providing high-probability entry points.
        
        Args:
            df: Daily OHLCV dataframe with indicators
            
        Returns:
            bool: True if valid pullback detected
        """
        pullback_days = self.config.get('strategy_params', 'pullback_days')
        curr = df.iloc[-1]
        
        dist_ema21 = abs(curr['close'] - curr['EMA21']) / curr['EMA21'] if curr['EMA21'] > 0 else 1.0
        dist_sma50 = abs(curr['close'] - curr['SMA50']) / curr['SMA50'] if curr['SMA50'] > 0 else 1.0
        near_ma = (dist_ema21 <= 0.025) or (dist_sma50 <= 0.025)
        
        if len(df) < pullback_days + 1:
            return False
        
        recent_high = df['high'].iloc[-(pullback_days+1):-1].max()
        is_pullback = recent_high > curr['high']
        
        return near_ma and is_pullback
    
    def check_stalling(self, df: pd.DataFrame) -> bool:
        """
        Stalling filter to avoid overextended or consolidating stocks.
        
        Checks two timeframes:
        - Long-term (stalling_days_long): Range should be > stalling_range_pct
        - Short-term (stalling_days_short): Range should be < stalling_range_pct
        
        This prevents buying stocks that are either:
        - Stalling after a big run (long-term range too tight)
        - In tight consolidation that might break either way
        
        Args:
            df: Daily OHLCV dataframe
            
        Returns:
            bool: True if stock is stalling (avoid)
        """
        stalling_days_long = self.config.get('strategy_params', 'stalling_days_long')
        stalling_days_short = self.config.get('strategy_params', 'stalling_days_short')
        stalling_range_pct = self.config.get('strategy_params', 'stalling_range_pct')
        
        if len(df) < stalling_days_long:
            return False
        
        window_long = df.iloc[-stalling_days_long:]
        range_long = window_long['high'].max() - window_long['low'].min()
        avg_price_long = (window_long['high'].max() + window_long['low'].min()) / 2
        
        if avg_price_long == 0:
            return False
        
        range_pct_long = (range_long / avg_price_long) * 100
        is_stalling_long = range_pct_long <= stalling_range_pct
        
        window_short = df.iloc[-stalling_days_short:]
        range_short = window_short['high'].max() - window_short['low'].min()
        avg_price_short = (window_short['high'].max() + window_short['low'].min()) / 2
        
        if avg_price_short == 0:
            return False
        
        range_pct_short = (range_short / avg_price_short) * 100
        is_consolidating = range_pct_short <= stalling_range_pct
        
        return is_stalling_long and not is_consolidating
    
    def check_extended_stock(self, df: pd.DataFrame, current_price: float) -> Tuple[bool, float]:
        """
        Check if stock is extended (gapped up beyond threshold from previous close)
        
        Used by: Feature #3 - Extended Stock Filter
        
        Purpose:
            Prevents buying stocks that have already "run away" with large gaps.
            Applies to BOTH B1 and B2 entries in Dual Buy mode.
            
        Args:
            df: Daily OHLCV dataframe with historical prices
            current_price: Current market price of the stock
            
        Returns:
            Tuple[bool, float]: (is_extended, gap_percentage)
            
        Configuration:
            strategy_params.enable_extended_filter: true/false
            strategy_params.max_gap_pct: Maximum gap (default: 0.04 = 4%)
        """
        if len(df) < 2:
            return False, 0.0
        
        lookback = self.config.get('strategy_params', 'lookback_for_gap')
        prev_close = df.iloc[-(lookback + 1)]['close']
        
        if not pd.notna(prev_close) or not pd.notna(current_price):
            return False, 0.0
        
        gap_pct = (current_price - prev_close) / prev_close
        
        max_gap_pct = self.config.get('strategy_params', 'max_gap_pct')
        is_extended = gap_pct > max_gap_pct
        
        return is_extended, gap_pct
    
    def calculate_score(self, df: pd.DataFrame, symbol: str, weekly_ok: bool, monthly_ok: bool, pattern_found: bool) -> float:
        """
        Calculate the 0-5.5 rating score for entry signal strength.

        This scoring system evaluates multiple factors to determine signal quality:
        - Base score (0-5): Core technical and performance criteria
        - Bonus points (0-0.5): Touch tracking bonuses for additional confirmation

        Scoring Components (Base Score 0-5):
        1. RSI Filter (1 point): RSI14 must be above 50 for bullish momentum
           - Indicates strong upward momentum and reduces false signals
           - Awards point if RSI14 > 50

        2. Weekly EMA21 Bullish (1 point): Weekly timeframe shows bullish EMA21 alignment
           - Passed as weekly_ok parameter from check_multitimeframe_confirmation()

        3. Monthly EMA10 Bullish (1 point): Monthly timeframe shows bullish EMA10 alignment
           - Passed as monthly_ok parameter from check_multitimeframe_confirmation()

        4. Volume Above Average (1 point): Current volume exceeds 21-day volume SMA
           - Uses VOL_SMA21 indicator calculated in calculate_indicators()

        5. Demand Zone Position (1 point): Current low within 3.5% of 21-day low
           - Institutional demand zone: low_21 * 1.035 threshold
           - Indicates price near recent lows where institutional buying occurs

        Bonus Points (0-0.5):
        - EMA21 Touch Bonus (0.5 points): Stock touched EMA21 during pullback tracking
          - Only awarded if explosive pattern is also detected
        - SMA50 Touch Bonus (0.5 points): Stock touched SMA50 during pullback tracking
          - Additional confirmation of support level interaction, only with pattern

        Score Interpretation:
        - 0-2: Weak signal, typically rejected
        - 3-4: Moderate signal, may qualify for B2 entries
        - 4.5-5.5: Strong signal, qualifies for B1 and B2 entries

        Args:
            df: Daily OHLCV dataframe with calculated indicators
            symbol: Stock ticker symbol for logging
            weekly_ok: Boolean result from weekly timeframe EMA21 check
            monthly_ok: Boolean result from monthly timeframe EMA10 check
            pattern_found: Boolean indicating if explosive pattern was detected

        Returns:
            float: Total score from 0.0 to 5.5 (base 0-5 + bonuses 0-0.5)

        Note:
            Score directly influences position sizing and entry priority.
            Higher scores get executed first in the signal queue system.
        """
        curr = df.iloc[-1]
        score = 0
        
        # 1. RSI Filter (RSI14 > 50)
        if pd.notna(curr['RSI14']) and curr['RSI14'] > 50:
            score += 1
            logger.debug(f"[{symbol}] RSI filter passed: {curr['RSI14']:.2f} > 50 (+1 point)")
        else:
            rsi_val = curr['RSI14'] if pd.notna(curr['RSI14']) else 'N/A'
            logger.debug(f"[{symbol}] RSI filter failed: {rsi_val} <= 50")
        
        # 2. Weekly EMA21 bullish
        if weekly_ok:
            score += 1
    
        # 3. Monthly EMA10 bullish  
        if monthly_ok:
            score += 1

        # 4. Volume above average
        if pd.notna(curr['volume']) and pd.notna(curr['VOL_SMA21']) and curr['volume'] > curr['VOL_SMA21']:
            score += 1
        
        # 5. Demand Zone
        low_21 = df['low'].iloc[-21:].min()
        if pd.notna(curr['low']) and pd.notna(low_21):
            dz_threshold = low_21 * 1.035
            if curr['low'] <= dz_threshold:
                score += 1
        
        # BONUSES: Touch bonuses (only if pattern found)
        if pattern_found:
            if self.touch_ema21_count > 0:
                score += 0.5
            if self.touch_sma50_count > 0:
                score += 0.5
        
        return score
    
    def analyze_entry_signal(self, symbol: str) -> Tuple[bool, Dict]:
        """
        Perform complete entry signal analysis for a stock symbol.

        This is the main entry point for signal detection, implementing the full Rajat Alpha V67
        strategy logic. The analysis follows a sequential validation pipeline where each check
        must pass before proceeding to the next. If any check fails, the analysis stops and
        returns the failure reason.

        Analysis Pipeline (in order):
        1. Data Validation: Check for sufficient historical data and stock maturity
        2. Market Structure: Verify bullish EMA21/SMA50 alignment on daily chart
        3. Multi-Timeframe Confirmation: Validate weekly EMA21 and monthly EMA10 bullishness
        4. Pullback Detection: Confirm price is in a valid pullback from recent highs
        5. Pattern Recognition: Detect explosive candlestick patterns (engulfing, etc.)
        6. Stalling Filter: Avoid overextended or consolidating stocks
        7. Extended Stock Filter: Prevent entry on stocks with large recent gaps
        8. Score Calculation: Compute 0-5.5 rating based on technical factors

        Args:
            symbol: Stock ticker symbol to analyze

        Returns:
            Tuple[bool, Dict]: (signal_valid, analysis_details)
                - signal_valid: True if all checks pass and entry is recommended
                - analysis_details: Dictionary containing:
                    - 'symbol': Stock symbol
                    - 'signal': Boolean signal validity
                    - 'reason': Failure reason (if signal=False) or success message
                    - 'score': Calculated rating (0-5.5) if signal valid
                    - 'pattern': Detected pattern name (e.g., 'Bullish Engulfing')
                    - 'price': Current market price
                    - 'checks': Dictionary of individual check results
                    - 'gap_pct': Gap percentage (if extended stock filter enabled)

        Check Results Dictionary:
            - 'market_structure': Boolean result of EMA/SMA alignment
            - 'weekly_ok': Boolean result of weekly timeframe check
            - 'monthly_ok': Boolean result of monthly timeframe check
            - 'pullback': Boolean result of pullback validation
            - 'pattern': Boolean result of pattern detection
            - 'stalling': Boolean result of stalling filter (True = avoid)
            - 'extended_stock': Boolean result of gap filter (True = avoid)

        Notes:
            - Touch tracking is updated during analysis for bonus scoring
            - All technical indicators are calculated on-demand
            - Failed checks are logged with specific rejection reasons
            - Successful signals include detailed scoring breakdown in logs
        """
        result = {
            'symbol': symbol,
            'signal': False,
            'reason': '',
            'score': 0,
            'pattern': 'None',
            'price': 0,
            'checks': {}
        }
        
        df_daily = self.data_fetcher.get_daily_bars(symbol, days=365)
        if df_daily is None or len(df_daily) < self.config.get('strategy_params', 'min_listing_days'):
            result['reason'] = "Insufficient data or immature stock"
            return False, result
        
        df_daily = self.calculate_indicators(df_daily)
        df_weekly = self.data_fetcher.get_weekly_bars(df_daily)
        df_monthly = self.data_fetcher.get_monthly_bars(df_daily)
        
        # Update touch tracking
        self.update_touch_tracking(df_daily)
        
        structure_ok = self.check_market_structure(df_daily)
        result['checks']['market_structure'] = structure_ok
        if not structure_ok:
            result['reason'] = "Market structure not bullish"
            return False, result
        
        weekly_ok, monthly_ok = self.check_multitimeframe_confirmation(df_daily, df_weekly, df_monthly)
        result['checks']['weekly_ok'] = weekly_ok
        result['checks']['monthly_ok'] = monthly_ok
        if not (weekly_ok and monthly_ok):
            result['reason'] = f"MTF failed (Weekly: {weekly_ok}, Monthly: {monthly_ok})"
            return False, result
        
        pullback_ok = self.check_pullback(df_daily)
        result['checks']['pullback'] = pullback_ok
        if not pullback_ok:
            result['reason'] = "No valid pullback"
            return False, result
        
        pattern_found, pattern_name = PatternDetector.has_pattern(df_daily)
        result['pattern'] = pattern_name
        result['checks']['pattern'] = pattern_found
        if not pattern_found:
            result['reason'] = "No explosive pattern"
            return False, result
        
        is_stalling = self.check_stalling(df_daily)
        result['checks']['stalling'] = is_stalling
        if is_stalling:
            result['reason'] = "Stock is stalling"
            return False, result
        
        # Get current price
        current_price = self.data_fetcher.get_current_price(symbol)
        if current_price is None:
            result['reason'] = "Could not fetch current price"
            return False, result
        result['price'] = current_price
        
        # CHECK: Extended Stock Filter (gap up >4%)
        if self.config.get('strategy_params', 'enable_extended_filter'):
            is_extended, gap_pct = self.check_extended_stock(df_daily, current_price)
            result['checks']['extended_stock'] = is_extended
            result['gap_pct'] = gap_pct * 100
            
            if is_extended:
                result['reason'] = f"Stock is EXTENDED - Gap up {gap_pct*100:.2f}% (max allowed: {self.config.get('strategy_params', 'max_gap_pct')*100:.1f}%)"
                logger.warning(f"[{symbol}] {result['reason']}")
                return False, result
        
        # CHECK: Green Candle Filter (MANDATORY)
        # Stock must be green today (current price > yesterday's close)
        prev_close = df_daily.iloc[-2]['close']
        is_green_today = current_price > prev_close
        
        result['checks']['green_candle'] = is_green_today
        result['prev_close'] = prev_close
        
        if not is_green_today:
            result['reason'] = f'Stock is RED today (${current_price:.2f} <= ${prev_close:.2f}) - only green stocks allowed'
            logger.info(f'[{symbol}]  GREEN CANDLE FILTER: FAILED - Current: ${current_price:.2f}, Previous Close: ${prev_close:.2f}')
            return False, result
        else:
            logger.info(f'[{symbol}]  GREEN CANDLE FILTER: PASSED - Green today (${current_price:.2f} > ${prev_close:.2f})')
        
        # Calculate Score
        score = self.calculate_score(df_daily, symbol, weekly_ok, monthly_ok, pattern_found)
        result['score'] = score
        
        # ALL CHECKS PASSED
        result['signal'] = True
        result['reason'] = f"VALID BUY SIGNAL - Score: {score}/5, Pattern: {pattern_name}"
        
        logger.info(f"[{symbol}] {result['reason']}")
        logger.info(f"[{symbol}]   Touch Bonuses: EMA21({self.touch_ema21_count > 0}) SMA50({self.touch_sma50_count > 0})")
        return True, result

# ================================================================================
# SIGNAL QUEUE (Smart Execution)
# ================================================================================

class SignalQueue:
    """
    Manages detected signals during monitoring period
    Sorts and executes top N signals at end of window
    """
    
    def __init__(self, monitoring_minutes: int = 15, top_n: int = 5):
        self.signals = {}  # {symbol: {signal_details, first_seen, last_validated}}
        self.monitoring_minutes = monitoring_minutes
        self.top_n = top_n
        self.window_start_time = None
    
    def add_signal(self, symbol: str, signal_details: Dict):
        """Add or update signal in queue"""
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
            logger.info(f"[{symbol}] Added to signal queue (Score: {signal_details['score']})")
        else:
            # Revalidate existing signal
            self.signals[symbol]['last_validated'] = now
            self.signals[symbol]['revalidation_count'] += 1
            self.signals[symbol]['details'] = signal_details  # Update with latest
            logger.info(f"[{symbol}] Signal revalidated ({self.signals[symbol]['revalidation_count']} times)")
    
    def is_window_complete(self) -> bool:
        """Check if monitoring window is complete"""
        if self.window_start_time is None:
            return False
        
        elapsed = (datetime.now() - self.window_start_time).total_seconds() / 60
        return elapsed >= self.monitoring_minutes
    
    def get_top_signals(self, analyzer) -> List[Tuple[str, Dict]]:
        """
        Get top N signals sorted by rating with tie-breaking
        Revalidates all signals before execution
        """
        validated_signals = []
        
        for symbol, signal_data in self.signals.items():
            # CRITICAL: Revalidate signal before execution
            signal_valid, signal_details = analyzer.analyze_entry_signal(symbol)
            
            if signal_valid:
                # Signal still valid after monitoring period
                signal_details['persistence_score'] = signal_data['revalidation_count']
                validated_signals.append((symbol, signal_details))
                logger.info(f"[{symbol}] ✅ Signal STILL VALID after monitoring period (Score: {signal_details['score']})")
            else:
                logger.warning(f"[{symbol}] ❌ Signal EXPIRED - {signal_details['reason']}")
        
        # Sort with tie-breaking logic
        validated_signals = self._sort_with_tie_breaking(validated_signals, analyzer)
        
        # Return top N
        return validated_signals[:self.top_n]
    
    def _sort_with_tie_breaking(self, signals: List[Tuple[str, Dict]], analyzer) -> List[Tuple[str, Dict]]:
        """
        Sort signals by score descending, with tie-breaking preferences when scores are equal
        
        Tie-breaking preferences (in order of priority):
        1. Higher persistence (more revalidations during monitoring)
        2. Pattern type priority (Engulfing > Piercing > Tweezer)
        3. Lower current price (more affordable)
        """
        def get_tie_breaking_key(signal_tuple):
            symbol, signal_details = signal_tuple
            score = signal_details['score']
            persistence = signal_details.get('persistence_score', 0)
            
            # Pattern priority (higher number = higher priority)
            pattern = signal_details.get('pattern', 'None')
            pattern_priority = 0
            if 'Engulfing' in pattern:
                pattern_priority = 3
            elif 'Piercing' in pattern:
                pattern_priority = 2
            elif 'Tweezer' in pattern:
                pattern_priority = 1
            
            # Price (lower price gets slight preference for diversification)
            price = signal_details.get('price', float('inf'))
            
            # Return tuple for sorting: (score DESC, persistence DESC, pattern_priority DESC, price ASC)
            return (-score, -persistence, -pattern_priority, price)
        
        # Sort by the tie-breaking key
        signals.sort(key=get_tie_breaking_key)
        
        # Log the final ranking
        logger.info("Signal ranking with tie-breaking applied:")
        for i, (symbol, signal_details) in enumerate(signals[:self.top_n], 1):
            score = signal_details['score']
            pattern = signal_details.get('pattern', 'None')
            persistence = signal_details.get('persistence_score', 0)
            logger.info(f"  #{i}: {symbol} (Score: {score}, Pattern: {pattern}, Persistence: {persistence})")
        
        return signals
    
    def reset(self):
        """Clear queue after execution"""
        self.signals = {}
        self.window_start_time = None

# ================================================================================
# POSITION MANAGER (Dual Buy Version with B1/B2 Support)
# ================================================================================

class PositionManager:
    """Manages dual position sizing, entry execution, partial exits, and stop loss"""
    
    def __init__(self, trading_client: TradingClient, config: ConfigManager, 
                 db: PositionDatabase, data_fetcher: MarketDataFetcher):
        self.trading_client = trading_client
        self.config = config
        self.db = db
        self.data_fetcher = data_fetcher
    
    def calculate_position_size(self, symbol: str, current_price: float, 
                               position_type: str) -> Tuple[int, float]:
        """Calculate position size based on configuration and position type with capital constraints"""
        account = self.trading_client.get_account()
        equity = float(account.equity)
        
        # Check capital utilization limits
        max_equity_utilization = self.config.get('trading_rules', 'max_equity_utilization_pct')
        enable_dynamic_limits = self.config.get('trading_rules', 'enable_dynamic_position_limits')
        capital_conservation_mode = self.config.get('trading_rules', 'capital_conservation_mode')
        
        # Calculate current equity utilization
        open_positions = self.db.get_open_positions()
        current_utilization = 0.0
        
        for pos in open_positions:
            # Estimate current position value (approximate)
            pos_value = pos['remaining_qty'] * current_price if pos['symbol'] == symbol else pos['entry_price'] * pos['remaining_qty']
            current_utilization += pos_value / equity
        
        logger.debug(f"Current equity utilization: {current_utilization:.1%} (max allowed: {max_equity_utilization:.1%})")
        
        # Check if we're approaching capital limits
        if current_utilization >= max_equity_utilization:
            logger.warning(f"Capital utilization limit reached ({current_utilization:.1%} >= {max_equity_utilization:.1%}), blocking new positions")
            return 0, 0.0
        
        sizing_mode = self.config.get('position_sizing', 'mode')
        
        # Use position-type specific sizing if available
        pct_key = f'percent_of_equity_{position_type.lower()}'
        pct = self.config.get('position_sizing', pct_key)
        if pct is None:
            pct = self.config.get('position_sizing', 'percent_of_equity')
        
        # Apply capital conservation mode (reduce sizing when capital is constrained)
        if capital_conservation_mode and current_utilization > max_equity_utilization * 0.7:
            # Reduce position size when utilization > 70% of max
            pct *= 0.5  # 50% reduction
            logger.info(f"Capital conservation mode: Reducing position size to {pct:.1%} of equity")
        
        if sizing_mode == 'percent_equity':
            trade_amount = equity * pct
        elif sizing_mode == 'fixed_dollar':
            trade_amount = self.config.get('position_sizing', 'fixed_amount')
        elif sizing_mode == 'percent_of_amount':
            base_amount = self.config.get('position_sizing', 'base_amount')
            pct = self.config.get('position_sizing', 'percent_of_amount')
            trade_amount = base_amount * pct
        else:
            raise ValueError(f"Invalid position sizing mode: {sizing_mode}")
        
        # Apply max loss limit
        max_loss_mode = self.config.get('risk_management', 'max_loss_mode')
        initial_sl_pct = self.config.get('risk_management', 'initial_stop_loss_pct')
        
        if max_loss_mode == 'percent':
            max_loss_pct = self.config.get('risk_management', 'max_loss_pct')
            max_trade_amount = (equity * max_loss_pct) / initial_sl_pct
            trade_amount = min(trade_amount, max_trade_amount)
        elif max_loss_mode == 'dollar':
            max_loss_dollars = self.config.get('risk_management', 'max_loss_dollars')
            max_trade_amount = max_loss_dollars / initial_sl_pct
            trade_amount = min(trade_amount, max_trade_amount)
        
        # Final capital utilization check
        projected_utilization = current_utilization + (trade_amount / equity)
        if projected_utilization > max_equity_utilization:
            # Reduce trade amount to stay within limits
            available_amount = equity * (max_equity_utilization - current_utilization)
            trade_amount = min(trade_amount, available_amount)
            logger.info(f"Adjusting position size to stay within capital limits: ${trade_amount:.2f}")
        
        shares = int(trade_amount / current_price)
        actual_amount = shares * current_price
        
        return shares, actual_amount
    
    def execute_buy(self, symbol: str, position_type: str, signal_details: Dict) -> bool:
        """Execute buy order for B1 or B2 position"""
        current_price = signal_details['price']
        score = signal_details['score']
        
        # Calculate position size
        shares, trade_amount = self.calculate_position_size(symbol, current_price, position_type)
        
        if shares <= 0:
            logger.warning(f"[{symbol}] {position_type} position size too small (0 shares), skipping")
            return False
        
        # Calculate initial stop loss
        initial_sl_pct = self.config.get('risk_management', 'initial_stop_loss_pct')
        stop_loss = current_price * (1 - initial_sl_pct)
        
        logger.info(f"[{symbol}] Executing {position_type} BUY: {shares} shares @ ${current_price:.2f} (Total: ${trade_amount:.2f})")
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
            
            logger.info(f"[{symbol}] {position_type} order submitted successfully (ID: {order.id})")
            
            # Extract pattern from signal details
            pattern_type = signal_details.get('pattern', 'Unknown')
            
            # Record in database with position type
            position_id = self.db.add_position(
                symbol=symbol,
                position_type=position_type,
                entry_price=current_price,
                quantity=shares,
                stop_loss=stop_loss,
                score=score,
                pattern=pattern_type
            )
            
            logger.info(f"[{symbol}] {position_type} position recorded in database (Position ID: {position_id}, Pattern: {pattern_type})")
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] {position_type} order execution failed: {e}")
            return False
    
    def update_trailing_stop_loss(self, position: Dict, current_price: float):
        """Update dynamic trailing stop loss (3-tier system)"""
        entry_price = position['entry_price']
        current_sl = position['stop_loss']
        position_id = position['id']
        position_type = position['position_type']
        
        profit_pct = (current_price - entry_price) / entry_price
        
        tier1_profit = self.config.get('risk_management', 'tier_1_profit_pct')
        tier2_profit = self.config.get('risk_management', 'tier_2_profit_pct')
        tier1_sl = self.config.get('risk_management', 'tier_1_stop_loss_pct')
        tier2_sl = self.config.get('risk_management', 'tier_2_stop_loss_pct')
        initial_sl = self.config.get('risk_management', 'initial_stop_loss_pct')
        
        if profit_pct >= tier2_profit:
            new_sl_pct = tier2_sl
        elif profit_pct >= tier1_profit:
            new_sl_pct = tier1_sl
        else:
            new_sl_pct = initial_sl
        
        new_sl = entry_price * (1 - new_sl_pct)
        
        if new_sl > current_sl:
            self.db.update_stop_loss(position_id, new_sl)
            logger.info(f"[{position['symbol']}] {position_type} Trailing SL updated: ${current_sl:.2f} → ${new_sl:.2f} (Profit: {profit_pct*100:.2f}%)")
    
    def check_partial_exit_targets(self, position: Dict, current_price: float) -> List[Tuple[str, int, float]]:
        """Check if partial profit targets are hit"""
        if not self.config.get('profit_taking', 'enable_partial_exits'):
            return []
        
        entry_price = position['entry_price']
        remaining_qty = position['remaining_qty']
        
        exits_to_execute = []
        
        targets = [
            ('PT1', self.config.get('profit_taking', 'target_1_pct'), 
             self.config.get('profit_taking', 'target_1_qty')),
            ('PT2', self.config.get('profit_taking', 'target_2_pct'), 
             self.config.get('profit_taking', 'target_2_qty')),
            ('PT3', self.config.get('profit_taking', 'target_3_pct'), 
             self.config.get('profit_taking', 'target_3_qty'))
        ]
        
        for target_name, target_pct, target_qty_pct in targets:
            target_price = entry_price * (1 + target_pct)
            
            if current_price >= target_price:
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
        position_type = position['position_type']
        
        logger.info(f"[{symbol}] Executing {position_type} Partial Exit {target_name}: {quantity} shares @ ${current_price:.2f}")
        
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = self.trading_client.submit_order(order_request)
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            self.db.add_partial_exit(
                position_id=position['id'],
                quantity=quantity,
                exit_price=current_price,
                profit_target=target_name,
                profit_pct=profit_pct
            )
            
            logger.info(f"[{symbol}] {position_type} {target_name} executed successfully (+{profit_pct:.2f}%)")
            
        except Exception as e:
            logger.error(f"[{symbol}] {position_type} partial exit failed: {e}")
    
    def execute_full_exit(self, position: Dict, current_price: float, reason: str):
        """Execute full position exit (FIFO per type)"""
        symbol = position['symbol']
        position_type = position['position_type']
        remaining_qty = position['remaining_qty']
        
        logger.info(f"[{symbol}] Executing {position_type} FULL EXIT: {remaining_qty} shares @ ${current_price:.2f} (Reason: {reason})")
        
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=remaining_qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = self.trading_client.submit_order(order_request)
            
            self.db.close_position(
                position_id=position['id'],
                exit_price=current_price,
                exit_reason=reason
            )
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            logger.info(f"[{symbol}] {position_type} Position CLOSED (P/L: {profit_pct:+.2f}%)")
            
        except Exception as e:
            logger.error(f"[{symbol}] {position_type} full exit failed: {e}")
    
    def check_stop_loss(self, position: Dict, current_price: float) -> bool:
        """Check if stop loss triggered"""
        stop_loss = position['stop_loss']
        stop_loss_mode = self.config.get('risk_management', 'stop_loss_mode')
        
        if stop_loss_mode == 'closing_basis':
            return current_price <= stop_loss
        else:
            return current_price <= stop_loss
    
    def check_time_exit(self, position: Dict) -> bool:
        """Check if Time Exit Signal (TES) triggered (separate for B1/B2)"""
        position_type = position['position_type']
        
        # Get TES days for this position type
        if position_type == 'B1':
            max_hold_days = self.config.get('risk_management', 'tes_days_b1')
        elif position_type == 'B2':
            max_hold_days = self.config.get('risk_management', 'tes_days_b2')
        else:
            max_hold_days = self.config.get('risk_management', 'max_hold_days')
        
        days_held = self.db.get_days_held(position['id'])
        return days_held >= max_hold_days

# ================================================================================
# TRADING BOT ORCHESTRATOR (Dual Buy Version)
# ================================================================================

class RajatAlphaTradingBot:
    """Main trading bot orchestrator - Dual Buy version"""
    
    def __init__(self, config_path='config_dual.json'):
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
        
        # Initialize signal queue with configurable monitoring window
        monitoring_minutes = self.config.get('execution_schedule', 'signal_monitoring_minutes')
        if monitoring_minutes is None:
            monitoring_minutes = 15
        self.signal_queue = SignalQueue(monitoring_minutes=monitoring_minutes, top_n=5)
        
        logger.info("=" * 80)
        logger.info("RAJAT ALPHA V67 DUAL BUY TRADING BOT INITIALIZED")
        logger.info(f"Mode: {'PAPER TRADING' if self.is_paper else 'LIVE TRADING'}")
        logger.info(f"Max Positions per Stock: B1={self.config.get('trading_rules', 'max_b1_per_stock')}, B2={self.config.get('trading_rules', 'max_b2_per_stock')}")
        logger.info(f"B2 Min Score: {self.config.get('trading_rules', 'score_b2_min')}")
        logger.info(f"Max Equity Utilization: {self.config.get('trading_rules', 'max_equity_utilization_pct'):.1%}")
        logger.info(f"Dynamic Position Limits: {self.config.get('trading_rules', 'enable_dynamic_position_limits')}")
        logger.info(f"Capital Conservation Mode: {self.config.get('trading_rules', 'capital_conservation_mode')}")
        logger.info(f"Signal Queue: {monitoring_minutes}-minute monitoring, top 5 execution")
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
        
        if now.weekday() > 4:
            return False
        
        market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_start <= now <= market_end
    
    def is_buy_window(self) -> bool:
        """Check if we're in the configured buy window with flexible presets"""
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        preset = self.config.get('execution_schedule', 'buy_window_preset')
        presets = self.config.get('execution_schedule', 'available_presets')
        
        if preset == 'custom':
            # Use custom window configuration
            minutes = self.config.get('execution_schedule', 'custom_window_minutes')
            position = self.config.get('execution_schedule', 'custom_window_position')
            
            if position == 'start':
                # Window starts at market open
                start_time = now.replace(hour=9, minute=30, second=0)
                end_time = start_time + timedelta(minutes=minutes)
            elif position == 'end':
                # Window ends at market close
                end_time = now.replace(hour=16, minute=0, second=0)
                start_time = end_time - timedelta(minutes=minutes)
            else:
                # Default to end position
                end_time = now.replace(hour=16, minute=0, second=0)
                start_time = end_time - timedelta(minutes=minutes)
        else:
            # Use preset configuration
            if preset in presets:
                preset_config = presets[preset]
                start_h, start_m = map(int, preset_config['start'].split(':'))
                end_h, end_m = map(int, preset_config['end'].split(':'))
            else:
                # Fallback to manual config
                buy_window_start = self.config.get('execution_schedule', 'buy_window_start_time')
                buy_window_end = self.config.get('execution_schedule', 'buy_window_end_time')
                start_h, start_m = map(int, buy_window_start.split(':'))
                end_h, end_m = map(int, buy_window_end.split(':'))
            
            start_time = now.replace(hour=start_h, minute=start_m, second=0)
            end_time = now.replace(hour=end_h, minute=end_m, second=0)
        
        in_window = start_time <= now <= end_time
        
        if in_window:
            logger.debug(f"In buy window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} (preset: {preset})")
        
        return in_window
    
    def get_dynamic_position_limits(self) -> int:
        """
        Calculate dynamic total position limits based on current capital utilization
        
        Returns:
            Total max positions allowed by capital constraints
        """
        if not self.config.get('trading_rules', 'enable_dynamic_position_limits'):
            # Return static total limit based on equity and position size
            position_size_pct = self.config.get('position_sizing', 'percent_of_equity')
            return int(1.0 / position_size_pct)
        
        account = self.trading_client.get_account()
        equity = float(account.equity)
        max_equity_utilization = self.config.get('trading_rules', 'max_equity_utilization_pct')
        
        # Calculate current equity utilization
        open_positions = self.db.get_open_positions()
        current_utilization = 0.0
        
        for pos in open_positions:
            # Use entry price as approximation for current value
            pos_value = pos['entry_price'] * pos['remaining_qty']
            current_utilization += pos_value / equity
        
        # Calculate available capacity
        available_capacity = max_equity_utilization - current_utilization
        position_size_pct = self.config.get('position_sizing', 'percent_of_equity')
        
        if available_capacity <= 0:
            logger.warning(f"No capital capacity available (utilization: {current_utilization:.1%})")
            return 0
        
        # Estimate how many positions we can fit
        max_positions_by_capital = int(available_capacity / position_size_pct)
        
        # Apply conservative approach - leave buffer
        max_positions_by_capital = max(0, max_positions_by_capital - 1)
        
        logger.info(f"Dynamic limits - Capital utilization: {current_utilization:.1%}, Available capacity: {available_capacity:.1%}")
        logger.info(f"Dynamic limits - Total positions allowed: {max_positions_by_capital}")
        
        return max_positions_by_capital
    
    def run_sell_guardian(self):
        """SELL GUARDIAN: Monitors all open positions (B1 and B2) for exit conditions"""
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
            position_type = position['position_type']
            
            current_price = self.data_fetcher.get_current_price(symbol)
            if current_price is None:
                logger.warning(f"[{symbol}] Could not fetch current price, skipping")
                continue
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            logger.info(f"[{symbol}] {position_type} Position ID {position['id']} | P/L: {profit_pct:+.2f}% | Remaining: {position['remaining_qty']} shares")
            
            # 1. Check Stop Loss
            if self.position_manager.check_stop_loss(position, current_price):
                logger.warning(f"[{symbol}] {position_type} STOP LOSS TRIGGERED at ${current_price:.2f}")
                self.position_manager.execute_full_exit(position, current_price, "Stop Loss")
                continue
            
            # 2. Check Time Exit Signal
            if self.position_manager.check_time_exit(position):
                logger.warning(f"[{symbol}] {position_type} TIME EXIT SIGNAL (TES) triggered")
                self.position_manager.execute_full_exit(position, current_price, "TES")
                continue
            
            # 3. Update Trailing Stop Loss
            self.position_manager.update_trailing_stop_loss(position, current_price)
            
            # 4. Check Partial Profit Targets
            partial_exits = self.position_manager.check_partial_exit_targets(position, current_price)
            for target_name, quantity, target_price in partial_exits:
                self.position_manager.execute_partial_exit(
                    position, target_name, quantity, current_price
                )
    
    def run_buy_hunter(self):
        """BUY HUNTER: Collects signals during monitoring window, executes top N after 15-minute wait"""
        if not self.is_buy_window():
            logger.info("BUY HUNTER: Outside buy window, skipping scan")
            return
        
        logger.info("--- BUY HUNTER: Scanning Watchlist (Dual Buy Mode) ---")
        
        # Get watchlist
        portfolio_mode = self.config.get('trading_rules', 'portfolio_mode')
        
        if portfolio_mode == 'watchlist_only':
            watchlist = self.get_watchlist()
        elif portfolio_mode == 'specific_stocks':
            watchlist = self.config.get('trading_rules', 'specific_stocks')
        else:
            watchlist = self.get_watchlist()
        
        # PHASE 1: COLLECT SIGNALS
        for symbol in watchlist:
            try:
                signal_valid, signal_details = self.analyzer.analyze_entry_signal(symbol)
                
                # Log signal to history (whether executed or not)
                self.db.log_signal(symbol, signal_details, False)
                
                if not signal_valid:
                    logger.debug(f"[{symbol}] No signal - {signal_details['reason']}")
                    continue
                
                # Signal is valid - add to queue
                score = signal_details['score']
                logger.info(f"[{symbol}] ✅ ENTRY SIGNAL DETECTED!")
                logger.info(f"[{symbol}] Score: {score}/5, Pattern: {signal_details['pattern']}")
                
                self.signal_queue.add_signal(symbol, signal_details)
                
            except Exception as e:
                logger.error(f"[{symbol}] Analysis error: {e}")
                continue
        
        # PHASE 2: CHECK IF MONITORING WINDOW COMPLETE
        if self.signal_queue.is_window_complete():
            logger.info("--- SIGNAL QUEUE: Monitoring window complete, executing top signals ---")
            self._execute_queued_signals()
        else:
            if self.signal_queue.window_start_time is not None:
                elapsed = (datetime.now() - self.signal_queue.window_start_time).total_seconds() / 60
                remaining = self.signal_queue.monitoring_minutes - elapsed
                logger.info(f"--- SIGNAL QUEUE: Collecting signals... {elapsed:.1f}/{self.signal_queue.monitoring_minutes} minutes elapsed, {remaining:.1f} remaining ---")
            else:
                logger.info("--- SIGNAL QUEUE: No signals collected yet ---")
    
    def _execute_queued_signals(self):
        """Execute top N signals from the queue after re-validation"""
        # Get dynamic total position limits based on capital utilization
        max_total = self.get_dynamic_position_limits()
        score_b2_min = self.config.get('trading_rules', 'score_b2_min')
        
        # Count current positions
        b1_count = self.db.count_active_positions_by_type('B1')
        b2_count = self.db.count_active_positions_by_type('B2')
        total_positions = b1_count + b2_count
        
        # Check daily trade limit
        max_daily_buys = self.config.get('trading_rules', 'max_daily_buys')
        trades_today = self.db.count_trades_today()
        
        if trades_today >= max_daily_buys:
            logger.info(f"Daily trade limit reached ({trades_today}/{max_daily_buys}), no new buys")
            self.signal_queue.reset()
            return
        
        logger.info(f"Current Positions: Total={total_positions}/{max_total}, Daily trades: {trades_today}/{max_daily_buys}")
        
        # Check if we have capacity for any new positions
        if total_positions >= max_total:
            logger.info("Total position limit reached, no new buys possible")
            self.signal_queue.reset()
            return
        
        # Get top signals (re-validated)
        top_signals = self.signal_queue.get_top_signals(self.analyzer)
        
        if not top_signals:
            logger.info("No signals survived re-validation")
            self.signal_queue.reset()
            return
        
        logger.info(f"Executing top {len(top_signals)} signals (re-validated and prioritized by score)")
        
        # Execute prioritized signals
        executed_count = 0
        for symbol, signal_details in top_signals:
            score = signal_details['score']
            
            # SAME-DAY PROTECTION CHECK
            enable_same_day_protection = self.config.get('trading_rules', 'prevent_same_day_reentry')
            if enable_same_day_protection and self.db.was_traded_today(symbol):
                logger.info(f"[{symbol}] ⚠️ SAME-DAY PROTECTION: Already traded {symbol} today, skipping")
                continue
            
            # Check daily limit before executing
            if self.db.count_trades_today() >= max_daily_buys:
                logger.info(f"Daily trade limit reached ({max_daily_buys}), stopping execution")
                break
            
            # Check per-stock limits
            max_b1_per_stock = self.config.get('trading_rules', 'max_b1_per_stock')
            max_b2_per_stock = self.config.get('trading_rules', 'max_b2_per_stock')
            
            b1_positions_this_stock = len(self.db.get_open_positions(symbol=symbol, position_type='B1'))
            b2_positions_this_stock = len(self.db.get_open_positions(symbol=symbol, position_type='B2'))
            
            # DUAL BUY LOGIC
            has_b1_active = self.db.has_active_position(symbol, 'B1')
            
            # Minimum score requirements
            min_score_b1 = self.config.get('trading_rules', 'min_score_b1')
            score_b2_min = self.config.get('trading_rules', 'score_b2_min')
            
            # B1 ENTRY: When no B1 position active AND score meets B1 minimum AND per-stock limit not reached
            if not has_b1_active and b1_positions_this_stock < max_b1_per_stock and score >= min_score_b1:
                logger.info(f"[{symbol}] Triggering B1 entry (score: {score} >= {min_score_b1})")
                success = self.position_manager.execute_buy(symbol, 'B1', signal_details)
                
                if success:
                    # Log executed signal
                    self.db.log_signal(symbol, signal_details, True)
                    b1_count += 1
                    total_positions += 1
                    executed_count += 1
            
            # B2 ENTRY: When B1 active AND score >= B2 threshold AND per-stock limit not reached
            elif has_b1_active and score >= score_b2_min and b2_positions_this_stock < max_b2_per_stock:
                logger.info(f"[{symbol}] Triggering B2 entry (score: {score} >= {score_b2_min})")
                success = self.position_manager.execute_buy(symbol, 'B2', signal_details)
                
                if success:
                    # Log executed signal
                    self.db.log_signal(symbol, signal_details, True)
                    b2_count += 1
                    total_positions += 1
                    executed_count += 1
            
            # OPPORTUNITY SIGNALS
            elif has_b1_active and score < score_b2_min:
                logger.info(f"[{symbol}] ⚠️ OPPORTUNITY SIGNAL (B1 active, score {score} < B2 min {score_b2_min})")
            elif not has_b1_active and score < min_score_b1:
                logger.info(f"[{symbol}] ⚠️ WEAK SIGNAL (score {score} < B1 min {min_score_b1})")
            else:
                logger.info(f"[{symbol}] Signal valid but position/stock limits reached or other constraint")
        
        logger.info(f"Signal execution complete: {executed_count} trades executed")
        
        # Reset queue for next monitoring window
        self.signal_queue.reset()
    
    def get_scan_interval(self) -> int:
        """Get dynamic scan interval based on market time and signal queue status"""
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        # During signal collection phase, scan more frequently
        if self.signal_queue.window_start_time is not None and not self.signal_queue.is_window_complete():
            return 60  # Scan every minute during collection
        
        # Default intervals based on market time
        if now.hour >= 15 and now.minute >= 30:  # Last 30 minutes
            return 60  # 1 minute scans
        elif now.hour >= 15:  # Last hour
            return 120  # 2 minute scans
        else:  # Regular hours
            return 120  # 2 minute scans
    
    def run(self):
        """Main execution loop"""
        logger.info("Starting main execution loop...")
        
        while True:
            try:
                if self.is_market_open():
                    # 1. Always run Sell Guardian
                    self.run_sell_guardian()
                    
                    # 2. Run Buy Hunter (only in buy window)
                    self.run_buy_hunter()
                    
                    # 3. Sleep until next scan
                    interval = self.get_scan_interval()
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

# ================================================================================
# ENTRY POINT
# ================================================================================

if __name__ == "__main__":
    bot = RajatAlphaTradingBot(config_path='config/config_dual.json')
    bot.run()
