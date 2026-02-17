# Utility Tools - Alpaca_Algo

Organized collection of helper scripts for testing, database access, and performance analysis.

---

## 📂 FOLDER STRUCTURE

```
utils/
├── testing/         # Testing & validation scripts
├── database/        # Database access tools
└── analysis/        # Performance analytics
```

---

## 🧪 TESTING TOOLS (`utils/testing/`)

### test_connection.py
**Purpose:** Validate Alpaca API connectivity

**Usage:**
```powershell
python utils/testing/test_connection.py
```

**What it checks:**
- API key authentication
- Market data access
- Account information retrieval
- Order placement permissions

---

### test_exclusion_*.py
**Purpose:** Validate exclusion list filtering logic

**Scripts:**
- `test_exclusion_comprehensive.py` - Full test suite with edge cases
- `test_exclusion_direct.py` - Direct function testing
- `test_exclusion_feature.py` - Feature-level testing

**Usage:**
```powershell
python utils/testing/test_exclusion_comprehensive.py
```

**Test coverage:**
- Exact ticker matching
- Case sensitivity
- Whitespace handling
- Empty exclusion list
- Duplicate entries

---

### validate_deployment.py
**Purpose:** Pre-deployment validation checklist

**Usage:**
```powershell
# Validate Single_Buy
cd Single_Buy
python ../utils/testing/validate_deployment.py

# Validate Dual_Buy
cd Dual_Buy
python ../utils/testing/validate_deployment.py
```

**Validates:**
- Config file exists and is valid JSON
- Required list files (watchlist, exclusionlist, selllist)
- Python dependencies installed
- Database schema correct
- API credentials configured

---

### verify_all_scripts.py
**Purpose:** Check all Python files for syntax errors

**Usage:**
```powershell
python utils/testing/verify_all_scripts.py
```

**What it does:**
- Compiles all `.py` files in workspace
- Reports syntax errors
- Validates import statements
- Checks for missing dependencies

---

## 🗄️ DATABASE TOOLS (`utils/database/`)

### db_explorer.py
**Purpose:** Interactive SQLite database query tool

**Usage:**
```powershell
# Interactive mode - Single_Buy
python utils/database/db_explorer.py

# Interactive mode - Dual_Buy
python utils/database/db_explorer.py --dual

# Single query
python utils/database/db_explorer.py --query "SELECT * FROM positions WHERE status='OPEN'"

# For Dual_Buy with query
python utils/database/db_explorer.py --dual --query "SELECT * FROM positions WHERE position_type='B2'"
```

**Interactive Commands:**
```sql
-- Show table structures
.schema

-- Show common queries
.queries

-- Run custom queries
SELECT * FROM positions WHERE entry_date >= '2026-01-01';

-- Exit
exit
```

**Key Features:**
- Auto-detects database location (Single_Buy or Dual_Buy)
- Formatted table output
- Common query templates
- Error handling with helpful messages

**Common Queries:**
```sql
-- Open positions
SELECT ticker, entry_price, current_price, unrealized_pnl 
FROM positions WHERE status='OPEN';

-- Recent trades
SELECT * FROM positions 
WHERE entry_date >= date('now', '-7 days') 
ORDER BY entry_date DESC;

-- Performance by score
SELECT 
    entry_score,
    COUNT(*) as trades,
    AVG(realized_pnl) as avg_pnl,
    SUM(realized_pnl) as total_pnl
FROM positions 
WHERE status='CLOSED' 
GROUP BY entry_score;

-- Signal history
SELECT * FROM signal_history 
WHERE timestamp >= datetime('now', '-1 day') 
ORDER BY timestamp DESC;

-- Partial exits
SELECT p.ticker, p.entry_price, pe.exit_price, pe.quantity, pe.pnl
FROM positions p
JOIN partial_exits pe ON p.ticker = pe.ticker
WHERE p.status='OPEN';
```

---

## 📊 ANALYSIS TOOLS (`utils/analysis/`)

### analyze_performance.py
**Purpose:** Generate performance reports by score and pattern

**Usage:**
```powershell
# Single_Buy analysis
python utils/analysis/analyze_performance.py

# Dual_Buy analysis (all positions)
python utils/analysis/analyze_performance.py --dual

# Dual_Buy - B1 only
python utils/analysis/analyze_performance.py --dual --b1

# Dual_Buy - B2 only
python utils/analysis/analyze_performance.py --dual --b2
```

**Reports Generated:**
1. **Performance by Score** - Breakdown by entry score (0-5)
2. **Performance by Pattern** - Stats by signal pattern (engulfing, piercing, etc.)
3. **Performance by Score & Pattern** - Cross-tabulation
4. **Position Type Comparison** (Dual_Buy only) - B1 vs B2 performance

**Output Example:**
```
Performance by Score:
Score | Trades | Win Rate | Avg P/L  | Total P/L | Avg Hold
------|--------|----------|----------|-----------|----------
5     | 12     | 75.0%    | $124.50  | $1,494.00 | 8.5 days
4     | 28     | 64.3%    | $89.30   | $2,500.40 | 11.2 days
3     | 45     | 55.6%    | $45.80   | $2,061.00 | 14.8 days

Performance by Pattern:
Pattern      | Trades | Win Rate | Avg P/L
-------------|--------|----------|---------
engulfing    | 32     | 68.8%    | $112.30
piercing     | 28     | 60.7%    | $78.50
tweezer      | 25     | 56.0%    | $52.20
```

---

## 📋 WORKFLOW EXAMPLES

### Daily Pre-Market Routine
```powershell
# 1. Test API connection
python utils/testing/test_connection.py

# 2. Validate deployment
cd Single_Buy
python ../utils/testing/validate_deployment.py

# 3. Check open positions
python ../utils/database/db_explorer.py --query "SELECT * FROM positions WHERE status='OPEN'"
```

---

### End of Week Analysis
```powershell
# 1. Generate performance report
python utils/analysis/analyze_performance.py

# 2. Review recent signals
python utils/database/db_explorer.py --query "
    SELECT * FROM signal_history 
    WHERE timestamp >= date('now', '-7 days')
    ORDER BY signal_score DESC
"

# 3. Check closed trades
python utils/database/db_explorer.py --query "
    SELECT ticker, entry_price, exit_price, realized_pnl, pattern 
    FROM positions 
    WHERE status='CLOSED' AND exit_date >= date('now', '-7 days')
"
```

---

### Debugging Failed Trades
```powershell
# 1. Check signal history for rejections
python utils/database/db_explorer.py --query "
    SELECT * FROM signal_history 
    WHERE timestamp >= date('now', '-1 day')
    ORDER BY timestamp DESC
"

# 2. Validate exclusion list logic
python utils/testing/test_exclusion_comprehensive.py

# 3. Review logs
Get-Content Single_Buy/rajat_alpha_v67.log -Tail 50
```

---

### Monthly Maintenance
```powershell
# 1. Verify all scripts compile
python utils/testing/verify_all_scripts.py

# 2. Full performance review
python utils/analysis/analyze_performance.py

# 3. Database integrity check
python utils/database/db_explorer.py --query ".schema"

# 4. Backup databases
copy Single_Buy/positions.db "Single_Buy/positions_backup_$(Get-Date -Format 'yyyy-MM-dd').db"
copy Dual_Buy/positions_dual.db "Dual_Buy/positions_dual_backup_$(Get-Date -Format 'yyyy-MM-dd').db"
```

---

## 🔧 UPDATING PATH REFERENCES

If you move these tools or need to run them from different locations:

### From Single_Buy folder:
```powershell
python ../utils/database/db_explorer.py
python ../utils/analysis/analyze_performance.py
python ../utils/testing/test_connection.py
```

### From Dual_Buy folder:
```powershell
python ../utils/database/db_explorer.py --dual
python ../utils/analysis/analyze_performance.py --dual
```

### From root (Alpaca_Algo):
```powershell
python utils/database/db_explorer.py
python utils/analysis/analyze_performance.py
```

---

## 📝 NOTES

- All testing tools work with both Single_Buy and Dual_Buy
- Database tools auto-detect folder structure
- Analysis tools require `--dual` flag for Dual_Buy
- Run from any directory - tools use relative paths

---

**Last Updated:** January 16, 2026
