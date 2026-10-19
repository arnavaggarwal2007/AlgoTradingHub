# Enterprise Features Directory (`enterprise_features/`)

This package provides institutional enterprise modules for advanced portfolio risk modeling and interactive UI dashboards.

---

## Modules

### 1. Risk Management (`enterprise_features/risk_management/`)
- `var_calculator.py`: **Value at Risk (VaR) Engine**. Computes historical simulation VaR and parametric Value at Risk at 95% and 99% confidence levels, providing maximum expected drawdown projections over single-day and multi-day horizons.

### 2. UI Dashboard (`enterprise_features/ui_dashboard/`)
- `app.py`: Flask dashboard service providing real-time portfolio visualization, active risk metrics, VaR analysis, and REST API endpoints.
- `templates/dashboard.html`: Responsive web frontend.
- `test_signals_api.py`: Automated test suite for the dashboard signal API endpoints.

---

## Running the Enterprise Dashboard

To launch the enterprise UI dashboard:
```bash
python enterprise_features/ui_dashboard/app.py
```
By default, the server starts on `http://localhost:5000`.
