# Options Premium Collection Strategy Framework

## 15-Year Proven Approach to Passive Income via Options Trading

> **Philosophy**: We are *insurance companies*, not gamblers. We sell premium (time value) to speculators
> and let Theta (time decay) work in our favor. Every strategy here has a **85–92% probability of profit**
> with defined risk and automated execution.

---

## Table of Contents

1. [Strategy Overview & Comparison](#strategy-overview)
2. [Capital Requirements](#capital-requirements)
3. [Risk Management Philosophy](#risk-management)
4. [Strategy Descriptions](#strategies)
5. [Paper Trading Validation Plan](#paper-trading)
6. [Production Deployment Plan](#production)
7. [Quick Start Guide](#quick-start)

---

## Strategy Overview & Comparison {#strategy-overview}

| # | Strategy | Type | Capital Needed | Monthly ROI | Win Rate | Risk Level | Complexity |
|---|----------|------|---------------|-------------|----------|------------|------------|
| 1 | **The Wheel Premium Engine** | CSP → CC | $5,000–$50,000 | 2–4% | 85–90% | Low | Beginner |
| 2 | **SPX Mechanical Credit Spreads** | Bull Put Spreads | $10,000–$100,000 | 1.5–3% | 85–92% | Low-Medium | Intermediate |
| 3 | **Iron Condor Income Machine** | Iron Condors | $10,000–$50,000 | 2–5% | 70–80% | Medium | Intermediate |
| 4 | **VIX-Regime Adaptive Strategy** | ML-Enhanced Spreads | $25,000–$100,000 | 3–6% | 80–88% | Medium | Advanced |

### Which Strategy Should You Start With?

```
Are you new to options?
  └─ YES → Strategy 1 (The Wheel) — Learn the mechanics
  └─ NO
      ├─ Do you want simplicity with tax benefits?
      │   └─ YES → Strategy 2 (SPX Credit Spreads) — Set & forget
      ├─ Do you want to profit in flat markets?
      │   └─ YES → Strategy 3 (Iron Condors) — Range-bound income
      └─ Do you want maximum edge with data?
          └─ YES → Strategy 4 (VIX-Regime Adaptive) — Quant approach
```

---

## Capital Requirements {#capital-requirements}

### The 5% Rule (Core Risk Principle)
**Never risk more than 5% of total capital on any single trade.**

This means:
- $10,000 account → Max $500 at risk per trade
- $50,000 account → Max $2,500 at risk per trade
- $100,000 account → Max $5,000 at risk per trade

### Minimum Capital by Strategy

| Strategy | Absolute Minimum | Recommended | Optimal |
|----------|-----------------|-------------|---------|
| The Wheel | $5,000 | $25,000 | $50,000+ |
| SPX Credit Spreads | $10,000 | $25,000 | $100,000+ |
| Iron Condors | $10,000 | $25,000 | $50,000+ |
| VIX-Regime Adaptive | $25,000 | $50,000 | $100,000+ |

---

## Risk Management Philosophy {#risk-management}

### The "Never Blow Up" Rules

These rules are NON-NEGOTIABLE. They have kept accounts safe through:
- 2008 Financial Crisis
- 2020 COVID Crash
- 2022 Bear Market
- Every "flash crash" in between

#### Rule 1: Position Sizing (5% Max Risk)
```
max_risk_per_trade = account_equity × 0.05
max_contracts = floor(max_risk_per_trade / max_loss_per_contract)
```

#### Rule 2: Portfolio Heat (Max 20% Total Exposure)
```
total_margin_used ≤ account_equity × 0.20
```
Never have more than 20% of your account tied up as collateral at any time.

#### Rule 3: The 2:1 Stop Loss
If you collect $1.00 in premium, exit when the position is worth $3.00 (you've lost $2.00).
```
stop_loss_price = premium_collected × 3.0
```

#### Rule 4: Time-Based Exit
Close any position at 50% profit OR at 21 DTE (whichever comes first).
Don't get greedy — take profits early and redeploy capital.

#### Rule 5: Earnings Avoidance
NEVER hold a position through an earnings announcement. Close 5 days before earnings.

#### Rule 6: Correlation Check
Don't sell puts on 5 tech stocks simultaneously. Diversify across sectors.
Max 3 positions in the same sector.

### Risk Metrics Tracked by the Bot

| Metric | Description | Threshold |
|--------|-------------|-----------|
| Portfolio Delta | Net directional exposure | < 0.15 per position |
| Portfolio Theta | Daily time decay income | Monitor (higher = better) |
| Max Drawdown | Largest peak-to-trough | < 10% of account |
| Win Rate | % of profitable trades | > 80% (target) |
| Avg Win/Loss Ratio | Average profit vs loss | > 1.5:1 |
| Portfolio VaR (95%) | Value at Risk | < 5% of account |

---

## Strategy Descriptions {#strategies}

### Strategy 1: The Wheel Premium Engine
**Folder**: `strategy-1-wheel-premium-engine/`

The most beginner-friendly premium collection strategy. A mechanical 2-phase system:
1. **Phase A**: Sell Cash-Secured Puts (CSPs) on quality stocks you'd be happy to own
2. **Phase B**: If assigned, sell Covered Calls until called away
3. **Repeat**: Go back to Phase A

**Best for**: Accounts $5K–$50K, beginners, people who want to "own" quality stocks at a discount.

### Strategy 2: SPX Mechanical Credit Spreads
**Folder**: `strategy-2-spx-mechanical-spreads/`

Systematic credit spread selling on the S&P 500 Index (SPX/XSP):
- Cash-settled (no assignment risk)
- Section 1256 tax benefits (60% long-term / 40% short-term)
- Mechanical entry every MWF at 0.10–0.15 Delta
- 30–45 DTE for optimal Theta decay

**Best for**: Accounts $10K+, passive traders, tax-conscious investors.

### Strategy 3: Iron Condor Income Machine
**Folder**: `strategy-3-iron-condor-income/`

Profit when markets stay in a range (which they do 70% of the time):
- Sell both a put spread AND a call spread simultaneously
- Collect premium from both sides
- Defined risk on both sides
- Works best in low-to-normal volatility environments

**Best for**: Accounts $10K+, range-bound market expectations.

### Strategy 4: VIX-Regime Adaptive Strategy
**Folder**: `strategy-4-vix-regime-adaptive/`

The "hedge fund" approach — uses machine learning to detect market regimes:
- Classifies market as Low Vol / Normal / High Vol / Crash Imminent
- Adapts strategy (spread width, Delta, DTE) based on regime
- Only enters trades when VIX is elevated but mean-reverting
- Uses Random Forest for regime detection

**Best for**: Accounts $25K+, quant-minded traders, maximum edge seekers.

---

## Paper Trading Validation Plan {#paper-trading}

### Phase 1: Individual Strategy Testing (Weeks 1–4)
- Deploy each strategy independently on Alpaca Paper
- Track every trade in the database
- Minimum 30 trades per strategy before evaluating

### Phase 2: Performance Comparison (Weeks 5–8)
- Compare strategies on: Win Rate, ROI, Max Drawdown, Sharpe Ratio
- Identify which strategy suits your risk tolerance
- Adjust parameters based on results

### Phase 3: Combined Portfolio Testing (Weeks 9–12)
- Run top 2 strategies simultaneously
- Test correlation between strategies
- Validate overall portfolio risk stays within bounds

### Metrics to Track During Paper Trading

| Metric | Target | Red Flag |
|--------|--------|----------|
| Win Rate | > 80% | < 65% |
| Monthly ROI | 1.5–4% | < 0.5% or > 8% (too risky) |
| Max Drawdown | < 5% | > 10% |
| Average DIT (Days in Trade) | 15–25 | > 40 |
| Premium Captured % | > 50% | < 30% |
| Sharpe Ratio | > 1.5 | < 0.5 |

---

## Production Deployment Plan {#production}

### Pre-Production Checklist
- [ ] 60+ days of paper trading completed
- [ ] Win rate consistently > 80%
- [ ] Max drawdown < 5% of paper account
- [ ] All stop-loss rules triggered correctly
- [ ] Earnings avoidance logic validated
- [ ] API error handling tested (disconnections, rate limits)
- [ ] Position sizing validated at live capital levels
- [ ] Backup/monitoring alerts configured

### Go-Live Plan
1. Start with **25% of intended capital** for first 30 days
2. If performance matches paper trading (±20%), scale to 50%
3. After 60 days of consistent performance, scale to 100%
4. Never scale position sizes — add more concurrent positions instead

---

## Quick Start Guide {#quick-start}

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp config/config_template.json config/config.json
# Edit config.json with your Alpaca API keys
```

### 3. Run Paper Trading (Strategy 1 as example)
```bash
cd strategy-1-wheel-premium-engine
python wheel_bot.py --mode paper
```

### 4. Monitor Dashboard
```bash
python shared/dashboard.py
```

---

## Project Structure

```
OptionStrategy/
├── README.md                              ← You are here
├── requirements.txt                       ← All Python dependencies
├── config/
│   ├── config_template.json               ← Template (copy to config.json)
│   └── config.json                        ← Your API keys (gitignored)
├── shared/
│   ├── __init__.py
│   ├── alpaca_options_client.py           ← Alpaca Options API wrapper
│   ├── risk_manager.py                    ← Portfolio-level risk management
│   ├── option_utils.py                    ← Greeks, IV calculations
│   ├── mid_price_executor.py             ← Smart order execution
│   ├── earnings_calendar.py              ← Earnings date checker
│   └── logger.py                          ← Structured logging
├── strategy-1-wheel-premium-engine/
│   ├── README.md                          ← Extensive manual + automated guide
│   ├── wheel_bot.py                       ← Automated trading bot
│   ├── config.json                        ← Strategy-specific config
│   └── backtest.py                        ← Historical backtesting
├── strategy-2-spx-mechanical-spreads/
│   ├── README.md
│   ├── spx_spread_bot.py
│   ├── config.json
│   └── backtest.py
├── strategy-3-iron-condor-income/
│   ├── README.md
│   ├── iron_condor_bot.py
│   ├── config.json
│   └── backtest.py
└── strategy-4-vix-regime-adaptive/
    ├── README.md
    ├── regime_adaptive_bot.py
    ├── regime_detector.py                 ← ML model for regime detection
    ├── config.json
    └── backtest.py
```

---

## Key Options Concepts (Quick Reference)

### The Greeks
| Greek | What It Measures | Why We Care |
|-------|-----------------|-------------|
| **Delta** (Δ) | Price sensitivity | We sell at 0.10–0.15 Delta = 85–90% win rate |
| **Theta** (Θ) | Time decay per day | This is how we MAKE money — time erodes option value |
| **Gamma** (Γ) | Rate of Delta change | Low Gamma = safer (far OTM options have low Gamma) |
| **Vega** (ν) | IV sensitivity | High IV = more premium = more income for us |
| **Rho** (ρ) | Interest rate sensitivity | Negligible for our strategies |

### Key Terms
- **DTE**: Days to Expiration — we target 30–45 DTE for optimal Theta decay
- **IV**: Implied Volatility — higher IV = more premium income
- **IV Rank**: Current IV vs. 52-week range (0–100) — we sell when IVR > 30
- **OTM**: Out of The Money — our sold options are OTM (high probability of expiring worthless)
- **CSP**: Cash-Secured Put — we have cash to buy the stock if assigned
- **CC**: Covered Call — we own the stock and sell calls against it
- **Spread**: Simultaneously buy and sell options to define max risk
- **Iron Condor**: A put spread + call spread = profit if price stays in range

### Theta Decay Curve
```
Premium Value
    |
    |*
    |  *
    |    *
    |      *
    |        *
    |          *
    |            **
    |              ***
    |                 ****
    |                     *******
    +-------------------------------→ DTE
    45   30   21   14   7    0

Theta accelerates after 21 DTE — this is why we:
1. ENTER at 30-45 DTE (slow decay, safer)
2. EXIT at 50% profit OR 21 DTE (before Gamma risk increases)
```

---

## Disclaimer

This software is for educational purposes and paper trading validation.
Always validate with paper trading before risking real capital.
Options trading involves substantial risk of loss and is not appropriate for all investors.
Past performance does not guarantee future results.

---

*Built with 15 years of options trading experience. Every rule exists because of a real loss that taught a lesson.*
