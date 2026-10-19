# Issue Analysis: Bug vs Account Problem?

**Date:** February 16, 2026  
**Trading Mode:** PAPER TRADING (No Real Money)  
**Question:** Are these script bugs or Alpaca account issues?

---

## TL;DR Answer

| Issue | Category | Severity | Cause |
|-------|----------|----------|-------|
| **Insufficient Buying Power Errors** | 🔵 **Alpaca Paper Trading Quirk** + 🟡 Script Logic Issue | HIGH | Paper trading capital exhausted; Script doesn't handle this gracefully |
| **Time Exit Signal Loop** | 🔴 **Script Bug** | MEDIUM | No retry limit on failed exits |
| **Position Saturation** | 🟢 **Expected Behavior** | LOW | Configuration limit (15 positions) combined with exit failures |

**Verdict:** Mix of issues - mostly script needs better error handling, but underlying trigger is Alpaca's paper trading behavior.

---

## Issue #1: Insufficient Buying Power (1,415 errors)

### The Error
```
{"buying_power":"0","code":40310000,"message":"insufficient buying power"}
```

### Analysis

#### ❓ The Puzzle
- You're trying to **SELL** positions (exit trades)
- Error says "insufficient buying power"
- But selling should **ADD** buying power, not require it!

#### 🔍 Root Cause (Paper Trading Specific)

This is **NOT a script bug** initially, but **HOW the script handles it IS a bug**.

**What's happening:**

1. **Paper Trading Capital Depletion**
   - Paper accounts typically start with $100,000
   - Your bot has been aggressively buying (9,549 buys in 12 days = 796/day!)
   - All paper capital is now deployed in 15 open positions
   - Buying power = $0

2. **Alpaca's Confusing Error Message**
   - When you try to sell with $0 buying power, Alpaca paper trading returns error code `40310000`
   - This error is typically for BUYING, not selling
   - This appears to be an **Alpaca API quirk** in paper trading mode

3. **Why This Doesn't Happen in Live Trading**
   - Live trading has different settlement rules
   - Selling immediately credits your account (or within T+2)
   - Paper trading simulates this but may have bugs

#### 🐛 Script Issues

1. **No Buying Power Check Before Trading**
   ```python
   # Script currently does:
   execute_full_exit(position)  # Just tries to exit
   
   # Should do:
   if check_buying_power() < minimum_threshold:
       alert("Low buying power - investigate")
       stop_new_trades()
   ```

2. **No Graceful Degradation**
   - Script assumes exits always work
   - When they fail, it just retries infinitely
   - No alerting or emergency stop

3. **No Exit Prioritization**
   - When capital is tight, should prioritize which exits to do first
   - Currently treats all exits equally

#### 🎯 Conclusion

**Primary Cause:** Alpaca paper trading behavior (all capital deployed)  
**Secondary Cause:** Script doesn't handle low buying power gracefully  
**Script Bug:** YES - lacks error handling and monitoring  
**Account Issue:** NO - paper trading is working as designed (poorly)

---

## Issue #2: Time Exit Signal Loop (1,483 warnings)

### The Error
```
[LLY] TIME EXIT SIGNAL (TES) triggered... (553 times)
[WELL] TIME EXIT SIGNAL (TES) triggered... (553 times)
```

### Analysis

#### 🐛 This is 100% a Script Bug

**What's happening:**

```python
# Current logic (simplified):
while True:
    for position in positions:
        if days_held > max_days:
            execute_full_exit(position)  # Triggers TES
            # Exit fails due to buying power error
            # Position remains in database as 'active'
            # Next loop iteration: Still exceeds max_days
            # Triggers TES again
            # Infinite loop! 🔁
```

**What the script SHOULD do:**

```python
# Proper logic:
failed_exits = {}  # Track failed attempts

while True:
    for position in positions:
        if days_held > max_days:
            # Check if we already tried and failed
            if position['id'] in failed_exits:
                attempt_count = failed_exits[position['id']]
                if attempt_count >= 3:
                    logger.error(f"Position {position['id']} stuck - needs manual intervention")
                    send_alert(f"STUCK POSITION: {position['symbol']}")
                    continue  # Skip this position
            
            # Try to exit
            success = execute_full_exit(position)
            
            if not success:
                # Track failure
                failed_exits[position['id']] = failed_exits.get(position['id'], 0) + 1
```

#### 🎯 Conclusion

**Primary Cause:** Script bug - no retry limit  
**Secondary Cause:** No tracking of failed exit attempts  
**Script Bug:** YES - definitely  
**Account Issue:** NO - this is pure logic error

---

## Issue #3: Position Saturation (15/15 positions)

### The Error
```
No execution slots available (Positions: 15/15, Daily: 0/3)
```

### Analysis

#### ✅ This is EXPECTED BEHAVIOR, not a bug

**What's happening:**

1. **Configuration Limit**
   ```json
   {
     "max_positions": 15,
     "daily_max_new_positions": 3
   }
   ```
   - You configured the bot to hold max 15 positions
   - And open max 3 new positions per day

2. **Exit Failures → Position Accumulation**
   ```
   Day 1: Open 3 positions → Total: 3
   Day 2: Open 3 positions → Total: 6
   Day 3: Open 3 positions → Total: 9
   Day 4: Open 3 positions → Total: 12
   Day 5: Open 3 positions → Total: 15 (LIMIT REACHED)
   Day 6: Cannot open new positions (15/15)
         Exit attempts fail due to buying power
         Still stuck at 15/15
   Day 7+: Still stuck because exits keep failing
   ```

3. **Daily Slots: 0/3**
   - You've already opened 3 new positions today
   - Daily limit exhausted
   - Must wait until tomorrow

#### 🎯 Conclusion

**Primary Cause:** Exit failures (Issue #1) preventing position turnover  
**Secondary Cause:** Aggressive buy strategy (796 buys/day average)  
**Script Bug:** NO - working as configured  
**Account Issue:** NO - this is by design

**However**, there IS a design issue:
- No emergency position reduction when exits are failing
- No dynamic adjustment of position limits based on success rate
- No priority exit queue

---

## Overall Diagnosis

### 🔴 Is This Your Script's Fault?

**Partially YES:**

1. **Lack of Error Handling** - Script assumes happy path always works
2. **No Retry Limits** - Infinite retry loops for failed operations
3. **No Monitoring** - Doesn't detect or alert on systemic failures
4. **No Circuit Breakers** - Keeps trading even when exits are failing
5. **Poor Buying Power Management** - Doesn't check or track buying power

### 🔵 Is This Alpaca's Fault?

**Partially YES:**

1. **Confusing Error Messages** - "Insufficient buying power" for SELL orders is misleading
2. **Paper Trading Quirks** - Paper trading doesn't perfectly simulate live trading
3. **Poor Documentation** - Alpaca doesn't clearly explain paper trading limits

### 🟢 Is This Expected Behavior?

**Partially YES:**

1. **Capital Depletion** - You deployed all $100k paper money (expected with aggressive strategy)
2. **Position Limits** - 15/15 is your configured limit (working as designed)
3. **PDT Simulation** - Paper trading may simulate PDT rules (though shouldn't)

---

## Comparison: If This Were Live Trading

If you were using REAL MONEY instead of paper trading:

| Issue | In Paper Trading | In Live Trading |
|-------|------------------|-----------------|
| **Buying Power Errors** | Common (capital exhausted) | Rare (selling adds buying power immediately or T+2) |
| **Exit Failures** | Due to paper trading quirk | Would likely succeed |
| **TES Loop** | Still a bug | Still a bug (but masked if exits work) |
| **Position Saturation** | Due to exit failures | Less likely (exits would work) |

**Key Difference:** Live trading has better handling of buying power for sell orders.

---

## Proof: Check These Facts

Run these scripts to confirm the diagnosis:

### 1. Check Account Status

```bash
cd C:\Alpaca_Algo\Single_Buy
python scripts/check_account_status.py
```

**What to look for:**
- Buying Power: $0 or very low?
- Account Status: Active?
- Trading Blocked: False?
- Pattern Day Trader: Should be False for paper trading

### 2. Check Positions

```bash
cd C:\Alpaca_Algo\Single_Buy
python scripts/check_positions.py
```

**What to look for:**
- How many positions are open? (Expecting 15)
- Are LLY, WELL, TKO among them?
- Days held for each position
- Database vs Alpaca sync status

### 3. Check Database

```bash
cd C:\Alpaca_Algo\Single_Buy
python scripts/db_manager.py --positions
```

**What to look for:**
- Active positions count
- Remaining quantity for each
- Any negative quantities?

---

## The Smoking Gun 🔫

Look at this progression from your logs:

| Date | Errors | Buys | Exits | Buy/Exit Ratio |
|------|--------|------|-------|----------------|
| Feb 2 | 0 | ~6000 | ~323 | 18.6:1 |
| Feb 3-10 | 0-19 | ~1000/day | ~100/day | 10:1 |
| Feb 11 | 312 | ~700 | ~221 | 3.2:1 |
| Feb 12 | 494 | ~1000 | ~645 | 1.5:1 |
| Feb 13 | 578 | ~1500 | ~745 | 2:1 |

**What this shows:**

1. **Feb 2:** MASSIVE buying day (6,323 trades - this is unusual!)
   - Likely bot restart or backlog processing
   - Deployed most of the $100k capital

2. **Feb 3-10:** Normal operation but high buy/exit ratio
   - Buying outpaced exits 10:1
   - Capital accumulating in positions

3. **Feb 11:** First error spike (312 errors)
   - **This is when buying power likely hit $0**
   - Exits started failing
   - TES loop began

4. **Feb 12-13:** Crisis escalation
   - Exit failure rate increased
   - TES warnings multiplied
   - System in degraded state

**Conclusion:** The bot ran out of paper money on Feb 11, and everything cascaded from there.

---

## Solutions

### Immediate Fixes (Do These Now)

#### 1. Reset Paper Trading Account
```
1. Go to: https://app.alpaca.markets/paper/dashboard/overview
2. Click "Reset Paper Account" (restores to $100,000)
3. This clears all positions and resets capital
4. Restart your bot
```

**Pros:**
- Quick and easy
- Clean slate
- No manual position management

**Cons:**
- Loses historical paper trading data
- Any profitable positions are closed

#### 2. Manually Close Stuck Positions

```bash
# First, identify them
python scripts/check_positions.py

# Then close them via Alpaca dashboard
# Go to: https://app.alpaca.markets/paper/dashboard/positions
# Close: LLY, WELL, TKO (and any others held > 7 days)
```

**Pros:**
- Preserves other positions
- Frees up capital gradually
- Maintains historical data

**Cons:**
- Manual work
- Partial solution (buying power still low)

### Code Fixes (Already Partially Done)

#### ✅ Already Fixed: Short Sell Protection

We added safeguards in the code review:
```python
# In execute_full_exit()
if remaining_qty <= 0:
    logger.warning(f"Cannot execute full exit - already exited")
    return

# In execute_partial_exit()
if quantity > position['remaining_qty']:
    logger.error(f"Cannot execute partial exit - trying to sell {quantity} but only {remaining_qty} remaining")
    return
```

#### ⏳ Still Needed: Exit Retry Limits

Add to the code:

```python
# Add to PositionManager class
self.failed_exits = {}  # position_id: (attempt_count, last_attempt_time)

def execute_full_exit(self, position: Dict, current_price: float, reason: str):
    """Execute full position exit (FIFO)"""
    symbol = position['symbol']
    remaining_qty = position['remaining_qty']
    pos_id = position['id']
    
    # Check if position still has shares to sell
    if remaining_qty <= 0:
        logger.warning(f"[{symbol}] Cannot execute full exit - position already fully exited")
        return
    
    # ✅ NEW: Check exit attempt history
    if pos_id in self.failed_exits:
        count, last_time = self.failed_exits[pos_id]
        if count >= 3:
            logger.error(f"[{symbol}] Position {pos_id} failed to exit {count} times - STUCK! Manual intervention needed")
            # Send alert email/SMS here
            return
        
        # Cooldown: Don't retry if we just tried < 1 hour ago
        if time.time() - last_time < 3600:
            return
    
    # Try to exit
    try:
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=remaining_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        order = self.trading_client.submit_order(order_request)
        
        # Success - clear failure tracking
        if pos_id in self.failed_exits:
            del self.failed_exits[pos_id]
        
        # ... rest of code
    
    except Exception as e:
        # ✅ NEW: Track failure
        if "insufficient buying power" in str(e).lower():
            logger.error(f"[{symbol}] Exit failed: {e}")
            self.failed_exits[pos_id] = (
                self.failed_exits.get(pos_id, (0, 0))[0] + 1,
                time.time()
            )
        else:
            raise
```

#### ⏳ Still Needed: Buying Power Monitoring

```python
def check_buying_power(self):
    """Check if we have sufficient buying power"""
    account = self.trading_client.get_account()
    buying_power = float(account.buying_power)
    
    if buying_power < 1000:  # Less than $1k
        logger.warning(f"Low buying power: ${buying_power:.2f}")
        return False
    
    return True

def run(self):
    """Main trading loop"""
    while True:
        # ... existing code ...
        
        # ✅ NEW: Check buying power before trading
        if not self.check_buying_power():
            logger.error("Buying power too low - pausing new trades")
            # Still run sell guardian to try to free up capital
            self.run_sell_guardian()
            continue  # Skip signal scanning and new buys
```

---

## Final Verdict

### Bug vs Account Issue Scorecard

| Aspect | Score | Notes |
|--------|-------|-------|
| **Script Bugs** | 🔴🔴🔴⚪⚪ | 3/5 - Significant issues but not catastrophic |
| **Alpaca Issues** | 🟡🟡⚪⚪⚪ | 2/5 - Paper trading quirks and confusing errors |
| **Configuration Issues** | 🟢⚪⚪⚪⚪ | 1/5 - Aggressive settings but working as designed |
| **User Error** | ⚪⚪⚪⚪⚪ | 0/5 - You didn't do anything wrong |

### Summary

**What Broke:** Paper trading capital exhausted + script can't handle exit failures gracefully

**Who's Responsible:**
- **40%** Script (poor error handling)
- **30%** Alpaca (confusing paper trading behavior)
- **20%** Strategy (very aggressive buying)
- **10%** Bad luck (all happened at once on Feb 11)

**Good News:**
- ✅ No real money at risk
- ✅ Easy to fix (reset paper account or close positions)
- ✅ Great learning opportunity
- ✅ Found bugs before live trading!

**Can Run With Confidence After:**
1. Resetting paper account OR closing stuck positions
2. Adding exit retry limits (code provided above)
3. Adding buying power monitoring (code provided above)
4. Monitoring daily with log analyzer tools

---

## How to Run the Diagnostic Scripts

### PowerShell (Windows)

```powershell
# Navigate to project
cd C:\Alpaca_Algo\Single_Buy

# Check account status
python scripts/check_account_status.py

# Check positions
python scripts/check_positions.py

# Check database
python scripts/db_manager.py --positions
```

### Expected Output

If diagnosis is correct, you'll see:
- ✅ Buying power: $0 or very low
- ✅ 15 active positions
- ✅ LLY, WELL, TKO among them
- ✅ Some positions held > 7 days
- ✅ Account status: Active (no blocks)
- ✅ Pattern Day Trader: False

---

**Next Step:** Run `python scripts/check_account_status.py` and share the output to confirm this diagnosis!
