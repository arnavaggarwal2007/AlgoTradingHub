# Database Directory (`db/`)

This directory contains the **active SQLite production database** used by the Rajat Alpha v67 trading bot.

---

## Active Database File

| File | Size | Description |
| :--- | :--- | :--- |
| `positions.db` | ~3.7 MB | The authoritative local ledger for all open and closed swing trade positions, partial exits, signals, and audit events. |

---

## Database Schema Overview

The database contains 5 core tables:

1. **`positions`**:
   - `id`: Primary key
   - `symbol`: Ticker symbol (e.g. `ECPG`, `LAMR`, `CSCO`)
   - `entry_price`: Fill price at entry
   - `initial_qty`: Initial shares bought
   - `remaining_qty`: Current active shares remaining
   - `status`: Position lifecycle (`OPEN`, `CLOSED`)
   - `score`: Entry signal score (e.g. 4.0, 5.0)
   - `pattern`: Technical setup pattern (e.g. `Momentum Pullback`, `EMA21 Demand Bounce`)
   - `stop_loss`: Current active stop price (dynamically updated by trailing stop tiers)
   - `take_profit`: Profit target price
   - `partial_exits_done`: Bitmask / counter of executed profit tiers (1, 2, 3)
   - `entry_date`: Timestamp of position fill
   - `exit_date`: Timestamp of full exit
   - `exit_price`: Final fill price on complete exit
   - `realized_pnl`: Net dollar profit / loss realized

2. **`partial_exits`**:
   - Ledger of each scaled exit (+5%, +10%, +15%) detailing timestamp, quantity exited, exit price, and realized profit.

3. **`signal_history`**:
   - Every candidate evaluated by the scanner with technical score, indicator readings, and execution decision.

4. **`trades`**:
   - Individual order execution records reconciled with Alpaca fills.

5. **`daily_performance`**:
   - Daily end-of-day equity mark-to-market snapshot, win rate, and drawdown metrics.

---

## Maintenance & Inspection Commands

Run these management utilities from the repository root:

```bash
# Check database tables and schemas
python scripts/db/db_manager.py --tables

# View all open positions
python scripts/db/db_manager.py --positions-open

# Reconcile DB positions against live Alpaca broker account
python scripts/db/check_positions.py

# Verify database integrity and vacuum
python scripts/db/cleanup_db.py --verify
```

> **Note on Backups**:
> Historical backups of this database are preserved in `backup/db/`. Never modify or delete `positions.db` while `rajat_alpha_v67_single.py` is actively running.
