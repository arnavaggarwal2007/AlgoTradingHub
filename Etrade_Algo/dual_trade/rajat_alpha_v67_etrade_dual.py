"""
================================================================================
RAJAT ALPHA V67 - E*TRADE DUAL BUY ALGORITHMIC TRADING BOT
================================================================================

STRATEGY: Dual Buy Entry (B1 + B2) with Dynamic Trailing Stop Loss and Partial Exits
BASED ON: Rajat Alpha v67 Strategy (PineScript - Dual Buy Version)
PLATFORM: E*TRADE API
VERSION: 1.0
DATE: January 12, 2026

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
- pyetrade
- alpaca-py (for market data only)
- pandas
- pandas-ta
- sqlite3
- pytz

E*TRADE SPECIFIC:
- OAuth 1.0a authentication (tokens expire ~24 hours)
- Preview THEN Place order workflow (E*TRADE requirement)
- Market data from Alpaca (E*TRADE has limited free data)
- Commission configurable (default $0 for most accounts)

SETUP:
1. Run etrade_oauth_setup.py to get access tokens
2. Update config_etrade_dual.json with tokens and account IDs
3. Run this script

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

# E*TRADE imports
from pyetrade import ETradeOAuth, order, accounts

# Alpaca imports (for market data only)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame

# ================================================================================
# LOGGING SETUP
# ================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('rajat_alpha_v67_etrade_dual.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    
    def __init__(self, db_path='positions_etrade_dual.db'):
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
                etrade_order_id TEXT,
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
                etrade_order_id TEXT,
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
                     quantity: int, stop_loss: float, score: float, etrade_order_id: str = None) -> int:
        """Add new position to database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, position_type, entry_date, entry_price, 
                                   quantity, remaining_qty, stop_loss, score, etrade_order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, position_type, datetime.now().isoformat(), entry_price, 
              quantity, quantity, stop_loss, score, etrade_order_id))
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
                        profit_target: str, profit_pct: float, etrade_order_id: str = None):
        """Record partial exit"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO partial_exits (position_id, exit_date, quantity, 
                                       exit_price, profit_target, profit_pct, etrade_order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (position_id, datetime.now().isoformat(), quantity, exit_price,
              profit_target, profit_pct, etrade_order_id))
        
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
    
    def log_signal(self, symbol: str, signal_details: Dict, executed: bool):
        """
        Log all buy signals (executed and rejected) to signal_history table
        
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

# ================================================================================
# CONFIGURATION MANAGER
# ================================================================================

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path='config_etrade_dual.json'):
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
        """Validate required configuration keys"""
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
        
        logger.info("Configuration validation passed")
    
    def get(self, *keys):
        """Get nested configuration value"""
        value = self.config
        for key in keys:
            value = value.get(key)
            if value is None:
                return None
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
# E*TRADE ORDER MANAGER
# ================================================================================

class ETradeOrderManager:
    """
    Handles E*TRADE order execution with Preview → Place workflow
    Supports both BUY and SELL orders for dual position management
    """
    
    def __init__(self, consumer_key: str, consumer_secret: str, 
                 access_token: str, access_secret: str,
                 account_id_key: str, is_sandbox: bool = True):
        self.account_id_key = account_id_key
        self.is_sandbox = is_sandbox
        
        # Initialize order client
        self.order_client = order.ETradeOrder(
            consumer_key,
            consumer_secret,
            access_token,
            access_secret,
            dev=is_sandbox
        )
        
        logger.info(f"E*TRADE Order Manager initialized (Sandbox: {is_sandbox})")
    
    def preview_order(self, symbol: str, quantity: int, action: str, 
                     order_type: str = "MARKET") -> Optional[Dict]:
        """
        Preview order before placing (E*TRADE requirement)
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            action: "BUY" or "SELL"
            order_type: "MARKET" or "LIMIT"
        
        Returns:
            Preview response dict or None if failed
        """
        try:
            preview_data = {
                "PreviewOrderRequest": {
                    "orderType": order_type,
                    "clientOrderId": f"{symbol}_{action}_{int(time.time())}",
                    "Order": {
                        "allOrNone": "false",
                        "priceType": order_type,
                        "orderTerm": "GOOD_FOR_DAY",
                        "marketSession": "REGULAR",
                        "Instrument": {
                            "Product": {
                                "securityType": "EQ",
                                "symbol": symbol
                            },
                            "orderAction": action,
                            "quantityType": "QUANTITY",
                            "quantity": quantity
                        }
                    }
                }
            }
            
            logger.info(f"[{symbol}] Previewing {action} order for {quantity} shares...")
            
            response = self.order_client.preview_equity_order(
                account_id_key=self.account_id_key,
                resp_format='json',
                **preview_data
            )
            
            logger.info(f"[{symbol}] Preview successful")
            return response
            
        except Exception as e:
            logger.error(f"[{symbol}] Preview order failed: {e}")
            return None
    
    def place_order(self, preview_response: Dict) -> Optional[str]:
        """
        Place order after successful preview
        
        Args:
            preview_response: Response from preview_order()
        
        Returns:
            Order ID (string) or None if failed
        """
        try:
            # Extract preview IDs
            preview_ids = preview_response.get('PreviewOrderResponse', {}).get('PreviewIds', {})
            preview_id = preview_ids.get('previewId')
            
            if not preview_id:
                logger.error("No preview ID found in response")
                return None
            
            logger.info(f"Placing order with preview ID: {preview_id}")
            
            # Place order using preview ID
            place_data = {
                "PlaceOrderRequest": {
                    "orderType": "EQ",
                    "clientOrderId": preview_response['PreviewOrderResponse']['Order']['clientOrderId'],
                    "PreviewIds": {
                        "previewId": preview_id
                    },
                    "Order": preview_response['PreviewOrderResponse']['Order']
                }
            }
            
            response = self.order_client.place_equity_order(
                account_id_key=self.account_id_key,
                resp_format='json',
                **place_data
            )
            
            # Extract order ID
            order_id = response.get('PlaceOrderResponse', {}).get('OrderIds', {}).get('orderId')
            
            if order_id:
                logger.info(f"✅ Order placed successfully (ID: {order_id})")
                return str(order_id)
            else:
                logger.error("Order placed but no order ID returned")
                return None
            
        except Exception as e:
            logger.error(f"Place order failed: {e}")
            return None
    
    def execute_market_order(self, symbol: str, quantity: int, action: str) -> Optional[str]:
        """
        Complete workflow: Preview → Place market order
        
        Returns:
            Order ID or None if failed
        """
        # Step 1: Preview
        preview_response = self.preview_order(symbol, quantity, action, "MARKET")
        
        if not preview_response:
            logger.error(f"[{symbol}] Cannot place order - preview failed")
            return None
        
        # Step 2: Place
        order_id = self.place_order(preview_response)
        
        return order_id

# ================================================================================
# POSITION MANAGER (E*TRADE Dual Buy Version)
# ================================================================================

class PositionManager:
    """
    Manages dual position sizing, entry execution, partial exits, and stop loss
    E*TRADE specific implementation with B1/B2 support
    """
    
    def __init__(self, order_manager: ETradeOrderManager, config: ConfigManager, 
                 db: PositionDatabase, data_fetcher: MarketDataFetcher,
                 accounts_client):
        self.order_manager = order_manager
        self.config = config
        self.db = db
        self.data_fetcher = data_fetcher
        self.accounts_client = accounts_client
    
    def get_account_balance(self) -> float:
        """Get current account equity from E*TRADE"""
        try:
            balance = self.accounts_client.get_account_balance(
                account_id_key=self.order_manager.account_id_key,
                resp_format='json'
            )
            
            # Extract total account value
            computed = balance.get('BalanceResponse', {}).get('Computed', {})
            total_value = float(computed.get('RealTimeValues', {}).get('totalAccountValue', 0))
            
            return total_value
            
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return 0.0
    
    def calculate_position_size(self, symbol: str, current_price: float, 
                               position_type: str) -> Tuple[int, float]:
        """
        Calculate position size based on configuration and position type
        Returns: (shares_to_buy, trade_amount)
        """
        equity = self.get_account_balance()
        
        if equity == 0:
            logger.error("Cannot calculate position size - account balance is 0")
            return 0, 0
        
        sizing_mode = self.config.get('position_sizing', 'mode')
        
        # Use position-type specific sizing if available
        pct_key = f'percent_of_equity_{position_type.lower()}'
        pct = self.config.get('position_sizing', pct_key)
        if pct is None:
            pct = self.config.get('position_sizing', 'percent_of_equity')
        
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
        
        shares = int(trade_amount / current_price)
        actual_amount = shares * current_price
        
        return shares, actual_amount
    
    def execute_buy(self, symbol: str, position_type: str, signal_details: Dict) -> bool:
        """Execute buy order for B1 or B2 position via E*TRADE"""
        current_price = signal_details['price']
        score = signal_details['score']
        
        # Calculate position size
        shares, trade_amount = self.calculate_position_size(symbol, current_price, position_type)
        
        if shares <= 0:
            logger.warning(f"[{symbol}] {position_type} Position size too small (0 shares), skipping")
            return False
        
        # Calculate initial stop loss
        initial_sl_pct = self.config.get('risk_management', 'initial_stop_loss_pct')
        stop_loss = current_price * (1 - initial_sl_pct)
        
        logger.info(f"[{symbol}] {position_type} Executing BUY: {shares} shares @ ${current_price:.2f} (Total: ${trade_amount:.2f})")
        logger.info(f"[{symbol}] {position_type} Initial Stop Loss: ${stop_loss:.2f} ({initial_sl_pct*100:.1f}% below entry)")
        
        try:
            # Execute via E*TRADE (preview + place)
            order_id = self.order_manager.execute_market_order(symbol, shares, "BUY")
            
            if not order_id:
                logger.error(f"[{symbol}] {position_type} Order execution failed")
                return False
            
            logger.info(f"[{symbol}] {position_type} Order submitted successfully (ID: {order_id})")
            
            # Record in database
            position_id = self.db.add_position(
                symbol=symbol,
                position_type=position_type,
                entry_price=current_price,
                quantity=shares,
                stop_loss=stop_loss,
                score=score,
                etrade_order_id=order_id
            )
            
            logger.info(f"[{symbol}] {position_type} Position recorded in database (Position ID: {position_id})")
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] {position_type} Order execution failed: {e}")
            return False
    
    def update_trailing_stop_loss(self, position: Dict, current_price: float):
        """Update dynamic trailing stop loss (3-tier system)"""
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
        
        if profit_pct >= tier2_profit:
            new_sl_pct = tier2_sl
        elif profit_pct >= tier1_profit:
            new_sl_pct = tier1_sl
        else:
            new_sl_pct = initial_sl
        
        new_sl = entry_price * (1 - new_sl_pct)
        
        # Only update if new SL is higher (trailing up)
        if new_sl > current_sl:
            self.db.update_stop_loss(position_id, new_sl)
            logger.info(f"[{position['symbol']}] {position['position_type']} Trailing SL updated: ${current_sl:.2f} → ${new_sl:.2f} (Profit: {profit_pct*100:.2f}%)")
    
    def check_partial_exit_targets(self, position: Dict, current_price: float) -> List[Tuple[str, int, float]]:
        """Check if partial profit targets are hit"""
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
        """Execute partial exit order via E*TRADE"""
        symbol = position['symbol']
        position_type = position['position_type']
        
        logger.info(f"[{symbol}] {position_type} Executing Partial Exit {target_name}: {quantity} shares @ ${current_price:.2f}")
        
        try:
            # Execute sell order
            order_id = self.order_manager.execute_market_order(symbol, quantity, "SELL")
            
            if not order_id:
                logger.error(f"[{symbol}] {position_type} Partial exit failed - order not placed")
                return
            
            # Record partial exit
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            self.db.add_partial_exit(
                position_id=position['id'],
                quantity=quantity,
                exit_price=current_price,
                profit_target=target_name,
                profit_pct=profit_pct,
                etrade_order_id=order_id
            )
            
            logger.info(f"[{symbol}] {position_type} {target_name} executed successfully (+{profit_pct:.2f}%)")
            
        except Exception as e:
            logger.error(f"[{symbol}] {position_type} Partial exit failed: {e}")
    
    def execute_full_exit(self, position: Dict, current_price: float, reason: str):
        """Execute full position exit (FIFO) via E*TRADE"""
        symbol = position['symbol']
        position_type = position['position_type']
        remaining_qty = position['remaining_qty']
        
        logger.info(f"[{symbol}] {position_type} Executing FULL EXIT: {remaining_qty} shares @ ${current_price:.2f} (Reason: {reason})")
        
        try:
            # Execute sell order
            order_id = self.order_manager.execute_market_order(symbol, remaining_qty, "SELL")
            
            if not order_id:
                logger.error(f"[{symbol}] {position_type} Full exit failed - order not placed")
                return
            
            # Close position in database
            self.db.close_position(
                position_id=position['id'],
                exit_price=current_price,
                exit_reason=reason
            )
            
            profit_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            logger.info(f"[{symbol}] {position_type} Position CLOSED (P/L: {profit_pct:+.2f}%)")
            
        except Exception as e:
            logger.error(f"[{symbol}] {position_type} Full exit failed: {e}")
    
    def check_stop_loss(self, position: Dict, current_price: float) -> bool:
        """Check if stop loss triggered"""
        stop_loss = position['stop_loss']
        stop_loss_mode = self.config.get('risk_management', 'stop_loss_mode')
        
        if stop_loss_mode == 'closing_basis':
            return current_price <= stop_loss
        elif stop_loss_mode == 'intraday_basis':
            return current_price <= stop_loss
        else:
            return current_price <= stop_loss
    
    def check_time_exit(self, position: Dict) -> bool:
        """Check if Time Exit Signal (TES) triggered"""
        position_type = position['position_type']
        
        # Get TES days based on position type
        if position_type == 'B1':
            max_hold_days = self.config.get('risk_management', 'tes_days_b1')
        elif position_type == 'B2':
            max_hold_days = self.config.get('risk_management', 'tes_days_b2')
        else:
            max_hold_days = self.config.get('risk_management', 'max_hold_days')
        
        days_held = self.db.get_days_held(position['id'])
        return days_held >= max_hold_days

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
    """Implements complete Rajat Alpha v67 strategy logic"""
    
    def __init__(self, config: ConfigManager, data_fetcher: MarketDataFetcher):
        self.config = config
        self.data_fetcher = data_fetcher
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all required technical indicators"""
        df['SMA50'] = ta.sma(df['close'], length=50)
        df['SMA200'] = ta.sma(df['close'], length=200)
        df['EMA21'] = ta.ema(df['close'], length=21)
        df['VOL_SMA21'] = ta.sma(df['volume'], length=21)
        return df
    
    def check_market_structure(self, df: pd.DataFrame) -> bool:
        """Requirement: 50 SMA > 200 SMA AND 21 EMA > 50 SMA"""
        curr = df.iloc[-1]
        
        if pd.isna(curr['SMA50']) or pd.isna(curr['SMA200']) or pd.isna(curr['EMA21']):
            return False
        
        return (curr['SMA50'] > curr['SMA200']) and (curr['EMA21'] > curr['SMA50'])
    
    def check_multitimeframe_confirmation(self, df_daily: pd.DataFrame, 
                                          df_weekly: pd.DataFrame, 
                                          df_monthly: pd.DataFrame) -> Tuple[bool, bool]:
        """Weekly: close > Weekly EMA21, Monthly: close > Monthly EMA10"""
        df_weekly['EMA21'] = ta.ema(df_weekly['close'], length=21)
        df_monthly['EMA10'] = ta.ema(df_monthly['close'], length=10)
        
        curr_w = df_weekly.iloc[-1]
        curr_m = df_monthly.iloc[-1]
        
        weekly_ok = curr_w['close'] > curr_w['EMA21'] if not pd.isna(curr_w['EMA21']) else False
        monthly_ok = curr_m['close'] > curr_m['EMA10'] if not pd.isna(curr_m['EMA10']) else False
        
        return weekly_ok, monthly_ok
    
    def check_pullback(self, df: pd.DataFrame) -> bool:
        """Pullback Detection"""
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
        """Stalling Filter"""
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
    
    def calculate_score(self, df: pd.DataFrame, symbol: str) -> float:
        """Scoring System (0-5)"""
        curr = df.iloc[-1]
        score = 0
        
        # 1. Stock vs QQQ Performance
        try:
            qqq_df = self.data_fetcher.get_daily_bars('QQQ', days=30)
            if qqq_df is not None and len(qqq_df) >= 22:
                stock_perf = (curr['close'] - df.iloc[-22]['close']) / df.iloc[-22]['close']
                qqq_perf = (qqq_df.iloc[-1]['close'] - qqq_df.iloc[-22]['close']) / qqq_df.iloc[-22]['close']
                if stock_perf > qqq_perf:
                    score += 1
        except:
            pass
        
        # 4. Volume above average
        if curr['volume'] > curr['VOL_SMA21']:
            score += 1
        
        # 5. Demand Zone
        low_21 = df['low'].iloc[-21:].min()
        dz_threshold = low_21 * 1.035
        if curr['low'] <= dz_threshold:
            score += 1
        
        return score
    
    def analyze_entry_signal(self, symbol: str) -> Tuple[bool, Dict]:
        """COMPLETE ENTRY ANALYSIS"""
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
        
        score = self.calculate_score(df_daily, symbol)
        result['score'] = score
        
        current_price = self.data_fetcher.get_current_price(symbol)
        result['price'] = current_price
        
        result['signal'] = True
        result['reason'] = f"VALID BUY SIGNAL - Score: {score}/5, Pattern: {pattern_name}"
        
        logger.info(f"[{symbol}] {result['reason']}")
        return True, result



# ================================================================================
# TRADING BOT ORCHESTRATOR (Dual Buy Version)
# ================================================================================

class RajatAlphaTradingBot:
    """Main trading bot orchestrator - E*TRADE Dual Buy version"""
    
    def __init__(self, config_path='config_etrade_dual.json'):
        # Load configuration
        self.config = ConfigManager(config_path)
        
        # Initialize database
        self.db = PositionDatabase()
        
        # Initialize E*TRADE OAuth
        consumer_key = self.config.get('api', 'consumer_key')
        consumer_secret = self.config.get('api', 'consumer_secret')
        access_token = self.config.get('api', 'access_token')
        access_secret = self.config.get('api', 'access_secret')
        account_id_key = self.config.get('api', 'account_id_key')
        environment = self.config.get('api', 'environment')
        
        is_sandbox = (environment == 'sandbox')
        
        # Validate OAuth credentials
        if not access_token or not access_secret:
            logger.error("Missing E*TRADE access tokens!")
            logger.error("Please run: python etrade_oauth_setup.py")
            raise ValueError("E*TRADE OAuth not configured")
        
        # Initialize E*TRADE clients
        self.order_manager = ETradeOrderManager(
            consumer_key, consumer_secret,
            access_token, access_secret,
            account_id_key, is_sandbox
        )
        
        self.accounts_client = accounts.ETradeAccounts(
            consumer_key, consumer_secret,
            access_token, access_secret,
            dev=is_sandbox
        )
        
        # Initialize market data (using Alpaca)
        # Note: E*TRADE market data requires subscription, so we use Alpaca for free data
        alpaca_key = self.config.get('market_data', 'alpaca_api_key')
        alpaca_secret = self.config.get('market_data', 'alpaca_secret_key')
        
        if not alpaca_key or not alpaca_secret:
            logger.warning("No Alpaca credentials - market data may not work")
            logger.warning("Add alpaca_api_key and alpaca_secret_key to config for market data")
        
        self.data_client = StockHistoricalDataClient(alpaca_key, alpaca_secret)
        self.data_fetcher = MarketDataFetcher(self.data_client)
        
        # Initialize components
        self.analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
        self.position_manager = PositionManager(
            self.order_manager, self.config, self.db, 
            self.data_fetcher, self.accounts_client
        )
        
        logger.info("=" * 80)
        logger.info("RAJAT ALPHA V67 - E*TRADE DUAL BUY TRADING BOT INITIALIZED")
        logger.info(f"Mode: {'SANDBOX' if is_sandbox else 'PRODUCTION'}")
        logger.info(f"Account: {account_id_key}")
        logger.info(f"Max B1 Positions: {self.config.get('trading_rules', 'max_positions_b1')}")
        logger.info(f"Max B2 Positions: {self.config.get('trading_rules', 'max_positions_b2')}")
        logger.info(f"B2 Min Score: {self.config.get('trading_rules', 'score_b2_min')}")
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
                symbols = [line.strip().upper() for line in f if line.strip()]
            
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
        """Check if we're in the configured buy window"""
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        buy_window_start = self.config.get('execution_schedule', 'buy_window_start_time')
        buy_window_end = self.config.get('execution_schedule', 'buy_window_end_time')
        
        start_h, start_m = map(int, buy_window_start.split(':'))
        end_h, end_m = map(int, buy_window_end.split(':'))
        
        start_time = now.replace(hour=start_h, minute=start_m, second=0)
        end_time = now.replace(hour=end_h, minute=end_m, second=0)
        
        return start_time <= now <= end_time
    
    def get_scan_interval(self) -> int:
        """Get scan interval based on time of day"""
        if self.is_buy_window():
            return self.config.get('execution_schedule', 'last_hour_interval_seconds')
        else:
            return self.config.get('execution_schedule', 'default_interval_seconds')
    
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
        """BUY HUNTER: Scans watchlist for B1 and B2 entry signals"""
        if not self.is_buy_window():
            logger.info("BUY HUNTER: Outside buy window, skipping scan")
            return
        
        logger.info("--- BUY HUNTER: Scanning Watchlist (Dual Buy Mode) ---")
        
        # Get position limits
        max_b1 = self.config.get('trading_rules', 'max_positions_b1')
        max_b2 = self.config.get('trading_rules', 'max_positions_b2')
        score_b2_min = self.config.get('trading_rules', 'score_b2_min')
        
        # Count current positions
        b1_count = self.db.count_active_positions_by_type('B1')
        b2_count = self.db.count_active_positions_by_type('B2')
        
        logger.info(f"Current Positions: B1={b1_count}/{max_b1}, B2={b2_count}/{max_b2}")
        
        # Get watchlist
        portfolio_mode = self.config.get('trading_rules', 'portfolio_mode')
        
        if portfolio_mode == 'watchlist_only':
            watchlist = self.get_watchlist()
        elif portfolio_mode == 'specific_stocks':
            watchlist = self.config.get('trading_rules', 'specific_stocks')
        else:
            watchlist = self.get_watchlist()
        
        # Scan each symbol
        for symbol in watchlist:
            # Check max trades per stock for each type
            max_trades_per_stock_b1 = self.config.get('trading_rules', 'max_trades_per_stock_b1')
            max_trades_per_stock_b2 = self.config.get('trading_rules', 'max_trades_per_stock_b2')
            
            b1_positions_this_stock = len(self.db.get_open_positions(symbol=symbol, position_type='B1'))
            b2_positions_this_stock = len(self.db.get_open_positions(symbol=symbol, position_type='B2'))
            
            # Analyze for entry signal
            try:
                signal_valid, signal_details = self.analyzer.analyze_entry_signal(symbol)
                
                if not signal_valid:
                    logger.debug(f"[{symbol}] No signal - {signal_details['reason']}")
                    continue
                
                # Signal is valid
                score = signal_details['score']
                logger.info(f"[{symbol}] ✅ ENTRY SIGNAL DETECTED!")
                logger.info(f"[{symbol}] Score: {score}/5, Pattern: {signal_details['pattern']}")
                
                # DUAL BUY LOGIC
                has_b1_active = self.db.has_active_position(symbol, 'B1')
                
                # B1 ENTRY: When no B1 position active
                if not has_b1_active and b1_count < max_b1 and b1_positions_this_stock < max_trades_per_stock_b1:
                    logger.info(f"[{symbol}] Triggering B1 entry (score: {score})")
                    success = self.position_manager.execute_buy(symbol, 'B1', signal_details)
                    
                    if success:
                        b1_count += 1
                
                # B2 ENTRY: When B1 active AND score >= threshold
                elif has_b1_active and score >= score_b2_min and b2_count < max_b2 and b2_positions_this_stock < max_trades_per_stock_b2:
                    logger.info(f"[{symbol}] Triggering B2 entry (score: {score} >= {score_b2_min})")
                    success = self.position_manager.execute_buy(symbol, 'B2', signal_details)
                    
                    if success:
                        b2_count += 1
                
                # OPPORTUNITY SIGNAL: B1 active but score too low for B2
                elif has_b1_active and score < score_b2_min:
                    logger.info(f"[{symbol}] ⚠️ OPPORTUNITY SIGNAL (B1 active, score {score} < {score_b2_min})")
                
                else:
                    logger.info(f"[{symbol}] Signal valid but position limits reached or other constraint")
                    
            except Exception as e:
                logger.error(f"[{symbol}] Analysis error: {e}")
                continue
    
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
    bot = RajatAlphaTradingBot(config_path='config_etrade_dual.json')
    bot.run()
