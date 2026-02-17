# Rajat Alpha v67 - Alpaca Trading Bot

## Complete Setup & Configuration Guide

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration Guide](#configuration-guide)
4. [Strategy Logic](#strategy-logic)
5. [Running the Bot](#running-the-bot)
6. [Database Management](#database-management)
7. [Troubleshooting](#troubleshooting)

---

## Overview

**Rajat Alpha v67** is a production-ready algorithmic trading bot for the Alpaca trading platform. It implements a single buy entry strategy with:

- **Dynamic 3-Tier Trailing Stop Loss** (17% → 9% → 1%)
- **Partial Profit Exits** (1/3 Rule: 33.3% @ 10%, 33.3% @ 15%, 33.4% @ 20%)
- **FIFO Selling** (First In First Out)
- **Multi-Timeframe Confirmation** (Daily + Weekly + Monthly)
- **Pattern Recognition** (Engulfing, Piercing, Tweezer Bottom)
- **Scoring System** (0-5 + bonuses)
- **Stalling Filter** (Avoids sideways consolidations)

---

## Installation

### 1. Requirements

- **Python 3.8+**
- **Alpaca Trading Account** (paper or live)

### 2. Install Dependencies

```bash
pip install alpaca-py pandas pandas-ta pytz
```

### 3. Project Structure

```
Alpaca_Algo/
├── rajat_alpha_v67.py          # Main trading bot
├── config_enhanced.json        # Configuration file
├── watchlist.txt               # Stock symbols to scan
├── positions.db                # SQLite database (auto-created)
└── rajat_alpha_v67.log         # Log file (auto-created)
```

---

## Configuration Guide

### config_enhanced.json Structure

#### **1. API Settings**

```json
"api": {
  "key_id": "YOUR_ALPACA_API_KEY",
  "secret_key": "YOUR_ALPACA_SECRET_KEY",
  "base_url": "https://paper-api.alpaca.markets"  // Paper trading
  // For live: "https://api.alpaca.markets"
}
```

**Get API Keys:**
1. Sign up at [Alpaca Markets](https://alpaca.markets)
2. Navigate to **Paper Trading** or **Live Trading**
3. Generate API keys
4. Copy Key ID and Secret Key

---

#### **2. Trading Rules**

```json
"trading_rules": {
  "max_open_positions": 2,            // Maximum concurrent positions
  "max_trades_per_stock": 2,          // Max positions per symbol
  "watchlist_file": "watchlist.txt",  // File with stock symbols
  "portfolio_mode": "watchlist_only", // "watchlist_only" or "specific_stocks"
  "specific_stocks": []               // If mode is "specific_stocks", list here
}
```

**Options:**
- `portfolio_mode`:
  - `"watchlist_only"`: Scan all symbols in watchlist.txt
  - `"specific_stocks"`: Only trade symbols in `specific_stocks` array

---

#### **3. Position Sizing**

```json
"position_sizing": {
  "mode": "percent_equity",      // "percent_equity", "fixed_dollar", or "percent_of_amount"
  "percent_of_equity": 0.10,     // 10% of account equity per trade
  "fixed_amount": 5000,          // $5000 per trade (if mode is "fixed_dollar")
  "base_amount": 50000,          // Base amount for percentage calculation
  "percent_of_amount": 0.03      // 3% of base_amount ($50k * 3% = $1500/trade)
}
```

**Modes Explained:**
1. **percent_equity**: Each trade = X% of account equity
   - Example: $100k account, 10% = $10k per trade
2. **fixed_dollar**: Fixed dollar amount per trade
   - Example: Always invest $5000 per trade
3. **percent_of_amount**: X% of a defined base amount
   - Example: 3% of $50k = $1500 per trade (conservative)

---

#### **4. Strategy Parameters**

```json
"strategy_params": {
  "min_listing_days": 200,          // Minimum trading history (maturity filter)
  "sma_fast": 50,                   // Fast moving average (50 SMA)
  "sma_slow": 200,                  // Slow moving average (200 SMA)
  "ema_trend": 21,                  // Trend EMA (21 EMA)
  "pullback_days": 4,               // Lookback for pullback detection
  "pullback_pct": 5.0,              // Pullback percentage threshold
  "stalling_days_long": 8,          // 8-day consolidation check
  "stalling_days_short": 3,         // 3-day recent consolidation check
  "stalling_range_pct": 5.0         // 5% range = stalling
}
```

**Filters:**
- **Maturity**: Stock must have >= 200 days of trading history
- **Stalling**: Rejects stocks in 8-day consolidation UNLESS recent 3-day also consolidating

---

#### **5. Risk Management**

```json
"risk_management": {
  "initial_stop_loss_pct": 0.17,     // 17% initial stop loss
  "tier_1_profit_pct": 0.05,         // Tier 1 trigger: +5% profit
  "tier_1_stop_loss_pct": 0.09,      // Tier 1 SL: 9% below entry
  "tier_2_profit_pct": 0.10,         // Tier 2 trigger: +10% profit
  "tier_2_stop_loss_pct": 0.01,      // Tier 2 SL: 1% below entry (near breakeven)
  "max_hold_days": 21,               // Time Exit Signal (TES) at 21 days
  "stop_loss_mode": "closing_basis", // "closing_basis" or "intraday_basis"
  "max_loss_mode": "percent",        // "percent" or "dollar"
  "max_loss_pct": 0.02,              // Max 2% loss per trade (if mode is "percent")
  "max_loss_dollars": 500            // Max $500 loss per trade (if mode is "dollar")
}
```

**3-Tier Trailing Stop Loss:**
1. **Initial**: -17% below entry (protects from big drops)
2. **Tier 1**: When +5% profit → SL moves to -9% below entry
3. **Tier 2**: When +10% profit → SL moves to -1% below entry (locks in ~9% profit)

**Stop Loss Mode:**
- `closing_basis`: SL triggers on closing price (default)
- `intraday_basis`: SL triggers on intraday low (more aggressive)

**Max Loss Per Trade:**
- `percent`: Limits position size so max loss = X% of equity
- `dollar`: Limits position size so max loss = $X

---

#### **6. Profit Taking (Partial Exits)**

```json
"profit_taking": {
  "enable_partial_exits": true,   // Enable 1/3 Rule partial exits
  "target_1_pct": 0.10,           // PT1: +10% profit
  "target_1_qty": 0.333,          // Sell 33.3% at PT1
  "target_2_pct": 0.15,           // PT2: +15% profit
  "target_2_qty": 0.333,          // Sell 33.3% at PT2
  "target_3_pct": 0.20,           // PT3: +20% profit
  "target_3_qty": 0.334           // Sell remaining 33.4% at PT3
}
```

**1/3 Rule (Default):**
- **PT1** @ +10%: Sell 1/3 (lock in partial profit)
- **PT2** @ +15%: Sell another 1/3
- **PT3** @ +20%: Sell final 1/3

**Alternative: 1/4 Rule** (Modify config):
```json
"target_1_pct": 0.10,
"target_1_qty": 0.25,  // 25%
"target_2_pct": 0.15,
"target_2_qty": 0.25,  // 25%
"target_3_pct": 0.20,
"target_3_qty": 0.25,  // 25%
"target_4_pct": 0.25,
"target_4_qty": 0.25   // Final 25% (need to add PT4 logic in code)
```

---

#### **7. Execution Schedule**

```json
"execution_schedule": {
  "buy_window_start_time": "15:00",      // Buy window starts at 3:00 PM EST
  "buy_window_end_time": "15:59",        // Buy window ends at 3:59 PM EST
  "default_interval_seconds": 120,       // Scan every 2 minutes (normal hours)
  "last_hour_interval_seconds": 60       // Scan every 1 minute (last hour)
}
```

**Execution Logic:**
- **Sell Guardian**: Runs continuously (every scan, all day)
- **Buy Hunter**: Only runs during buy window (3:00-3:59 PM EST by default)
- **Scan Frequency**:
  - 9:30 AM - 3:00 PM: Every 2 minutes
  - 3:00 PM - 4:00 PM: Every 1 minute (power hour)

**Customizing Buy Window (15-Minute Intervals):**
```json
// Last 15 minutes only
"buy_window_start_time": "15:45",
"buy_window_end_time": "15:59"

// Last 30 minutes
"buy_window_start_time": "15:30",
"buy_window_end_time": "15:59"

// Last 2 hours
"buy_window_start_time": "14:00",
"buy_window_end_time": "15:59"
```

---

### watchlist.txt

Create a file with one stock symbol per line:

```
AAPL
NVDA
AMD
MSFT
TSLA
META
GOOGL
AMZN
```

**Update Frequency:**
- Daily: Recommended for active trading
- Weekly: For swing trading approach

---

## Strategy Logic

### Entry Requirements (ALL MUST BE TRUE)

#### 1. Market Structure ✅
- **50 SMA > 200 SMA** (golden cross setup)
- **21 EMA > 50 SMA** (strong uptrend)

#### 2. Multi-Timeframe Confirmation ✅
- **Weekly Close > Weekly EMA21**
- **Monthly Close > Monthly EMA10**

#### 3. Pullback Detection ✅
- Price near **21 EMA** or **50 SMA** (within 2.5%)
- Recent pullback: Highest high in last 4 bars > current high

#### 4. Pattern Recognition ✅ (MANDATORY)
Must have ONE of these explosive patterns:
- **Engulfing**: Green candle closes >= yesterday's open (red candle)
- **Piercing**: Green candle closes above yesterday's midpoint but < yesterday's open, with >= 40% explosive body ratio
- **Tweezer Bottom**: Today's low within 0.2% of yesterday's low (red candle)

#### 5. Stalling Filter ✅
- **Reject** if 8-day range <= 5% of average price
- **UNLESS** 3-day range also <= 5% (recent consolidation breakout OK)

#### 6. Volume Check ✅
- Current volume > 21-day average (conviction)

#### 7. Scoring System ✅
**Base Score (0-5):**
- +1: Stock 21-day performance > QQQ 21-day performance
- +1: Weekly confirmation (Weekly close > Weekly EMA21)
- +1: Monthly confirmation (Monthly close > Monthly EMA10)
- +1: Volume above 21-day average
- +1: Price in Demand Zone (within 3.5% of 21-day low)

**Touch Bonuses:**
- +0.5: First touch of EMA21 after uptrend
- +0.5: First touch of SMA50 after uptrend

---

### Exit Management

#### 1. Dynamic Trailing Stop Loss (3-Tier) 🛡️

**Tier 0 (Entry):**
- Initial SL: -17% below entry price

**Tier 1 (At +5% Profit):**
- SL moves to: -9% below entry (locks in breakeven + small profit)

**Tier 2 (At +10% Profit):**
- SL moves to: -1% below entry (locks in ~9% profit)

**Example:**
- Entry: $100
- Initial SL: $83 (-17%)
- At $105 (+5%): SL → $91 (-9%)
- At $110 (+10%): SL → $99 (-1%)
- Never trails down, only up!

---

#### 2. Partial Profit Exits (1/3 Rule) 💰

**PT1 @ +10%:**
- Sell 33.3% of position
- Lock in partial profit

**PT2 @ +15%:**
- Sell another 33.3%
- Further reduce risk

**PT3 @ +20%:**
- Sell remaining 33.4%
- Position fully closed with excellent profit

**Example:**
- Entry: 100 shares @ $100 = $10,000
- PT1 @ $110 (+10%): Sell 33 shares, keep 67
- PT2 @ $115 (+15%): Sell 33 shares, keep 34
- PT3 @ $120 (+20%): Sell remaining 34 shares

**Database Tracking:**
- All partial exits recorded in `partial_exits` table
- Prevents double-selling same target
- Tracks remaining quantity accurately

---

#### 3. Time Exit Signal (TES) ⏰

- **Max Hold Days**: 21 days (configurable)
- Automatically exits position after 21 days, regardless of profit/loss
- Prevents "dead money" sitting in stagnant positions

---

#### 4. FIFO Selling 📊

**First In, First Out:**
- If you have 2 positions in AAPL:
  - Position 1 entered on Jan 1 @ $100
  - Position 2 entered on Jan 5 @ $105
- When exit condition triggers → Position 1 sells first

**Database Implementation:**
- All positions stored with entry timestamp
- Sorted by `entry_date ASC` when retrieving
- Ensures oldest position exits first

---

## Running the Bot

### 1. First Time Setup

```bash
# 1. Update config file
# Replace YOUR_ALPACA_API_KEY and YOUR_ALPACA_SECRET_KEY with real keys

# 2. Update watchlist
echo "AAPL" > watchlist.txt
echo "NVDA" >> watchlist.txt
echo "TSLA" >> watchlist.txt

# 3. Test configuration
python rajat_alpha_v67.py
```

### 2. Paper Trading (Recommended)

```json
"api": {
  "base_url": "https://paper-api.alpaca.markets"
}
```

**Paper trading benefits:**
- No real money at risk
- Test strategy in real market conditions
- Same API as live trading
- $100k virtual cash

### 3. Live Trading (After Testing)

```json
"api": {
  "base_url": "https://api.alpaca.markets"
}
```

**⚠️ WARNING:**
- Only use live trading after thorough paper testing
- Start with small position sizes
- Monitor closely for first week
- Have stop losses in place

### 4. Running the Bot

```bash
# Run in foreground (testing)
python rajat_alpha_v67.py

# Run in background (production, Linux/Mac)
nohup python rajat_alpha_v67.py &

# Run in background (production, Windows)
# Use Task Scheduler or pythonw.exe
pythonw rajat_alpha_v67.py
```

### 5. Monitoring

**Check Logs:**
```bash
tail -f rajat_alpha_v67.log
```

**Log Output Example:**
```
2026-01-11 09:30:01 | INFO | === RAJAT ALPHA V67 TRADING BOT INITIALIZED ===
2026-01-11 09:30:01 | INFO | Mode: PAPER TRADING
2026-01-11 09:30:02 | INFO | Watchlist loaded: 6 symbols
2026-01-11 09:35:00 | INFO | --- SELL GUARDIAN: Monitoring Positions ---
2026-01-11 09:35:00 | INFO | No open positions to monitor
2026-01-11 09:35:00 | INFO | BUY HUNTER: Outside buy window, skipping scan
2026-01-11 15:00:00 | INFO | --- BUY HUNTER: Scanning Watchlist ---
2026-01-11 15:01:23 | INFO | [AAPL] ✅ ENTRY SIGNAL DETECTED!
2026-01-11 15:01:23 | INFO | [AAPL] Score: 4/5, Pattern: Piercing
2026-01-11 15:01:25 | INFO | [AAPL] Executing BUY: 50 shares @ $150.25 (Total: $7512.50)
2026-01-11 15:01:25 | INFO | [AAPL] Initial Stop Loss: $124.71 (17.0% below entry)
2026-01-11 15:01:26 | INFO | [AAPL] Order submitted successfully (ID: abc123)
2026-01-11 15:01:26 | INFO | [AAPL] Position recorded in database (Position ID: 1)
```

---

## Database Management

### Database Schema

**Table: positions**
```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
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
    created_at TIMESTAMP
);
```

**Table: partial_exits**
```sql
CREATE TABLE partial_exits (
    id INTEGER PRIMARY KEY,
    position_id INTEGER NOT NULL,
    exit_date TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    exit_price REAL NOT NULL,
    profit_target TEXT,
    profit_pct REAL,
    FOREIGN KEY (position_id) REFERENCES positions(id)
);
```

### Querying the Database

```bash
# Open database
sqlite3 positions.db

# View all open positions
SELECT * FROM positions WHERE status = 'OPEN';

# View closed positions with profit/loss
SELECT symbol, entry_price, exit_price, profit_loss_pct, exit_reason 
FROM positions 
WHERE status = 'CLOSED' 
ORDER BY exit_date DESC;

# View partial exits
SELECT p.symbol, pe.profit_target, pe.quantity, pe.profit_pct 
FROM partial_exits pe 
JOIN positions p ON pe.position_id = p.id 
ORDER BY pe.exit_date DESC;

# Calculate total P/L
SELECT SUM(profit_loss_pct) FROM positions WHERE status = 'CLOSED';
```

### Backup Database

```bash
# Create backup
cp positions.db positions_backup_$(date +%Y%m%d).db

# Restore from backup
cp positions_backup_20260111.db positions.db
```

---

## Troubleshooting

### Common Issues

#### 1. "Insufficient data or immature stock"
**Cause**: Stock doesn't have 200 days of trading history

**Solution**:
- Reduce `min_listing_days` in config:
  ```json
  "min_listing_days": 100
  ```
- Or remove recently listed stocks from watchlist

---

#### 2. "No valid pullback to key moving averages"
**Cause**: Stock hasn't pulled back to 21 EMA or 50 SMA

**Solution**: Wait for pullback (this is working correctly, not a bug)

---

#### 3. "No explosive bullish pattern detected"
**Cause**: No Engulfing, Piercing, or Tweezer pattern on latest candle

**Solution**: 
- Pattern is MANDATORY for entry (this is by design)
- Check daily candles manually to verify
- Wait for pattern to form

---

#### 4. "Market structure not bullish"
**Cause**: 50 SMA <= 200 SMA OR 21 EMA <= 50 SMA

**Solution**:
- This is a filter (working correctly)
- Stock may be in downtrend/sideways
- Remove from watchlist if persistently bearish

---

#### 5. "Stock is stalling (sideways consolidation)"
**Cause**: 8-day range <= 5% with no recent consolidation breakout

**Solution**:
- Adjust stalling parameters:
  ```json
  "stalling_range_pct": 3.0  // Tighter filter (3% instead of 5%)
  ```
- Or disable stalling filter (modify code, not recommended)

---

#### 6. "Order execution failed"
**Cause**: Alpaca API error, insufficient buying power, market closed

**Solution**:
- Check Alpaca account status
- Verify buying power:
  ```python
  account = trading_client.get_account()
  print(f"Buying power: ${account.buying_power}")
  ```
- Check market hours
- Review logs for detailed error message

---

#### 7. Database Locked Error
**Cause**: Multiple instances accessing database simultaneously

**Solution**:
- Ensure only one bot instance running
- Kill other processes:
  ```bash
  ps aux | grep rajat_alpha_v67
  kill <PID>
  ```

---

#### 8. Partial Exits Not Executing
**Cause**: 
- Database not tracking partial exits correctly
- Profit targets not reached

**Solution**:
- Verify database:
  ```sql
  SELECT * FROM partial_exits WHERE position_id = 1;
  ```
- Check current price vs targets:
  ```python
  entry_price = 100
  current_price = 110
  pt1_price = entry_price * 1.10  # Should be 110
  print(f"PT1 at ${pt1_price}, Current: ${current_price}")
  ```

---

### Performance Optimization

#### 1. Reduce API Calls
- Use data caching (5-minute expiry implemented)
- Increase scan intervals during slow hours

#### 2. Database Optimization
```sql
-- Create index for faster queries
CREATE INDEX idx_status ON positions(status);
CREATE INDEX idx_symbol ON positions(symbol);
```

#### 3. Logging Levels
```python
# Set to WARNING to reduce log volume
logging.basicConfig(level=logging.WARNING)

# Set to DEBUG for detailed troubleshooting
logging.basicConfig(level=logging.DEBUG)
```

---

## Strategy Customization

### Conservative Setup (Lower Risk)

```json
{
  "trading_rules": {
    "max_open_positions": 1,        // Only 1 position at a time
    "max_trades_per_stock": 1
  },
  "position_sizing": {
    "mode": "percent_of_amount",
    "base_amount": 50000,
    "percent_of_amount": 0.02       // 2% = $1000 per trade (very conservative)
  },
  "risk_management": {
    "initial_stop_loss_pct": 0.12,  // Tighter SL (12% instead of 17%)
    "max_loss_mode": "dollar",
    "max_loss_dollars": 300         // Max $300 loss per trade
  },
  "profit_taking": {
    "target_1_pct": 0.08,           // Lower targets (8%, 12%, 16%)
    "target_2_pct": 0.12,
    "target_3_pct": 0.16
  }
}
```

### Aggressive Setup (Higher Risk, Higher Reward)

```json
{
  "trading_rules": {
    "max_open_positions": 5,        // More concurrent positions
    "max_trades_per_stock": 2
  },
  "position_sizing": {
    "mode": "percent_equity",
    "percent_of_equity": 0.20       // 20% per trade (aggressive)
  },
  "risk_management": {
    "initial_stop_loss_pct": 0.20,  // Wider SL (more room to run)
    "max_loss_mode": "percent",
    "max_loss_pct": 0.05            // Max 5% loss per trade
  },
  "profit_taking": {
    "target_1_pct": 0.15,           // Higher targets (15%, 25%, 35%)
    "target_2_pct": 0.25,
    "target_3_pct": 0.35
  }
}
```

---

## Support & Resources

**Alpaca Documentation:**
- API Docs: https://docs.alpaca.markets
- Paper Trading: https://app.alpaca.markets/paper/dashboard/overview
- Live Trading: https://app.alpaca.markets/live/dashboard/overview

**Python Libraries:**
- alpaca-py: https://github.com/alpacahq/alpaca-py
- pandas-ta: https://github.com/twopirllc/pandas-ta

**Strategy Reference:**
- Original PineScript: `c:\Rajat-Code\AlgoPractice\PineScript\Rajat Alpha v67 Strategy Single Buy.pine`
- Logic Reference: `c:\Rajat-Code\AlgoPractice\PineScript\Rajat Alpha v67 Strategy Logic Reference.md`

---

## License

This is a proprietary trading strategy. Unauthorized distribution prohibited.

**Disclaimer**: Trading involves substantial risk of loss. This bot is provided "as is" without warranty. Use at your own risk. Past performance does not guarantee future results.

---

**Version**: 1.0  
**Last Updated**: January 11, 2026  
**Author**: Rajat (AI Assistant: GitHub Copilot)
