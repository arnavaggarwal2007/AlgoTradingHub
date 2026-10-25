# Future Institutional Enhancement: Stop Loss Fill-Price Anchoring Specification

**Author**: Senior Quantitative Strategist & Risk Architect  
**Target Module**: `PositionManager.execute_buy()` & `PositionManager.calculate_stop_loss()` in `rajat_alpha_v67_single.py`  
**Status**: Documented Architecture for Future Release  

---

## 1. Executive Summary & Problem Definition

In algorithmic swing trading systems, an entry signal is evaluated during an observation window prior to order placement. The initial stop loss (SL) is computed using the price observed at signal generation ($P_{\text{signal}}$):

$$\text{SL}_{\text{initial}} = P_{\text{signal}} - (k \times \text{ATR}_{14})$$

However, in fast-moving, high-conviction breakout setups (such as high-CPS candidates with Bullish Engulfing candles and $>2.0\text{x}$ relative volume), the order executes at an execution price ($P_{\text{fill}}$) that may diverge from $P_{\text{signal}}$ due to:
1. **SOEE Escalation**: Transitioning from Step 1 (passive midpoint) to Step 2 (stepped-up limit: $\text{Mid} + 0.25 \times \text{Spread}$).
2. **Breakout Momentum Slippage**: Tight market order execution when the ask price moves upward before execution.

If the system records $P_{\text{fill}}$ as the entry price in SQLite but retains the pre-calculated $\text{SL}_{\text{initial}}$, the **true dollar risk per share expands**, breaching the trader's predefined portfolio risk budget.

---

## 2. Concrete Numerical Walkthrough

### Scenario: High-RVol Breakout on Symbol `XYZ`

- **Observed Signal Price ($P_{\text{signal}}$)**: **$100.00**
- **14-Day ATR ($\text{ATR}_{14}$)**: **$3.00**
- **Conviction Score**: $4.0$ ($k = 2.0\text{x}$ ATR)
- **Account Equity**: $100,000.00
- **Target Risk**: 0.5% of Equity = **$500.00**

#### Step 1: Pre-Execution Sizing Calculation
$$\Delta \text{SL}_{\text{planned}} = P_{\text{signal}} - \text{SL}_{\text{initial}} = \$100.00 - (\$100.00 - 2.0 \times \$3.00) = \$6.00 \text{ (6.0\% risk distance)}$$
$$\text{Shares} = \frac{\$500.00}{\$6.00} = 83 \text{ shares}$$

#### Step 2: Live Execution Slippage via SOEE Step 2
The order fills at **$101.50** ($+1.5\%$ above signal price).

#### Case A: Current Behavior (Unanchored Stop Loss)
- `entry_price` = **$101.50**
- `stop_loss` = **$94.00** (Stale, anchored to $100.00)
- **Actual Risk Distance per Share**:
  $$\$101.50 - \$94.00 = \$7.50 \text{ per share (7.39\% risk)}$$
- **Total Portfolio Dollar Risk**:
  $$83 \text{ shares} \times \$7.50 = \$622.50$$
- **Deviation**: The trader is risking **$622.50** instead of the budgeted **$500.00** (+24.5% unintended dollar risk expansion).

#### Case B: With Fill-Price Anchoring
- `entry_price` = **$101.50**
- Immediately upon broker fill confirmation, the stop loss is recalculated using $P_{\text{fill}}$:
  $$\text{SL}_{\text{anchored}} = \$101.50 - (2.0 \times \$3.00) = \$95.50$$
- **Actual Risk Distance per Share**:
  $$\$101.50 - \$95.50 = \$6.00 \text{ per share (5.91\% risk)}$$
- **Total Portfolio Dollar Risk**:
  $$83 \text{ shares} \times \$6.00 = \$498.00$$
- **Result**: Portfolio dollar risk strictly matches the budgeted **$500.00** target.

---

## 3. Strategic Trade-Off Analysis

| Strategy Dimension | Unanchored Stop (Technical Pivot) | Fill-Price Anchored Stop (Risk Budget) |
|:---|:---|:---|
| **Primary Philosophy** | Technical swing-low preservation | Strict institutional risk-of-ruin parity |
| **Stop Placement** | Kept at pre-breakout consolidation low | Kept at exact risk distance below execution |
| **Slippage Impact** | Expands dollar loss on losing trades | Maintains constant dollar risk |
| **Noise Stop-Out Risk** | Lower (stop sits slightly further away) | Slightly higher if entry was heavily stepped up |
| **Best Used In** | Low-volatility large-cap trading | High-beta growth / prop firm volatility regimes |

---

## 4. Proposed Implementation Architecture

### Configuration Switch
Add to `config/config.json` under `risk_management`:
```json
{
  "risk_management": {
    "anchor_initial_sl_to_fill_price": true
  }
}
```

### Proposed Code Diff in `PositionManager.execute_buy()`
```python
# Extract actual filled average price from broker
actual_fill_price = float(getattr(filled_order, 'filled_avg_price', None) or current_price)
actual_fill_qty = int(getattr(filled_order, 'filled_qty', None) or shares)

# Optional Fill-Price Anchoring
if self.config.get('risk_management', 'anchor_initial_sl_to_fill_price', False):
    effective_sl = self.calculate_stop_loss(symbol, actual_fill_price, score, df_daily)
    logger.info(f"[{symbol}] Stop loss anchored to actual fill price: ${actual_fill_price:.2f} -> SL: ${effective_sl:.2f}")
else:
    effective_sl = stop_loss

position_id = self.db.add_position(
    symbol=symbol,
    entry_price=actual_fill_price,
    quantity=actual_fill_qty,
    stop_loss=effective_sl,
    score=score,
    pattern=signal_details.get('pattern', 'Unknown'),
    initial_stop_loss=effective_sl,
    rs_score=signal_details.get('rs_score', 50.0),
    cps=signal_details.get('cps'),
    rvol=signal_details.get('rvol'),
    candle_pattern=signal_details.get('candle_pattern')
)
```

---

## 5. Summary Recommendation

This enhancement is fully documented and backwards-compatible. When activated via configuration, it locks down risk budgeting for aggressive or stepped-up order execution profiles.

