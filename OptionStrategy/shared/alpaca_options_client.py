"""
================================================================================
ALPACA OPTIONS CLIENT WRAPPER
================================================================================
Unified wrapper for Alpaca's Options Trading API.
Handles option chain retrieval, order placement, position management,
and smart mid-price execution.

Alpaca Options API Reference:
- Options are available on Alpaca for US-listed equity options
- Options symbols follow OCC format: SYMBOL + YYMMDD + C/P + Strike (8 digits)
  Example: AAPL260320C00150000 = AAPL March 20, 2026 $150 Call
================================================================================
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    LimitOrderRequest,
    GetOrdersRequest,
    ClosePositionRequest,
)
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce,
    OrderType,
    OrderClass,
    QueryOrderStatus,
    AssetClass,
)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    OptionChainRequest,
    OptionLatestQuoteRequest,
    OptionSnapshotRequest,
    StockLatestBarRequest,
)

logger = logging.getLogger('options_strategy')


class AlpacaOptionsClient:
    """
    Wrapper around Alpaca's Options and Trading APIs.
    
    Responsibilities:
    - Retrieve option chains with filtering (delta, DTE, type)
    - Get real-time option quotes and snapshots
    - Place option orders (single legs and multi-leg spreads)
    - Execute smart mid-price limit orders
    - Manage option positions
    """

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.trading_client = TradingClient(api_key, secret_key, paper=paper)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
        self.option_data_client = OptionHistoricalDataClient(api_key, secret_key)
        self.paper = paper
        logger.info(f"AlpacaOptionsClient initialized (paper={paper})")

    # ──────────────────────────────────────────────────────────────
    # ACCOUNT & POSITIONS
    # ──────────────────────────────────────────────────────────────

    def get_account(self):
        """Get account information including buying power and equity."""
        return self.trading_client.get_account()

    def get_buying_power(self) -> float:
        """Get current buying power (cash available for CSPs)."""
        account = self.get_account()
        return float(account.buying_power)

    def get_equity(self) -> float:
        """Get total account equity."""
        account = self.get_account()
        return float(account.equity)

    def get_option_positions(self) -> list:
        """Get all open option positions."""
        positions = self.trading_client.get_all_positions()
        return [p for p in positions if p.asset_class == 'us_option']

    def get_stock_positions(self) -> list:
        """Get all open stock positions (needed for covered calls in Wheel)."""
        positions = self.trading_client.get_all_positions()
        return [p for p in positions if p.asset_class != 'us_option']

    # ──────────────────────────────────────────────────────────────
    # OPTION CHAIN DATA
    # ──────────────────────────────────────────────────────────────

    def get_option_chain(
        self,
        symbol: str,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        strike_price_gte: Optional[float] = None,
        strike_price_lte: Optional[float] = None,
        option_type: Optional[str] = None,  # 'call' or 'put'
    ) -> list:
        """
        Get option chain for a symbol with optional filters.
        
        Args:
            symbol: Underlying stock symbol (e.g., 'AAPL')
            expiration_date_gte: Min expiration (YYYY-MM-DD)
            expiration_date_lte: Max expiration (YYYY-MM-DD)
            strike_price_gte: Min strike price
            strike_price_lte: Max strike price
            option_type: 'call' or 'put'
        
        Returns:
            List of option contracts
        """
        params = {"underlying_symbols": [symbol]}
        
        if expiration_date_gte:
            params["expiration_date_gte"] = expiration_date_gte
        if expiration_date_lte:
            params["expiration_date_lte"] = expiration_date_lte
        if strike_price_gte:
            params["strike_price_gte"] = str(strike_price_gte)
        if strike_price_lte:
            params["strike_price_lte"] = str(strike_price_lte)
        if option_type:
            params["type"] = option_type

        request = OptionChainRequest(**params)
        chain = self.option_data_client.get_option_chain(request)
        return chain

    def get_option_snapshot(self, option_symbols: List[str]) -> dict:
        """
        Get real-time snapshots for option contracts.
        Returns bid, ask, last price, greeks, IV, volume, etc.
        """
        request = OptionSnapshotRequest(symbol_or_symbols=option_symbols)
        return self.option_data_client.get_option_snapshot(request)

    def get_option_quote(self, option_symbol: str) -> dict:
        """Get latest bid/ask quote for a single option."""
        request = OptionLatestQuoteRequest(symbol_or_symbols=[option_symbol])
        return self.option_data_client.get_option_latest_quote(request)

    def get_underlying_price(self, symbol: str) -> float:
        """Get current price of the underlying stock."""
        request = StockLatestBarRequest(symbol_or_symbols=[symbol])
        bars = self.data_client.get_stock_latest_bar(request)
        return float(bars[symbol].close)

    # ──────────────────────────────────────────────────────────────
    # OPTION CONTRACT SELECTION
    # ──────────────────────────────────────────────────────────────

    def find_put_by_delta(
        self,
        symbol: str,
        target_delta: float = 0.15,
        min_dte: int = 30,
        max_dte: int = 45,
        delta_tolerance: float = 0.05,
    ) -> Optional[dict]:
        """
        Find a put option near the target delta within the DTE range.
        
        For SELLING puts: We want delta around -0.10 to -0.15
        (85-90% probability of expiring OTM = profitable for seller)
        
        Args:
            symbol: Underlying symbol
            target_delta: Absolute delta value (e.g., 0.15 for ~85% POP)
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            delta_tolerance: How much delta can deviate from target
        
        Returns:
            Best matching option contract dict or None
        """
        now = datetime.now()
        exp_gte = (now + timedelta(days=min_dte)).strftime('%Y-%m-%d')
        exp_lte = (now + timedelta(days=max_dte)).strftime('%Y-%m-%d')

        chain = self.get_option_chain(
            symbol=symbol,
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
            option_type='put',
        )

        if not chain:
            logger.warning(f"No put options found for {symbol} ({min_dte}-{max_dte} DTE)")
            return None

        # Get snapshots for all contracts to check deltas
        symbols_list = list(chain.keys()) if isinstance(chain, dict) else [c.symbol for c in chain]
        
        if not symbols_list:
            return None

        snapshots = self.get_option_snapshot(symbols_list)
        
        best_match = None
        best_delta_diff = float('inf')

        for sym, snap in snapshots.items():
            if not hasattr(snap, 'greeks') or snap.greeks is None:
                continue
            
            option_delta = abs(float(snap.greeks.delta)) if snap.greeks.delta else 0
            delta_diff = abs(option_delta - target_delta)

            if delta_diff < best_delta_diff and delta_diff <= delta_tolerance:
                best_delta_diff = delta_diff
                best_match = {
                    'symbol': sym,
                    'delta': float(snap.greeks.delta) if snap.greeks.delta else 0,
                    'gamma': float(snap.greeks.gamma) if snap.greeks.gamma else 0,
                    'theta': float(snap.greeks.theta) if snap.greeks.theta else 0,
                    'vega': float(snap.greeks.vega) if snap.greeks.vega else 0,
                    'iv': float(snap.implied_volatility) if snap.implied_volatility else 0,
                    'bid': float(snap.latest_quote.bid_price) if snap.latest_quote else 0,
                    'ask': float(snap.latest_quote.ask_price) if snap.latest_quote else 0,
                    'mid': 0,
                    'underlying': symbol,
                }
                if best_match['bid'] and best_match['ask']:
                    best_match['mid'] = round((best_match['bid'] + best_match['ask']) / 2, 2)

        if best_match:
            logger.info(
                f"Found put for {symbol}: {best_match['symbol']} | "
                f"Delta={best_match['delta']:.3f} | Mid=${best_match['mid']:.2f}"
            )
        return best_match

    def find_call_by_delta(
        self,
        symbol: str,
        target_delta: float = 0.30,
        min_dte: int = 30,
        max_dte: int = 45,
        delta_tolerance: float = 0.05,
    ) -> Optional[dict]:
        """
        Find a call option near the target delta within the DTE range.
        
        For SELLING covered calls: delta ~0.25–0.35 is typical
        (gives upside room while collecting decent premium)
        """
        now = datetime.now()
        exp_gte = (now + timedelta(days=min_dte)).strftime('%Y-%m-%d')
        exp_lte = (now + timedelta(days=max_dte)).strftime('%Y-%m-%d')

        chain = self.get_option_chain(
            symbol=symbol,
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
            option_type='call',
        )

        if not chain:
            logger.warning(f"No call options found for {symbol} ({min_dte}-{max_dte} DTE)")
            return None

        symbols_list = list(chain.keys()) if isinstance(chain, dict) else [c.symbol for c in chain]
        
        if not symbols_list:
            return None

        snapshots = self.get_option_snapshot(symbols_list)
        
        best_match = None
        best_delta_diff = float('inf')

        for sym, snap in snapshots.items():
            if not hasattr(snap, 'greeks') or snap.greeks is None:
                continue
            
            option_delta = abs(float(snap.greeks.delta)) if snap.greeks.delta else 0
            delta_diff = abs(option_delta - target_delta)

            if delta_diff < best_delta_diff and delta_diff <= delta_tolerance:
                best_delta_diff = delta_diff
                best_match = {
                    'symbol': sym,
                    'delta': float(snap.greeks.delta) if snap.greeks.delta else 0,
                    'gamma': float(snap.greeks.gamma) if snap.greeks.gamma else 0,
                    'theta': float(snap.greeks.theta) if snap.greeks.theta else 0,
                    'vega': float(snap.greeks.vega) if snap.greeks.vega else 0,
                    'iv': float(snap.implied_volatility) if snap.implied_volatility else 0,
                    'bid': float(snap.latest_quote.bid_price) if snap.latest_quote else 0,
                    'ask': float(snap.latest_quote.ask_price) if snap.latest_quote else 0,
                    'mid': 0,
                    'underlying': symbol,
                }
                if best_match['bid'] and best_match['ask']:
                    best_match['mid'] = round((best_match['bid'] + best_match['ask']) / 2, 2)

        if best_match:
            logger.info(
                f"Found call for {symbol}: {best_match['symbol']} | "
                f"Delta={best_match['delta']:.3f} | Mid=${best_match['mid']:.2f}"
            )
        return best_match

    def find_spread_contracts(
        self,
        symbol: str,
        spread_type: str,  # 'bull_put' or 'bear_call'
        target_delta: float = 0.10,
        spread_width: float = 5.0,
        min_dte: int = 30,
        max_dte: int = 45,
    ) -> Optional[Dict]:
        """
        Find contracts for a vertical spread.
        
        Bull Put Spread (credit): Sell higher strike put, buy lower strike put
        Bear Call Spread (credit): Sell lower strike call, buy higher strike call
        
        Args:
            symbol: Underlying symbol
            spread_type: 'bull_put' or 'bear_call'
            target_delta: Delta for the short leg
            spread_width: Distance between strikes in dollars
            min_dte/max_dte: Days to expiration range
        
        Returns:
            Dict with 'short_leg' and 'long_leg' contract info, or None
        """
        option_type = 'put' if spread_type == 'bull_put' else 'call'
        
        # Find the short leg
        if option_type == 'put':
            short_leg = self.find_put_by_delta(symbol, target_delta, min_dte, max_dte)
        else:
            short_leg = self.find_call_by_delta(symbol, target_delta, min_dte, max_dte)
        
        if not short_leg:
            return None

        # Parse the short leg's strike from the OCC symbol
        # OCC format: SYMBOL + YYMMDD + C/P + StrikePrice (8 digits, 5.3 format)
        short_symbol = short_leg['symbol']
        
        # Determine the long leg strike
        # For bull put: long leg is LOWER strike
        # For bear call: long leg is HIGHER strike
        now = datetime.now()
        exp_gte = (now + timedelta(days=min_dte)).strftime('%Y-%m-%d')
        exp_lte = (now + timedelta(days=max_dte)).strftime('%Y-%m-%d')

        # Get the full chain to find the matching long leg
        chain = self.get_option_chain(
            symbol=symbol,
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
            option_type=option_type,
        )

        if not chain:
            return None

        # Get snapshots with quotes
        symbols_list = list(chain.keys()) if isinstance(chain, dict) else [c.symbol for c in chain]
        snapshots = self.get_option_snapshot(symbols_list)

        # Find the long leg (further OTM)
        best_long = None
        
        for sym, snap in snapshots.items():
            if sym == short_symbol:
                continue
            if not hasattr(snap, 'greeks') or snap.greeks is None:
                continue
            
            snap_delta = abs(float(snap.greeks.delta)) if snap.greeks.delta else 0
            
            # Long leg should be further OTM (lower delta) than short leg
            if snap_delta < abs(short_leg['delta']) - 0.02:
                bid = float(snap.latest_quote.bid_price) if snap.latest_quote else 0
                ask = float(snap.latest_quote.ask_price) if snap.latest_quote else 0
                
                long_candidate = {
                    'symbol': sym,
                    'delta': float(snap.greeks.delta) if snap.greeks.delta else 0,
                    'bid': bid,
                    'ask': ask,
                    'mid': round((bid + ask) / 2, 2) if bid and ask else 0,
                }
                
                if best_long is None or abs(snap_delta) > abs(best_long['delta']):
                    # Prefer the option closest to but still OTM of the short
                    best_long = long_candidate

        if not best_long:
            logger.warning(f"Could not find long leg for {spread_type} spread on {symbol}")
            return None

        # Calculate spread credit
        net_credit = round(short_leg['mid'] - best_long['mid'], 2)

        spread = {
            'type': spread_type,
            'underlying': symbol,
            'short_leg': short_leg,
            'long_leg': best_long,
            'net_credit': net_credit,
            'max_loss': round(spread_width - net_credit, 2),
            'spread_width': spread_width,
        }

        logger.info(
            f"Spread found: {spread_type} on {symbol} | "
            f"Credit=${net_credit:.2f} | MaxLoss=${spread['max_loss']:.2f}"
        )
        return spread

    # ──────────────────────────────────────────────────────────────
    # ORDER EXECUTION
    # ──────────────────────────────────────────────────────────────

    def sell_to_open(
        self,
        option_symbol: str,
        qty: int,
        limit_price: float,
        time_in_force: TimeInForce = TimeInForce.DAY,
    ) -> Optional[object]:
        """
        Sell to open an option contract (collect premium).
        Used for: Selling CSPs, selling covered calls, short legs of spreads.
        """
        order_request = LimitOrderRequest(
            symbol=option_symbol,
            qty=qty,
            side=OrderSide.SELL,
            type=OrderType.LIMIT,
            time_in_force=time_in_force,
            limit_price=limit_price,
        )

        try:
            order = self.trading_client.submit_order(order_request)
            logger.info(
                f"SELL TO OPEN: {option_symbol} x{qty} @ ${limit_price:.2f} | "
                f"Order ID: {order.id}"
            )
            return order
        except Exception as e:
            logger.error(f"Failed to sell to open {option_symbol}: {e}")
            return None

    def buy_to_close(
        self,
        option_symbol: str,
        qty: int,
        limit_price: float,
        time_in_force: TimeInForce = TimeInForce.DAY,
    ) -> Optional[object]:
        """
        Buy to close an option position (exit short position).
        """
        order_request = LimitOrderRequest(
            symbol=option_symbol,
            qty=qty,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            time_in_force=time_in_force,
            limit_price=limit_price,
        )

        try:
            order = self.trading_client.submit_order(order_request)
            logger.info(
                f"BUY TO CLOSE: {option_symbol} x{qty} @ ${limit_price:.2f} | "
                f"Order ID: {order.id}"
            )
            return order
        except Exception as e:
            logger.error(f"Failed to buy to close {option_symbol}: {e}")
            return None

    def buy_to_open(
        self,
        option_symbol: str,
        qty: int,
        limit_price: float,
        time_in_force: TimeInForce = TimeInForce.DAY,
    ) -> Optional[object]:
        """
        Buy to open an option contract (pay premium for protection/long leg).
        Used for: Long legs of spreads.
        """
        order_request = LimitOrderRequest(
            symbol=option_symbol,
            qty=qty,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            time_in_force=time_in_force,
            limit_price=limit_price,
        )

        try:
            order = self.trading_client.submit_order(order_request)
            logger.info(
                f"BUY TO OPEN: {option_symbol} x{qty} @ ${limit_price:.2f} | "
                f"Order ID: {order.id}"
            )
            return order
        except Exception as e:
            logger.error(f"Failed to buy to open {option_symbol}: {e}")
            return None

    def place_spread_order(
        self,
        short_symbol: str,
        long_symbol: str,
        qty: int,
        net_credit: float,
    ) -> Optional[object]:
        """
        Place a multi-leg spread order.
        Sells the short leg and buys the long leg simultaneously.
        
        Note: Alpaca supports multi-leg options orders via their API.
        The net_credit is the total credit received for the spread.
        """
        try:
            # Place as two separate orders if multi-leg not available
            # In production, use Alpaca's multi-leg order if supported
            sell_order = self.sell_to_open(short_symbol, qty, net_credit)
            if sell_order:
                # Get the long leg price (should be cheaper)
                quote = self.get_option_quote(long_symbol)
                if quote and long_symbol in quote:
                    ask = float(quote[long_symbol].ask_price)
                    buy_order = self.buy_to_open(long_symbol, qty, ask)
                    
                    return {
                        'sell_order': sell_order,
                        'buy_order': buy_order,
                        'net_credit': net_credit,
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to place spread order: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # SMART MID-PRICE EXECUTION
    # ──────────────────────────────────────────────────────────────

    def execute_at_mid_price(
        self,
        option_symbol: str,
        qty: int,
        side: str,  # 'sell' or 'buy'
        max_retries: int = 10,
        increment: float = 0.01,
        retry_seconds: int = 30,
    ) -> Optional[object]:
        """
        Smart mid-price execution engine.
        
        Logic:
        1. Get bid/ask for the option
        2. Place limit order at mid-price
        3. If not filled in retry_seconds, cancel and adjust by increment
        4. Repeat up to max_retries times
        
        This prevents paying the full spread (bid-ask) and saves 
        significant money over time.
        """
        for attempt in range(max_retries):
            # Get current quote
            quote_data = self.get_option_quote(option_symbol)
            if not quote_data or option_symbol not in quote_data:
                logger.warning(f"Could not get quote for {option_symbol}")
                return None

            quote = quote_data[option_symbol]
            bid = float(quote.bid_price) if quote.bid_price else 0
            ask = float(quote.ask_price) if quote.ask_price else 0

            if bid == 0 or ask == 0:
                logger.warning(f"Invalid bid/ask for {option_symbol}: bid={bid}, ask={ask}")
                return None

            mid = round((bid + ask) / 2, 2)

            # Adjust price based on attempt number
            if side == 'sell':
                # Start at mid, then decrease toward bid
                price = round(mid - (attempt * increment), 2)
                price = max(price, bid)  # Don't go below bid
                order = self.sell_to_open(option_symbol, qty, price)
            else:
                # Start at mid, then increase toward ask
                price = round(mid + (attempt * increment), 2)
                price = min(price, ask)  # Don't go above ask
                order = self.buy_to_close(option_symbol, qty, price)

            if not order:
                continue

            logger.info(
                f"Mid-price attempt {attempt + 1}/{max_retries}: "
                f"{side.upper()} {option_symbol} @ ${price:.2f} "
                f"(bid=${bid:.2f}, ask=${ask:.2f}, mid=${mid:.2f})"
            )

            # Wait and check if filled
            time.sleep(retry_seconds)

            try:
                updated_order = self.trading_client.get_order_by_id(order.id)
                if updated_order.status == 'filled':
                    logger.info(f"Order FILLED at ${updated_order.filled_avg_price}")
                    return updated_order
                else:
                    # Cancel and retry with adjusted price
                    self.trading_client.cancel_order_by_id(order.id)
                    logger.info(f"Order not filled, cancelling and adjusting price...")
            except Exception as e:
                logger.error(f"Error checking order status: {e}")

        logger.warning(f"Failed to fill order after {max_retries} attempts")
        return None

    # ──────────────────────────────────────────────────────────────
    # ORDER MANAGEMENT
    # ──────────────────────────────────────────────────────────────

    def get_open_orders(self) -> list:
        """Get all open/pending orders."""
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        return self.trading_client.get_orders(request)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order."""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[object]:
        """Get the status of a specific order."""
        try:
            return self.trading_client.get_order_by_id(order_id)
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
