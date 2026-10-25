"""
================================================================================
UNIT TESTS: INSTITUTIONAL WEEKLY SWING TRADING SCREENER & RADAR (V3.5)
================================================================================
Tests:
1. Segmented Universe fetching (Indices vs Broader Market Alpha, Dow 30, Nasdaq 100)
2. Indicator calculations (EMA10, EMA21, SMA50, SMA150, SMA200, ATR14, slopes)
3. 30-Day Swing Structure Analyzer (Higher Lows SL2 >= SL1, Volatility Contraction, Dates)
4. Multi-Timeframe Demand Zone & Sell Zone Classifier (Daily, Weekly, Monthly)
5. TradingView 13-Rules Evaluation & Gating Logic
6. Setup Horizon Classification (Tier 1: Trigger Ready vs Tier 2: On-Deck)
7. Institutional Quality Score (IQS: 0-100) and Automated Trade Plans
8. 6-Sheet Formatted Institutional Excel Workbook Export
9. Candlestick Chart Generation
================================================================================
"""

import os
import tempfile
import pytest
import numpy as np
import pandas as pd
import openpyxl
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scanner.run_institutional_weekly_screener import (
    get_segmented_universe,
    get_screener_universe,
    calculate_screener_indicators,
    calculate_multitimeframe_demand_zones,
    analyze_swing_structure,
    evaluate_screener_candidate,
    generate_candlestick_chart,
    export_screener_to_excel,
    export_watchlist_txt,
    DOW_30_SYMBOLS,
    NASDAQ_100_SYMBOLS,
    BROADER_MARKET_SYMBOLS
)


def create_synthetic_market_data(
    bars: int = 260,
    base_price: float = 100.0,
    trend: str = "uptrend",
    vol_base: float = 500000.0
) -> pd.DataFrame:
    """Helper to generate clean synthetic OHLCV daily bars"""
    dates = pd.date_range(end=pd.Timestamp.today(), periods=bars, freq='B')
    
    if trend == "uptrend":
        price_trend = np.linspace(base_price * 0.70, base_price, bars)
    elif trend == "downtrend":
        price_trend = np.linspace(base_price * 1.30, base_price, bars)
    else:
        price_trend = np.full(bars, base_price)
        
    noise = np.sin(np.linspace(0, 10, bars)) * (base_price * 0.02)
    closes = price_trend + noise
    highs = closes * 1.015
    lows = closes * 0.985
    opens = (closes + lows) / 2.0
    volumes = np.full(bars, vol_base)
    volumes[-1] = vol_base * 1.30
    
    df = pd.DataFrame({
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
        'Volume': volumes
    }, index=dates)
    return df


class TestInstitutionalScreenerV35:
    
    def test_get_segmented_universe_indices_vs_broader(self):
        """Dual segmentation correctly identifies Index constituents vs Broader Market Alpha"""
        syms, cat_map = get_segmented_universe("combined")
        assert len(syms) > 100
        assert "AAPL" in syms
        assert cat_map["AAPL"] == "INDEX"
        # Check broader market symbol like CELH or INSW
        assert "INSW" in syms or "CELH" in syms or "MSTR" in syms
        for s in syms:
            assert cat_map[s] in ["INDEX", "BROADER_MARKET"]

    def test_get_screener_universe_compatibility(self):
        """Compatibility wrapper returns ticker list"""
        dow = get_screener_universe("dow30")
        assert len(dow) >= 30
        assert "MSFT" in dow

    def test_calculate_screener_indicators_success(self):
        """Computes all moving averages, slopes, and range profiles"""
        df = create_synthetic_market_data(bars=260, base_price=120.0, trend="uptrend")
        res = calculate_screener_indicators(df)
        assert res is not None
        
        expected_cols = [
            'EMA10', 'EMA21', 'SMA50', 'SMA150', 'SMA200',
            'VOL_SMA21', 'VOL_SMA100', 'HIGH_52W', 'LOW_52W', 'LOW_21',
            'ATR14', 'SLOPE_EMA21', 'SLOPE_SMA50', 'SLOPE_SMA200'
        ]
        for col in expected_cols:
            assert col in res.columns
            assert not pd.isna(res[col].iloc[-1])

    def test_calculate_multitimeframe_demand_zones(self):
        """Accurately classifies daily, weekly, monthly demand zones and sell zone"""
        df = create_synthetic_market_data(bars=260, base_price=100.0, trend="uptrend")
        df_ind = calculate_screener_indicators(df)
        zones = calculate_multitimeframe_demand_zones(df_ind)
        assert 'daily_demand' in zones
        assert 'weekly_demand' in zones
        assert 'monthly_demand' in zones
        assert 'sell_zone' in zones
        assert zones['sell_zone'] in ["YES (Extended/Distribution Risk)", "NO (Low-Risk Accumulation Area)"]

    def test_analyze_swing_structure_with_dates(self):
        """Extracts swing highs and lows along with calendar dates"""
        dates = pd.date_range(end=pd.Timestamp.today(), periods=35, freq='B')
        df = pd.DataFrame(index=dates)
        prices = np.full(35, 110.0)
        prices[4] = 104.0; prices[5] = 100.0; prices[6] = 106.0
        prices[11] = 115.0; prices[12] = 120.0; prices[13] = 114.0
        prices[19] = 108.0; prices[20] = 105.0; prices[21] = 109.0
        prices[26] = 114.0; prices[27] = 118.0; prices[28] = 113.0
        
        df['High'] = prices * 1.01
        df['Low'] = prices * 0.99
        df.loc[dates[5], 'Low'] = 100.0
        df.loc[dates[12], 'High'] = 120.0
        df.loc[dates[20], 'Low'] = 105.0
        df.loc[dates[27], 'High'] = 118.0
        df['Close'] = prices
        df['Open'] = prices
        df['Volume'] = 500000.0
        
        res = analyze_swing_structure(df, window_bars=30)
        assert res['valid_structure'] is True
        assert res['higher_low'] is True
        assert res['contraction'] is True
        assert res['sl1'] == 100.0
        assert res['sl2'] == 105.0
        assert res['sl1_date'] != "N/A"
        assert res['sl2_date'] != "N/A"

    def test_evaluate_screener_candidate_tier1_readiness(self):
        """Evaluates textbook Tier 1 Trigger Ready setup"""
        df = create_synthetic_market_data(bars=260, base_price=100.0, trend="uptrend", vol_base=600000.0)
        df_ind = calculate_screener_indicators(df)
        
        res = evaluate_screener_candidate("ALPHA", df_ind, category="BROADER_MARKET")
        assert res is not None
        assert res['symbol'] == "ALPHA"
        assert res['category'] == "BROADER_MARKET"
        assert "TIER" in res['setup_horizon']
        assert res['iqs_score'] >= 60
        assert res['suggested_entry'] > 0
        assert res['initial_stop_loss'] < res['suggested_entry']
        assert 5.0 <= res['risk_pct'] <= 10.0
        assert res['risk_reward'] >= 1.0

    def test_evaluate_screener_candidate_gating_failures(self):
        """Fails rule checks for penny stock or down-trending asset"""
        df_penny = create_synthetic_market_data(bars=260, base_price=7.0, trend="uptrend")
        df_penny_ind = calculate_screener_indicators(df_penny)
        assert evaluate_screener_candidate("PENNY", df_penny_ind) is None
        
        df_bear = create_synthetic_market_data(bars=260, base_price=100.0, trend="downtrend")
        df_bear_ind = calculate_screener_indicators(df_bear)
        assert evaluate_screener_candidate("BEAR", df_bear_ind) is None

    def test_generate_candlestick_chart(self):
        """Generates 35-day candlestick chart without errors"""
        df = create_synthetic_market_data(bars=260, base_price=150.0, trend="uptrend")
        df_ind = calculate_screener_indicators(df)
        eval_res = evaluate_screener_candidate("CHART_SYM", df_ind, category="INDEX")
        assert eval_res is not None
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            chart_path = tf.name
            
        try:
            generate_candlestick_chart("CHART_SYM", df_ind, eval_res, output_path=chart_path, show=False)
            assert os.path.exists(chart_path)
            assert os.path.getsize(chart_path) > 1000  # Non-empty image file
        finally:
            if os.path.exists(chart_path):
                os.remove(chart_path)

    def test_export_screener_to_excel_6_sheets(self):
        """Generates 6-sheet institutional Excel workbook"""
        mock_candidates = [
            {
                'symbol': 'NVDA', 'category': 'INDEX', 'setup_horizon': 'TIER 1: TRIGGER-READY (THIS WEEK / 0-3d)',
                'readiness_badge': 'TRIGGER READY', 'close': 140.50, 'ytd_perf_pct': 185.2, 'vol_100d_k': 45200.0,
                'rvol': 1.65, 'dist_to_ema21_pct': 1.2, 'dist_to_sma50_pct': 3.1, 'dist_to_sma200_pct': 28.5,
                'dist_from_52w_high_pct': 2.5, 'dist_from_52w_low_pct': 110.0, 'slope_ema21': 3.2,
                'slope_sma50': 2.1, 'ema21_slope_desc': 'Strongly Upward', 'sma50_slope_desc': 'Strongly Upward',
                'buy_zone_type': 'Dual Convergence Sweet Spot', 'daily_demand_zone': 'YES',
                'weekly_demand_zone': 'YES', 'monthly_demand_zone': 'YES', 'sell_zone': 'NO (Low-Risk Accumulation Area)',
                'volume_surge_tag': 'YES (Green Pocket Pivot)', 'swing_higher_low': 'YES (SL2 >= SL1)',
                'swing_contraction': 'YES (VCP)', 'sl1': 130.0, 'sl1_date': '2026-10-01', 'sl2': 136.0,
                'sl2_date': '2026-10-15', 'sh1': 142.0, 'sh1_date': '2026-10-08', 'sh2': 144.0,
                'sh2_date': '2026-10-20', 'rs_score': 94.5, 'iqs_score': 96, 'grade': 'A+', 'star_rating': '⭐⭐⭐⭐⭐ (Elite A+)',
                'action_verdict': 'PRIME BUY SETUP', 'suggested_entry': 140.50, 'initial_stop_loss': 132.00,
                'risk_pct': 6.0, 'target_1': 147.53, 'target_2': 154.55, 'target_3': 161.58, 'risk_reward': 1.65
            },
            {
                'symbol': 'CELH', 'category': 'BROADER_MARKET', 'setup_horizon': 'TIER 2: ON-DECK (1-2 WEEKS)',
                'readiness_badge': 'ON DECK', 'close': 45.00, 'ytd_perf_pct': 24.5, 'vol_100d_k': 3200.0,
                'rvol': 1.35, 'dist_to_ema21_pct': 2.8, 'dist_to_sma50_pct': 4.1, 'dist_to_sma200_pct': 16.5,
                'dist_from_52w_high_pct': 6.5, 'dist_from_52w_low_pct': 45.0, 'slope_ema21': 1.5,
                'slope_sma50': 1.1, 'ema21_slope_desc': 'Upward', 'sma50_slope_desc': 'Upward',
                'buy_zone_type': 'Upper Pullback Zone', 'daily_demand_zone': 'YES',
                'weekly_demand_zone': 'YES', 'monthly_demand_zone': 'YES', 'sell_zone': 'NO (Low-Risk Accumulation Area)',
                'volume_surge_tag': 'YES (Green Pocket Pivot)', 'swing_higher_low': 'YES (SL2 >= SL1)',
                'swing_contraction': 'YES (VCP)', 'sl1': 41.0, 'sl1_date': '2026-10-02', 'sl2': 43.5,
                'sl2_date': '2026-10-16', 'sh1': 46.5, 'sh1_date': '2026-10-10', 'sh2': 47.0,
                'sh2_date': '2026-10-22', 'rs_score': 82.0, 'iqs_score': 88, 'grade': 'A', 'star_rating': '⭐⭐⭐⭐ (Grade A High Conviction)',
                'action_verdict': 'HIGH WATCHLIST PRIORITY', 'suggested_entry': 43.80, 'initial_stop_loss': 40.75,
                'risk_pct': 7.0, 'target_1': 45.99, 'target_2': 48.18, 'target_3': 50.37, 'risk_reward': 1.44
            }
        ]
        
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            temp_path = tf.name
            
        try:
            export_screener_to_excel(mock_candidates, output_path=temp_path)
            assert os.path.exists(temp_path)
            
            wb = openpyxl.load_workbook(temp_path)
            expected_sheets = [
                "Index_Watchlist_Top_Setups",
                "Broader_Market_Alpha_Setups",
                "Trigger_Ready_This_Week",
                "Multi_Timeframe_Demand_Matrix",
                "All_Screened_Candidates",
                "Watchlist_TXT_Export"
            ]
            for s in expected_sheets:
                assert s in wb.sheetnames
                
            ws_txt = wb["Watchlist_TXT_Export"]
            assert ws_txt.cell(row=2, column=1).value == "NVDA"
            assert ws_txt.cell(row=2, column=5).value == "A+"
            assert ws_txt.cell(row=3, column=1).value == "CELH"
            assert ws_txt.cell(row=3, column=5).value == "A"
            wb.close()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_export_watchlist_txt(self):
        """Exports clean plain-text watchlist"""
        mock_candidates = [
            {'symbol': 'NVDA', 'setup_horizon': 'TIER 1', 'iqs_score': 95},
            {'symbol': 'CELH', 'setup_horizon': 'TIER 2', 'iqs_score': 85}
        ]
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            txt_path = tf.name
        try:
            export_watchlist_txt(mock_candidates, output_txt=txt_path)
            assert os.path.exists(txt_path)
            with open(txt_path, "r") as f:
                content = f.read()
            assert "NVDA\nCELH" in content or "NVDA" in content
        finally:
            if os.path.exists(txt_path):
                os.remove(txt_path)

    def test_colab_kernelspec_and_interactive_charting(self):
        """Verify notebooks have proper kernelspec metadata and interactive widgets"""
        screener_nb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "colab", "Rajat_Alpha_Institutional_Weekly_Screener.ipynb"
        )
        assert os.path.exists(screener_nb_path)
        with open(screener_nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
            
        # Verify kernelspec prevents 'no runtime environment configured' error
        assert "kernelspec" in nb["metadata"]
        assert nb["metadata"]["kernelspec"]["name"] == "python3"
        
        # Verify Step 6 has interactive dropdown inspector and top 10 auto-render
        step6_source = "".join(nb["cells"][6]["source"])
        assert "ipywidgets as widgets" in step6_source
        assert "Dropdown" in step6_source
        assert "plot_candlestick_chart" in step6_source
        assert "min(10, len(stored_chart_data))" in step6_source or "top_candidates" in step6_source

    def test_colab_master_suite_and_modular_structure(self):
        """Verify Master Suite notebook exists and modular folders are intact"""
        base_colab = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "colab"
        )
        master_nb_path = os.path.join(base_colab, "Rajat_Alpha_Master_Trading_Suite.ipynb")
        assert os.path.exists(master_nb_path)
        with open(master_nb_path, "r", encoding="utf-8") as f:
            mnb = json.load(f)
        assert "kernelspec" in mnb["metadata"]
        assert mnb["metadata"]["kernelspec"]["name"] == "python3"
        
        expected_modules = [
            "00_master_suite",
            "01_weekly_screener",
            "02_swing_backtest",
            "03_institutional_prop_protocol",
            "04_scanned_watchlist_backtest",
            "05_reference_simulations"
        ]
        for m in expected_modules:
            mod_dir = os.path.join(base_colab, m)
            assert os.path.isdir(mod_dir)
            assert os.path.exists(os.path.join(mod_dir, "README.md"))

