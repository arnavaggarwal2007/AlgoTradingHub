"""
SQLite Database Explorer - Interactive Query Tool

Quick access to positions database with common queries

Usage:
    python db_explorer.py                    # Explore Single_Buy database
    python db_explorer.py --dual             # Explore Dual_Buy database
    python db_explorer.py --query "SELECT * FROM positions LIMIT 5"
"""

import sqlite3
import argparse
from pathlib import Path

class DatabaseExplorer:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def execute_query(self, query):
        """Execute query and return formatted results"""
        cursor = self.conn.cursor()
        cursor.execute(query)
        
        rows = cursor.fetchall()
        if not rows:
            return "No results found"
        
        # Get column names
        columns = rows[0].keys()
        
        # Calculate column widths
        widths = {col: len(col) for col in columns}
        for row in rows:
            for col in columns:
                value_str = str(row[col]) if row[col] is not None else 'NULL'
                widths[col] = max(widths[col], len(value_str))
        
        # Build output
        output = []
        
        # Header
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        output.append(header)
        output.append("-" * len(header))
        
        # Rows
        for row in rows:
            row_str = " | ".join(
                str(row[col]).ljust(widths[col]) if row[col] is not None else 'NULL'.ljust(widths[col])
                for col in columns
            )
            output.append(row_str)
        
        return "\n".join(output)
    
    def show_schema(self):
        """Show table schemas"""
        tables_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        cursor = self.conn.cursor()
        cursor.execute(tables_query)
        tables = [row[0] for row in cursor.fetchall()]
        
        output = ["\nDATABASE SCHEMA\n" + "="*80 + "\n"]
        
        for table in tables:
            output.append(f"\nTable: {table}")
            output.append("-" * 40)
            
            schema_query = f"PRAGMA table_info({table})"
            cursor.execute(schema_query)
            columns = cursor.fetchall()
            
            for col in columns:
                col_id, name, col_type, not_null, default, pk = col
                pk_marker = " [PRIMARY KEY]" if pk else ""
                null_marker = " NOT NULL" if not_null else ""
                default_marker = f" DEFAULT {default}" if default else ""
                output.append(f"  - {name} ({col_type}){pk_marker}{null_marker}{default_marker}")
        
        return "\n".join(output)
    
    def show_common_queries(self):
        """Display common query examples"""
        return """
COMMON QUERIES

1. All Open Positions:
   SELECT symbol, entry_date, entry_price, stop_loss, score, pattern 
   FROM positions WHERE status = 'OPEN'

2. All Closed Positions with P/L:
   SELECT symbol, entry_date, exit_date, profit_loss_pct, exit_reason, score, pattern 
   FROM positions WHERE status = 'CLOSED' ORDER BY profit_loss_pct DESC

3. Today's Signals:
   SELECT symbol, score, pattern, price, executed, reason 
   FROM signal_history WHERE signal_date = date('now')

4. Performance Summary:
   SELECT 
     COUNT(*) as total_trades,
     SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) as wins,
     ROUND(AVG(profit_loss_pct), 2) as avg_pl_pct,
     ROUND(MAX(profit_loss_pct), 2) as best_trade,
     ROUND(MIN(profit_loss_pct), 2) as worst_trade
   FROM positions WHERE status = 'CLOSED'

5. Pattern Performance:
   SELECT pattern, COUNT(*) as trades, 
          ROUND(AVG(profit_loss_pct), 2) as avg_pl
   FROM positions WHERE status = 'CLOSED'
   GROUP BY pattern ORDER BY avg_pl DESC

6. Partial Exits History:
   SELECT p.symbol, p.entry_price, pe.exit_date, pe.quantity, 
          pe.exit_price, pe.profit_target, pe.profit_pct
   FROM partial_exits pe
   JOIN positions p ON pe.position_id = p.id
   ORDER BY pe.exit_date DESC

7. Count Trades Today:
   SELECT COUNT(*) as trades_today 
   FROM positions WHERE date(entry_date) = date('now')

8. Stocks by Win Rate:
   SELECT symbol, COUNT(*) as trades,
          SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
          ROUND(AVG(profit_loss_pct), 2) as avg_pl
   FROM positions WHERE status = 'CLOSED'
   GROUP BY symbol HAVING COUNT(*) >= 3
   ORDER BY win_rate DESC

Use: python db_explorer.py --query "YOUR_QUERY_HERE"
        """
    
    def interactive_mode(self):
        """Start interactive query mode"""
        print("\n" + "="*80)
        print("SQLite Database Explorer - Interactive Mode")
        print("="*80)
        print(f"Database: {self.db_path}")
        print("\nCommands:")
        print("  .schema    - Show database schema")
        print("  .queries   - Show common query examples")
        print("  .quit      - Exit")
        print("  Or enter any SQL query")
        print("="*80 + "\n")
        
        while True:
            try:
                query = input("SQL> ").strip()
                
                if not query:
                    continue
                
                if query.lower() == '.quit':
                    print("Goodbye!")
                    break
                
                if query.lower() == '.schema':
                    print(self.show_schema())
                    continue
                
                if query.lower() == '.queries':
                    print(self.show_common_queries())
                    continue
                
                # Execute SQL query
                result = self.execute_query(query)
                print(f"\n{result}\n")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}\n")
    
    def close(self):
        self.conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='SQLite Database Explorer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--dual', action='store_true', 
                       help='Explore Dual_Buy database')
    parser.add_argument('--query', '-q', type=str,
                       help='Execute a single query and exit')
    parser.add_argument('--schema', action='store_true',
                       help='Show database schema and exit')
    parser.add_argument('--examples', action='store_true',
                       help='Show common query examples and exit')
    
    args = parser.parse_args()
    
    # Determine database path (relative to project root)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # utils/database/ -> utils/ -> Alpaca_Algo/
    
    if args.dual:
        db_path = project_root / 'Dual_Buy' / 'positions_dual.db'
    else:
        db_path = project_root / 'Single_Buy' / 'positions.db'
    
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}")
        print("The database will be created on first trade.")
        return
    
    explorer = DatabaseExplorer(db_path)
    
    try:
        if args.schema:
            print(explorer.show_schema())
        elif args.examples:
            print(explorer.show_common_queries())
        elif args.query:
            result = explorer.execute_query(args.query)
            print(f"\n{result}\n")
        else:
            explorer.interactive_mode()
    finally:
        explorer.close()

if __name__ == '__main__':
    main()
