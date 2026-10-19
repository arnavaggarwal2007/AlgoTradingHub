#!/usr/bin/env python3
"""
Alpaca Account Status Checker
Diagnoses account issues and restrictions
"""

import sys
import os
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from rajat_alpha_v67_single import ConfigManager
from alpaca.trading.client import TradingClient


def check_account_status():
    """Check Alpaca account status and diagnose issues"""
    
    print("=" * 80)
    print("🔍 ALPACA ACCOUNT STATUS CHECKER")
    print("=" * 80)
    print()
    
    # Load configuration
    config_manager = ConfigManager('config/config.json')
    
    api_key = config_manager.get('api', 'key_id')
    secret_key = config_manager.get('api', 'secret_key')
    base_url = config_manager.get('api', 'base_url')
    paper = 'paper' in base_url.lower() if base_url else True
    
    if not api_key or not secret_key:
        print("❌ Error: API credentials not found in config/config.json")
        return
    
    # Initialize trading client
    trading_client = TradingClient(api_key, secret_key, paper=paper)
    
    try:
        # Get account information
        account = trading_client.get_account()
        
        print("📊 ACCOUNT INFORMATION")
        print("-" * 80)
        print(f"Account Number:        {account.account_number}")
        print(f"Account Status:        {account.status}")
        print(f"Trading Mode:          {'📝 PAPER TRADING' if paper else '💰 LIVE TRADING'}")
        print(f"Currency:              {account.currency}")
        print()
        
        print("💵 BUYING POWER & EQUITY")
        print("-" * 80)
        print(f"Buying Power:          ${float(account.buying_power):,.2f}")
        print(f"Cash:                  ${float(account.cash):,.2f}")
        print(f"Portfolio Value:       ${float(account.portfolio_value):,.2f}")
        print(f"Equity:                ${float(account.equity):,.2f}")
        print(f"Long Market Value:     ${float(account.long_market_value):,.2f}")
        print(f"Short Market Value:    ${float(account.short_market_value):,.2f}")
        print()
        
        print("🚨 RESTRICTIONS & LIMITATIONS")
        print("-" * 80)
        print(f"Pattern Day Trader:    {account.pattern_day_trader}")
        print(f"Trading Blocked:       {account.trading_blocked}")
        print(f"Transfers Blocked:     {account.transfers_blocked}")
        print(f"Account Blocked:       {account.account_blocked}")
        print(f"Trade Suspended:       {account.trade_suspended_by_user}")
        print(f"Shorting Enabled:      {account.shorting_enabled}")
        print(f"Multiplier:            {account.multiplier}")
        print()
        
        print("📈 TRADING ACTIVITY")
        print("-" * 80)
        print(f"Daytrade Count:        {account.daytrade_count}")
        print(f"Last Equity:           ${float(account.last_equity):,.2f}")
        print(f"Initial Margin:        ${float(account.initial_margin):,.2f}")
        print(f"Maintenance Margin:    ${float(account.maintenance_margin):,.2f}")
        print()
        
        # Analyze issues
        print("=" * 80)
        print("🔬 ISSUE ANALYSIS")
        print("=" * 80)
        print()
        
        issues_found = []
        warnings_found = []
        
        # Check 1: Buying Power
        buying_power = float(account.buying_power)
        if buying_power <= 0:
            issues_found.append(f"🚨 CRITICAL: Buying power is ${buying_power:,.2f}")
            print("❌ Issue #1: Zero Buying Power")
            print(f"   Current buying power: ${buying_power:,.2f}")
            if paper:
                print("   This is UNUSUAL for paper trading - paper accounts should have large buying power")
                print("   Possible causes:")
                print("     - Paper trading account may need to be reset")
                print("     - Too many open positions using all allocated paper money")
                print("     - Alpaca paper trading bug")
            else:
                print("   Possible causes:")
                print("     - All capital deployed in positions")
                print("     - Margin call or account restriction")
                print("     - Pattern Day Trader (PDT) violation")
            print()
        elif buying_power < 1000:
            warnings_found.append(f"⚠️  Low buying power: ${buying_power:,.2f}")
            print(f"⚠️  Warning: Low buying power (${buying_power:,.2f})")
            print()
        else:
            print(f"✅ Buying power looks good: ${buying_power:,.2f}")
            print()
        
        # Check 2: Pattern Day Trader
        if account.pattern_day_trader:
            if paper:
                warnings_found.append("⚠️  PDT flag set in paper account (unusual)")
                print("⚠️  Warning: Pattern Day Trader flag is TRUE")
                print("   This is unusual for paper trading accounts")
                print("   PDT restrictions shouldn't apply to paper trading")
                print()
            else:
                issues_found.append("🚨 Pattern Day Trader restrictions active")
                print("❌ Issue #2: Pattern Day Trader (PDT) Restrictions")
                print("   Your account is flagged as a Pattern Day Trader")
                print("   Requirements:")
                print("     - Must maintain $25,000 minimum equity")
                print(f"     - Current equity: ${float(account.equity):,.2f}")
                if float(account.equity) < 25000:
                    print("     - ⚠️  BELOW PDT MINIMUM - Trading may be restricted!")
                print()
        else:
            print("✅ No Pattern Day Trader restrictions")
            print()
        
        # Check 3: Account Blocks
        if account.trading_blocked:
            issues_found.append("🚨 CRITICAL: Trading is BLOCKED")
            print("❌ Issue #3: Trading Blocked")
            print("   Trading is currently blocked on this account")
            print("   Contact Alpaca support to resolve")
            print()
        elif account.account_blocked:
            issues_found.append("🚨 CRITICAL: Account is BLOCKED")
            print("❌ Issue #4: Account Blocked")
            print("   Account is blocked - no trading allowed")
            print("   Contact Alpaca support immediately")
            print()
        else:
            print("✅ No trading blocks detected")
            print()
        
        # Check 4: Daytrade count
        dt_cnt = account.daytrade_count if account.daytrade_count is not None else 0
        if dt_cnt >= 3 and not account.pattern_day_trader:
            warnings_found.append(f"⚠️  High daytrade count: {dt_cnt}/3")
            print(f"⚠️  Warning: Close to PDT limit ({dt_cnt}/3 day trades)")
            print("   One more day trade in 5 days will trigger PDT restrictions")
            print()
        
        # Check 5: Paper Trading with Low Equity
        if paper and float(account.equity) < 100000:
            warnings_found.append(f"⚠️  Paper account equity seems low: ${float(account.equity):,.2f}")
            print(f"⚠️  Warning: Low equity for paper account (${float(account.equity):,.2f})")
            print("   Paper accounts typically start with $100,000")
            print("   Consider resetting your paper account if needed")
            print()
        
        # Summary
        print("=" * 80)
        print("📋 SUMMARY")
        print("=" * 80)
        print()
        
        if not issues_found and not warnings_found:
            print("✅ ✅ ✅  NO ISSUES DETECTED - Account looks healthy!")
            print()
            if buying_power <= 0:
                print("However, buying power is $0, which explains the 'insufficient buying power' errors.")
                print()
                if paper:
                    print("DIAGNOSIS: This is likely an Alpaca paper trading issue or")
                    print("           all your paper trading capital is deployed in open positions.")
                    print()
                    print("SOLUTION:")
                    print("  1. Check open positions (run check_positions.py)")
                    print("  2. Close some positions to free up capital")
                    print("  3. Or reset your paper trading account via Alpaca dashboard")
        else:
            print(f"Found {len(issues_found)} critical issues and {len(warnings_found)} warnings:")
            print()
            for issue in issues_found:
                print(f"  {issue}")
            for warning in warnings_found:
                print(f"  {warning}")
            print()
        
        # Specific diagnosis for the log issues
        print("=" * 80)
        print("🎯 DIAGNOSIS: Your Log Issues")
        print("=" * 80)
        print()
        
        if buying_power <= 0:
            print("Issue #1: 'Insufficient Buying Power' Errors (1,415 errors)")
            print("├─ Root Cause: Buying power is $0")
            if paper:
                print("├─ Why: Paper trading account capital is fully deployed")
                print("├─ Impact: Cannot sell positions (Alpaca bug - selling shouldn't need buying power)")
                print("└─ Solution: See recommendations below")
            else:
                print("├─ Why: Real account capital is fully deployed or restricted")
                print("└─ Solution: See recommendations below")
            print()
        
        print("Issue #2: Time Exit Signal Loop (1,483 warnings)")
        print("├─ Root Cause: Script bug - no exit retry limit")
        print("├─ Why: Exit fails → position stays open → TES triggers again → loop")
        print("└─ Solution: Already fixed in code (added safeguards)")
        print()
        
        print("Issue #3: Position Saturation (15/15 positions)")
        print("├─ Root Cause: Exits failing + continuous buying")
        print("├─ Why: Exit failure rate is 52% due to buying power issue")
        print("└─ Solution: Fix buying power issue first")
        print()
        
        # Recommendations
        print("=" * 80)
        print("💡 RECOMMENDATIONS")
        print("=" * 80)
        print()
        
        if paper:
            print("Since you're in PAPER TRADING, this is NOT a financial emergency!")
            print()
            print("Option 1: Reset Paper Trading Account")
            print("  1. Go to https://app.alpaca.markets/paper/dashboard/overview")
            print("  2. Reset paper trading account (restores to $100,000)")
            print("  3. Restart your bot")
            print()
            print("Option 2: Close Stuck Positions")
            print("  1. Run: python scripts/check_positions.py")
            print("  2. Manually close LLY, WELL, TKO positions via Alpaca dashboard")
            print("  3. This frees up capital for normal operation")
            print()
            print("Option 3: Wait for Positions to Exit Naturally")
            print("  1. Stop the bot temporarily")
            print("  2. Manually close all positions via Alpaca dashboard")
            print("  3. Restart bot with clean slate")
            print()
        else:
            print("Since you're in LIVE TRADING:")
            print()
            print("1. Review all open positions immediately")
            print("2. Consider closing positions manually if stuck")
            print("3. Contact Alpaca support if issues persist")
            print("4. Ensure you have sufficient equity for PDT requirements")
            print()
        
        print("=" * 80)
        print("✅ Analysis Complete")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error getting account information: {e}")
        print()
        print("Possible causes:")
        print("  - Invalid API credentials")
        print("  - Network connection issue")
        print("  - Alpaca API is down")
        return


if __name__ == '__main__':
    check_account_status()
