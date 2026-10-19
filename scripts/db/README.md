# Database Management Scripts (`scripts/db/`)

This directory contains database management, inspection, maintenance, and reconciliation utilities for the SQLite production database (`db/positions.db`).

---

## Available Scripts

| Script | Purpose | Description |
| :--- | :--- | :--- |
| `check_positions.py` | **Broker vs DB Reconciliation** | Fetches live open positions from Alpaca via API and matches them against `positions.db`. Flags quantity mismatches, ghost records, or unsynced orders. |
| `check_account_status.py` | **Account Health Audit** | Queries Alpaca account balance, buying power, equity, portfolio value, pattern day trader (PDT) status, and account blocking flags. |
| `db_manager.py` | **Database Query CLI** | Interactive command-line utility to query tables, filter open/closed positions, view signals, and display performance statistics. |
| `cleanup_db.py` | **Maintenance & Optimization** | Runs database integrity checks, removes orphan records, and performs `VACUUM` to reclaim disk space. |
| `upgrade_db.py` | **Schema Migration** | Safely upgrades older versions of `positions.db` to the schema required by v3.2. |
| `inspect_open_positions.py` | **Quick Positions Dump** | Minimalist script that dumps current open positions directly from SQLite. |
| `test_live_db_loader.py` | **Database Loader Test** | Verifies that the trading bot initializes and loads active positions without raising exceptions. |

---

## Common Usage Examples

### 1. Reconcile Live Alpaca Account with Database
```bash
python scripts/db/check_positions.py
```
*Expected output*: Lists each position held in Alpaca, verifies whether it exists in `positions.db`, and confirms share count synchronization.

### 2. Check Account Buying Power & Health
```bash
python scripts/db/check_account_status.py
```
*Expected output*: Shows Portfolio Equity, Cash, Buying Power, Day Trade Count, and Status (ACTIVE).

### 3. Inspect Open Positions in SQLite
```bash
python scripts/db/db_manager.py --positions-open
```

### 4. Inspect Recent Signals
```bash
python scripts/db/db_manager.py --signals-today
```

### 5. Verify Database Integrity & Vacuum
```bash
python scripts/db/cleanup_db.py --verify
python scripts/db/cleanup_db.py --vacuum
```

---

## Safety & Best Practices
- These scripts automatically locate `db/positions.db` relative to the repository root, so they can be run from any current working directory.
- Always execute `check_positions.py` before starting the trading bot to ensure your local ledger matches Alpaca broker reality.
