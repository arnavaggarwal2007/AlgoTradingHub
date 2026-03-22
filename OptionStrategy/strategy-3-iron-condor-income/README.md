# Strategy 3: Iron Condor Income Machine

## Profit When Markets Stay in a Range (Which They Do 70% of the Time)

> **The Iron Condor is the ultimate "I don't think the market will do anything crazy" trade.**
> You collect premium from BOTH sides — puts AND calls — and profit as long as the underlying
> stays within your expected range. It's like getting paid for predicting normalcy.

---

## Table of Contents

1. [What Is an Iron Condor?](#what-is-it)
2. [Why It Works](#why-it-works)
3. [The Mechanical Rules](#rules)
4. [Stock/ETF Selection](#selection)
5. [Manual Trading Guide](#manual-guide)
6. [Automated Bot Guide](#bot-guide)
7. [Configuration Reference](#configuration)
8. [Risk Management](#risk-management)
9. [Adjustment Techniques](#adjustments)
10. [Real Trade Examples](#examples)

---

## 1. What Is an Iron Condor? {#what-is-it}

An Iron Condor combines TWO credit spreads:
1. **Bull Put Spread** (below the market) — protection against downside
2. **Bear Call Spread** (above the market) — protection against upside

You collect premium from BOTH sides and profit if the price stays BETWEEN your short strikes.

```
Profit/Loss Diagram:

    P&L
     |
  +$3│          ┌────────────────┐
     │         ╱                  ╲
   $0│────────╱────────────────────╲────────
     │       ╱                      ╲
  -$2│──────╱                        ╲──────
     │
     └────────────────────────────────────────→ Price
        450   460   470   480   490   500   510   520

     Put Spread:  460/450 (Bull Put)     ← Downside protection
     Call Spread: 510/520 (Bear Call)    ← Upside protection
     
     "Profit Zone": Between 460 and 510
     Total Credit: $3.00 ($300 per iron condor)
     Max Loss: $2.00 ($200 per side) = Width - Credit/2
```

### Iron Condor = 4 Legs

| Leg | Action | Strike | Type | Purpose |
|-----|--------|--------|------|---------|
| 1 | BUY | 450 | Put | Long protection (downside) |
| 2 | SELL | 460 | Put | Short leg (collect premium) |
| 3 | SELL | 510 | Call | Short leg (collect premium) |
| 4 | BUY | 520 | Call | Long protection (upside) |

### Key Insight: Markets Range More Than They Trend

Historical data shows:
- **70% of trading days**: Market moves < 1%
- **85% of months**: Market stays within 1 standard deviation
- **Iron Condors profit when "nothing happens"** — and nothing happens most of the time

---

## 2. Why It Works {#why-it-works}

### The Premium Collection Machine

Since you're selling TWO spreads, you collect MORE premium than a single spread:

| Strategy | Premium Collected | Max Loss | Win Rate |
|----------|------------------|----------|----------|
| Single Put Spread | $2.00 | $3.00 | 85% |
| Single Call Spread | $1.50 | $3.50 | 85% |
| **Iron Condor (both)** | **$3.50** | **$1.50** | **~70-80%** |

Notice: The combined credit REDUCES your max loss per side because you collect from both directions.

### Theta Decay on Steroids

With 4 legs decaying simultaneously, your Theta income is roughly doubled compared to a single spread.

```
Single spread Theta:  ~$5/day
Iron Condor Theta:    ~$8-12/day per contract

On 5 iron condors: $40-60/day in time decay income
Monthly: $800-$1,200 just from Theta
```

---

## 3. The Mechanical Rules {#rules}

### Entry Criteria

```
IRON CONDOR ENTRY CHECKLIST:
  ✅ IV Rank > 30 (higher IV = better premium = wider wings)
  ✅ DTE: 30-45 days (sweet spot for Theta)
  ✅ Put side: Delta = 0.10-0.15 (90-85% POP per side)
  ✅ Call side: Delta = 0.10-0.15 (same)
  ✅ Wing width: $5-$10 (defined risk per side)
  ✅ Total credit > 1/3 of wing width
  ✅ No earnings within DTE period
  ✅ VIX between 15-30 (sweet spot for iron condors)
```

### The "1/3 Rule" for Credit

**Your total credit should be at least 1/3 of the wing width.** This ensures a favorable risk/reward.

```
Wing width: $10
Minimum credit: $3.33
If you can't get $3.33, the trade isn't worth the risk.

Example:
  Put spread: 460/450 ($10 wide) → Credit $2.00
  Call spread: 510/500 ($10 wide) → Credit $1.80
  Total credit: $3.80 > $3.33 ✅
```

### Exit Rules

```
EXIT RULES (check every 5 minutes):
  1. Total P&L > 50% of credit → CLOSE ALL 4 LEGS
  2. One side breached (delta > 0.40) → CLOSE THAT SIDE
  3. DTE ≤ 21 → CLOSE ALL LEGS
  4. Total loss > 2× credit → CLOSE ALL LEGS
  5. VIX spikes > 35 intraday → CLOSE ALL (market stress)
```

### Best Underlyings for Iron Condors

| Symbol | Type | Why It's Great |
|--------|------|----------------|
| SPY | ETF | Liquid, diversified, predictable range |
| QQQ | ETF | Tech-heavy but very liquid |
| IWM | ETF | Small caps, higher IV = better premium |
| SPX/XSP | Index | Cash-settled, tax benefits |
| AAPL | Stock | Liquid, tends to range between earnings |
| MSFT | Stock | Same — stable, liquid |

---

## 4. Stock/ETF Selection {#selection}

### Ideal Iron Condor Candidates

The perfect iron condor candidate:
1. **High liquidity** — tight bid-ask spreads
2. **Elevated IV** — IVR > 30 for good premium
3. **Range-bound** — not in a strong trend
4. **No catalysts** — no earnings, no FDA approvals, no splits
5. **Clean chart** — clear support and resistance levels

### When NOT to Trade Iron Condors

🚫 **Strong trending market** (use directional spreads instead)
🚫 **VIX < 12** (not enough premium to justify risk)  
🚫 **VIX > 35** (too volatile, one side will get breached)
🚫 **Major events** (Fed meetings, elections, earnings season for stocks)

---

## 5. Manual Trading Guide {#manual-guide}

### Step-by-Step: Placing an Iron Condor

#### Step 1: Choose Your Underlying
- Pick a liquid ETF (SPY, QQQ, IWM) or stock
- Check that IVR > 30

#### Step 2: Choose Your Expiration
- 30-45 DTE
- Avoid any dates with known catalysts

#### Step 3: Pick the Put Side (Below Current Price)
1. Find the put with Delta ≈ −0.12
2. This is your **SHORT PUT** strike
3. Go $5-$10 below for your **LONG PUT** strike (protection)

#### Step 4: Pick the Call Side (Above Current Price)
1. Find the call with Delta ≈ 0.12
2. This is your **SHORT CALL** strike
3. Go $5-$10 above for your **LONG CALL** strike (protection)

#### Step 5: Verify the Credit
```
Total Credit = Put Spread Credit + Call Spread Credit
Minimum = Wing Width / 3

Example (SPY at $530):
  Sell 510 Put / Buy 500 Put = $1.20 credit
  Sell 555 Call / Buy 565 Call = $1.10 credit
  Total: $2.30 credit on $10 wings
  $2.30 > $3.33? NO → Widen wings or pick higher IV underlying

  Try $5 wings:
  Sell 515 Put / Buy 510 Put = $0.90
  Sell 545 Call / Buy 550 Call = $0.80
  Total: $1.70 on $5 wings
  $1.70 > $1.67 ✅ (barely — acceptable)
```

#### Step 6: Place the Order
- Order Type: **Iron Condor** (most brokers have this)
- Or place as two separate spread orders
- Price: Limit at or near mid-price
- Quantity: 1 iron condor to start

#### Step 7: Management
- Check once daily (2-3 minutes)
- Set alerts for 50% profit and stop loss

### Manual Iron Condor P&L Scenarios

Given: SPY Iron Condor, $5 wings, $1.70 total credit

| SPY at Expiration | Put Side | Call Side | Total P&L |
|-------------------|----------|-----------|-----------|
| $490 (below long put) | -$330 | +$80 | -$250 |
| $510 (below short put) | -$160 | +$80 | -$80 |
| $515 (at short put) | +$0 | +$80 | +$80 |
| $530 (center) | +$90 | +$80 | **+$170** (max) |
| $545 (at short call) | +$90 | +$0 | +$90 |
| $555 (above short call) | +$90 | -$170 | -$80 |
| $570 (above long call) | +$90 | -$420 | -$330 |

---

## 6. Automated Bot Guide {#bot-guide}

File: `iron_condor_bot.py`

### What the Bot Does

```
DAILY ROUTINE:
  1. Check IVR for watchlist (is it worth trading today?)
  2. Monitor open iron condors for exit signals
     → 50% profit → Close entire condor
     → One side breached (delta > 0.40) → Close that side  
     → Stop loss → Close entire condor
     → Time exit (21 DTE) → Close
  3. If below max positions and IVR is good:
     → Find put spread at target delta
     → Find call spread at target delta
     → Verify combined credit meets 1/3 rule
     → Execute at mid-price
  4. Log daily P&L and performance
```

### Running the Bot

```bash
cd strategy-3-iron-condor-income
python iron_condor_bot.py              # Paper trading
python iron_condor_bot.py --dry-run    # Preview mode
python iron_condor_bot.py --symbol IWM # Trade IWM instead
```

---

## 7. Configuration Reference {#configuration}

```json
{
    "strategy": "iron_condor_income",
    "watchlist": ["SPY", "QQQ", "IWM"],
    "condor_rules": {
        "put_delta": 0.12,
        "call_delta": 0.12,
        "wing_width": 5,
        "min_dte": 30,
        "max_dte": 45,
        "min_total_credit_ratio": 0.33,
        "profit_target_pct": 0.50,
        "stop_loss_multiplier": 2.0,
        "time_exit_dte": 21,
        "side_breach_delta": 0.40
    },
    "iv_rules": {
        "min_iv_rank": 30,
        "optimal_iv_rank": 50,
        "skip_below_vix": 12,
        "skip_above_vix": 35
    },
    "risk": {
        "max_concurrent_condors": 5,
        "max_risk_per_condor_pct": 0.05,
        "max_portfolio_exposure_pct": 0.20
    }
}
```

---

## 8. Risk Management {#risk-management}

### Iron Condor Risk Profile

| Scenario | What Happens | Action |
|----------|-------------|--------|
| SPY stays flat | Both sides expire worthless → **MAX PROFIT** | Keep full credit |
| SPY moves up slightly | Call side stressed, put side profits | Monitor call side delta |
| SPY moves down slightly | Put side stressed, call side profits | Monitor put side delta |
| SPY movers sharply one direction | One side hit, other side expires OTM | Stop loss on breached side |
| SPY gaps huge (black swan) | One side max loss, other side max profit | Net loss = max loss - other credit |

### The "Defend the Tested Side" Approach

When one side is threatened:
1. **Delta > 0.30**: Warning — the side is getting tested
2. **Delta > 0.40**: Close the tested side (take the loss)
3. **Keep the untested side** — it will still decay to zero
4. **Net P&L** = credit from winners side - loss from tested side

This is better than closing the entire condor at a loss.

### Maximum Loss Calculation

```
Max loss per side = Wing Width - (Total Credit / 2)
                  = $5 - ($1.70 / 2)
                  = $5 - $0.85
                  = $4.15 per side
                  
Total max loss = $4.15 × 100 = $415 per iron condor
But with stop loss at 2×: actual max = $1.70 × 2 × 100 = $340
```

---

## 9. Adjustment Techniques {#adjustments}

### Technique 1: Roll the Tested Side

If the put side is breached:
1. Close the current put spread (take small loss)
2. Open a new put spread further OTM at same or later expiration
3. You collect additional credit on the new spread

### Technique 2: Convert to a 3-Legged "Broken Wing"

If one side is breached but you're optimistic it will recover:
1. Close the tested side only
2. Leave the untested side to decay
3. The untested side's credit reduces your loss on the tested side

### Technique 3: "Roll Down and Out"

If the put side is tested and you have time:
1. Close current put spread
2. Sell a new put spread 2-3 weeks further out, further OTM
3. Target a NET CREDIT on the roll (receive more than you pay)

### When NOT to Adjust

🚫 Don't adjust within 7 DTE — just close and take the loss  
🚫 Don't roll for a net debit — you're adding risk, not reducing it  
🚫 Don't adjust more than once per condor — it's a sign the trade is wrong  

---

## 10. Real Trade Examples {#examples}

### Example 1: Perfect Iron Condor (Both Sides Win)

```
Date: February 1, 2026
SPY: $530
IVR: 42

Iron Condor:
  Sell 510 Put / Buy 505 Put = $0.80  (Delta: -0.11)
  Sell 555 Call / Buy 560 Call = $0.70 (Delta: 0.10)
  Total Credit: $1.50 ($150 per condor)
  Wing Width: $5 each side
  Max Loss: ($5 - $1.50) × 100 = $350 per side

February 14 (13 days later):
  SPY at $528 (barely moved)
  Both sides decaying nicely
  Iron condor now worth $0.70
  P&L: +$80 (53% of max)
  
  Action: CLOSE ALL LEGS
  Net Profit: +$80 per condor in 13 days
  Annualized: ($80/$350) × (365/13) = 642% ✅ (this is why the math works)
```

### Example 2: One Side Tested (Partial Management)

```
Date: March 1, 2026
QQQ: $480
IVR: 35

Iron Condor:
  Sell 460 Put / Buy 455 Put = $0.90
  Sell 500 Call / Buy 505 Call = $0.75
  Total Credit: $1.65

March 10:
  QQQ rallies to $498 (near short call)
  Call spread delta: 0.38 (approaching breach)
  Put spread: nearly worthless ($0.10) — this side wins
  
  Action: CLOSE THE CALL SIDE at $2.50

  P&L:
    Call side: Collected $0.75, paid $2.50 = -$175 loss
    Put side: Worth $0.10, close for +$80 (collected $0.90)
    Net: -$175 + $80 = -$95 total loss

  Without management: max loss could have been $335
  With management: loss limited to -$95 ✅
```

---

## Key Takeaways

1. **Iron Condors work best in range-bound, moderate IV environments**
2. **Collect from both sides = more income, better risk/reward**
3. **The 1/3 rule ensures favorable math**
4. **Manage one side at a time — don't panic close everything**
5. **Exit at 50% profit — don't wait for expiration**
6. **Works great alongside Strategy 1 (Wheel) or Strategy 2 (SPX Spreads)**

*Markets do nothing exciting 70% of the time. Iron Condors turn boring into profitable.*
