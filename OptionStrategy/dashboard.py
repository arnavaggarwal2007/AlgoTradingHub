"""
================================================================================
PROFESSIONAL P&L DASHBOARD — Options Strategy Performance Visualization
================================================================================

Flask + Plotly web dashboard providing:
- Real-time P&L by strategy and aggregate
- Equity curves with drawdown overlay
- Market regime map with strategy performance
- Position heat map (exposure by sector/strategy)
- Risk gauge (portfolio risk grade)
- Backtest results comparison
- Stock scanner results table
- Position sizing calculator

Run:
    python dashboard.py                   # Start on port 5050
    python dashboard.py --port 8080       # Custom port

================================================================================
"""

import os
import sys
import json
import glob
import math
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from flask import Flask, render_template_string, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ──────────────────────────────────────────────────────────────
# Data Loaders
# ──────────────────────────────────────────────────────────────

def load_backtest_summary() -> List[Dict]:
    """Load backtest summary JSON."""
    path = os.path.join(BASE_DIR, 'backtest_results', 'summary.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def load_equity_curves() -> Dict[str, pd.DataFrame]:
    """Load all equity curve CSVs."""
    curves = {}
    pattern = os.path.join(BASE_DIR, 'backtest_results', '*_equity_curve.csv')
    for path in glob.glob(pattern):
        name = os.path.basename(path).replace('_equity_curve.csv', '')
        df = pd.read_csv(path)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        curves[name] = df
    return curves


def load_trade_history() -> Dict[str, pd.DataFrame]:
    """Load trade history CSVs."""
    trades = {}
    pattern = os.path.join(BASE_DIR, 'backtest_results', '*_trades.csv')
    for path in glob.glob(pattern):
        name = os.path.basename(path).replace('_trades.csv', '')
        df = pd.read_csv(path)
        trades[name] = df
    return trades


def load_scan_results() -> Optional[pd.DataFrame]:
    """Load most recent scan results."""
    pattern = os.path.join(BASE_DIR, 'scan_results', 'scan_*.csv')
    files = sorted(glob.glob(pattern))
    if files:
        return pd.read_csv(files[-1])
    return None


# ──────────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────────

@app.route('/api/summary')
def api_summary():
    data = load_backtest_summary()
    return jsonify(data)


@app.route('/api/equity/<strategy>')
def api_equity(strategy):
    curves = load_equity_curves()
    if strategy in curves:
        df = curves[strategy]
        return jsonify({
            'dates': df['date'].astype(str).tolist() if 'date' in df.columns else [],
            'equity': df['equity'].tolist() if 'equity' in df.columns else [],
            'cash': df['cash'].tolist() if 'cash' in df.columns else [],
        })
    return jsonify({'dates': [], 'equity': [], 'cash': []})


@app.route('/api/trades/<strategy>')
def api_trades(strategy):
    all_trades = load_trade_history()
    if strategy in all_trades:
        df = all_trades[strategy]
        return jsonify(df.head(200).to_dict(orient='records'))
    return jsonify([])


@app.route('/api/scanner')
def api_scanner():
    df = load_scan_results()
    if df is not None:
        return jsonify(df.head(30).to_dict(orient='records'))
    return jsonify([])


@app.route('/api/risk')
def api_risk():
    summary = load_backtest_summary()
    risk = {
        'strategies': [],
        'total_pnl': 0,
        'avg_sharpe': 0,
        'worst_drawdown': 0,
    }
    sharpes = []
    for s in summary:
        risk['strategies'].append({
            'name': s.get('strategy', ''),
            'pnl': s.get('total_pnl', 0),
            'win_rate': s.get('win_rate', 0),
            'drawdown': s.get('max_drawdown_pct', 0),
            'sharpe': s.get('sharpe_ratio', 0),
        })
        risk['total_pnl'] += s.get('total_pnl', 0)
        sharpes.append(s.get('sharpe_ratio', 0))
        risk['worst_drawdown'] = min(risk['worst_drawdown'], s.get('max_drawdown_pct', 0))

    risk['avg_sharpe'] = round(np.mean(sharpes), 3) if sharpes else 0
    risk['total_pnl'] = round(risk['total_pnl'], 2)
    return jsonify(risk)


# ──────────────────────────────────────────────────────────────
# Main Dashboard HTML (Single-page with Plotly.js + Charts)
# ──────────────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Options Strategy Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #1c2128;
            --border: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-blue: #58a6ff;
            --accent-orange: #d29922;
            --accent-purple: #bc8cff;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header h1 {
            font-size: 20px;
            font-weight: 600;
            color: var(--accent-blue);
        }

        .header .status {
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .header .status .live {
            color: var(--accent-green);
            font-weight: 600;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }

        /* KPI Cards Row */
        .kpi-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }

        .kpi-card .label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .kpi-card .value {
            font-size: 28px;
            font-weight: 700;
        }

        .kpi-card .sub {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .positive { color: var(--accent-green); }
        .negative { color: var(--accent-red); }
        .neutral { color: var(--accent-blue); }

        /* Chart grid */
        .chart-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 24px;
        }

        .chart-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }

        .chart-card.full-width {
            grid-column: 1 / -1;
        }

        .chart-card h3 {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Strategy comparison table */
        .table-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        th {
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid var(--border);
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }

        td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
        }

        tr:hover { background: rgba(88, 166, 255, 0.05); }

        /* Risk gauge */
        .risk-gauge {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .gauge-letter {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 700;
        }

        .grade-A { background: #1a4d2e; color: var(--accent-green); }
        .grade-B { background: #2d3a1a; color: #9be65a; }
        .grade-C { background: #4d3a1a; color: var(--accent-orange); }
        .grade-D { background: #4d1a1a; color: var(--accent-red); }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .tab {
            padding: 8px 16px;
            cursor: pointer;
            border: none;
            background: none;
            color: var(--text-secondary);
            font-size: 14px;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab:hover { color: var(--text-primary); }
        .tab.active {
            color: var(--accent-blue);
            border-bottom-color: var(--accent-blue);
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Scanner table */
        .scanner-table td { font-size: 13px; }
        .score-bar {
            height: 6px;
            border-radius: 3px;
            background: var(--border);
            min-width: 60px;
        }
        .score-fill {
            height: 100%;
            border-radius: 3px;
            background: var(--accent-blue);
        }

        @media (max-width: 900px) {
            .chart-grid { grid-template-columns: 1fr; }
            .kpi-row { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>&#x1F4C8; Options Strategy Dashboard</h1>
        <div class="status">
            <span>Last Updated: <span id="lastUpdate">Loading...</span></span>
            <span class="live">● PAPER TRADING</span>
        </div>
    </div>

    <div class="container">
        <!-- KPI Cards -->
        <div class="kpi-row" id="kpiRow">
            <div class="kpi-card"><div class="label">Total P&L</div><div class="value" id="kpiPnl">--</div><div class="sub" id="kpiPnlSub"></div></div>
            <div class="kpi-card"><div class="label">Win Rate</div><div class="value" id="kpiWinRate">--</div><div class="sub" id="kpiWinSub"></div></div>
            <div class="kpi-card"><div class="label">Sharpe Ratio</div><div class="value neutral" id="kpiSharpe">--</div><div class="sub">Risk-adjusted return</div></div>
            <div class="kpi-card"><div class="label">Max Drawdown</div><div class="value" id="kpiDD">--</div><div class="sub">Worst peak-to-trough</div></div>
            <div class="kpi-card"><div class="label">Total Trades</div><div class="value neutral" id="kpiTrades">--</div><div class="sub" id="kpiTradesSub"></div></div>
            <div class="kpi-card"><div class="label">Risk Grade</div><div class="value" id="kpiGrade">--</div><div class="sub" id="kpiGradeSub"></div></div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="switchTab('overview')">Overview</button>
            <button class="tab" onclick="switchTab('strategies')">Strategy Detail</button>
            <button class="tab" onclick="switchTab('trades')">Trade Log</button>
            <button class="tab" onclick="switchTab('scanner')">Stock Scanner</button>
            <button class="tab" onclick="switchTab('risk')">Risk Analysis</button>
        </div>

        <!-- OVERVIEW TAB -->
        <div class="tab-content active" id="tab-overview">
            <div class="chart-grid">
                <div class="chart-card full-width">
                    <h3>Equity Curves</h3>
                    <div id="equityChart" style="height:400px;"></div>
                </div>
                <div class="chart-card">
                    <h3>P&L by Strategy</h3>
                    <div id="pnlBarChart" style="height:300px;"></div>
                </div>
                <div class="chart-card">
                    <h3>P&L by Market Condition</h3>
                    <div id="conditionChart" style="height:300px;"></div>
                </div>
            </div>

            <!-- Strategy Comparison Table -->
            <div class="table-card">
                <h3 style="font-size:14px; color:var(--text-secondary); margin-bottom:12px;">STRATEGY COMPARISON</h3>
                <table id="strategyTable">
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>Trades</th>
                            <th>Win Rate</th>
                            <th>Total P&L</th>
                            <th>Avg Trade</th>
                            <th>Max DD</th>
                            <th>Sharpe</th>
                            <th>Ann. Return</th>
                        </tr>
                    </thead>
                    <tbody id="strategyTableBody"></tbody>
                </table>
            </div>
        </div>

        <!-- STRATEGY DETAIL TAB -->
        <div class="tab-content" id="tab-strategies">
            <div class="chart-grid">
                <div class="chart-card full-width">
                    <h3>Individual Strategy Equity Curve</h3>
                    <select id="strategySelect" onchange="loadStrategyDetail()" style="background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border);padding:6px 12px;border-radius:4px;margin-bottom:12px;">
                        <option value="wheel">Wheel (CSP)</option>
                        <option value="spx_spreads">SPX Bull Put Spreads</option>
                        <option value="iron_condors">Iron Condors</option>
                        <option value="regime_adaptive">VIX-Regime Adaptive</option>
                    </select>
                    <div id="singleEquityChart" style="height:350px;"></div>
                </div>
                <div class="chart-card">
                    <h3>Exit Reason Distribution</h3>
                    <div id="exitReasonChart" style="height:300px;"></div>
                </div>
                <div class="chart-card">
                    <h3>P&L Distribution</h3>
                    <div id="pnlDistChart" style="height:300px;"></div>
                </div>
            </div>
        </div>

        <!-- TRADE LOG TAB -->
        <div class="tab-content" id="tab-trades">
            <div class="table-card">
                <h3 style="font-size:14px; color:var(--text-secondary); margin-bottom:12px;">RECENT TRADES</h3>
                <select id="tradeStrategySelect" onchange="loadTradeLog()" style="background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border);padding:6px 12px;border-radius:4px;margin-bottom:12px;">
                    <option value="wheel">Wheel</option>
                    <option value="spx_spreads">SPX Spreads</option>
                    <option value="iron_condors">Iron Condors</option>
                    <option value="regime_adaptive">Regime Adaptive</option>
                </select>
                <table>
                    <thead>
                        <tr>
                            <th>Entry Date</th>
                            <th>Symbol</th>
                            <th>P&L</th>
                            <th>Exit Reason</th>
                            <th>VIX</th>
                            <th>Market</th>
                        </tr>
                    </thead>
                    <tbody id="tradeTableBody"></tbody>
                </table>
            </div>
        </div>

        <!-- SCANNER TAB -->
        <div class="tab-content" id="tab-scanner">
            <div class="table-card">
                <h3 style="font-size:14px; color:var(--text-secondary); margin-bottom:12px;">STOCK SCANNER RESULTS</h3>
                <table class="scanner-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Price</th>
                            <th>IV Rank</th>
                            <th>ATR%</th>
                            <th>Trend</th>
                            <th>RSI</th>
                            <th>Sector</th>
                            <th>Wheel</th>
                            <th>Spread</th>
                            <th>Condor</th>
                            <th>Composite</th>
                        </tr>
                    </thead>
                    <tbody id="scannerTableBody"></tbody>
                </table>
            </div>
        </div>

        <!-- RISK ANALYSIS TAB -->
        <div class="tab-content" id="tab-risk">
            <div class="chart-grid">
                <div class="chart-card">
                    <h3>Risk Metrics</h3>
                    <div id="riskMetrics" style="padding:16px;">
                        <div class="risk-gauge">
                            <div class="gauge-letter grade-B" id="riskGaugeLetter">B</div>
                            <div>
                                <div style="font-weight:600;" id="riskGradeText">Moderate Risk</div>
                                <div style="font-size:12px;color:var(--text-secondary);" id="riskGradeDesc">Portfolio within expected parameters</div>
                            </div>
                        </div>
                        <div style="margin-top:24px;" id="riskDetailsList"></div>
                    </div>
                </div>
                <div class="chart-card">
                    <h3>Drawdown Analysis</h3>
                    <div id="drawdownChart" style="height:300px;"></div>
                </div>
                <div class="chart-card full-width">
                    <h3>Win Rate vs Sharpe by Strategy</h3>
                    <div id="winRateSharpeChart" style="height:300px;"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const plotLayout = {
            paper_bgcolor: '#1c2128',
            plot_bgcolor: '#1c2128',
            font: { color: '#8b949e', size: 12 },
            margin: { l: 50, r: 20, t: 10, b: 40 },
            xaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d' },
            yaxis: { gridcolor: '#30363d', zerolinecolor: '#30363d' },
            legend: { bgcolor: 'transparent', font: { color: '#e6edf3' } },
            showlegend: true,
        };

        const colors = ['#58a6ff', '#3fb950', '#d29922', '#bc8cff', '#f85149'];

        // Tab switching
        function switchTab(name) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            event.target.classList.add('active');

            if (name === 'strategies') loadStrategyDetail();
            if (name === 'trades') loadTradeLog();
            if (name === 'scanner') loadScanner();
            if (name === 'risk') loadRiskAnalysis();
        }

        // Load overview data
        async function loadOverview() {
            document.getElementById('lastUpdate').textContent = new Date().toLocaleString();

            const resp = await fetch('/api/summary');
            const data = await resp.json();

            if (!data.length) {
                document.getElementById('kpiPnl').textContent = 'No Data';
                document.getElementById('kpiPnl').className = 'value neutral';
                return;
            }

            // KPIs
            const totalPnl = data.reduce((sum, s) => sum + (s.total_pnl || 0), 0);
            const avgWinRate = data.reduce((sum, s) => sum + (s.win_rate || 0), 0) / data.length;
            const avgSharpe = data.reduce((sum, s) => sum + (s.sharpe_ratio || 0), 0) / data.length;
            const worstDD = Math.min(...data.map(s => s.max_drawdown_pct || 0));
            const totalTrades = data.reduce((sum, s) => sum + (s.total_trades || 0), 0);

            document.getElementById('kpiPnl').textContent = '$' + totalPnl.toLocaleString(undefined, {minimumFractionDigits: 2});
            document.getElementById('kpiPnl').className = 'value ' + (totalPnl >= 0 ? 'positive' : 'negative');
            document.getElementById('kpiPnlSub').textContent = `Across ${data.length} strategies`;

            document.getElementById('kpiWinRate').textContent = avgWinRate.toFixed(1) + '%';
            document.getElementById('kpiWinRate').className = 'value ' + (avgWinRate >= 60 ? 'positive' : avgWinRate >= 50 ? 'neutral' : 'negative');
            document.getElementById('kpiWinSub').textContent = 'Average across strategies';

            document.getElementById('kpiSharpe').textContent = avgSharpe.toFixed(3);
            document.getElementById('kpiDD').textContent = worstDD.toFixed(2) + '%';
            document.getElementById('kpiDD').className = 'value ' + (worstDD > -10 ? 'positive' : worstDD > -20 ? 'neutral' : 'negative');

            document.getElementById('kpiTrades').textContent = totalTrades;
            document.getElementById('kpiTradesSub').textContent = 'Backtest period';

            // Risk grade
            let grade = 'B';
            if (avgSharpe > 1 && worstDD > -10) grade = 'A';
            else if (avgSharpe > 0.5 && worstDD > -15) grade = 'B';
            else if (avgSharpe > 0 && worstDD > -25) grade = 'C';
            else grade = 'D';

            const gradeEl = document.getElementById('kpiGrade');
            gradeEl.textContent = grade;
            gradeEl.className = 'value ' + (grade === 'A' ? 'positive' : grade === 'B' ? 'neutral' : 'negative');
            document.getElementById('kpiGradeSub').textContent = {A:'Low Risk',B:'Moderate',C:'Elevated',D:'High Risk'}[grade];

            // Strategy comparison table
            let tableHtml = '';
            data.forEach(s => {
                const pnlClass = (s.total_pnl || 0) >= 0 ? 'positive' : 'negative';
                tableHtml += `<tr>
                    <td style="font-weight:600">${s.strategy || ''}</td>
                    <td>${s.total_trades || 0}</td>
                    <td class="${(s.win_rate||0)>=60?'positive':'neutral'}">${(s.win_rate||0).toFixed(1)}%</td>
                    <td class="${pnlClass}">$${(s.total_pnl||0).toLocaleString(undefined,{minimumFractionDigits:2})}</td>
                    <td class="${(s.avg_trade_pnl||0)>=0?'positive':'negative'}">$${(s.avg_trade_pnl||0).toFixed(2)}</td>
                    <td class="${(s.max_drawdown_pct||0)>-15?'positive':'negative'}">${(s.max_drawdown_pct||0).toFixed(2)}%</td>
                    <td>${(s.sharpe_ratio||0).toFixed(3)}</td>
                    <td class="${(s.annualized_return_pct||0)>=0?'positive':'negative'}">${(s.annualized_return_pct||0).toFixed(2)}%</td>
                </tr>`;
            });
            document.getElementById('strategyTableBody').innerHTML = tableHtml;

            // P&L bar chart
            Plotly.newPlot('pnlBarChart', [{
                x: data.map(s => s.strategy),
                y: data.map(s => s.total_pnl || 0),
                type: 'bar',
                marker: { color: data.map(s => (s.total_pnl||0) >= 0 ? '#3fb950' : '#f85149') },
            }], {...plotLayout, xaxis: {...plotLayout.xaxis, tickangle: -25}, showlegend: false}, {responsive: true});

            // Market condition chart
            const conditions = ['uptrend', 'sideways', 'downtrend', 'choppy'];
            const condTraces = data.map((s, i) => ({
                x: conditions,
                y: conditions.map(c => {
                    const mc = s.market_condition_pnl || {};
                    return (mc[c] && mc[c].pnl) || 0;
                }),
                name: s.strategy,
                type: 'bar',
                marker: { color: colors[i] },
            }));
            Plotly.newPlot('conditionChart', condTraces, {...plotLayout, barmode: 'group'}, {responsive: true});

            // Equity curves
            const strategies = ['wheel', 'spx_spreads', 'iron_condors', 'regime_adaptive'];
            const eqTraces = [];
            for (let i = 0; i < strategies.length; i++) {
                try {
                    const eqResp = await fetch('/api/equity/' + strategies[i]);
                    const eqData = await eqResp.json();
                    if (eqData.dates && eqData.dates.length) {
                        eqTraces.push({
                            x: eqData.dates,
                            y: eqData.equity,
                            name: data[i] ? data[i].strategy : strategies[i],
                            type: 'scatter',
                            mode: 'lines',
                            line: { color: colors[i], width: 2 },
                        });
                    }
                } catch(e) {}
            }
            if (eqTraces.length) {
                Plotly.newPlot('equityChart', eqTraces, {
                    ...plotLayout,
                    yaxis: { ...plotLayout.yaxis, title: 'Equity ($)' },
                    xaxis: { ...plotLayout.xaxis, title: 'Date' },
                }, {responsive: true});
            }
        }

        // Strategy detail tab
        async function loadStrategyDetail() {
            const strategy = document.getElementById('strategySelect').value;

            // Single equity curve
            try {
                const resp = await fetch('/api/equity/' + strategy);
                const data = await resp.json();
                if (data.dates && data.dates.length) {
                    // Calculate drawdown
                    let peak = 0;
                    const dd = data.equity.map(eq => {
                        peak = Math.max(peak, eq);
                        return ((eq - peak) / peak) * 100;
                    });

                    Plotly.newPlot('singleEquityChart', [
                        { x: data.dates, y: data.equity, name: 'Equity', type: 'scatter', mode: 'lines', line: {color: '#58a6ff', width: 2} },
                        { x: data.dates, y: dd, name: 'Drawdown %', type: 'scatter', mode: 'lines', yaxis: 'y2', line: {color: '#f85149', width: 1}, fill: 'tozeroy', fillcolor: 'rgba(248,81,73,0.1)' },
                    ], {
                        ...plotLayout,
                        yaxis: { ...plotLayout.yaxis, title: 'Equity ($)', side: 'left' },
                        yaxis2: { title: 'Drawdown %', overlaying: 'y', side: 'right', gridcolor: '#30363d', zerolinecolor: '#30363d', font: {color: '#8b949e'} },
                    }, {responsive: true});
                }
            } catch(e) {}

            // Trade data for distributions
            try {
                const resp = await fetch('/api/trades/' + strategy);
                const trades = await resp.json();
                if (trades.length) {
                    // Exit reasons
                    const reasons = {};
                    const pnls = [];
                    trades.forEach(t => {
                        reasons[t.exit_reason || 'unknown'] = (reasons[t.exit_reason || 'unknown'] || 0) + 1;
                        if (t.pnl !== undefined) pnls.push(t.pnl);
                    });

                    Plotly.newPlot('exitReasonChart', [{
                        labels: Object.keys(reasons),
                        values: Object.values(reasons),
                        type: 'pie',
                        marker: { colors: colors },
                        textfont: { color: '#e6edf3' },
                    }], {...plotLayout, showlegend: true}, {responsive: true});

                    // P&L histogram
                    Plotly.newPlot('pnlDistChart', [{
                        x: pnls,
                        type: 'histogram',
                        nbinsx: 30,
                        marker: { color: '#58a6ff' },
                    }], {...plotLayout, xaxis: {...plotLayout.xaxis, title: 'P&L ($)'}, yaxis: {...plotLayout.yaxis, title: 'Count'}, showlegend: false}, {responsive: true});
                }
            } catch(e) {}
        }

        // Trade log tab
        async function loadTradeLog() {
            const strategy = document.getElementById('tradeStrategySelect').value;
            try {
                const resp = await fetch('/api/trades/' + strategy);
                const trades = await resp.json();
                let html = '';
                trades.slice(0, 100).forEach(t => {
                    const pnlClass = (t.pnl || 0) >= 0 ? 'positive' : 'negative';
                    html += `<tr>
                        <td>${t.entry_date || ''}</td>
                        <td>${t.symbol || ''}</td>
                        <td class="${pnlClass}">$${(t.pnl || 0).toFixed(2)}</td>
                        <td>${t.exit_reason || ''}</td>
                        <td>${(t.entry_vix || 0).toFixed(1)}</td>
                        <td>${t.market_condition || ''}</td>
                    </tr>`;
                });
                document.getElementById('tradeTableBody').innerHTML = html || '<tr><td colspan="6">No trades found</td></tr>';
            } catch(e) {
                document.getElementById('tradeTableBody').innerHTML = '<tr><td colspan="6">Error loading trades</td></tr>';
            }
        }

        // Scanner tab
        async function loadScanner() {
            try {
                const resp = await fetch('/api/scanner');
                const data = await resp.json();
                let html = '';
                data.forEach(s => {
                    const maxScore = 100;
                    html += `<tr>
                        <td style="font-weight:600">${s.symbol}</td>
                        <td>$${(s.price||0).toFixed(2)}</td>
                        <td>${(s.iv_rank_proxy||0).toFixed(1)}</td>
                        <td>${(s.atr_pct||0).toFixed(2)}%</td>
                        <td>${s.trend_score || 0}/4</td>
                        <td>${(s.rsi_14||0).toFixed(1)}</td>
                        <td>${s.sector || ''}</td>
                        <td>${(s.wheel_score||0).toFixed(0)}</td>
                        <td>${(s.spread_score||0).toFixed(0)}</td>
                        <td>${(s.condor_score||0).toFixed(0)}</td>
                        <td style="font-weight:600">${(s.composite_score||0).toFixed(0)}</td>
                    </tr>`;
                });
                document.getElementById('scannerTableBody').innerHTML = html || '<tr><td colspan="11">Run stock_scanner.py first</td></tr>';
            } catch(e) {
                document.getElementById('scannerTableBody').innerHTML = '<tr><td colspan="11">No scanner data</td></tr>';
            }
        }

        // Risk analysis tab
        async function loadRiskAnalysis() {
            try {
                const resp = await fetch('/api/risk');
                const data = await resp.json();

                // Risk details
                let details = '';
                data.strategies.forEach(s => {
                    const winClass = s.win_rate >= 60 ? 'positive' : s.win_rate >= 50 ? 'neutral' : 'negative';
                    const ddClass = s.drawdown > -15 ? 'positive' : s.drawdown > -25 ? 'neutral' : 'negative';
                    details += `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
                        <span>${s.name}</span>
                        <span>WR: <span class="${winClass}">${s.win_rate.toFixed(1)}%</span> | DD: <span class="${ddClass}">${s.drawdown.toFixed(2)}%</span> | Sharpe: ${s.sharpe.toFixed(3)}</span>
                    </div>`;
                });
                document.getElementById('riskDetailsList').innerHTML = details;

                // Drawdown chart
                const strategies = ['wheel', 'spx_spreads', 'iron_condors', 'regime_adaptive'];
                const ddTraces = [];
                for (let i = 0; i < strategies.length; i++) {
                    try {
                        const eqResp = await fetch('/api/equity/' + strategies[i]);
                        const eqData = await eqResp.json();
                        if (eqData.dates && eqData.dates.length) {
                            let peak = 0;
                            const dd = eqData.equity.map(eq => {
                                peak = Math.max(peak, eq);
                                return ((eq - peak) / peak) * 100;
                            });
                            ddTraces.push({
                                x: eqData.dates, y: dd,
                                name: data.strategies[i] ? data.strategies[i].name : strategies[i],
                                type: 'scatter', mode: 'lines',
                                line: { color: colors[i], width: 1.5 },
                                fill: 'tozeroy', fillcolor: colors[i] + '15',
                            });
                        }
                    } catch(e) {}
                }
                if (ddTraces.length) {
                    Plotly.newPlot('drawdownChart', ddTraces, {
                        ...plotLayout,
                        yaxis: { ...plotLayout.yaxis, title: 'Drawdown (%)' },
                    }, {responsive: true});
                }

                // Win rate vs Sharpe scatter
                if (data.strategies.length) {
                    Plotly.newPlot('winRateSharpeChart', [{
                        x: data.strategies.map(s => s.win_rate),
                        y: data.strategies.map(s => s.sharpe),
                        text: data.strategies.map(s => s.name),
                        mode: 'markers+text',
                        type: 'scatter',
                        textposition: 'top center',
                        textfont: { color: '#e6edf3', size: 11 },
                        marker: { size: 16, color: colors },
                    }], {
                        ...plotLayout,
                        xaxis: { ...plotLayout.xaxis, title: 'Win Rate (%)' },
                        yaxis: { ...plotLayout.yaxis, title: 'Sharpe Ratio' },
                        showlegend: false,
                    }, {responsive: true});
                }
            } catch(e) {}
        }

        // Init
        loadOverview();
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)


def main():
    parser = argparse.ArgumentParser(description='Options Strategy Dashboard')
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger.info(f"Starting dashboard at http://{args.host}:{args.port}")
    logger.info("Run backtester.py and stock_scanner.py first to populate data")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
