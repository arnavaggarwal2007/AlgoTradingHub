#!/usr/bin/env python3
"""
Log Analyzer Dashboard - Interactive Web UI for Trading Bot Log Analysis
"""

from flask import Flask, render_template_string, request, jsonify
import json
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the log analyzer
from tools.log_analyzer import LogAnalyzer

app = Flask(__name__)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Log Analyzer Dashboard - Rajat Alpha V67</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        
        .controls {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        
        .form-group {
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }
        
        input[type="date"], select {
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            min-width: 150px;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .stat-card.error {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .stat-card.warning {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }
        
        .stat-card.success {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        .stat-card h3 {
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
        }
        
        .section {
            margin-bottom: 30px;
        }
        
        .section h2 {
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .error-row {
            background: #fff5f5;
        }
        
        .warning-row {
            background: #fffbf0;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #667eea;
            font-size: 1.2em;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .category-section {
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .category-title {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .log-entry {
            padding: 10px;
            margin: 5px 0;
            background: white;
            border-left: 4px solid #ddd;
            border-radius: 4px;
        }
        
        .log-entry.error {
            border-left-color: #f5576c;
        }
        
        .log-entry.warning {
            border-left-color: #fee140;
        }
        
        .timestamp {
            color: #999;
            font-size: 0.9em;
            margin-right: 10px;
        }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Log Analyzer Dashboard</h1>
        <p class="subtitle">Rajat Alpha V67 Trading Bot - Comprehensive Log Analysis</p>
        
        <div class="controls">
            <div class="form-group">
                <label for="startDate">Start Date:</label>
                <input type="date" id="startDate" value="{{ default_start }}">
            </div>
            <div class="form-group">
                <label for="endDate">End Date:</label>
                <input type="date" id="endDate" value="{{ default_end }}">
            </div>
            <div class="form-group">
                <label>&nbsp;</label>
                <button onclick="analyzeLog()">🔍 Analyze Logs</button>
            </div>
            <div class="form-group">
                <label>&nbsp;</label>
                <button onclick="exportCSV()">📥 Export CSV</button>
            </div>
        </div>
        
        <div id="results"></div>
    </div>
    
    <script>
        // Set default dates (last 7 days)
        function analyzeLog() {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const resultsDiv = document.getElementById('results');
            
            if (!startDate || !endDate) {
                alert('Please select both start and end dates');
                return;
            }
            
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Analyzing logs, please wait...</div>';
            
            fetch('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    start_date: startDate,
                    end_date: endDate
                })
            })
            .then(response => response.json())
            .then(data => {
                displayResults(data);
            })
            .catch(error => {
                resultsDiv.innerHTML = '<div class="no-data">❌ Error analyzing logs: ' + error + '</div>';
            });
        }
        
        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            
            let html = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>📝 Total Entries</h3>
                        <div class="value">${data.total_entries.toLocaleString()}</div>
                    </div>
                    <div class="stat-card error">
                        <h3>🚨 Errors</h3>
                        <div class="value">${data.total_errors.toLocaleString()}</div>
                    </div>
                    <div class="stat-card warning">
                        <h3>⚠️ Warnings</h3>
                        <div class="value">${data.total_warnings.toLocaleString()}</div>
                    </div>
                    <div class="stat-card success">
                        <h3>💰 Trades</h3>
                        <div class="value">${data.total_trades.toLocaleString()}</div>
                    </div>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card success">
                        <h3>📡 Signals Generated</h3>
                        <div class="value">${data.signals_generated.toLocaleString()}</div>
                    </div>
                    <div class="stat-card">
                        <h3>🛒 Buy Orders</h3>
                        <div class="value">${data.total_buys.toLocaleString()}</div>
                    </div>
                    <div class="stat-card">
                        <h3>🎯 Full Exits</h3>
                        <div class="value">${data.full_exits.toLocaleString()}</div>
                    </div>
                    <div class="stat-card">
                        <h3>📊 Partial Exits</h3>
                        <div class="value">${data.partial_exits.toLocaleString()}</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📅 Daily Statistics</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Errors</th>
                                <th>Warnings</th>
                                <th>Trades</th>
                                <th>Signals</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            if (data.daily_stats && Object.keys(data.daily_stats).length > 0) {
                Object.keys(data.daily_stats).sort().forEach(date => {
                    const stats = data.daily_stats[date];
                    html += `
                        <tr>
                            <td><strong>${date}</strong></td>
                            <td>${stats.errors}</td>
                            <td>${stats.warnings}</td>
                            <td>${stats.trades}</td>
                            <td>${stats.signals}</td>
                        </tr>
                    `;
                });
            } else {
                html += '<tr><td colspan="5" class="no-data">No data available</td></tr>';
            }
            
            html += `
                        </tbody>
                    </table>
                </div>
                
                <div class="section">
                    <h2>🚨 Error Categories</h2>
            `;
            
            if (data.error_categories && Object.keys(data.error_categories).length > 0) {
                Object.entries(data.error_categories).forEach(([category, errors]) => {
                    html += `
                        <div class="category-section">
                            <div class="category-title">${category} (${errors.length})</div>
                    `;
                    
                    errors.slice(0, 5).forEach(error => {
                        html += `
                            <div class="log-entry error">
                                <span class="timestamp">${error.timestamp}</span>
                                <span>${error.message.substring(0, 150)}...</span>
                            </div>
                        `;
                    });
                    
                    if (errors.length > 5) {
                        html += `<div style="text-align: center; margin-top: 10px; color: #999;">
                            ... and ${errors.length - 5} more
                        </div>`;
                    }
                    
                    html += `</div>`;
                });
            } else {
                html += '<div class="no-data">✅ No errors found!</div>';
            }
            
            html += `
                </div>
                
                <div class="section">
                    <h2>⚠️ Warning Categories</h2>
            `;
            
            if (data.warning_categories && Object.keys(data.warning_categories).length > 0) {
                Object.entries(data.warning_categories).forEach(([category, warnings]) => {
                    html += `
                        <div class="category-section">
                            <div class="category-title">${category} (${warnings.length})</div>
                    `;
                    
                    warnings.slice(0, 5).forEach(warning => {
                        html += `
                            <div class="log-entry warning">
                                <span class="timestamp">${warning.timestamp}</span>
                                <span>${warning.message.substring(0, 150)}...</span>
                            </div>
                        `;
                    });
                    
                    if (warnings.length > 5) {
                        html += `<div style="text-align: center; margin-top: 10px; color: #999;">
                            ... and ${warnings.length - 5} more
                        </div>`;
                    }
                    
                    html += `</div>`;
                });
            } else {
                html += '<div class="no-data">✅ No warnings found!</div>';
            }
            
            html += `</div>`;
            
            resultsDiv.innerHTML = html;
        }
        
        function exportCSV() {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            
            if (!startDate || !endDate) {
                alert('Please select both start and end dates and analyze first');
                return;
            }
            
            window.location.href = `/export?start_date=${startDate}&end_date=${endDate}`;
        }
        
        // Auto-analyze on page load with default date range
        window.onload = function() {
            analyzeLog();
        };
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Render the main dashboard"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    return render_template_string(HTML_TEMPLATE, 
                                 default_start=start_date,
                                 default_end=end_date)


@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze logs for the given date range"""
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing date parameters'}), 400
    
    try:
        # Create analyzer and process logs
        analyzer = LogAnalyzer('logs/rajat_alpha_v67.log')
        analyzer.analyze_date_range(start_date, end_date)
        
        # Prepare response data
        error_categories = analyzer.categorize_errors()
        warning_categories = analyzer.categorize_warnings()
        daily_stats = analyzer.generate_daily_stats()
        
        # Format errors and warnings for JSON
        formatted_errors = {}
        for category, errors in error_categories.items():
            formatted_errors[category] = [
                {
                    'timestamp': e.get('parsed_timestamp', '').strftime('%Y-%m-%d %H:%M:%S') if e.get('parsed_timestamp') else '',
                    'message': e.get('message', '')
                }
                for e in errors
            ]
        
        formatted_warnings = {}
        for category, warnings in warning_categories.items():
            formatted_warnings[category] = [
                {
                    'timestamp': w.get('parsed_timestamp', '').strftime('%Y-%m-%d %H:%M:%S') if w.get('parsed_timestamp') else '',
                    'message': w.get('message', '')
                }
                for w in warnings
            ]
        
        response = {
            'total_entries': len(analyzer.entries),
            'total_errors': len(analyzer.errors),
            'total_warnings': len(analyzer.warnings),
            'total_trades': len(analyzer.trades),
            'signals_generated': analyzer.stats.get('signals_generated', 0),
            'signals_rejected': analyzer.stats.get('signals_rejected', 0),
            'total_buys': analyzer.stats.get('total_buys', 0),
            'full_exits': analyzer.stats.get('full_exits', 0),
            'partial_exits': analyzer.stats.get('partial_exits', 0),
            'error_categories': formatted_errors,
            'warning_categories': formatted_warnings,
            'daily_stats': daily_stats
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/export')
def export():
    """Export analysis to CSV"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return "Missing date parameters", 400
    
    try:
        analyzer = LogAnalyzer('logs/rajat_alpha_v67.log')
        analyzer.analyze_date_range(start_date, end_date)
        
        # Generate CSV
        csv_file = f'log_analysis_{start_date}_to_{end_date}.csv'
        analyzer.generate_csv_report(csv_file)
        
        from flask import send_file
        return send_file(csv_file, as_attachment=True)
    
    except Exception as e:
        return f"Error generating CSV: {str(e)}", 500


def main():
    print("=" * 80)
    print("📊 LOG ANALYZER DASHBOARD")
    print("=" * 80)
    print()
    print("Starting web dashboard on http://localhost:5001")
    print()
    print("Features:")
    print("  ✅ Interactive date range selection")
    print("  ✅ Real-time log analysis")
    print("  ✅ Error and warning categorization")
    print("  ✅ Daily statistics table")
    print("  ✅ CSV export functionality")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    
    app.run(debug=True, host='0.0.0.0', port=5001)


if __name__ == '__main__':
    main()
