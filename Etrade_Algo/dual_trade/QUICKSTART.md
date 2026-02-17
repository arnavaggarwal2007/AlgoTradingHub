# E*TRADE Dual Buy Bot - Quick Start Guide

**Last Updated**: January 12, 2026  
**Status**: ✅ Production Ready

---

## 5-Minute Setup

### Step 1: Get E*TRADE OAuth Tokens
```bash
python etrade_oauth_setup.py
```
- Browser will open with E*TRADE OAuth login
- Approve the request
- Copy the tokens displayed in terminal

### Step 2: Update Configuration
Edit `config_etrade_dual.json` and add:

```json
{
  "api": {
    "consumer_key": "FROM_etrade_oauth_setup",
    "consumer_secret": "FROM_etrade_oauth_setup",
    "access_token": "FROM_etrade_oauth_setup",
    "access_secret": "FROM_etrade_oauth_setup",
    "account_id_key": "YOUR_ACCOUNT_ID (from E*TRADE dashboard)",
    "environment": "sandbox"
  },
  "market_data": {
    "alpaca_api_key": "YOUR_ALPACA_KEY",
    "alpaca_secret_key": "YOUR_ALPACA_SECRET"
  }
}
```

### Step 3: Install Dependencies
```bash
pip install pyetrade alpaca-py pandas pandas-ta
```

### Step 4: Start the Bot
```bash
python rajat_alpha_v67_etrade_dual.py
```

Monitor the log:
```bash
tail -f rajat_alpha_v67_etrade_dual.log
```

---

## Configuration Details

### Essential Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `max_positions_b1` | 2 | Max B1 positions (primary buys) |
| `max_positions_b2` | 2 | Max B2 positions (high-score secondary) |
| `score_b2_min` | 3 | Minimum score to trigger B2 entry |
| `tes_days_b1` | 21 | B1 hold days before forced exit |
| `tes_days_b2` | 21 | B2 hold days before forced exit |
| `buy_window_start_time` | "15:00" | Buy window start (3 PM EST) |
| `buy_window_end_time` | "16:00" | Buy window end (4 PM EST) |

### Position Sizing

**Mode: percent_equity** (Recommended)
```json
"position_sizing": {
  "mode": "percent_equity",
  "percent_of_equity_b1": 0.05,  // 5% per B1
  "percent_of_equity_b2": 0.05   // 5% per B2
}
```

**Mode: fixed_dollar**
```json
"position_sizing": {
  "mode": "fixed_dollar",
  "fixed_amount": 1000  // $1000 per trade
}
```

### Risk Management

```json
"risk_management": {
  "initial_stop_loss_pct": 0.17,      // 17% below entry
  "tier_1_profit_pct": 0.05,          // Move SL at +5% profit
  "tier_1_stop_loss_pct": 0.09,       // To 9% below entry
  "tier_2_profit_pct": 0.10,          // Move SL at +10% profit
  "tier_2_stop_loss_pct": 0.01,       // To 1% below entry (breakeven+)
  "max_loss_dollars": 500,            // Max $500 loss per trade
  "stop_loss_mode": "closing_basis"   // Check at close prices
}
```

### Profit Taking

```json
"profit_taking": {
  "enable_partial_exits": true,
  "target_1_pct": 0.10,    // Close 33.3% at +10%
  "target_1_qty": 0.333,
  "target_2_pct": 0.15,    // Close 33.3% at +15%
  "target_2_qty": 0.333,
  "target_3_pct": 0.20,    // Close 33.4% at +20%
  "target_3_qty": 0.334
}
```

---

## Dual Buy Strategy Explained

### B1 (Primary Buy)
- **When**: Enters on ANY valid signal (score >= 1)
- **Max**: 2 positions simultaneously
- **Hold**: 21 days (configurable TES)
- **Exit**: Stop loss, profit targets, or TES

### B2 (Secondary High-Score Buy)
- **When**: Only when B1 active AND score >= 3 (configurable)
- **Max**: 2 positions simultaneously
- **Hold**: 21 days (separate TES from B1)
- **Purpose**: Capture additional setups while B1 is running

### Example Scenario
```
Market time: 3:15 PM EST

TSLA signal appears (Score: 4/5)
  → B1 position limit not reached
  → Execute B1 entry: 10 shares @ $250 = $2,500

3 minutes later: AAPL signal appears (Score: 4/5)
  → B1 position limit not reached
  → Execute B2 entry: 8 shares @ $200 = $1,600 (B2 for AAPL!)
  → Now have: 1 B1 (TSLA) + 1 B2 (AAPL)

Later: MSFT signal appears (Score: 2/5)
  → Score too low for B2 (< 3 minimum)
  → Log "Opportunity" signal (signal valid but no entry)

Later: NVDA signal appears (Score: 3.5/5)
  → B1 active (TSLA still holding)
  → Score >= 3: Execute B2 entry on NVDA
  → Now have: 1 B1 (TSLA) + 2 B2 (AAPL, NVDA) = FULL
```

---

## Watchlist Management

### Add Symbols
Edit `watchlist.txt`:
```
AAPL
MSFT
NVDA
TSLA
AMZN
...
```
One symbol per line, uppercase.

### Exclude Symbols
Edit `exclusionlist.txt`:
```
BAD_STOCK_1
AVOID_THIS
...
```
Symbols here will never be traded.

---

## Log Monitoring

### What to Look For

**Good Signs**:
```
✅ ENTRY SIGNAL DETECTED! Score: 4/5, Pattern: Engulfing
✅ Order placed successfully (ID: 123456)
✅ Trailing SL updated: $145.50 → $146.20 (Profit: 5.23%)
✅ PT1 executed successfully (+10.00%)
```

**Warning Signs**:
```
⚠️ Preview order failed
⚠️ Could not fetch current price
⚠️ Position limits reached
⚠️ Max trades per stock reached
```

**Error Signs**:
```
❌ Missing E*TRADE access tokens!
❌ Order execution failed
❌ No preview ID found in response
```

### Real-time Monitoring
```bash
# Watch log in real-time
tail -f rajat_alpha_v67_etrade_dual.log

# Filter for errors only
grep ERROR rajat_alpha_v67_etrade_dual.log | tail -20

# See all signals from today
grep "ENTRY SIGNAL" rajat_alpha_v67_etrade_dual.log
```

---

## Common Commands

### Check Current Positions
```python
import sqlite3
conn = sqlite3.connect('positions_etrade_dual.db')
cursor = conn.cursor()
cursor.execute('SELECT symbol, position_type, entry_price, remaining_qty, stop_loss FROM positions WHERE status = "OPEN"')
for row in cursor.fetchall():
    print(row)
conn.close()
```

### View Trade History
```python
cursor.execute('SELECT symbol, position_type, entry_price, exit_price, profit_loss_pct FROM positions WHERE status = "CLOSED" ORDER BY exit_date DESC LIMIT 10')
```

### Export Positions to CSV
```python
import sqlite3
import pandas as pd
df = pd.read_sql('SELECT * FROM positions', sqlite3.connect('positions_etrade_dual.db'))
df.to_csv('positions_export.csv', index=False)
```

---

## Troubleshooting

### Bot Won't Start
```
ERROR: Missing E*TRADE access tokens!
```
**Fix**: Run `python etrade_oauth_setup.py` again

### Orders Not Executing
```
ERROR: Preview order failed
```
**Fix**:
1. Check E*TRADE account has buying power
2. Verify OAuth tokens not expired
3. Check symbol is valid (uppercase)

### No Signals Detected
```
DEBUG: [SYMBOL] No signal - Market structure not bullish
```
**Fix**: 
- Market conditions don't meet requirements
- Check if 50 SMA < 200 SMA (downtrend)
- Look for signals in strong up-trending stocks

### Database Errors
```
ERROR: database is locked
```
**Fix**:
1. Stop the bot
2. Wait 2 seconds
3. Start again
4. If persists, delete `positions_etrade_dual.db` and restart

---

## Optimization Tips

### Reduce API Calls
```json
{
  "execution_schedule": {
    "default_interval_seconds": 300,        // 5 min instead of 2 min
    "last_hour_interval_seconds": 120       // 2 min instead of 1 min
  }
}
```

### Reduce Trading Activity
```json
{
  "trading_rules": {
    "max_positions_b1": 1,      // Reduce from 2 to 1
    "max_positions_b2": 1       // Reduce from 2 to 1
  }
}
```

### More Conservative Position Sizing
```json
{
  "position_sizing": {
    "percent_of_equity_b1": 0.02,   // Reduce from 5% to 2%
    "percent_of_equity_b2": 0.02
  }
}
```

---

## Common Configuration Presets

### Conservative (Low Risk)
```json
{
  "max_positions_b1": 1,
  "max_positions_b2": 0,
  "percent_of_equity_b1": 0.02,
  "initial_stop_loss_pct": 0.20,
  "max_loss_dollars": 250,
  "tes_days_b1": 14
}
```

### Balanced (Medium Risk)
```json
{
  "max_positions_b1": 2,
  "max_positions_b2": 1,
  "percent_of_equity_b1": 0.05,
  "percent_of_equity_b2": 0.03,
  "initial_stop_loss_pct": 0.17,
  "max_loss_dollars": 500,
  "tes_days_b1": 21
}
```

### Aggressive (High Risk)
```json
{
  "max_positions_b1": 2,
  "max_positions_b2": 2,
  "percent_of_equity_b1": 0.10,
  "percent_of_equity_b2": 0.10,
  "initial_stop_loss_pct": 0.15,
  "max_loss_dollars": 1000,
  "tes_days_b1": 21
}
```

---

## First Day Checklist

- [ ] OAuth tokens generated and added to config
- [ ] Alpaca market data credentials added
- [ ] Account ID added to config
- [ ] Watchlist updated with 5-10 stocks
- [ ] Running in SANDBOX mode (not production)
- [ ] Log file monitored (no errors showing)
- [ ] First buy window (3-4 PM EST) observed
- [ ] At least 1 signal detected and executed
- [ ] Position appears in database
- [ ] Stop loss shows in logs
- [ ] Partial exit triggers correctly

---

## Support

**E*TRADE API Help**:
- Docs: https://developer.etrade.com/docs
- Rate limits: 120 req/min
- OAuth expires: ~24 hours

**Alpaca API Help**:
- Docs: https://docs.alpaca.markets
- Rate limits: 200 req/min
- Free market data: Yes (1-min bars)

---

## Safety Notes

⚠️ **SANDBOX FIRST**: Always test thoroughly in sandbox mode before going live

⚠️ **SMALL POSITIONS**: Start with 1-2% position sizing, not 10%

⚠️ **TOKEN REFRESH**: OAuth tokens expire daily, refresh every morning

⚠️ **STOP LOSS REQUIRED**: Never disable stop loss checks

⚠️ **MONITOR LOGS**: Check logs daily for errors or unexpected behavior

---

**Ready to trade? Start with Step 1 above!**

For complete documentation, see `COMPLETION_REPORT.md`
