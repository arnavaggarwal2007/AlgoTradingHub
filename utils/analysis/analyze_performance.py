"""
PERFORMANCE ANALYZER - Score & Pattern Analysis
Analyzes trading performance grouped by entry score and candlestick pattern

Usage:
    python analyze_performance.py                    # Analyze Single_Buy
    python analyze_performance.py --dual             # Analyze Dual_Buy
    python analyze_performance.py --dual --b1        # Analyze only B1 positions
    python analyze_performance.py --dual --b2        # Analyze only B2 positions
"""

import argparse
import sys
from pathlib import Path

# Add project folders to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent  # utils/analysis/ -> utils/ -> Alpaca_Algo/

sys.path.insert(0, str(project_root / 'Single_Buy'))
sys.path.insert(0, str(project_root / 'Dual_Buy'))

def analyze_single_buy():
    """Analyze Single_Buy performance"""
    from rajat_alpha_v67 import PositionDatabase
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    db_path = project_root / 'Single_Buy' / 'positions.db'
    
    db = PositionDatabase(str(db_path))
    
    print("\n" + "="*80)
    print("SINGLE BUY PERFORMANCE ANALYSIS")
    print("="*80)
    
    # Performance by Score
    print("\nPERFORMANCE BY SCORE")
    print("-" * 80)
    score_data = db.get_performance_by_score()
    
    if score_data:
        print(f"{'Score':<8} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12} {'Avg Win%':<12} {'Avg Loss%':<12} {'Max%':<10} {'Min%':<10}")
        print("-" * 80)
        for row in score_data:
            print(f"{row['score']:<8.1f} {row['trades']:<8} {row['win_rate']:<10.1f} "
                  f"{row['avg_pl']:<12.2f} {row['avg_win'] or 0:<12.2f} {row['avg_loss'] or 0:<12.2f} "
                  f"{row['max_pl']:<10.2f} {row['min_pl']:<10.2f}")
    else:
        print("No closed positions found")
    
    # Performance by Pattern
    print("\n\nPERFORMANCE BY PATTERN")
    print("-" * 80)
    pattern_data = db.get_performance_by_pattern()
    
    if pattern_data:
        print(f"{'Pattern':<15} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12} {'Avg Win%':<12} {'Avg Loss%':<12}")
        print("-" * 80)
        for row in pattern_data:
            print(f"{row['pattern']:<15} {row['trades']:<8} {row['win_rate']:<10.1f} "
                  f"{row['avg_pl']:<12.2f} {row['avg_win'] or 0:<12.2f} {row['avg_loss'] or 0:<12.2f}")
    else:
        print("No closed positions found")
    
    # Score × Pattern Matrix
    print("\n\nSCORE x PATTERN MATRIX")
    print("-" * 80)
    matrix_data = db.get_performance_by_score_and_pattern()
    
    if matrix_data:
        print(f"{'Score':<8} {'Pattern':<15} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12}")
        print("-" * 80)
        for row in matrix_data:
            print(f"{row['score']:<8.1f} {row['pattern']:<15} {row['trades']:<8} "
                  f"{row['win_rate']:<10.1f} {row['avg_pl']:<12.2f}")
    else:
        print("No closed positions found")
    
    print("\n" + "="*80 + "\n")

def analyze_dual_buy(position_filter=None):
    """Analyze Dual_Buy performance"""
    from rajat_alpha_v67_dual import PositionDatabase
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    db_path = project_root / 'Dual_Buy' / 'positions_dual.db'
    
    db = PositionDatabase(str(db_path))
    
    filter_label = f" ({position_filter} ONLY)" if position_filter else ""
    
    print("\n" + "="*80)
    print(f"DUAL BUY PERFORMANCE ANALYSIS{filter_label}")
    print("="*80)
    
    # Performance by Position Type (B1 vs B2)
    if not position_filter:
        print("\nB1 vs B2 COMPARISON")
        print("-" * 80)
        type_data = db.get_performance_by_position_type()
        
        if type_data:
            print(f"{'Type':<8} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12} {'Avg Win%':<12} {'Avg Loss%':<12}")
            print("-" * 80)
            for row in type_data:
                print(f"{row['position_type']:<8} {row['trades']:<8} {row['win_rate']:<10.1f} "
                      f"{row['avg_pl']:<12.2f} {row['avg_win'] or 0:<12.2f} {row['avg_loss'] or 0:<12.2f}")
        else:
            print("No closed positions found")
    
    # Performance by Score
    print("\n\nPERFORMANCE BY SCORE")
    print("-" * 80)
    score_data = db.get_performance_by_score(position_filter)
    
    if score_data:
        print(f"{'Score':<8} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12} {'Avg Win%':<12} {'Avg Loss%':<12} {'Max%':<10} {'Min%':<10}")
        print("-" * 80)
        for row in score_data:
            print(f"{row['score']:<8.1f} {row['trades']:<8} {row['win_rate']:<10.1f} "
                  f"{row['avg_pl']:<12.2f} {row['avg_win'] or 0:<12.2f} {row['avg_loss'] or 0:<12.2f} "
                  f"{row['max_pl']:<10.2f} {row['min_pl']:<10.2f}")
    else:
        print("No closed positions found")
    
    # Performance by Pattern
    print("\n\nPERFORMANCE BY PATTERN")
    print("-" * 80)
    pattern_data = db.get_performance_by_pattern(position_filter)
    
    if pattern_data:
        print(f"{'Pattern':<15} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12} {'Avg Win%':<12} {'Avg Loss%':<12}")
        print("-" * 80)
        for row in pattern_data:
            print(f"{row['pattern']:<15} {row['trades']:<8} {row['win_rate']:<10.1f} "
                  f"{row['avg_pl']:<12.2f} {row['avg_win'] or 0:<12.2f} {row['avg_loss'] or 0:<12.2f}")
    else:
        print("No closed positions found")
    
    # Score × Pattern Matrix
    print("\n\nSCORE x PATTERN MATRIX")
    print("-" * 80)
    matrix_data = db.get_performance_by_score_and_pattern(position_filter)
    
    if matrix_data:
        print(f"{'Score':<8} {'Pattern':<15} {'Trades':<8} {'Win%':<10} {'Avg P/L%':<12}")
        print("-" * 80)
        for row in matrix_data:
            print(f"{row['score']:<8.1f} {row['pattern']:<15} {row['trades']:<8} "
                  f"{row['win_rate']:<10.1f} {row['avg_pl']:<12.2f}")
    else:
        print("No closed positions found")
    
    print("\n" + "="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description='Analyze trading performance by score and pattern',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_performance.py              # Analyze Single_Buy
  python analyze_performance.py --dual       # Analyze Dual_Buy (all positions)
  python analyze_performance.py --dual --b1  # Analyze only B1 positions
  python analyze_performance.py --dual --b2  # Analyze only B2 positions
        """
    )
    
    parser.add_argument('--dual', action='store_true', 
                       help='Analyze Dual_Buy instead of Single_Buy')
    parser.add_argument('--b1', action='store_true', 
                       help='Filter by B1 positions only (Dual_Buy only)')
    parser.add_argument('--b2', action='store_true', 
                       help='Filter by B2 positions only (Dual_Buy only)')
    
    args = parser.parse_args()
    
    if args.dual:
        position_filter = None
        if args.b1:
            position_filter = 'B1'
        elif args.b2:
            position_filter = 'B2'
        
        analyze_dual_buy(position_filter)
    else:
        if args.b1 or args.b2:
            print("Error: --b1 and --b2 flags only work with --dual")
            sys.exit(1)
        
        analyze_single_buy()

if __name__ == '__main__':
    main()
