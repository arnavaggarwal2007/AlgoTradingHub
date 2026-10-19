# Executive Reporting Scripts (`scripts/reporting/`)

This directory contains publication-grade reporting tools for producing executive presentations, performance summaries, and institutional audit decks.

---

## Available Scripts

| Script | Purpose | Description |
| :--- | :--- | :--- |
| `generate_executive_pdf.py` | **Executive Summary PDF Generator** | Generates a 2-page, high-impact, publication-grade PDF report summarizing the v3.2 architecture, statistical backtest results, capacity constraints, risk controls, and audit verification sign-offs. |

---

## Executive Summary PDF (`generate_executive_pdf.py`)

### Overview
Built using ReportLab with a custom two-pass canvas (`NumberedCanvas`) for running page counts and institutional headers/footers. Designed specifically for fund managers, stakeholders, and technical auditors.

### Content Included in Report:
- **Header**: Document classification, date, version, and repository status.
- **Section 1: Executive Overview & Mandate**: 4-step framework, target win rates, and expected return profile.
- **Section 2: The Four-Step Institutional Protocol**:
  - Step 1: Mathematical Account Mapping
  - Step 2: Shape of the Strategy (Win Rate 77.8%, Profit Factor 3.68, Expectancy +$137.95)
  - Step 3: 10,000-Path Monte Carlo Simulation (90% cumulative pass rate across 4 attempts)
  - Step 4: Live Execution Architecture
- **Section 3: Portfolio Capacity & Capital Allocation**: 15-position concurrency model, 3% per-trade risk, 6% maximum symbol exposure, 90% equity utilization cap.
- **Section 4: Trailing Stop Stepper & Multi-Tier Profit Harvesting Matrix**:
  - Tier 1 (+5% gain) $\to$ Stop raised to -4%
  - Tier 2 (+10% gain) $\to$ Stop raised to break-even (0%)
  - Tier 3 (+15% gain) $\to$ Stop raised to lock in +3%
- **Section 5: 4-Year Capital Growth & 5-Year Historical Performance Simulation**.
- **Section 6: Institutional Sign-Off Matrix**: 31/31 unit tests certified green, zero regressions.

### How to Run:
```bash
python scripts/reporting/generate_executive_pdf.py
```
*Output File*: `docs/Rajat_Alpha_v67_Executive_Summary.pdf`
