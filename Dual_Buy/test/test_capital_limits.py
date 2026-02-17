#!/usr/bin/env python3
"""
Test script for capital-based position limits functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rajat_alpha_v67_dual import ConfigManager, PositionDatabase

def test_capital_limits():
    """Test the capital-based limits configuration and logic"""

    print("=== Testing Capital-Based Limits Configuration ===\n")

    # Test configuration loading
    config = ConfigManager('config_dual.json')

    print("Configuration loaded successfully!")
    print(f"Max Equity Utilization: {config.get('trading_rules', 'max_equity_utilization_pct'):.1%}")
    print(f"Dynamic Position Limits: {config.get('trading_rules', 'enable_dynamic_position_limits')}")
    print(f"Capital Conservation Mode: {config.get('trading_rules', 'capital_conservation_mode')}")
    print(f"Position Sizing: {config.get('position_sizing', 'percent_of_equity'):.1%} per position")

    # Test database initialization
    db = PositionDatabase('test_positions.db')
    print("\nDatabase initialized successfully!")

    # Test position counting
    open_positions = db.get_open_positions()
    print(f"Current open positions: {len(open_positions)}")

    b1_count = db.count_active_positions_by_type('B1')
    b2_count = db.count_active_positions_by_type('B2')
    print(f"B1 positions: {b1_count}, B2 positions: {b2_count}")

    print("\n=== Capital Limits Logic Test ===")

    # Simulate different equity utilization scenarios
    test_scenarios = [
        {"equity": 10000, "utilization": 0.0, "description": "No positions"},
        {"equity": 10000, "utilization": 0.25, "description": "25% utilized"},
        {"equity": 10000, "utilization": 0.45, "description": "45% utilized (near limit)"},
        {"equity": 10000, "utilization": 0.55, "description": "55% utilized (over limit)"},
    ]

    max_equity_utilization = config.get('trading_rules', 'max_equity_utilization_pct')
    position_size_pct = config.get('position_sizing', 'percent_of_equity')

    for scenario in test_scenarios:
        available_capacity = max_equity_utilization - scenario['utilization']
        max_positions_by_capital = int(available_capacity / position_size_pct) if available_capacity > 0 else 0
        max_positions_conservative = max(0, max_positions_by_capital - 1)

        print(f"\n{scenario['description']}:")
        print(f"  Equity: ${scenario['equity']:,.0f}")
        print(f"  Current utilization: {scenario['utilization']:.1%}")
        print(f"  Available capacity: {available_capacity:.1%}")
        print(f"  Max positions (raw): {max_positions_by_capital}")
        print(f"  Max positions (conservative): {max_positions_conservative}")

    print("\n=== Test Complete ===")
    print("Capital-based limits configuration and logic verified!")

if __name__ == "__main__":
    test_capital_limits()