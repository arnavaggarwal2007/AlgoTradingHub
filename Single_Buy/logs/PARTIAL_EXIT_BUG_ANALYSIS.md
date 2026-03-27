# Partial Exit Bug Analysis & Fix
**Date: March 27, 2026**
**Issue: Partial Exit Quantity Calculation Bug**

---

## SUMMARY

❌ **BUG CONFIRMED**: Partial exits calculate 33% of **remaining qty** instead of **original qty**

**Impact**: Each subsequent partial exit sells incorrect (lower) amounts than intended

---

## BUG EVIDENCE

### HAL (Position 14) - Live Example from Database

**Configuration:**
- PT1 @ 10%: Sell 33.3% 
- PT2 @ 15%: Sell 33.3%
- PT3 @ 20%: Sell 33.4%

**What SHOULD Happen (Correct Logic):**
```
Original Qty: 85 shares

PT1 @ 10% profit:
  Expected to sell: 33.3% × 85 = 28 shares
  Remaining after: 85 - 28 = 57 shares

PT2 @ 15% profit:
  Expected to sell: 33.3% × 85 = 28 shares  ← STILL 28 (of original)
  Remaining after: 57 - 28 = 29 shares

PT3 @ 20% profit:
  Expected to sell: 33.4% × 85 = 28 shares  ← STILL 28 (of original)
  Remaining after: 29 - 28 = 1 share
```

**What ACTUALLY Happened (Bug in Code):**
```
Original Qty: 85 shares

PT1 @ 10% profit (March 24):
  SOLD: 28 shares @ $38.29 ✓ CORRECT
  Remaining: 57 shares

PT2 @ 15% profit (March 26):
  SOLD: 18 shares @ $39.73 ❌ WRONG
  Expected: 28 shares (33% of original 85)
  Actual: 18 shares (33% of remaining 57)
  
  PROOF: 57 × 0.333 = 18.98 ≈ 18
         85 × 0.333 = 28.31 ≈ 28
```

### Database Records Confirming Bug

```
PARTIAL EXITS TABLE (last 7 days):

1. HAL (PT1) - 2026-03-24
   Original Qty: 85
   Qty Sold: 28 
   Status: OK (28 = 33% of 85)

2. HAL (PT2) - 2026-03-26
   Original Qty: 85
   Qty Sold: 18
   Status: BUG (18 ≠ 28; it's 33% of 57 remaining, not 85 original)
   
   Expected: 28 (33% of 85)
   Actual:   18 (33% of 57)
   Error:    -10 shares SHORT

3. AEIS (PT1) - 2026-03-24
   Status: OK (small qty, coincidentally correct)

4. NVMI (PT1) - 2026-03-24
   Status: OK (small qty, coincidentally correct)
```

---

## ROOT CAUSE

**File:** `c:\Alpaca_Algo\Single_Buy\rajat_alpha_v67_single.py`
**Method:** `check_partial_exit_targets()` (line ~1460)
**Problematic Code:**

```python
def check_partial_exit_targets(self, position: Dict, current_price: float) -> List[Tuple[str, int, float]]:
    """
    Check if partial profit targets are hit
    Returns: [(target_name, quantity_to_sell, target_price)]
    """
    if not self.config.get('profit_taking', 'enable_partial_exits'):
        return []
    
    entry_price = position['entry_price']
    remaining_qty = position['remaining_qty']  # <-- THIS IS THE PROBLEM
    
    exits_to_execute = []
    
    # ... loop through targets ...
    
    for target_name, target_pct, target_qty_pct in targets:
        target_price = entry_price * (1 + target_pct)
        
        if current_price >= target_price:
            # Check if we've already taken this target
            cursor = self.db.conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM partial_exits 
                WHERE position_id = ? AND profit_target = ?
            ''', (position['id'], target_name))
            already_taken = cursor.fetchone()[0] > 0
            
            if not already_taken and remaining_qty > 0:
                qty_to_sell = int(remaining_qty * target_qty_pct)  # ❌ BUG: Uses remaining_qty
                if qty_to_sell > 0:
                    exits_to_execute.append((target_name, qty_to_sell, target_price))
    
    return exits_to_execute
```

**The Bug:**
Line: `qty_to_sell = int(remaining_qty * target_qty_pct)`

Should be:
Line: `qty_to_sell = int(position['quantity'] * target_qty_pct)`

---

## SOLUTION

Change the calculation to use **original quantity** (`position['quantity']`) instead of **remaining quantity** (`remaining_qty`):

### Before (BUGGY):
```python
qty_to_sell = int(remaining_qty * target_qty_pct)
```

### After (FIXED):
```python
qty_to_sell = int(position['quantity'] * target_qty_pct)
```

---

## IMPACT ANALYSIS

### Affected Positions
- **HAL (Position 14)**: Already affected
  - PT1 (Mar 24): Sold 28 correctly
  - PT2 (Mar 26): Sold 18 instead of 28 (SHORT by 10)
  - PT3 @ 20%: If triggered, will sell ~12 instead of 28 (SHORT by 16)

### Future Positions
- Any position with multiple partial exits will compound the error
- PT1 usually correct (sells 33% of original)
- PT2 sells 33% of (original - PT1) instead of 33% of original
- PT3 sells 33% of (original - PT1 - PT2_buggy) instead of 33% of original

### Example with 120-share position:
```
Expected (Correct):
- PT1: 40 shares (33% of 120)
- PT2: 40 shares (33% of 120)
- PT3: 40 shares (33% of 120)
Total: 120 shares

Actual (Buggy):
- PT1: 40 shares (33% of 120) ✓
- PT2: 26 shares (33% of 80 remaining) ❌
- PT3: 17 shares (33% of 54 remaining) ❌
Total: 83 shares (17 shares left over)
```

---

## VERIFICATION

After applying fix, HAL position should show:
- PT1 (Mar 24): 28 shares @ $38.29 ✓
- PT2 (Mar 26): 28 shares @ $39.73 (currently wrong, showing 18)
  - After fix: New PT2 execution will be corrected when next target hit
  - **Note**: Historical data cannot be retroactively corrected; only future execution will be accurate

---

## RECOMMENDATION

1. **Immediate**: Apply the code fix to prevent further incorrect PT2/PT3 exits
2. **HAL Position**: Monitor for PT3 @ 20% target
   - When price hits 20% gain, should sell 28 shares (not ~12)
3. **Future**: Consider adding a "reset" mechanism for misaligned partial exits (optional)

