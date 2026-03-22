"""
================================================================================
THE WHEEL PREMIUM ENGINE — Automated Trading Bot
================================================================================

Strategy: Sell Cash-Secured Puts → If Assigned, Sell Covered Calls → Repeat

This bot:
1. Scans a watchlist for CSP (Cash-Secured Put) opportunities
2. Filters by Delta, IV Rank, DTE, and annualized return
3. Passes trades through the Risk Manager (5% rule, sector limits, etc.)
4. Executes orders at mid-price for best fills
5. Monitors open positions for exit signals (50% profit, stop loss, time)
6. Detects assignment and auto-switches to covered call selling
7. Tracks all trades in SQLite database for performance analysis

Usage:
    python wheel_bot.py              # Run in paper trading mode
    python wheel_bot.py --dry-run    # Show what would happen without placing orders
    python wheel_bot.py --config my_config.json  # Use custom config

================================================================================
"""

import os
import sys
import json
import time
import argparse
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import pytz

# Add parent directory for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.alpaca_options_client import AlpacaOptionsClient
from shared.risk_manager import RiskManager
from shared.option_utils import (
    annualized_return,
    calculate_dte,
    calculate_iv_rank,
    probability_of_profit_put,
)
from shared.earnings_calendar import EarningsCalendar
from shared.logger import setup_logger
from ladder_exit import LadderExitManager


class WheelBot:
    """
    The Wheel Premium Engine — automated CSP + CC income strategy.
    
    Phases:
        A. Sell Cash-Secured Puts on watchlist stocks
        B. If assigned, sell Covered Calls on held stock
        C. If called away, return to Phase A
    """

    def __init__(self, config_path: str = 'config.json', dry_run: bool = False):
        self.dry_run = dry_run
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Setup logging
        log_dir = self.config.get('logging', {}).get('log_dir', 'logs')
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        self.logger = setup_logger('wheel_strategy', log_dir, log_level)

        # Load API keys from environment or config
        api_key = os.environ.get('ALPACA_API_KEY', self.config['api']['key_id']) if 'api' in self.config else os.environ.get('ALPACA_API_KEY', '')
        secret_key = os.environ.get('ALPACA_SECRET_KEY', self.config['api']['secret_key']) if 'api' in self.config else os.environ.get('ALPACA_SECRET_KEY', '')
        base_url = self.config.get('api', {}).get('base_url', 'https://paper-api.alpaca.markets')
        is_paper = 'paper' in base_url

        if not api_key or not secret_key:
            # Try loading from parent config
            parent_config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config', 'config.json'
            )
            if os.path.exists(parent_config_path):
                with open(parent_config_path, 'r') as f:
                    parent_config = json.load(f)
                api_key = parent_config['api']['key_id']
                secret_key = parent_config['api']['secret_key']
                base_url = parent_config['api']['base_url']
                is_paper = 'paper' in base_url

        if not api_key or not secret_key:
            self.logger.error("No API keys found. Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables or configure in config.json")
            sys.exit(1)

        # Initialize clients
        self.client = AlpacaOptionsClient(api_key, secret_key, paper=is_paper)
        
        # Risk manager (uses parent config path for DB)
        db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db')
        os.makedirs(db_dir, exist_ok=True)
        self.risk_manager = RiskManager(
            self.config.get('risk', {}),
            db_path=os.path.join(db_dir, 'wheel_trades.db')
        )

        # Earnings calendar
        manual_dates = self.config.get('earnings_dates_manual', {})
        self.earnings = EarningsCalendar(manual_dates=manual_dates)

        # Strategy parameters
        self.watchlist = self.config.get('watchlist', [])
        self.csp = self.config.get('csp_rules', {})
        self.cc = self.config.get('cc_rules', {})
        self.execution = self.config.get('execution', {})

        # State tracking
        self.wheel_phase = {}  # {symbol: 'A' or 'B'}

        # Ladder exit manager for tiered profit-taking
        ladder_state = os.path.join(db_dir, 'ladder_state.json')
        self.ladder = LadderExitManager(
            state_file=ladder_state,
            logger=self.logger,
        )

        self.logger.info("=" * 70)
        self.logger.info("WHEEL PREMIUM ENGINE v1.0 — INITIALIZED")
        self.logger.info(f"Mode: {'DRY RUN' if dry_run else ('PAPER' if is_paper else 'LIVE')}")
        self.logger.info(f"Watchlist: {', '.join(self.watchlist)}")
        self.logger.info(f"CSP Delta: {self.csp.get('target_delta', 0.15)}")
        self.logger.info(f"CC Delta: {self.cc.get('target_delta', 0.30)}")
        self.logger.info("=" * 70)

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self):
        """Main bot loop — runs continuously during market hours."""
        self.logger.info("Starting Wheel Premium Engine main loop...")
        scan_interval = self.execution.get('scan_interval_minutes', 5) * 60

        while True:
            try:
                if not self._is_market_hours():
                    self.logger.info("Market closed. Sleeping 60 seconds...")
                    time.sleep(60)
                    continue

                self._run_cycle()
                
                self.logger.info(f"Cycle complete. Next scan in {scan_interval // 60} minutes.")
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user.")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)  # Wait before retrying

    def _run_cycle(self):
        """Single cycle: check exits, then hunt for new entries."""
        account_equity = self.client.get_equity()
        self.logger.info(f"Account Equity: ${account_equity:,.2f}")

        # Phase 1: Guardian — Monitor existing positions
        self._guardian_check_exits()

        # Phase 2: Check for assignments (CSP → CC transition)
        self._check_for_assignments()

        # Phase 3: Hunter — Look for new CSP opportunities
        self._hunter_scan_for_csps(account_equity)

        # Phase 4: Hunter — Look for CC opportunities on held stock
        self._hunter_scan_for_ccs(account_equity)

        # Log summary
        self._log_portfolio_summary()

    # ──────────────────────────────────────────────────────────────
    # GUARDIAN: POSITION MANAGEMENT
    # ──────────────────────────────────────────────────────────────

    def _guardian_check_exits(self):
        """Check all open option positions for exit conditions using ladder exit manager."""
        open_trades = self.risk_manager.get_open_trades(strategy='wheel_csp')
        open_trades += self.risk_manager.get_open_trades(strategy='wheel_cc')

        for trade in open_trades:
            symbol = trade['symbol']
            premium_collected = trade['premium_collected']
            
            # Get current option price
            try:
                quote = self.client.get_option_quote(symbol)
                if not quote or symbol not in quote:
                    continue
                
                current_bid = float(quote[symbol].bid_price) if quote[symbol].bid_price else 0
                current_ask = float(quote[symbol].ask_price) if quote[symbol].ask_price else 0
                current_mid = round((current_bid + current_ask) / 2, 2)
            except Exception as e:
                self.logger.error(f"Error getting quote for {symbol}: {e}")
                continue

            # Register with ladder if not already tracked
            pos_key = f"{trade['id']}_{symbol}"
            if not self.ladder.is_registered(pos_key):
                self.ladder.register_position(
                    pos_key, premium_collected, trade['quantity'], side='short'
                )

            # Time Exit: always check DTE regardless of ladder
            max_dte = self.csp.get('max_dte_to_hold', 21)
            if trade.get('expiration_date'):
                remaining_dte = calculate_dte(trade['expiration_date'][:10])
                if remaining_dte <= max_dte:
                    pnl = (premium_collected - current_mid) * 100 * trade['quantity']
                    self.logger.info(
                        f"TIME EXIT: {trade['underlying']} | {symbol} | "
                        f"{remaining_dte} DTE remaining | P&L: ${pnl:.2f}"
                    )
                    self._close_position(trade, current_mid, pnl, f"Time exit ({remaining_dte} DTE)")
                    self.ladder.remove_position(pos_key)
                    continue

            # Ladder exit check
            result = self.ladder.check_exit(pos_key, current_mid)

            if result['action'] == 'stop_loss':
                pnl = (premium_collected - current_mid) * 100 * result['contracts_to_sell']
                self.logger.warning(
                    f"LADDER STOP: {trade['underlying']} | {symbol} | {result['reason']}"
                )
                self._close_position(trade, current_mid, pnl, f"Ladder stop: {result['tier']}")
                self.ladder.remove_position(pos_key)

            elif result['action'] in ('sell_partial', 'sell_all'):
                qty = result['contracts_to_sell']
                pnl = (premium_collected - current_mid) * 100 * qty
                self.logger.info(
                    f"LADDER EXIT: {trade['underlying']} | {symbol} | "
                    f"{result['reason']} | P&L: ${pnl:.2f}"
                )
                self._close_partial(trade, current_mid, qty, pnl, result['reason'])
                self.ladder.confirm_sell(pos_key, qty, current_mid)

            else:
                pnl_pct = result['profit_pct']
                self.logger.info(
                    f"HOLD: {trade['underlying']} | {symbol} | "
                    f"P&L: {pnl_pct:+.1%} | SL: ${result['stop_loss']:.2f} | "
                    f"Tier: {result['tier']} | Mid: ${current_mid:.2f}"
                )

    def _close_position(self, trade: dict, exit_price: float, pnl: float, reason: str):
        """Close an option position (all contracts)."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would close {trade['symbol']} | Reason: {reason}")
            return

        qty = trade['quantity']
        order = self.client.buy_to_close(trade['symbol'], qty, exit_price)
        
        if order:
            self.risk_manager.close_trade(trade['id'], exit_price, pnl, reason)
        else:
            self.logger.error(f"Failed to close position {trade['symbol']}")

    def _close_partial(self, trade: dict, exit_price: float, qty: int,
                       pnl: float, reason: str):
        """Close a partial number of contracts from a position."""
        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would close {qty} of {trade['quantity']} contracts "
                f"on {trade['symbol']} | Reason: {reason}"
            )
            return

        order = self.client.buy_to_close(trade['symbol'], qty, exit_price)
        if order:
            # Record partial P&L; trade stays open with fewer contracts
            self.risk_manager.close_trade(trade['id'], exit_price, pnl, f"Partial: {reason}")
        else:
            self.logger.error(f"Failed to partially close {trade['symbol']}")

    # ──────────────────────────────────────────────────────────────
    # ASSIGNMENT DETECTION
    # ──────────────────────────────────────────────────────────────

    def _check_for_assignments(self):
        """
        Check if any CSPs have been assigned (we now own the stock).
        If so, transition to Phase B (covered calls).
        """
        stock_positions = self.client.get_stock_positions()
        
        for pos in stock_positions:
            symbol = pos.symbol
            qty = int(pos.qty)
            
            # Check if this stock is in our wheel watchlist
            if symbol not in self.watchlist:
                continue
            
            # Check if we have an open CSP trade for this symbol
            open_csp_trades = [
                t for t in self.risk_manager.get_open_trades(strategy='wheel_csp')
                if t['underlying'] == symbol
            ]
            
            if open_csp_trades and qty >= 100:
                self.logger.info(
                    f"ASSIGNMENT DETECTED: {symbol} | "
                    f"{qty} shares owned | Switching to Phase B (Covered Calls)"
                )
                self.wheel_phase[symbol] = 'B'
                
                # Close the CSP trade record
                for csp_trade in open_csp_trades:
                    self.risk_manager.close_trade(
                        csp_trade['id'], 0, 
                        csp_trade['premium_collected'] * 100,  # Keep the full premium
                        "Assigned — transitioning to covered calls"
                    )

    # ──────────────────────────────────────────────────────────────
    # HUNTER: NEW CSP OPPORTUNITIES
    # ──────────────────────────────────────────────────────────────

    def _hunter_scan_for_csps(self, account_equity: float):
        """Scan watchlist for new Cash-Secured Put opportunities."""
        open_trades = self.risk_manager.get_open_trades()
        
        # Check if we can open new positions
        max_positions = self.config.get('risk', {}).get('max_total_positions', 5)
        if len(open_trades) >= max_positions:
            self.logger.info(f"Max positions reached ({len(open_trades)}/{max_positions}). No new CSPs.")
            return

        # Stocks already in Phase B shouldn't get new CSPs
        stocks_in_phase_b = {s for s, p in self.wheel_phase.items() if p == 'B'}
        stocks_with_open_trades = {t['underlying'] for t in open_trades}

        self.logger.info("--- Hunter: Scanning for CSP opportunities ---")

        for symbol in self.watchlist:
            if symbol in stocks_with_open_trades:
                continue
            if symbol in stocks_in_phase_b:
                continue

            try:
                self._evaluate_csp(symbol, account_equity)
            except Exception as e:
                self.logger.error(f"Error evaluating {symbol}: {e}")

    def _evaluate_csp(self, symbol: str, account_equity: float):
        """Evaluate a specific stock for a CSP trade."""
        # Check earnings
        if self.earnings.has_earnings_within(symbol, self.csp.get('min_dte', 30)):
            self.logger.info(f"SKIP {symbol}: Earnings within DTE window")
            return

        # Find put option at target delta
        put = self.client.find_put_by_delta(
            symbol=symbol,
            target_delta=self.csp.get('target_delta', 0.15),
            min_dte=self.csp.get('min_dte', 30),
            max_dte=self.csp.get('max_dte', 45),
            delta_tolerance=self.csp.get('delta_tolerance', 0.05),
        )

        if not put:
            self.logger.info(f"SKIP {symbol}: No suitable put found")
            return

        premium = put['mid']
        if premium <= 0:
            self.logger.info(f"SKIP {symbol}: No premium (mid=${premium:.2f})")
            return

        # Get strike from OCC symbol parsing
        underlying_price = self.client.get_underlying_price(symbol)
        
        # Approximate strike from delta and price
        # For a -0.15 delta put, strike is roughly at price × (1 - some %)
        # We'll use the premium and underlying price for collateral calculation
        # In reality, the strike comes from the option chain
        from shared.option_utils import parse_occ_symbol
        parsed = parse_occ_symbol(put['symbol'])
        strike = parsed['strike'] if parsed else underlying_price * 0.9
        expiration = parsed['expiration'] if parsed else ''
        
        dte = calculate_dte(expiration) if expiration else 35
        
        # Calculate collateral required (strike × 100 per contract)
        collateral = strike * 100

        # Check minimum annualized return
        ann_return = annualized_return(premium, strike, dte)
        min_return = self.csp.get('min_annualized_return_pct', 15)
        if ann_return < min_return:
            self.logger.info(
                f"SKIP {symbol}: Annualized return {ann_return:.1f}% < {min_return}% minimum"
            )
            return

        # Calculate max loss for risk check
        stop_mult = self.csp.get('stop_loss_multiplier', 3.0)
        max_loss = premium * stop_mult * 100  # Per contract, with stop loss

        # Risk manager approval
        earnings_dates = self.earnings.get_earnings_dates(symbol)
        approved, reason = self.risk_manager.approve_trade(
            symbol=put['symbol'],
            underlying=symbol,
            trade_type='csp',
            max_loss=max_loss,
            collateral_required=collateral,
            account_equity=account_equity,
            earnings_dates=earnings_dates,
            expiration_date=expiration,
        )

        if not approved:
            self.logger.info(f"REJECTED {symbol}: {reason}")
            return

        # Calculate position size
        contracts = self.risk_manager.calculate_position_size(account_equity, max_loss)
        if contracts < 1:
            self.logger.info(f"SKIP {symbol}: Position size too small (0 contracts)")
            return
        contracts = 1  # Start conservative with 1 contract

        # POP calculation
        pop = probability_of_profit_put(
            underlying_price, strike, premium, put.get('iv', 0.3), dte
        )

        self.logger.info(
            f"OPPORTUNITY: {symbol} | Strike=${strike:.2f} | Premium=${premium:.2f} | "
            f"Delta={put['delta']:.3f} | DTE={dte} | POP={pop:.1f}% | "
            f"Annual={ann_return:.1f}% | Contracts={contracts}"
        )

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would sell {contracts} CSP on {symbol}")
            return

        # Execute the trade
        if self.execution.get('use_mid_price', True):
            order = self.client.execute_at_mid_price(
                put['symbol'], contracts, 'sell',
                max_retries=self.execution.get('mid_price_max_retries', 10),
                increment=self.execution.get('mid_price_increment', 0.01),
                retry_seconds=self.execution.get('mid_price_retry_seconds', 30),
            )
        else:
            order = self.client.sell_to_open(put['symbol'], contracts, put['bid'])

        if order:
            filled_price = float(order.filled_avg_price) if hasattr(order, 'filled_avg_price') and order.filled_avg_price else premium
            
            # Record trade
            self.risk_manager.record_trade({
                'strategy': 'wheel_csp',
                'symbol': put['symbol'],
                'underlying': symbol,
                'trade_type': 'csp',
                'side': 'sell',
                'quantity': contracts,
                'entry_price': filled_price,
                'premium_collected': filled_price,
                'max_loss': max_loss,
                'collateral_used': collateral * contracts,
                'stop_loss_price': self.risk_manager.calculate_stop_loss(filled_price),
                'profit_target_price': self.risk_manager.calculate_profit_target(filled_price),
                'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiration_date': expiration,
            })

            self.wheel_phase[symbol] = 'A'
            self.logger.info(f"CSP OPENED: {symbol} | {put['symbol']} @ ${filled_price:.2f}")

    # ──────────────────────────────────────────────────────────────
    # HUNTER: COVERED CALL OPPORTUNITIES
    # ──────────────────────────────────────────────────────────────

    def _hunter_scan_for_ccs(self, account_equity: float):
        """Scan for covered call opportunities on stocks we own (Phase B)."""
        stock_positions = self.client.get_stock_positions()

        for pos in stock_positions:
            symbol = pos.symbol
            qty = int(pos.qty)

            if symbol not in self.watchlist:
                continue
            if qty < 100:
                continue

            # Check if we already have an open CC on this stock
            open_cc_trades = [
                t for t in self.risk_manager.get_open_trades(strategy='wheel_cc')
                if t['underlying'] == symbol
            ]
            if open_cc_trades:
                continue

            # Check earnings
            if self.earnings.has_earnings_within(symbol, self.cc.get('min_dte', 30)):
                self.logger.info(f"SKIP CC on {symbol}: Earnings within DTE window")
                continue

            try:
                self._evaluate_cc(symbol, account_equity, pos)
            except Exception as e:
                self.logger.error(f"Error evaluating CC for {symbol}: {e}")

    def _evaluate_cc(self, symbol: str, account_equity: float, stock_position):
        """Evaluate a covered call opportunity on a held stock."""
        call = self.client.find_call_by_delta(
            symbol=symbol,
            target_delta=self.cc.get('target_delta', 0.30),
            min_dte=self.cc.get('min_dte', 30),
            max_dte=self.cc.get('max_dte', 45),
            delta_tolerance=self.cc.get('delta_tolerance', 0.05),
        )

        if not call:
            self.logger.info(f"SKIP CC {symbol}: No suitable call found")
            return

        premium = call['mid']
        if premium <= 0:
            return

        from shared.option_utils import parse_occ_symbol
        parsed = parse_occ_symbol(call['symbol'])
        strike = parsed['strike'] if parsed else 0
        expiration = parsed['expiration'] if parsed else ''
        dte = calculate_dte(expiration) if expiration else 35

        # Check if strike is above cost basis (optional safety)
        cost_basis = float(stock_position.avg_entry_price)
        if self.cc.get('sell_above_cost_basis', True) and strike < cost_basis:
            self.logger.info(
                f"SKIP CC {symbol}: Strike ${strike:.2f} below cost basis ${cost_basis:.2f}"
            )
            return

        contracts = int(int(stock_position.qty) / 100)

        ann_return_val = annualized_return(premium, float(stock_position.market_value) / contracts / 100, dte)

        self.logger.info(
            f"CC OPPORTUNITY: {symbol} | Strike=${strike:.2f} | Premium=${premium:.2f} | "
            f"Delta={call['delta']:.3f} | DTE={dte} | Annual={ann_return_val:.1f}%"
        )

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would sell {contracts} CC on {symbol}")
            return

        order = self.client.sell_to_open(call['symbol'], contracts, premium)
        
        if order:
            filled_price = float(order.filled_avg_price) if hasattr(order, 'filled_avg_price') and order.filled_avg_price else premium
            
            self.risk_manager.record_trade({
                'strategy': 'wheel_cc',
                'symbol': call['symbol'],
                'underlying': symbol,
                'trade_type': 'cc',
                'side': 'sell',
                'quantity': contracts,
                'entry_price': filled_price,
                'premium_collected': filled_price,
                'max_loss': 0,  # CC risk is limited to opportunity cost
                'collateral_used': 0,  # Stock already owned
                'stop_loss_price': self.risk_manager.calculate_stop_loss(filled_price),
                'profit_target_price': self.risk_manager.calculate_profit_target(filled_price),
                'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiration_date': expiration,
            })

            self.logger.info(f"CC OPENED: {symbol} | {call['symbol']} @ ${filled_price:.2f}")

    # ──────────────────────────────────────────────────────────────
    # UTILITIES
    # ──────────────────────────────────────────────────────────────

    def _is_market_hours(self) -> bool:
        """Check if we're within trading hours (9:30 AM - 4:00 PM ET)."""
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        if now.weekday() > 4:  # Weekend
            return False
        
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Apply delays
        open_delay = self.execution.get('market_open_delay_minutes', 30)
        close_buffer = self.execution.get('market_close_buffer_minutes', 15)
        
        effective_open = market_open + timedelta(minutes=open_delay)
        effective_close = market_close - timedelta(minutes=close_buffer)
        
        return effective_open <= now <= effective_close

    def _log_portfolio_summary(self):
        """Log a summary of current portfolio state."""
        summary = self.risk_manager.get_performance_summary(strategy='wheel_csp')
        cc_summary = self.risk_manager.get_performance_summary(strategy='wheel_cc')
        
        open_count = len(self.risk_manager.get_open_trades())
        
        self.logger.info("--- Portfolio Summary ---")
        self.logger.info(f"Open Positions: {open_count}")
        self.logger.info(
            f"CSP: {summary['total_trades']} trades | "
            f"Win Rate: {summary['win_rate']:.1f}% | "
            f"Total P&L: ${summary['total_pnl']:.2f}"
        )
        self.logger.info(
            f" CC: {cc_summary['total_trades']} trades | "
            f"Win Rate: {cc_summary['win_rate']:.1f}% | "
            f"Total P&L: ${cc_summary['total_pnl']:.2f}"
        )


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Wheel Premium Engine Bot')
    parser.add_argument('--config', default='config.json', help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no real orders)')
    args = parser.parse_args()

    bot = WheelBot(config_path=args.config, dry_run=args.dry_run)
    bot.run()


if __name__ == '__main__':
    main()
