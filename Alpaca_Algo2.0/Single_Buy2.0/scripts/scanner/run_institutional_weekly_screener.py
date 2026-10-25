"""
================================================================================
INSTITUTIONAL WEEKLY SWING TRADING SCREENER & RADAR (V3.5)
================================================================================
Senior Quantitative Strategist Architecture (15+ Years Multi-Cycle Prop Experience)

Key Capabilities:
1. Dual Universe Architecture:
   - LIST A: Inside Major Indices (S&P 500, Nasdaq 100, Dow 30)
   - LIST B: Outside Major Indices (Broader Market High-Growth Mid-Cap Alpha)
2. Complete 13 TradingView Screener Rules (Trend, Stacking, Clearance, Volume)
3. Mark Minervini 52-Week High Clearance (Within 25% of 52w High)
4. Moving Average Slope & Curvature Verification (Flat, Turning Up, Strongly Upward)
5. Precision Buy Zone & Setup Horizon Classification:
   - TIER 1: TRIGGER-READY (0-3 Days / This Week) -> At 21 EMA / 50 SMA Demand Zone
   - TIER 2: ON-DECK (1-2 Weeks) -> Pulling back to 21 EMA with Higher Low (SL2 >= SL1)
   - TIER 3: BASE FORMATION (2-3 Weeks) -> Consolidating near highs
6. 30-Day Swing Pivot Structure (SL1, SL2, SH1, SH2, Higher Lows & VCP Contraction)
7. Multi-Timeframe Demand Zone Matrix (Daily, Weekly, Monthly Demand & Sell Zones)
8. Volume Surge & Green Pocket Pivot Accumulation Tracking
9. IBD Relative Strength Composite (0-100)
10. Automated Trade Execution Plan (Entry, Stop Loss bounded 5-10%, Targets 1/2/3, R:R)
11. Publication-Quality Candlestick Chart Generator (with MAs, Demand Bands, Swings, Plans)
12. Multi-Sheet Formatted Excel Workbook (.xlsx) & Direct watchlist.txt Export
================================================================================
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

import pandas as pd
import numpy as np
import yfinance as yf
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Candlestick plotting support
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ================================================================================
# 1. INSTITUTIONAL UNIVERSE DEFINITIONS (DUAL SEGMENTATION)
# ================================================================================

DOW_30_SYMBOLS = [
    "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
    "DOW", "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD",
    "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "WMT"
]

NASDAQ_100_SYMBOLS = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN",
    "AMZN", "APP", "ARM", "ASML", "AVGO", "AXON", "BIIB", "BKNG", "BKR",
    "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CPRT", "CRWD", "CSCO", "CSX", "CTAS",
    "CTSH", "DASH", "DDOG", "DLTR", "DXCM", "EA", "EXC", "FANG", "FAST", "FTNT",
    "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HON", "IDXX", "ILMN", "INTC", "INTU",
    "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "LULU", "MAR", "MCHP", "MDB",
    "MDLZ", "MELI", "META", "MNST", "MRNA", "MRVL", "MSFT", "MU", "NFLX", "NVDA",
    "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR",
    "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS", "TEAM", "TMUS", "TSLA",
    "TTD", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "XEL", "ZS"
]

SP_500_CORE_SAMPLE = [
    "AAPL", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "LLY", "AVGO",
    "TSLA", "JPM", "WMT", "UNH", "XOM", "V", "PG", "MA", "COST", "JNJ",
    "ORCL", "HD", "BAC", "ABBV", "CVX", "NFLX", "KO", "MRK", "CRM", "AMD",
    "PEP", "LIN", "TMO", "ACN", "WFC", "CSCO", "MCD", "ABT", "GE", "IBM",
    "PM", "ISRG", "TXN", "CAT", "NOW", "QCOM", "VZ", "MS", "AMAT", "UBER",
    "GS", "SPGI", "AXP", "BKNG", "RTX", "HON", "LOW", "PFE", "SYK", "UNP",
    "BLK", "TJX", "VRTX", "REGN", "ETN", "PANW", "PGR", "LRCX", "CB", "BSX",
    "ADI", "CI", "C", "MDT", "PLTR", "ANET", "KLAC", "SCHW", "SNPS",
    "CDNS", "CRWD", "MAR", "APH", "EOG", "TDG", "WM", "ITW", "SHW", "CTAS",
    "FTNT", "ORLY", "COF", "MCK", "NXPI", "DE", "WELL", "PH", "EMR", "PCAR"
]

# High-liquidity mid-cap, high-growth, Russell 1000/2000 & institutional leaders outside major indices
BROADER_MARKET_SYMBOLS = [
    # Top Momentum, SaaS & Cloud
    "NET", "SNOW", "HUBS", "ESTC", "PATH", "DOCN", "MSTR", "TOST", "DUOL", "IOT",
    "SYM", "TEM", "ALAB", "VRT", "RBRK", "TWLO", "SHOP", "SE", "BILL", "AFRM",
    "UPST", "HOOD", "SOFI", "COIN", "DT", "GWRE", "MNDY", "PEGA", "PCTY", "PAYC",
    "MANH", "TYL", "PTC", "APPF", "BL", "SMAR", "TENB", "VRNS", "OKTA", "FROG",
    "U", "RELY", "GH",
    # Semiconductors & Hardware Leaders
    "TSM", "SMCI", "PSTG", "CAHR", "MPWR", "ALGM", "COHR", "AMBA", "POWI", "RMBS",
    "ACLS", "DIOD", "LSCC", "MTSI", "TER", "ENTG", "MKSI", "CCMP", "FORM", "AMKR",
    "CAMT", "ICHR", "UCTT", "VECO",
    # Energy, Marine Shipping & Infrastructure
    "INSW", "TNK", "LPG", "FRO", "STNG", "GSL", "ZIM", "VIST", "EQT", "LNG",
    "FSLR", "NXT", "AR", "RRC", "CHRD", "SM", "PR", "MTDR", "MGY", "CRK",
    "CNX", "DVN", "APA", "CTRA", "OVV", "HES", "OXY", "PAGP", "OKE",
    # High-Velocity Industrials & Construction
    "PWR", "EME", "FIX", "BLDR", "IBP", "ACM", "J", "HUBB", "NVT", "GWW",
    "FDX", "SAIA", "XPO", "WSO", "TTC", "AGCO", "SITE", "TREX", "AZEK", "OSK",
    "CR", "RBC", "AIT", "GGG", "LECO", "MIDD", "CW", "HEI", "HII", "HWM",
    "ATI", "NDSN", "NSP", "TILE",
    # High-Growth Consumer, Dining & Retail
    "CELH", "ONON", "BIRK", "DECK", "SHAK", "CAVA", "WING", "BROS", "SG", "BOOT",
    "CROX", "SKX", "TSCO", "FIVE", "OLLI", "CHWY", "CART", "CAKE", "EAT", "DRI",
    "TXRH", "YUM", "DPZ", "PZZA", "BJRI", "PLAY", "LOCO", "ARCO", "DIN", "CHEF",
    "CNK", "IMAX",
    # Healthcare, MedTech & Biotech Growth
    "ARGX", "ALNY", "BMRN", "CRSP", "BEAM", "NTRA", "RVMD", "KNSA", "AXSM", "INSM",
    "CYTK", "ARDX", "VKTX", "MDGL", "APGE", "HALO", "INCY", "NBIX", "JAZZ", "IONS",
    "ICPT", "ALKS", "PODD", "PEN", "TFX", "EW", "HOLX", "WST", "CAH", "BDX",
    "BMY", "IMVT", "GKOS", "PHVS", "AXGN", "THG",
    # Financial Leaders & Alternative Asset Managers
    "KKR", "APO", "ARES", "BX", "OWL", "HLNE", "STEP", "CG", "LPLA", "RJF",
    "IBKR", "TW", "VIRT", "PIPR", "MC", "EVR", "CNO", "BFH", "UMBF", "WSBC",
    "BUSE", "PK", "RHI", "FCF", "NBTB", "BPOP", "S", "CBSH", "HNGE", "HSIC",
    "ACT", "NSIT", "USB", "WT", "PFG", "LFST", "UBSI", "AIZ", "ALL", "VOYA",
    "ONB", "ASH", "CLBK", "CATY", "BEN", "IVZ", "NTAP", "GCMG", "MET", "EG",
    "NTRS", "VCTR", "NMIH", "TNET", "NOV", "TIGO", "MSGE", "ECPG", "ROIV",
    "CLMT", "CON", "AVT", "XYZ", "RGA", "FA", "AMP", "KFY", "CXW"
]

def get_segmented_universe(mode: str = "combined") -> Tuple[List[str], Dict[str, str]]:
    """
    Returns (symbol_list, category_map) where category is 'INDEX' or 'BROADER_MARKET'.
    Supported modes:
    - 'combined': Both Index Leaders AND Broader Market Growth (~850+ stocks)
    - 'indices': S&P 500, Nasdaq 100, Dow 30 only
    - 'broader': Broader market stocks outside major indices only
    - 'dow30', 'nasdaq100', 'sp500'
    """
    m = mode.lower().strip()
    category_map = {}
    
    # Major Indices Set
    index_set = set(DOW_30_SYMBOLS + NASDAQ_100_SYMBOLS + SP_500_CORE_SAMPLE)
    
    # Scrape full S&P 500 if requested
    if m in ["indices", "combined", "all", "sp500"]:
        try:
            import urllib.request
            import ssl
            import re
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                html = resp.read().decode("utf-8")
            raw_syms = re.findall(r'href="https://www\.nyse\.com/quote/XNYS:([A-Z\.]+)"', html)
            if not raw_syms:
                raw_syms = re.findall(r'<td><a rel="nofollow" class="external text" href="[^"]+">([A-Z\.\-]+)</a></td>', html)
            if raw_syms:
                index_set.update([s.replace(".", "-") for s in raw_syms if len(s) <= 5])
        except Exception:
            pass
            
    for s in index_set:
        category_map[s] = "INDEX"
        
    # Broader Market Set
    broader_set = set(BROADER_MARKET_SYMBOLS) - index_set
    for s in broader_set:
        category_map[s] = "BROADER_MARKET"
        
    if m == "indices":
        final_list = sorted(list(index_set))
    elif m == "broader":
        final_list = sorted(list(broader_set))
    elif m == "dow30":
        final_list = sorted(list(set(DOW_30_SYMBOLS)))
    elif m == "nasdaq100":
        final_list = sorted(list(set(NASDAQ_100_SYMBOLS)))
    elif m == "sp500":
        final_list = sorted(list(index_set))
    else:  # combined
        final_list = sorted(list(index_set | broader_set))
        
    return final_list, category_map

def get_screener_universe(universe_name: str = "combined") -> List[str]:
    """Compatibility helper returning ticker list for selected universe"""
    return get_segmented_universe(universe_name)[0]

# ================================================================================
# 2. VECTORIZED INDICATOR & MULTI-TIMEFRAME ENGINE
# ================================================================================

def calculate_screener_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Calculates all moving averages, slopes, ranges, and volume metrics"""
    if df is None or len(df) < 200:
        return None
    df = df.copy()
    c = df['Close']
    h = df['High']
    l = df['Low']
    v = df['Volume']
    
    # Core Moving Averages
    df['EMA10'] = c.ewm(span=10, adjust=False).mean()
    df['EMA21'] = c.ewm(span=21, adjust=False).mean()
    df['SMA50'] = c.rolling(window=50).mean()
    df['SMA150'] = c.rolling(window=150).mean()
    df['SMA200'] = c.rolling(window=200).mean()
    
    # Volume Profiles
    df['VOL_SMA21'] = v.rolling(window=21).mean()
    df['VOL_SMA100'] = v.rolling(window=100).mean()
    
    # 52-Week High and Low (252 trading days)
    df['HIGH_52W'] = h.rolling(window=min(252, len(df))).max()
    df['LOW_52W'] = l.rolling(window=min(252, len(df))).min()
    df['LOW_21'] = l.rolling(window=21).min()
    
    # Average True Range (ATR14)
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(window=14).mean()
    
    # Moving Average Slopes (% change over recent bars)
    df['SLOPE_EMA21'] = ((df['EMA21'] - df['EMA21'].shift(5)) / df['EMA21'].shift(5)) * 100.0
    df['SLOPE_SMA50'] = ((df['SMA50'] - df['SMA50'].shift(10)) / df['SMA50'].shift(10)) * 100.0
    df['SLOPE_SMA200'] = ((df['SMA200'] - df['SMA200'].shift(20)) / df['SMA200'].shift(20)) * 100.0
    
    return df

def calculate_multitimeframe_demand_zones(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluates multi-timeframe demand and sell zones matching Single_Buy2.0:
    - Daily Demand Zone: Price <= 21d Low * 1.035 (Gate 5 in bot)
    - Weekly Demand Zone: Close near Weekly EMA21 or <= 8-week low * 1.05
    - Monthly Demand Zone: Close > Monthly EMA10 and resting near support
    - Overextended / Sell Zone: Price > 5.0% above 21 EMA or Upper Wick Rejection > 50%
    """
    curr = df.iloc[-1]
    close = float(curr['Close'])
    low = float(curr['Low'])
    high = float(curr['High'])
    ema21 = float(curr['EMA21'])
    sma50 = float(curr['SMA50'])
    low21 = float(curr['LOW_21']) if 'LOW_21' in curr and not pd.isna(curr['LOW_21']) else low
    
    # Daily Demand Zone (Gate 5 in script)
    daily_demand = low <= (low21 * 1.035)
    
    # Weekly Multi-Timeframe Demand
    weekly_demand = False
    weekly_bullish = False
    try:
        df_weekly = df.resample('W-FRI').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
        if len(df_weekly) >= 21:
            w_close = float(df_weekly['Close'].iloc[-1])
            w_ema21 = float(df_weekly['Close'].ewm(span=21, adjust=False).mean().iloc[-1])
            w_low8 = float(df_weekly['Low'].iloc[-8:].min())
            weekly_bullish = w_close > w_ema21
            weekly_demand = (abs(w_close - w_ema21) / w_ema21 <= 0.03) or (w_close <= w_low8 * 1.05)
    except Exception:
        weekly_demand = daily_demand
        weekly_bullish = True
        
    # Monthly Multi-Timeframe Demand
    monthly_demand = False
    try:
        df_monthly = df.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
        if len(df_monthly) >= 10:
            m_close = float(df_monthly['Close'].iloc[-1])
            m_ema10 = float(df_monthly['Close'].ewm(span=10, adjust=False).mean().iloc[-1])
            monthly_demand = (m_close > m_ema10) and (abs(m_close - m_ema10) / m_ema10 <= 0.06)
    except Exception:
        monthly_demand = True
        
    # Overextended / Sell Zone
    dist_ema21_pct = (close - ema21) / ema21 * 100.0
    c_range = max(high - low, 0.001)
    upper_wick = high - max(close, float(curr['Open']))
    upper_wick_ratio = upper_wick / c_range
    
    is_overextended = dist_ema21_pct > 5.0
    is_shooting_star = upper_wick_ratio >= 0.50 and (upper_wick / max(abs(close - float(curr['Open'])), 0.001)) >= 2.0
    
    if is_overextended or is_shooting_star:
        sell_zone = "YES (Extended/Distribution Risk)"
    else:
        sell_zone = "NO (Low-Risk Accumulation Area)"
        
    return {
        'daily_demand': "YES" if daily_demand else "NO",
        'weekly_demand': "YES" if weekly_demand else "NO",
        'monthly_demand': "YES" if monthly_demand else "NO",
        'weekly_bullish': weekly_bullish,
        'sell_zone': sell_zone,
        'is_extended': is_overextended,
        'is_shooting_star': is_shooting_star
    }

# ================================================================================
# 3. 30-DAY SWING PIVOT STRUCTURE ANALYZER
# ================================================================================

def analyze_swing_structure(df: pd.DataFrame, window_bars: int = 30) -> Dict[str, Any]:
    """
    Identifies 2 swing highs and 2 swing lows with prices and dates:
    - SL1, SL2: checks higher swing low (SL2 >= SL1)
    - SH1, SH2: checks volatility contraction (Range2 <= Range1)
    """
    if len(df) < window_bars + 2:
        return {
            'valid_structure': False, 'higher_low': False, 'contraction': False,
            'sl1': 0.0, 'sl2': 0.0, 'sh1': 0.0, 'sh2': 0.0,
            'sl1_date': 'N/A', 'sl2_date': 'N/A', 'sh1_date': 'N/A', 'sh2_date': 'N/A'
        }
        
    sub = df.iloc[-(window_bars + 2):].copy()
    highs = []
    lows = []
    
    for i in range(1, len(sub) - 1):
        # 3-bar local high
        if sub['High'].iloc[i] > sub['High'].iloc[i-1] and sub['High'].iloc[i] > sub['High'].iloc[i+1]:
            highs.append((sub.index[i].strftime('%Y-%m-%d'), float(sub['High'].iloc[i])))
        # 3-bar local low
        if sub['Low'].iloc[i] < sub['Low'].iloc[i-1] and sub['Low'].iloc[i] < sub['Low'].iloc[i+1]:
            lows.append((sub.index[i].strftime('%Y-%m-%d'), float(sub['Low'].iloc[i])))
            
    has_two_swings = len(highs) >= 2 and len(lows) >= 2
    higher_low = False
    contraction = False
    sl1_val, sl2_val = 0.0, 0.0
    sh1_val, sh2_val = 0.0, 0.0
    sl1_dt, sl2_dt = "N/A", "N/A"
    sh1_dt, sh2_dt = "N/A", "N/A"
    
    if len(lows) >= 2:
        sl1_dt, sl1_val = lows[-2]
        sl2_dt, sl2_val = lows[-1]
        higher_low = sl2_val >= (sl1_val * 0.995)
    elif len(lows) == 1:
        sl2_dt, sl2_val = lows[-1]
        
    if len(highs) >= 2:
        sh1_dt, sh1_val = highs[-2]
        sh2_dt, sh2_val = highs[-1]
        if sl1_val > 0 and sl2_val > 0:
            range1 = max(0.01, sh1_val - sl1_val)
            range2 = max(0.01, sh2_val - sl2_val)
            contraction = range2 <= (range1 * 1.05)
    elif len(highs) == 1:
        sh2_dt, sh2_val = highs[-1]
        
    return {
        'valid_structure': has_two_swings,
        'swing_highs_count': len(highs),
        'swing_lows_count': len(lows),
        'sh1': sh1_val,
        'sh2': sh2_val,
        'sl1': sl1_val,
        'sl2': sl2_val,
        'sh1_date': sh1_dt,
        'sh2_date': sh2_dt,
        'sl1_date': sl1_dt,
        'sl2_date': sl2_dt,
        'higher_low': higher_low,
        'contraction': contraction
    }

# ================================================================================
# 4. CANDIDATE EVALUATION & SETUP HORIZON CLASSIFIER
# ================================================================================

def evaluate_screener_candidate(symbol: str, df: pd.DataFrame,
                                category: str = "INDEX",
                                spy_df: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
    """
    Evaluates candidate against:
    1. 13 TradingView Gating Filters
    2. Minervini 52w High Proximity (<=25%)
    3. Moving Average Slopes (EMA21 & SMA50 flat or upward)
    4. Setup Horizon Classification (Tier 1: 0-3d, Tier 2: 1-2w, Tier 3: 2-3w)
    5. Multi-Timeframe Demand & Sell Zones
    6. Volume Surge & Pocket Pivot Accumulation
    7. 30-Day Swing Structure (SL1, SL2, SH1, SH2)
    8. Automated Trade Execution Plan (Entry, Stop bounded 5-10%, Targets 1/2/3, R:R)
    """
    if df is None or len(df) < 200:
        return None
        
    c_bar = df.iloc[-1]
    p_bar = df.iloc[-2]
    
    close = float(c_bar['Close'])
    open_px = float(c_bar['Open'])
    prev_close = float(p_bar['Close'])
    volume = float(c_bar['Volume'])
    prev_volume = float(p_bar['Volume'])
    
    ema10 = float(c_bar['EMA10'])
    ema21 = float(c_bar['EMA21'])
    sma50 = float(c_bar['SMA50'])
    sma150 = float(c_bar['SMA150'])
    sma200 = float(c_bar['SMA200'])
    
    vol_sma21 = float(c_bar['VOL_SMA21']) if not pd.isna(c_bar['VOL_SMA21']) else volume
    vol_sma100 = float(c_bar['VOL_SMA100']) if not pd.isna(c_bar['VOL_SMA100']) else volume
    
    high52w = float(c_bar['HIGH_52W'])
    low52w = float(c_bar['LOW_52W'])
    atr14 = float(c_bar['ATR14']) if not pd.isna(c_bar['ATR14']) else close * 0.03
    
    slope_ema21 = float(c_bar['SLOPE_EMA21']) if not pd.isna(c_bar['SLOPE_EMA21']) else 0.0
    slope_sma50 = float(c_bar['SLOPE_SMA50']) if not pd.isna(c_bar['SLOPE_SMA50']) else 0.0
    slope_sma200 = float(c_bar['SLOPE_SMA200']) if not pd.isna(c_bar['SLOPE_SMA200']) else 0.0
    
    # -------------------------------------------------------------
    # 1. TRADINGVIEW 13 CORE CRITERIA GATING
    # -------------------------------------------------------------
    # Rule 1: Price >= 10 USD
    if close < 10.0: return None
    
    # Rule 11: 100-Day Average Volume > 250,000 shares
    if vol_sma100 < 250000: return None
    
    # Rule 4: EMA 21 >= SMA 50
    if ema21 < sma50: return None
    
    # Rule 5: Price above 52-week low by >= 15%
    dist_from_52w_low_pct = (close - low52w) / low52w if low52w > 0 else 0.0
    if dist_from_52w_low_pct < 0.15: return None
    
    # Rule 6: SMA 50 below price by 0% to 10%
    dist_from_sma50_pct = (close - sma50) / sma50 if sma50 > 0 else 0.0
    if dist_from_sma50_pct < 0.0 or dist_from_sma50_pct > 0.10: return None
    
    # Rule 7: SMA 200 below price by >= 10%
    dist_from_sma200_pct = (close - sma200) / sma200 if sma200 > 0 else 0.0
    if dist_from_sma200_pct < 0.10: return None
    
    # Rule 8: SMA 50 >= SMA 200
    if sma50 < sma200: return None
    
    # Rule 9: Volume Change > 10% (vs prior day or 21-day average)
    vol_chg_prior = (volume - prev_volume) / prev_volume if prev_volume > 0 else 0.0
    vol_chg_ma = (volume - vol_sma21) / vol_sma21 if vol_sma21 > 0 else 0.0
    if vol_chg_prior <= 0.10 and vol_chg_ma <= 0.10: return None
    
    # Rule 10: EMA 10 >= EMA 21
    if ema10 < ema21: return None
    
    # Rule 12: SMA 150 >= SMA 200
    if sma150 < sma200: return None
    
    # Rule 13: SMA 50 >= SMA 150
    if sma50 < sma150: return None
    
    # Rule 3: Performance YTD > +8.0%
    current_year = df.index[-1].year
    ytd_bars = df[df.index.year == current_year]
    if len(ytd_bars) >= 2:
        ytd_open = float(ytd_bars['Open'].iloc[0])
        ytd_perf_pct = (close - ytd_open) / ytd_open
    else:
        six_mo_px = float(df['Close'].iloc[-min(126, len(df))])
        ytd_perf_pct = (close - six_mo_px) / six_mo_px
    if ytd_perf_pct <= 0.08: return None
    
    # -------------------------------------------------------------
    # 2. SENIOR STRATEGIST QUALITY & READINESS EVALUATION
    # -------------------------------------------------------------
    # Minervini 52-Week High Proximity (Within 25% of High)
    dist_from_52w_high_pct = (high52w - close) / high52w if high52w > 0 else 0.0
    is_near_52w_high = dist_from_52w_high_pct <= 0.25
    
    # Slopes
    ema21_slope_desc = "Strongly Upward" if slope_ema21 >= 1.5 else ("Upward" if slope_ema21 > 0.0 else ("Flat / Curving" if slope_ema21 >= -0.2 else "Downward"))
    sma50_slope_desc = "Strongly Upward" if slope_sma50 >= 1.0 else ("Upward" if slope_sma50 >= 0.0 else ("Flat" if slope_sma50 >= -0.2 else "Downward"))
    
    # Distance to Moving Averages
    dist_to_ema21_pct = (close - ema21) / ema21 * 100.0
    dist_to_sma50_pct = (close - sma50) / sma50 * 100.0
    
    # Buy Zone Geometry
    if abs(dist_to_ema21_pct) <= 2.0 and dist_to_sma50_pct <= 3.5:
        buy_zone_type = "Dual Convergence Sweet Spot"
    elif abs(dist_to_ema21_pct) <= 2.0:
        buy_zone_type = "21 EMA Prime Zone"
    elif dist_to_sma50_pct <= 3.0:
        buy_zone_type = "50 SMA Demand Zone"
    elif dist_to_ema21_pct <= 4.2:
        buy_zone_type = "Upper Pullback Zone"
    else:
        buy_zone_type = "Extended (>4.2%)"
        
    # Multi-Timeframe Demand & Sell Zones
    mtf_zones = calculate_multitimeframe_demand_zones(df)
    
    # 30-Day Swing Structure
    swing_info = analyze_swing_structure(df, window_bars=30)
    
    # Volume Accumulation Pocket Pivot Flag
    vol_surge_green = (vol_chg_prior > 0.10 or vol_chg_ma > 0.10) and (close > prev_close and close >= open_px)
    vol_surge_tag = "YES (Green Pocket Pivot)" if vol_surge_green else ("YES (Volume Surge)" if (vol_chg_prior > 0.10 or vol_chg_ma > 0.10) else "NO")
    
    # Setup Horizon & Actionability Classification (The User's Core Need)
    # Tier 1: Trigger-Ready (0-3 Days / This Week)
    # Tier 2: On-Deck (1-2 Weeks)
    # Tier 3: Base Formation (2-3 Weeks)
    if (abs(dist_to_ema21_pct) <= 2.0 or dist_to_sma50_pct <= 2.5) and (mtf_zones['daily_demand'] == "YES" or mtf_zones['weekly_demand'] == "YES") and slope_ema21 >= -0.2:
        setup_horizon = "TIER 1: TRIGGER-READY (THIS WEEK / 0-3d)"
        readiness_badge = "TRIGGER READY"
    elif dist_to_ema21_pct <= 4.2 and swing_info.get('higher_low', False):
        setup_horizon = "TIER 2: ON-DECK (1-2 WEEKS)"
        readiness_badge = "ON DECK"
    else:
        setup_horizon = "TIER 3: BASE FORMATION (2-3 WEEKS)"
        readiness_badge = "BASE FORMING"
        
    # IBD Relative Strength Composite vs SPY
    rs_score = 50.0
    if spy_df is not None and len(spy_df) >= 200:
        try:
            spy_c = spy_df['Close']
            s_curr, s_63, s_126, s_189, s_252 = (
                close, float(df['Close'].iloc[-min(63, len(df))]),
                float(df['Close'].iloc[-min(126, len(df))]),
                float(df['Close'].iloc[-min(189, len(df))]),
                float(df['Close'].iloc[-min(252, len(df))])
            )
            stock_weighted = (
                0.40 * (s_curr / s_63 - 1) +
                0.20 * (s_63 / s_126 - 1) +
                0.20 * (s_126 / s_189 - 1) +
                0.20 * (s_189 / s_252 - 1)
            )
            spy_curr = float(spy_c.iloc[-1])
            spy_252 = float(spy_c.iloc[-min(252, len(spy_c))])
            bench_weighted = (spy_curr / spy_252) - 1.0
            rs_score = round(max(1.0, min(99.0, 50.0 + ((stock_weighted - bench_weighted) * 150.0))), 1)
        except Exception:
            rs_score = 50.0
            
    # Institutional Quality Score (IQS: 0 to 100)
    pts_trend = 0
    if ema10 > ema21 > sma50 > sma150 > sma200: pts_trend += 15
    if slope_ema21 > 0: pts_trend += 8
    if slope_sma50 >= 0: pts_trend += 7
    
    pts_zone = 0
    if buy_zone_type == "Dual Convergence Sweet Spot": pts_zone += 25
    elif buy_zone_type == "21 EMA Prime Zone": pts_zone += 20
    elif buy_zone_type == "50 SMA Demand Zone": pts_zone += 18
    elif buy_zone_type == "Upper Pullback Zone": pts_zone += 10
    else: pts_zone += 2
    
    pts_swing = 0
    if swing_info.get('higher_low', False): pts_swing += 12
    if swing_info.get('contraction', False): pts_swing += 8
    
    pts_vol = 0
    rvol = volume / vol_sma21 if vol_sma21 > 0 else 1.0
    if rvol >= 1.5: pts_vol += 10
    elif rvol >= 1.1: pts_vol += 7
    else: pts_vol += 4
    if close > prev_close: pts_vol += 5
    
    pts_rs = 0
    if rs_score >= 80: pts_rs += 6
    elif rs_score >= 65: pts_rs += 4
    if is_near_52w_high: pts_rs += 4
    
    # Priority bonus for Tier 1 Trigger Ready setups
    tier_bonus = 10 if "TIER 1" in setup_horizon else (5 if "TIER 2" in setup_horizon else 0)
    iqs_total = min(100, pts_trend + pts_zone + pts_swing + pts_vol + pts_rs + tier_bonus)
    
    if iqs_total >= 90:
        star_rating = "⭐⭐⭐⭐⭐ (Elite A+)"
        action_verdict = "PRIME BUY SETUP"
    elif iqs_total >= 80:
        star_rating = "⭐⭐⭐⭐ (Grade A High Conviction)"
        action_verdict = "HIGH WATCHLIST PRIORITY"
    elif iqs_total >= 70:
        star_rating = "⭐⭐⭐ (Grade B+ Developing)"
        action_verdict = "ACCUMULATION WATCH"
    else:
        star_rating = "⭐⭐ (Grade B)"
        action_verdict = "SECONDARY WATCH"
        
    # Automated Trade Plan Parameters
    # If Tier 1: Enter at current close (or limit at 21 EMA)
    # If Tier 2: Projected Entry is at the 21 EMA support level
    if "TIER 1" in setup_horizon:
        suggested_entry = round(close, 2)
    else:
        suggested_entry = round(ema21, 2)
        
    raw_sl = suggested_entry - (2.0 * atr14)
    min_sl = suggested_entry * 0.90  # Max 10% risk
    max_sl = suggested_entry * 0.95  # Min 5% risk
    initial_sl = round(min(max_sl, max(min_sl, raw_sl)), 2)
    risk_dollars = round(suggested_entry - initial_sl, 2)
    risk_pct = round((risk_dollars / suggested_entry) * 100.0, 1) if suggested_entry > 0 else 7.0
    
    target_1 = round(suggested_entry * 1.05, 2)
    target_2 = round(suggested_entry * 1.10, 2)
    target_3 = round(suggested_entry * 1.15, 2)
    risk_reward = round((target_2 - suggested_entry) / risk_dollars, 2) if risk_dollars > 0 else 1.6
    
    return {
        'symbol': symbol,
        'category': category,
        'setup_horizon': setup_horizon,
        'readiness_badge': readiness_badge,
        'close': close,
        'ytd_perf_pct': round(ytd_perf_pct * 100.0, 1),
        'vol_100d_k': round(vol_sma100 / 1000.0, 1),
        'rvol': round(rvol, 2),
        'dist_to_ema21_pct': round(dist_to_ema21_pct, 1),
        'dist_to_sma50_pct': round(dist_to_sma50_pct, 1),
        'dist_to_sma200_pct': round(dist_from_sma200_pct * 100.0, 1),
        'dist_from_52w_high_pct': round(dist_from_52w_high_pct * 100.0, 1),
        'dist_from_52w_low_pct': round(dist_from_52w_low_pct * 100.0, 1),
        'slope_ema21': round(slope_ema21, 2),
        'slope_sma50': round(slope_sma50, 2),
        'ema21_slope_desc': ema21_slope_desc,
        'sma50_slope_desc': sma50_slope_desc,
        'buy_zone_type': buy_zone_type,
        'daily_demand_zone': mtf_zones['daily_demand'],
        'weekly_demand_zone': mtf_zones['weekly_demand'],
        'monthly_demand_zone': mtf_zones['monthly_demand'],
        'sell_zone': mtf_zones['sell_zone'],
        'volume_surge_tag': vol_surge_tag,
        'swing_higher_low': "YES (SL2 >= SL1)" if swing_info.get('higher_low') else "NO",
        'swing_contraction': "YES (VCP)" if swing_info.get('contraction') else "NO",
        'sl1': round(swing_info.get('sl1', 0.0), 2),
        'sl1_date': swing_info.get('sl1_date', 'N/A'),
        'sl2': round(swing_info.get('sl2', 0.0), 2),
        'sl2_date': swing_info.get('sl2_date', 'N/A'),
        'sh1': round(swing_info.get('sh1', 0.0), 2),
        'sh1_date': swing_info.get('sh1_date', 'N/A'),
        'sh2': round(swing_info.get('sh2', 0.0), 2),
        'sh2_date': swing_info.get('sh2_date', 'N/A'),
        'rs_score': rs_score,
        'iqs_score': iqs_total,
        'star_rating': star_rating,
        'action_verdict': action_verdict,
        'suggested_entry': suggested_entry,
        'initial_stop_loss': initial_sl,
        'risk_pct': risk_pct,
        'target_1': target_1,
        'target_2': target_2,
        'target_3': target_3,
        'risk_reward': risk_reward
    }

# ================================================================================
# 5. PUBLICATION-QUALITY CANDLESTICK CHART GENERATOR
# ================================================================================

def generate_candlestick_chart(symbol: str, df: pd.DataFrame, cand_data: Dict[str, Any],
                               output_path: Optional[str] = None, show: bool = False):
    """
    Renders an institutional 35-day daily candlestick chart:
    - EMA10 (Cyan), EMA21 (Gold), SMA50 (Magenta), SMA200 (Dark Red dashed)
    - Shaded Daily Demand Zone band
    - Swing Lows (SL1, SL2) and Swing Highs (SH1, SH2) plotted with markers
    - Annotated Trade Execution Levels (Planned Entry, Stop Loss, Target 1, Target 2)
    - Setup Horizon Banner (Tier 1: Trigger Ready vs Tier 2: On-Deck)
    """
    if df is None or len(df) < 35:
        return
        
    sub = df.iloc[-35:].copy()
    fig, ax = plt.subplots(figsize=(13, 6.5), facecolor='#0d1117')
    ax.set_facecolor('#161b22')
    
    # 1. Candlestick Bars
    width = 0.6
    up = sub[sub['Close'] >= sub['Open']]
    down = sub[sub['Close'] < sub['Open']]
    
    ax.bar(up.index, up['Close'] - up['Open'], width, bottom=up['Open'], color='#00e676', edgecolor='#00e676', zorder=3)
    ax.vlines(up.index, up['Low'], up['High'], color='#00e676', linewidth=1.2, zorder=2)
    
    ax.bar(down.index, down['Close'] - down['Open'], width, bottom=down['Open'], color='#ff5252', edgecolor='#ff5252', zorder=3)
    ax.vlines(down.index, down['Low'], down['High'], color='#ff5252', linewidth=1.2, zorder=2)
    
    # 2. Moving Averages
    ax.plot(sub.index, sub['EMA10'], color='#00e5ff', label='10 EMA', linewidth=1.4, zorder=4)
    ax.plot(sub.index, sub['EMA21'], color='#ffd700', label='21 EMA (Prime Support)', linewidth=2.0, zorder=4)
    ax.plot(sub.index, sub['SMA50'], color='#e040fb', label='50 SMA (Institutional Demand)', linewidth=1.8, zorder=4)
    if 'SMA200' in sub.columns and not pd.isna(sub['SMA200'].iloc[-1]):
        ax.plot(sub.index, sub['SMA200'], color='#ff1744', label='200 SMA (Macro Baseline)', linewidth=1.5, linestyle='--', zorder=4)
        
    # 3. Daily Demand Zone Shaded Band (from 21d low to 21d low * 1.035)
    low_21 = float(sub['Low'].min())
    demand_top = low_21 * 1.035
    ax.axhspan(low_21, demand_top, color='#00e676', alpha=0.15, label='Daily Demand Zone (<=3.5% above 21d low)', zorder=1)
    
    # 4. Annotate Swing Lows and Highs
    sl1_val = cand_data.get('sl1', 0.0)
    sl2_val = cand_data.get('sl2', 0.0)
    sh1_val = cand_data.get('sh1', 0.0)
    sh2_val = cand_data.get('sh2', 0.0)
    
    if sl1_val > 0:
        ax.scatter([sub.index[-12]], [sl1_val], color='#00e676', s=90, marker='^', zorder=5)
        ax.text(sub.index[-12], sl1_val * 0.985, f"SL1: ${sl1_val:.2f}", color='#00e676', fontsize=8, ha='center', weight='bold')
    if sl2_val > 0:
        ax.scatter([sub.index[-4]], [sl2_val], color='#00e676', s=110, marker='^', zorder=5)
        ax.text(sub.index[-4], sl2_val * 0.985, f"SL2: ${sl2_val:.2f}", color='#00e676', fontsize=8, ha='center', weight='bold')
        
    if sh1_val > 0:
        ax.scatter([sub.index[-18]], [sh1_val], color='#ff5252', s=90, marker='v', zorder=5)
        ax.text(sub.index[-18], sh1_val * 1.01, f"SH1: ${sh1_val:.2f}", color='#ff5252', fontsize=8, ha='center', weight='bold')
    if sh2_val > 0:
        ax.scatter([sub.index[-8]], [sh2_val], color='#ff5252', s=110, marker='v', zorder=5)
        ax.text(sub.index[-8], sh2_val * 1.01, f"SH2: ${sh2_val:.2f}", color='#ff5252', fontsize=8, ha='center', weight='bold')
        
    # 5. Projected Execution Lines
    entry = cand_data.get('suggested_entry', float(sub['Close'].iloc[-1]))
    stop = cand_data.get('initial_stop_loss', entry * 0.93)
    t1 = cand_data.get('target_1', entry * 1.05)
    t2 = cand_data.get('target_2', entry * 1.10)
    
    ax.axhline(entry, color='#00e5ff', linestyle='--', linewidth=1.5, label=f"Projected Entry: ${entry:.2f}")
    ax.axhline(stop, color='#ff1744', linestyle='--', linewidth=1.5, label=f"Stop Loss: ${stop:.2f} (-{cand_data.get('risk_pct', 7.0)}%)")
    ax.axhline(t1, color='#69f0ae', linestyle=':', linewidth=1.2, label=f"Target 1 (+5%): ${t1:.2f}")
    ax.axhline(t2, color='#ffd700', linestyle=':', linewidth=1.2, label=f"Target 2 (+10%): ${t2:.2f} (R:R {cand_data.get('risk_reward', 1.6)}:1)")
    
    # 6. Styling, Grid, & Titles
    ax.grid(True, color='#21262d', linestyle='--', alpha=0.6)
    ax.tick_params(colors='#8b949e', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#30363d')
        
    category_badge = f"[{cand_data.get('category', 'INDEX')}]"
    horizon_text = cand_data.get('setup_horizon', 'TIER 1')
    iqs = cand_data.get('iqs_score', 85)
    stars = cand_data.get('star_rating', '⭐⭐⭐⭐')
    
    title_main = f"{symbol} {category_badge} — {horizon_text} | IQS: {iqs}/100 {stars}"
    subtitle = f"Buy Zone: {cand_data.get('buy_zone_type', '21 EMA')} | Daily Demand: {cand_data.get('daily_demand_zone')} | Weekly Demand: {cand_data.get('weekly_demand_zone')} | Vol Pocket Pivot: {cand_data.get('volume_surge_tag')}"
    
    plt.suptitle(title_main, color='#f0f6fc', fontsize=12, fontweight='bold', y=0.98)
    plt.title(subtitle, color='#8b949e', fontsize=9, pad=8)
    
    ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='#c9d1d9', loc='upper left', fontsize=8, ncol=2)
    
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()

# ================================================================================
# 6. MULTI-SHEET FORMATTED EXCEL WORKBOOK GENERATOR
# ================================================================================

def export_screener_to_excel(results: List[Dict], output_path: str = "weekly_swing_screener_results.xlsx"):
    """
    Exports screened candidates to a 6-sheet institutional Excel workbook:
    - Sheet 1: 'Index_Watchlist_Top_Setups' (Top setups from S&P 500, Nasdaq 100, Dow 30)
    - Sheet 2: 'Broader_Market_Alpha_Setups' (Top setups outside major indices)
    - Sheet 3: 'Trigger_Ready_This_Week' (Consolidated Tier 1 candidates ready for immediate bot execution)
    - Sheet 4: 'Multi_Timeframe_Demand_Matrix' (Daily, Weekly, Monthly demand/sell zone breakdown)
    - Sheet 5: 'All_Screened_Candidates' (Full quantitative dataset)
    - Sheet 6: 'Watchlist_TXT_Export' (Direct symbols list for config/watchlist.txt)
    """
    if not results:
        print("No candidates met screener criteria. Excel export skipped.")
        return
        
    wb = openpyxl.Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)
    
    # Styles
    navy_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    gold_fill = PatternFill(start_color="B28900", end_color="B28900", fill_type="solid")
    dark_green_fill = PatternFill(start_color="1E4620", end_color="1E4620", fill_type="solid")
    purple_fill = PatternFill(start_color="4A154B", end_color="4A154B", fill_type="solid")
    slate_fill = PatternFill(start_color="333F48", end_color="333F48", fill_type="solid")
    
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=10, bold=True)
    regular_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    headers_primary = [
        "Rank", "Symbol", "Category", "Setup Horizon", "Price ($)", "IQS Score", "Star Rating",
        "Action Verdict", "Buy Zone", "Dist EMA21 (%)", "Dist SMA50 (%)", "EMA21 Slope",
        "SMA50 Slope", "Daily Demand", "Weekly Demand", "Volume Pocket Pivot",
        "Higher Low (SL2>=SL1)", "VCP Contraction", "SL1 ($)", "SL2 ($)", "SH1 ($)", "SH2 ($)",
        "IBD RS", "Projected Entry ($)", "Stop Loss ($)", "Risk (%)", "Target 1 (+5%)",
        "Target 2 (+10%)", "Target 3 (+15%)", "Risk/Reward"
    ]
    
    def populate_sheet(ws, candidates, title_fill):
        ws.append(headers_primary)
        for col_num in range(1, len(headers_primary) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = title_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        for idx, r in enumerate(candidates, 1):
            row_vals = [
                idx, r['symbol'], r['category'], r['setup_horizon'], r['close'], r['iqs_score'],
                r['star_rating'], r['action_verdict'], r['buy_zone_type'], r['dist_to_ema21_pct'],
                r['dist_to_sma50_pct'], r['ema21_slope_desc'], r['sma50_slope_desc'],
                r['daily_demand_zone'], r['weekly_demand_zone'], r['volume_surge_tag'],
                r['swing_higher_low'], r['swing_contraction'], r['sl1'], r['sl2'],
                r['sh1'], r['sh2'], r['rs_score'], r['suggested_entry'], r['initial_stop_loss'],
                r['risk_pct'], r['target_1'], r['target_2'], r['target_3'], r['risk_reward']
            ]
            ws.append(row_vals)
            curr_row = ws.max_row
            for c_idx in range(1, len(row_vals) + 1):
                c = ws.cell(row=curr_row, column=c_idx)
                c.font = regular_font
                c.border = thin_border
                c.alignment = Alignment(horizontal="center" if c_idx in [1, 2, 3, 4, 14, 15, 16, 17, 18] else "right")
                
    # Sort candidates
    sorted_all = sorted(results, key=lambda x: (
        0 if "TIER 1" in x['setup_horizon'] else (1 if "TIER 2" in x['setup_horizon'] else 2),
        -x['iqs_score']
    ))
    
    index_candidates = [c for c in sorted_all if c['category'] == "INDEX"]
    broader_candidates = [c for c in sorted_all if c['category'] == "BROADER_MARKET"]
    trigger_ready = [c for c in sorted_all if "TIER 1" in c['setup_horizon']]
    
    # Sheet 1: Index Watchlist
    ws1 = wb.create_sheet("Index_Watchlist_Top_Setups")
    populate_sheet(ws1, index_candidates[:30], navy_fill)
    
    # Sheet 2: Broader Market Alpha Watchlist
    ws2 = wb.create_sheet("Broader_Market_Alpha_Setups")
    populate_sheet(ws2, broader_candidates[:30], gold_fill)
    
    # Sheet 3: Trigger Ready This Week
    ws3 = wb.create_sheet("Trigger_Ready_This_Week")
    populate_sheet(ws3, trigger_ready[:30] if trigger_ready else sorted_all[:15], dark_green_fill)
    
    # Sheet 4: Multi-Timeframe Demand Matrix
    ws4 = wb.create_sheet("Multi_Timeframe_Demand_Matrix")
    headers_demand = [
        "Rank", "Symbol", "Category", "Setup Horizon", "Price ($)", "Daily Demand",
        "Weekly Demand", "Monthly Demand", "Sell Zone", "Dist to EMA21 (%)",
        "Dist to SMA50 (%)", "Volume Surge Tag", "SL2 >= SL1", "VCP Contraction", "IQS Score"
    ]
    ws4.append(headers_demand)
    for col_num in range(1, len(headers_demand) + 1):
        c = ws4.cell(row=1, column=col_num)
        c.fill = purple_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        
    for idx, r in enumerate(sorted_all, 1):
        ws4.append([
            idx, r['symbol'], r['category'], r['setup_horizon'], r['close'],
            r['daily_demand_zone'], r['weekly_demand_zone'], r['monthly_demand_zone'],
            r['sell_zone'], r['dist_to_ema21_pct'], r['dist_to_sma50_pct'],
            r['volume_surge_tag'], r['swing_higher_low'], r['swing_contraction'], r['iqs_score']
        ])
        
    # Sheet 5: All Screened Candidates
    ws5 = wb.create_sheet("All_Screened_Candidates")
    populate_sheet(ws5, sorted_all, slate_fill)
    
    # Sheet 6: Watchlist TXT Export
    ws6 = wb.create_sheet("Watchlist_TXT_Export")
    ws6.cell(row=1, column=1, value="Symbol (Ready to Copy to config/watchlist.txt)").font = header_font
    ws6.cell(row=1, column=1).fill = navy_fill
    ws6.cell(row=1, column=2, value="Category").font = header_font
    ws6.cell(row=1, column=2).fill = navy_fill
    ws6.cell(row=1, column=3, value="Setup Horizon").font = header_font
    ws6.cell(row=1, column=3).fill = navy_fill
    ws6.cell(row=1, column=4, value="IQS Score").font = header_font
    ws6.cell(row=1, column=4).fill = navy_fill
    
    # Top 30 combined actionable symbols
    top_export = sorted_all[:30]
    for r in top_export:
        ws6.append([r['symbol'], r['category'], r['setup_horizon'], r['iqs_score']])
        
    # Auto-fit columns
    for ws in [ws1, ws2, ws3, ws4, ws5, ws6]:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or '')
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
            
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    print(f"📊 6-Sheet Institutional Excel workbook successfully exported to: {output_path}")

def export_watchlist_txt(results: List[Dict], output_txt: str = "watchlist.txt", top_n: int = 30):
    """Exports clean symbol list for Single_Buy2.0 config/watchlist.txt"""
    sorted_all = sorted(results, key=lambda x: (
        0 if "TIER 1" in x['setup_horizon'] else (1 if "TIER 2" in x['setup_horizon'] else 2),
        -x['iqs_score']
    ))
    top_syms = [r['symbol'] for r in sorted_all[:top_n]]
    os.makedirs(os.path.dirname(os.path.abspath(output_txt)), exist_ok=True)
    with open(output_txt, "w") as f:
        for s in top_syms:
            f.write(f"{s}\n")
    print(f"📝 Plain-text watchlist ({len(top_syms)} symbols) exported to: {output_txt}")

# ================================================================================
# 7. SCANNER ORCHESTRATION PIPELINE
# ================================================================================

def run_screener_pipeline(universe_mode: str = "combined",
                          output_excel: str = "weekly_swing_screener_results.xlsx",
                          output_txt: str = "watchlist.txt",
                          update_watchlist: bool = False,
                          top_n_watchlist: int = 30,
                          generate_charts: bool = False,
                          max_charts: int = 10) -> List[Dict]:
    """Runs complete end-to-end scanning, ranking, charting, and multi-sheet export"""
    print("=" * 80)
    print(f"🏛️ INSTITUTIONAL WEEKLY SWING TRADING RADAR (MODE: {universe_mode.upper()})")
    print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 80)
    
    symbols, category_map = get_segmented_universe(universe_mode)
    print(f"Total symbols in universe: {len(symbols)}")
    index_cnt = sum(1 for s in symbols if category_map.get(s) == "INDEX")
    broader_cnt = sum(1 for s in symbols if category_map.get(s) == "BROADER_MARKET")
    print(f"  • Inside Major Indices: {index_cnt}")
    print(f"  • Outside Major Indices (Broader Growth Alpha): {broader_cnt}")
    
    # SPY benchmark for RS calculation
    spy_df = None
    try:
        spy_raw = yf.download("SPY", period="2y", interval="1d", progress=False)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = spy_raw.columns.get_level_values(0)
        spy_df = spy_raw.dropna()
    except Exception:
        pass
        
    candidates = []
    batch_size = 60
    stored_dfs = {}
    
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        print(f"Scanning batch {i+1} to {min(i+len(batch), len(symbols))} of {len(symbols)}...")
        try:
            data = yf.download(batch, period="2y", interval="1d", group_by="ticker", threads=True, progress=False)
        except Exception as e:
            print(f"Batch fetch error: {e}")
            continue
            
        for sym in batch:
            try:
                df = None
                if len(batch) == 1:
                    df = data.copy()
                elif sym in data.columns.levels[0]:
                    df = data[sym].dropna()
                    
                if df is not None and len(df) >= 200:
                    df_ind = calculate_screener_indicators(df)
                    if df_ind is not None:
                        cat = category_map.get(sym, "INDEX")
                        eval_res = evaluate_screener_candidate(sym, df_ind, category=cat, spy_df=spy_df)
                        if eval_res:
                            candidates.append(eval_res)
                            if generate_charts and len(stored_dfs) < max_charts:
                                stored_dfs[sym] = (df_ind, eval_res)
            except Exception:
                continue
                
    print("=" * 80)
    print(f"Scanning Complete! Total Qualifying Candidates: {len(candidates)}")
    t1_cnt = sum(1 for c in candidates if "TIER 1" in c['setup_horizon'])
    t2_cnt = sum(1 for c in candidates if "TIER 2" in c['setup_horizon'])
    t3_cnt = sum(1 for c in candidates if "TIER 3" in c['setup_horizon'])
    print(f"  • Tier 1 (Trigger-Ready This Week): {t1_cnt}")
    print(f"  • Tier 2 (On-Deck 1-2 Weeks): {t2_cnt}")
    print(f"  • Tier 3 (Base Formation 2-3 Weeks): {t3_cnt}")
    print("=" * 80)
    
    # Export Excel
    export_screener_to_excel(candidates, output_path=output_excel)
    
    # Export Watchlist TXT
    export_watchlist_txt(candidates, output_txt=output_txt, top_n=top_n_watchlist)
    
    # Optionally update Single_Buy2.0 live config/watchlist.txt
    if update_watchlist and candidates:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_cfg = os.path.join(project_root, "config", "watchlist.txt")
        export_watchlist_txt(candidates, output_txt=target_cfg, top_n=top_n_watchlist)
        print(f"✅ Automatically updated live bot config at: {target_cfg}")
        
    # Generate Candlestick Charts if requested
    if generate_charts and stored_dfs:
        chart_dir = os.path.join(os.path.dirname(os.path.abspath(output_excel)), "charts")
        os.makedirs(chart_dir, exist_ok=True)
        print(f"📈 Generating {len(stored_dfs)} Candlestick Charts in {chart_dir}...")
        for sym, (df_ind, cand_data) in stored_dfs.items():
            chart_file = os.path.join(chart_dir, f"{sym}_swing_setup.png")
            generate_candlestick_chart(sym, df_ind, cand_data, output_path=chart_file)
        print(f"✅ Charts saved to: {chart_dir}")
        
    return candidates

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Institutional Weekly Swing Trading Screener & Radar")
    parser.add_argument("--universe", type=str, default="combined", choices=["combined", "indices", "broader", "dow30", "nasdaq100", "sp500"])
    parser.add_argument("--output", type=str, default="weekly_swing_screener_results.xlsx")
    parser.add_argument("--output-txt", type=str, default="watchlist.txt")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--update-watchlist", action="store_true")
    parser.add_argument("--charts", action="store_true")
    parser.add_argument("--max-charts", type=int, default=10)
    args = parser.parse_args()
    
    run_screener_pipeline(
        universe_mode=args.universe,
        output_excel=args.output,
        output_txt=args.output_txt,
        update_watchlist=args.update_watchlist,
        top_n_watchlist=args.top,
        generate_charts=args.charts,
        max_charts=args.max_charts
    )
