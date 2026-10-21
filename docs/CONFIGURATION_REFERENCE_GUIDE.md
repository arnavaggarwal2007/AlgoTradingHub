# Rajat Alpha v67 — Master Configuration Reference Guide

This reference guide is the definitive manual for configuring, tuning, and operating the **Rajat Alpha v67 (Version 3.2)** algorithmic swing trading engine.

Every parameter across [`config/config.json`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/config.json), [`config/selllist.txt`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/selllist.txt), [`config/watchlist.txt`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/watchlist.txt), and [`config/exclusionlist.txt`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/exclusionlist.txt) is documented below with its exact definition, valid values, system action, and performance impact.

---

## 📋 Table of Contents
1. [Configuration Hierarchy & File Roles](#1-configuration-hierarchy--file-roles)
2. [Fast Manual Overrides (`config/selllist.txt`)](#2-fast-manual-overrides-configselllisttxt)
3. [Master Strings & Action Enums Cheat-Sheet](#3-master-strings--action-enums-cheat-sheet)
4. [Master Configuration Dictionary (`config.json`)](#4-master-configuration-dictionary-configjson)
   - [4.1 API & Environment (`api`)](#41-api--environment-api)
   - [4.2 Trading Rules & Universe (`trading_rules`)](#42-trading-rules--universe-trading_rules)
   - [4.3 Smart Order Execution Engine (`order_execution`)](#43-smart-order-execution-engine-order_execution)
   - [4.4 Position Sizing & Allocation (`position_sizing`)](#44-position-sizing--allocation-position_sizing)
   - [4.5 Candle Quality & Rejection Filters (`candle_quality`)](#45-candle-quality--rejection-filters-candle_quality)
   - [4.6 Pullback & Impulse Wave Validation (`pullback_validation`)](#46-pullback--impulse-wave-validation-pullback_validation)
   - [4.7 Candlestick Patterns & Weighting (`pattern_config`)](#47-candlestick-patterns--weighting-pattern_config)
   - [4.8 Strategy Parameters & Gating Thresholds (`strategy_params`)](#48-strategy-parameters--gating-thresholds-strategy_params)
   - [4.9 Risk Management & Stop Loss Stepper (`risk_management`)](#49-risk-management--stop-loss-stepper-risk_management)
   - [4.10 Profit-Taking Ladder & Runner Mode (`profit_taking`)](#410-profit-taking-ladder--runner-mode-profit_taking)
   - [4.11 First-Hour Volatility Guard (`first_hour_guard`)](#411-first-hour-volatility-guard-first_hour_guard)
   - [4.12 Broad Market Regime Filter (`market_regime`)](#412-broad-market-regime-filter-market_regime)
   - [4.13 Institutional Relative Strength Filter (`relative_strength`)](#413-institutional-relative-strength-filter-relative_strength)
5. [Operational Scenario Recipes (How-To)](#5-operational-scenario-recipes-how-to)

---

## 1. Configuration Hierarchy & File Roles

To prevent operational mistakes and ensure maximum system uptime:

| File | Purpose | When to Edit | Risk Level if Edited Live |
| :--- | :--- | :--- | :--- |
| **`config/config.json`** | **Global Architecture & Parameters**: Risk bounds, indicators, timing, API keys, profit tiers. | Setup or deliberate weekend tuning. | **High**: A missing comma or JSON syntax error will crash the bot. |
| **`config/selllist.txt`** | **Fast Manual Live Overrides**: 1-line emergency exits, stop-loss adjustments, TES extensions. | Anytime during market hours. | **Zero**: Simple text format parsed safely line-by-line. |
| **`config/watchlist.txt`** | **Active Scan Universe**: Symbols monitored for buy signals. | Weekly / Monthly as watchlist rotates. | **Zero**: Text file containing one symbol per line. |
| **`config/exclusionlist.txt`**| **Blacklist**: Symbols strictly forbidden from being bought. | As needed (e.g. pending mergers, high-risk earnings). | **Zero**: Text file containing one symbol per line. |

---

## 2. Fast Manual Overrides (`config/selllist.txt`)

Instead of editing `config.json` while the bot is actively running, use [`config/selllist.txt`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/selllist.txt). 

The bot reads this file every 60 seconds. Each non-empty, non-comment line represents an override command targeted to that specific stock.

### Supported Syntax Options:

```text
# 1. Immediate Market Exit: Submits sell order to Alpaca & cleanly closes DB record
AAPL

# 2. Immediate Market Exit with Custom Audit Reason:
CSCO:FORCE_SELL:Earnings de-risk

# 3. Update Stop Loss Immediately: Updates SL in DB for targeted position
MSFT:SL:415.50
OR
MSFT:UPDATE_STOP_LOSS:415.50

# 4. Grant Dynamic TES Extension: Adds +10 days to holding limit
NVDA:TES:10
OR
NVDA:EXTEND_TES:10
```

- **Targeted**: Only affects the symbol you specify; all other positions continue trading normally.
- **Single Execution Guarantee**: The bot records the execution in the `processed_overrides` SQLite table, ensuring it never re-triggers repeatedly.

---

## 3. Master Strings & Action Enums Cheat-Sheet

All action strings and enum parameters are parsed with **case-insensitive normalization** (`.strip().upper()`).

| Enum Category | Canonical String | Accepted Aliases | File & Key Location | Behavior & Action |
| :--- | :--- | :--- | :--- | :--- |
| **Manual Action** | `FORCE_SELL` | `SELL`, `EXIT`, `FORCE_CLOSE`, or just `SYMBOL` | `config/selllist.txt` | Sends market sell to Alpaca, closes SQLite record, marks quantity 0. |
| **Manual Action** | `UPDATE_STOP_LOSS`| `SL`, `STOP_LOSS` | `config/selllist.txt` (`SYM:SL:val`) | Updates `stop_loss` in SQLite DB for that specific stock. |
| **Manual Action** | `EXTEND_TES` | `TES`, `EXTEND_DAYS` | `config/selllist.txt` (`SYM:TES:val`) | Increments `tes_extensions_count` and grants extra days. |
| **Initial SL Mode**| `hybrid_atr` | `HYBRID_ATR`, `ATR_ADAPTIVE` | `config.json` -> `risk_management.stop_loss_mode` | Initial stop calculated as $Entry - (k \times ATR_{14})$, bounded by 5% and 17%. |
| **Initial SL Mode**| `fixed` | `FIXED_PERCENT` | `config.json` -> `risk_management.stop_loss_mode` | Initial stop set strictly to $Entry \times (1 - 0.17)$. |
| **Stepper Mode** | `user_fixed` | `USER_FIXED`, `FIXED_STEPS` | `config.json` -> `risk_management.stepper_mode` | Stepper uses discrete profit tiers (-4% @ 5%, +1% @ 8%, +3% @ 10%, ratchet @ 15%). |
| **Stepper Mode** | `atr_proportional`| `ATR_STEPPER`, `VOLATILITY` | `config.json` -> `risk_management.stepper_mode` | Stepper trails based on proportional units of initial ATR risk. |
| **Stepper Mode** | `adaptive_atr_hybrid`| `ADAPTIVE`, `HYBRID_STEPPER`| `config.json` -> `risk_management.stepper_mode` | High-ATR stocks (>3.5%) use ATR breathing room; low-ATR stocks use fixed milestones. |
| **SL Evaluation** | `daily_close_confirmed`| `CLOSING_BASIS`, `CLOSE` | `config.json` -> `risk_management.stop_loss_evaluation` | Evaluates stop loss strictly at confirmed market close (15:55–16:00 ET). |
| **SL Evaluation** | `intraday_tick` | `TICK`, `REALTIME` | `config.json` -> `risk_management.stop_loss_evaluation` | Evaluates live 1-minute tick (vulnerable to intraday wicks). |
| **Order Execution**| `smart_limit_ladder` | `SOEE`, `SMART_EXECUTION` | `config.json` -> `order_execution.execution_mode` | Uses SOEE Midpoint limit pegging to capture the spread. |
| **Order Execution**| `market` | `MARKET_ORDER` | `config.json` -> `order_execution.execution_mode` | Submits immediate market orders (crosses spread). |
| **Sizing Mode** | `percent_equity` | `PERCENT_CAPITAL` | `config.json` -> `position_sizing.mode` | Allocates a fixed percentage of total equity (e.g. 3% = $3,000). |
| **Sizing Mode** | `fixed_risk_pct` | `RISK_BASED`, `VOLATILITY_RISK` | `config.json` -> `position_sizing.mode` | Risks a fixed dollar percentage (e.g. 0.5% = $500) divided by stop distance. |

---

## 4. Master Configuration Dictionary (`config.json`)

### 4.1 API & Environment (`api`)
```json
"api": {
  "key_id": "YOUR_ALPACA_KEY_ID",
  "secret_key": "YOUR_ALPACA_SECRET_KEY",
  "base_url": "https://paper-api.alpaca.markets"
}
```
- **`key_id`** (`string`): Your Alpaca API Key.
- **`secret_key`** (`string`): Your Alpaca Secret Key.
- **`base_url`** (`string`): Endpoint URL. Use `https://paper-api.alpaca.markets` for paper trading or `https://api.alpaca.markets` for live trading.

---

### 4.2 Trading Rules & Universe (`trading_rules`)
- **`sizing_mode`** (`string`, default: `"capital_pct"`):
  - `"capital_pct"` (Approach 1): Fixed capital percentage per trade (e.g. 3% = $3,000 on $100k equity).
  - `"risk_based"` (Approach 2): Institutional Equal Risk Contribution / Volatility Parity ($500 fixed dollar risk / $(Entry - SL)$ distance), bounded by `max_allocation_per_stock_pct`.
- **`per_trade_pct`** (`float`, default: `0.03`): Percentage of account equity allocated to a single trade when `sizing_mode` is `"capital_pct"` (0.03 = 3% = $3,000 on a $100k account).
- **`risk_per_trade_pct`** (`float`, default: `0.005`): Fractional risk budget per trade when `sizing_mode` is `"risk_based"` (0.005 = 0.5% risk = $500 on $100k account).
- **`fixed_risk_dollars`** (`float`, default: `500.0`): Hard dollar risk budget per trade. If $> 0$, overrides `risk_per_trade_pct` to risk exactly this dollar amount.
- **`max_allocation_per_stock_pct`** (`float`, default: `0.06`): Maximum allowable capital allocation across any single symbol (0.06 = 6% = $6,000 ceiling on a $100k account). Essential institutional guardrail preventing overleveraging on tight-stop setups.
- **`max_equity_utilization_pct`** (`float`, default: `0.90`): Maximum portfolio exposure (90% of total equity). Blocks new buys if exceeded.
- **`capital_conservation_mode`** (`boolean`, default: `false`): When enabled, if portfolio utilization exceeds 70% of max limit, position size or risk allocation is automatically halved.
- **`portfolio_mode`** (`string`, default: `"watchlist_only"`): Options: `"watchlist_only"` or `"all"`.
- **`min_touch_only_score`** (`float`, default: `5.0`): Minimum conviction score required to take a trade that has a moving average touch but no candlestick pattern.

---

### 4.3 Smart Order Execution Engine (`order_execution`)
- **`execution_mode`** (`string`, default: `"smart_limit_ladder"`): Enables SOEE midpoint pegging to eliminate the 0.40%–0.80% jobbing disadvantage.
- **`stage_1_timeout_minutes`** (`integer`, default: `10`): Minutes to leave order pegged at the exact Bid-Ask Midpoint.
- **`stage_1_peg`** (`string`, default: `"midpoint"`): Target price for Stage 1. Options: `"midpoint"`, `"bid"`, `"ask"`.
- **`stage_2_timeout_minutes`** (`integer`, default: `15`): Minutes to leave order with near-touch offset.
- **`stage_2_offset_cents`** (`float`, default: `0.02`): Cent offset closer to near-touch ($0.02) to accelerate fills.
- **`stage_3_marketable_limit`** (`boolean`, default: `true`): Converts order to marketable limit at the Ask at minute 25 to guarantee fill before close.
- **`market_close_cutoff_time`** (`string`, default: `"15:55"`): Cutoff time (ET) to convert all unfilled orders before market close.

---

### 4.4 Position Sizing & Allocation (`position_sizing`)
- **`mode`** (`string`, default: `"percent_equity"`):
  - `"percent_equity"`: Invests a fixed percentage of total capital (e.g. 3% = $3,000).
  - `"fixed_risk_pct"`: Risks a fixed percentage of total capital (e.g. 0.5% = $500 dollar risk) divided by stop distance.
- **`percent_of_equity`** (`float`, default: `0.03`): Allocation fraction for `"percent_equity"` mode (0.03 = 3%).
- **`fixed_amount`** (`float`, default: `5000`): Dollar allocation used when mode is set to fixed dollars.

---

### 4.5 Candle Quality & Rejection Filters (`candle_quality`)
- **`enable_shooting_star_filter`** (`boolean`, default: `true`): **MANDATORY**. Rejects candles with heavy seller distribution wicks.
- **`max_upper_wick_ratio`** (`float`, default: `0.50`): Maximum allowable upper wick as fraction of total candle range (0.50 = 50%).
- **`max_wick_to_body_ratio`** (`float`, default: `2.0`): Rejects candle if upper wick is more than $2\times$ the real body size.

---

### 4.6 Pullback & Impulse Wave Validation (`pullback_validation`)
- **`enable_impulse_validation`** (`boolean`, default: `true`): **MANDATORY**. Enforces that stock was in a genuine markup wave before pulling back.
- **`min_impulse_extension_pct`** (`float`, default: `0.05`): Prior swing high must have been at least **+5.0% above 21 EMA**.
- **`min_pullback_decline_pct`** (`float`, default: `0.03`): Retracement from swing high must be at least **3.0%**.
- **`min_consecutive_lower_closes`** (`integer`, default: `3`): Alternative orderly retracement proof: 3 consecutive lower daily closes.
- **`impulse_lookback_bars`** (`integer`, default: `20`): Daily lookback window to find preceding swing high (20 trading days).

---

### 4.7 Candlestick Patterns & Weighting (`pattern_config`)
```json
"enabled_patterns": {
  "Engulfing": {"enable": true, "score_weight": 1.0, "tier": "A"},
  "Piercing": {"enable": true, "score_weight": 1.0, "tier": "A"},
  "Tweezer": {"enable": true, "score_weight": 0.8, "tier": "B"},
  "Hammer": {"enable": true, "score_weight": 0.8, "tier": "B"},
  "UpsideReversal": {"enable": true, "score_weight": 0.6, "tier": "C"}
}
```
- Each pattern can be individually enabled/disabled (`"enable": true/false`).
- `"score_weight"` dictates how many points the pattern adds to the conviction score (0.6 to 1.0).

---

### 4.8 Strategy Parameters & Gating Thresholds (`strategy_params`)
- **`min_signal_score`** (`float`, default: `4.0`): Minimum composite score required to generate a buy signal (4.0 out of 5.0).
- **`min_listing_days`** (`integer`, default: `200`): Minimum historical bars required (excludes recent IPOs without 200 SMA).
- **`sma_fast`** (`integer`, default: `50`): Fast moving average period (50 SMA).
- **`sma_slow`** (`integer`, default: `200`): Slow moving average period (200 SMA).
- **`ema_trend`** (`integer`, default: `21`): Intermediate momentum trend period (21 EMA).
- **`stalling_range_pct`** (`float`, default: `5.0`): Rejects consolidation if 8-day price range is $< 5.0\%$.
- **`max_gap_pct`** (`float`, default: `0.04`): Extended stock filter: rejects signals if today's open gaps up $> 4.0\%$ above prior close.

---

### 4.9 Risk Management & Stop Loss Stepper (`risk_management`)
- **`stop_loss_mode`** (`string`, default: `"hybrid_atr"`): `"hybrid_atr"` (volatility adaptive) or `"fixed"`.
- **`stepper_mode`** (`string`, default: `"user_fixed"`): Options: `"user_fixed"`, `"atr_proportional"`, or `"adaptive_atr_hybrid"`.
- **`atr_period`** (`integer`, default: `14`): Lookback period for ATR calculation.
- **`atr_multiplier_default`** (`float`, default: `2.0`): ATR multiplier for score 4.0 setups ($2.0\times$ ATR).
- **`atr_multiplier_high_conviction`** (`float`, default: `1.5`): ATR multiplier for score $\ge 5.0$ setups ($1.5\times$ ATR).
- **`max_initial_sl_pct`** (`float`, default: `0.17`): Hard maximum initial stop loss cap (17.0%).
- **`min_initial_sl_pct`** (`float`, default: `0.05`): Hard minimum initial stop loss floor (5.0%).
- **`stepper_stage_1_gain`** (`float`, default: `0.05`): Gain threshold to trigger Stage 1 (+5.0%).
- **`stepper_stage_1_sl_pct`** (`float`, default: `-0.04`): SL moved to **-4.0%** below entry at Stage 1.
- **`stepper_stage_2_gain`** (`float`, default: `0.08`): Gain threshold to trigger Stage 2 (+8.0%).
- **`stepper_stage_2_sl_pct`** (`float`, default: `0.01`): SL moved to **+1.0% above entry price** at Stage 2 (locks in positive exit).
- **`stepper_stage_3_gain`** (`float`, default: `0.10`): Gain threshold to trigger Stage 3 (+10.0%).
- **`stepper_stage_3_sl_pct`** (`float`, default: `0.03`): SL moved to **+3.0% locked profit** at Stage 3.
- **`trailing_ratchet_per_pct`** (`float`, default: `0.01`): When price exceeds Stage 3 by +5% (+15% gain), SL moves to Stage 3 level (+10%) and ratchets +1.0% for every additional +1.0% gain.
- **`stop_loss_evaluation`** (`string`, default: `"daily_close_confirmed"`): Stop loss evaluated at 15:55–16:00 ET based on confirmed close.
- **`max_hold_days`** (`integer`, default: `21`): **GLOBAL HOLDING LIMIT**. Base Time-Based Exit (TES) in trading days for all portfolio stocks.
- **`enable_dynamic_tes_extension`** (`boolean`, default: `true`): Allows +10-day extensions for bases holding $\ge 21$ EMA.
- **`tes_extension_days`** (`integer`, default: `10`): Number of days granted per extension.
- **`max_tes_extensions`** (`integer`, default: `2`): Maximum extensions allowed (2 extensions = 21 + 10 + 10 = 41 days max).

---

### 4.10 Profit-Taking Ladder & Runner Mode (`profit_taking`)
- **`enable_partial_exits`** (`boolean`, default: `true`): Enables multi-tier profit taking.
- **`target_1_pct`** (`float`, default: `0.05`): PT1 profit target (+5.0%).
- **`target_1_qty`** (`float`, default: `0.20`): Sells 20% of original shares at PT1.
- **`target_2_pct`** (`float`, default: `0.10`): PT2 profit target (+10.0%).
- **`target_2_qty`** (`float`, default: `0.25`): Sells 25% of original shares at PT2.
- **`target_3_pct`** (`float`, default: `0.15`): PT3 profit target (+15.0%).
- **`target_3_qty`** (`float`, default: `0.25`): Sells 25% of original shares at PT3.
- **`runner_qty`** (`float`, default: `0.30`): Remaining 30% of position enters **Runner Mode**.
- **`runner_exempt_from_tes`** (`boolean`, default: `true`): Runner positions are permanently exempt from TES holding caps.

---

### 4.11 First-Hour Volatility Guard (`first_hour_guard`)
- **`enable`** (`boolean`, default: `true`): Activates opening morning volatility suppression.
- **`guard_start_time`** (`string`, default: `"09:30"`): Window start time (ET).
- **`guard_end_time`** (`string`, default: `"10:30"`): Window end time (ET).
- **`catastrophic_override_pct`** (`float`, default: `-0.22`): Hard emergency breaker: liquidates immediately if loss reaches -22.0%.
- **`stock_gap_override_pct`** (`float`, default: `-0.10`): Hard emergency breaker: liquidates immediately on -10.0% gap-down.
- **`suppress_sl`** (`boolean`, default: `true`): Suppresses regular stop losses between 09:30–10:30 ET when market open is red.
- **`allow_profit_exits`** (`boolean`, default: `true`): Allows profit-taking limit orders to execute during the morning guard window.

---

### 4.12 Broad Market Regime Filter (`market_regime`)
- **`enable_index_gate`** (`boolean`, default: `true`): Blocks new buy signals if SPY or QQQ is trading below its 50 SMA.
- **`index_symbols`** (`array`, default: `["SPY", "QQQ"]`): Benchmarks evaluated.

---

### 4.13 Institutional Relative Strength Filter (`relative_strength`)
- **`enable`** (`boolean`, default: `false`): Enables IBD-style 0–100 RS Composite filter.
- **`min_rs_rating`** (`float`, default: `40.0`): Minimum RS score required for entry.
- **`rs_score_bonus_points`** (`float`, default: `0.5`): Bonus score awarded to stocks with RS $\ge 70.0$.

---

## 5. Operational Scenario Recipes (How-To)

### Scenario A: How to change the global holding days from 21 to 31 days
1. Open [`config/config.json`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/config.json).
2. Under `"risk_management"`, locate `"max_hold_days": 21`.
3. Change to `"max_hold_days": 31`.
4. Save the file.
- **Impact**: All stocks across the entire portfolio will now be held for 31 days before their first TES evaluation.

### Scenario B: How to customize your 4-Tier Profit Exits (e.g. 5%, 8%, 10%)
1. Open [`config/config.json`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/config.json).
2. Under `"profit_taking"`, update:
   ```json
   "target_1_pct": 0.05,
   "target_1_qty": 0.20,
   "target_2_pct": 0.08,
   "target_2_qty": 0.25,
   "target_3_pct": 0.10,
   "target_3_qty": 0.25,
   "runner_qty": 0.30
   ```
3. Save the file.
- **Impact**: Sells 20% at +5%, 25% at +8%, 25% at +10%, and the remaining 30% enters Runner Mode.

### Scenario C: How to immediately force-sell a specific stock during market hours
1. Open [`config/selllist.txt`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/selllist.txt).
2. Add a new line with the stock symbol:
   ```text
   AAPL
   ```
3. Save the file.
- **Impact**: Within 60 seconds, the bot submits a market sell order to Alpaca for AAPL, cleanly updates `positions.db`, marks quantity to 0, and records the override. No other holdings are touched.

### Scenario D: How to raise a stop loss manually on a specific stock
1. Open [`config/selllist.txt`](file:///C:/Alpaca_Algo2.0/Single_Buy2.0/config/selllist.txt).
2. Add a new line:
   ```text
   MSFT:SL:418.00
   ```
3. Save the file.
- **Impact**: The bot immediately updates MSFT's `stop_loss` in SQLite to $418.00 and logs the update in `audit.log`.

