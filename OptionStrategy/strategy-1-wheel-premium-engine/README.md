# Strategy 1: The Wheel Premium Engine

## Cash-Secured Puts → Covered Calls → Repeat

> **The Wheel** is the single best strategy for someone starting options trading.
> It's simple, mechanical, and has been generating consistent income for 15+ years.
> Think of it as being a landlord — you collect rent (premium) on stocks you'd happily own.

---

## Table of Contents

1. [Strategy Explanation (Plain English)](#explanation)
2. [How It Works — Step by Step](#how-it-works)
3. [Stock Selection Criteria](#stock-selection)
4. [Manual Trading Guide (If You Want to Place Trades Yourself)](#manual-guide)
5. [Automated Bot Guide](#bot-guide)
6. [Configuration Reference](#configuration)
7. [Risk Management Rules](#risk-management)
8. [Real Trade Examples](#examples)
9. [Common Mistakes to Avoid](#mistakes)
10. [FAQ](#faq)

---

## 1. Strategy Explanation (Plain English) {#explanation}

### What Is The Wheel?

The Wheel is a **2-phase premium collection machine**:

**Phase A — Sell Cash-Secured Puts (CSPs):**
- You sell a put option on a stock you'd be happy to own at a lower price
- You get paid premium upfront (this is your income)
- If the stock stays above your strike price: you keep the premium, trade over ✅
- If the stock drops below your strike price: you buy the stock at a discount + keep the premium

**Phase B — Sell Covered Calls (CCs):**
- If you got assigned stock in Phase A, now you sell calls against those shares
- You get paid more premium (more income!)
- If the stock stays below your call strike: you keep the premium + the stock
- If the stock rises above your call strike: you sell the stock at a profit + keep the premium

**Then you repeat Phase A. That's The Wheel. 🎡**

### Why It Works

| Factor | Explanation |
|--------|-------------|
| **Theta Decay** | Options lose value every day. As the seller, time works FOR you |
| **Statistical Edge** | At 0.15 Delta, you win ~85% of the time |
| **Downside Buffer** | The premium you collect lowers your cost basis |
| **No Naked Risk** | CSPs are backed by cash, CCs are backed by shares |
| **Works in Any Market** | Bullish → CSPs expire worthless. Flat → same. Bearish → you buy stocks at a discount |

### Expected Returns

| Account Size | Monthly Premium | Annual Return | Assumptions |
|-------------|-----------------|---------------|-------------|
| $5,000 | $75–$150 | 18–36% | 1 contract, conservative stocks |
| $25,000 | $375–$750 | 18–36% | 3-5 contracts, diversified |
| $50,000 | $750–$1,500 | 18–36% | 5-10 contracts, diversified |
| $100,000 | $1,500–$3,000 | 18–36% | 10-20 contracts, diversified |

---

## 2. How It Works — Step by Step {#how-it-works}

### Phase A: Selling Cash-Secured Puts

```
Step 1: Pick a quality stock you'd own (e.g., AAPL at $180)
Step 2: Sell a put option at ~0.15 Delta (e.g., $165 strike, 30-45 DTE)
Step 3: Collect premium (e.g., $2.50 per share = $250 per contract)
Step 4: Wait.

Outcome A (85% of the time): Stock stays above $165 → 
  Put expires worthless → You keep $250 → Go back to Step 1

Outcome B (15% of the time): Stock drops below $165 →
  You buy 100 shares at $165 → Your actual cost = $165 - $2.50 = $162.50
  → Move to Phase B
```

### Phase B: Selling Covered Calls

```
Step 1: You own 100 shares of AAPL at cost basis $162.50
Step 2: Sell a call option at ~0.30 Delta (e.g., $185 strike, 30-45 DTE)
Step 3: Collect premium (e.g., $3.00 per share = $300 per contract)
Step 4: Wait.

Outcome A: Stock stays below $185 → 
  Call expires worthless → You keep $300 + still own shares → Repeat Phase B

Outcome B: Stock rises above $185 → 
  You sell shares at $185 → Profit = ($185 - $162.50) + $3.00 = $25.50/share
  → Go back to Phase A
```

### The Full Wheel Cycle Diagram

```
         ┌──────────────────┐
         │ Phase A: Sell CSP │←──────────────────────┐
         │ Collect Premium   │                       │
         └────────┬─────────┘                       │
                  │                                  │
         ┌────────▼─────────┐                       │
         │ Stock stays above │──YES──→ Keep Premium  │
         │ strike price?     │         Repeat ───────┘
         └────────┬─────────┘
                  │ NO (assigned)
                  │
         ┌────────▼─────────┐
         │ Phase B: Sell CC  │←──────────────────────┐
         │ Collect Premium   │                       │
         └────────┬─────────┘                       │
                  │                                  │
         ┌────────▼─────────┐                       │
         │ Stock stays below │──YES──→ Keep Premium  │
         │ call strike?      │         + Shares ─────┘
         └────────┬─────────┘
                  │ NO (called away)
                  │
                  └──→ Sell shares at profit
                       → Go back to Phase A
```

---

## 3. Stock Selection Criteria {#stock-selection}

### The "Would I Own This?" Test

**Only run The Wheel on stocks you'd happily hold for 6-12 months.**

If you can't answer YES to ALL of these, skip the stock:
- [ ] Is it a profitable, established company?
- [ ] Does it have a stock price between $20–$200 (affordable contracts)?
- [ ] Does it have liquid options (tight bid-ask spreads)?
- [ ] Is IV Rank > 30? (adequate premium)
- [ ] Is it NOT reporting earnings within the next 45 days?

### Recommended Watchlist (Wheel-Friendly Stocks)

| Symbol | Sector | Price Range | Why It's Good for The Wheel |
|--------|--------|-------------|---------------------------|
| AAPL | Tech | $150–$200 | Liquid, stable, you'd own it |
| MSFT | Tech | $350–$450 | Enterprise cloud king |
| AMD | Tech | $100–$170 | High IV = better premiums |
| NVDA | Tech | $100–$150 | AI leader, you know it from interviews |
| GOOGL | Tech | $150–$200 | Advertising monopoly |
| JPM | Finance | $180–$220 | Banking titan, dividend payer |
| COST | Consumer | $700–$900 | Resilient business model |
| WMT | Consumer | $75–$100 | Recession-proof |
| JNJ | Healthcare | $150–$170 | Dividend aristocrat |
| KO | Consumer | $55–$65 | Ultimate defensive stock |
| SPY | ETF | $450–$550 | Diversified, the whole market |
| QQQ | ETF | $400–$500 | Tech-heavy but diversified |

### Strike Selection Rules

| Phase | Delta Target | What This Means |
|-------|-------------|-----------------|
| CSP (Phase A) | 0.10–0.15 | 85–90% chance of expiring worthless |
| CC (Phase B) | 0.25–0.35 | Above recent resistance, room to run |

### DTE (Days to Expiration) Rules

| Parameter | Value | Reason |
|-----------|-------|--------|
| Entry DTE | 30–45 days | Optimal Theta decay zone |
| Exit for Profit | 50% of premium collected | Don't get greedy, redeploy capital |
| Exit for Time | 21 DTE remaining | Close and roll if needed |
| Exit for Loss | When position = 3× premium | The 2:1 stop loss rule |

---

## 4. Manual Trading Guide {#manual-guide}

### If You Want to Place Trades Yourself (Step-by-Step)

This section is for placing trades manually on Alpaca Web or any broker.

#### A. Selling a Cash-Secured Put (Manual)

1. **Check your buying power**: You need enough cash to buy 100 shares at the strike price
   - Example: $165 strike → need $16,500 in cash

2. **Open the options chain** for your chosen stock

3. **Select expiration**: Pick one that's 30–45 days out
   - Look at the calendar. If today is March 1, pick April 4 or April 11 expiration

4. **Find the right strike**:
   - Look at the PUT side
   - Find the option with Delta closest to −0.15 (shown as 0.15 or 15% in some platforms)
   - This strike will be below the current stock price (OTM)

5. **Check the premium**:
   - Look at the "Bid" price — this is what you'll receive
   - Calculate annualized return: (Bid × 100 / Strike × 100) × (365/DTE) × 100
   - If < 15% annualized, skip — not worth the capital tie-up

6. **Check earnings**: Make sure the stock doesn't report earnings before expiration

7. **Place the order**:
   - Action: **Sell to Open**
   - Quantity: Start with 1 contract
   - Price: Use a **Limit order at the Mid-price** (halfway between Bid and Ask)
   - Duration: Day order

8. **Set your alerts**:
   - Stop loss alert: If the put's price reaches 3× what you collected
   - Profit alert: If the put's price drops to 50% of what you collected

9. **Management**:
   - Check once per day (takes 2 minutes)
   - If 50% profit reached → Buy to Close → Start new CSP
   - If 21 DTE → Close the position → Start new CSP
   - If stop loss hit → Close the position → Assess whether to pause

#### B. Selling a Covered Call (Manual — After Assignment)

1. **You now own 100 shares** at the put strike minus premium (your cost basis)

2. **Open the options chain** for the stock you own

3. **Select expiration**: 30–45 days out

4. **Find the right strike**:
   - Look at the CALL side
   - Find the option with Delta closest to 0.30
   - This strike will be above the current stock price
   - **Important**: Ideally above your cost basis (so you profit if called away)

5. **Place the order**:
   - Action: **Sell to Open**
   - Quantity: 1 contract per 100 shares owned
   - Price: Limit at mid-price

6. **Management**: Same as CSPs — exit at 50% profit or 21 DTE

#### C. Manual Trade Tracking Sheet

Record every trade in a spreadsheet:

| Date | Symbol | Type | Strike | DTE | Premium | Cost Basis | Exit Price | P&L | Win/Loss |
|------|--------|------|--------|-----|---------|-----------|-----------|------|----------|
| 3/1 | AAPL | CSP | $165 | 35 | $2.50 | N/A | $0 (expired) | +$250 | WIN |
| 4/5 | AAPL | CSP | $160 | 30 | $2.00 | N/A | $1.00 (50%) | +$100 | WIN |
| 5/5 | AAPL | CSP | $155 | 40 | $3.00 | $152 (assigned) | Assigned | — | PHASE B |
| 5/6 | AAPL | CC | $170 | 35 | $2.50 | $152 | Called away | +$2,050 | WIN |

---

## 5. Automated Bot Guide {#bot-guide}

### How the Bot Works

File: `wheel_bot.py`

The bot runs on a schedule and performs these actions:

```
Every 5 minutes during market hours:
  1. Check existing positions for exit signals
     → 50% profit? → Close
     → 21 DTE remaining? → Close
     → Stop loss hit? → Close
     → Assigned on CSP? → Switch to Phase B (sell covered call)
  
  2. If capital available and < max positions:
     → Scan watchlist for CSP opportunities
     → Filter by: IV Rank > 30, Delta ~0.15, DTE 30-45
     → Pass through Risk Manager (5% rule, sector limits, etc.)
     → Execute at mid-price
```

### Running the Bot

```bash
# Paper trading mode (default)
cd strategy-1-wheel-premium-engine
python wheel_bot.py

# With custom config
python wheel_bot.py --config my_config.json

# Dry run (shows what it would do without placing orders)
python wheel_bot.py --dry-run
```

### Bot Output Example

```
2026-02-27 10:00:00 | INFO     | ========================================
2026-02-27 10:00:00 | INFO     | WHEEL PREMIUM ENGINE v1.0 - Starting
2026-02-27 10:00:00 | INFO     | Mode: PAPER TRADING
2026-02-27 10:00:00 | INFO     | Account Equity: $50,000.00
2026-02-27 10:00:00 | INFO     | Available Capital: $42,500.00
2026-02-27 10:00:00 | INFO     | Open Positions: 2
2026-02-27 10:00:00 | INFO     | ========================================
2026-02-27 10:00:01 | INFO     | Guardian: Checking AAPL CSP ($165 Put) | P&L: +42% | Action: HOLD
2026-02-27 10:00:01 | INFO     | Guardian: Checking AMD CSP ($140 Put) | P&L: +51% | Action: CLOSE (50% target)
2026-02-27 10:00:02 | INFO     | BUY TO CLOSE: AMD260404P00140000 x1 @ $1.25
2026-02-27 10:00:02 | INFO     | Trade closed: P&L = +$125.00
2026-02-27 10:00:03 | INFO     | Hunter: Scanning watchlist for new CSPs...
2026-02-27 10:00:04 | INFO     | Hunter: NVDA — IVR=45, Delta=0.14, Premium=$3.50, Annual=42%
2026-02-27 10:00:04 | INFO     | TRADE APPROVED: NVDA csp | MaxLoss=$500.00
2026-02-27 10:00:05 | INFO     | Mid-price attempt 1/10: SELL NVDA260404P00115000 @ $3.50
2026-02-27 10:00:35 | INFO     | Order FILLED at $3.45
```

---

## 6. Configuration Reference {#configuration}

### config.json

```json
{
    "strategy": "wheel_premium_engine",
    "watchlist": [
        "AAPL", "MSFT", "AMD", "NVDA", "GOOGL",
        "JPM", "KO", "JNJ", "SPY", "QQQ"
    ],
    
    "csp_rules": {
        "target_delta": 0.15,
        "delta_tolerance": 0.05,
        "min_dte": 30,
        "max_dte": 45,
        "min_iv_rank": 30,
        "min_annualized_return_pct": 15,
        "profit_target_pct": 0.50,
        "stop_loss_multiplier": 3.0,
        "max_dte_to_hold": 21
    },
    
    "cc_rules": {
        "target_delta": 0.30,
        "delta_tolerance": 0.05,
        "min_dte": 30,
        "max_dte": 45,
        "sell_above_cost_basis": true,
        "profit_target_pct": 0.50,
        "max_dte_to_hold": 21
    },
    
    "risk": {
        "max_capital_per_position_pct": 0.20,
        "max_total_positions": 5,
        "max_risk_per_trade_pct": 0.05,
        "max_same_sector": 2,
        "earnings_buffer_days": 5
    },
    
    "execution": {
        "use_mid_price": true,
        "mid_price_increment": 0.01,
        "mid_price_max_retries": 10,
        "scan_interval_minutes": 5
    }
}
```

### Configuration Explained

| Parameter | Default | Explanation |
|-----------|---------|-------------|
| `target_delta` | 0.15 | The delta we want for CSPs. Lower = safer but less premium |
| `min_iv_rank` | 30 | Minimum IVR to sell premium. Below 30 = not worth it |
| `min_annualized_return_pct` | 15% | Skip trades with < 15% annualized return |
| `profit_target_pct` | 0.50 | Close at 50% of maximum profit |
| `stop_loss_multiplier` | 3.0 | Close when position = 3× premium collected |
| `max_dte_to_hold` | 21 | Close any position with < 21 DTE remaining |
| `max_capital_per_position_pct` | 0.20 | No single position uses > 20% of account |

---

## 7. Risk Management Rules {#risk-management}

### The Wheel's Built-in Safety

| Risk | How The Wheel Handles It |
|------|--------------------------|
| Stock drops significantly | You bought at a discount (strike - premium). You'd own it anyway. |
| Stock drops to zero | Same risk as owning stock — but your cost basis is lower. Mitigated by stock selection (blue chips only). |
| Opportunity cost | If stock rockets up past your put strike, you miss the move. But you still keep premium. |
| Assignment | Not a risk — it's part of the strategy! You WANT to potentially own these stocks. |

### When to STOP Trading The Wheel

🚨 **Stop trading immediately if:**
- You've hit 3 consecutive losses
- Your account drawdown exceeds 10%
- The VIX is above 35 (extreme fear — wait for it to drop below 25)
- You're "revenge trading" to recover losses

### Position Sizing Worksheet

```
Account Equity:           $50,000
Max Risk Per Trade (5%):  $2,500
Max Positions:            5
Max Per Position (20%):   $10,000

For a $100 stock at $95 strike:
  Collateral needed:      $9,500 (95 × 100)
  ✅ Under 20% limit:     $9,500 < $10,000

  If premium = $2.00:
  Max loss = $9,500 - $200 = $9,300 (theoretical)
  But with stop loss at 3×:
  Realistic max loss = $2.00 × 3 × 100 = $600
  ✅ Under 5% limit:      $600 < $2,500
```

---

## 8. Real Trade Examples {#examples}

### Example 1: Successful CSP (No Assignment)

```
Date: January 15, 2026
Stock: AAPL trading at $182
Action: Sell AAPL Feb 28 $170 Put
Premium: $2.30 ($230 per contract)
Delta: -0.14
IVR: 38
DTE: 44

January 29 (14 days later):
  AAPL at $186, put now worth $1.10
  P&L: +$120 (52% of max profit)
  Action: BUY TO CLOSE at $1.10
  
Net Profit: $230 - $110 = $120 in 14 days
Annualized: ($120 / $17,000) × (365/14) = 18.4% annualized ✅
Capital was tied up for only 14 days, not the full 44.
```

### Example 2: Assignment → Covered Call → Called Away

```
Date: February 1, 2026
Stock: AMD trading at $155
Action: Sell AMD Mar 14 $145 Put
Premium: $3.50 ($350 per contract)
Delta: -0.16
DTE: 41

February 20:
  AMD drops to $140
  At expiration (Mar 14): AMD at $142
  ASSIGNED: Buy 100 shares at $145
  Cost basis: $145 - $3.50 = $141.50

March 15 (Phase B begins):
  AMD at $143
  Action: Sell AMD Apr 25 $155 Call
  Premium: $2.80 ($280 per contract)
  Delta: 0.28
  DTE: 41

April 10 (26 days later):
  AMD rises to $158
  Call now worth $5.50 (ITM)
  At expiration: AMD at $160
  CALLED AWAY: Sell 100 shares at $155
  
Total Profit:
  Put premium:    +$350
  Call premium:   +$280
  Stock profit:   ($155 - $145) × 100 = +$1,000
  Total:          +$1,630 on $14,500 capital over ~2.5 months
  Annualized:     ~54% ✅
```

### Example 3: Stop Loss Triggered (Taking the L)

```
Date: March 1, 2026
Stock: NVDA trading at $130
Action: Sell NVDA Apr 11 $115 Put
Premium: $2.00 ($200 per contract)
Stop Loss: $6.00 (3× premium)

March 15:
  NVDA drops sharply to $112 on bad earnings guidance
  Put now worth $7.50
  STOP LOSS TRIGGERED at $6.00

  Action: BUY TO CLOSE at $6.00
  Loss: $600 - $200 = -$400

  This is painful, but controlled:
  - Without stop loss: loss could have been $1,500+
  - With stop loss: capped at -$400 (2% of $20K account)
  - Account survives to fight another day ✅
```

---

## 9. Common Mistakes to Avoid {#mistakes}

### ❌ Mistake 1: Selling Puts on Stocks You Don't Want to Own
**Why it's bad**: If assigned, you're stuck with a stock you hate.
**Fix**: Only wheel stocks you'd hold for a year.

### ❌ Mistake 2: Ignoring Earnings
**Why it's bad**: Stocks can gap 10-20% on earnings. Your "safe" put becomes ITM overnight.
**Fix**: Close all positions 5+ days before earnings. The bot does this automatically.

### ❌ Mistake 3: Chasing High Premiums
**Why it's bad**: High premium = high IV = the market expects a big move = higher chance you lose.
**Fix**: Stick to IVR 30-60 range. Above 60 is tempting but dangerous unless you know why IV is high.

### ❌ Mistake 4: Not Taking Profits at 50%
**Why it's bad**: Holding to expiration incurs Gamma risk. The last 7 days are volatile.
**Fix**: Close at 50% profit. Redeploy capital into a new trade. Faster turnover = more income.

### ❌ Mistake 5: Too Many Positions in Same Sector
**Why it's bad**: If tech crashes, all your tech CSPs get assigned simultaneously.
**Fix**: Max 2-3 positions per sector. The bot enforces this.

### ❌ Mistake 6: Using Too Much Capital
**Why it's bad**: One bad month wipes out all gains.
**Fix**: Never use more than 20% of account as collateral. Keep 80% as a cushion.

---

## 10. FAQ {#faq}

**Q: What happens if my put gets assigned?**
A: Great! You now own a quality stock at a discount. The bot automatically switches to Phase B (covered calls) to generate more income while you hold the shares.

**Q: What if the stock keeps dropping after I'm assigned?**
A: Continue selling covered calls. Each call premium lowers your cost basis further. As long as the company is fundamentally sound (which is why we only wheel blue chips), the stock will recover.

**Q: How much time does this take?**
A: With the bot: ~15 minutes per week to review. Manually: ~30 minutes per day to check positions and scan for new trades.

**Q: Can I lose money?**
A: Yes. If a stock drops significantly and you don't stop out. That's why we have the 2:1 stop loss and only wheel stocks we'd own. Max loss per trade is capped at 5% of your account.

**Q: What's the minimum account size?**
A: $5,000 lets you wheel stocks under $50. $25,000 is recommended for meaningful income and diversification.

**Q: Should I use margin?**
A: NO. Cash-secured only. Margin amplifies losses and can blow up your account. We're in the business of consistency, not leverage.

**Q: What about taxes?**
A: Options premiums are taxed as short-term capital gains. If you hold assigned stock > 1 year before selling, you get long-term rates. Consult a tax professional.

---

## Next Steps

1. **Paper trade** this strategy for 30+ trades before going live
2. Review the bot code in `wheel_bot.py`
3. Set up your config in `config.json`
4. Start with 1-2 positions and scale up as you gain confidence

*The Wheel isn't flashy. It's boring. And that's exactly why it works.*
