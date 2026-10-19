# Rajat Alpha v67 - Implementation Comparison

## Overview

This document compares all implementations of the Rajat Alpha v67 trading strategy across platforms.

---

## Implementation Matrix

| Implementation | Platform | Strategy Type | Max Positions | Entry Signals | File Location |
|----------------|----------|---------------|---------------|---------------|---------------|
| **alpha_bot.py** | Alpaca | Single Buy (Basic) | 5 | B (basic) | `c:\Alpaca_Algo\alpha_bot.py` |
| **rajat_alpha_v67.py** | Alpaca | Single Buy (Complete) | 2 | B (scored) | `c:\Alpaca_Algo\rajat_alpha_v67.py` |
| **rajat_alpha_v67_dual.py** | Alpaca | Dual Buy (B1+B2) | 4 (2 per type) | B1 + B2 + OPP | `c:\Alpaca_Algo\Dual_Buy\rajat_alpha_v67_dual.py` |
| **rajat_alpha_v67_single_etrade.py** | E*TRADE | Single Buy (Complete) | 2 | B (scored) | `c:\Alpaca_Algo\Etrade_Algo\rajat_alpha_v67_single_etrade.py` |
| **rajat_alpha_v67_dual_etrade.py** | E*TRADE | Dual Buy (B1+B2) | 4 (2 per type) | B1 + B2 + OPP | `c:\Alpaca_Algo\Etrade_Algo\rajat_alpha_v67_dual_etrade.py` |

---

## Key Differences

### 1. Single Buy vs Dual Buy

#### Single Buy Strategy
- **Max Positions**: 2 (configurable)
- **Entry Logic**: Single "B" signal when all criteria met
- **Position Type**: All positions treated equally
- **Score Requirement**: Minimum score 0/5 (all signals valid)
- **Use Case**: Conservative, clear signals only

#### Dual Buy Strategy (B1 + B2)
- **Max Positions**: 4 (2x B1 + 2x B2, configurable)
- **Entry Logic**:
  - **B1**: Primary buy signal (any score)
  - **B2**: Secondary high-score buy when B1 active AND score >= threshold (default 3/5)
  - **OPP**: Opportunity signal (visual only) when B1 active but score < B2 minimum
- **Position Types**: Tracked separately (B1 vs B2)
- **Score Requirement**: B2 requires minimum score (default 3/5)
- **Use Case**: Aggressive, captures multiple entries per stock

---

### 2. Alpaca vs E*TRADE API

| Feature | Alpaca | E*TRADE |
|---------|--------|---------|
| **API Library** | `alpaca-py` | `pyetrade` |
| **Authentication** | API Key + Secret | OAuth 1.0a (Consumer Key + Secret) |
| **Market Data** | Built-in historical data client | Separate market data API |
| **Order Types** | Market, Limit, Stop, Stop Limit | Market, Limit, Stop, Stop Limit, Trailing Stop |
| **Paper Trading** | Native support (separate URL) | Sandbox environment |
| **Commission** | $0 (commission-free) | Varies by account type |
| **Real-time Data** | Included | Requires subscription |
| **Account Types** | Trading, Crypto | Cash, Margin, IRA |

---

## Watchlist vs Portfolio Scanning

### Current Implementation (Correct)

✅ **BUY SIGNALS**: Scan watchlist.txt only
- Only stocks in `watchlist.txt` are analyzed for entry signals
- Controlled, curated list of stocks to trade
- Prevents random entries from entire market

✅ **SELL SIGNALS**: Monitor complete portfolio (all open positions)
- Sell Guardian monitors ALL open positions regardless of origin
- Positions may have been opened on previous days
- Ensures all positions are protected with stop loss / profit targets

### Example Flow

```
Day 1 (watchlist.txt):
AAPL
NVDA
MSFT

Result: Buy AAPL @ $150 (signal detected)

Day 2 (watchlist.txt - updated):
NVDA
TSLA
AMD

BUY HUNTER:
- Scans: NVDA, TSLA, AMD (from watchlist)
- Ignores: AAPL (not in watchlist anymore)

SELL GUARDIAN:
- Monitors: AAPL position from Day 1 (from portfolio)
- Also monitors: Any new positions opened today

This is CORRECT behavior:
- Buy: Controlled watchlist
- Sell: Protect all positions
```

---

## Configuration Differences

### Single Buy Config
```json
{
  "trading_rules": {
    "max_open_positions": 2,
    "max_trades_per_stock": 2
  }
}
```

### Dual Buy Config
```json
{
  "trading_rules": {
    "max_open_positions_b1": 2,
    "max_open_positions_b2": 2,
    "max_trades_per_stock_b1": 2,
    "max_trades_per_stock_b2": 1,
    "score_b2_min": 3
  }
}
```

---

## Entry Signal Comparison

### Single Buy Entry
```python
# ALL these must be TRUE:
1. Market Structure OK (50 SMA > 200, 21 EMA > 50)
2. Multi-Timeframe OK (Weekly + Monthly)
3. Pullback detected
4. Pattern present (Engulfing/Piercing/Tweezer)
5. No stalling
6. In buy window (3-4 PM EST)
7. Score >= 0 (any score)

→ Execute: strategy.entry("B", long)
```

### Dual Buy Entry
```python
# B1 Entry (same as Single Buy):
[All 7 conditions above]
→ Execute: strategy.entry("B1", long)

# B2 Entry (ADDITIONAL requirement):
1. B1 position ACTIVE
2. ALL 7 conditions above
3. Score >= 3/5 (configurable)

→ Execute: strategy.entry("B2", long)

# OPP Signal (visual only):
1. B1 position ACTIVE
2. ALL 7 conditions above
3. Score < 3/5 (below B2 threshold)

→ Visual label only (no entry)
```

---

## Exit Management Comparison

### Identical for Both Single and Dual:
- ✅ Dynamic 3-tier trailing SL (17% → 9% → 1%)
- ✅ Partial exits (1/3 Rule or 1/4 Rule)
- ✅ FIFO selling (oldest position first)
- ✅ TES (Time Exit Signal) - max hold days
- ✅ Profit targets (PT1/PT2/PT3/PT4)

### Dual Buy Addition:
- **Separate TES for B1 and B2**:
  ```json
  {
    "tes_days_b1": 21,
    "tes_days_b2": 21
  }
  ```
- **Labeled exits** (B1 vs B2):
  - `SL` → B1 stop loss
  - `SL2` → B2 stop loss
  - `TES` → B1 time exit
  - `TES2` → B2 time exit

---

## Alpaca API Compliance Checklist

### ✅ Current Implementation (rajat_alpha_v67.py)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| **Authentication** | ✅ | TradingClient(api_key, secret_key, paper=True) |
| **Market Data** | ✅ | StockHistoricalDataClient for daily/weekly/monthly |
| **Order Placement** | ✅ | MarketOrderRequest with qty, side, time_in_force |
| **Position Tracking** | ✅ | get_all_positions() + SQLite database |
| **Account Info** | ✅ | get_account() for equity/buying power |
| **Error Handling** | ✅ | Try-except blocks around all API calls |
| **Rate Limiting** | ✅ | 5-minute data caching |
| **Paper Trading** | ✅ | Configurable base_url |
| **Commission Handling** | ✅ | $0 commission (Alpaca is commission-free) |

### Alpaca-Specific Features Used
```python
# Historical Data
params = StockBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame.Day,  # or Week, Month
    start=start_date
)
bars = data_client.get_stock_bars(params)

# Order Execution
order_request = MarketOrderRequest(
    symbol=symbol,
    qty=shares,
    side=OrderSide.BUY,  # or SELL
    time_in_force=TimeInForce.DAY
)
order = trading_client.submit_order(order_request)

# Position Management
positions = trading_client.get_all_positions()
for pos in positions:
    current_price = float(pos.current_price)
    unrealized_pl = float(pos.unrealized_pl)
```

---

## E*TRADE API Compliance Requirements

### Key Differences from Alpaca

1. **OAuth Authentication**
   ```python
   # E*TRADE uses OAuth 1.0a (not API key/secret like Alpaca)
   from pyetrade import ETradeOAuth, ETradeMarket, ETradeOrder
   
   oauth = ETradeOAuth(
       consumer_key="YOUR_CONSUMER_KEY",
       consumer_secret="YOUR_CONSUMER_SECRET"
   )
   
   # Manual browser-based authorization
   auth_url = oauth.get_request_token()
   # User visits URL, gets verifier code
   oauth.get_access_token(verifier_code)
   ```

2. **Market Data**
   ```python
   # Separate market client
   market = ETradeMarket(
       consumer_key,
       consumer_secret,
       access_token,
       access_secret
   )
   
   # Quote API
   quotes = market.get_quote(symbols=["AAPL", "NVDA"])
   ```

3. **Order Placement**
   ```python
   # Order client
   orders = ETradeOrder(
       consumer_key,
       consumer_secret,
       access_token,
       access_secret,
       account_id_key
   )
   
   # Preview order first (REQUIRED)
   preview = orders.preview_equity_order(
       account_id_key=account_id,
       symbol="AAPL",
       order_action="BUY",
       client_order_id="unique_id",
       price_type="MARKET",
       quantity=10
   )
   
   # Then place order
   order = orders.place_equity_order(
       account_id_key=account_id,
       preview_id=preview['previewId']
   )
   ```

4. **Account Types**
   ```python
   # E*TRADE supports multiple account types
   accounts = orders.list_accounts()
   # Filter for specific account type (CASH, MARGIN, IRA)
   ```

---

## File Structure

```
c:\Alpaca_Algo\
├── rajat_alpha_v67.py                    # Single Buy (Main Alpaca bot)
├── config_enhanced.json → config.json    # Configuration
├── watchlist.txt                         # Buy watchlist
├── positions.db                          # SQLite database
├── rajat_alpha_v67.log                   # Log file
├── requirements.txt                      # Dependencies
├── README_COMPLETE_GUIDE.md              # Full documentation
├── QUICKSTART.md                         # 5-min setup
├── IMPLEMENTATION_SUMMARY.md             # Feature summary
├── IMPLEMENTATION_COMPARISON.md          # This file
│
├── Dual_Buy/                             # Dual Buy Alpaca (B1+B2)
│   ├── rajat_alpha_v67_dual.py
│   ├── config_dual.json
│   ├── watchlist.txt → ../watchlist.txt (symlink)
│   ├── positions_dual.db
│   └── README_DUAL_BUY.md
│
└── Etrade_Algo/                          # E*TRADE implementations
    ├── rajat_alpha_v67_single_etrade.py  # Single Buy E*TRADE
    ├── rajat_alpha_v67_dual_etrade.py    # Dual Buy E*TRADE
    ├── config_etrade_single.json
    ├── config_etrade_dual.json
    ├── watchlist.txt → ../watchlist.txt (symlink)
    ├── positions_etrade_single.db
    ├── positions_etrade_dual.db
    ├── requirements_etrade.txt
    ├── ETRADE_SETUP_GUIDE.md             # OAuth setup, API activation
    └── ETRADE_QUICKSTART.md              # 5-min start guide
```

---

## Recommendations

### When to Use Each Implementation

#### Single Buy (Alpaca or E*TRADE)
**Best for:**
- Conservative trading approach
- Clear, high-confidence signals only
- Simpler position management
- Lower risk tolerance
- Beginners starting with algo trading

**Account Size:** $10k - $50k

#### Dual Buy (Alpaca or E*TRADE)
**Best for:**
- Aggressive trading approach
- Capturing multiple entries per stock
- Willingness to manage more positions
- Higher risk tolerance
- Experienced algo traders

**Account Size:** $50k+

### Platform Selection

#### Choose Alpaca if:
- ✅ You want commission-free trading
- ✅ You need native paper trading
- ✅ You prefer simpler API authentication
- ✅ You're algorithmic trading focused
- ✅ You want included market data

#### Choose E*TRADE if:
- ✅ You already have an E*TRADE account
- ✅ You want IRA support for algo trading
- ✅ You need advanced order types (trailing stop, etc.)
- ✅ You prefer established retail broker
- ✅ You want full-service brokerage features

---

## Migration Path

### From alpha_bot.py to rajat_alpha_v67.py
```bash
# 1. Backup existing database
cp positions.db positions_alpha_bot_backup.db

# 2. Update config
cp config_enhanced.json config.json
# Edit config.json with your settings

# 3. Stop old bot
pkill -f alpha_bot.py

# 4. Start new bot
python rajat_alpha_v67.py
```

### From Single Buy to Dual Buy
```bash
# 1. Backup current database
cp positions.db positions_single_backup.db

# 2. Set up Dual Buy
cd Dual_Buy
cp ../config.json config_dual.json
# Edit config_dual.json (add B2 parameters)

# 3. Run both simultaneously (different databases)
python rajat_alpha_v67_dual.py
```

### From Alpaca to E*TRADE
```bash
# 1. Get E*TRADE API keys (see ETRADE_SETUP_GUIDE.md)

# 2. Install E*TRADE dependencies
pip install -r Etrade_Algo/requirements_etrade.txt

# 3. Configure OAuth
cd Etrade_Algo
python setup_oauth.py  # Interactive OAuth flow

# 4. Run E*TRADE bot
python rajat_alpha_v67_single_etrade.py
```

---

## Performance Comparison (Estimated)

| Metric | Single Buy | Dual Buy |
|--------|------------|----------|
| **Max Drawdown** | Lower (-15% typical) | Higher (-25% typical) |
| **Win Rate** | Higher (65%+) | Moderate (55%+) |
| **Average Trade** | +8% typical | +6% typical (more entries) |
| **Trades/Month** | 2-4 trades | 6-10 trades |
| **Portfolio Utilization** | 20-40% | 40-80% |
| **Complexity** | Simple | Moderate |

---

## Next Steps

1. ✅ **Verify Current Implementation**: Alpaca Single Buy complete
2. 🔄 **Create Dual Buy Alpaca**: In progress
3. 🔄 **Create E*TRADE Single**: In progress
4. 🔄 **Create E*TRADE Dual**: In progress
5. 📝 **Documentation**: Setup guides for each

---

**Last Updated**: January 11, 2026  
**Version**: 1.0
