"""
DATABASE MIGRATION SCRIPT - Add signal_history Table
Migrates Dual_Buy database to include signal_history table

Usage:
    python utils/database/migrate_dual_buy_db.py
"""

import sqlite3
from pathlib import Path
import shutil
from datetime import datetime

def backup_database(db_path: Path) -> Path:
    """Create backup of existing database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f"positions_dual_backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path

def migrate_database(db_path: Path):
    """Add signal_history table to existing database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if signal_history table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='signal_history'
    """)
    
    if cursor.fetchone():
        print("✓ signal_history table already exists - no migration needed")
        conn.close()
        return False
    
    # Create signal_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            score REAL,
            pattern TEXT,
            price REAL,
            reason TEXT,
            executed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    return True

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    db_path = project_root / 'Dual_Buy' / 'positions_dual.db'
    
    print("="*80)
    print("DUAL_BUY DATABASE MIGRATION - Add signal_history Table")
    print("="*80)
    
    if not db_path.exists():
        print(f"\n❌ ERROR: Database not found at {db_path}")
        print("   Database will be created with signal_history table on first run")
        print("   No migration needed.")
        return
    
    print(f"\nDatabase: {db_path}")
    
    # Create backup
    print("\n1. Creating backup...")
    backup_path = backup_database(db_path)
    print(f"   ✓ Backup created: {backup_path.name}")
    
    # Run migration
    print("\n2. Running migration...")
    migrated = migrate_database(db_path)
    
    if migrated:
        print("   ✓ signal_history table added successfully")
        
        # Verify
        print("\n3. Verifying migration...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f"   Tables now in database: {', '.join(tables)}")
        
        if 'signal_history' in tables:
            print("\n" + "="*80)
            print("✓ MIGRATION SUCCESSFUL")
            print("="*80)
            print(f"\nBackup location: {backup_path}")
            print("\nYou can now run rajat_alpha_v67_dual.py with signal tracking enabled.")
        else:
            print("\n❌ MIGRATION FAILED - signal_history table not found")
    else:
        print("\n" + "="*80)
        print("NO MIGRATION NEEDED")
        print("="*80)

if __name__ == '__main__':
    main()
