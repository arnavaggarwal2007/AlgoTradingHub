# E*TRADE API Setup Guide

## Complete Setup Process for Rajat Alpha v67 with E*TRADE

---

## Step 1: Get E*TRADE API Keys (15 minutes)

### 1.1 Create or Access E*TRADE Account
- Go to https://www.etrade.com
- Log in to existing account OR create new account
- Verify account is active and funded

### 1.2 Request API Access
```
1. Log in to E*TRADE
2. Navigate to: https://us.etrade.com/etx/ris/apikey
3. Click "Create API Key"
4. Fill out form:
   - Application Name: "Rajat Alpha v67 Trading Bot"
   - Environment: Sandbox (for testing)
   - Accept Terms & Conditions
5. Submit request
```

### 1.3 Receive API Credentials
You will receive via email:
- **Consumer Key** (similar to Alpaca API Key)
- **Consumer Secret** (similar to Alpaca Secret Key)

**Save these securely!**

---

## Step 2: Install E*TRADE Python Library (5 minutes)

```bash
cd c:\Alpaca_Algo\Etrade_Algo
pip install -r requirements_etrade.txt
```

**Dependencies Installed:**
- `pyetrade` - Official E*TRADE Python SDK
- `requests-oauthlib` - OAuth 1.0a authentication
- `xmltodict` - E*TRADE XML response parsing
- `pandas`, `pandas-ta` - Technical analysis
- `pytz` - Timezone handling

---

## Step 3: OAuth Authorization (10 minutes - ONE TIME)

### 3.1 What is OAuth?

E*TRADE uses OAuth 1.0a (different from Alpaca's simple API key):
- **Step 1**: Get request token
- **Step 2**: User authorizes in browser (manual)
- **Step 3**: Exchange for access token
- **Step 4**: Use access token for trading

### 3.2 Run OAuth Setup Script

```bash
cd c:\Alpaca_Algo\Etrade_Algo
python etrade_oauth_setup.py
```

**Interactive Process:**
```
=== E*TRADE OAuth Setup ===

1. Authorization URL: https://us.etrade.com/e/t/etws/authorize?key=...
2. Open this URL in your browser
3. Log in to E*TRADE
4. Click "Accept" to authorize the application
5. Copy the verification code displayed

Enter verification code: [PASTE CODE HERE]

✅ Access Token: abc123...
✅ Access Secret: xyz789...

Tokens saved to config_etrade_single.json
```

### 3.3 Update Configuration

Edit `config_etrade_single.json`:
```json
{
  "api": {
    "consumer_key": "PASTE_CONSUMER_KEY_HERE",
    "consumer_secret": "PASTE_CONSUMER_SECRET_HERE",
    "access_token": "AUTO_FILLED_BY_OAUTH_SCRIPT",
    "access_secret": "AUTO_FILLED_BY_OAUTH_SCRIPT",
    "environment": "sandbox",
    "account_id_key": "AUTO_FILLED_AFTER_FIRST_RUN"
  }
}
```

---

## Step 4: Verify Account Access (5 minutes)

### 4.1 Test Connection

```bash
python test_etrade_connection.py
```

**Expected Output:**
```
Connecting to E*TRADE API...
✅ Authentication successful

Accounts found:
1. Account ID: 12345678 (CASH) - Balance: $10,000.00
2. Account ID: 87654321 (MARGIN) - Balance: $25,000.00

Using Account: 12345678 (CASH)
Account ID Key saved to config.
```

### 4.2 Update Config with Account ID

Script automatically updates `account_id_key` in config:
```json
{
  "api": {
    ...
    "account_id_key": "12345678"
  }
}
```

---

## Step 5: Paper Trading (Sandbox) Setup

### 5.1 Sandbox vs Production

| Environment | Purpose | Real Money | Configuration |
|-------------|---------|------------|---------------|
| **Sandbox** | Testing | NO ❌ | `"environment": "sandbox"` |
| **Production** | Live Trading | YES ✅ | `"environment": "prod"` |

### 5.2 Sandbox Limitations
- Virtual $100,000 starting capital
- Delayed market data (15 minutes)
- All orders simulated
- Perfect for testing strategy logic

### 5.3 Test Trade in Sandbox

```bash
python test_etrade_order.py
```

**Test Order:**
```
Symbol: AAPL
Action: BUY
Quantity: 1 share
Price Type: MARKET

Preview Order...
✅ Preview successful
  Estimated Cost: $150.25
  Commission: $0.00

Place Order...
✅ Order placed
  Order ID: 12345
  Status: EXECUTED
```

---

## Step 6: Run Trading Bot

### 6.1 Configure Strategy

Edit `config_etrade_single.json`:
```json
{
  "trading_rules": {
    "max_open_positions": 2,      // Start conservative
    "max_trades_per_stock": 2
  },
  "position_sizing": {
    "mode": "percent_equity",
    "percent_of_equity": 0.05      // 5% per trade (conservative)
  },
  "etrade_specific": {
    "environment": "sandbox",      // ALWAYS test in sandbox first!
    "commission_per_trade": 0.00
  }
}
```

### 6.2 Start Bot

```bash
python rajat_alpha_v67_single_etrade.py
```

**Console Output:**
```
================================================================================
RAJAT ALPHA V67 - E*TRADE TRADING BOT (SINGLE BUY)
================================================================================
Environment: SANDBOX (Paper Trading)
Account: 12345678 (CASH)
Balance: $100,000.00

Watchlist loaded: 6 symbols
Strategy: Single Buy with partial exits

Starting main execution loop...
Market closed. Sleeping for 5 minutes...
```

---

## Step 7: Monitor & Validate (2 weeks recommended)

### 7.1 Check Logs

```bash
tail -f rajat_alpha_v67_etrade_single.log
```

### 7.2 Review Database

```bash
sqlite3 positions_etrade_single.db
sqlite> SELECT * FROM positions WHERE status = 'OPEN';
```

### 7.3 E*TRADE Web Portal

- Log in to E*TRADE
- Go to "Accounts" → "Portfolio"
- Verify positions match bot database

---

## Step 8: Go Live (After Testing)

### 8.1 Create Production API Keys

```
1. Go to https://us.etrade.com/etx/ris/apikey
2. Create NEW key with Environment: PRODUCTION
3. Save Production Consumer Key + Secret
```

### 8.2 Re-run OAuth for Production

```bash
# Update config with production keys
# Edit config_etrade_single.json:
{
  "api": {
    "consumer_key": "PRODUCTION_KEY",
    "consumer_secret": "PRODUCTION_SECRET",
    "environment": "prod"
  }
}

# Re-authorize
python etrade_oauth_setup.py
# Follow authorization flow again for production
```

### 8.3 Start with Small Position Size

```json
{
  "trading_rules": {
    "max_open_positions": 1  // Start with 1 position only
  },
  "position_sizing": {
    "percent_of_equity": 0.02  // 2% per trade (very conservative)
  }
}
```

### 8.4 Run Live Bot

```bash
python rajat_alpha_v67_single_etrade.py
```

---

## Key Differences: E*TRADE vs Alpaca

### Authentication
**Alpaca**: Simple API Key + Secret (one-time setup)
**E*TRADE**: OAuth 1.0a (browser authorization required)

### Order Placement
**Alpaca**: Direct order placement
```python
order = client.submit_order(request)
```

**E*TRADE**: Preview THEN place (two-step)
```python
# Step 1: Preview
preview = client.preview_equity_order(...)
# Step 2: Place using preview ID
order = client.place_equity_order(preview_id=preview['id'])
```

### Market Data
**Alpaca**: Included free with API
**E*TRADE**: Delayed (15 min) in sandbox, real-time requires subscription

### Commission
**Alpaca**: $0 (commission-free)
**E*TRADE**: Varies by account type
- Active Trader (30+ trades/quarter): $0
- Regular: $0-$6.95/trade
- Options: $0.50-$0.65 per contract

### Account Types
**Alpaca**: Trading accounts only
**E*TRADE**: Cash, Margin, IRA (Individual Retirement Account)

---

## Troubleshooting

### Issue: OAuth Authorization Fails
**Solution:**
```bash
# Clear cached tokens
rm config_etrade_single.json
cp config_etrade_single.json.backup config_etrade_single.json

# Re-run OAuth
python etrade_oauth_setup.py
```

### Issue: "Preview Order Failed"
**Cause**: E*TRADE requires order preview before placing

**Solution**: Bot automatically previews. If error persists:
- Check account has sufficient buying power
- Verify market is open (9:30 AM - 4:00 PM EST)
- Ensure stock is tradeable (not halted)

### Issue: "Account ID Not Found"
**Solution:**
```bash
# List all accounts
python etrade_list_accounts.py

# Copy correct account_id_key to config
```

### Issue: "Commission Unexpected"
**E*TRADE commissions vary:**
- Update config:
  ```json
  {
    "etrade_specific": {
      "commission_per_trade": 6.95  // Or your actual commission
    }
  }
  ```

### Issue: "Market Data Delayed"
**Sandbox has 15-minute delay** (this is normal)

**For real-time data:**
1. Subscribe to E*TRADE real-time quotes ($24.99/month)
2. Use production environment
3. Update config: `"environment": "prod"`

---

## Security Best Practices

### 1. Never Commit API Keys to Git
```bash
# Add to .gitignore
echo "config_etrade_*.json" >> .gitignore
echo "*.log" >> .gitignore
echo "*.db" >> .gitignore
```

### 2. Secure Token Storage
```bash
# Set restrictive file permissions (Windows)
icacls config_etrade_single.json /grant:r %USERNAME%:F /inheritance:r
```

### 3. Rotate Tokens Regularly
- E*TRADE access tokens expire after inactivity
- Re-run OAuth setup monthly for production

### 4. Monitor for Suspicious Activity
- Check E*TRADE alerts
- Review trade confirmations daily
- Verify all positions in bot database match E*TRADE portfolio

---

## Advanced Configuration

### Trading in IRA Accounts
```json
{
  "trading_rules": {
    "account_type_filter": "IRA"  // Cash, Margin, or IRA
  }
}
```

### Enable Margin Trading (Risky!)
```json
{
  "etrade_specific": {
    "allow_margin_trading": true,
    "margin_multiplier": 2.0  // 2x leverage (risky!)
  }
}
```

### Limit Orders (Advanced)
```json
{
  "etrade_specific": {
    "use_market_orders": false,
    "limit_offset_pct": 0.005  // 0.5% above bid for buys
  }
}
```

---

## Support Resources

**E*TRADE Developer Portal:**
- Docs: https://developer.etrade.com/home
- API Reference: https://apisb.etrade.com/docs/api/authorization/request_token.html
- Support: https://us.etrade.com/customer-service

**Python Library:**
- pyetrade GitHub: https://github.com/jessecooper/pyetrade
- Documentation: https://pyetrade.readthedocs.io

**Bot-Specific:**
- See [ETRADE_QUICKSTART.md](ETRADE_QUICKSTART.md) for 5-min setup
- See [README_ALL_IMPLEMENTATIONS.md](../README_ALL_IMPLEMENTATIONS.md) for comparison

---

**Last Updated**: January 11, 2026  
**E*TRADE API Version**: v1  
**OAuth Version**: 1.0a  
**Status**: Complete setup guide
