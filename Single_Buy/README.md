# Rajat Alpha v67 - Single Buy Trading Bot

## 📋 Overview

Rajat Alpha v67 is a sophisticated algorithmic trading bot implementing a single-buy entry strategy with dynamic trailing stop losses and partial profit taking for swing trading in US equities using the Alpaca API.

**Current Status:** ✅ Production Ready (Paper Trading Mode)  
**Version:** 1.0  
**Last Updated:** February 16, 2026

## 🎯 Key Features

- **Automated Signal Detection**: Technical analysis-based entry signals
- **Risk Management**: Configurable stop losses and position sizing
- **Portfolio Monitoring**: Real-time position tracking and analytics
- **Web Dashboard**: Flask-based UI for monitoring performance
- **Compliance Logging**: JSON-formatted audit trails
- **Flexible Configuration**: JSON-based configuration system

## 📁 Project Structure

```
Single_Buy/
├── rajat_alpha_v67_single.py    # 🤖 Main trading bot
├── requirements.txt              # 📦 Python dependencies
├── README.md                     # 📖 This file
│
├── config/                       # ⚙️ Configuration Files
│   ├── config.json              # Main bot configuration
│   ├── watchlist.txt            # Stocks to monitor
│   ├── exclusionlist.txt        # Stocks to exclude
│   └── selllist.txt             # Priority sell symbols
│
├── db/                           # 💾 Database Files
│   ├── positions.db             # Main production database
│   ├── test_positions.db        # Test database
│   ├── rajat_alpha_v67.db       # Legacy database
│   └── trading.db               # Alternative database
│
├── logs/                         # 📝 Log Files
│   ├── rajat_alpha_v67.log      # Main application log (JSON format)
│   └── audit.log                # Audit log (WARNING+ only)
│
├── scripts/                      # 🛠️ Utility Scripts
│   ├── db_manager.py            # Database query and management
│   ├── cleanup_db.py            # Database maintenance
│   └── signal_dashboard.py      # Signal monitoring dashboard
│
├── tests/                        # 🧪 Test Files
│   ├── test_bot.py              # Main bot unit tests
│   ├── test_comprehensive.py    # Integration tests
│   └── test_analysis.py         # Analysis tool tests
│
├── tools/                        # 📊 Analysis Tools
│   ├── watchlist_analyzer.py    # Analyze watchlist stocks
│   ├── benchmark_analyzer.py    # Data quality checks
│   └── stock_analyzer.py        # Individual stock analysis
│
├── docs/                         # 📚 Documentation
│   ├── QUICKSTART.md            # Quick start guide
│   ├── IMPLEMENTATION_SUMMARY.md # Implementation details
│   └── README_COMPLETE_GUIDE.md # Comprehensive guide
│
└── enterprise_features/          # 🏢 Advanced Features
    ├── risk_management/         # VaR calculations
    │   ├── var_calculator.py
    │   └── __init__.py
    └── ui_dashboard/            # Flask web dashboard
        ├── app.py
        ├── templates/
        ├── test_signals_api.py
        └── __init__.py
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Alpaca trading account (paper or live)
- Windows, Linux, or macOS

### Installation

1. **Install Dependencies**
   ```bash
   cd Single_Buy
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   
   Edit `config/config.json`:
   ```json
   {
     "api": {
       "key_id": "YOUR_ALPACA_KEY_ID",
       "secret_key": "YOUR_ALPACA_SECRET_KEY",
       "base_url": "https://paper-api.alpaca.markets"
     }
   }
   ```

3. **Set Up Watchlist**
   
   Edit `config/watchlist.txt` (one symbol per line):
   ```
   AAPL
   MSFT
   GOOGL
   TSLA
   NVDA
   ```

4. **Run the Bot**
   ```bash
   python rajat_alpha_v67_single.py
   ```

5. **Monitor Performance**
   ```bash
   # View open positions
   python scripts/db_manager.py --positions-open
   
   # View recent signals
   python scripts/db_manager.py --signals
   
   # View performance stats
   python scripts/db_manager.py --stats
   
   # Complete dashboard
   python scripts/db_manager.py --all
   ```

6. **Launch Web Dashboard**
   ```bash
   python -m enterprise_features.ui_dashboard.app
   ```
   Access at: http://localhost:5000

## 📖 Usage Guide

### Main Trading Bot

```bash
# Run the bot (continuous monitoring)
python rajat_alpha_v67_single.py
```

The bot will:
- Scan watchlist stocks every 2 minutes (1 minute during last hour)
- Detect entry signals based on strategy rules
- Execute trades when conditions are met
- Monitor open positions for exit conditions
- Log all activity to `logs/rajat_alpha_v67.log`

### Database Manager (`scripts/db_manager.py`)

Replaces: `check_db.py`, `query_db.py`, `check_signals.py`, `check_trades.py`, `check_recent_signals.py`, `check_valid_signals.py`

```bash
# Show all tables and schemas
python scripts/db_manager.py --tables

# Show all positions
python scripts/db_manager.py --positions

# Show only open positions
python scripts/db_manager.py --positions-open

# Show only closed positions
python scripts/db_manager.py --positions-closed

# Show recent signals (last 20)
python scripts/db_manager.py --signals

# Show only valid signals (score >= 2)
python scripts/db_manager.py --signals-valid

# Show today's signals
python scripts/db_manager.py --signals-today

# Show performance statistics
python scripts/db_manager.py --stats

# Show complete dashboard (recommended)
python scripts/db_manager.py --all

# Change result limit (default: 20)
python scripts/db_manager.py --signals --limit 50
```

### Signal Dashboard (`scripts/signal_dashboard.py`)

Replaces: `signals_dashboard.py`

```bash
# Show today's signals dashboard
python scripts/signal_dashboard.py

# Show specific date
python scripts/signal_dashboard.py --date 2026-02-15

# Watch mode (auto-refresh every 60 seconds)
python scripts/signal_dashboard.py --watch
```

### Database Cleanup (`scripts/cleanup_db.py`)

Replaces: `cleanup_signals.py`

```bash
# Remove invalid signals (score <= 0)
python scripts/cleanup_db.py --remove-invalid

# Archive old positions (90+ days)
python scripts/cleanup_db.py --archive 90

# Vacuum database (reclaim space)
python scripts/cleanup_db.py --vacuum

# Verify database integrity
python scripts/cleanup_db.py --verify

# Run all cleanup operations
python scripts/cleanup_db.py --all
```

### Analysis Tools

```bash
# Analyze watchlist stocks
python tools/watchlist_analyzer.py

# Check data quality/benchmarks
python tools/benchmark_analyzer.py

# Analyze individual stock
python tools/stock_analyzer.py
```

### Testing

```bash
# Run main bot tests
python tests/test_bot.py

# Run comprehensive tests
python tests/test_comprehensive.py

# Run analysis tests
python tests/test_analysis.py
```

## ⚙️ Configuration

### Main Configuration (`config/config.json`)

Key sections:

#### API Configuration
```json
"api": {
  "key_id": "YOUR_KEY",
  "secret_key": "YOUR_SECRET",
  "base_url": "https://paper-api.alpaca.markets"
}
```

#### Trading Rules
```json
"trading_rules": {
  "max_open_positions": 10,
  "max_trades_per_stock": 2,
  "max_trades_per_day": 3,
  "min_signal_score": 2,
  "prevent_same_day_reentry": true
}
```

#### Position Sizing
```json
"position_sizing": {
  "mode": "percent_equity",
  "percent_of_equity": 0.10
}
```

#### Strategy Parameters
```json
"strategy_params": {
  "min_listing_days": 200,
  "sma_fast": 50,
  "sma_slow": 200,
  "ema_trend": 21,
  "ma_touch_threshold_pct": 0.025
}
```

#### Risk Management
```json
"risk_management": {
  "initial_stop_loss_pct": 0.17,
  "tier_1_profit_pct": 0.05,
  "tier_1_stop_loss_pct": 0.09,
  "tier_2_profit_pct": 0.10,
  "tier_2_stop_loss_pct": 0.01,
  "max_hold_days": 21
}
```

#### Profit Taking
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

See `docs/README_COMPLETE_GUIDE.md` for full configuration details.

### Watchlist Files

#### `config/watchlist.txt`
One symbol per line:
```
AAPL
MSFT
GOOGL
```

#### `config/exclusionlist.txt`
Symbols to exclude (with comments):
```
# Stocks to skip
TSLA
NVDA
```

#### `config/selllist.txt`
Priority symbols for sell monitoring:
```
AAPL
MSFT
```

## 📊 Strategy Overview

### Entry Requirements (ALL must be TRUE)

1. **Market Structure**: 50 SMA > 200 SMA AND 21 EMA ≥ 50 SMA * (1 - tolerance)
2. **Pullback Detection**: Price within 2.5% of 21 EMA or 50 SMA
3. **Signal Confirmation**: Explosive pattern (Engulfing/Piercing/Tweezer) OR touch signal
4. **Multi-Timeframe**: Weekly close > Weekly EMA21 AND Monthly close > Monthly EMA10
5. **Maturity Filter**: Stock traded ≥ 200 days
6. **Volume Check**: Above 21-day average
7. **Green Candle**: Current price > previous close
8. **Scoring**: Minimum score threshold (default: 2.0)

### Exit Management

- **Dynamic Trailing Stop**: 17% → 9% @ +5% profit → 1% @ +10% profit
- **Partial Exits**: 33.3% @ +10%, 33.3% @ +15%, 33.4% @ +20%
- **Time Exit Signal**: Maximum hold period (default: 21 days)
- **Stop Loss Mode**: Closing basis (recommended)

### Scoring System (0-7 points)

**Base Score (0-5):**
1. RSI(14) > 50
2. Weekly close > Weekly EMA21
3. Monthly close > Monthly EMA10
4. Volume > 21-day average
5. Price within 3.5% above 21-day low

**Bonus Points (0-2):**
- EMA21 touch: +1.0
- SMA50 touch: +1.0

**Signal Quality:**
- 0-2: Poor (avoid)
- 3-4: Moderate (acceptable)
- 5-6: High (preferred)
- 6-7: Exceptional (optimal)

## 💾 Database Schema

### `positions` Table
Tracks all trading positions:
- `id`: Unique identifier
- `symbol`: Stock ticker
- `entry_date`, `entry_price`: Entry details
- `quantity`, `remaining_qty`: Position sizes
- `stop_loss`: Current stop loss price
- `status`: 'OPEN' or 'CLOSED'
- `exit_date`, `exit_price`: Exit details
- `profit_loss_pct`: Realized P&L
- `score`, `pattern`: Signal details

### `partial_exits` Table
Tracks partial profit taking:
- `position_id`: Links to positions
- `exit_date`, `exit_price`: Exit details
- `quantity`: Shares sold
- `profit_target`: 'PT1', 'PT2', or 'PT3'

### `signal_history` Table
Tracks all detected signals:
- `symbol`: Stock ticker
- `signal_date`: Detection date
- `score`: Signal quality score
- `pattern`: Detected pattern
- `executed`: Whether trade was executed

## 🧪 Testing

### Run All Tests
```bash
# Main bot tests
python tests/test_bot.py

# Comprehensive integration tests
python tests/test_comprehensive.py

# Analysis tool tests
python tests/test_analysis.py
```

### Test Coverage
- ✅ Database operations
- ✅ Configuration loading
- ✅ Pattern detection
- ✅ Signal analysis
- ✅ Entry/exit logic
- ✅ Risk management

## 🔧 Troubleshooting

### Common Issues

**Database Not Found**
```bash
# Make sure you're in the Single_Buy directory
cd Single_Buy
python scripts/db_manager.py --verify
```

**Configuration Errors**
- Verify JSON syntax in `config/config.json`
- Check API keys are correct
- Ensure watchlist file exists

**API Connection Issues**
- Verify internet connectivity
- Check Alpaca account status
- Confirm API keys have proper permissions

**No Signals Detected**
- Check watchlist has valid symbols
- Verify market hours (signals detected during trading hours)
- Review logs in `logs/rajat_alpha_v67.log`

###Log Analysis

```bash
# View recent log entries
tail -n 100 logs/rajat_alpha_v67.log

# Search for errors (Windows PowerShell)
Select-String "ERROR" logs\rajat_alpha_v67.log

# Search for signals (Windows PowerShell)
Select-String "VALID BUY SIGNAL" logs\rajat_alpha_v67.log
```

## 📈 Performance Monitoring

### View Statistics
```bash
python scripts/db_manager.py --stats
```

Shows:
- Overall win rate and average P/L
- Performance by signal score
- Performance by pattern type
- Current open positions
- Recent signal activity

### Web Dashboard
```bash
python -m enterprise_features.ui_dashboard.app
```

Features:
- Real-time portfolio view
- Performance charts
- Signal history
- Risk metrics (VaR)

## 🚨 Risk Disclaimers

⚠️ **IMPORTANT - READ BEFORE USING:**

1. **Trading Risk**: All trading involves substantial risk of loss. Past performance does not guarantee future results.

2. **Testing Required**: Always test thoroughly in paper trading mode before deploying to live trading.

3. **No Guarantees**: This software is provided "as-is" without any guarantees or warranty.

4. **Your Responsibility**: You are solely responsible for all trading decisions and their outcomes.

5. **Start Small**: When switching to live trading, start with small position sizes and monitor closely.

## 📝 Change Log

### Version 1.0 (February 16, 2026)
- ✅ Complete project reorganization
- ✅ Consolidated 7 redundant scripts into 3 unified utilities
- ✅ Created proper directory structure (db/, logs/, scripts/, tests/, tools/)
- ✅ Updated all file references to new paths
- ✅ Added comprehensive README with usage examples
- ✅ Moved documentation to docs/ folder
- ✅ Created database manager, cleanup, and dashboard utilities
- ✅ Organized tests and analysis tools

### Version 0.9 (January 2026)
- Initial implementation
- Core strategy and risk management
- Database tracking
- Web dashboard
- Enterprise features

## 📚 Additional Documentation

- **Quick Start**: `docs/QUICKSTART.md`
- **Full Guide**: `docs/README_COMPLETE_GUIDE.md`
- **Implementation Details**: `docs/IMPLEMENTATION_SUMMARY.md`

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in `logs/` directory
3. Consult the complete guide in `docs/`
4. Test in paper trading mode first

## 📄 License

For educational and research purposes. Use at your own risk.

---

**Remember**: Always test thoroughly in paper trading mode before deploying to live markets. Start small and monitor performance closely.
