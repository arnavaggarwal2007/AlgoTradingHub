# Rajat Alpha V67 Dual Buy Trading Bot

A sophisticated algorithmic trading bot for Alpaca markets, implementing dual-buy strategies with capital-based position management, PineScript-inspired signals, and comprehensive risk controls.

## Strategy Overview

### Core Strategy: Dual Buy with Capital Management
The Rajat Alpha V67 implements a sophisticated **dual-buy system** inspired by PineScript trading strategies. The bot can hold up to two positions per stock:
- **B1 (Primary Buy)**: Initial entry when all conditions are met
- **B2 (Secondary Buy)**: Additional position only when B1 is active and score meets higher threshold

### Key Features
- **Capital-Based Position Limits**: Total positions dynamically calculated as `floor(total_equity / position_size)`
- **Per-Stock Limits**: Maximum 1 B1 + 1 B2 per stock (configurable)
- **Daily Buy Limits**: Maximum 3 buys per day (configurable), prioritized by signal score (higher first)
- **Signal Prioritization**: Collects signals over monitoring window, sorts by score, executes top opportunities
- **Risk Management**: 3-tier trailing stops, partial exits, time-based exits, capital utilization caps

### Example Scenarios
- **Capital $10,000, 5% position size**: Max 20 total positions (any B1/B2 mix)
- **Per stock**: Max 2 positions (1 B1 + 1 B2)
- **Daily trading**: Max 3 buys, prioritized by highest-scoring signals
- **Capital utilization**: Hard cap at 50% equity deployment

## Detailed Strategy Logic

### Entry Signal Requirements
A stock must pass ALL of the following checks to generate a buy signal:

#### 1. Market Structure Check
- **SMA50 > SMA200**: Stock must be in an uptrend
- **EMA21 > SMA50**: Short-term momentum must be bullish
- **Purpose**: Ensures we're only buying stocks in established uptrends

#### 2. Multi-Timeframe Confirmation
- **Weekly**: Close > Weekly EMA21 (21-period)
- **Monthly**: Close > Monthly EMA10 (10-period)
- **Purpose**: Confirms bullish momentum across higher timeframes

#### 3. Pullback Detection
- **Near Moving Averages**: Price within 2.5% of EMA21 or SMA50
- **Recent High Check**: Must have made a higher high in the last 4 days
- **Purpose**: Identifies stocks pulling back to support levels in uptrends

#### 4. Explosive Pattern Recognition
- **Supported Patterns**: Engulfing, Piercing, Tweezer Bottom, and other bullish reversal patterns
- **Purpose**: Confirms the pullback has strong reversal potential

#### 5. Stalling Filter
- **Long-term Range**: 8-day range < 5% (prevents buying overextended stocks)
- **Short-term Consolidation**: 3-day range < 5% (allows for tight consolidation)
- **Purpose**: Avoids stocks that are stalling or have run too far

#### 6. Extended Stock Filter (Optional)
- **Gap Check**: Prevents buying stocks that gapped up >4% from previous close
- **Lookback**: Checks gap over configurable days
- **Purpose**: Avoids stocks that have already "run away"

### Signal Rating System (0-5 Scale + Bonuses)

#### Base Score Components (0-5 points):
1. **Performance vs Benchmark (1 point)**:
   - Compares 22-day performance vs QQQ/SPY
   - Falls back to SPY if QQQ data unavailable
   - +1 if stock outperforms benchmark

2. **Weekly Confirmation (1 point)**:
   - +1 if weekly close > weekly EMA21

3. **Monthly Confirmation (1 point)**:
   - +1 if monthly close > monthly EMA10

4. **Volume Confirmation (1 point)**:
   - +1 if current volume > 21-day average volume

5. **Demand Zone (1 point)**:
   - +1 if current low is within 3.5% of 21-day low
   - Indicates institutional accumulation

#### Bonus Points (0.5 each):
- **EMA21 Touch Bonus**: +0.5 if price touched EMA21 since last trend reset
- **SMA50 Touch Bonus**: +0.5 if price touched SMA50 since last trend reset

#### Touch Tracking System:
- **Reset Condition**: Counters reset when SMA50 crosses above SMA200 (new trend)
- **Touch Detection**: Price within 2.5% of moving average
- **Purpose**: Rewards stocks that have tested support levels multiple times

### Dual Buy Logic
- **B1 Entry**: Requires score ≥ minimum B1 score (default 3), no active B1, within per-stock limits
- **B2 Entry**: Requires active B1 in same stock, score ≥ minimum B2 score (default 3), within per-stock limits
- **Priority**: B1 takes precedence over B2 for new stocks

### Position Sizing
- **Base Size**: Configurable % of equity (default 5%)
- **Capital Conservation**: Reduces size by 50% when utilization >70% of max
- **Max Loss Limits**: Respects per-trade loss limits
- **Utilization Cap**: Prevents exceeding max equity utilization

### Exit Strategy
- **Stop Loss**: Initial 17% below entry, trails with profits
- **3-Tier Trailing Stops**:
  - Tier 1: ≥5% profit → 9% stop loss
  - Tier 2: ≥10% profit → 1% stop loss
  - Tier 3: ≥20% profit → 1% stop loss (maintains profits)
- **Partial Exits**: Takes profits at 10%, 15%, 20% targets
- **Time Exit**: Forces exit after 21 days (configurable per B1/B2)
- **Stop Loss Mode**: Closing basis (uses daily close for trigger)

### Risk Management Features
- **Daily Trade Limits**: Maximum buys per day (default 3)
- **Per-Stock Limits**: Maximum positions per stock (1 B1 + 1 B2)
- **Capital Limits**: Maximum equity utilization (default 50%)
- **Same-Day Protection**: Prevents re-entry on same day
- **Exclusion Lists**: Manual stock exclusions
- **Watchlist Filtering**: Only trades specified stocks

### Execution Logic
- **Signal Collection**: Monitors watchlist during buy window
- **Prioritization**: Sorts signals by score (highest first)
- **Execution**: Executes top N signals respecting all limits
- **Buy Window**: Configurable time windows (default: last hour)
- **Smart Execution**: Validates signals before execution

## Configuration Guide

All settings are in `config_dual.json`. Below are all parameters with descriptions, example values, and usage notes.

### API Configuration
```json
"api": {
  "key_id": "YOUR_ALPACA_KEY_ID",
  "secret_key": "YOUR_ALPACA_SECRET_KEY",
  "base_url": "https://paper-api.alpaca.markets"
}
```
- **key_id**: Your Alpaca API key
- **secret_key**: Your Alpaca secret key
- **base_url**: Use paper trading URL for testing, live URL for production

### Trading Rules
```json
"trading_rules": {
  "max_b1_per_stock": 1,
  "max_b2_per_stock": 1,
  "max_daily_buys": 3,
  "min_score_b1": 3,
  "score_b2_min": 3,
  "prevent_same_day_reentry": true,
  "watchlist_file": "watchlist.txt",
  "exclusion_file": "exclusionlist.txt",
  "sell_watchlist_file": "selllist.txt",
  "log_excluded_symbols": true,
  "portfolio_mode": "watchlist_only",
  "max_equity_utilization_pct": 0.50,
  "enable_dynamic_position_limits": true,
  "capital_conservation_mode": false
}
```

#### Position Limits
- **max_b1_per_stock**: `1` - Maximum B1 positions per stock
- **max_b2_per_stock**: `1` - Maximum B2 positions per stock
- **max_daily_buys**: `3` - Maximum buy orders per trading day
- **max_equity_utilization_pct**: `0.50` - Maximum equity utilization (50%)
- **enable_dynamic_position_limits**: `true` - Enable capital-based dynamic limits
- **capital_conservation_mode**: `false` - Reduce position sizes when nearing utilization limits

#### Signal Thresholds
- **min_score_b1**: `3` - Minimum score required for B1 entry (1-5 scale)
- **score_b2_min**: `3` - Minimum score required for B2 entry (higher than B1)

#### Portfolio Management
- **prevent_same_day_reentry**: `true` - Prevent buying same stock twice in one day
- **watchlist_file**: `"watchlist.txt"` - File containing symbols to monitor
- **exclusion_file**: `"exclusionlist.txt"` - Symbols to exclude from trading
- **sell_watchlist_file**: `"selllist.txt"` - Symbols to prioritize for selling
- **log_excluded_symbols**: `true` - Log excluded symbols in output
- **portfolio_mode**: `"watchlist_only"` - Trading mode (`watchlist_only`, `specific_stocks`)

### Position Sizing
```json
"position_sizing": {
  "mode": "percent_equity",
  "percent_of_equity": 0.05,
  "fixed_amount": 5000,
  "base_amount": 50000,
  "percent_of_amount": 0.03
}
```
- **mode**: `"percent_equity"` - Sizing mode (`percent_equity`, `fixed_dollar`, `percent_of_amount`)
- **percent_of_equity**: `0.05` - Position size as % of total equity (5%)
- **fixed_amount**: `5000` - Fixed dollar amount per position
- **base_amount**: `50000` - Base amount for percentage calculations
- **percent_of_amount**: `0.03` - Position size as % of base amount

### Strategy Parameters
```json
"strategy_params": {
  "min_signal_score": 3,
  "min_listing_days": 200,
  "sma_fast": 50,
  "sma_slow": 200,
  "ema_trend": 21,
  "pullback_days": 4,
  "pullback_pct": 5.0,
  "stalling_days_long": 8,
  "stalling_days_short": 3,
  "stalling_range_pct": 5.0,
  "enable_extended_filter": true,
  "max_gap_pct": 0.04,
  "lookback_for_gap": 1
}
```
- **min_signal_score**: `3` - Minimum signal score for consideration
- **min_listing_days**: `200` - Minimum days stock has been listed
- **sma_fast/sma_slow**: `50/200` - Fast/slow SMA periods for trend analysis
- **ema_trend**: `21` - EMA period for trend confirmation
- **pullback_days**: `4` - Days to look back for pullback analysis
- **pullback_pct**: `5.0` - Maximum pullback percentage
- **stalling_days_long/short**: `8/3` - Days for stalling detection
- **stalling_range_pct**: `5.0` - Maximum range for stalling
- **enable_extended_filter**: `true` - Enable additional filtering
- **max_gap_pct**: `0.04` - Maximum gap percentage allowed
- **lookback_for_gap**: `1` - Days to look back for gap analysis

### Risk Management
```json
"risk_management": {
  "initial_stop_loss_pct": 0.17,
  "tier_1_profit_pct": 0.05,
  "tier_1_stop_loss_pct": 0.09,
  "tier_2_profit_pct": 0.10,
  "tier_2_stop_loss_pct": 0.01,
  "tes_days_b1": 21,
  "tes_days_b2": 21,
  "stop_loss_mode": "closing_basis",
  "max_loss_mode": "percent",
  "max_loss_pct": 0.02,
  "max_loss_dollars": 500
}
```
- **initial_stop_loss_pct**: `0.17` - Initial stop loss percentage (17%)
- **tier_1/2_profit_pct**: `0.05/0.10` - Profit levels for trailing stop adjustments
- **tier_1/2_stop_loss_pct**: `0.09/0.01` - Stop loss levels for each tier
- **tes_days_b1/b2**: `21/21` - Time Exit Signal days for B1/B2 positions
- **stop_loss_mode**: `"closing_basis"` - Stop loss trigger mode
- **max_loss_mode**: `"percent"` - Max loss calculation mode
- **max_loss_pct**: `0.02` - Maximum loss as percentage of equity
- **max_loss_dollars**: `500` - Maximum loss in dollars

### Profit Taking
```json
"profit_taking": {
  "enable_partial_exits": true,
  "target_1_pct": 0.10,
  "target_1_qty": 0.333,
  "target_2_pct": 0.15,
  "target_2_qty": 0.333,
  "target_3_pct": 0.20,
  "target_3_qty": 0.334
}
```
- **enable_partial_exits**: `true` - Enable partial profit taking
- **target_1/2/3_pct**: `0.10/0.15/0.20` - Profit target percentages
- **target_1/2/3_qty**: `0.333/0.333/0.334` - Quantity to sell at each target

### Execution Schedule
```json
"execution_schedule": {
  "buy_window_preset": "last_hour",
  "buy_window_start_time": "15:00",
  "buy_window_end_time": "15:59",
  "custom_window_minutes": 60,
  "custom_window_position": "end",
  "enable_smart_execution": true,
  "signal_monitoring_minutes": 15,
  "top_n_trades": 5,
  "sort_by": "score",
  "default_interval_seconds": 120,
  "last_hour_interval_seconds": 60
}
```
- **buy_window_preset**: `"last_hour"` - Predefined buy window
- **buy_window_start/end_time**: `"15:00"/"15:59"` - Custom window times
- **custom_window_minutes**: `60` - Custom window duration
- **custom_window_position**: `"end"` - Window position relative to market close
- **enable_smart_execution**: `true` - Enable smart execution features
- **signal_monitoring_minutes**: `15` - Minutes to monitor signals
- **top_n_trades**: `5` - Number of top trades to consider
- **sort_by**: `"score"` - Sorting criteria for trades
- **default/last_hour_interval_seconds**: `120/60` - Scan intervals

## Installation and Setup

### Prerequisites
- Python 3.8+
- Alpaca account (paper or live)
- Required packages: `pip install alpaca-py pandas numpy pytz`

### Local Setup
1. Clone/download the bot files
2. Update `config_dual.json` with your Alpaca credentials
3. Create watchlist files:
   - `watchlist.txt`: Symbols to monitor (one per line)
   - `exclusionlist.txt`: Symbols to exclude
   - `selllist.txt`: Symbols to prioritize selling
4. Run: `python rajat_alpha_v67_dual.py`

### AWS Deployment

#### Option 1: EC2 Instance
1. Launch EC2 instance (t3.micro for testing, t3.small+ for production)
2. Install dependencies:
   ```bash
   sudo yum update -y
   sudo yum install python3 python3-pip -y
   pip3 install alpaca-py pandas numpy pytz
   ```
3. Upload bot files to instance
4. Configure `config_dual.json`
5. Run with nohup:
   ```bash
   nohup python3 rajat_alpha_v67_dual.py &
   ```

#### Option 2: Lambda (Serverless)
1. Create Lambda function with Python 3.8+ runtime
2. Package dependencies in deployment package
3. Set environment variables for config
4. Use EventBridge for scheduling
5. Monitor via CloudWatch logs

### DigitalOcean Deployment

#### Droplet Setup
1. Create Droplet (Basic plan, $6/month)
2. SSH into droplet
3. Install dependencies:
   ```bash
   apt update
   apt install python3 python3-pip -y
   pip3 install alpaca-py pandas numpy pytz
   ```
4. Upload bot files via SCP or Git
5. Configure `config_dual.json`
6. Run with screen/tmux:
   ```bash
   screen -S trading-bot
   python3 rajat_alpha_v67_dual.py
   Ctrl+A+D to detach
   ```

#### App Platform (Managed)
1. Connect GitHub repository
2. Set build command: `pip install -r requirements.txt`
3. Set run command: `python rajat_alpha_v67_dual.py`
4. Configure environment variables
5. Deploy and monitor

## Monitoring and Maintenance

### Logs
- Check console output for real-time updates
- Logs include position entries, exits, signal detection
- Monitor for error messages and API issues

### Database
- SQLite database tracks all positions and trades
- Backup regularly for record-keeping
- Check position status via database queries

### Performance Monitoring
- Track win/loss ratio, average profit per trade
- Monitor capital utilization vs. limits
- Review signal accuracy and score distribution

### Troubleshooting
- **No signals detected**: Check market hours, watchlist validity
- **API errors**: Verify credentials, check rate limits
- **Position limits hit**: Review capital utilization, adjust config
- **Daily limits reached**: Monitor trading frequency, adjust limits

## Risk Warnings

- This bot trades with real money when using live credentials
- Past performance does not guarantee future results
- Always test with paper trading first
- Monitor positions closely, especially during volatile markets
- Set appropriate stop losses and position sizes for your risk tolerance

## Support

For issues or questions:
1. Check logs for error messages
2. Verify configuration settings
3. Test with paper trading
4. Review Alpaca API documentation