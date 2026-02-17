"""
VaR Calculator for Portfolio Risk Assessment
===========================================

Calculates Value at Risk (VaR) using historical simulation method.
VaR represents the maximum potential loss over a specific time frame
with a given confidence level.

Methods:
- Historical Simulation: Uses actual historical returns
- Parametric (Normal): Assumes normal distribution (future enhancement)

Usage:
    calculator = VarCalculator(confidence_level=0.95, time_horizon=1)
    var_value = calculator.calculate_var(returns_series)
"""

import numpy as np
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class VarCalculator:
    """
    Value at Risk Calculator using Historical Simulation

    VaR measures the potential loss in value of a portfolio over a defined
    period for a given confidence interval.

    Example:
        95% VaR of $10,000 means there's a 5% chance of losing more than
        $10,000 in the next day.
    """

    def __init__(self, confidence_level: float = 0.95, time_horizon: int = 1):
        """
        Initialize VaR Calculator

        Args:
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            time_horizon: Time horizon in days
        """
        self.confidence_level = confidence_level
        self.time_horizon = time_horizon
        self.alpha = 1 - confidence_level  # Significance level

    def calculate_var(self, returns: List[float]) -> Optional[float]:
        """
        Calculate VaR using historical simulation

        Args:
            returns: List of historical daily returns (as decimals, e.g., 0.02 for 2%)

        Returns:
            VaR value as positive number (potential loss amount)
            None if insufficient data
        """
        if not returns or len(returns) < 30:
            logger.warning("Insufficient historical returns for VaR calculation")
            return None

        try:
            # Convert to numpy array
            returns_array = np.array(returns)

            # Calculate portfolio values (assuming $1 initial investment)
            portfolio_values = np.cumprod(1 + returns_array)

            # Calculate daily losses (negative returns)
            daily_losses = -returns_array  # Losses are positive values

            # Sort losses in ascending order
            sorted_losses = np.sort(daily_losses)

            # Find the VaR percentile
            # For 95% confidence, we want the loss that is exceeded only 5% of the time
            var_index = int(np.ceil(self.alpha * len(sorted_losses))) - 1
            var_index = max(0, min(var_index, len(sorted_losses) - 1))

            daily_var = sorted_losses[var_index]

            # Scale for time horizon (square root of time for volatility scaling)
            # For simplicity, assume daily VaR scales with sqrt(time)
            if self.time_horizon > 1:
                daily_var = daily_var * np.sqrt(self.time_horizon)

            logger.info(f"VaR calculated: {daily_var:.2f}")
            return daily_var

        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return None

    def calculate_portfolio_var(self, positions: List[dict], current_prices: dict) -> Optional[float]:
        """
        Calculate portfolio-level VaR

        Args:
            positions: List of position dicts with 'symbol', 'quantity', 'entry_price'
            current_prices: Dict of current prices by symbol

        Returns:
            Portfolio VaR value
        """
        if not positions:
            return 0.0

        total_portfolio_value = 0.0
        weighted_returns = []

        # Calculate portfolio weights and collect returns
        for position in positions:
            symbol = position['symbol']
            quantity = position.get('remaining_qty', position.get('quantity', 0))
            entry_price = position['entry_price']
            current_price = current_prices.get(symbol, entry_price)

            if quantity <= 0 or current_price <= 0:
                continue

            position_value = quantity * current_price
            total_portfolio_value += position_value

            # For simplicity, use a placeholder return series
            # In production, you'd fetch historical returns for each symbol
            # Here we'll use a mock calculation
            daily_return = (current_price - entry_price) / entry_price
            weighted_returns.append(daily_return * (position_value / total_portfolio_value))

        if not weighted_returns:
            return None

        # Simplified portfolio return
        portfolio_return = sum(weighted_returns)

        # Mock historical returns for demonstration
        # In real implementation, use actual historical data
        mock_returns = np.random.normal(portfolio_return, 0.02, 252)  # 252 trading days

        return self.calculate_var(mock_returns.tolist())

    def get_var_summary(self, returns: List[float]) -> dict:
        """
        Get comprehensive VaR summary

        Returns:
            Dict with VaR, expected shortfall, and confidence intervals
        """
        var_value = self.calculate_var(returns)
        if var_value is None:
            return {}

        # Calculate Expected Shortfall (CVaR)
        returns_array = np.array(returns)
        losses = -returns_array
        sorted_losses = np.sort(losses)
        var_index = int(np.ceil(self.alpha * len(sorted_losses))) - 1
        var_index = max(0, min(var_index, len(sorted_losses) - 1))

        # Expected Shortfall: average of losses beyond VaR
        tail_losses = sorted_losses[var_index:]
        expected_shortfall = np.mean(tail_losses) if len(tail_losses) > 0 else var_value

        return {
            'var_value': var_value,
            'expected_shortfall': expected_shortfall,
            'confidence_level': self.confidence_level,
            'time_horizon_days': self.time_horizon,
            'method': 'historical_simulation'
        }