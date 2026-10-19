# Backup Directory (`backup/`)

This directory safely archives historical database snapshots and rotated log files. Keeping these files separated from the active working directories prevents accidental overwrites and ensures clean repository organization.

---

## Directory Structure

```text
backup/
├── db/
│   ├── positions-old.db                      # Legacy database snapshot
│   ├── positions_backup_20261005.db         # Pre-upgrade database backup (Oct 5, 2026)
│   └── positions_backup_20261017_150534.db  # Pre-v3.2 upgrade database snapshot (Oct 17, 2026)
└── logs/
    ├── audit.log                            # Rotated historical audit log (pre-Oct 5, 2026)
    └── rajat_alpha_v67.log                  # Rotated historical runtime log (~157 MB)
```

---

## Backup Management Policy

1. **Active Database Isolation**: The live trading engine exclusively touches `db/positions.db`. The files in `backup/db/` are read-only cold archives.
2. **Log Archiving**: Active runtime logs reside in `logs/`. Periodically rotated large logs are compressed and archived here in `backup/logs/`.
3. **Database Restore Procedure**:
   In the unlikely event of data corruption in `db/positions.db`:
   ```bash
   # 1. Stop the trading bot
   # 2. Copy the desired backup to db/
   cp backup/db/positions_backup_20261017_150534.db db/positions.db
   # 3. Verify integrity
   python scripts/db/cleanup_db.py --verify
   # 4. Check position reconciliation with Alpaca
   python scripts/db/check_positions.py
   ```
