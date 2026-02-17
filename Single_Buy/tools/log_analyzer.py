#!/usr/bin/env python3
"""
Log Analyzer - Comprehensive Trading Bot Log Analysis Tool
Analyzes rajat_alpha_v67.log to extract insights, errors, and trading activities
"""

import json
import re
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LogAnalyzer:
    """Analyzes trading bot logs and generates comprehensive reports"""
    
    def __init__(self, log_file: str = "logs/rajat_alpha_v67.log"):
        self.log_file = log_file
        self.entries = []
        self.errors = []
        self.warnings = []
        self.trades = []
        self.signals = []
        self.positions = []
        self.stats = defaultdict(int)
        
    def parse_log_line(self, line: str) -> Optional[Dict]:
        """Parse a JSON log line"""
        try:
            # Try to parse as JSON
            if line.strip().startswith('{'):
                return json.loads(line)
            # Try to extract JSON from line
            match = re.search(r'\{.*\}', line)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        
        # Fallback: parse old-style log format
        # Format: 2026-02-16 21:05:57 | INFO | Message
        match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+) \| (.+)$', line.strip())
        if match:
            return {
                'timestamp': match.group(1),
                'level': match.group(2),
                'message': match.group(3)
            }
        
        return None
    
    def parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Parse timestamp from various formats"""
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with microseconds
            '%Y-%m-%dT%H:%M:%SZ',      # ISO format
            '%Y-%m-%d %H:%M:%S',       # Simple format
            '%Y-%m-%d %H:%M:%S.%f',    # Simple with microseconds
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except (ValueError, TypeError):
                continue
        return None
    
    def analyze_date_range(self, start_date: str, end_date: str, max_lines: int = None):
        """Analyze logs within a date range"""
        print(f"📊 Analyzing logs from {start_date} to {end_date}...")
        print(f"📁 Log file: {self.log_file}")
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        
        lines_processed = 0
        lines_matched = 0
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                lines_processed += 1
                if max_lines and lines_processed > max_lines:
                    break
                
                # Quick date filter before parsing
                if not re.search(f'{start_date[:7]}', line):  # Match year-month
                    continue
                
                entry = self.parse_log_line(line)
                if not entry:
                    continue
                
                # Parse timestamp
                ts = self.parse_timestamp(entry.get('timestamp', ''))
                if not ts or ts < start_dt or ts >= end_dt:
                    continue
                
                lines_matched += 1
                entry['parsed_timestamp'] = ts
                self.entries.append(entry)
                
                # Categorize entries
                level = entry.get('level', 'INFO')
                message = entry.get('message', '')
                
                if level == 'ERROR':
                    self.errors.append(entry)
                elif level == 'WARNING':
                    self.warnings.append(entry)
                
                # Extract trading activities
                if 'BUY' in message or 'POSITION OPENED' in message:
                    self.trades.append(entry)
                    self.stats['total_buys'] += 1
                elif 'SELL' in message or 'EXIT' in message:
                    self.trades.append(entry)
                    if 'FULL EXIT' in message:
                        self.stats['full_exits'] += 1
                    elif 'Partial Exit' in message:
                        self.stats['partial_exits'] += 1
                
                # Extract signals
                if 'SIGNAL GENERATED' in message or '✅ VALID SIGNAL' in message:
                    self.signals.append(entry)
                    self.stats['signals_generated'] += 1
                elif '❌' in message and 'Signal failed' in message:
                    self.stats['signals_rejected'] += 1
                
                # Position tracking
                if 'Position Summary' in message or 'Active Positions' in message:
                    self.positions.append(entry)
                
                # Progress indicator
                if lines_processed % 100000 == 0:
                    print(f"  Processed {lines_processed:,} lines...", end='\r')
        
        print(f"\n✅ Processed {lines_processed:,} lines, matched {lines_matched:,} entries")
        return lines_matched
    
    def categorize_errors(self) -> Dict[str, List[Dict]]:
        """Categorize errors by type"""
        categories = defaultdict(list)
        
        for error in self.errors:
            msg = error.get('message', '')
            
            if 'API' in msg or 'HTTP' in msg or 'Request' in msg:
                categories['API Errors'].append(error)
            elif 'Database' in msg or 'SQL' in msg or 'db' in msg:
                categories['Database Errors'].append(error)
            elif 'Market' in msg or 'Trading' in msg or 'Order' in msg:
                categories['Trading Errors'].append(error)
            elif 'Data' in msg or 'fetch' in msg or 'download' in msg:
                categories['Data Errors'].append(error)
            else:
                categories['Other Errors'].append(error)
        
        return dict(categories)
    
    def categorize_warnings(self) -> Dict[str, List[Dict]]:
        """Categorize warnings by type"""
        categories = defaultdict(list)
        
        for warning in self.warnings:
            msg = warning.get('message', '')
            
            if 'Capital' in msg or 'limit' in msg or 'exceeded' in msg:
                categories['Capital Limit Warnings'].append(warning)
            elif 'Position' in msg or 'overselling' in msg:
                categories['Position Warnings'].append(warning)
            elif 'Signal' in msg or 'validation' in msg:
                categories['Signal Warnings'].append(warning)
            elif 'Market' in msg or 'closed' in msg:
                categories['Market Status Warnings'].append(warning)
            else:
                categories['Other Warnings'].append(warning)
        
        return dict(categories)
    
    def generate_summary(self) -> str:
        """Generate human-readable summary report"""
        report = []
        report.append("=" * 80)
        report.append("📊 RAJAT ALPHA V67 - LOG ANALYSIS SUMMARY")
        report.append("=" * 80)
        report.append("")
        
        # Date range
        if self.entries:
            first_dt = self.entries[0]['parsed_timestamp']
            last_dt = self.entries[-1]['parsed_timestamp']
            report.append(f"📅 Date Range: {first_dt.strftime('%Y-%m-%d %H:%M')} to {last_dt.strftime('%Y-%m-%d %H:%M')}")
            report.append(f"⏱️  Duration: {(last_dt - first_dt).days} days, {(last_dt - first_dt).seconds // 3600} hours")
        
        report.append(f"📝 Total Log Entries: {len(self.entries):,}")
        report.append("")
        
        # Error Summary
        report.append("=" * 80)
        report.append("🚨 ERROR SUMMARY")
        report.append("=" * 80)
        report.append(f"Total Errors: {len(self.errors):,}")
        report.append("")
        
        error_categories = self.categorize_errors()
        for category, errors in sorted(error_categories.items(), key=lambda x: len(x[1]), reverse=True):
            report.append(f"  {category}: {len(errors):,}")
            # Show top 3 unique error messages
            error_msgs = Counter([e.get('message', '')[:100] for e in errors])
            for msg, count in error_msgs.most_common(3):
                report.append(f"    - [{count}x] {msg}...")
        report.append("")
        
        # Warning Summary
        report.append("=" * 80)
        report.append("⚠️  WARNING SUMMARY")
        report.append("=" * 80)
        report.append(f"Total Warnings: {len(self.warnings):,}")
        report.append("")
        
        warning_categories = self.categorize_warnings()
        for category, warnings in sorted(warning_categories.items(), key=lambda x: len(x[1]), reverse=True):
            report.append(f"  {category}: {len(warnings):,}")
            # Show top 3 unique warning messages
            warning_msgs = Counter([w.get('message', '')[:100] for w in warnings])
            for msg, count in warning_msgs.most_common(3):
                report.append(f"    - [{count}x] {msg}...")
        report.append("")
        
        # Trading Activity
        report.append("=" * 80)
        report.append("💰 TRADING ACTIVITY")
        report.append("=" * 80)
        report.append(f"Total Buy Orders: {self.stats.get('total_buys', 0):,}")
        report.append(f"Full Exits: {self.stats.get('full_exits', 0):,}")
        report.append(f"Partial Exits: {self.stats.get('partial_exits', 0):,}")
        report.append("")
        
        # Signal Analysis
        report.append("=" * 80)
        report.append("📡 SIGNAL ANALYSIS")
        report.append("=" * 80)
        report.append(f"Signals Generated: {self.stats.get('signals_generated', 0):,}")
        report.append(f"Signals Rejected: {self.stats.get('signals_rejected', 0):,}")
        
        if self.stats.get('signals_generated', 0) + self.stats.get('signals_rejected', 0) > 0:
            total_signals = self.stats['signals_generated'] + self.stats['signals_rejected']
            acceptance_rate = (self.stats['signals_generated'] / total_signals) * 100
            report.append(f"Signal Acceptance Rate: {acceptance_rate:.1f}%")
        report.append("")
        
        # Recent Critical Issues
        report.append("=" * 80)
        report.append("🔴 RECENT CRITICAL ISSUES (Last 10 Errors)")
        report.append("=" * 80)
        for error in self.errors[-10:]:
            ts = error.get('parsed_timestamp', '')
            msg = error.get('message', '')[:150]
            report.append(f"[{ts.strftime('%Y-%m-%d %H:%M:%S') if ts else 'Unknown'}] {msg}")
        report.append("")
        
        report.append("=" * 80)
        report.append("📋 END OF SUMMARY")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def generate_csv_report(self, output_file: str):
        """Generate CSV report of all errors and warnings"""
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Level', 'Category', 'Message', 'Function', 'Line'])
            
            # Errors
            error_categories = self.categorize_errors()
            for category, errors in error_categories.items():
                for error in errors:
                    ts = error.get('parsed_timestamp', '')
                    writer.writerow([
                        ts.strftime('%Y-%m-%d %H:%M:%S') if ts else '',
                        'ERROR',
                        category,
                        error.get('message', ''),
                        error.get('function', ''),
                        error.get('line', '')
                    ])
            
            # Warnings
            warning_categories = self.categorize_warnings()
            for category, warnings in warning_categories.items():
                for warning in warnings:
                    ts = warning.get('parsed_timestamp', '')
                    writer.writerow([
                        ts.strftime('%Y-%m-%d %H:%M:%S') if ts else '',
                        'WARNING',
                        category,
                        warning.get('message', ''),
                        warning.get('function', ''),
                        warning.get('line', '')
                    ])
        
        print(f"✅ CSV report saved to: {output_file}")
    
    def generate_daily_stats(self) -> Dict[str, Dict]:
        """Generate statistics grouped by day"""
        daily = defaultdict(lambda: {
            'errors': 0,
            'warnings': 0,
            'trades': 0,
            'signals': 0,
            'error_types': Counter(),
            'warning_types': Counter()
        })
        
        for entry in self.entries:
            ts = entry.get('parsed_timestamp')
            if not ts:
                continue
            
            day = ts.strftime('%Y-%m-%d')
            level = entry.get('level', '')
            
            if level == 'ERROR':
                daily[day]['errors'] += 1
                msg = entry.get('message', '')
                if 'API' in msg:
                    daily[day]['error_types']['API'] += 1
                elif 'Database' in msg:
                    daily[day]['error_types']['Database'] += 1
                elif 'Trading' in msg:
                    daily[day]['error_types']['Trading'] += 1
            elif level == 'WARNING':
                daily[day]['warnings'] += 1
            
            msg = entry.get('message', '')
            if 'BUY' in msg or 'SELL' in msg or 'EXIT' in msg:
                daily[day]['trades'] += 1
            if 'SIGNAL GENERATED' in msg:
                daily[day]['signals'] += 1
        
        return dict(daily)
    
    def print_daily_table(self):
        """Print daily statistics as a table"""
        daily_stats = self.generate_daily_stats()
        
        print("\n" + "=" * 100)
        print("📅 DAILY STATISTICS TABLE")
        print("=" * 100)
        print(f"{'Date':<12} {'Errors':<8} {'Warnings':<10} {'Trades':<8} {'Signals':<10} {'Top Error Type':<25}")
        print("-" * 100)
        
        for day in sorted(daily_stats.keys()):
            stats = daily_stats[day]
            top_error = stats['error_types'].most_common(1)
            top_error_str = f"{top_error[0][0]} ({top_error[0][1]})" if top_error else "N/A"
            
            print(f"{day:<12} {stats['errors']:<8} {stats['warnings']:<10} {stats['trades']:<8} {stats['signals']:<10} {top_error_str:<25}")
        
        print("=" * 100)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Rajat Alpha V67 trading bot logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze last 7 days
  python log_analyzer.py --days 7
  
  # Analyze specific date range
  python log_analyzer.py --start 2026-02-02 --end 2026-02-16
  
  # Generate CSV report
  python log_analyzer.py --start 2026-02-02 --end 2026-02-16 --csv errors.csv
  
  # Show daily statistics table
  python log_analyzer.py --start 2026-02-02 --end 2026-02-16 --daily
        """
    )
    
    parser.add_argument('--log', default='logs/rajat_alpha_v67.log',
                        help='Path to log file (default: logs/rajat_alpha_v67.log)')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, help='Analyze last N days')
    parser.add_argument('--csv', help='Export to CSV file')
    parser.add_argument('--daily', action='store_true', help='Show daily statistics table')
    parser.add_argument('--max-lines', type=int, help='Maximum lines to process (for testing)')
    
    args = parser.parse_args()
    
    # Calculate date range
    if args.days:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    elif args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        # Default: last 7 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Analyze logs
    analyzer = LogAnalyzer(args.log)
    analyzer.analyze_date_range(start_date, end_date, max_lines=args.max_lines)
    
    # Generate summary
    summary = analyzer.generate_summary()
    print("\n" + summary)
    
    # Show daily table if requested
    if args.daily:
        analyzer.print_daily_table()
    
    # Export to CSV if requested
    if args.csv:
        analyzer.generate_csv_report(args.csv)
    
    print(f"\n✅ Analysis complete!")
    print(f"   Errors: {len(analyzer.errors):,}")
    print(f"   Warnings: {len(analyzer.warnings):,}")
    print(f"   Trades: {len(analyzer.trades):,}")
    print(f"   Signals: {len(analyzer.signals):,}")


if __name__ == '__main__':
    main()
