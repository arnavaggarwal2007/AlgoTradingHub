# QUICK REFERENCE - New Features

## 🚀 Quick Start

### 1. Delete Old Databases (Required)
```powershell
cd c:\Alpaca_Algo\Single_Buy
del positions.db

cd c:\Alpaca_Algo\Dual_Buy  
del positions_dual.db
```

### 2. Run Bot (Auto-creates new tables)
```powershell
cd c:\Alpaca_Algo\Single_Buy
python rajat_alpha_v67.py
```

---

## ⚙️ Configuration Quick Reference

### Feature 1: Max Trades Per Day
**File:** `config.json` or `config_dual.json`
```json
"trading_rules": {
    "max_trades_per_day": 3
}
```
- Default: 3 trades per day
- Set to 99 to disable

---

### Feature 2: Smart Execution Queue
**File:** `config.json` or `config_dual.json`
```json
"execution_schedule": {
    "enable_smart_execution": true,      // true=queue, false=immediate
    "signal_monitoring_minutes": 15,     // Collection period
    "top_n_trades": 5                    // Execute top N
}
```
- `true` = Collect 15 min, execute top 5
- `false` = Original immediate execution

---

### Feature 3: Extended Stock Filter
**File:** `config.json` or `config_dual.json`
```json
"strategy_params": {
    "enable_extended_filter": true,  // true=filter, false=allow all
    "max_gap_pct": 0.04              // 4% max gap allowed
}
```
- Rejects stocks gapped up >4% from prev close
- Set to `false` to disable

---

### Feature 4: Signal History
**No config needed** - Always active
- Logs all signals to database
- Check with SQL queries

---

## 📊 Database Queries

### Access Database
```powershell
cd c:\Alpaca_Algo\Single_Buy
sqlite3 positions.db
```

### Useful Queries
```sql
-- Today's signals
SELECT symbol, score, pattern, executed 
FROM signal_history 
WHERE signal_date = date('now');

-- Missed opportunities (not executed, score >= 4)
SELECT symbol, score, pattern, price 
FROM signal_history 
WHERE executed = 0 AND score >= 4;

-- Daily trade count
SELECT COUNT(*) FROM positions 
WHERE date(entry_date) = date('now');

-- Exit database
.quit
```

---

## 🔍 Log Monitoring

### What to Look For

**Max Trades Per Day:**
```
Daily trade limit reached (3/3), no new buys
```

**Extended Stock Filter:**
```
[NVDA] Stock is EXTENDED - Gap up 5.23% (max allowed: 4.0%)
```

**Smart Execution:**
```
--- SIGNAL COLLECTION PHASE ---
[AAPL] Added to signal queue (Score: 4)
--- EXECUTION PHASE: Processing Top Signals ---
  #1: MSFT - Score: 5/5, Pattern: Engulfing
```

---

## 🎯 Testing Checklist

- [ ] Delete old database files
- [ ] Start bot in paper trading
- [ ] Wait for buy window (3:00-4:00 PM EST)
- [ ] Check logs for "SIGNAL COLLECTION PHASE"
- [ ] Verify top signals executed after 15 min
- [ ] Query `signal_history` table
- [ ] Verify max 3 trades per day

---

## 🛠️ Troubleshooting

**Issue:** Bot crashes on startup
- **Fix:** Delete `positions.db` and `positions_dual.db`

**Issue:** Smart execution not working
- **Check:** `enable_smart_execution` is `true`
- **Check:** In buy window (3:00-4:00 PM EST)

**Issue:** Extended filter too strict
- **Fix:** Increase `max_gap_pct` to 0.06 (6%)

**Issue:** Signal history table missing
- **Fix:** Delete database or manually add table (see implementation summary)

---

## 📞 Support

- Full documentation: [IMPLEMENTATION_SUMMARY_2026-01-15.md](IMPLEMENTATION_SUMMARY_2026-01-15.md)
- Check logs: `rajat_alpha_v67.log`
- Database: `positions.db` (Single_Buy) or `positions_dual.db` (Dual_Buy)
