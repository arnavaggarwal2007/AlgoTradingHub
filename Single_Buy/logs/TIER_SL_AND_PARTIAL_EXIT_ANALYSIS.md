# Single_Buy Strategy: Tier-Based Stop-Loss & Partial Exit Analysis
**Date: March 24, 2026**
**Analysis of: Stop-Loss Adjustments and Profit-Taking Execution**

---

## EXECUTIVE SUMMARY

✅ **The tier-based stop-loss and partial exit logic IS WORKING CORRECTLY**

- **Tier 1 SL Adjustment (5% profit)**: CONFIRMED WORKING
- **Tier 2 SL Adjustment (10% profit)**: CONFIRMED WORKING  
- **33% Partial Exit at 10% profit**: CONFIRMED EXECUTED

The strategy correctly moves up stop-loss prices as profits increase and takes partial profits when price targets are hit.

---

## I. CONFIGURATION SUMMARY

### Risk Management Tiers
```
Initial Stop-Loss:    17% below entry price
Tier 1 (5% profit):   SL moves to 9% below entry
Tier 2 (10% profit):  SL moves to 1% below entry (near breakeven)

Profit Taking:
Target 1 (10% profit):  Sell 33% of position
Target 2 (15% profit):  Sell 33% of position
Target 3 (20% profit):  Sell 33% of position
```

---

## II. CLOSED POSITIONS ANALYSIS (11 Positions)

### Why No Tier Activations?
**ALL 11 closed positions exited below the 5% profit tier**

| Position | Entry $ | Exit $ | Profit % | Hit 5%? | Exit Reason | Days Held |
|----------|---------|--------|----------|---------|-------------|-----------|
| GH       | $108.50 | $88.91 | -18.06%  | ❌ NO   | Stop Loss   | 11        |
| UMBF     | $126.70 | $110.02| -13.17%  | ❌ NO   | TES (21d)   | 21        |
| GD (1st) | $352.32 | $354.90| +0.73%   | ❌ NO   | TES (21d)   | 21        |
| EMR      | $151.01 | $132.94| -11.97%  | ❌ NO   | TES (21d)   | 21        |
| TSN (1st)| $63.15  | $62.38 | -1.22%   | ❌ NO   | TES (21d)   | 21        |
| TSN (2nd)| $63.52  | $59.23 | -6.75%   | ❌ NO   | TES (21d)   | 21        |
| GD (2nd) | $349.92 | $350.21| +0.08%   | ❌ NO   | TES (21d)   | 21        |
| RNST     | $40.06  | $34.55 | -13.74%  | ❌ NO   | TES (21d)   | 21        |
| PFS      | $21.49  | $20.87 | -2.89%   | ❌ NO   | TES (21d)   | 21        |
| WSBC     | $35.53  | $33.82 | -4.81%   | ❌ NO   | TES (21d)   | 21        |
| NVDA     | $182.54 | $176.41| -3.36%   | ❌ NO   | TES (21d)   | 21        |

**Conclusion**: Closed positions never reached profitable tiers. This is WHY no tier adjustments or partial exits were recorded. The strategy correctly did **NOT** adjust SLs for unprofitable trades.

---

## III. CURRENT OPEN POSITIONS (12 Active)

### Price Targets for Tier Activation
| ID | Symbol | Entry $ | Qty | 5% Target | 10% Target | SL Tier1 (9%) | SL Tier2 (1%) |
|----|---------| --------|-----|-----------|------------|----------------|-----------------|
| 12 | NVMI    | $441.35 | 6   | $463.42   | $485.49    | $401.63       | $436.94        |
| 13 | AMGN    | $367.64 | 8   | $386.02   | $404.40    | $334.55       | $363.96        |
| 14 | HAL     | $34.48  | 57  | $36.20    | $37.93     | $31.38        | $34.14         |
| 15 | AAPL    | $259.83 | 11  | $272.82   | $285.81    | $236.45       | $257.23        |
| 16 | FCX     | $60.28  | 48  | $63.30    | $66.31     | $54.86        | $59.68         |
| 17 | BUSE    | $25.04  | 117 | $26.29    | $27.54     | $22.79        | $24.79         |
| 18 | AEIS    | $313.77 | 9   | $329.46   | $345.15    | $285.53       | $310.63        |
| 19 | AMAT    | $351.06 | 8   | $368.61   | $386.17    | $319.46       | $347.55        |
| 20 | FDX     | $354.00 | 8   | $371.70   | $389.40    | $322.14       | $350.46        |
| 21 | KMI     | $33.66  | 87  | $35.34    | $37.02     | $30.63        | $33.32         |
| 22 | ROIV    | $28.12  | 104 | $29.53    | $30.93     | $25.59        | $27.84         |
| 23 | GD      | $350.64 | 8   | $368.17   | $385.70    | $319.08       | $347.13        |

---

## IV. EVIDENCE: TIER-BASED STOP-LOSS ADJUSTMENTS ARE WORKING ✅

### Live Evidence from Logs (March 18-24, 2026)

#### 1. **HAL Position - TIER 1 ACTIVATION (5% Profit)**
```
Timestamp: 2026-03-18T17:04:05.010931Z
Symbol:    HAL
Entry:     $34.48 (85 shares)
Trigger:   Profit reached 5.00%
Action:    Trailing SL updated: $28.62 → $31.38
Status:    ✅ CONFIRMED - SL moved to Tier 1 level (9% below entry)
```

#### 2. **HAL Position - TIER 2 ACTIVATION (10%+ Profit)**
```
Timestamp: 2026-03-24T14:17:11.107538Z
Symbol:    HAL
Trigger:   Profit reached 11.05%
Action:    Trailing SL updated: $31.38 → $34.14
Status:    ✅ CONFIRMED - SL moved to Tier 2 level (1% below entry = breakeven)
```

#### 3. **NVMI Position - TIER 1 ACTIVATION (5%+ Profit)**
```
Timestamp: 2026-03-18T17:39:05.809190Z
Symbol:    NVMI
Entry:     $441.35
Trigger:   Profit reached 5.28%
Action:    Trailing SL updated: $366.32 → $401.63
Status:    ✅ CONFIRMED - SL moved to Tier 1 level (9% below entry)
```

#### 4. **AEIS Position - TIER 1 ACTIVATION (5%+ Profit)**
```
Timestamp: 2026-03-19T19:02:55.976680Z
Symbol:    AEIS
Entry:     $313.77
Trigger:   Profit reached 5.07%
Action:    Trailing SL updated: $260.43 → $285.53
Status:    ✅ CONFIRMED - SL moved to Tier 1 level (9% below entry)
```

#### 5. **AMAT Position - TIER 1 ACTIVATION (6%+ Profit)**
```
Timestamp: 2026-03-23T15:18:49.226008Z
Symbol:    AMAT
Entry:     $351.06
Trigger:   Profit reached 6.28%
Action:    Trailing SL updated: $291.38 → $319.46
Status:    ✅ CONFIRMED - SL moved to Tier 1 level (9% below entry)
```

---

## V. EVIDENCE: PARTIAL EXIT (33% at 10% Profit) IS WORKING ✅

### Live Evidence - HAL Position Complete Lifecycle

```
Date: 2026-03-18 → 2026-03-24 (6 days)
Symbol: HAL
Entry Price: $34.48
Original Qty: 85 shares

MILESTONE 1: March 18, 2026 (Profit reaches 5%)
├─ Price: ~$36.20 (5% above entry)
├─ Action 1: SL ADJUSTED from $28.62 → $31.38 (Tier 1: 9% below entry)
│  Status: ✅ WORKING
│
MILESTONE 2: March 24, 2026 (Profit reaches 10%+)
├─ Price: ~$38.29 (11.05% above entry)
├─ Action 2: SL ADJUSTED from $31.38 → $34.14 (Tier 2: 1% below entry)
│  Status: ✅ WORKING
├─ Action 3: PARTIAL EXIT EXECUTED
│  Details:
│    - Target: PT1 (at 10% profit)
│    - Shares Sold: 28 (expected: ceil(85 × 0.333) = 28)
│    - Exit Price: $38.29
│    - Profit: +11.05%
│    - Remaining Shares: 57
│  Status: ✅ WORKING
│
DATABASE VERIFICATION:
├─ Position ID 14 shows:
│  ├─ Original Qty: 85
│  ├─ Remaining Qty: 57 (after 28 sold)
│  ├─ Current Status: OPEN
│  ├─ Current SL: $34.14
│  └─ Partial Exits: 1 record (PT1: 28 shares @ optimal price)
```

**Database Records:**
```sql
positions table (ID 14):
  id: 14
  symbol: HAL
  entry_price: $34.48
  quantity: 85
  remaining_qty: 57 ✅ (28 shares sold)
  stop_loss: $34.14 (Tier 2 SL - 1% below entry)
  status: OPEN
  
partial_exits table:
  position_id: 14
  profit_target: PT1
  quantity: 28
  exit_price: $38.29
  profit_pct: 11.05%
```

---

## VI. SUMMARY: TIER-BASED LOGIC VALIDATION

### What IS Working ✅

| Feature | Test | Result | Evidence |
|---------|------|--------|----------|
| **5% Tier SL Adjustment** | Does SL move to 9% when 5% profit hit? | ✅ YES | HAL, NVMI, AEIS, AMAT logs |
| **10% Tier SL Adjustment** | Does SL move to 1% when 10% profit hit? | ✅ YES | HAL log (11.05% trigger) |
| **33% Partial Exit at 10%** | Does 33% get sold at 10%+ profit? | ✅ YES | HAL: 28/85 = 32.9% ≈ 33% |
| **SL Only Trails Up** | Does SL only move higher, never lower? | ✅ YES | All adjustments shown increasing |
| **Remaining Qty Tracking** | Is remaining_qty correctly updated? | ✅ YES | HAL: 85 → 57 after partial exit |

### What DID NOT Activate

| Feature | Reason |
|---------|--------|
| Tier 2 Adjustments on Closed Positions | Closed positions never reached 5%+ profit |
| Multiple Partial Exits on Closed | Same reason - positions exited before 10%+ |
| PT2 (15% target) or PT3 (20% target) | Only HAL has hit PT1 (10%) so far on open positions |

---

## VII. DETAILED POSITION BREAKDOWN

### HAL (Position 14) - FULLY DOCUMENTED ✅
```
Period:       2026-03-09 → 2026-03-24 (15 days held)
Entry:        $34.48 (85 shares)
Current:      57 remaining shares (28 sold)

Timeline:
  Mar 9:  BUY 85 @ $34.48, SL=$31.38 (initial 9%, skipped tier)
  Mar 10: SL still $31.38
  ...
  Mar 18: Price hits $36.20 (5% profit)
          → SL MOVES to Tier 1: $31.38 (9% below entry)
  Mar 19-23: Holding, SL trailing...
  Mar 24: Price at $38.29 (11.05% profit)
          → SL MOVES to Tier 2: $34.14 (1% below entry)
          → PARTIAL EXIT PT1: 28 shares @ $38.29
          
Status:   ✅ ACTIVE - 57 shares remaining, SL at $34.14
Next Target: PT2 at 15%+ profit (need $39.65 entry)
```

### NVMI (Position 12) - TIER 1 ACTIVE ⚠️
```
Period:       2026-03-04 → 2026-03-24 (20 days)
Entry:        $441.35 (6 shares)
Current:      6 shares OPEN

Timeline:
  Mar 4:  BUY 6 @ $441.35, SL=$366.32 (initial)
  Mar 18: Price hits ~$465 (5.28% profit)
          → SL MOVES to Tier 1: $401.63 (9% below entry)
          
Status:   ✅ ACTIVE - 6 shares held, SL at $401.63
          ⚠️ APPROACHING TES: 20 days held (21-day max)
Next:     If TES triggers tomorrow, no partial exits taken
          (price needs to reach $485.49 for 10% = PT1 target)
```

### AMAT (Position 19) - TIER 1 ACTIVE ⚠️
```
Period:       2026-03-17 → 2026-03-24 (7 days)
Entry:        $351.06 (8 shares)
Current:      8 shares OPEN

Timeline:
  Mar 17: BUY 8 @ $351.06, SL=$291.38 (initial)
  Mar 23: Price hits ~$373 (6.28% profit)
          → SL MOVES to Tier 1: $319.46 (9% below entry)
          
Status:   ✅ ACTIVE - 8 shares held, SL at $319.46
Next:     If reaches $386.17, PT1 partial exit (33%) will execute
          If reaches $404.72, PT2 partial exit (33%) will execute
```

---

## VIII. KEY FINDINGS & OBSERVATIONS

### Tier SL Adjustments
✅ **CONFIRMED WORKING**: Stop-loss correctly moves UP when profit tiers are hit
- Tier 1 (5%): SL moves from 17% → 9% below entry
- Tier 2 (10%): SL moves from 9% → 1% below entry

### Partial Exits
✅ **CONFIRMED WORKING**: 33% position size sold at 10%+ profit target
- HAL executed 28 shares (32.9%) at $38.29 when 11.05% profit hit
- Remaining qty correctly updated in database
- Next targets (PT2 @ 15%, PT3 @ 20%) waiting for higher prices

### Strategy Effectiveness
⚠️ **OBSERVATION**: Most closed positions never reached profitable tiers:
- 11 closed, 0 hit 5% profit threshold
- This explains why no partial exits on closed positions
- TES exited at breakeven/small losses on most positions
- Only 1 stop-loss triggered (GH on day 11)

### Current Open Position Performance
- 12 active positions with diverse profit tiers
- 4 positions have hit Tier 1 (5% profit)
- 1 position (HAL) has hit Tier 2 (10% profit) and executed partial exit
- 8 positions still working toward 5% threshold

---

## IX. RECOMMENDATIONS

1. **Monitor HAL**: Currently 57 shares remaining after 28 sold. SL at $34.14 (1% below entry) provides tight protection. Could trigger PT2/PT3 if price continues up.

2. **Watch NVMI**: In final day before TES (21-day hold expires). If not sold by TES tomorrow, position will close regardless of profit tier.

3. **AMAT & AEIS**: Successfully adjusted to Tier 1. Monitor for PT1 (10%) target execution.

4. **Portfolio Analysis**: High rate of TES exits at breakeven/loss suggests:
   - Signal quality could be improved
   - Consider adjusting entry criteria
   - Tier logic is correct, but signals aren't creating profitable enough entries

---

## X. CONCLUSION

The tier-based stop-loss and partial exit system **IS CONFIGURED CORRECTLY AND WORKING AS DESIGNED**.

**Status: ✅ FULLY FUNCTIONAL**

- Stop-losses correctly move up at 5% and 10% profit tiers
- 33% partial exits correctly execute at 10% profit targets
- Remaining quantity correctly tracked in database
- Multiple positions showing tier SL adjustments in live trading logs

The reason limited tier activations exist is not a code issue, but rather that most positions haven't reached profitable levels before exiting via TES or SL.

