"""
================================================================================
VIX-REGIME ADAPTIVE ML BOT — Automated Regime-Aware Credit Spread Trading
================================================================================

Strategy: Sell credit spreads (primarily put spreads) with parameters that
dynamically adjust based on the current volatility regime detected by an
ML model (Random Forest on VIX/SPY features).

This bot:
1. Runs the regime detection model to classify the market
2. Adjusts delta, spread width, DTE, and position size per regime
3. Only enters High Vol trades when VIX is declining (mean reversion)
4. Monitors positions with regime-adjusted profit targets
5. Emergency closes everything if VIX > 45 or regime shifts to Crash
6. Auto-retrains the model monthly

KEY RULES:
- Crash regime: STOP all trading immediately
- Low Vol regime: Skip (disabled by default, premiums too thin)
- Normal regime: Standard credit spreads (0.12 delta, $5 wide)
- High Vol regime: Aggressive spreads (0.15 delta, $10 wide, 150% size)
  BUT only when VIX is declining from a recent peak
- Stop loss: Always 2× credit received
- Max exposure: 20% of equity

Usage:
    python regime_adaptive_bot.py              # Paper trading
    python regime_adaptive_bot.py --dry-run    # Preview mode
    python regime_adaptive_bot.py --retrain    # Retrain model first
    python regime_adaptive_bot.py --symbol SPY # Specific symbol

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
from shared.option_utils import calculate_dte, parse_occ_symbol
from shared.earnings_calendar import EarningsCalendar
from shared.logger import setup_logger
from regime_detector import RegimeDetector, REGIME_NAMES
from ladder_exit import LadderExitManager


class RegimeAdaptiveBot:
    """
    VIX-Regime Adaptive ML Bot — adjusts every parameter based on
    the current market volatility regime.
    """

    def __init__(self, config_path: str = 'config.json', dry_run: bool = False,
                 symbol: str = None, retrain: bool = False):
        self.dry_run = dry_run

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        log_dir = self.config.get('logging', {}).get('log_dir', 'logs')
        self.logger = setup_logger('regime_adaptive', log_dir)

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

        # Risk manager
        db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db')
        os.makedirs(db_dir, exist_ok=True)
        self.risk_manager = RiskManager(
            self.config.get('risk', {}),
            db_path=os.path.join(db_dir, 'regime_trades.db')
        )

        # Regime detector
        self.detector = RegimeDetector(self.config)
        if retrain or self.detector.needs_retrain():
            self.logger.info("Model needs (re)training...")
            self.detector.retrain() if self.detector.model else self.detector.train()

        if self.detector.model is None:
            self.logger.warning(
                "No trained model available. Using VIX threshold fallback. "
                "Run: python regime_detector.py --train"
            )

        self.watchlist = [symbol.upper()] if symbol else self.config.get('watchlist', ['SPY'])
        self.regime_rules = self.config.get('regime_rules', {})
        self.hard_limits = self.config.get('hard_limits', {})
        self.execution = self.config.get('execution', {})

        self.earnings = EarningsCalendar(
            manual_dates=self.config.get('earnings_dates_manual', {})
        )

        # Current regime state
        self.current_regime = None
        self.current_params = {}

        # Ladder exit manager
        ladder_state = os.path.join(db_dir, 'ladder_state.json')
        self.ladder = LadderExitManager(
            state_file=ladder_state,
            logger=self.logger,
        )

        self.logger.info("=" * 70)
        self.logger.info("VIX-REGIME ADAPTIVE ML BOT v1.0")
        self.logger.info(f"Mode: {'DRY RUN' if dry_run else ('PAPER' if is_paper else 'LIVE')}")
        self.logger.info(f"Watchlist: {', '.join(self.watchlist)}")
        self.logger.info(f"ML Model: {'Loaded' if self.detector.model else 'Fallback mode'}")
        self.logger.info("=" * 70)

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self):
        """Main bot loop."""
        scan_interval = self.execution.get('scan_interval_minutes', 10) * 60

        while True:
            try:
                if not self._is_market_hours():
                    self.logger.info("Market closed. Sleeping...")
                    time.sleep(60)
                    continue

                self._run_cycle()
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user.")
                break
            except Exception as e:
                self.logger.error(f"Cycle error: {e}", exc_info=True)
                time.sleep(60)

    def _run_cycle(self):
        """Single trading cycle."""
        equity = self.client.get_equity()
        self.logger.info(f"Equity: ${equity:,.2f}")

        # 1. Detect current regime
        regime = self._detect_regime()
        if regime is None:
            self.logger.error("Failed to detect regime. Skipping cycle.")
            return

        # 2. Emergency checks
        if self._check_emergency(regime, equity):
            return

        # 3. Monitor existing positions
        self._monitor_positions(regime)

        # 4. Hunt for new trades (if regime allows)
        self._hunt_for_spreads(regime, equity)

        # 5. Log summary
        self._log_summary(regime)

    # ──────────────────────────────────────────────────────────────
    # REGIME DETECTION
    # ──────────────────────────────────────────────────────────────

    def _detect_regime(self) -> dict:
        """Run the ML regime detection model."""
        try:
            regime = self.detector.predict_regime()

            self.logger.info(
                f"REGIME: {regime['regime_name']} | "
                f"VIX: {regime['vix_level']:.1f} | "
                f"MA20: {regime['vix_ma20']:.1f} | "
                f"Confidence: {regime['confidence']:.0%} | "
                f"Mean Reversion: {'YES' if regime['mean_reversion'] else 'NO'}"
            )

            # Update current state
            old_regime = self.current_regime
            self.current_regime = regime

            # Set parameters for this regime
            regime_key = regime['regime_key']
            self.current_params = self.regime_rules.get(regime_key, {})

            # Log regime transitions
            if old_regime and old_regime['regime_id'] != regime['regime_id']:
                self.logger.warning(
                    f"REGIME TRANSITION: {old_regime['regime_name']} → {regime['regime_name']}"
                )

            return regime

        except Exception as e:
            self.logger.error(f"Regime detection failed: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # EMERGENCY CHECKS
    # ──────────────────────────────────────────────────────────────

    def _check_emergency(self, regime: dict, equity: float) -> bool:
        """Check hard limits. Returns True to abort cycle."""
        vix = regime['vix_level']

        # Hard VIX stop
        emergency_vix = self.hard_limits.get('emergency_vix_stop', 45)
        if vix >= emergency_vix:
            self.logger.critical(
                f"EMERGENCY: VIX={vix:.1f} >= {emergency_vix}! "
                "Closing ALL positions immediately!"
            )
            self._emergency_close_all("VIX emergency stop")
            return True

        # Crash regime
        if regime['regime_id'] == 3:
            self.logger.warning(
                "CRASH REGIME detected. No new trades. "
                "Monitoring existing positions for exit."
            )
            # Don't abort — still need to monitor existing positions
            return False

        # Daily loss limit
        summary = self.risk_manager.get_performance_summary(strategy='regime_adaptive')
        today_pnl = summary.get('today_pnl', 0) or 0
        max_daily_loss = equity * self.hard_limits.get('max_daily_loss_pct', 0.10)
        if today_pnl < -max_daily_loss:
            self.logger.critical(
                f"DAILY LOSS LIMIT: ${today_pnl:.2f} exceeds ${-max_daily_loss:.2f}. "
                "Closing all positions!"
            )
            self._emergency_close_all("Daily loss limit")
            return True

        return False

    def _emergency_close_all(self, reason: str):
        """Emergency close all open positions."""
        open_trades = self.risk_manager.get_open_trades(strategy='regime_adaptive')
        for trade in open_trades:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would emergency close {trade['symbol']}")
                    continue

                quote = self.client.get_option_quote(trade['symbol'])
                current_price = 0
                if quote and trade['symbol'] in quote:
                    q = quote[trade['symbol']]
                    current_price = round(
                        (float(q.bid_price or 0) + float(q.ask_price or 0)) / 2, 2
                    )

                pnl = (trade['premium_collected'] - current_price) * 100 * trade['quantity']
                order = self.client.buy_to_close(trade['symbol'], trade['quantity'], current_price)
                if order:
                    self.risk_manager.close_trade(trade['id'], current_price, pnl, reason)
                    self.logger.info(f"Emergency closed: {trade['symbol']} | P&L: ${pnl:.2f}")
            except Exception as e:
                self.logger.error(f"Failed to emergency close {trade['symbol']}: {e}")

    # ──────────────────────────────────────────────────────────────
    # POSITION MONITORING
    # ──────────────────────────────────────────────────────────────

    def _monitor_positions(self, regime: dict):
        """Monitor all open positions with regime-aware exit logic."""
        open_trades = self.risk_manager.get_open_trades(strategy='regime_adaptive')

        if not open_trades:
            return

        self.logger.info(f"Monitoring {len(open_trades)} open positions...")

        for trade in open_trades:
            self._check_position_exit(trade, regime)

    def _check_position_exit(self, trade: dict, regime: dict):
        """Check if a position should be exited using ladder exit manager."""
        try:
            quote = self.client.get_option_quote(trade['symbol'])
            if not quote or trade['symbol'] not in quote:
                return

            q = quote[trade['symbol']]
            current_price = round(
                (float(q.bid_price or 0) + float(q.ask_price or 0)) / 2, 2
            )

            premium = trade['premium_collected']
            if premium <= 0:
                return

            # Register with ladder if not already tracked
            pos_key = f"{trade['id']}_{trade['symbol']}"
            if not self.ladder.is_registered(pos_key):
                self.ladder.register_position(
                    pos_key, premium, trade['quantity'], side='short'
                )

            # Crash regime — close immediately (overrides ladder)
            if regime['regime_id'] == 3:
                self.logger.warning(
                    f"CRASH EXIT: {trade['symbol']} | Closing due to crash regime"
                )
                self._close_position(trade, current_price, "Crash regime exit")
                self.ladder.remove_position(pos_key)
                return

            # Time exit
            if trade.get('expiration_date'):
                remaining = calculate_dte(trade['expiration_date'][:10])
                if remaining <= 21:
                    self.logger.info(
                        f"TIME EXIT: {trade['symbol']} | {remaining} DTE remaining"
                    )
                    self._close_position(trade, current_price, f"Time exit ({remaining} DTE)")
                    self.ladder.remove_position(pos_key)
                    return

            # Ladder exit check
            result = self.ladder.check_exit(pos_key, current_price)

            if result['action'] == 'stop_loss':
                pnl = (premium - current_price) * 100 * result['contracts_to_sell']
                self.logger.warning(
                    f"LADDER STOP: {trade['symbol']} | {result['reason']} | "
                    f"Regime: {regime['regime_name']}"
                )
                self._close_position(trade, current_price, f"Ladder stop: {result['tier']}")
                self.ladder.remove_position(pos_key)

            elif result['action'] in ('sell_partial', 'sell_all'):
                qty = result['contracts_to_sell']
                pnl = (premium - current_price) * 100 * qty
                self.logger.info(
                    f"LADDER EXIT: {trade['symbol']} | {result['reason']} | "
                    f"Regime: {regime['regime_name']}"
                )
                self._close_partial(trade, current_price, qty, pnl, result['reason'])
                self.ladder.confirm_sell(pos_key, qty, current_price)

            else:
                self.logger.info(
                    f"HOLD: {trade['symbol']} | P&L: {result['profit_pct']:+.1%} | "
                    f"SL: ${result['stop_loss']:.2f} | Tier: {result['tier']} | "
                    f"Regime: {regime['regime_name']}"
                )

        except Exception as e:
            self.logger.error(f"Error monitoring {trade['symbol']}: {e}")

    def _close_position(self, trade: dict, current_price: float, reason: str):
        """Close a single position."""
        if self.dry_run:
            pnl = (trade['premium_collected'] - current_price) * 100 * trade['quantity']
            self.logger.info(
                f"[DRY RUN] Would close {trade['symbol']} | "
                f"P&L: ${pnl:.2f} | Reason: {reason}"
            )
            return

        pnl = (trade['premium_collected'] - current_price) * 100 * trade['quantity']
        order = self.client.buy_to_close(trade['symbol'], trade['quantity'], current_price)
        if order:
            self.risk_manager.close_trade(trade['id'], current_price, pnl, reason)

    def _close_partial(self, trade: dict, current_price: float, qty: int,
                       pnl: float, reason: str):
        """Close a partial number of contracts."""
        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would close {qty} of {trade['quantity']} contracts "
                f"on {trade['symbol']} | P&L: ${pnl:.2f} | Reason: {reason}"
            )
            return

        order = self.client.buy_to_close(trade['symbol'], qty, current_price)
        if order:
            self.risk_manager.close_trade(trade['id'], current_price, pnl, f"Partial: {reason}")
            self.logger.info(f"CLOSED: {trade['symbol']} | P&L: ${pnl:.2f} | {reason}")

    # ──────────────────────────────────────────────────────────────
    # HUNTING FOR NEW SPREADS
    # ──────────────────────────────────────────────────────────────

    def _hunt_for_spreads(self, regime: dict, equity: float):
        """Scan for new credit spread opportunities based on current regime."""

        # Check if regime allows trading
        if not self.current_params.get('enabled', False):
            self.logger.info(
                f"Trading DISABLED for {regime['regime_name']} regime. Skipping hunt."
            )
            return

        # High Vol regime requires mean reversion
        if regime['regime_id'] == 2:  # High Vol
            mr_cfg = self.config.get('mean_reversion', {})
            if mr_cfg.get('require_declining_vix', True) and not regime['mean_reversion']:
                self.logger.info(
                    f"HIGH VOL but VIX not declining (mean reversion: NO). "
                    "Waiting for VIX to start reverting before entry."
                )
                return
            self.logger.info("HIGH VOL + VIX declining = PRIME ENTRY ZONE!")

        # Check max positions
        open_trades = self.risk_manager.get_open_trades(strategy='regime_adaptive')
        max_spreads = self.config.get('risk', {}).get('max_concurrent_spreads', 8)
        if len(open_trades) >= max_spreads:
            self.logger.info(f"Max spreads reached ({len(open_trades)}/{max_spreads})")
            return

        # Get regime parameters
        delta = self.current_params.get('delta', 0.12)
        spread_width = self.current_params.get('spread_width', 5)
        dte_min = self.current_params.get('dte_min', 30)
        dte_max = self.current_params.get('dte_max', 45)
        size_mult = self.current_params.get('size_multiplier', 1.0)

        self.logger.info(
            f"Hunting with regime params: delta={delta}, width=${spread_width}, "
            f"DTE={dte_min}-{dte_max}, size={size_mult * 100:.0f}%"
        )

        for symbol in self.watchlist:
            # Check earnings
            earnings_buffer = self.config.get('risk', {}).get('earnings_buffer_days', 5)
            if self.earnings.has_earnings_within(symbol, dte_max + earnings_buffer):
                self.logger.info(f"SKIP {symbol}: Earnings within DTE window")
                continue

            # Check same underlying limit
            same_underlying = sum(
                1 for t in open_trades
                if t.get('underlying', '') == symbol
            )
            max_same = self.config.get('risk', {}).get('max_same_underlying', 3)
            if same_underlying >= max_same:
                self.logger.info(f"SKIP {symbol}: Max {max_same} positions on same underlying")
                continue

            try:
                self._evaluate_spread(symbol, equity, delta, spread_width,
                                      dte_min, dte_max, size_mult, regime)
            except Exception as e:
                self.logger.error(f"Error evaluating {symbol}: {e}")

    def _evaluate_spread(self, symbol: str, equity: float, delta: float,
                         spread_width: int, dte_min: int, dte_max: int,
                         size_mult: float, regime: dict):
        """Evaluate a put credit spread opportunity."""
        self.logger.info(f"Evaluating put credit spread on {symbol}...")

        # Find spread at regime-adjusted delta
        spread = self.client.find_spread_contracts(
            symbol=symbol,
            spread_type='bull_put',
            target_delta=delta,
            spread_width=spread_width,
            min_dte=dte_min,
            max_dte=dte_max,
        )

        if not spread:
            self.logger.info(f"SKIP {symbol}: No suitable spread found")
            return

        credit = spread['net_credit']
        max_loss_per = (spread_width - credit) * 100

        # 1/3 credit rule (always enforce)
        min_credit = spread_width / 3
        if credit < min_credit:
            self.logger.info(
                f"SKIP {symbol}: Credit ${credit:.2f} < ${min_credit:.2f} (1/3 rule)"
            )
            return

        # Position sizing with regime multiplier
        base_risk = equity * self.config.get('risk', {}).get('max_risk_per_trade_pct', 0.05)
        adjusted_risk = base_risk * size_mult
        num_spreads = max(1, int(adjusted_risk / max_loss_per))

        total_collateral = max_loss_per * num_spreads
        max_exposure = equity * self.config.get('risk', {}).get('max_portfolio_exposure_pct', 0.20)

        # Check total portfolio exposure
        open_trades = self.risk_manager.get_open_trades(strategy='regime_adaptive')
        current_collateral = sum(t.get('collateral_used', 0) for t in open_trades)
        if current_collateral + total_collateral > max_exposure:
            available = max_exposure - current_collateral
            if available <= 0:
                self.logger.info(f"SKIP {symbol}: Max portfolio exposure reached")
                return
            num_spreads = max(1, int(available / max_loss_per))
            total_collateral = max_loss_per * num_spreads

        # Risk approval
        approved, reason = self.risk_manager.approve_trade(
            symbol=f"{symbol}_regime",
            underlying=symbol,
            trade_type='put_credit_spread',
            max_loss=total_collateral,
            collateral_required=total_collateral,
            account_equity=equity,
        )

        if not approved:
            self.logger.info(f"REJECTED {symbol}: {reason}")
            return

        # Get expiration info
        parsed = parse_occ_symbol(spread['short_leg']['symbol'])
        expiration = parsed['expiration'] if parsed else ''
        dte = calculate_dte(expiration) if expiration else dte_min

        self.logger.info(
            f"SPREAD FOUND: {symbol} | "
            f"Regime: {regime['regime_name']} | "
            f"Credit: ${credit:.2f} × {num_spreads} = ${credit * num_spreads:.2f} | "
            f"MaxLoss: ${total_collateral:.2f} | "
            f"Delta: ~{delta} | DTE: {dte} | "
            f"Size Mult: {size_mult * 100:.0f}%"
        )

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would open {num_spreads}× put spread on {symbol}")
            return

        # Execute
        order = self.client.place_spread_order(
            short_symbol=spread['short_leg']['symbol'],
            long_symbol=spread['long_leg']['symbol'],
            qty=num_spreads,
            net_credit=credit,
        )

        if order:
            self.risk_manager.record_trade({
                'strategy': 'regime_adaptive',
                'symbol': spread['short_leg']['symbol'],
                'underlying': symbol,
                'trade_type': 'put_credit_spread',
                'side': 'sell',
                'quantity': num_spreads,
                'entry_price': credit,
                'premium_collected': credit,
                'max_loss': total_collateral,
                'collateral_used': total_collateral,
                'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expiration_date': expiration,
                'entry_regime': regime['regime_name'],
                'entry_vix': regime['vix_level'],
                'entry_confidence': regime['confidence'],
            })

            self.logger.info(
                f"SPREAD OPENED: {symbol} | {num_spreads} contracts | "
                f"Credit: ${credit * num_spreads * 100:.2f} | "
                f"Regime: {regime['regime_name']}"
            )

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

    def _log_summary(self, regime: dict):
        """Log end-of-cycle summary."""
        summary = self.risk_manager.get_performance_summary(strategy='regime_adaptive')
        open_trades = self.risk_manager.get_open_trades(strategy='regime_adaptive')

        self.logger.info(
            f"Summary: {len(open_trades)} positions | "
            f"Regime: {regime['regime_name']} | "
            f"VIX: {regime['vix_level']:.1f} | "
            f"Total Trades: {summary.get('total_trades', 0)} | "
            f"Total P&L: ${summary.get('total_pnl', 0) or 0:.2f}"
        )


def main():
    parser = argparse.ArgumentParser(description='VIX-Regime Adaptive ML Bot')
    parser.add_argument('--config', default='config.json', help='Config file')
    parser.add_argument('--dry-run', action='store_true', help='Preview mode')
    parser.add_argument('--symbol', default=None, help='Single symbol override')
    parser.add_argument('--retrain', action='store_true', help='Retrain model first')
    args = parser.parse_args()

    bot = RegimeAdaptiveBot(
        config_path=args.config,
        dry_run=args.dry_run,
        symbol=args.symbol,
        retrain=args.retrain,
    )
    bot.run()


if __name__ == '__main__':
    main()
