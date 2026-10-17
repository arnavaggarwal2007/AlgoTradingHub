# Tests Directory

This directory contains all test files for the trading bot.

## Available Tests

### 1. `test_bot.py`

**Purpose**: Unit tests for the main trading bot components.

**Original Name**: `test_rajat_alpha_v67.py`

**Usage**:
```bash
python tests/test_bot.py
```

**Test Coverage**:
- ✅ PositionDatabase operations
- ✅ ConfigManager loading and validation
- ✅ PatternDetector accuracy
- ✅ RajatAlphaAnalyzer logic
- ✅ Integration tests
- ✅ Method existence verification

**Test Classes**:
1. `TestPositionDatabase`: Database CRUD operations
2. `TestConfigManager`: Configuration loading
3. `TestPatternDetector`: Pattern recognition
4. `TestRajatAlphaAnalyzer`: Signal analysis
5. `TestIntegration`: End-to-end workflows
6. `TestMethodExistence`: API compatibility

---

### 2. `test_comprehensive.py`

**Purpose**: Comprehensive integration and system tests.

**Original Name**: `comprehensive_test.py`

**Usage**:
```bash
python tests/test_comprehensive.py
```

**Test Coverage**:
- ✅ Complete signal detection pipeline
- ✅ Entry requirement validation
- ✅ Exit management system
- ✅ Risk management logic
- ✅ Position tracking accuracy
- ✅ Configuration validation

**Features**:
- Tests entire signal-to-trade workflow
- Validates all entry requirements
- Tests edge cases and error handling
- Performance testing
- Integration with Alpaca API (mocked)

---

### 3. `test_analysis.py`

**Purpose**: Tests for stock analysis tools.

**Original Name**: `test_stock_analysis.py`

**Usage**:
```bash
python tests/test_analysis.py
```

**Test Coverage**:
- ✅ Technical indicator calculations
- ✅ Market structure detection
- ✅ Multi-timeframe analysis
- ✅ Pattern recognition accuracy
- ✅ Scoring system logic

---

## Running Tests

### Run All Tests
```bash
# From Single_Buy directory
python tests/test_bot.py
python tests/test_comprehensive.py
python tests/test_analysis.py
```

### Run Specific Test Class
```bash
# Example: Run only PatternDetector tests
python -m unittest tests.test_bot.TestPatternDetector
```

### Run with Verbose Output
```bash
python tests/test_bot.py -v
```

## Test Philosophy

### What We Test

1. **Core Logic**
   - Entry signal detection
   - Exit trigger conditions
   - Risk calculations
   - Position sizing

2. **Data Operations**
   - Database CRUD
   - Configuration loading
   - File I/O operations

3. **Integration Points**
   - API connectivity (mocked)
   - Multi-component workflows
   - Error handling

### What We Don't Test

- Live market data (too variable)
- Actual trade execution (use paper trading)
- External API behavior (not under our control)
- UI components (manual testing)

## Test Database

Tests use a separate database (`db/test_positions.db`) to avoid corrupting production data.

**Note**: Test database is automatically created and cleaned up by tests.

## Adding New Tests

### Template for New Test Class

```python
import unittest
from rajat_alpha_v67_single import YourClass

class TestYourFeature(unittest.TestCase):
    """Tests for your new feature"""
    
    def setUp(self):
        """Called before each test"""
        self.instance = YourClass()
    
    def tearDown(self):
        """Called after each test"""
        pass
    
    def test_basic_functionality(self):
        """Test basic feature works"""
        result = self.instance.your_method()
        self.assertTrue(result)
    
    def test_edge_case(self):
        """Test edge case handling"""
        with self.assertRaises(ValueError):
            self.instance.your_method(bad_input)

if __name__ == '__main__':
    unittest.main()
```

## Test Coverage

### Current Coverage

- **High Coverage** (>80%):
  - Database operations
  - Configuration management
  - Pattern detection
  - Signal scoring

- **Medium Coverage** (50-80%):
  - Market structure checks
  - Risk management
  - Exit logic

- **Low Coverage** (<50%):
  - API integration (mostly mocked)
  - Logging functionality
  - Error recovery

### Coverage Goal

Target: 80%+ coverage for core trading logic

## Common Test Failures

### Database Locked
**Cause**: Another process has database open  
**Fix**: Close other database connections, restart test

### Import Errors
**Cause**: Missing dependencies or wrong directory  
**Fix**: Run from `Single_Buy/` directory, install requirements

### API Errors
**Cause**: Invalid test API keys  
**Fix**: Update test config with valid paper trading keys

### Assertion Failures
**Cause**: Logic changes breaking tests  
**Fix**: Review changes, update tests if logic intentionally changed

## Best Practices

1. **Run tests before committing changes**
2. **Add tests for new features**
3. **Keep tests independent** (no test depends on another)
4. **Use setUp/tearDown** for common initialization
5. **Test edge cases** (empty data, invalid input, etc.)
6. **Mock external dependencies** (APIs, file I/O)
7. **Keep tests fast** (<1 second per test)

## Continuous Testing

### Pre-Commit Checklist
```bash
# 1. Run all tests
python tests/test_bot.py
python tests/test_comprehensive.py
python tests/test_analysis.py

# 2. Check for errors
echo $?  # Should be 0

# 3. Review coverage
# (Add coverage tool if needed)
```

### Automated Testing
Consider setting up:
- Pre-commit hooks to run tests
- CI/CD pipeline for automatic testing
- Scheduled nightly test runs

## Troubleshooting Tests

### Tests Hang
- Check for infinite loops
- Verify API calls are mocked
- Look for database locks

### Tests Fail Randomly
- Check for timing dependencies
- Verify test isolation
- Look for shared state

### Tests Pass But Bot Fails
- Tests may not cover all scenarios
- Add integration tests
- Test with real market data (paper trading)

## Requirements

- Python 3.8+
- unittest (built-in)
- All main bot dependencies
- Test database access

No additional test frameworks required.
