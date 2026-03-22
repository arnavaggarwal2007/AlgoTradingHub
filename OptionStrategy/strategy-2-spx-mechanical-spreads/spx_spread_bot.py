"""
================================================================================
SPX MECHANICAL CREDIT SPREADS — Automated Trading Bot
================================================================================

Strategy: Sell Bull Put Spreads on SPX/XSP every MWF at 0.10-0.15 Delta

This bot:
1. Opens on scheduled days (MWF) only
2. Checks VIX for market regime (pause in extreme conditions)
3. Finds optimal put spread at target delta with 30-45 DTE
4. Executes at mid-price for best fills
5. Monitors open spreads for exit signals
6. Tracks all trades for performance analysis

KEY RULES:
- Entry at 0.10-0.15 Delta (85-90% POP)
- Spread width: $50 for SPX / $5 for XSP
- Exit at 50% profit, 21 DTE, or 3× stop loss
- Max 6 concurrent spreads
- Pause when VIX > 40

Usage:
    python spx_spread_bot.py                # Paper trading
    python spx_spread_bot.py --dry-run      # Show actions without executing
    python spx_spread_bot.py --symbol XSP   # Use Mini SPX

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
    probability_of_profit_spread,
    annualized_return,
    parse_occ_symbol,
)
from shared.logger import setup_logger
from ladder_exit import LadderExitManager


class SPXSpreadBot:
    """
    Mechanical SPX Bull Put Spread income engine.
    
    Sells credit spreads on the S&P 500 Index every MWF.
    Fully automated with defined risk and mechanical exits.
    """

    def __init__(self, config_path: str = 'config.json', dry_run: bool = False, symbol: str = None):
        self.dry_run = dry_run

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        log_dir = self.config.get('logging', {}).get('log_dir', 'logs')
        self.logger = setup_logger('spx_spreads', log_dir)

        # Determine underlying
        if symbol:
            self.underlying = symbol.upper()
        elif self.config.get('use_alternative', False):
            self.underlying = self.config.get('alternative_underlying', 'XSP')
        else:
            self.underlying = self.config.get('underlying', 'SPX')

        # Load API keys
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
            db_path=os.path.join(db_dir, 'spx_trades.db')
        )

        self.spread = self.config.get('spread_rules', {})
        self.vix_rules = self.config.get('vix_rules', {})
        self.execution = self.config.get('execution', {})

        # Ladder exit manager
        ladder_state = os.path.join(db_dir, 'ladder_state.json')
        self.ladder = LadderExitManager(
            state_file=ladder_state,
            logger=self.logger,
        )

        self.logger.info("=" * 70)
        self.logger.info(f"SPX MECHANICAL SPREADS v1.0 — {self.underlying}")
        self.logger.info(f"Mode: {'DRY RUN' if dry_run else ('PAPER' if is_paper else 'LIVE')}")
        self.logger.info(f"Entry Days: {self.spread.get('entry_days', ['Mon', 'Wed', 'Fri'])}")
        self.logger.info(f"Delta Target: {self.spread.get('target_delta', 0.12)}")
        self.logger.info(f"Spread Width: ${self.spread.get('spread_width', 50)}")
        self.logger.info("=" * 70)

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self):
        """Main loop — continuously scan during market hours."""
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
        """Single cycle: monitor exits, then look for new entries."""
        equity = self.client.get_equity()
        self.logger.info(f"Equity: ${equity:,.2f}")

        # 1. Monitor existing spreads
        self._monitor_exits()

        # 2. Check if we should enter new spreads today
        if self._is_entry_day() and self._is_entry_window():
            self._enter_new_spread(equity)

        self._log_summary()

    # ──────────────────────────────────────────────────────────────
    # EXIT MONITORING
    # ──────────────────────────────────────────────────────────────

    def _monitor_exits(self):
        """Check all open spreads for exit conditions using ladder exit manager."""
        open_trades = self.risk_manager.get_open_trades(strategy='spx_bull_put')

        for trade in open_trades:
            try:
                short_symbol = trade['symbol']
                quote = self.client.get_option_quote(short_symbol)
                
                if not quote or short_symbol not in quote:
                    continue

                q = quote[short_symbol]
                current_mid = round(
                    (float(q.bid_price or 0) + float(q.ask_price or 0)) / 2, 2
                )

                entry_credit = trade['premium_collected']

                # Register with ladder if not already tracked
                pos_key = f"{trade['id']}_{short_symbol}"
                if not self.ladder.is_registered(pos_key):
                    self.ladder.register_position(
                        pos_key, entry_credit, trade['quantity'], side='short'
                    )

                # Time exit: always check DTE
                if trade.get('expiration_date'):
                    remaining = calculate_dte(trade['expiration_date'][:10])
                    if remaining <= self.spread.get('time_exit_dte', 21):
                        pnl = (entry_credit - current_mid) * 100 * trade['quantity']
                        self.logger.info(
                            f"TIME EXIT: {short_symbol} | {remaining} DTE | P&L: ${pnl:.2f}"
                        )
                        self._close_spread(trade, current_mid, pnl, f"Time exit ({remaining} DTE)")
                        self.ladder.remove_position(pos_key)
                        continue

                # Emergency VIX check
                vix = self.client.get_vix_level()
                if vix and vix >= self.vix_rules.get('emergency_close_level', 50):
                    pnl = (entry_credit - current_mid) * 100 * trade['quantity']
                    self.logger.warning(f"VIX EMERGENCY: Closing {short_symbol} | VIX={vix:.1f}")
                    self._close_spread(trade, current_mid, pnl, f"VIX emergency ({vix:.1f})")
                    self.ladder.remove_position(pos_key)
                    continue

                # Ladder exit check
                result = self.ladder.check_exit(pos_key, current_mid)

                if result['action'] == 'stop_loss':
                    pnl = (entry_credit - current_mid) * 100 * result['contracts_to_sell']
                    self._close_spread(trade, current_mid, pnl, f"Ladder stop: {result['tier']}")
                    self.ladder.remove_position(pos_key)

                elif result['action'] in ('sell_partial', 'sell_all'):
                    qty = result['contracts_to_sell']
                    pnl = (entry_credit - current_mid) * 100 * qty
                    self.logger.info(f"LADDER EXIT: {short_symbol} | {result['reason']}")
                    self._close_spread_partial(trade, current_mid, qty, pnl, result['reason'])
                    self.ladder.confirm_sell(pos_key, qty, current_mid)

                else:
                    self.logger.info(
                        f"HOLD: {short_symbol} | P&L: {result['profit_pct']:+.1%} | "
                        f"SL: ${result['stop_loss']:.2f} | Tier: {result['tier']}"
                    )

            except Exception as e:
                self.logger.error(f"Error monitoring {trade['symbol']}: {e}")

    def _close_spread(self, trade: dict, exit_price: float, pnl: float, reason: str):
        """Close a spread position."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would close {trade['symbol']} — {reason}")
            return

        # Buy to close the short leg
        order = self.client.buy_to_close(trade['symbol'], trade['quantity'], exit_price)
        if order:
            self.risk_manager.close_trade(trade['id'], exit_price, pnl, reason)

    def _close_spread_partial(self, trade: dict, exit_price: float, qty: int,
                              pnl: float, reason: str):
        """Close a partial number of spread contracts."""
        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would close {qty} of {trade['quantity']} spreads "
                f"on {trade['symbol']} — {reason}"
            )
            return

        order = self.client.buy_to_close(trade['symbol'], qty, exit_price)
        if order:
            self.risk_manager.close_trade(trade['id'], exit_price, pnl, f"Partial: {reason}")

    # ──────────────────────────────────────────────────────────────
    # NEW SPREAD ENTRY
    # ──────────────────────────────────────────────────────────────

    def _enter_new_spread(self, equity: float):
        """Find and enter a new bull put spread."""
        # Check position limits
        open_trades = self.risk_manager.get_open_trades(strategy='spx_bull_put')
        max_spreads = self.config.get('risk', {}).get('max_concurrent_spreads', 6)
        
        if len(open_trades) >= max_spreads:
            self.logger.info(f"Max spreads reached ({len(open_trades)}/{max_spreads})")
            return

        # Check VIX
        vix_ok, vix_value = self._check_vix()
        if not vix_ok:
            return

        # Adjust delta based on VIX
        target_delta = self.spread.get('target_delta', 0.12)
        if vix_value >= self.vix_rules.get('reduce_delta_above', 25):
            target_delta = 0.08
            self.logger.info(f"VIX={vix_value:.1f} — reducing delta to {target_delta}")
        elif vix_value >= self.vix_rules.get('aggressive_above', 20):
            target_delta = 0.12
            self.logger.info(f"VIX={vix_value:.1f} — elevated IV, good premiums")

        # Find the spread
        spread_data = self.client.find_spread_contracts(
            symbol=self.underlying,
            spread_type='bull_put',
            target_delta=target_delta,
            spread_width=self.spread.get('spread_width', 50),
            min_dte=self.spread.get('min_dte', 30),
            max_dte=self.spread.get('max_dte', 45),
        )

        if not spread_data:
            self.logger.info(f"No suitable spread found for {self.underlying}")
            return

        credit = spread_data['net_credit']
        max_loss = spread_data['max_loss'] * 100  # Per contract

        # Minimum credit check
        min_credit = self.spread.get('min_credit', 1.50)
        if credit < min_credit:
            self.logger.info(
                f"SKIP: Credit ${credit:.2f} below minimum ${min_credit:.2f}"
            )
            return

        # Risk manager approval
        approved, reason = self.risk_manager.approve_trade(
            symbol=spread_data['short_leg']['symbol'],
            underlying=self.underlying,
            trade_type='bull_put_spread',
            max_loss=max_loss,
            collateral_required=max_loss,
            account_equity=equity,
        )

        if not approved:
            self.logger.info(f"REJECTED: {reason}")
            return

        # Get expiration info
        parsed = parse_occ_symbol(spread_data['short_leg']['symbol'])
        expiration = parsed['expiration'] if parsed else ''
        dte = calculate_dte(expiration) if expiration else 35
        short_strike = parsed['strike'] if parsed else 0

        # Get underlying price for POP
        underlying_price = self.client.get_underlying_price(self.underlying)
        
        parsed_long = parse_occ_symbol(spread_data['long_leg']['symbol'])
        long_strike = parsed_long['strike'] if parsed_long else short_strike - self.spread.get('spread_width', 50)
        
        pop = probability_of_profit_spread(
            underlying_price, short_strike, long_strike, credit,
            spread_data['short_leg'].get('iv', 0.2), dte
        )

        self.logger.info(
            f"SPREAD FOUND: {self.underlying} | "
            f"Short={short_strike:.0f} / Long={long_strike:.0f} | "
            f"Credit=${credit:.2f} | MaxLoss=${max_loss:.2f} | "
            f"POP={pop:.1f}% | DTE={dte}"
        )

        if self.dry_run:
            self.logger.info("[DRY RUN] Would enter this spread")
            return

        # Execute
        order = self.client.place_spread_order(
            short_symbol=spread_data['short_leg']['symbol'],
            long_symbol=spread_data['long_leg']['symbol'],
            qty=1,
            net_credit=credit,
        )

        if order:
            self.risk_manager.record_trade({
                'strategy': 'spx_bull_put',
                'symbol': spread_data['short_leg']['symbol'],
                'underlying': self.underlying,
                'trade_type': 'bull_put_spread',
                'side': 'sell',
                'quantity': 1,
                'entry_price': credit,
                'premium_collected': credit,
                'max_loss': max_loss,
                'collateral_used': max_loss,
                'stop_loss_price': self.risk_manager.calculate_stop_loss(credit),
                'profit_target_price': self.risk_manager.calculate_profit_target(credit),
                'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiration_date': expiration,
            })
            self.logger.info(f"SPREAD OPENED: {self.underlying} ${short_strike}/{long_strike}")

    # ──────────────────────────────────────────────────────────────
    # VIX CHECK
    # ──────────────────────────────────────────────────────────────

    def _check_vix(self):
        """Check VIX level and determine if conditions are suitable."""
        try:
            vix_price = self.client.get_underlying_price('VIXY')  # VIX proxy ETF
            # Note: For actual VIX, use CBOE data or Alpaca's VIX data
        except Exception:
            self.logger.warning("Could not get VIX data, using default=20")
            vix_price = 20.0

        min_vix = self.vix_rules.get('min_vix', 15)
        max_vix = self.vix_rules.get('max_vix', 35)
        pause_above = self.vix_rules.get('pause_above', 40)

        if vix_price > pause_above:
            self.logger.warning(f"VIX={vix_price:.1f} > {pause_above} — PAUSING all entries")
            return False, vix_price
        
        if vix_price < min_vix:
            self.logger.info(f"VIX={vix_price:.1f} < {min_vix} — premiums too low, skipping")
            return False, vix_price

        self.logger.info(f"VIX={vix_price:.1f} — within acceptable range")
        return True, vix_price

    # ──────────────────────────────────────────────────────────────
    # SCHEDULING
    # ──────────────────────────────────────────────────────────────

    def _is_entry_day(self) -> bool:
        """Check if today is an entry day (MWF by default)."""
        now = datetime.now(pytz.timezone('US/Eastern'))
        day_name = now.strftime('%A')
        entry_days = self.spread.get('entry_days', ['Monday', 'Wednesday', 'Friday'])
        return day_name in entry_days

    def _is_entry_window(self) -> bool:
        """Check if we're in the entry time window."""
        now = datetime.now(pytz.timezone('US/Eastern'))
        start = self.spread.get('entry_time_start', '10:00')
        end = self.spread.get('entry_time_end', '15:00')
        
        start_h, start_m = map(int, start.split(':'))
        end_h, end_m = map(int, end.split(':'))
        
        current_time = now.hour * 60 + now.minute
        start_time = start_h * 60 + start_m
        end_time = end_h * 60 + end_m
        
        return start_time <= current_time <= end_time

    def _is_market_hours(self) -> bool:
        """Check if market is open."""
        now = datetime.now(pytz.timezone('US/Eastern'))
        if now.weekday() > 4:
            return False
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now <= market_close

    def _log_summary(self):
        """Log portfolio summary."""
        summary = self.risk_manager.get_performance_summary(strategy='spx_bull_put')
        open_count = len(self.risk_manager.get_open_trades(strategy='spx_bull_put'))
        
        self.logger.info(
            f"Summary: {open_count} open | "
            f"{summary['total_trades']} total | "
            f"Win: {summary['win_rate']:.0f}% | "
            f"P&L: ${summary['total_pnl']:.2f}"
        )


def main():
    parser = argparse.ArgumentParser(description='SPX Mechanical Credit Spreads Bot')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--symbol', default=None, help='Override underlying (SPX or XSP)')
    args = parser.parse_args()

    bot = SPXSpreadBot(config_path=args.config, dry_run=args.dry_run, symbol=args.symbol)
    bot.run()


if __name__ == '__main__':
    main()
