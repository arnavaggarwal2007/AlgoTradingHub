# QUICK START GUIDE - Rajat Alpha v67 Trading Bot

## 5-Minute Setup

### Step 1: Install Dependencies (1 minute)

```bash
cd c:\Alpaca_Algo
pip install -r requirements.txt
```

### Step 2: Get Alpaca API Keys (2 minutes)

1. Go to https://alpaca.markets
2. Sign up for a **Paper Trading** account (free)
3. Navigate to **Dashboard → API Keys**
4. Click **Generate New Key**
5. Copy **API Key ID** and **Secret Key**

### Step 3: Configure Bot (1 minute)

1. Rename `config_enhanced.json` to `config.json`:
```bash
copy config_enhanced.json config.json
```

2. Edit `config.json`:
```json
{
  "api": {
    "key_id": "PASTE_YOUR_KEY_ID_HERE",
    "secret_key": "PASTE_YOUR_SECRET_KEY_HERE",
    "base_url": "https://paper-api.alpaca.markets"
  }
  // ... rest of config
}
```

### Step 4: Update Watchlist (30 seconds)

Edit `watchlist.txt`:
```
AAPL
NVDA
MSFT
```

### Step 5: Run Bot (30 seconds)

```bash
python rajat_alpha_v67.py
```

**You should see:**
```
2026-01-11 09:30:01 | INFO | RAJAT ALPHA V67 TRADING BOT INITIALIZED
2026-01-11 09:30:01 | INFO | Mode: PAPER TRADING
2026-01-11 09:30:02 | INFO | Watchlist loaded: 3 symbols
2026-01-11 09:30:05 | INFO | --- SELL GUARDIAN: Monitoring Positions ---
```

---

## What Happens Next?

### During Market Hours (9:30 AM - 4:00 PM EST)

**Every 2 Minutes (9:30 AM - 3:00 PM):**
- **Sell Guardian** checks all open positions for:
  - Stop loss triggers
  - Profit targets (partial exits)
  - Time exit signals
- **Buy Hunter** skips scanning (outside buy window)

**Every 1 Minute (3:00 PM - 4:00 PM - POWER HOUR):**
- **Sell Guardian** continues monitoring
- **Buy Hunter** ACTIVATES and scans watchlist for:
  - Market structure (50 SMA > 200 SMA, 21 EMA > 50 SMA)
  - Multi-timeframe confirmation (Weekly + Monthly)
  - Pullback to key MAs
  - Explosive pattern (Engulfing/Piercing/Tweezer)
  - Score >= 3/5
  
**When Signal Found:**
```
[AAPL] ✅ ENTRY SIGNAL DETECTED!
[AAPL] Score: 4/5, Pattern: Piercing
[AAPL] Executing BUY: 50 shares @ $150.25 (Total: $7512.50)
[AAPL] Initial Stop Loss: $124.71 (17.0% below entry)
[AAPL] Order submitted successfully
```

### After Market Close (4:00 PM EST)

Bot sleeps until next market open.

---

## Configuration Presets

### Conservative (Recommended for Beginners)

```json
{
  "trading_rules": {
    "max_open_positions": 1
  },
  "position_sizing": {
    "mode": "percent_equity",
    "percent_of_equity": 0.05  // 5% per trade
  },
  "risk_management": {
    "max_loss_mode": "percent",
    "max_loss_pct": 0.01  // Max 1% loss per trade
  }
}
```

**Profile**: Low risk, 1 position max, 5% position size

### Moderate (Default)

```json
{
  "trading_rules": {
    "max_open_positions": 2
  },
  "position_sizing": {
    "mode": "percent_equity",
    "percent_of_equity": 0.10  // 10% per trade
  },
  "risk_management": {
    "max_loss_mode": "percent",
    "max_loss_pct": 0.02  // Max 2% loss per trade
  }
}
```

**Profile**: Moderate risk, 2 positions max, 10% position size

### Aggressive

```json
{
  "trading_rules": {
    "max_open_positions": 5
  },
  "position_sizing": {
    "mode": "percent_equity",
    "percent_of_equity": 0.15  // 15% per trade
  },
  "risk_management": {
    "max_loss_mode": "percent",
    "max_loss_pct": 0.03  // Max 3% loss per trade
  }
}
```

**Profile**: High risk/reward, 5 positions max, 15% position size

---

## Testing Checklist

Before going live, verify:

- [ ] Bot connects to Alpaca (no API errors)
- [ ] Watchlist loads successfully
- [ ] Market data fetches correctly
- [ ] Entry signals detected (check logs during 3-4 PM)
- [ ] Orders execute (check Alpaca dashboard)
- [ ] Positions recorded in database
- [ ] Partial exits trigger at profit targets
- [ ] Stop loss triggers work
- [ ] Database updates correctly

**Test Period**: Run in paper trading for at least 2 weeks

---

## Monitoring Commands

### View Live Logs
```bash
# Windows
type rajat_alpha_v67.log

# Linux/Mac
tail -f rajat_alpha_v67.log
```

### Check Database
```bash
sqlite3 positions.db
sqlite> SELECT * FROM positions WHERE status = 'OPEN';
sqlite> .quit
```

### Check Alpaca Positions
```python
from alpaca.trading.client import TradingClient

client = TradingClient("YOUR_KEY", "YOUR_SECRET", paper=True)
positions = client.get_all_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.qty} shares @ ${pos.avg_entry_price}")
```

---

## Troubleshooting Quick Fixes

### "ImportError: No module named 'alpaca'"
```bash
pip install alpaca-py
```

### "FileNotFoundError: config.json"
```bash
copy config_enhanced.json config.json
```

### "API authentication failed"
- Double-check API keys in `config.json`
- Ensure no extra spaces or quotes
- Verify paper trading URL: `https://paper-api.alpaca.markets`

### "No signals detected"
- Check if it's 3-4 PM EST (buy window)
- Verify stocks in watchlist meet all criteria:
  - 50 SMA > 200 SMA
  - 21 EMA > 50 SMA
  - Has explosive pattern today
- Review logs for specific rejection reasons

---

## Next Steps

1. **Paper Trade for 2+ Weeks**
   - Monitor all signals
   - Verify profit targets work
   - Ensure stop losses trigger correctly

2. **Review Database Results**
   ```sql
   SELECT symbol, AVG(profit_loss_pct) AS avg_profit
   FROM positions 
   WHERE status = 'CLOSED'
   GROUP BY symbol;
   ```

3. **Optimize Configuration**
   - Adjust position sizing
   - Fine-tune profit targets
   - Modify buy window

4. **Consider Live Trading** (Only After Success in Paper)
   - Change `base_url` to `https://api.alpaca.markets`
   - Use LIVE API keys
   - Start with small position sizes

---

## Support

For detailed documentation, see: `README_COMPLETE_GUIDE.md`

For PineScript strategy reference, see:
- `c:\Rajat-Code\AlgoPractice\PineScript\Rajat Alpha v67 Strategy Single Buy.pine`
- `c:\Rajat-Code\AlgoPractice\PineScript\Rajat Alpha v67 Strategy Logic Reference.md`

---

**Happy Trading!** 🚀📈
