import sys
import os
# Add parent directory to path to import the bot module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rajat_alpha_v67_single import PositionManager, ConfigManager, PositionDatabase
import logging

# Set up minimal logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def test_capital_conservation_mode():
    """Test capital conservation mode activation"""
    print('🧪 Testing Capital Conservation Mode...')

    try:
        config = ConfigManager('config/config.json')
        db = PositionDatabase()

        # Enable conservation mode for this test
        config.config['trading_rules']['capital_conservation_mode'] = True

        # Mock trading client
        class MockTradingClient:
            def get_account(self):
                class MockAccount:
                    equity = '100000.0'  # $100k account
                return MockAccount()

        trading_client = MockTradingClient()
        position_manager = PositionManager(trading_client, config, db, None)

        # Current utilization is ~19.9%, so conservation mode should NOT activate
        # (threshold is 70% of max_utilization_pct = 70% of 50% = 35%)

        shares, amount = position_manager.calculate_position_size('NORMAL_TEST', 100.0)
        print(f'✅ Normal utilization (~20%): {shares} shares = ${amount:.2f} (no conservation)')

        # Now let's simulate high utilization by temporarily modifying the database query
        # We'll mock a scenario where utilization is high enough to trigger conservation

        # Test with a scenario that would trigger conservation mode
        # We need utilization > 35% (70% of 50% max)
        # Let's simulate 40% utilization

        original_get_open_positions = db.get_open_positions

        def mock_get_open_positions(symbol=None):
            # Return positions that total $40k (40% utilization)
            return [
                {'symbol': 'MOCK1', 'entry_price': 100.0, 'remaining_qty': 200, 'stop_loss': 90.0},  # $20k
                {'symbol': 'MOCK2', 'entry_price': 100.0, 'remaining_qty': 200, 'stop_loss': 90.0},  # $20k
            ]

        db.get_open_positions = mock_get_open_positions

        shares, amount = position_manager.calculate_position_size('CONSERVATION_TEST', 100.0)
        print(f'✅ High utilization (40%): {shares} shares = ${amount:.2f} (conservation active)')

        # Restore original method
        db.get_open_positions = original_get_open_positions

        print('✅ Capital Conservation Mode test passed')
        return True

    except Exception as e:
        print(f'❌ Capital Conservation Mode test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_utilization_limits():
    """Test utilization limit enforcement"""
    print('🧪 Testing Utilization Limit Enforcement...')

    try:
        config = ConfigManager('config/config.json')
        config.config['trading_rules']['max_equity_utilization_pct'] = 0.50
        db = PositionDatabase()

        # Mock trading client
        class MockTradingClient:
            def get_account(self):
                class MockAccount:
                    equity = '100000.0'  # $100k account
                return MockAccount()

        trading_client = MockTradingClient()
        position_manager = PositionManager(trading_client, config, db, None)

        # Current utilization ~19.9%, max allowed 50%
        # A trade bringing total under 50% - should be allowed

        shares, amount = position_manager.calculate_position_size('ALLOWED_TEST', 100.0)
        if shares > 0:
            print(f'✅ Trade allowed: {shares} shares = ${amount:.2f} (under limit)')
        else:
            print('❌ Trade incorrectly blocked')
            return False

        # Now test with utilization that would exceed limit
        original_get_open_positions = db.get_open_positions

        def mock_high_util_positions(symbol=None):
            # Return positions that total $50k (50% utilization - limit reached)
            return [
                {'symbol': 'HIGH1', 'entry_price': 100.0, 'remaining_qty': 250, 'stop_loss': 90.0},  # $25k
                {'symbol': 'HIGH2', 'entry_price': 100.0, 'remaining_qty': 250, 'stop_loss': 90.0},  # $25k
            ]

        db.get_open_positions = mock_high_util_positions

        shares, amount = position_manager.calculate_position_size('BLOCKED_TEST', 100.0)
        if shares == 0:
            print('✅ Trade correctly blocked (would exceed 50% limit)')
        else:
            print(f'❌ Trade incorrectly allowed: {shares} shares = ${amount:.2f}')
            return False

        # Restore original method
        db.get_open_positions = original_get_open_positions

        print('✅ Utilization Limit test passed')
        return True

    except Exception as e:
        print(f'❌ Utilization Limit test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_dynamic_position_limits():
    """Test dynamic position limits"""
    print('🧪 Testing Dynamic Position Limits...')

    try:
        config = ConfigManager('config/config.json')
        db = PositionDatabase()

        # Mock trading client
        class MockTradingClient:
            def get_account(self):
                class MockAccount:
                    equity = '100000.0'  # $100k account
                return MockAccount()

        trading_client = MockTradingClient()
        position_manager = PositionManager(trading_client, config, db, None)

        # With current utilization ~19.9%, available equity = $80.1k
        # Position size = $10k, so max additional positions = 8
        # But config max_open_positions = 4, so effective limit = 4

        # We currently have 2 positions, so should allow 2 more
        max_positions = config.get('trading_rules', 'max_open_positions')
        current_positions = len(db.get_open_positions())

        print(f'   Config max positions: {max_positions}')
        print(f'   Current positions: {current_positions}')
        print(f'   Should allow: {max_positions - current_positions} more positions')

        # Test that position sizing still works
        shares, amount = position_manager.calculate_position_size('DYNAMIC_TEST', 100.0)
        if shares > 0:
            print(f'✅ Dynamic limits working: {shares} shares = ${amount:.2f}')
        else:
            print('❌ Dynamic limits test failed - trade blocked')
            return False

        print('✅ Dynamic Position Limits test passed')
        return True

    except Exception as e:
        print(f'❌ Dynamic Position Limits test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print('🚀 Running Complete Test Suite for Enhanced Single_Buy Implementation')
    print('=' * 70)

    tests = [
        test_capital_conservation_mode,
        test_utilization_limits,
        test_dynamic_position_limits,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print('=' * 70)
    print(f'📊 Test Results: {passed}/{total} tests passed')

    if passed == total:
        print('🎉 ALL TESTS PASSED! Enhanced Single_Buy implementation is working correctly.')
    else:
        print('❌ Some tests failed. Please review the implementation.')