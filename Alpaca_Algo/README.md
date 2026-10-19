# Alpaca_Algo - Trading Bot Suite

Automated trading system implementing Rajat Alpha v67 strategy for Alpaca and E*TRADE brokers.

---

## 📁 FOLDER STRUCTURE

```
Alpaca_Algo/
├── Single_Buy/               # Single position entry system
│   ├── rajat_alpha_v67.py   # Main trading bot
│   ├── test_rajat_alpha_v67.py  # Unit tests
│   ├── config.json          # Configuration
│   ├── watchlist.txt        # Stocks to scan
│   ├── exclusionlist.txt    # Stocks to avoid
│   ├── selllist.txt         # Stocks to monitor for exit
│   ├── positions.db         # Trade history database
│   └── docs/                # Documentation
│       ├── README_COMPLETE_GUIDE.md
│       ├── QUICKSTART.md
│       ├── MONITORING_GUIDE.md
│       ├── IMPLEMENTATION_SUMMARY.md
│       └── FIX_SUMMARY_2026-01-12.md
│
├── Dual_Buy/                # Dual position system (B1 + B2)
│   ├── rajat_alpha_v67_dual.py  # Main trading bot
│   ├── config_dual.json     # Configuration
│   ├── watchlist.txt
│   ├── exclusionlist.txt
│   ├── selllist.txt
│   ├── positions_dual.db
│   └── docs/
│       └── README.md
│
├── Etrade_Algo/             # E*TRADE implementations
│   ├── single_Trade/        # Single buy for E*TRADE
│   ├── dual_trade/          # Dual buy for E*TRADE
│   ├── requirements_etrade.txt
│   └── docs/
│       ├── ETRADE_SETUP_GUIDE.md
│       └── ETRADE_QUICKSTART.md
│
├── utils/                   # Utility scripts
│   ├── testing/             # Testing & validation
│   │   ├── test_connection.py
│   │   ├── test_exclusion_comprehensive.py
│   │   ├── test_exclusion_direct.py
│   │   ├── test_exclusion_feature.py
│   │   ├── validate_deployment.py
│   │   └── verify_all_scripts.py
│   │
│   ├── database/            # Database tools
│   │   └── db_explorer.py  # Interactive SQLite explorer
│   │
│   └── analysis/            # Performance analysis
│       └── analyze_performance.py  # Score & pattern analytics
│
├── docs/                    # Project-wide documentation
│   ├── README_ALL_IMPLEMENTATIONS.md
│   ├── QUICK_REFERENCE.md
│   ├── QUICKSTART.md
│   ├── CODE_VALIDATION_REPORT.md
│   ├── PERFORMANCE_TRACKING_GUIDE.md
│   ├── IMPLEMENTATION_SUMMARY_2026-01-15.md
│   ├── COMPREHENSIVE_TEST_REPORT.md
│   ├── CONFIGURATION_ANALYSIS.md
│   ├── CONFIGURATION_FIX_REPORT.md
│   ├── VERIFICATION_REPORT.md
│   ├── SAME_DAY_PROTECTION_SUMMARY.md
│   └── IMPLEMENTATION_STATUS.md
│
├── alpha_bot.py             # Legacy bot (deprecated)
├── config_Google_Generated.json
└── requirements.txt

```

---

## 🚀 QUICK START

### Single Buy System
```powershell
cd Single_Buy
python rajat_alpha_v67.py
```

### Dual Buy System
```powershell
cd Dual_Buy
python rajat_alpha_v67_dual.py
```

---

## 🛠️ UTILITY TOOLS

### Database Explorer
```powershell
# Interactive SQL queries
python utils/database/db_explorer.py

# Single query
python utils/database/db_explorer.py --query "SELECT * FROM positions WHERE status='OPEN'"

# For Dual_Buy
python utils/database/db_explorer.py --dual
```

### Performance Analyzer
```powershell
# Analyze Single_Buy
python utils/analysis/analyze_performance.py

# Analyze Dual_Buy
python utils/analysis/analyze_performance.py --dual

# Analyze only B1 or B2
python utils/analysis/analyze_performance.py --dual --b1
```

### Testing & Validation
```powershell
# Test API connection
python utils/testing/test_connection.py

# Validate deployment
python utils/testing/validate_deployment.py

# Run all unit tests
cd Single_Buy
python test_rajat_alpha_v67.py
```

---

## 📊 STRATEGY OVERVIEW

**Rajat Alpha v67** - Swing trading strategy for US stocks

### Core Logic:
1. **Market Structure** - 50 SMA > 200 SMA, 21 EMA > 50 SMA
2. **Pullback Detection** - Price retraces to key EMAs
3. **Pattern Confirmation** - Engulfing/Piercing/Tweezer patterns
4. **Multi-Timeframe** - Weekly & monthly EMA confirmation
5. **Scoring System** - 0-5 base score + touch bonuses

### Entry Signals:
- **B (Single Buy)** - Primary entry when score >= min threshold
- **B1 (Dual Buy)** - Primary position
- **B2 (Dual Buy)** - High-score secondary (score >= 3)

### Exit Management:
- **Stop Loss** - Dynamic trailing (17% → 9% @ +5% → 1% @ +10%)
- **Partial Exits** - 1/3 at 10%, 15%, 20% or 1/4 at 5%, 10%, 15%, 20%
- **Time Exit (TES)** - Max hold period (default 21 days)

---

## 🔧 CONFIGURATION

### Single_Buy: `config.json`
### Dual_Buy: `config_dual.json`

**Key Settings:**
- `max_trades_per_day` - Daily trade limit (default: 3)
- `max_open_positions` - Max concurrent positions (default: 2)
- `enable_smart_execution` - 15-minute signal monitoring
- `enable_extended_filter` - Reject gap-up stocks >4%
- `min_signal_score` - Minimum score for entry

---

## 📈 NEW FEATURES (Jan 2026)

✅ **Max Trades Per Day** - Limit daily entries  
✅ **Smart 15-Min Execution** - Queue signals, execute top N  
✅ **Extended Stock Filter** - Reject gap-up >4%  
✅ **Signal History Tracking** - Log all signals to database  
✅ **Performance Analytics** - Score & pattern breakdown  

See [docs/PERFORMANCE_TRACKING_GUIDE.md](docs/PERFORMANCE_TRACKING_GUIDE.md)

---

## 📚 DOCUMENTATION

### Quick References
- [Quick Start](docs/QUICK_REFERENCE.md)
- [Performance Tracking](docs/PERFORMANCE_TRACKING_GUIDE.md)
- [Code Validation](docs/CODE_VALIDATION_REPORT.md)

### Implementation Guides
- [Single_Buy Complete Guide](Single_Buy/docs/README_COMPLETE_GUIDE.md)
- [Dual_Buy README](Dual_Buy/docs/README.md)
- [E*TRADE Setup](Etrade_Algo/docs/ETRADE_SETUP_GUIDE.md)

### Technical Details
- [Implementation Summary](docs/IMPLEMENTATION_SUMMARY_2026-01-15.md)
- [Configuration Analysis](docs/CONFIGURATION_ANALYSIS.md)
- [Test Report](docs/COMPREHENSIVE_TEST_REPORT.md)

---

## 🔍 TROUBLESHOOTING

### Common Issues

**"No positions found"**
- Database is empty - wait for first trade or check watchlist

**"API connection failed"**
- Run `python utils/testing/test_connection.py` to diagnose
- Check API keys in config

**"Signal detected but not traded"**
- Check max_trades_per_day limit
- Check max_open_positions
- Review logs for rejection reason

**Database errors**
- Delete old DB files to recreate with new schema:
  ```powershell
  del Single_Buy/positions.db
  del Dual_Buy/positions_dual.db
  ```

---

## 📝 MAINTENANCE

### Update Watchlist
Edit `watchlist.txt` in respective folder (one ticker per line)

### View Logs
- `Single_Buy/rajat_alpha_v67.log`
- `Dual_Buy/rajat_alpha_v67_dual.log`

### Backup Database
```powershell
copy Single_Buy/positions.db Single_Buy/positions_backup_$(Get-Date -Format 'yyyy-MM-dd').db
```

---

## 🏗️ DEVELOPMENT

### Run Tests
```powershell
cd Single_Buy
python test_rajat_alpha_v67.py
```

### Validate Code
```powershell
python -m py_compile Single_Buy/rajat_alpha_v67.py
python -m py_compile Dual_Buy/rajat_alpha_v67_dual.py
```

### Check All Scripts
```powershell
python utils/testing/verify_all_scripts.py
```

---

## 📞 SUPPORT

- **Documentation:** See `docs/` folder
- **Logs:** Check `.log` files in respective folders
- **Database:** Use `utils/database/db_explorer.py`
- **Analysis:** Use `utils/analysis/analyze_performance.py`

---

**Last Updated:** January 16, 2026  
**Version:** Rajat Alpha v67 with Performance Tracking
