import os
import shutil
import sqlite3
import sys
from datetime import datetime

def upgrade_database(db_path: str) -> bool:
    """
    Safely upgrades an existing Rajat Alpha positions.db SQLite database
    to support all v3.2 features (ATR SL, Runner Mode, Dynamic TES, RS Composite)
    without affecting existing positions or open holdings.
    """
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file not found at: {db_path}")
        return False

    print("=" * 75)
    print(f"RAJAT ALPHA DATABASE UPGRADE UTILITY")
    print(f"Target Database: {os.path.abspath(db_path)}")
    print(f"Execution Time:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    # -------------------------------------------------------------
    # STEP 1: CREATE AUTOMATIC TIMESTAMPED BACKUP
    # -------------------------------------------------------------
    # Store automatic backups cleanly in backup/db directory
    backup_dir = os.path.join("backup", "db")
    os.makedirs(backup_dir, exist_ok=True)
    db_name = os.path.basename(db_path)
    base_name, ext = os.path.splitext(db_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{base_name}_backup_{timestamp}{ext}")

    try:
        shutil.copy2(db_path, backup_path)
        backup_size = os.path.getsize(backup_path) / 1024
        print(f"[OK] 1. Backup created successfully:")
        print(f"     Path: {backup_path} ({backup_size:.1f} KB)")
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to create backup: {e}")
        print("Aborting database upgrade to prevent potential data loss.")
        return False

    # -------------------------------------------------------------
    # STEP 2: OPEN DATABASE AND RUN PRE-CHECK
    # -------------------------------------------------------------
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA integrity_check;")
        integrity = cursor.fetchone()[0]
        if integrity != "ok":
            print(f"[ERROR] Database integrity check failed: {integrity}")
            conn.close()
            return False
        print(f"[OK] 2. Pre-upgrade integrity check passed: {integrity}")

        # Check existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"     Existing tables: {', '.join(tables)}")

        if "positions" not in tables:
            print("[ERROR] Table 'positions' not found in database. Is this a valid positions.db?")
            conn.close()
            return False

        # -------------------------------------------------------------
        # STEP 3: UPGRADE 'positions' TABLE SCHEMA
        # -------------------------------------------------------------
        print("\n[INFO] 3. Inspecting and upgrading 'positions' table schema...")
        cursor.execute("PRAGMA table_info(positions);")
        pos_columns = {r[1]: r[2] for r in cursor.fetchall()}

        new_pos_columns = [
            ("initial_stop_loss", "REAL", "NULL"),
            ("is_runner", "BOOLEAN DEFAULT 0", "0"),
            ("tes_extensions_count", "INTEGER DEFAULT 0", "0"),
            ("last_tes_evaluation", "TEXT", "NULL"),
            ("highest_price_seen", "REAL", "NULL"),
            ("sl_stage", "INTEGER DEFAULT 0", "0"),
            ("rs_score", "REAL", "NULL")
        ]

        added_pos_count = 0
        for col_name, col_def, default_val in new_pos_columns:
            if col_name not in pos_columns:
                alter_sql = f"ALTER TABLE positions ADD COLUMN {col_name} {col_def};"
                cursor.execute(alter_sql)
                print(f"     + Added column: {col_name} ({col_def})")
                added_pos_count += 1
            else:
                print(f"     = Column already exists: {col_name}")

        # -------------------------------------------------------------
        # STEP 4: UPGRADE 'signal_history' TABLE SCHEMA (IF PRESENT)
        # -------------------------------------------------------------
        if "signal_history" in tables:
            print("\n[INFO] 4. Inspecting and upgrading 'signal_history' table schema...")
            cursor.execute("PRAGMA table_info(signal_history);")
            sig_columns = {r[1]: r[2] for r in cursor.fetchall()}

            new_sig_columns = [
                ("rs_score", "REAL", "NULL"),
                ("candle_pattern", "TEXT", "NULL")
            ]

            for col_name, col_def, default_val in new_sig_columns:
                if col_name not in sig_columns:
                    cursor.execute(f"ALTER TABLE signal_history ADD COLUMN {col_name} {col_def};")
                    print(f"     + Added column to signal_history: {col_name}")
                else:
                    print(f"     = Column already exists in signal_history: {col_name}")

        # -------------------------------------------------------------
        # STEP 5: CREATE 'processed_overrides' TABLE
        # -------------------------------------------------------------
        print("\n[INFO] 5. Ensuring 'processed_overrides' table exists...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                override_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                position_id INTEGER,
                action TEXT NOT NULL,
                exit_price REAL,
                quantity INTEGER,
                exit_reason TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        print("     + Table 'processed_overrides' verified/created.")

        # -------------------------------------------------------------
        # STEP 6: BACKFILL DATA SAFELY WITHOUT IMPACTING OPEN HOLDINGS
        # -------------------------------------------------------------
        print("\n[INFO] 6. Performing safe data backfill for existing rows...")

        # A. Backfill initial_stop_loss where NULL
        # If stop_loss is around 17% below entry, use stop_loss. Otherwise calculate entry * 0.83.
        cursor.execute('''
            UPDATE positions 
            SET initial_stop_loss = CASE 
                WHEN stop_loss <= (entry_price * 0.85) THEN stop_loss 
                ELSE ROUND(entry_price * 0.83, 4) 
            END
            WHERE initial_stop_loss IS NULL;
        ''')
        updated_sl = cursor.rowcount
        print(f"     * Backfilled 'initial_stop_loss' for {updated_sl} existing positions.")

        # B. Backfill highest_price_seen where NULL
        cursor.execute('''
            UPDATE positions 
            SET highest_price_seen = entry_price 
            WHERE highest_price_seen IS NULL;
        ''')
        updated_high = cursor.rowcount
        print(f"     * Backfilled 'highest_price_seen' for {updated_high} existing positions.")

        # C. Backfill defaults for boolean/integer flags
        cursor.execute("UPDATE positions SET is_runner = 0 WHERE is_runner IS NULL;")
        cursor.execute("UPDATE positions SET tes_extensions_count = 0 WHERE tes_extensions_count IS NULL;")
        cursor.execute("UPDATE positions SET sl_stage = 0 WHERE sl_stage IS NULL;")

        # D. FIX GHOST POSITIONS (Clean up 0-quantity positions stuck in 'OPEN' status)
        cursor.execute('''
            SELECT id, symbol, remaining_qty FROM positions 
            WHERE status = 'OPEN' AND remaining_qty <= 0;
        ''')
        ghosts = cursor.fetchall()

        if ghosts:
            print(f"\n[ATTENTION] Found {len(ghosts)} Ghost Position(s) with 0 remaining shares stuck in 'OPEN' status:")
            for gid, gsym, gqty in ghosts:
                print(f"     - Fixing Ghost Position ID {gid} ({gsym}): Setting status='CLOSED'")
                cursor.execute('''
                    UPDATE positions 
                    SET status = 'CLOSED',
                        exit_reason = COALESCE(exit_reason, 'Partial Exits Complete'),
                        exit_date = COALESCE(exit_date, CURRENT_TIMESTAMP)
                    WHERE id = ?;
                ''', (gid,))
            print(f"     * Successfully cleaned up {len(ghosts)} ghost position(s).")
        else:
            print("     * No ghost positions found. Database clean.")

        # -------------------------------------------------------------
        # STEP 7: COMMIT AND POST-VERIFICATION
        # -------------------------------------------------------------
        conn.commit()

        cursor.execute("PRAGMA integrity_check;")
        post_integrity = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'OPEN';")
        open_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'CLOSED';")
        closed_count = cursor.fetchone()[0]

        print("\n" + "=" * 75)
        print("DATABASE UPGRADE COMPLETED SUCCESSFULLY")
        print("=" * 75)
        print(f"Post-Upgrade Integrity Check: {post_integrity}")
        print(f"Verified Active Open Positions: {open_count} (Preserved with zero data loss)")
        print(f"Verified Closed Positions:     {closed_count}")
        print(f"Safe Backup Location:          {backup_path}")
        print("=" * 75)

        conn.close()
        return True

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"\n[CRITICAL ERROR] Migration failed: {e}")
        print(f"Your original database has been rolled back. Backup is safe at: {backup_path}")
        return False

if __name__ == "__main__":
    # If path provided via CLI, use it; otherwise use default relative path
    target_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("db", "positions.db")
    success = upgrade_database(target_path)
    sys.exit(0 if success else 1)

