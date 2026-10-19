# E*TRADE DUAL TRADE IMPLEMENTATION GUIDE

## Files Created

1. **`rajat_alpha_v67_etrade_dual.py`** - Main trading script (partially converted)
2. **`config_etrade_dual.json`** - Configuration file
3. **`watchlist.txt`** - Stock watchlist
4. **`exclusionlist.txt`** - Exclusion list

## Conversion Status

### ✅ Completed
- Header and docstring updated to E*TRADE Dual Buy
- Imports changed from Alpaca Trading to E*TRADE + Alpaca Data
- Database schema updated with `etrade_order_id` field
- Position tracking methods updated
- Log file renamed to `rajat_alpha_v67_etrade_dual.log`

### 🔧 Remaining Work Required

The following components need to be manually added/updated:

#### 1. E*TRADE Order Manager Class
Insert after `ConfigManager` class (around line 320):

```python
# ================================================================================
# E*TRADE ORDER MANAGER
# ================================================================================

class ETradeOrderManager:
    """Handles E*TRADE order execution with Preview → Place workflow"""
    
    def __init__(self, consumer_key: str, consumer_secret: str, 
                 access_token: str, access_secret: str,
                 account_id_key: str, is_sandbox: bool = True):
        self.account_id_key = account_id_key
        self.is_sandbox = is_sandbox
        
        # Initialize order client
        self.order_client = order.ETradeOrder(
            consumer_key,
            consumer_secret,
            access_token,
            access_secret,
            dev=is_sandbox
        )
        
        logger.info(f"E*TRADE Order Manager initialized (Sandbox: {is_sandbox})")
    
    # Copy preview_order(), place_order(), execute_market_order() methods
    # from single_Trade/rajat_alpha_v67_etrade.py lines 723-827
```

#### 2. Position Manager Updates
Replace the PositionManager class `__init__` and trading methods:

**Changes needed:**
- Add `order_manager` and `accounts_client` parameters
- Replace Alpaca `trading_client` with E*TRADE `order_manager`
- Update `calculate_position_size()` to use E*TRADE `get_account_balance()`
- Update `execute_buy_b1()` and `execute_buy_b2()` to use E*TRADE preview→place workflow
- Update all sell methods to use E*TRADE orders
- Store `etrade_order_id` when recording positions

#### 3. Main Bot Orchestrator
Update `RajatAlphaTradingBot.__init__()`:

```python
def __init__(self, config_path='config_etrade_dual.json'):
    # Load configuration
    self.config = ConfigManager(config_path)
    
    # Initialize database
    self.db = PositionDatabase()
    
    # E*TRADE credentials
    consumer_key = self.config.get('etrade', 'consumer_key')
    consumer_secret = self.config.get('etrade', 'consumer_secret')
    access_token = self.config.get('etrade', 'access_token')
    access_secret = self.config.get('etrade', 'access_secret')
    account_id_key = self.config.get('etrade', 'account_id_key')
    is_sandbox = self.config.get('etrade', 'sandbox')
    
    # Alpaca for market data only
    alpaca_key = self.config.get('alpaca_data', 'key_id')
    alpaca_secret = self.config.get('alpaca_data', 'secret_key')
    self.data_client = StockHistoricalDataClient(alpaca_key, alpaca_secret)
    
    # E*TRADE order manager
    self.order_manager = ETradeOrderManager(
        consumer_key, consumer_secret,
        access_token, access_secret,
        account_id_key, is_sandbox
    )
    
    # E*TRADE accounts client
    self.accounts_client = accounts.ETradeAccounts(
        consumer_key, consumer_secret,
        access_token, access_secret,
        dev=is_sandbox
    )
    
    # Initialize components
    self.data_fetcher = MarketDataFetcher(self.data_client)
    self.analyzer = RajatAlphaAnalyzer(self.config, self.data_fetcher)
    self.position_manager = PositionManager(
        self.order_manager, self.config, self.db, 
        self.data_fetcher, self.accounts_client
    )
```

#### 4. Configuration File Updates
Update `config_etrade_dual.json`:

```json
{
  "etrade": {
    "consumer_key": "YOUR_CONSUMER_KEY",
    "consumer_secret": "YOUR_CONSUMER_SECRET",
    "access_token": "YOUR_ACCESS_TOKEN",
    "access_secret": "YOUR_ACCESS_SECRET",
    "account_id_key": "YOUR_ACCOUNT_ID_KEY",
    "sandbox": true
  },
  "alpaca_data": {
    "key_id": "YOUR_ALPACA_KEY",
    "secret_key": "YOUR_ALPACA_SECRET"
  },
  "trading_rules": {
    "max_positions_b1": 2,
    "max_positions_b2": 2,
    "max_trades_per_stock_b1": 2,
    "max_trades_per_stock_b2": 1,
    "score_b2_min": 3,
    "watchlist_file": "watchlist.txt",
    "exclusion_file": "exclusionlist.txt",
    "portfolio_mode": "watchlist_only"
  },
  ...rest of config same as dual_buy...
}
```

## Quick Completion Steps

### Option 1: Manual Completion
1. Copy E*TRADEOrderManager class from `single_Trade/rajat_alpha_v67_etrade.py` (lines 700-827)
2. Update PositionManager class - replace Alpaca calls with E*TRADE calls
3. Update bot initialization as shown above
4. Update config file with E*TRADE credentials

### Option 2: Use Reference Script
The complete working version combines:
- Database/Config from `Etrade_Algo/dual_trade/rajat_alpha_v67_etrade_dual.py` (partially done)
- E*TRADE API integration from `Etrade_Algo/single_Trade/rajat_alpha_v67_etrade.py`
- Dual position logic from `Dual_Buy/rajat_alpha_v67_dual.py`

## Testing

1. **Sandbox First**: Set `"sandbox": true` in config
2. **OAuth Tokens**: Run `etrade_oauth_setup.py` to get fresh tokens
3. **Test Order**: Try one buy signal with minimal position size
4. **Monitor Logs**: Check `rajat_alpha_v67_etrade_dual.log`

## Key Differences from Alpaca Dual

| Feature | Alpaca Dual | E*TRADE Dual |
|---------|-------------|--------------|
| Order Execution | `trading_client.submit_order()` | `preview_order()` → `place_order()` |
| Market Data | Alpaca Trading API | Alpaca Data API (separate) |
| Position Tracking | Alpaca positions | Database only |
| Account Balance | `account.equity` | `accounts_client.get_account_balance()` |
| Order IDs | Alpaca UUID | E*TRADE order ID (numeric string) |
| Commission | Included in Alpaca | Configurable in E*TRADE |

## Additional Files Needed

From `Etrade_Algo/single_Trade/`:
- `etrade_oauth_setup.py` - Get access tokens (expires ~24hrs)
- `etrade_account_info.py` - Test E*TRADE connection
- `requirements_etrade.txt` - Python dependencies

## Support Files

All created in `Etrade_Algo/dual_trade/`:
- ✅ `watchlist.txt`
- ✅ `exclusionlist.txt`
- ✅ `config_etrade_dual.json` (needs E*TRADE credentials)
- ⚠️ `rajat_alpha_v67_etrade_dual.py` (needs E*TRADE class integration)

---

**Status**: 40% Complete - Database and structure done, E*TRADE API integration needed
