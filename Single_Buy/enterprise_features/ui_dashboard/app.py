"""
Flask Dashboard for Trading Performance and Risk Metrics
========================================================

Web-based dashboard to visualize:
- Portfolio positions and P&L
- Trading performance metrics
- VaR calculations
- Signal history and analytics

Run with: python app.py
Access at: http://localhost:5000
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
import json
from datetime import datetime, timedelta
import os
import sys
from datetime import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from enterprise_features.risk_management.var_calculator import VarCalculator
    VAR_AVAILABLE = True
except ImportError:
    print("Warning: VarCalculator not available, VaR features disabled")
    VAR_AVAILABLE = False

app = Flask(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'positions.db')

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/portfolio')
def get_portfolio():
    """Get current portfolio data"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get open positions
    cursor.execute('''
        SELECT * FROM positions
        WHERE status = 'OPEN'
        ORDER BY entry_date DESC
    ''')
    positions = [dict(row) for row in cursor.fetchall()]

    # Calculate portfolio metrics
    total_value = sum(pos.get('quantity', 0) * pos.get('entry_price', 0) for pos in positions)
    total_positions = len(positions)

    conn.close()

    return jsonify({
        'positions': positions,
        'total_value': total_value,
        'total_positions': total_positions
    })

@app.route('/api/performance')
def get_performance():
    """Get performance metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get closed positions for performance analysis
    cursor.execute('''
        SELECT * FROM positions
        WHERE status = 'CLOSED'
        ORDER BY exit_date DESC
    ''')
    closed_positions = [dict(row) for row in cursor.fetchall()]

    # Calculate metrics
    total_trades = len(closed_positions)
    winning_trades = len([p for p in closed_positions if p['profit_loss_pct'] > 0])
    losing_trades = total_trades - winning_trades

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    total_return = sum(p['profit_loss_pct'] for p in closed_positions)
    avg_return = total_return / total_trades if total_trades > 0 else 0

    # Best and worst trades
    best_trade = max(closed_positions, key=lambda x: x['profit_loss_pct']) if closed_positions else None
    worst_trade = min(closed_positions, key=lambda x: x['profit_loss_pct']) if closed_positions else None

    conn.close()

    return jsonify({
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': round(win_rate, 2),
        'avg_return': round(avg_return, 2),
        'best_trade': best_trade,
        'worst_trade': worst_trade
    })

@app.route('/api/var')
def get_var():
    """Get Value at Risk calculation"""
    if not VAR_AVAILABLE:
        return jsonify({
            'var_95': None,
            'summary': None,
            'note': 'VaR calculator not available'
        })

    # Mock returns data - in production, fetch real historical returns
    # For demonstration, using simulated returns
    import numpy as np
    np.random.seed(42)  # For consistent results
    mock_returns = np.random.normal(0.0005, 0.02, 252).tolist()  # 252 trading days

    calculator = VarCalculator(confidence_level=0.95, time_horizon=1)
    var_value = calculator.calculate_var(mock_returns)
    var_summary = calculator.get_var_summary(mock_returns)

    return jsonify({
        'var_95': var_value,
        'summary': var_summary,
        'note': 'Using simulated returns for demonstration'
    })

@app.route('/api/signals')
def get_signals():
    """Get recent valid signals (score > 0)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get recent valid signals only
    cursor.execute('''
        SELECT * FROM signal_history
        WHERE score > 0
        ORDER BY created_at DESC
        LIMIT 50
    ''')
    signals = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({'signals': signals})

@app.route('/api/performance_by_score')
def get_performance_by_score():
    """Get performance grouped by score"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            score,
            COUNT(*) as trades,
            ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
            ROUND(AVG(profit_loss_pct), 2) as avg_pl
        FROM positions
        WHERE status = 'CLOSED'
        GROUP BY score
        ORDER BY score DESC
    ''')
    data = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({'data': data})

@app.route('/api/performance_by_pattern')
def get_performance_by_pattern():
    """Get performance grouped by pattern"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            pattern,
            COUNT(*) as trades,
            ROUND(SUM(CASE WHEN profit_loss_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
            ROUND(AVG(profit_loss_pct), 2) as avg_pl
        FROM positions
        WHERE status = 'CLOSED'
        GROUP BY pattern
        ORDER BY win_rate DESC
    ''')
    data = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({'data': data})

def is_market_open():
    """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, weekdays)"""
    now = datetime.now()

    # Check if it's a weekday (Monday = 0, Sunday = 6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False

    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)

    current_time = now.time()
    return market_open <= current_time <= market_close

@app.route('/api/active_signals')
def get_active_signals():
    """Get top 5 recent active signals during market hours"""
    if not is_market_open():
        return jsonify({
            'signals': [],
            'market_open': False,
            'message': 'Market is currently closed'
        })

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get top 5 recent valid signals during market hours (one per symbol)
    cursor.execute('''
        SELECT * FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY created_at DESC) as rn
            FROM signal_history
            WHERE score > 0
        ) ranked_signals
        WHERE rn = 1
        ORDER BY created_at DESC
        LIMIT 5
    ''')
    signals = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'signals': signals,
        'market_open': True,
        'message': 'Market is open - showing active signals'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)