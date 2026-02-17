# Utility Scripts Directory

This directory contains consolidated utility scripts that replace the numerous scattered check/query files.

## Available Scripts

### 1. `db_manager.py` - Database Query & Management Tool

**Purpose**: Unified interface for all database queries and inspection.

**Replaces**: 
- `check_db.py`
- `query_db.py`
- `check_signals.py`
- `check_trades.py`
- `check_recent_signals.py`
- `check_valid_signals.py`

**Usage Examples**:
```bash
# Show all tables and their schemas
python scripts/db_manager.py --tables

# View positions
python scripts/db_manager.py --positions              # All positions
python scripts/db_manager.py --positions-open         # Open only
python scripts/db_manager.py --positions-closed       # Closed only

# View signals
python scripts/db_manager.py --signals                # Recent signals (last 20)
python scripts/db_manager.py --signals-valid          # Valid signals only (score >= 2)
python scripts/db_manager.py --signals-today          # Today's signals
python scripts/db_manager.py --signals --limit 50     # Change limit

# View statistics
python scripts/db_manager.py --stats                  # Performance statistics

# Complete dashboard
python scripts/db_manager.py --all                    # Everything
```

**Features**:
- Tabular display with emojis for visual clarity
- Performance statistics by score and pattern
- Win rate and P/L analysis
- Flexible filtering and limits

---

### 2. `cleanup_db.py` - Database Maintenance Tool

**Purpose**: Database cleanup and maintenance operations.

**Replaces**:
- `cleanup_signals.py`

**Usage Examples**:
```bash
# Remove invalid signals (score <= 0)
python scripts/cleanup_db.py --remove-invalid

# Archive old closed positions
python scripts/cleanup_db.py --archive 90            # Archive positions older than 90 days

# Vacuum database to reclaim space
python scripts/cleanup_db.py --vacuum

# Verify database integrity
python scripts/cleanup_db.py --verify

# Run all cleanup operations
python scripts/cleanup_db.py --all
```

**Features**:
- Safe removal of invalid data
- Database optimization (VACUUM)
- Integrity checks
- Orphaned record detection
- Statistics reporting

---

### 3. `signal_dashboard.py` - Signal Monitoring Dashboard

**Purpose**: Interactive dashboard for monitoring trading signals.

**Replaces**:
- `signals_dashboard.py` (root directory)

**Usage Examples**:
```bash
# Show today's signals
python scripts/signal_dashboard.py

# Show signals for specific date
python scripts/signal_dashboard.py --date 2026-02-15

# Watch mode (auto-refresh every 60 seconds)
python scripts/signal_dashboard.py --watch
```

**Features**:
- Real-time signal monitoring
- Execution status tracking
- Signal type breakdown
- Top pending signals highlight
- Watch mode for continuous monitoring

---

## Why These Scripts?

### Before Reorganization
- 7+ scattered check/query scripts with overlapping functionality
- Inconsistent output formats
- Difficult to remember which script does what
- Hard to maintain and update

### After Reorganization
- 3 focused, well-documented scripts
- Consistent output formatting with visual indicators
- Clear separation of concerns:
  - **Query** (db_manager.py)
  - **Maintain** (cleanup_db.py)
  - **Monitor** (signal_dashboard.py)
- Easy to extend and maintain

## Common Workflows

### Daily Monitoring
```bash
# Check today's signals and current positions
python scripts/signal_dashboard.py

# View open positions
python scripts/db_manager.py --positions-open

# Check performance stats
python scripts/db_manager.py --stats
```

### Weekly Maintenance
```bash
# Clean up invalid signals
python scripts/cleanup_db.py --remove-invalid

# Vacuum database
python scripts/cleanup_db.py --vacuum

# Verify integrity
python scripts/cleanup_db.py --verify
```

### Performance Analysis
```bash
# Complete dashboard with all metrics
python scripts/db_manager.py --all

# Analyze specific patterns
python scripts/db_manager.py --stats
```

## Tips

1. **Use --all for complete view**: `python scripts/db_manager.py --all` gives you everything at once

2. **Watch mode for active trading**: `python scripts/signal_dashboard.py --watch` during trading hours

3. **Regular cleanup**: Run `python scripts/cleanup_db.py --all` weekly to maintain database health

4. **Check specific dates**: All scripts support date filtering for historical analysis

## Requirements

All scripts require:
- Python 3.8+
- SQLite3 (built-in with Python)
- Database file at `db/positions.db`

No additional dependencies beyond the main bot requirements.
