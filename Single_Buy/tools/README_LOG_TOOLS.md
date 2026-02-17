# Log Analyzer Tools - User Guide

Comprehensive log analysis tools for Rajat Alpha V67 trading bot. Analyze massive log files, identify errors, track trading activity, and generate actionable insights.

---

## Overview

The Log Analyzer Tools consist of two components:

1. **CLI Tool** (`log_analyzer.py`) - Fast command-line analysis and reporting
2. **Web Dashboard** (`log_dashboard.py`) - Interactive visual interface

Both tools can handle **very large log files** (170+ MB tested successfully) and provide:
- Error categorization and analysis
- Warning detection and grouping  
- Trading activity tracking
- Daily statistics breakdown
- CSV export for detailed review

---

## Quick Start

### Method 1: Command-Line Analysis

```bash
# Analyze last 7 days
python tools/log_analyzer.py --days 7

# Analyze specific date range with daily breakdown
python tools/log_analyzer.py --start 2026-02-02 --end 2026-02-16 --daily

# Export to CSV
python tools/log_analyzer.py --start 2026-02-02 --end 2026-02-16 --csv reports/analysis.csv
```

### Method 2: Web Dashboard

```bash
# Start the web dashboard
python tools/log_dashboard.py
```

Then open your browser to: **http://localhost:5001**

Features:
- 📅 Interactive date range selector
- 📊 Real-time statistics cards
- 📋 Daily breakdown table
- 🗂️ Categorized errors and warnings
- 📥 One-click CSV export

---

## CLI Tool Usage

### Basic Commands

```bash
# Show help
python tools/log_analyzer.py --help

# Analyze last N days
python tools/log_analyzer.py --days 7

# Analyze specific date range
python tools/log_analyzer.py --start 2026-02-01 --end 2026-02-16

# Show daily statistics table
python tools/log_analyzer.py --start 2026-02-01 --end 2026-02-16 --daily

# Export to CSV
python tools/log_analyzer.py --start 2026-02-01 --end 2026-02-16 --csv output.csv
```

### Advanced Options

```bash
# Use custom log file path
python tools/log_analyzer.py --log path/to/custom.log --days 7

# Limit processing (for testing large files)
python tools/log_analyzer.py --days 7 --max-lines 100000

# Combine multiple options
python tools/log_analyzer.py \
  --start 2026-02-01 \
  --end 2026-02-16 \
  --daily \
  --csv reports/feb_analysis.csv
```

### Output Format

The CLI tool generates:

1. **Summary Report** (stdout)
   - Total log entries processed
   - Error summary with categories
   - Warning summary with categories
   - Trading activity metrics
   - Signal analysis statistics
   - Recent critical issues (last 10 errors)

2. **Daily Statistics Table** (with `--daily` flag)
   - Errors per day
   - Warnings per day
   - Trades per day
   - Signals per day
   - Top error types

3. **CSV Export** (with `--csv` flag)
   - Timestamp, Level, Category, Message, Function, Line
   - All errors and warnings included
   - Importable into Excel, Google Sheets, etc.

---

## Web Dashboard Features

### Starting the Dashboard

```bash
cd C:\Alpaca_Algo\Single_Buy
python tools/log_dashboard.py
```

Output:
```
================================================================================
📊 LOG ANALYZER DASHBOARD
================================================================================

Starting web dashboard on http://localhost:5001

Features:
  ✅ Interactive date range selection
  ✅ Real-time log analysis
  ✅ Error and warning categorization
  ✅ Daily statistics table
  ✅ CSV export functionality

Press Ctrl+C to stop the server
================================================================================
```

### Dashboard Interface

The web dashboard provides:

#### 1. Date Range Controls
- Start date picker
- End date picker
- Analyze button (triggers real-time analysis)
- Export CSV button

#### 2. Statistics Cards
- **Total Entries**: All log entries in date range
- **Errors**: Total error count with red gradient
- **Warnings**: Total warning count with yellow gradient
- **Trades**: Total trading activity with blue gradient
- **Signals Generated**: Valid signals created
- **Buy Orders**: New positions opened
- **Full Exits**: Positions completely closed
- **Partial Exits**: Partial profit-taking events

#### 3. Daily Statistics Table
- Date column
- Errors, Warnings, Trades, Signals per day
- Sortable and easy to scan for patterns

#### 4. Error Categories Section
- Grouped by error type (API, Database, Trading, etc.)
- Shows count for each category
- Displays top 5 recent errors per category
- "... and X more" indicator for large categories

#### 5. Warning Categories Section  
- Grouped by warning type (Capital, Position, Signal, etc.)
- Shows count for each category
- Displays top 5 recent warnings per category
- Timestamps included for all entries

### Customization

You can customize the dashboard port:

```python
# Edit log_dashboard.py, line 437
app.run(debug=True, host='0.0.0.0', port=5001)  # Change 5001 to your preferred port
```

---

## Understanding the Analysis

### Error Categories

The analyzer automatically categorizes errors:

| Category | Triggers | Example |
|----------|----------|---------|
| **API Errors** | "API", "HTTP", "Request" | `API rate limit exceeded` |
| **Database Errors** | "Database", "SQL", "db" | `Database connection failed` |
| **Trading Errors** | "Market", "Trading", "Order" | `Order execution failed: insufficient buying power` |
| **Data Errors** | "Data", "fetch", "download" | `Failed to fetch market data` |
| **Other Errors** | Everything else | Miscellaneous errors |

### Warning Categories

| Category | Triggers | Example |
|----------|----------|---------|
| **Capital Limit Warnings** | "Capital", "limit", "exceeded" | `Capital utilization limit reached` |
| **Position Warnings** | "Position", "overselling" | `No execution slots available` |
| **Signal Warnings** | "Signal", "validation" | `Signal EXPIRED during monitoring` |
| **Market Status Warnings** | "Market", "closed" | `Market closed. Sleeping...` |
| **Other Warnings** | Everything else | Miscellaneous warnings |

### Trading Activity Tracking

The tools track these trading events:

- **Buy Orders**: Any message containing "BUY" or "POSITION OPENED"
- **Full Exits**: Messages with "FULL EXIT"
- **Partial Exits**: Messages with "Partial Exit"
- **Signals**: "SIGNAL GENERATED" or "✅ VALID SIGNAL"

---

## Use Cases

### 1. Daily Health Check

```bash
# Check yesterday's logs
python tools/log_analyzer.py --days 1

# Look for:
# - Error count (should be low)
# - Warning patterns
# - Buy/Exit ratio (should be balanced)
```

### 2. Investigate Issues

```bash
# When you notice problems, analyze the period
python tools/log_analyzer.py --start 2026-02-11 --end 2026-02-13 --daily --csv issue_analysis.csv

# Open CSV in Excel to:
# - Sort by error type
# - Find patterns in timestamps
# - Identify affected stocks
```

### 3. Weekly Performance Review

```bash
# Every Monday, review the previous week
python tools/log_analyzer.py --days 7 --daily --csv weekly_report.csv

# Look for trends:
# - Are errors increasing?
# - What's the signal acceptance rate?
# - Is trading activity consistent?
```

### 4. Incident Response

When your bot has issues:

1. **Start Web Dashboard**
   ```bash
   python tools/log_dashboard.py
   ```

2. **Select Incident Period**
   - Use date pickers to isolate the problem timeframe

3. **Review Categories**
   - Check which error categories have the highest counts
   - Look for patterns in recent errors

4. **Export for Detailed Analysis**
   - Click "Export CSV" button
   - Open in Excel/Google Sheets for deeper investigation

---

## Performance Notes

### Large Log Files

The tools are optimized for large files:

- **Tested:** 170 MB log file (682,099 lines)
- **Processing Time:** ~2 minutes for 400,000+ entries
- **Memory Usage:** Efficient streaming and filtering

### Optimization Tips

1. **Use Specific Date Ranges**
   ```bash
   # Good: Analyze just the problem period
   --start 2026-02-11 --end 2026-02-13
   
   # Avoid: Analyzing entire history unnecessarily
   --start 2026-01-01 --end 2026-12-31
   ```

2. **Test with Limited Lines First**
   ```bash
   # Process first 100k lines to verify it works
   python tools/log_analyzer.py --days 7 --max-lines 100000
   ```

3. **Run Dashboard on Separate Machine**
   - If your trading bot is resource-constrained
   - Copy log file to analysis machine
   - Run dashboard there to avoid impacting bot performance

---

## Troubleshooting

### Issue: "File not found" Error

```bash
Error: [Errno 2] No such file or directory: 'logs/rajat_alpha_v67.log'
```

**Solution:**
```bash
# Specify full path
python tools/log_analyzer.py --log C:\Alpaca_Algo\Single_Buy\logs\rajat_alpha_v67.log --days 7
```

### Issue: Unicode Encoding Errors on Windows

```
UnicodeEncodeError: 'charmap' codec can't encode character
```

**Solution:**
Set UTF-8 encoding:
```powershell
$env:PYTHONIOENCODING="utf-8"
python tools/log_analyzer.py --days 7
```

### Issue: Dashboard Not Loading

```
This site can't be reached - localhost refused to connect
```

**Solutions:**
1. Check if Flask started successfully (no errors in terminal)
2. Verify port 5001 is not in use by another application
3. Try changing the port in `log_dashboard.py`
4. Check firewall settings

### Issue: Analysis Takes Too Long

**Solutions:**
1. Use more specific date range
2. Use `--max-lines` to test first
3. Close other applications to free memory
4. Consider running overnight for multi-month analysis

---

## CSV Export Details

### CSV Format

The exported CSV contains:

| Column | Description | Example |
|--------|-------------|---------|
| **Timestamp** | When the log entry occurred | `2026-02-13 20:56:28` |
| **Level** | Severity (ERROR/WARNING) | `ERROR` |
| **Category** | Auto-categorized type | `Trading Errors` |
| **Message** | Full log message | `[TKO] Full exit failed: {...}` |
| **Function** | Function where log originated | `execute_full_exit` |
| **Line** | Line number in source code | `1494` |

### Working with CSV in Excel

1. **Open CSV**
   ```
   File > Open > Select CSV file
   ```

2. **Apply Filters**
   - Select header row
   - Data > Filter
   - Click dropdown arrows to filter by category, level, etc.

3. **Pivot Table Analysis**
   - Insert > PivotTable
   - Rows: Date (from Timestamp)
   - Columns: Category
   - Values: Count of Message

4. **Chart Creation**
   - Select data range
   - Insert > Chart
   - Create time-series chart of errors/warnings

---

## API Reference (For Developers)

### LogAnalyzer Class

```python
from tools.log_analyzer import LogAnalyzer

# Initialize
analyzer = LogAnalyzer(log_file='logs/rajat_alpha_v67.log')

# Analyze date range
analyzer.analyze_date_range('2026-02-01', '2026-02-16')

# Access data
print(f"Errors: {len(analyzer.errors)}")
print(f"Warnings: {len(analyzer.warnings)}")
print(f"Trades: {len(analyzer.trades)}")

# Generate summary
summary = analyzer.generate_summary()
print(summary)

# Categorize errors
error_categories = analyzer.categorize_errors()
for category, errors in error_categories.items():
    print(f"{category}: {len(errors)} errors")

# Generate daily stats
daily_stats = analyzer.generate_daily_stats()
for day, stats in daily_stats.items():
    print(f"{day}: {stats['errors']} errors, {stats['trades']} trades")

# Export CSV
analyzer.generate_csv_report('output.csv')
```

### Flask Dashboard Endpoints

```python
# GET / - Main dashboard page
http://localhost:5001/

# POST /analyze - Analyze logs (returns JSON)
POST http://localhost:5001/analyze
Body: {"start_date": "2026-02-01", "end_date": "2026-02-16"}

# GET /export - Download CSV
GET http://localhost:5001/export?start_date=2026-02-01&end_date=2026-02-16
```

---

## Best Practices

### 1. Regular Monitoring

```bash
# Create a daily cron job / scheduled task
0 9 * * * cd /path/to/Single_Buy && python tools/log_analyzer.py --days 1 >> daily_reports/$(date +\%Y-\%m-\%d).txt
```

### 2. Alert Thresholds

Monitor these metrics and alert if exceeded:

- **Errors > 50/day** - Investigate immediately
- **Warnings > 100/day** - Review for patterns
- **Buy/Exit Ratio > 5:1** - Capital may be getting locked up
- **Same stock in errors 10+ times** - Position may be stuck

### 3. Weekly Reviews

Every week, run:
```bash
python tools/log_analyzer.py --days 7 --daily --csv weekly_reports/week_$(date +\%Y-\%W).csv
```

Review the CSV to identify:
- Trending issues
- Performance degradation
- Successful strategies

### 4. Before Deploying Changes

After code changes:
```bash
# Baseline before change
python tools/log_analyzer.py --days 1 --csv before_change.csv

# Deploy change and run for 1 day

# Compare after change
python tools/log_analyzer.py --days 1 --csv after_change.csv

# Diff the error counts to verify improvement
```

---

## Future Enhancements

Potential improvements for future versions:

- [ ] Real-time log tailing (watch mode)
- [ ] Email/SMS alerts for critical errors
- [ ] Integration with monitoring services (Datadog, New Relic)
- [ ] Machine learning anomaly detection
- [ ] Performance metrics (trade P&L tracking)
- [ ] Position-level drill-down analysis
- [ ] Comparative analysis (week-over-week)
- [ ] Export to PDF reports
- [ ] Slack/Discord webhooks for alerts

---

## Support

For issues or questions:

1. Check this README first
2. Review the Troubleshooting section
3. Examine example outputs in `reports/` directory
4. Check the main project documentation

---

## Files Included

```
tools/
├── log_analyzer.py       # CLI tool for log analysis
├── log_dashboard.py      # Web dashboard for visual analysis
└── README_LOG_TOOLS.md   # This file

reports/
└── LOG_ANALYSIS_FEB2-16_2026.md  # Example analysis report
```

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════╗
║                    LOG ANALYZER QUICK REFERENCE                    ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  DAILY CHECK:                                                      ║
║  python tools/log_analyzer.py --days 1                             ║
║                                                                    ║
║  WEEKLY REVIEW:                                                    ║
║  python tools/log_analyzer.py --days 7 --daily                     ║
║                                                                    ║
║  INVESTIGATE ISSUE:                                                ║
║  python tools/log_analyzer.py --start YYYY-MM-DD --end YYYY-MM-DD  ║
║                                                                    ║
║  EXPORT CSV:                                                       ║
║  python tools/log_analyzer.py --days 7 --csv report.csv            ║
║                                                                    ║
║  WEB DASHBOARD:                                                    ║
║  python tools/log_dashboard.py                                     ║
║  Open: http://localhost:5001                                       ║
║                                                                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

**Last Updated:** February 16, 2026  
**Version:** 1.0  
**Tested On:** Windows, Python 3.13, 170MB log file
