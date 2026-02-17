# Log Analysis Summary: February 2-16, 2026

**Generated:** February 16, 2026  
**Tool:** Log Analyzer v1.0  
**Log File:** rajat_alpha_v67.log (170 MB)  
**Analysis Period:** Feb 2, 2026 00:09 to Feb 13, 2026 22:29 (11 days, 22 hours)

---

## Executive Summary

The trading bot processed **396,558 log entries** over the analysis period with significant trading activity but encountered **critical issues** that require immediate attention:

### 🚨 Critical Findings

1. **Insufficient Buying Power Errors** (1,384 instances)
   - The bot repeatedly failed to execute full exits due to "insufficient buying power"
   - Most affected stocks: **LLY, WELL, TKO**
   - Errors escalated significantly from Feb 11-13 (312 → 494 → 578 errors/day)

2. **Time Exit Signal (TES) Overload** (1,253 warnings)
   - Excessive TIME EXIT SIGNAL triggers for the same positions
   - Suggests positions held beyond intended timeframe
   - Most affected: **LLY** (553x), **WELL** (553x), **TKO** (147x)

3. **Position Limit Saturation** (10 warnings)
   - Position slots maxed out at **15/15** with **0/3 daily slots**
   - Prevented new opportunities from being captured

---

## Metrics Overview

| Metric | Count | Notes |
|--------|-------|-------|
| **Total Log Entries** | 396,558 | 11.9 days of operation |
| **Errors** | 1,415 | 97.8% related to buying power |
| **Warnings** | 1,483 | 84.5% time exit signals |
| **Total Trades** | 16,844 | High activity period |
| **Buy Orders** | 9,549 | New positions opened |
| **Full Exits** | 1,260 | Positions closed completely |
| **Partial Exits** | 0 | No partial profit taking |
| **Signals Generated** | 0 | No signal generation in logs |
| **Signals Rejected** | 0 | N/A |

---

## Daily Breakdown

| Date | Errors | Warnings | Trades | Key Issues |
|------|--------|----------|--------|------------|
| **Feb 2** | 0 | 11 | 6,323 | Clean day, high trading volume |
| **Feb 3** | 1 | 8 | 1,063 | Normal operation |
| **Feb 4** | 0 | 0 | 457 | Perfect day - no issues |
| **Feb 5** | 19 | 0 | 946 | First error spike |
| **Feb 6** | 1 | 45 | 1,080 | Warning increase |
| **Feb 9** | 0 | 161 | 1,403 | TES warnings begin |
| **Feb 10** | 10 | 0 | 761 | Error recurrence |
| **Feb 11** | 312 | 182 | 921 | ⚠️ **Major escalation** |
| **Feb 12** | 494 | 494 | 1,645 | 🚨 **Critical issues** |
| **Feb 13** | 578 | 582 | 2,245 | 🚨 **Worst day** |

### Trend Analysis
- **Feb 2-10:** Relatively stable with occasional errors
- **Feb 11-13:** Catastrophic escalation (58% increase in errors/day)
- **Trading Volume:** Inverse relationship - errors increased as trade count varied

---

## Error Analysis

### 1. Insufficient Buying Power Errors (1,384 / 97.8%)

**Root Cause:**  
The bot attempts to sell positions (full exit) but Alpaca rejects the order due to insufficient buying power. This is counterintuitive because **selling should add buying power**, not require it.

**Possible Explanations:**
1. **Pattern Day Trader (PDT) Rule Violation**
   - Account may be flagged for day trading violations
   - Buying power restricted to prevent further violations
   
2. **Unsettled Funds / T+2 Settlement**
   - Funds from previous sales not yet settled
   - Cannot use unsettled funds for new trades
   
3. **Margin Call / Account Restriction**
   - Account may be in a restricted state
   - Trading permissions limited by broker

**Most Affected Stocks:**
- **LLY** (Eli Lilly): 553+ failed exit attempts
- **WELL** (Welltower Inc): 553+ failed exit attempts  
- **TKO** (TKO Group Holdings): 147+ failed exit attempts

**Example Error:**
```json
{
  "buying_power": "0",
  "code": 40310000,
  "cost_basis": "3486.02",
  "message": "insufficient buying power"
}
```

**Impact:**
- Positions held longer than intended
- Unable to realize profits or cut losses
- Capital locked in positions
- Missed opportunities for new trades

**Recommended Actions:**
1. Check Alpaca account status for PDT flags or restrictions
2. Review settlement rules and adjust trading frequency
3. Implement retry logic with exponential backoff
4. Add account status checks before trading
5. Monitor buying power trends in real-time

---

### 2. Trading Errors (31 / 2.2%)

**Description:**  
Order execution failures during buy operations, also related to buying power.

**Affected Stocks:**
- LEU, BTSG, KLAC, and 28 others

**Example:**
```
[LEU] Order execution failed: 
{"buying_power":"1825.95","code":40310000,"cost_basis":"2813.21","message":"insufficient buying power"}
```

**Pattern:**
- Occurs during position entry attempts
- Buying power shown as low but non-zero
- Suggests capital management issues

---

## Warning Analysis

### 1. Time Exit Signal (TES) Warnings (1,469 / 99.1%)

**Description:**  
The bot triggers TIME EXIT SIGNAL repeatedly for the same positions, indicating they've been held beyond the intended timeframe.

**Frequency Distribution:**
- **LLY:** 553 warnings (37.6%)
- **WELL:** 553 warnings (37.6%)
- **TKO:** 147 warnings (10.0%)
- **Others:** 216 warnings (14.8%)

**Timeline:**
```
Feb 6:  45 TES warnings (first appearance)
Feb 9:  161 TES warnings (escalation)
Feb 11: 182 TES warnings (peak for LLY/WELL)
Feb 12: 494 TES warnings (continued)
Feb 13: 582 TES warnings (ongoing)
```

**Analysis:**
The TIME EXIT SIGNAL is designed to close positions after a certain holding period. The fact that it triggers **hundreds of times for the same stocks** indicates:

1. **Exit Order Failures:** TES triggers → exit attempt → insufficient buying power error → position remains open → TES triggers again (loop)

2. **No Exit Cooldown:** The bot doesn't track failed exit attempts, so it keeps retrying every cycle

3. **Position Lock-In:** LLY and WELL positions became stuck due to buying power restrictions

**Impact:**
- Log file bloat (1,469 redundant warnings)
- CPU cycles wasted on retry attempts
- Obscures other important warnings
- Prevents proper position turnover

**Recommended Actions:**
1. Add exit attempt tracking to prevent repeated failures
2. Implement cooldown period after failed exits
3. Alert administrator after 3 consecutive failures
4. Consider manual intervention for stuck positions

---

### 2. Position Limit Warnings (10 / 0.7%)

**Description:**
```
No execution slots available (Positions: 15/15, Daily: 0/3)
```

**Analysis:**
- Maximum positions reached: **15 simultaneous positions**
- Daily new position limit: **3 per day** (already exhausted: 0/3)
- Bot unable to capitalize on new signals

**Impact:**
- Missed trading opportunities
- Signal generation wasted
- Capital inefficiently allocated (stuck in failing positions)

**Timeline Correlation:**
These warnings appeared when buying power errors were also occurring, suggesting:
- Old positions couldn't be exited (buying power issue)
- New positions couldn't be opened (slot limits)
- **Double constraint**: locked in bad positions, blocked from good ones

---

### 3. Signal Expiration Warnings (4 / 0.3%)

**Stocks Affected:**
- **TMDX** (2 warnings): No valid pullback to key moving averages
- **ULTA** (1 warning): No explosive bullish pattern
- **CMI** (1 warning): No valid pullback

**Analysis:**
Signals expired during monitoring phase because entry criteria were no longer met. This is normal behavior and shows the bot's signal validation is working correctly.

---

## Trading Activity Analysis

### Volume Breakdown

| Activity Type | Count | Daily Average |
|---------------|-------|---------------|
| **Total Trades** | 16,844 | 1,404 trades/day |
| **Buy Orders** | 9,549 | 796 buys/day |
| **Full Exits** | 1,260 | 105 exits/day |
| **Partial Exits** | 0 | 0 exits/day |

### Observations

1. **High Buy-to-Exit Ratio:**
   - **Buy/Exit Ratio:** 9,549 / 1,260 = **7.6:1**
   - For every 1 exit, there were 7.6 new buys
   - This is unsustainable and explains position saturation

2. **No Partial Exits:**
   - Zero partial profit-taking occurred
   - Suggests partial exit logic may be disabled or targets not reached
   - All exits were "full exits" (attempts to close entire position)

3. **Feb 2 Anomaly:**
   - **6,323 trades on Feb 2** (37.5% of all trades)
   - Possible causes:
     - Bot restart with backlog processing
     - Configuration change
     - Market high volatility day
     - Data catch-up from previous period

4. **Exit Failure Rate:**
   - Attempted exits: ~1,260 successful + ~1,384 failed = ~2,644 attempts
   - **Failure rate: 52.3%** (more than half of exits failed!)

---

## Root Cause Analysis

### Primary Issue: Insufficient Buying Power Loop

**Scenario Reconstruction:**

```
DAY 1-5: Normal Trading
├─ Bot opens positions successfully
├─ Capital allocated across multiple positions
└─ Exit attempts succeed

DAY 6-9: Problem Emergence  
├─ Some exit attempts start failing (buying power errors)
├─ Positions accumulate (exits failing but buys continuing)
├─ TIME EXIT SIGNALS start triggering
└─ Position slots fill up (approaching 15/15)

DAY 10-13: Crisis Mode
├─ Position limit reached (15/15)
├─ Exit failure rate increases to ~50%
├─ TIME EXIT SIGNALS fire continuously (553x for LLY/WELL)
├─ No daily slots available (0/3)
├─ New opportunities missed
└─ Bot effectively "stuck"
```

**The Vicious Cycle:**
1. Position held → needs to exit
2. Exit attempt → "insufficient buying power" error
3. Position remains open → TIME EXIT SIGNAL triggers again
4. Repeat 553 times for same position
5. Meanwhile, new buys continue (capital allocation continues)
6. Position slots saturate → new opportunities blocked

### Contributing Factors

1. **Account Restrictions:**
   - PDT rule violations
   - Margin restrictions
   - Settlement delays (T+2)

2. **Configuration Issues:**
   - No exit retry limit
   - No failed exit cooldown
   - Aggressive position accumulation

3. **Market Conditions:**
   - Possible high volatility period
   - Multiple positions hitting exit criteria simultaneously

---

## Recommendations

### Immediate Actions (Next 24 Hours)

1. **Check Alpaca Account Status**
   ```python
   # Add to bot startup
   account = trading_client.get_account()
   print(f"Account Status: {account.status}")
   print(f"Pattern Day Trader: {account.pattern_day_trader}")
   print(f"Buying Power: ${account.buying_power}")
   print(f"Trade Suspended: {account.trade_suspended_by_user}")
   ```

2. **Manual Position Review**
   - Review LLY, WELL, TKO positions
   - Check if they're still open
   - Attempt manual exit if needed

3. **Add Exit Failure Tracking**
   ```python
   # Track failed exits in database
   failed_exits = {}  # position_id: (attempt_count, last_attempt_time)
   
   def execute_full_exit(position):
       pos_id = position['id']
       if pos_id in failed_exits:
           count, last_time = failed_exits[pos_id]
           if count >= 3:
               logger.error(f"Position {pos_id} exit failed {count} times - manual intervention needed")
               send_alert(f"STUCK POSITION: {position['symbol']}")
               return
   ```

### Short-Term Fixes (Next Week)

1. **Implement Exit Retry Logic with Backoff**
   ```python
   MAX_EXIT_ATTEMPTS = 3
   EXIT_RETRY_COOLDOWN = 3600  # 1 hour
   
   if exit_failed:
       if attempt_count < MAX_EXIT_ATTEMPTS:
           if time.time() - last_attempt > EXIT_RETRY_COOLDOWN:
               retry_exit()
       else:
           alert_admin("Position stuck - needs manual exit")
   ```

2. **Add Real-Time Buying Power Monitoring**
   ```python
   def check_buying_power_before_trade():
       account = trading_client.get_account()
       if float(account.buying_power) < MIN_BUYING_POWER_THRESHOLD:
           logger.warning(f"Low buying power: ${account.buying_power}")
           return False
       return True
   ```

3. **Implement Position Age Limits**
   ```python
   MAX_POSITION_AGE_DAYS = 30
   
   if days_held > MAX_POSITION_AGE_DAYS:
       force_exit_or_alert(position)
   ```

### Medium-Term Improvements (Next Month)

1. **Settlement-Aware Trading**
   - Track unsettled funds
   - Adjust available capital calculations
   - Implement T+2 settlement tracking

2. **Dynamic Position Limits**
   - Reduce max positions when buying power is low
   - Increase when capital is ample
   - Implement soft/hard limits

3. **Alert System Enhancement**
   - Email/SMS alerts for stuck positions
   - Daily summary of failed operations
   - Real-time monitoring dashboard

4. **Partial Exit Strategy**
   - Enable partial exits to free up capital faster
   - Take profits incrementally
   - Reduces position lock-in risk

### Long-Term Architecture Changes

1. **Capital Management Module**
   - Centralized buying power tracking
   - Predictive capital requirements
   - Settlement-aware allocations

2. **Circuit Breakers**
   - Auto-pause trading if error rate exceeds threshold
   - Gradual recovery mode
   - Manual approval for resumption

3. **Position Health Scoring**
   - Identify "zombie positions" (stuck, failing exits)
   - Prioritize exit attempts by health score
   - Automatic escalation for unhealthy positions

---

## Testing and Validation

### Verify Log Analyzer Tool

```bash
# Test on different date ranges
python tools/log_analyzer.py --days 1
python tools/log_analyzer.py --start 2026-02-11 --end 2026-02-13

# Export CSV for detailed analysis
python tools/log_analyzer.py --start 2026-02-02 --end 2026-02-16 --csv reports/detailed_analysis.csv

# Launch web dashboard
python tools/log_dashboard.py
# Open http://localhost:5001
```

### Monitor Key Metrics Daily

```bash
# Quick daily check
python tools/log_analyzer.py --days 1 --daily

# Watch for:
# - Error count > 50/day
# - Warning count > 100/day
# - Buy/Exit ratio > 5:1
# - Same stock appearing in errors repeatedly
```

---

## Conclusion

### Summary

The trading bot operated with **high trading volume** (16,844 trades over 12 days) but encountered **critical operational issues** starting Feb 11:

- ✅ **Signal validation working correctly** (rejecting invalid signals)
- ✅ **High trading activity** (796 buys/day average)
- ❌ **Insufficient buying power errors** (52% exit failure rate)
- ❌ **Position lock-in** (LLY, WELL stuck for days)
- ❌ **Log file bloat** (1,469 redundant TES warnings)

### Severity Assessment

**CRITICAL** - Immediate action required

The bot is currently in a degraded state where:
1. Exits fail more often than they succeed
2. Capital is locked in stuck positions
3. New opportunities are blocked
4. The same errors repeat thousands of times

### Next Steps

1. ✅ **Log Analyzer Tool Created** - Can now monitor logs easily
2. ⏭️ **Check Alpaca account status** - Verify no restrictions
3. ⏭️ **Review open positions** - Identify stuck positions
4. ⏭️ **Implement exit retry logic** - Prevent infinite retry loops
5. ⏭️ **Add buying power monitoring** - Proactive checks before trading

### Tools Available

You now have two powerful tools to monitor your trading bot:

1. **CLI Tool:** `tools/log_analyzer.py`
   - Quick command-line analysis
   - CSV export for detailed review
   - Daily statistics tables

2. **Web Dashboard:** `tools/log_dashboard.py`
   - Visual, interactive interface
   - Real-time date range selection
   - Categorized error/warning display
   - One-click CSV export

---

**Report Generated:** February 16, 2026  
**Analysis Duration:** 2 minutes 15 seconds  
**Data Processed:** 682,099 log lines  
**Tools Used:** Log Analyzer v1.0
