"""
================================================================================
IRON CONDOR INCOME MACHINE — Automated Trading Bot
================================================================================

Strategy: Sell Iron Condors (Put Spread + Call Spread) on liquid ETFs/Indices.
Profits when the underlying stays within a price range.

This bot:
1. Scans watchlist for iron condor opportunities (IVR > 30)
2. Finds put & call spreads at target deltas
3. Verifies 1/3 credit rule (credit ≥ wing_width / 3)
4. Monitors positions for profit targets, stop losses, and side breaches
5. Manages tested sides independently (close one side if breached)
6. Tracks all trades in SQLite for performance analysis

KEY RULES:
- Both sides at 0.10-0.15 Delta
- Total credit ≥ 33% of wing width
- Exit at 50% profit or 21 DTE
- Close tested side at delta > 0.40
- Stop loss at 2× total credit

Usage:
    python iron_condor_bot.py              # Paper trading
    python iron_condor_bot.py --dry-run    # Preview mode
    python iron_condor_bot.py --symbol IWM # Specific underlying

================================================================================
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta

import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.alpaca_options_client import AlpacaOptionsClient
from shared.risk_manager import RiskManager
from shared.option_utils import (
    calculate_dte,
    calculate_iv_rank,
    annualized_return,
    parse_occ_symbol,
)
from shared.earnings_calendar import EarningsCalendar
from shared.logger import setup_logger
from ladder_exit import LadderExitManager


class IronCondorBot:
    """
    Iron Condor Income Machine — automated range-bound income strategy.
    
    Sells both a put spread and call spread simultaneously.
    Profits when the underlying stays within the short strikes.
    """

    def __init__(self, config_path: str = 'config.json', dry_run: bool = False, symbol: str = None):
        self.dry_run = dry_run

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        log_dir = self.config.get('logging', {}).get('log_dir', 'logs')
        self.logger = setup_logger('iron_condor', log_dir)

        # API setup
        api_key = os.environ.get('ALPACA_API_KEY', '')
        secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
        base_url = 'https://paper-api.alpaca.markets'

        if 'api' in self.config:
            api_key = api_key or self.config['api'].get('key_id', '')
            secret_key = secret_key or self.config['api'].get('secret_key', '')
            base_url = self.config['api'].get('base_url', base_url)

        if not api_key or not secret_key:
            parent_config = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config', 'config.json'
            )
            if os.path.exists(parent_config):
                with open(parent_config, 'r') as f:
                    pc = json.load(f)
                api_key = pc['api']['key_id']
                secret_key = pc['api']['secret_key']
                base_url = pc['api']['base_url']

        is_paper = 'paper' in base_url
        self.client = AlpacaOptionsClient(api_key, secret_key, paper=is_paper)

        db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db')
        os.makedirs(db_dir, exist_ok=True)
        self.risk_manager = RiskManager(
            self.config.get('risk', {}),
            db_path=os.path.join(db_dir, 'condor_trades.db')
        )

        self.watchlist = [symbol.upper()] if symbol else self.config.get('watchlist', ['SPY'])
        self.condor = self.config.get('condor_rules', {})
        self.iv_rules = self.config.get('iv_rules', {})
        self.execution = self.config.get('execution', {})
        
        self.earnings = EarningsCalendar(
            manual_dates=self.config.get('earnings_dates_manual', {})
        )

        # Ladder exit manager
        ladder_state = os.path.join(db_dir, 'ladder_state.json')
        self.ladder = LadderExitManager(
            state_file=ladder_state,
            logger=self.logger,
        )

        self.logger.info("=" * 70)
        self.logger.info("IRON CONDOR INCOME MACHINE v1.0")
        self.logger.info(f"Mode: {'DRY RUN' if dry_run else ('PAPER' if is_paper else 'LIVE')}")
        self.logger.info(f"Watchlist: {', '.join(self.watchlist)}")
        self.logger.info(f"Put Delta: {self.condor.get('put_delta', 0.12)}")
        self.logger.info(f"Call Delta: {self.condor.get('call_delta', 0.12)}")
        self.logger.info(f"Wing Width: ${self.condor.get('wing_width', 5)}")
        self.logger.info("=" * 70)

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self):
        """Main bot loop."""
        scan_interval = self.execution.get('scan_interval_minutes', 5) * 60

        while True:
            try:
                if not self._is_market_hours():
                    self.logger.info("Market closed. Sleeping...")
                    time.sleep(60)
                    continue

                self._run_cycle()
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                self.logger.info("Bot stopped.")
                break
            except Exception as e:
                self.logger.error(f"Error: {e}", exc_info=True)
                time.sleep(60)

    def _run_cycle(self):
        """Single cycle: monitor, then hunt."""
        equity = self.client.get_equity()
        self.logger.info(f"Equity: ${equity:,.2f}")

        # 1. Monitor existing iron condors
        self._monitor_positions()

        # 2. Hunt for new iron condors
        self._hunt_for_condors(equity)

        self._log_summary()

    # ──────────────────────────────────────────────────────────────
    # POSITION MONITORING
    # ──────────────────────────────────────────────────────────────

    def _monitor_positions(self):
        """Monitor all open iron condor legs."""
        # Get all open trades for this strategy
        put_trades = self.risk_manager.get_open_trades(strategy='condor_put_side')
        call_trades = self.risk_manager.get_open_trades(strategy='condor_call_side')

        # Group by underlying for iron condor management
        condors = {}
        for trade in put_trades:
            underlying = trade['underlying']
            if underlying not in condors:
                condors[underlying] = {'put': None, 'call': None}
            condors[underlying]['put'] = trade

        for trade in call_trades:
            underlying = trade['underlying']
            if underlying not in condors:
                condors[underlying] = {'put': None, 'call': None}
            condors[underlying]['call'] = trade

        for underlying, sides in condors.items():
            self._check_condor_exits(underlying, sides)

    def _check_condor_exits(self, underlying: str, sides: dict):
        """Check exit conditions for an iron condor using ladder exit manager."""
        put_trade = sides.get('put')
        call_trade = sides.get('call')

        total_credit = 0
        total_current = 0
        
        put_current = 0
        call_current = 0

        # Get current prices for each side
        if put_trade:
            try:
                quote = self.client.get_option_quote(put_trade['symbol'])
                if quote and put_trade['symbol'] in quote:
                    q = quote[put_trade['symbol']]
                    put_current = round(
                        (float(q.bid_price or 0) + float(q.ask_price or 0)) / 2, 2
                    )
                    total_credit += put_trade['premium_collected']
                    total_current += put_current
            except Exception as e:
                self.logger.error(f"Error getting put quote: {e}")

        if call_trade:
            try:
                quote = self.client.get_option_quote(call_trade['symbol'])
                if quote and call_trade['symbol'] in quote:
                    q = quote[call_trade['symbol']]
                    call_current = round(
                        (float(q.bid_price or 0) + float(q.ask_price or 0)) / 2, 2
                    )
                    total_credit += call_trade['premium_collected']
                    total_current += call_current
            except Exception as e:
                self.logger.error(f"Error getting call quote: {e}")

        if total_credit == 0:
            return

        # Time exit: always check DTE
        exp_date = None
        if put_trade and put_trade.get('expiration_date'):
            exp_date = put_trade['expiration_date'][:10]
        elif call_trade and call_trade.get('expiration_date'):
            exp_date = call_trade['expiration_date'][:10]

        if exp_date:
            remaining = calculate_dte(exp_date)
            if remaining <= self.condor.get('time_exit_dte', 21):
                self.logger.info(
                    f"TIME EXIT: {underlying} iron condor | {remaining} DTE"
                )
                self._close_condor_with_ladder(sides, f"Time exit ({remaining} DTE)")
                return

        # Side breach detection (delta-based, independent of ladder)
        breach_delta = self.condor.get('side_breach_delta', 0.40)
        
        if put_trade and put_current > 0:
            try:
                snap = self.client.get_option_snapshot([put_trade['symbol']])
                if snap and put_trade['symbol'] in snap:
                    put_delta = abs(float(snap[put_trade['symbol']].greeks.delta or 0))
                    if put_delta >= breach_delta:
                        self.logger.warning(
                            f"PUT SIDE BREACH: {underlying} | Delta={put_delta:.2f} > {breach_delta}"
                        )
                        pos_key = f"{put_trade['id']}_{put_trade['symbol']}"
                        self._close_side(put_trade, put_current, "Put side breach")
                        self.ladder.remove_position(pos_key)
                        return
            except Exception:
                pass

        if call_trade and call_current > 0:
            try:
                snap = self.client.get_option_snapshot([call_trade['symbol']])
                if snap and call_trade['symbol'] in snap:
                    call_delta = abs(float(snap[call_trade['symbol']].greeks.delta or 0))
                    if call_delta >= breach_delta:
                        self.logger.warning(
                            f"CALL SIDE BREACH: {underlying} | Delta={call_delta:.2f} > {breach_delta}"
                        )
                        pos_key = f"{call_trade['id']}_{call_trade['symbol']}"
                        self._close_side(call_trade, call_current, "Call side breach")
                        self.ladder.remove_position(pos_key)
                        return
            except Exception:
                pass

        # Ladder check for each side independently
        for side_name, trade, current in [('put', put_trade, put_current),
                                           ('call', call_trade, call_current)]:
            if not trade or current <= 0:
                continue

            pos_key = f"{trade['id']}_{trade['symbol']}"
            if not self.ladder.is_registered(pos_key):
                self.ladder.register_position(
                    pos_key, trade['premium_collected'],
                    trade['quantity'], side='short'
                )

            result = self.ladder.check_exit(pos_key, current)

            if result['action'] == 'stop_loss':
                pnl = (trade['premium_collected'] - current) * 100 * result['contracts_to_sell']
                self._close_side(trade, current, f"Ladder stop ({side_name}): {result['tier']}")
                self.ladder.remove_position(pos_key)

            elif result['action'] in ('sell_partial', 'sell_all'):
                qty = result['contracts_to_sell']
                pnl = (trade['premium_collected'] - current) * 100 * qty
                self.logger.info(
                    f"LADDER EXIT ({side_name}): {trade['symbol']} | {result['reason']}"
                )
                self._close_side_partial(trade, current, qty, pnl, result['reason'])
                self.ladder.confirm_sell(pos_key, qty, current)

        total_pnl_pct = (total_credit - total_current) / total_credit if total_credit > 0 else 0
        self.logger.info(
            f"HOLD: {underlying} IC | P&L: {total_pnl_pct:.0%} | "
            f"Put: ${put_current:.2f} | Call: ${call_current:.2f}"
        )

    def _close_condor_with_ladder(self, sides: dict, reason: str):
        """Close both sides and clean up ladder state."""
        for side_name in ['put', 'call']:
            trade = sides.get(side_name)
            if trade:
                pos_key = f"{trade['id']}_{trade['symbol']}"
                self._close_side(trade, 0, reason)
                self.ladder.remove_position(pos_key)

    def _close_side(self, trade: dict, current_price: float, reason: str):
        """Close one side of the iron condor."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would close {trade['symbol']} — {reason}")
            return

        pnl = (trade['premium_collected'] - current_price) * 100 * trade['quantity']
        order = self.client.buy_to_close(trade['symbol'], trade['quantity'], current_price)
        if order:
            self.risk_manager.close_trade(trade['id'], current_price, pnl, reason)

    def _close_side_partial(self, trade: dict, current_price: float, qty: int,
                            pnl: float, reason: str):
        """Close a partial number of contracts from one side."""
        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would close {qty} of {trade['quantity']} contracts "
                f"on {trade['symbol']} — {reason}"
            )
            return

        order = self.client.buy_to_close(trade['symbol'], qty, current_price)
        if order:
            self.risk_manager.close_trade(trade['id'], current_price, pnl, f"Partial: {reason}")

    # ──────────────────────────────────────────────────────────────
    # HUNTING FOR NEW IRON CONDORS
    # ──────────────────────────────────────────────────────────────

    def _hunt_for_condors(self, equity: float):
        """Scan watchlist for new iron condor opportunities."""
        open_trades = self.risk_manager.get_open_trades()
        max_condors = self.config.get('risk', {}).get('max_concurrent_condors', 5)
        
        # Each condor has 2 sides, so divide by 2
        current_condors = len(open_trades) // 2
        if current_condors >= max_condors:
            self.logger.info(f"Max condors reached ({current_condors}/{max_condors})")
            return

        for symbol in self.watchlist:
            # Check earnings
            if self.earnings.has_earnings_within(symbol, self.condor.get('min_dte', 30)):
                continue

            try:
                self._evaluate_condor(symbol, equity)
            except Exception as e:
                self.logger.error(f"Error evaluating {symbol}: {e}")

    def _evaluate_condor(self, symbol: str, equity: float):
        """Evaluate iron condor opportunity for a specific underlying."""
        self.logger.info(f"Evaluating iron condor on {symbol}...")

        # Find put spread (bull put)
        put_spread = self.client.find_spread_contracts(
            symbol=symbol,
            spread_type='bull_put',
            target_delta=self.condor.get('put_delta', 0.12),
            spread_width=self.condor.get('wing_width', 5),
            min_dte=self.condor.get('min_dte', 30),
            max_dte=self.condor.get('max_dte', 45),
        )

        if not put_spread:
            self.logger.info(f"SKIP {symbol}: No suitable put spread")
            return

        # Find call spread (bear call)
        call_spread = self.client.find_spread_contracts(
            symbol=symbol,
            spread_type='bear_call',
            target_delta=self.condor.get('call_delta', 0.12),
            spread_width=self.condor.get('wing_width', 5),
            min_dte=self.condor.get('min_dte', 30),
            max_dte=self.condor.get('max_dte', 45),
        )

        if not call_spread:
            self.logger.info(f"SKIP {symbol}: No suitable call spread")
            return

        # Calculate total credit
        total_credit = put_spread['net_credit'] + call_spread['net_credit']
        wing_width = self.condor.get('wing_width', 5)
        min_credit_ratio = self.condor.get('min_total_credit_ratio', 0.33)

        # 1/3 credit rule check
        if total_credit < wing_width * min_credit_ratio:
            self.logger.info(
                f"SKIP {symbol}: Credit ${total_credit:.2f} < "
                f"${wing_width * min_credit_ratio:.2f} (1/3 rule)"
            )
            return

        # Max loss per side
        max_loss_per_side = (wing_width - total_credit / 2) * 100

        # Risk approval
        approved, reason = self.risk_manager.approve_trade(
            symbol=f"{symbol}_IC",
            underlying=symbol,
            trade_type='iron_condor',
            max_loss=max_loss_per_side,
            collateral_required=max_loss_per_side,
            account_equity=equity,
        )

        if not approved:
            self.logger.info(f"REJECTED {symbol}: {reason}")
            return

        # Get expiration info
        parsed = parse_occ_symbol(put_spread['short_leg']['symbol'])
        expiration = parsed['expiration'] if parsed else ''
        dte = calculate_dte(expiration) if expiration else 35

        self.logger.info(
            f"CONDOR FOUND: {symbol} | "
            f"Put: ${put_spread['net_credit']:.2f} | "
            f"Call: ${call_spread['net_credit']:.2f} | "
            f"Total: ${total_credit:.2f} | "
            f"MaxLoss/side: ${max_loss_per_side:.2f} | DTE: {dte}"
        )

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would open iron condor on {symbol}")
            return

        # Execute both sides
        # Put side
        put_order = self.client.place_spread_order(
            short_symbol=put_spread['short_leg']['symbol'],
            long_symbol=put_spread['long_leg']['symbol'],
            qty=1,
            net_credit=put_spread['net_credit'],
        )

        if put_order:
            self.risk_manager.record_trade({
                'strategy': 'condor_put_side',
                'symbol': put_spread['short_leg']['symbol'],
                'underlying': symbol,
                'trade_type': 'iron_condor_put',
                'side': 'sell',
                'quantity': 1,
                'entry_price': put_spread['net_credit'],
                'premium_collected': put_spread['net_credit'],
                'max_loss': max_loss_per_side,
                'collateral_used': max_loss_per_side,
                'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiration_date': expiration,
            })

        # Call side
        call_order = self.client.place_spread_order(
            short_symbol=call_spread['short_leg']['symbol'],
            long_symbol=call_spread['long_leg']['symbol'],
            qty=1,
            net_credit=call_spread['net_credit'],
        )

        if call_order:
            self.risk_manager.record_trade({
                'strategy': 'condor_call_side',
                'symbol': call_spread['short_leg']['symbol'],
                'underlying': symbol,
                'trade_type': 'iron_condor_call',
                'side': 'sell',
                'quantity': 1,
                'entry_price': call_spread['net_credit'],
                'premium_collected': call_spread['net_credit'],
                'max_loss': max_loss_per_side,
                'collateral_used': max_loss_per_side,
                'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiration_date': expiration,
            })

        self.logger.info(f"IRON CONDOR OPENED: {symbol}")

    # ──────────────────────────────────────────────────────────────
    # UTILITIES
    # ──────────────────────────────────────────────────────────────

    def _is_market_hours(self) -> bool:
        now = datetime.now(pytz.timezone('US/Eastern'))
        if now.weekday() > 4:
            return False
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now <= market_close

    def _log_summary(self):
        put_summary = self.risk_manager.get_performance_summary(strategy='condor_put_side')
        call_summary = self.risk_manager.get_performance_summary(strategy='condor_call_side')
        open_count = len(self.risk_manager.get_open_trades())
        
        total_pnl = (put_summary['total_pnl'] or 0) + (call_summary['total_pnl'] or 0)
        total_trades = (put_summary['total_trades'] or 0) + (call_summary['total_trades'] or 0)
        
        self.logger.info(
            f"Summary: {open_count // 2} condors open | "
            f"{total_trades} total legs | "
            f"Total P&L: ${total_pnl:.2f}"
        )


def main():
    parser = argparse.ArgumentParser(description='Iron Condor Income Machine')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--symbol', default=None)
    args = parser.parse_args()

    bot = IronCondorBot(config_path=args.config, dry_run=args.dry_run, symbol=args.symbol)
    bot.run()


if __name__ == '__main__':
    main()
