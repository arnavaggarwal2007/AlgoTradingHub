"""
Cross-File Method Verification Script
Checks for method definition/call mismatches across all trading scripts
"""

import re
import os
from typing import Dict, List, Set, Tuple

def extract_method_definitions(file_path: str) -> Set[str]:
    """Extract all method definitions from a Python file"""
    methods = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find all method definitions: def method_name(
            pattern = r'def\s+([a-zA-Z_]\w+)\s*\('
            matches = re.findall(pattern, content)
            methods = set(matches)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return methods

def extract_method_calls(file_path: str, class_name: str = None) -> Dict[str, List[int]]:
    """Extract all method calls from a Python file"""
    calls = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                # Find self.method_name( calls
                pattern = r'self\.([a-zA-Z_]\w+)\s*\('
                matches = re.findall(pattern, line)
                for method in matches:
                    if method not in calls:
                        calls[method] = []
                    calls[method].append(i)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return calls

def check_file(file_path: str) -> Tuple[bool, List[str]]:
    """Check if all method calls have corresponding definitions"""
    print(f"\nChecking: {file_path}")
    print("-" * 80)
    
    definitions = extract_method_definitions(file_path)
    calls = extract_method_calls(file_path)
    
    issues = []
    all_ok = True
    
    # Check for undefined methods
    for method, lines in calls.items():
        if method not in definitions:
            # Skip built-in Python methods
            if method.startswith('__'):
                continue
            
            issue = f"❌ Method '{method}' called on line(s) {lines} but NOT defined!"
            print(issue)
            issues.append(issue)
            all_ok = False
    
    # Check for unused definitions (informational only)
    unused = definitions - set(calls.keys())
    # Filter out constructors and special methods
    unused = {m for m in unused if not m.startswith('__')}
    
    if unused and len(unused) < 10:  # Only show if reasonable number
        print(f"ℹ️  Unused methods (may be called externally): {', '.join(sorted(unused))}")
    
    if all_ok:
        print(f"✅ All {len(calls)} method calls verified!")
    
    return all_ok, issues

def main():
    print("="*80)
    print("CROSS-FILE METHOD VERIFICATION")
    print("="*80)
    
    files_to_check = [
        r'c:\Alpaca_Algo\Single_Buy\rajat_alpha_v67.py',
        r'c:\Alpaca_Algo\Dual_Buy\rajat_alpha_v67_dual.py',
        r'c:\Alpaca_Algo\Etrade_Algo\single_Trade\rajat_alpha_v67_etrade.py',
    ]
    
    all_files_ok = True
    all_issues = []
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"\n⚠️  File not found: {file_path}")
            continue
        
        ok, issues = check_file(file_path)
        if not ok:
            all_files_ok = False
            all_issues.extend(issues)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if all_files_ok:
        print("\n🎉 ALL FILES VERIFIED - NO METHOD MISMATCH ISSUES FOUND\n")
        print("All method calls have corresponding definitions.")
        print("No typos like 'check_multitimet_confirmation' detected.")
        return True
    else:
        print(f"\n⚠️  FOUND {len(all_issues)} ISSUE(S):\n")
        for issue in all_issues:
            print(f"  {issue}")
        print("\nPlease fix these issues before deployment.")
        return False

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
