# CONFIGURATION ANALYSIS - REQUESTED FEATURES
**Date:** January 12, 2026

## ✅ FEATURE STATUS ACROSS ALL SCRIPTS

### 1. ❌ EXCLUSION LIST (exclusionlist.txt)
**Status:** NOT IMPLEMENTED

**Current Behavior:**
- Only watchlist.txt is supported
- No exclusion/blacklist mechanism exists
- All symbols in watchlist are processed

**Implementation Needed:**
- Add `exclusion_file` to trading_rules config
- Load exclusionlist.txt in get_watchlist() method
- Filter out excluded symbols before analysis
- Log excluded symbols

---

### 2. ✅ PORTFOLIO AMOUNT / TOTAL CAPITAL
**Status:** PARTIALLY IMPLEMENTED

**Current Implementation:**
```json
"position_sizing": {
  "mode": "percent_of_amount",
  "base_amount": 50000,          // ← This is your total portfolio
  "percent_of_amount": 0.03      // ← % per position (3%)
}
```

**Options Available:**
1. **percent_equity** - % of current account equity (dynamic)
2. **fixed_dollar** - Fixed dollar amount per trade
3. **percent_of_amount** - % of base portfolio amount (static)

**Current Config Uses:**
- Single_Buy: `percent_equity: 10%` (10% of account equity)
- Dual_Buy: `percent_equity: 5%` (5% of account equity)

**Issue:** No explicit "total_portfolio_capital" parameter separate from account equity.

---

### 3. ✅ % INVESTMENT IN EACH STOCK
**Status:** IMPLEMENTED

**Configuration:**
```json
"position_sizing": {
  "mode": "percent_of_amount",
  "base_amount": 100000,         // Your total capital
  "percent_of_amount": 0.02      // 2% per stock
}
```

**How It Works:**
- Mode: `percent_of_amount`
- Base Amount: Your defined total portfolio (e.g., $100,000)
- Percent per trade: 2% or 3% as you specify
- Example: $100,000 × 2% = $2,000 per position

**Alternative Mode (Current Default):**
```json
"position_sizing": {
  "mode": "percent_equity",
  "percent_of_equity": 0.03      // 3% of account equity
}
```

---

### 4. ✅ NUMBER OF TRADES PER STRATEGY
**Status:** IMPLEMENTED

**Single_Buy Configuration:**
```json
"trading_rules": {
  "max_open_positions": 2,        // Max total positions
  "max_trades_per_stock": 2       // Max entries per symbol
}
```

**Dual_Buy Configuration:**
```json
"trading_rules": {
  "max_positions_b1": 2,          // B1 (high-quality) max positions
  "max_positions_b2": 2,          // B2 (secondary) max positions
  "max_trades_per_stock_b1": 2,   // B1 max per symbol
  "max_trades_per_stock_b2": 1    // B2 max per symbol
}
```

**Flexibility:**
- Can set different limits per strategy type (B1 vs B2)
- Controls total open positions
- Controls entries per specific stock

---

## 📊 CURRENT vs DESIRED CONFIGURATION

### Current Setup (Single_Buy)
```json
{
  "position_sizing": {
    "mode": "percent_equity",       // Uses account equity
    "percent_of_equity": 0.10       // 10% per position
  },
  "trading_rules": {
    "max_open_positions": 2,
    "max_trades_per_stock": 2,
    "watchlist_file": "watchlist.txt"
    // ❌ No exclusion list
  }
}
```

### Recommended Setup (Your Requirements)
```json
{
  "position_sizing": {
    "mode": "percent_of_amount",    // Use fixed portfolio amount
    "base_amount": 100000,          // Your total capital
    "percent_of_amount": 0.02       // 2% per stock
  },
  "trading_rules": {
    "max_open_positions": 10,       // Based on 2% = max 50 positions theoretically
    "max_trades_per_stock": 1,      // One entry per symbol
    "watchlist_file": "watchlist.txt",
    "exclusion_file": "exclusionlist.txt"  // ← NEEDS TO BE ADDED
  }
}
```

---

## 🔧 REQUIRED CHANGES

### Priority 1: Add Exclusion List Support

**Files to Modify:**
1. `config.json` / `config_dual.json` / `config_etrade_single.json`
2. `rajat_alpha_v67.py` / `rajat_alpha_v67_dual.py` / `rajat_alpha_v67_etrade.py`

**Changes Needed:**

**Config Addition:**
```json
"trading_rules": {
  "exclusion_file": "exclusionlist.txt",
  "log_excluded_symbols": true
}
```

**Code Changes in get_watchlist():**
```python
def get_watchlist(self) -> List[str]:
    """Load watchlist and apply exclusions"""
    # Load watchlist
    watchlist_file = self.config.get('trading_rules', 'watchlist_file')
    watchlist = self._load_symbol_file(watchlist_file)
    
    # Load exclusions
    exclusion_file = self.config.get('trading_rules', 'exclusion_file')
    if exclusion_file:
        exclusions = self._load_symbol_file(exclusion_file)
        original_count = len(watchlist)
        watchlist = [s for s in watchlist if s not in exclusions]
        excluded_count = original_count - len(watchlist)
        if excluded_count > 0:
            logger.info(f"Excluded {excluded_count} symbols from watchlist")
    
    logger.info(f"Active watchlist: {len(watchlist)} symbols")
    return watchlist
```

---

### Priority 2: Update Position Sizing Configuration

**Current Config Update Needed:**

**Change FROM:**
```json
"position_sizing": {
  "mode": "percent_equity",
  "percent_of_equity": 0.10
}
```

**Change TO:**
```json
"position_sizing": {
  "mode": "percent_of_amount",
  "base_amount": 100000,          // YOUR TOTAL CAPITAL
  "percent_of_amount": 0.02       // 2% or 3% as desired
}
```

**No code changes needed** - already supports this mode!

---

### Priority 3: Adjust Trade Limits

**Update:**
```json
"trading_rules": {
  "max_open_positions": 10,       // Adjust based on your 2% sizing
  "max_trades_per_stock": 1       // Or 2 if you want multiple entries
}
```

---

## 📋 IMPLEMENTATION SUMMARY

| Feature | Status | Action Required |
|---------|--------|-----------------|
| 1. Exclusion List | ❌ Missing | **IMPLEMENT** - Add code + config |
| 2. Portfolio Amount | ✅ Exists | **CONFIGURE** - Change mode to `percent_of_amount` |
| 3. % Per Stock | ✅ Exists | **CONFIGURE** - Set `percent_of_amount` to 0.02 or 0.03 |
| 4. Max Trades per Strategy | ✅ Exists | **CONFIGURE** - Adjust `max_open_positions` |

---

## 🎯 NEXT STEPS

**Option 1: I Can Implement All Changes**
I can:
1. Add exclusion list support to all 3 scripts
2. Update all config files with your preferences
3. Create exclusionlist.txt template
4. Test all changes

**Option 2: You Configure What Exists**
You can immediately:
1. Change position sizing mode to `percent_of_amount`
2. Set your total capital in `base_amount`
3. Set your % per stock in `percent_of_amount`
4. Adjust max positions

Then I implement exclusion list separately.

**Which approach do you prefer?**
