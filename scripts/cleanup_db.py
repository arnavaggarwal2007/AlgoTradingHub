"""
Database Cleanup Utility

This script provides database maintenance operations:
- Remove invalid signals (score <= 0)
- Archive old closed positions
- Vacuum database to reclaim space
- Verify database integrity

Usage:
    python scripts/cleanup_db.py --remove-invalid    # Remove invalid signals
    python scripts/cleanup_db.py --vacuum            # Vacuum database
    python scripts/cleanup_db.py --verify            # Verify integrity
    python scripts/cleanup_db.py --all               # Run all cleanup operations
"""

import sqlite3
import argparse
import os
from datetime import datetime, timedelta

DB_PATH = 'db/positions.db'


def check_database_exists() -> bool:
    """Check if database file exists"""
    if not os.path.exists(DB_PATH):
        print(f'❌ Database not found at: {DB_PATH}')
        return False
    return True


def remove_invalid_signals():
    """Remove all signals with score <= 0"""
    print('\n' + '=' * 80)
    print('REMOVING INVALID SIGNALS')
    print('=' * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check current count
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    total_before = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM signal_history WHERE score <= 0')
    invalid_count = cursor.fetchone()[0]
    
    print(f"\n📊 Before cleanup: {total_before} total signals")
    print(f"   Invalid signals to remove: {invalid_count}")
    
    if invalid_count == 0:
        print("\n✅ No invalid signals found - database is clean!")
        conn.close()
        return
    
    # Remove invalid signals
    cursor.execute('DELETE FROM signal_history WHERE score <= 0')
    conn.commit()
    
    # Check after cleanup
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    total_after = cursor.fetchone()[0]
    
    print(f"\n✅ After cleanup: {total_after} valid signals remaining")
    print(f"   Removed: {invalid_count} invalid signals")
    
    # Show remaining signal distribution
    cursor.execute('''
        SELECT 
            ROUND(score) as score_group, 
            COUNT(*) as count 
        FROM signal_history 
        GROUP BY score_group 
        ORDER BY score_group DESC
    ''')
    score_dist = cursor.fetchall()
    
    print("\n📈 Remaining signal distribution:")
    for score, count in score_dist:
        print(f"   Score {score:.0f}: {count} signals")
    
    conn.close()


def archive_old_positions(days: int = 90):
    """Archive closed positions older than specified days"""
    print('\n' + '=' * 80)
    print(f'ARCHIVING POSITIONS OLDER THAN {days} DAYS')
    print('=' * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
    
    cursor.execute('''
        SELECT COUNT(*) FROM positions 
        WHERE status = 'CLOSED' AND exit_date < ?
    ''', (cutoff_date,))
    old_count = cursor.fetchone()[0]
    
    print(f"\n📊 Found {old_count} closed positions older than {cutoff_date}")
    
    if old_count == 0:
        print("✅ No old positions to archive")
        conn.close()
        return
    
    # Note: In production, you might want to move to an archive table
    # For now, we'll just report what could be archived
    print(f"\n💡 To implement archiving, consider:")
    print(f"   1. Create an archive table")
    print(f"   2. Move old records to archive")
    print(f"   3. Keep main table lean for performance")
    
    conn.close()


def vacuum_database():
    """Vacuum database to reclaim space"""
    print('\n' + '=' * 80)
    print('VACUUMING DATABASE')
    print('=' * 80)
    
    # Get file size before
    size_before = os.path.getsize(DB_PATH)
    print(f"\n📊 Database size before: {size_before / 1024:.2f} KB")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('VACUUM')
    conn.close()
    
    # Get file size after
    size_after = os.path.getsize(DB_PATH)
    saved = size_before - size_after
    
    print(f"✅ Database size after: {size_after / 1024:.2f} KB")
    print(f"   Space reclaimed: {saved / 1024:.2f} KB ({(saved/size_before)*100:.1f}%)")


def verify_integrity():
    """Verify database integrity"""
    print('\n' + '=' * 80)
    print('VERIFYING DATABASE INTEGRITY')
    print('=' * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Run integrity check
    cursor.execute('PRAGMA integrity_check')
    result = cursor.fetchone()[0]
    
    if result == 'ok':
        print("\n✅ Database integrity check: PASSED")
    else:
        print(f"\n❌ Database integrity check: FAILED")
        print(f"   Error: {result}")
    
    # Check for orphaned partial_exits
    cursor.execute('''
        SELECT COUNT(*) FROM partial_exits pe
        LEFT JOIN positions p ON pe.position_id = p.id
        WHERE p.id IS NULL
    ''')
    orphaned = cursor.fetchone()[0]
    
    if orphaned > 0:
        print(f"\n⚠️  Found {orphaned} orphaned partial_exit records")
    else:
        print("\n✅ No orphaned records found")
    
    # Check for positions with invalid quantities
    cursor.execute('''
        SELECT COUNT(*) FROM positions
        WHERE remaining_qty > quantity OR remaining_qty < 0
    ''')
    invalid_qty = cursor.fetchone()[0]
    
    if invalid_qty > 0:
        print(f"\n⚠️  Found {invalid_qty} positions with invalid quantities")
    else:
        print("\n✅ All position quantities are valid")
    
    # Show database statistics
    print("\n📊 Database Statistics:")
    
    cursor.execute('SELECT COUNT(*) FROM positions')
    total_positions = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "OPEN"')
    open_positions = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM signal_history')
    total_signals = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM partial_exits')
    total_partial_exits = cursor.fetchone()[0]
    
    print(f"   Total positions: {total_positions} ({open_positions} open)")
    print(f"   Total signals: {total_signals}")
    print(f"   Total partial exits: {total_partial_exits}")
    
    conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Database Cleanup Utility - Maintain trading bot database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--remove-invalid', action='store_true', 
                       help='Remove signals with score <= 0')
    parser.add_argument('--archive', type=int, metavar='DAYS',
                       help='Archive closed positions older than DAYS')
    parser.add_argument('--vacuum', action='store_true',
                       help='Vacuum database to reclaim space')
    parser.add_argument('--verify', action='store_true',
                       help='Verify database integrity')
    parser.add_argument('--all', action='store_true',
                       help='Run all cleanup operations')
    
    args = parser.parse_args()
    
    if not check_database_exists():
        return
    
    # If no args, show help
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    # Execute requested operations
    if args.remove_invalid or args.all:
        remove_invalid_signals()
    
    if args.archive:
        archive_old_positions(args.archive)
    
    if args.vacuum or args.all:
        vacuum_database()
    
    if args.verify or args.all:
        verify_integrity()
    
    print('\n' + '=' * 80)
    print('✅ CLEANUP COMPLETE')
    print('=' * 80 + '\n')


if __name__ == "__main__":
    main()
