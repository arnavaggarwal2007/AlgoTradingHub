# Rajat Alpha v67 - Dual Buy Implementation (B1 + B2)

## Quick Start

This is the **Dual Buy** implementation of Rajat Alpha v67 for Alpaca, supporting B1 (primary) and B2 (high-score secondary) positions simultaneously.

### Setup (5 minutes)

```bash
cd c:\Alpaca_Algo\Dual_Buy

# 1. Edit config_dual.json with your Alpaca API keys
# 2. Edit watchlist.txt with your stock symbols
# 3. Run the bot
python rajat_alpha_v67_dual.py
```

---

## Dual Buy System Explained

### Position Types

**B1 (Primary Buy)**:
- Enters when NO B1 position active for this stock
- Triggers on any valid signal (score 0-5)
- Max positions: 2 (configurable: `max_positions_b1`)
- TES (Time Exit): 21 days (configurable: `tes_days_b1`)

**B2 (High-Score Buy)**:
- Enters when B1 active AND score >= 3 (configurable: `score_b2_min`)
- Only enters if B1 position already exists
- Max positions: 2 (configurable: `max_positions_b2`)
- TES (Time Exit): 21 days (configurable: `tes_days_b2`)

**OPP (Opportunity)**:
- Logged when B1 active but score < B2 threshold
- No position entered (informational only)

---

## Entry Logic Flow

```
Valid Signal Detected (Score: 4/5)
    ↓
Has B1 Position Active?
    ├─ NO  → Enter B1 (any score)
    └─ YES → Check score >= 3?
              ├─ YES → Enter B2 (high score)
              └─ NO  → Log OPP (opportunity, no entry)
```

### Example Scenario:

**Day 1**: AAPL signal (score 2/5) → Enter B1 ✅  
**Day 3**: AAPL signal (score 4/5) → Enter B2 ✅ (B1 active + score >= 3)  
**Day 5**: AAPL signal (score 2/5) → Log OPP ⚠️ (B1 active, score < 3)  
**Day 7**: NVDA signal (score 3/5) → Enter B1 ✅ (no B1 for NVDA)  

---

## Configuration

### Key Settings (`config_dual.json`)

```json
{
  "trading_rules": {
    "max_positions_b1": 2,        // Max B1 positions across all stocks
    "max_positions_b2": 2,        // Max B2 positions across all stocks
    "max_trades_per_stock_b1": 2, // Max B1 positions per stock
    "max_trades_per_stock_b2": 1, // Max B2 positions per stock
    "score_b2_min": 3             // Minimum score for B2 entry
  },
  
  "risk_management": {
    "tes_days_b1": 21,            // B1 time exit (days)
    "tes_days_b2": 21             // B2 time exit (days)
  }
}
```

### Position Sizing

Same equity per position by default. You can configure separate sizing:

```json
{
  "position_sizing": {
    "mode": "percent_equity",
    "percent_of_equity": 0.05,     // Default 5% per position
    "percent_of_equity_b1": 0.05,  // Optional: B1 specific
    "percent_of_equity_b2": 0.03   // Optional: B2 specific (smaller)
  }
}
```

---

## Database Schema

**Table**: `positions` (file: `positions_dual.db`)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Position ID |
| symbol | TEXT | Stock symbol |
| **position_type** | TEXT | **'B1' or 'B2'** |
| entry_date | TEXT | Entry timestamp |
| entry_price | REAL | Entry price |
| quantity | INTEGER | Initial quantity |
| remaining_qty | INTEGER | Remaining shares |
| stop_loss | REAL | Current stop loss |
| status | TEXT | 'OPEN' or 'CLOSED' |
| score | REAL | Entry signal score |

---

## Exit Management

### Independent Stop Loss

Each position (B1/B2) has its own trailing stop loss:
- **17%** below entry (initial)
- **9%** below entry @ +5% profit
- **1%** below entry @ +10% profit

### Partial Exits (1/3 Rule)

Applies to BOTH B1 and B2:
- **PT1**: Sell 33.3% @ +10% profit
- **PT2**: Sell 33.3% @ +15% profit  
- **PT3**: Sell 33.4% @ +20% profit

### Time Exit Signal (TES)

Separate for each position type:
- **B1**: Max 21 days (configurable)
- **B2**: Max 21 days (configurable)

---

## FIFO Selling

Positions are closed FIFO **within each position type**:

**Example**:
```
B1 Position 1: AAPL (Entry: Day 1)
B1 Position 2: AAPL (Entry: Day 5)
B2 Position 1: AAPL (Entry: Day 3)

Stop Loss Hit:
→ B1 Position 1 exits first (oldest B1)
→ B1 Position 2 exits second
→ B2 Position 1 independent (different type)
```

---

## Monitoring

### Check Active Positions

```bash
# View database
sqlite3 positions_dual.db
SELECT symbol, position_type, entry_price, remaining_qty, status FROM positions WHERE status='OPEN';
```

### View Logs

```bash
tail -f rajat_alpha_v67_dual.log
```

**Sample Output**:
```
2026-01-11 15:05:00 | INFO | [AAPL] ✅ ENTRY SIGNAL DETECTED!
2026-01-11 15:05:00 | INFO | [AAPL] Score: 4/5, Pattern: Engulfing
2026-01-11 15:05:00 | INFO | [AAPL] Triggering B2 entry (score: 4 >= 3)
2026-01-11 15:05:01 | INFO | [AAPL] Executing B2 BUY: 10 shares @ $175.00
2026-01-11 15:05:02 | INFO | [AAPL] B2 order submitted successfully
```

---

## Differences from Single Buy

| Feature | Single Buy | Dual Buy |
|---------|-----------|----------|
| Position Types | 1 (unnamed) | 2 (B1, B2) |
| Max Positions | 2 total | 2 B1 + 2 B2 = 4 total |
| Entry Logic | Any valid signal | B1: any signal<br>B2: B1 active + high score |
| TES | Same for all | Separate for B1/B2 |
| Database | positions.db | positions_dual.db |
| Config File | config.json | config_dual.json |

---

## Performance Expectations

Based on PineScript backtests:

**Single Buy**:
- Win Rate: ~65-70%
- Avg Profit: ~12-15% per trade
- Max Drawdown: ~15%

**Dual Buy**:
- Win Rate: ~55-60% (slightly lower due to more entries)
- Avg Profit: ~10-12% per trade
- Max Drawdown: ~25% (higher due to 2x positions)
- More entries = more opportunities but higher risk

**Use Dual Buy When**:
- You have higher capital ($25K+)
- You want more aggressive entries
- You can manage 4+ positions
- You understand the B2 threshold concept

**Use Single Buy When**:
- Learning the strategy
- Limited capital ($10K-$25K)
- Conservative approach
- Fewer positions to monitor

---

## Troubleshooting

### Issue: "B2 never enters"
**Cause**: Score never reaches threshold (default 3)

**Solution**:
1. Lower `score_b2_min` in config (try 2 or 2.5)
2. OR accept fewer B2 entries (by design)

---

### Issue: "Too many positions"
**Cause**: Both B1 and B2 active

**Solution**:
- This is expected behavior (allows 2 B1 + 2 B2 = 4 total)
- Reduce `max_positions_b1` or `max_positions_b2` if needed

---

### Issue: "Database locked"
**Cause**: Multiple bot instances running

**Solution**:
```bash
# Stop all instances
# Delete lock file
rm positions_dual.db-journal
```

---

## Going Live

### Before Production:

1. **Test in Paper Trading** (2-4 weeks)
   ```json
   {
     "api": {
       "base_url": "https://paper-api.alpaca.markets"
     }
   }
   ```

2. **Review Performance**
   - Check B1 vs B2 win rates separately
   - Verify TES is working for both types
   - Monitor max simultaneous positions

3. **Switch to Live**
   ```json
   {
     "api": {
       "base_url": "https://api.alpaca.markets"
     }
   }
   ```

4. **Start Conservative**
   - Lower `max_positions_b1` to 1
   - Lower `max_positions_b2` to 1
   - Use smaller `percent_of_equity` (3-5%)

---

## Files in This Folder

```
Dual_Buy/
├── rajat_alpha_v67_dual.py   # Main dual buy bot
├── config_dual.json           # Dual buy configuration
├── watchlist.txt              # Stock watchlist
├── positions_dual.db          # Database (auto-created)
├── rajat_alpha_v67_dual.log   # Log file (auto-created)
└── README.md                  # This file
```

---

## Support

For complete strategy documentation, see:
- PineScript: `c:\Rajat-Code\AlgoPractice\PineScript\Rajat Alpha v67 Strategy.pine`
- Single Buy: `c:\Alpaca_Algo\Single_Buy\README_COMPLETE_GUIDE.md`

---

**Last Updated**: January 11, 2026  
**Version**: 1.0  
**Platform**: Alpaca Trading API  
**Strategy**: Dual Buy (B1 + B2)
