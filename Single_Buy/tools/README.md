# Analysis Tools Directory

This directory contains tools for analyzing stocks, watchlists, and data quality.

## Available Tools

### 1. `watchlist_analyzer.py`

**Purpose**: Comprehensive analysis of all stocks in the watchlist.

**Original Name**: `comprehensive_watchlist_analysis.py`

**Usage**:
```bash
python tools/watchlist_analyzer.py
```

**Features**:
- Analyzes all stocks in `config/watchlist.txt`
- Checks market structure (SMA/EMA alignments)
- Evaluates multi-timeframe confirmations
- Identifies potential entry signals
- Generates summary statistics

**Output**:
- List of stocks meeting entry criteria
- Signal scores for each symbol
- Pattern detections
- Recommendations for trades

---

### 2. `benchmark_analyzer.py`

**Purpose**: Validate data quality and benchmark performance.

**Original Name**: `test_benchmark_data.py`

**Usage**:
```bash
python tools/benchmark_analyzer.py
```

**Features**:
- Tests market data retrieval
- Validates technical indicator calculations
- Checks for data quality issues
- Benchmarks analysis speed
- Verifies API connectivity

**Output**:
- Data quality report
- Performance benchmarks
- Error detection
- Recommendations

---

### 3. `stock_analyzer.py`

**Purpose**: Detailed analysis of individual stocks.

**Original Name**: `stock_analysis_report.py`

**Usage**:
```bash
python tools/stock_analyzer.py
```

**Features**:
- Deep dive into single stock technicals
- Complete indicator breakdown
- Chart pattern analysis
- Entry/exit point identification
- Risk assessment

**Output**:
- Comprehensive stock report
- Technical indicator values
- Buy/sell signals
- Risk metrics

---

## When to Use Each Tool

### Watchlist Analyzer
**Use when**:
- You want to scan all watchlist stocks at once
- Looking for the best opportunities across your universe
- Need to prioritize which stocks to focus on
- Want a complete portfolio view

**Best for**: Daily/weekly portfolio scans

---

### Benchmark Analyzer
**Use when**:
- Testing new API keys or configurations
- Verifying data quality
- Troubleshooting issues
- Measuring system performance
- After major updates

**Best for**: System validation and troubleshooting

---

### Stock Analyzer
**Use when**:
- Researching a specific stock in detail
- Need complete technical picture
- Preparing trade analysis
- Investigating why stock was/wasn't signaled

**Best for**: Individual stock research

---

## Common Workflows

### Pre-Market Analysis
```bash
# 1. Check data quality
python tools/benchmark_analyzer.py

# 2. Scan watchlist for opportunities
python tools/watchlist_analyzer.py

# 3. Deep dive on top picks
python tools/stock_analyzer.py
```

### Troubleshooting

```bash
# If signals seem off
1. Run benchmark_analyzer.py to verify data
2. Run watchlist_analyzer.py to check calculations
3. Run stock_analyzer.py on specific symbol
```

### Weekly Research
```bash
# Sunday evening routine
1. python tools/watchlist_analyzer.py > weekly_scan.txt
2. Review top scores
3. python tools/stock_analyzer.py for detailed research
```

## Configuration

All tools use the main configuration:
- **Watchlist**: `config/watchlist.txt`
- **Exclusions**: `config/exclusionlist.txt`
- **Parameters**: `config/config.json`

No separate configuration needed.

## Requirements

- Python 3.8+
- All main bot dependencies (pandas, pandas-ta, alpaca-py)
- Valid Alpaca API credentials
- Watchlist file

## Tips

1. **Run during market hours** for most accurate data

2. **Use output redirection** to save reports:
   ```bash
   python tools/watchlist_analyzer.py > reports/daily_scan.txt
   ```

3. **Combine with scripts**:
   ```bash
   # Scan watchlist then check database
   python tools/watchlist_analyzer.py
   python scripts/db_manager.py --signals-today
   ```

4. **Benchmark before and after changes** to measure impact

5. **Keep historical scans** to track how opportunities evolve
