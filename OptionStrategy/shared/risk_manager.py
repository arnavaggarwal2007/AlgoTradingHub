"""
================================================================================
PORTFOLIO-LEVEL RISK MANAGER
================================================================================
Enforces all "Never Blow Up" rules across all strategies.
This is the GATEKEEPER — no trade gets placed without passing through here.

Rules Enforced:
1. 5% max risk per trade
2. 20% max portfolio exposure  
3. 2:1 stop loss enforcement
4. Earnings avoidance
5. Sector correlation limits
6. Position sizing calculations
================================================================================
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger('options_strategy')


# Sector mapping for correlation checks
SECTOR_MAP = {
    # Technology
    'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology',
    'AMZN': 'Technology', 'META': 'Technology', 'NVDA': 'Technology',
    'AMD': 'Technology', 'INTC': 'Technology', 'CRM': 'Technology',
    'ADBE': 'Technology', 'ORCL': 'Technology', 'CSCO': 'Technology',
    'AVGO': 'Technology', 'QCOM': 'Technology', 'TSM': 'Technology',
    # Financials
    'JPM': 'Financials', 'BAC': 'Financials', 'GS': 'Financials',
    'MS': 'Financials', 'WFC': 'Financials', 'C': 'Financials',
    'V': 'Financials', 'MA': 'Financials', 'AXP': 'Financials',
    # Healthcare
    'JNJ': 'Healthcare', 'UNH': 'Healthcare', 'PFE': 'Healthcare',
    'ABBV': 'Healthcare', 'MRK': 'Healthcare', 'LLY': 'Healthcare',
    'TMO': 'Healthcare', 'ABT': 'Healthcare',
    # Consumer
    'WMT': 'Consumer', 'KO': 'Consumer', 'PEP': 'Consumer',
    'PG': 'Consumer', 'COST': 'Consumer', 'MCD': 'Consumer',
    'NKE': 'Consumer', 'SBUX': 'Consumer', 'HD': 'Consumer',
    # Energy
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy',
    'SLB': 'Energy', 'EOG': 'Energy',
    # Industrials
    'BA': 'Industrials', 'CAT': 'Industrials', 'GE': 'Industrials',
    'UPS': 'Industrials', 'HON': 'Industrials', 'LMT': 'Industrials',
    # ETFs / Indices
    'SPY': 'Index', 'QQQ': 'Index', 'IWM': 'Index',
    'DIA': 'Index', 'SPX': 'Index', 'XSP': 'Index',
    'VIX': 'Volatility',
}


class RiskManager:
    """
    Portfolio-level risk management system.
    
    Every trade MUST pass through approve_trade() before execution.
    This class is the gatekeeper for all strategies.
    """

    def __init__(self, config: dict, db_path: str = 'db/options_trades.db'):
        self.config = config.get('global_risk', config)
        self.max_portfolio_risk_pct = self.config.get('max_portfolio_risk_pct', 0.20)
        self.max_risk_per_trade_pct = self.config.get('max_risk_per_trade_pct', 0.05)
        self.max_positions = self.config.get('max_positions', 10)
        self.max_same_sector = self.config.get('max_same_sector', 3)
        self.earnings_buffer_days = self.config.get('earnings_buffer_days', 5)
        self.stop_loss_multiplier = self.config.get('stop_loss_multiplier', 3.0)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.50)
        
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the trades tracking database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS option_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                underlying TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL DEFAULT 0,
                premium_collected REAL DEFAULT 0,
                max_loss REAL DEFAULT 0,
                collateral_used REAL DEFAULT 0,
                stop_loss_price REAL DEFAULT 0,
                profit_target_price REAL DEFAULT 0,
                entry_date TEXT NOT NULL,
                expiration_date TEXT,
                exit_date TEXT,
                exit_price REAL,
                pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'open',
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date TEXT PRIMARY KEY,
                realized_pnl REAL DEFAULT 0,
                unrealized_pnl REAL DEFAULT 0,
                total_equity REAL DEFAULT 0,
                total_collateral REAL DEFAULT 0,
                trade_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()

    # ──────────────────────────────────────────────────────────────
    # TRADE APPROVAL (THE GATEKEEPER)
    # ──────────────────────────────────────────────────────────────

    def approve_trade(
        self,
        symbol: str,
        underlying: str,
        trade_type: str,  # 'csp', 'cc', 'bull_put_spread', 'iron_condor', etc.
        max_loss: float,
        collateral_required: float,
        account_equity: float,
        earnings_dates: Optional[List[str]] = None,
        expiration_date: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Approve or reject a trade based on all risk rules.
        
        Returns: (approved: bool, reason: str)
        """
        checks = [
            self._check_position_limit(),
            self._check_risk_per_trade(max_loss, account_equity),
            self._check_portfolio_exposure(collateral_required, account_equity),
            self._check_sector_concentration(underlying),
        ]
        
        if earnings_dates and expiration_date:
            checks.append(
                self._check_earnings_conflict(earnings_dates, expiration_date)
            )

        for approved, reason in checks:
            if not approved:
                logger.warning(f"TRADE REJECTED: {underlying} {trade_type} — {reason}")
                return False, reason

        logger.info(f"TRADE APPROVED: {underlying} {trade_type} | MaxLoss=${max_loss:.2f}")
        return True, "All risk checks passed"

    def _check_position_limit(self) -> Tuple[bool, str]:
        """Rule: Don't exceed max open positions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM option_trades WHERE status = 'open'")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count >= self.max_positions:
            return False, f"Max positions reached ({count}/{self.max_positions})"
        return True, "OK"

    def _check_risk_per_trade(self, max_loss: float, equity: float) -> Tuple[bool, str]:
        """Rule 1: Never risk more than 5% on a single trade."""
        max_allowed_risk = equity * self.max_risk_per_trade_pct
        if max_loss > max_allowed_risk:
            return False, (
                f"Trade risk ${max_loss:.2f} exceeds 5% limit "
                f"(${max_allowed_risk:.2f} on ${equity:.2f} equity)"
            )
        return True, "OK"

    def _check_portfolio_exposure(
        self, new_collateral: float, equity: float
    ) -> Tuple[bool, str]:
        """Rule 2: Total portfolio exposure must stay under 20%."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(collateral_used), 0) FROM option_trades WHERE status = 'open'"
        )
        current_collateral = cursor.fetchone()[0]
        conn.close()

        total_exposure = current_collateral + new_collateral
        max_exposure = equity * self.max_portfolio_risk_pct

        if total_exposure > max_exposure:
            return False, (
                f"Portfolio exposure ${total_exposure:.2f} would exceed 20% limit "
                f"(${max_exposure:.2f} on ${equity:.2f} equity)"
            )
        return True, "OK"

    def _check_sector_concentration(self, underlying: str) -> Tuple[bool, str]:
        """Rule 6: Max 3 positions in the same sector."""
        sector = SECTOR_MAP.get(underlying, 'Unknown')
        if sector in ('Index', 'Unknown'):
            return True, "OK"  # Index positions don't count for sector limits

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT underlying FROM option_trades WHERE status = 'open'"
        )
        open_underlyings = [row[0] for row in cursor.fetchall()]
        conn.close()

        same_sector_count = sum(
            1 for u in open_underlyings 
            if SECTOR_MAP.get(u, 'Unknown') == sector
        )

        if same_sector_count >= self.max_same_sector:
            return False, (
                f"Sector concentration: {same_sector_count} positions in {sector} "
                f"(max {self.max_same_sector})"
            )
        return True, "OK"

    def _check_earnings_conflict(
        self, earnings_dates: List[str], expiration_date: str
    ) -> Tuple[bool, str]:
        """Rule 5: Never hold through earnings."""
        exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
        
        for ed in earnings_dates:
            earnings_date = datetime.strptime(ed, '%Y-%m-%d')
            buffer_start = earnings_date - timedelta(days=self.earnings_buffer_days)
            
            if buffer_start <= exp_date <= earnings_date + timedelta(days=1):
                return False, (
                    f"Earnings conflict: earnings on {ed}, "
                    f"option expires {expiration_date} "
                    f"(within {self.earnings_buffer_days}-day buffer)"
                )
        return True, "OK"

    # ──────────────────────────────────────────────────────────────
    # POSITION SIZING
    # ──────────────────────────────────────────────────────────────

    def calculate_position_size(
        self,
        account_equity: float,
        max_loss_per_contract: float,
    ) -> int:
        """
        Calculate the number of contracts to trade.
        
        Formula: contracts = floor(max_risk / max_loss_per_contract)
        Where max_risk = equity × 5%
        """
        max_risk = account_equity * self.max_risk_per_trade_pct
        
        if max_loss_per_contract <= 0:
            return 0
        
        contracts = int(max_risk / max_loss_per_contract)
        return max(contracts, 0)

    def calculate_stop_loss(self, premium_collected: float) -> float:
        """
        Rule 3: The 2:1 Stop Loss.
        If premium collected = $1.00, stop loss when position worth $3.00.
        """
        return round(premium_collected * self.stop_loss_multiplier, 2)

    def calculate_profit_target(self, premium_collected: float) -> float:
        """
        Take profit at 50% of premium collected.
        If collected $1.00, close when position worth $0.50.
        """
        return round(premium_collected * (1 - self.profit_target_pct), 2)

    # ──────────────────────────────────────────────────────────────
    # TRADE TRACKING
    # ──────────────────────────────────────────────────────────────

    def record_trade(self, trade: dict) -> int:
        """Record a new trade in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO option_trades 
            (strategy, symbol, underlying, trade_type, side, quantity,
             entry_price, premium_collected, max_loss, collateral_used,
             stop_loss_price, profit_target_price, entry_date, expiration_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
        ''', (
            trade['strategy'],
            trade['symbol'],
            trade['underlying'],
            trade['trade_type'],
            trade['side'],
            trade['quantity'],
            trade['entry_price'],
            trade['premium_collected'],
            trade['max_loss'],
            trade['collateral_used'],
            trade.get('stop_loss_price', 0),
            trade.get('profit_target_price', 0),
            trade['entry_date'],
            trade.get('expiration_date', ''),
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Trade recorded: ID={trade_id} | {trade['symbol']} | {trade['strategy']}")
        return trade_id

    def close_trade(self, trade_id: int, exit_price: float, pnl: float, notes: str = ''):
        """Close a trade and record P&L."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE option_trades 
            SET status = 'closed', exit_date = ?, exit_price = ?, pnl = ?, notes = ?
            WHERE id = ?
        ''', (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            exit_price,
            pnl,
            notes,
            trade_id,
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Trade closed: ID={trade_id} | P&L=${pnl:.2f} | {notes}")

    def get_open_trades(self, strategy: Optional[str] = None) -> List[dict]:
        """Get all open trades, optionally filtered by strategy."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if strategy:
            cursor.execute(
                "SELECT * FROM option_trades WHERE status = 'open' AND strategy = ?",
                (strategy,)
            )
        else:
            cursor.execute("SELECT * FROM option_trades WHERE status = 'open'")
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades

    def get_performance_summary(self, strategy: Optional[str] = None) -> dict:
        """Get performance statistics for closed trades."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clause = "WHERE status = 'closed'"
        params = ()
        if strategy:
            where_clause += " AND strategy = ?"
            params = (strategy,)

        cursor.execute(
            f"SELECT COUNT(*), SUM(pnl), AVG(pnl) FROM option_trades {where_clause}",
            params
        )
        total, total_pnl, avg_pnl = cursor.fetchone()
        
        cursor.execute(
            f"SELECT COUNT(*) FROM option_trades {where_clause} AND pnl > 0",
            params
        )
        winners = cursor.fetchone()[0]
        
        cursor.execute(
            f"SELECT MIN(pnl) FROM option_trades {where_clause}",
            params
        )
        worst_trade = cursor.fetchone()[0]
        
        cursor.execute(
            f"SELECT MAX(pnl) FROM option_trades {where_clause}",
            params
        )
        best_trade = cursor.fetchone()[0]
        
        conn.close()
        
        total = total or 0
        return {
            'total_trades': total,
            'total_pnl': total_pnl or 0,
            'avg_pnl': avg_pnl or 0,
            'win_rate': (winners / total * 100) if total > 0 else 0,
            'winners': winners or 0,
            'losers': (total - (winners or 0)),
            'best_trade': best_trade or 0,
            'worst_trade': worst_trade or 0,
        }
