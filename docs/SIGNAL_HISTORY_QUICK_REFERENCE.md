# Signal History - Quick Reference

**All 4 implementations now have signal_history tracking**

---

## 📊 What Gets Tracked

Every buy signal (executed OR rejected) is logged:
- Symbol
- Date
- Score (0-5)
- Pattern (engulfing/piercing/tweezer/none)
- Price at signal
- Rejection reason (if not executed)
- Executed flag (True/False)

---

## 🗄️ Database Locations

| Implementation | Database Path | Status |
|----------------|---------------|--------|
| Alpaca Single Buy | `Single_Buy/positions.db` | ✅ Has signal_history |
| Alpaca Dual Buy | `Dual_Buy/positions_dual.db` | ✅ Migrated |
| E*TRADE Single | `Etrade_Algo/single_Trade/positions_etrade.db` | ✅ Added |
| E*TRADE Dual | `Etrade_Algo/dual_trade/positions_etrade_dual.db` | ✅ Added |

---

## 🔍 Quick Queries

### View Today's Signals
```powershell
python utils\database\db_explorer.py --query "SELECT * FROM signal_history WHERE signal_date = date('now') ORDER BY score DESC"
```

### Rejected Signals
```powershell
python utils\database\db_explorer.py --query "SELECT symbol, score, pattern, reason FROM signal_history WHERE executed = 0 ORDER BY signal_date DESC LIMIT 10"
```

### Pattern Performance
```powershell
python utils\database\db_explorer.py --query "SELECT pattern, COUNT(*) as signals, SUM(executed) as executed, ROUND(SUM(executed)*100.0/COUNT(*),1) as exec_rate FROM signal_history GROUP BY pattern"
```

### High Score Rejections
```powershell
python utils\database\db_explorer.py --query "SELECT * FROM signal_history WHERE score >= 4 AND executed = 0 ORDER BY signal_date DESC"
```

---

## 🛠️ For Dual Buy

Add `--dual` flag:
```powershell
python utils\database\db_explorer.py --dual --query "SELECT * FROM signal_history WHERE signal_date = date('now')"
```

---

## 🚨 If Database Missing signal_history

### For Dual_Buy (Alpaca):
```powershell
python utils\database\migrate_dual_buy_db.py
```

### For New Databases:
Delete old database - it will be recreated with signal_history on next run.

---

## 📝 Schema

```sql
CREATE TABLE signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    score REAL,
    pattern TEXT,
    price REAL,
    reason TEXT,
    executed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

---

**Last Updated:** January 16, 2026
