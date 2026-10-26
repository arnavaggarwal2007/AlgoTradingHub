"""
================================================================================
INSTITUTIONAL WEEKLY SWING TRADING SCREENER & RADAR (V3.5.1)
================================================================================
Senior Quantitative Strategist Architecture (15+ Years Multi-Cycle Prop Experience)

Key Capabilities:
1. Dual Universe Architecture:
   - LIST A: Inside Major Indices (S&P 500, Nasdaq 100, Dow 30)
   - LIST B: Outside Major Indices (Broader Market High-Growth Mid-Cap Alpha)
2. Complete 13 TradingView Screener Rules (Trend, Stacking, Clearance, Volume)
3. Mark Minervini 52-Week High Clearance (Within 25% of 52w High)
4. Moving Average Slope & Curvature Verification (Flat, Turning Up, Strongly Upward)
5. Setup Horizon & Actionability Classification (Configurable Top N, Default: 50):
   - TIER 1: TRIGGER-READY (0-3 Days / This Week) -> At 21 EMA / 50 SMA Demand Zone
   - TIER 2: ON-DECK (1-2 Weeks) -> Pulling back to 21 EMA with Higher Low (SL2 >= SL1)
   - TIER 3: BASE FORMATION (2-3 Weeks) -> Consolidating near highs
6. 5-Tier Letter Grade Rating System (From Top A+ Setup to B-):
   - Grade A+ (IQS 90-100): ⭐⭐⭐⭐⭐ (Elite A+ / Prime Buy Setup)
   - Grade A  (IQS 80-89):  ⭐⭐⭐⭐ (Grade A High Conviction)
   - Grade B+ (IQS 70-79):  ⭐⭐⭐+ (Grade B+ Setup Developing)
   - Grade B  (IQS 60-69):  ⭐⭐⭐ (Grade B Standard Swing)
   - Grade B- (IQS 50-59):  ⭐⭐ (Grade B- Base Monitor / Reserve)
7. 30-Day Swing Pivot Structure (SL1, SL2, SH1, SH2, Higher Lows & VCP Contraction)
8. Multi-Timeframe Demand Zone Matrix (Daily, Weekly, Monthly Demand & Sell Zones)
9. Volume Surge & Green Pocket Pivot Accumulation Tracking
10. IBD Relative Strength Composite (0-100)
11. Automated Trade Execution Plan (Entry, Stop Loss bounded 5-10%, Targets 1/2/3, R:R)
12. Publication-Quality Candlestick Chart Generator (with MAs, Demand Bands, Swings, Plans)
13. Formatted 6-Sheet Excel Workbook (.xlsx) & Direct watchlist.txt Export (Default 50 Setups)
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
import logging
import warnings
warnings.filterwarnings('ignore')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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
    "CTSH", "DASH", "DDOG", "DLTR", "DXCM", "APP", "EXC", "FANG", "FAST", "FTNT",
    "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HON", "IDXX", "ILMN", "INTC", "INTU",
    "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "LULU", "MAR", "MCHP", "MDB",
    "MDLZ", "MELI", "META", "MNST", "MRNA", "MRVL", "MSFT", "MU", "NFLX", "NVDA",
    "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR",
    "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS", "TEAM", "TMUS", "TSLA",
    "TTD", "TXN", "VRSK", "VRTX", "ARM", "WDAY", "XEL", "ZS"
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

BROADER_MARKET_SYMBOLS = [
    "NET", "SNOW", "HUBS", "ESTC", "PATH", "DOCN", "MSTR", "TOST", "DUOL", "IOT",
    "SYM", "TEM", "ALAB", "VRT", "RBRK", "TWLO", "SHOP", "SE", "BILL", "AFRM",
    "UPST", "HOOD", "SOFI", "COIN", "DT", "GWRE", "MNDY", "PEGA", "PCTY", "PAYC",
    "MANH", "TYL", "PTC", "APPF", "BL", "TENB", "VRNS", "OKTA", "FROG",
    "U", "RELY", "GH", "TSM", "SMCI", "MPWR", "ALGM", "COHR",
    "AMBA", "POWI", "RMBS", "ACLS", "DIOD", "LSCC", "MTSI", "TER", "ENTG", "MKSI",
    "FORM", "AMKR", "CAMT", "ICHR", "UCTT", "VECO", "INSW", "TNK", "LPG",
    "FRO", "STNG", "GSL", "ZIM", "VIST", "EQT", "LNG", "FSLR", "NXT", "AR",
    "RRC", "CHRD", "SM", "PR", "MTDR", "MGY", "CRK", "CNX", "DVN", "APA",
    "OVV", "OXY", "PAGP", "OKE", "PWR", "EME", "FIX", "BLDR",
    "IBP", "ACM", "J", "HUBB", "NVT", "GWW", "FDX", "SAIA", "XPO", "WSO",
    "TTC", "AGCO", "SITE", "TREX", "OSK", "CR", "RBC", "AIT", "GGG",
    "LECO", "MIDD", "CW", "HEI", "HII", "HWM", "ATI", "NDSN", "NSP", "TILE",
    "CELH", "ONON", "BIRK", "DECK", "SHAK", "CAVA", "WING", "BROS", "SG", "BOOT",
    "CROX", "TSCO", "FIVE", "OLLI", "CHWY", "CART", "CAKE", "EAT", "DRI",
    "TXRH", "YUM", "DPZ", "PZZA", "BJRI", "PLAY", "LOCO", "ARCO", "DIN", "CHEF",
    "CNK", "IMAX", "ARGX", "ALNY", "BMRN", "CRSP", "BEAM", "NTRA", "RVMD", "KNSA",
    "AXSM", "INSM", "CYTK", "ARDX", "VKTX", "MDGL", "HALO", "INCY", "NBIX",
    "JAZZ", "IONS", "ALKS", "PODD", "PEN", "TFX", "EW", "WST",
    "CAH", "BDX", "BMY", "IMVT", "GKOS", "PHVS", "AXGN", "THG", "KKR", "APO",
    "ARES", "BX", "OWL", "HLNE", "STEP", "CG", "LPLA", "RJF", "IBKR", "TW",
    "VIRT", "PIPR", "MC", "EVR", "CNO", "BFH", "UMBF", "WSBC", "BUSE", "PK",
    "RHI", "FCF", "NBTB", "BPOP", "S", "CBSH", "HNGE", "HSIC", "ACT", "NSIT",
    "USB", "WT", "PFG", "LFST", "UBSI", "AIZ", "ALL", "VOYA", "ONB", "ASH",
    "CLBK", "CATY", "BEN", "IVZ", "NTAP", "GCMG", "MET", "EG", "NTRS", "VCTR",
    "NMIH", "TNET", "NOV", "TIGO", "MSGE", "ECPG", "ROIV", "CLMT", "CON", "AVT",
    "RGA", "FA", "AMP", "KFY", "CXW"
]


def parse_tradingview_export(filepath_or_content: str) -> List[str]:
    """
    Parses a TradingView export (CSV, TXT, or comma-separated string).
    Strips exchange prefixes (NASDAQ:NVDA -> NVDA) and header rows.
    """
    content = ""
    if os.path.exists(filepath_or_content):
        with open(filepath_or_content, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    else:
        content = filepath_or_content
        
    symbols = []
    lines = content.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        tokens = [t.strip().strip('"').strip("'") for t in line.split(",") if t.strip()]
        for token in tokens:
            if token.lower() in ['ticker', 'symbol', 'description', 'price', 'volume', 'name']:
                continue
            sym = token.split(":")[-1].strip().upper()
            if sym.isalpha() and 1 <= len(sym) <= 5:
                symbols.append(sym)
    return list(dict.fromkeys(symbols))

def get_segmented_universe(mode: str = "combined") -> Tuple[List[str], Dict[str, str]]:
    m = mode.lower().strip()
    category_map = {}
    index_set = set(DOW_30_SYMBOLS + NASDAQ_100_SYMBOLS + SP_500_CORE_SAMPLE)
    
    if m in ["indices", "combined", "sp500"]:
        try:
            import urllib.request
            import ssl
            import re
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                html = resp.read().decode("utf-8")
            raw_syms = re.findall(r'href="https://www\.nyse\.com/quote/XNYS:([A-Z\.]+)"', html)
            if not raw_syms:
                raw_syms = re.findall(r'<td><a rel="nofollow" class="external text" href="[^"]+">([A-Z\.\-]+)</a></td>', html)
            if raw_syms:
                index_set.update([s.replace(".", "-") for s in raw_syms if len(s) <= 5])
        except Exception:
            pass
            
    for s in index_set: category_map[s] = "INDEX"
    broader_set = set(BROADER_MARKET_SYMBOLS) - index_set
    for s in broader_set: category_map[s] = "BROADER_MARKET"
    
    if m == "indices": final_list = sorted(list(index_set))
    elif m == "broader": final_list = sorted(list(broader_set))
    elif m == "dow30": final_list = sorted(list(set(DOW_30_SYMBOLS)))
    elif m == "nasdaq100": final_list = sorted(list(set(NASDAQ_100_SYMBOLS)))
    elif m == "sp500": final_list = sorted(list(index_set))
    else: final_list = sorted(list(index_set | broader_set))
    return final_list, category_map

def get_screener_universe(universe_name: str = "combined") -> List[str]:
    """Compatibility helper returning ticker list for selected universe"""
    return get_segmented_universe(universe_name)[0]

# ================================================================================
# 2. VECTORIZED INDICATOR & MULTI-TIMEFRAME ENGINE
# ================================================================================

def calculate_screener_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df is None or len(df) < 200: return None
    df = df.copy()
    c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']
    
    df['EMA10'] = c.ewm(span=10, adjust=False).mean()
    df['EMA21'] = c.ewm(span=21, adjust=False).mean()
    df['SMA50'] = c.rolling(window=50).mean()
    df['SMA150'] = c.rolling(window=150).mean()
    df['SMA200'] = c.rolling(window=200).mean()
    
    df['VOL_SMA21'] = v.rolling(window=21).mean()
    df['VOL_SMA100'] = v.rolling(window=100).mean()
    
    df['HIGH_52W'] = h.rolling(window=min(252, len(df))).max()
    df['LOW_52W'] = l.rolling(window=min(252, len(df))).min()
    df['LOW_21'] = l.rolling(window=21).min()
    
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(window=14).mean()
    
    df['SLOPE_EMA21'] = ((df['EMA21'] - df['EMA21'].shift(5)) / df['EMA21'].shift(5)) * 100.0
    df['SLOPE_SMA50'] = ((df['SMA50'] - df['SMA50'].shift(10)) / df['SMA50'].shift(10)) * 100.0
    df['SLOPE_SMA200'] = ((df['SMA200'] - df['SMA200'].shift(20)) / df['SMA200'].shift(20)) * 100.0
    return df

def calculate_multitimeframe_demand_zones(df: pd.DataFrame) -> Dict[str, Any]:
    curr = df.iloc[-1]
    close, low, high = float(curr['Close']), float(curr['Low']), float(curr['High'])
    ema21 = float(curr['EMA21'])
    low21 = float(curr['LOW_21']) if 'LOW_21' in curr and not pd.isna(curr['LOW_21']) else low
    
    daily_demand = low <= (low21 * 1.035)
    
    weekly_demand, weekly_bullish = False, True
    try:
        df_w = df.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        if len(df_w) >= 21:
            w_c = float(df_w['Close'].iloc[-1])
            w_ema21 = float(df_w['Close'].ewm(span=21, adjust=False).mean().iloc[-1])
            w_low8 = float(df_w['Low'].iloc[-8:].min())
            weekly_bullish = w_c > w_ema21
            weekly_demand = (abs(w_c - w_ema21) / w_ema21 <= 0.03) or (w_c <= w_low8 * 1.05)
    except Exception:
        weekly_demand = daily_demand
        
    monthly_demand = False
    try:
        df_m = df.resample('ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        if len(df_m) >= 10:
            m_c = float(df_m['Close'].iloc[-1])
            m_ema10 = float(df_m['Close'].ewm(span=10, adjust=False).mean().iloc[-1])
            monthly_demand = (m_c > m_ema10) and (abs(m_c - m_ema10) / m_ema10 <= 0.06)
    except Exception:
        monthly_demand = True
        
    dist_ema21_pct = (close - ema21) / ema21 * 100.0
    c_range = max(high - low, 0.001)
    upper_wick = high - max(close, float(curr['Open']))
    is_overextended = dist_ema21_pct > 5.0
    is_shooting_star = (upper_wick / c_range >= 0.50) and (upper_wick / max(abs(close - float(curr['Open'])), 0.001) >= 2.0)
    
    sell_zone = "YES (Extended/Distribution Risk)" if (is_overextended or is_shooting_star) else "NO (Low-Risk Accumulation Area)"
    return {
        'daily_demand': "YES" if daily_demand else "NO",
        'weekly_demand': "YES" if weekly_demand else "NO",
        'monthly_demand': "YES" if monthly_demand else "NO",
        'weekly_bullish': weekly_bullish,
        'sell_zone': sell_zone
    }

# ================================================================================
# 3. 30-DAY SWING PIVOT STRUCTURE ANALYZER
# ================================================================================

def analyze_swing_structure(df: pd.DataFrame, window_bars: int = 30) -> Dict[str, Any]:
    if len(df) < window_bars + 2:
        return {'valid_structure': False, 'higher_low': False, 'contraction': False, 'sl1': 0.0, 'sl2': 0.0, 'sh1': 0.0, 'sh2': 0.0, 'sl1_date': 'N/A', 'sl2_date': 'N/A', 'sh1_date': 'N/A', 'sh2_date': 'N/A'}
    sub = df.iloc[-(window_bars + 2):].copy()
    highs, lows = [], []
    for i in range(1, len(sub) - 1):
        if sub['High'].iloc[i] > sub['High'].iloc[i-1] and sub['High'].iloc[i] > sub['High'].iloc[i+1]:
            highs.append((sub.index[i].strftime('%Y-%m-%d'), float(sub['High'].iloc[i])))
        if sub['Low'].iloc[i] < sub['Low'].iloc[i-1] and sub['Low'].iloc[i] < sub['Low'].iloc[i+1]:
            lows.append((sub.index[i].strftime('%Y-%m-%d'), float(sub['Low'].iloc[i])))
            
    higher_low, contraction = False, False
    sl1_val, sl2_val, sh1_val, sh2_val = 0.0, 0.0, 0.0, 0.0
    sl1_dt, sl2_dt, sh1_dt, sh2_dt = "N/A", "N/A", "N/A", "N/A"
    
    if len(lows) >= 2:
        sl1_dt, sl1_val = lows[-2]
        sl2_dt, sl2_val = lows[-1]
        higher_low = sl2_val >= (sl1_val * 0.995)
    if len(highs) >= 2:
        sh1_dt, sh1_val = highs[-2]
        sh2_dt, sh2_val = highs[-1]
        if sl1_val > 0 and sl2_val > 0:
            contraction = max(0.01, sh2_val - sl2_val) <= (max(0.01, sh1_val - sl1_val) * 1.05)
            
    return {
        'valid_structure': len(highs) >= 2 and len(lows) >= 2,
        'sh1': sh1_val, 'sh2': sh2_val, 'sl1': sl1_val, 'sl2': sl2_val,
        'sh1_date': sh1_dt, 'sh2_date': sh2_dt, 'sl1_date': sl1_dt, 'sl2_date': sl2_dt,
        'higher_low': higher_low, 'contraction': contraction
    }

# ================================================================================
# 4. CANDIDATE EVALUATION & 5-TIER LETTER GRADE CLASSIFIER (A+ TO B-)
# ================================================================================

def evaluate_screener_candidate(symbol: str, df: pd.DataFrame,
                                category: str = "INDEX",
                                spy_df: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
    if df is None or len(df) < 200: return None
    c_bar, p_bar = df.iloc[-1], df.iloc[-2]
    close, open_px, prev_close = float(c_bar['Close']), float(c_bar['Open']), float(p_bar['Close'])
    volume, prev_volume = float(c_bar['Volume']), float(p_bar['Volume'])
    
    ema10, ema21 = float(c_bar['EMA10']), float(c_bar['EMA21'])
    sma50, sma150, sma200 = float(c_bar['SMA50']), float(c_bar['SMA150']), float(c_bar['SMA200'])
    vol_sma21 = float(c_bar['VOL_SMA21']) if not pd.isna(c_bar['VOL_SMA21']) else volume
    vol_sma100 = float(c_bar['VOL_SMA100']) if not pd.isna(c_bar['VOL_SMA100']) else volume
    high52w, low52w = float(c_bar['HIGH_52W']), float(c_bar['LOW_52W'])
    atr14 = float(c_bar['ATR14']) if not pd.isna(c_bar['ATR14']) else close * 0.03
    slope_ema21 = float(c_bar['SLOPE_EMA21']) if not pd.isna(c_bar['SLOPE_EMA21']) else 0.0
    slope_sma50 = float(c_bar['SLOPE_SMA50']) if not pd.isna(c_bar['SLOPE_SMA50']) else 0.0
    
    # 13 TRADINGVIEW CRITERIA
    if close < 10.0: return None
    if vol_sma100 < 250000: return None
    if ema21 < sma50: return None
    if (close - low52w) / low52w < 0.15: return None
    dist_sma50 = (close - sma50) / sma50
    if dist_sma50 < 0.0 or dist_sma50 > 0.10: return None
    dist_sma200 = (close - sma200) / sma200
    if dist_sma200 < 0.10: return None
    if sma50 < sma200: return None
    vol_chg_p = (volume - prev_volume) / prev_volume if prev_volume > 0 else 0.0
    vol_chg_m = (volume - vol_sma21) / vol_sma21 if vol_sma21 > 0 else 0.0
    if vol_chg_p <= 0.10 and vol_chg_m <= 0.10: return None
    if ema10 < ema21: return None
    if sma150 < sma200: return None
    if sma50 < sma150: return None
    
    # YTD Perf
    c_yr = df.index[-1].year
    ytd_bars = df[df.index.year == c_yr]
    ytd_perf = (close - float(ytd_bars['Open'].iloc[0])) / float(ytd_bars['Open'].iloc[0]) if len(ytd_bars) >= 2 else (close - float(df['Close'].iloc[-min(126, len(df))])) / float(df['Close'].iloc[-min(126, len(df))])
    if ytd_perf <= 0.08: return None
    
    # Senior Strategist Checks
    off_52w_high = (high52w - close) / high52w
    is_near_52w_high = off_52w_high <= 0.25
    dist_ema21_pct = (close - ema21) / ema21 * 100.0
    dist_sma50_pct = (close - sma50) / sma50 * 100.0
    
    ema21_slope_desc = "Strongly Upward" if slope_ema21 >= 1.5 else ("Upward" if slope_ema21 > 0.0 else ("Flat / Curving" if slope_ema21 >= -0.2 else "Downward"))
    sma50_slope_desc = "Strongly Upward" if slope_sma50 >= 1.0 else ("Upward" if slope_sma50 >= 0.0 else ("Flat" if slope_sma50 >= -0.2 else "Downward"))
    
    if abs(dist_ema21_pct) <= 2.0 and dist_sma50_pct <= 3.5: buy_zone = "Dual Convergence Sweet Spot"
    elif abs(dist_ema21_pct) <= 2.0: buy_zone = "21 EMA Prime Zone"
    elif dist_sma50_pct <= 3.0: buy_zone = "50 SMA Demand Zone"
    elif dist_ema21_pct <= 4.2: buy_zone = "Upper Pullback Zone"
    else: buy_zone = "Extended (>4.2%)"
    
    mtf = calculate_multitimeframe_demand_zones(df)
    swings = analyze_swing_structure(df, window_bars=30)
    
    # Setup Horizon
    if (abs(dist_ema21_pct) <= 2.0 or dist_sma50_pct <= 2.5) and (mtf['daily_demand'] == "YES" or mtf['weekly_demand'] == "YES") and slope_ema21 >= -0.2:
        horizon = "TIER 1: TRIGGER-READY (THIS WEEK / 0-3d)"
        readiness_badge = "TRIGGER READY"
    elif dist_ema21_pct <= 4.2 and swings.get('higher_low', False):
        horizon = "TIER 2: ON-DECK (1-2 WEEKS)"
        readiness_badge = "ON DECK"
    else:
        horizon = "TIER 3: BASE FORMATION (2-3 WEEKS)"
        readiness_badge = "BASE FORMING"
        
    vol_surge_green = (vol_chg_p > 0.10 or vol_chg_m > 0.10) and (close > prev_close and close >= open_px)
    vol_tag = "YES (Green Pocket Pivot)" if vol_surge_green else ("YES (Volume Surge)" if (vol_chg_p > 0.10 or vol_chg_m > 0.10) else "NO")
    
    # IBD RS Rating
    rs_score = 50.0
    if spy_df is not None and len(spy_df) >= 200:
        try:
            stk_w = 0.4*(close/df['Close'].iloc[-63]-1) + 0.2*(df['Close'].iloc[-63]/df['Close'].iloc[-126]-1) + 0.2*(df['Close'].iloc[-126]/df['Close'].iloc[-189]-1) + 0.2*(df['Close'].iloc[-189]/df['Close'].iloc[-252]-1)
            spy_w = (spy_df['Close'].iloc[-1]/spy_df['Close'].iloc[-252]) - 1.0
            rs_score = round(max(1.0, min(99.0, 50.0 + (stk_w - spy_w)*150.0)), 1)
        except Exception: rs_score = 50.0
        
    # IQS Scoring (0-100)
    pts = 0
    if ema10 > ema21 > sma50 > sma150 > sma200: pts += 15
    if slope_ema21 > 0: pts += 8
    if slope_sma50 >= 0: pts += 7
    if buy_zone == "Dual Convergence Sweet Spot": pts += 25
    elif "21 EMA" in buy_zone: pts += 20
    elif "50 SMA" in buy_zone: pts += 18
    elif "Upper Pullback" in buy_zone: pts += 10
    else: pts += 2
    if swings.get('higher_low'): pts += 12
    if swings.get('contraction'): pts += 8
    rvol = volume / vol_sma21 if vol_sma21 > 0 else 1.0
    if rvol >= 1.5: pts += 10
    elif rvol >= 1.1: pts += 7
    else: pts += 4
    if close > prev_close: pts += 5
    if rs_score >= 80: pts += 6
    elif rs_score >= 65: pts += 4
    if is_near_52w_high: pts += 4
    if "TIER 1" in horizon: pts += 10
    elif "TIER 2" in horizon: pts += 5
    iqs = min(100, pts)
    
    # 5-Tier Letter Grade Rating (A+ to B-)
    if iqs >= 90:
        grade = "A+"
        star_rating = "⭐⭐⭐⭐⭐ (Grade A+ Elite)"
        action_verdict = "PRIME BUY SETUP"
    elif iqs >= 80:
        grade = "A"
        star_rating = "⭐⭐⭐⭐ (Grade A High Conviction)"
        action_verdict = "HIGH WATCHLIST PRIORITY"
    elif iqs >= 70:
        grade = "B+"
        star_rating = "⭐⭐⭐+ (Grade B+ Setup Developing)"
        action_verdict = "ACCUMULATION WATCH"
    elif iqs >= 60:
        grade = "B"
        star_rating = "⭐⭐⭐ (Grade B Standard Swing)"
        action_verdict = "SWING WATCH"
    else:
        grade = "B-"
        star_rating = "⭐⭐ (Grade B- Base Monitor)"
        action_verdict = "SECONDARY WATCH"
        
    # Automated Trade Plan
    entry = round(close if "TIER 1" in horizon else ema21, 2)
    sl = round(min(entry * 0.95, max(entry * 0.90, entry - 2.0 * atr14)), 2)
    risk_dlr = entry - sl
    risk_pct = round((risk_dlr / entry) * 100.0, 1) if entry > 0 else 7.0
    t1, t2, t3 = round(entry * 1.05, 2), round(entry * 1.10, 2), round(entry * 1.15, 2)
    rr = round((t2 - entry) / risk_dlr, 2) if risk_dlr > 0 else 1.6
    
    return {
        'symbol': symbol, 'category': category, 'setup_horizon': horizon, 'readiness_badge': readiness_badge,
        'close': close, 'ytd_perf_pct': round(ytd_perf * 100, 1), 'vol_100d_k': round(vol_sma100 / 1000.0, 1),
        'rvol': round(rvol, 2), 'dist_to_ema21_pct': round(dist_ema21_pct, 1), 'dist_to_sma50_pct': round(dist_sma50_pct, 1),
        'dist_to_sma200_pct': round(dist_sma200 * 100.0, 1), 'dist_from_52w_high_pct': round(off_52w_high * 100.0, 1),
        'dist_from_52w_low_pct': round((close - low52w) / low52w * 100.0, 1), 'slope_ema21': round(slope_ema21, 2),
        'slope_sma50': round(slope_sma50, 2), 'ema21_slope_desc': ema21_slope_desc, 'sma50_slope_desc': sma50_slope_desc,
        'buy_zone_type': buy_zone, 'daily_demand_zone': mtf['daily_demand'], 'weekly_demand_zone': mtf['weekly_demand'],
        'monthly_demand_zone': mtf['monthly_demand'], 'sell_zone': mtf['sell_zone'], 'volume_surge_tag': vol_tag,
        'swing_higher_low': "YES (SL2 >= SL1)" if swings.get('higher_low') else "NO",
        'swing_contraction': "YES (VCP)" if swings.get('contraction') else "NO",
        'sl1': round(swings.get('sl1', 0), 2), 'sl1_date': swings.get('sl1_date', 'N/A'),
        'sl2': round(swings.get('sl2', 0), 2), 'sl2_date': swings.get('sl2_date', 'N/A'),
        'sh1': round(swings.get('sh1', 0), 2), 'sh1_date': swings.get('sh1_date', 'N/A'),
        'sh2': round(swings.get('sh2', 0), 2), 'sh2_date': swings.get('sh2_date', 'N/A'),
        'rs_score': rs_score, 'iqs_score': iqs, 'grade': grade, 'star_rating': star_rating,
        'action_verdict': action_verdict, 'suggested_entry': entry, 'initial_stop_loss': sl,
        'risk_pct': risk_pct, 'target_1': t1, 'target_2': t2, 'target_3': t3, 'risk_reward': rr
    }

# ================================================================================
# 5. PUBLICATION-QUALITY CANDLESTICK CHART GENERATOR
# ================================================================================

def generate_candlestick_chart(symbol: str, df: pd.DataFrame, cand_data: Dict[str, Any],
                               output_path: Optional[str] = None, show: bool = False,
                               theme: str = 'dark'):
    if df is None or len(df) < 35: return
    sub = df.iloc[-35:].copy()
    
    is_dark = (theme.lower() == 'dark')
    bg_fig = '#0d1117' if is_dark else '#ffffff'
    bg_ax = '#161b22' if is_dark else '#f6f8fa'
    text_color = '#f0f6fc' if is_dark else '#24292f'
    subtext_color = '#8b949e' if is_dark else '#57606a'
    grid_color = '#21262d' if is_dark else '#d0d7de'
    border_color = '#30363d' if is_dark else '#d0d7de'
    sma200_color = '#ffffff' if is_dark else '#000000'
    
    fig, ax = plt.subplots(figsize=(14, 6.5), facecolor=bg_fig)
    ax.set_facecolor(bg_ax)
    fig.subplots_adjust(top=0.88, bottom=0.12, left=0.07, right=0.96)
    
    width = 0.6
    up = sub[sub['Close'] >= sub['Open']]
    down = sub[sub['Close'] < sub['Open']]
    
    ax.bar(up.index, up['Close'] - up['Open'], width, bottom=up['Open'], color='#00e676', edgecolor='#00e676', zorder=3)
    ax.vlines(up.index, up['Low'], up['High'], color='#00e676', linewidth=1.2, zorder=2)
    ax.bar(down.index, down['Close'] - down['Open'], width, bottom=down['Open'], color='#ff5252', edgecolor='#ff5252', zorder=3)
    ax.vlines(down.index, down['Low'], down['High'], color='#ff5252', linewidth=1.2, zorder=2)
    
    # User-Specified Color Scheme:
    # 10 EMA: Cyan | 21 EMA: Green | 50 SMA: Orange | 150 SMA: Blue | 200 SMA: White (dark) / Black (light)
    ax.plot(sub.index, sub['EMA10'], color='#00e5ff', label='10 EMA (Momentum)', linewidth=1.4, zorder=4)
    ax.plot(sub.index, sub['EMA21'], color='#00e676', label='21 EMA (Prime Pullback Support)', linewidth=2.0, zorder=4)
    ax.plot(sub.index, sub['SMA50'], color='#ff9100', label='50 SMA (Institutional Demand)', linewidth=1.8, zorder=4)
    if 'SMA150' in sub.columns and not pd.isna(sub['SMA150'].iloc[-1]):
        ax.plot(sub.index, sub['SMA150'], color='#2979ff', label='150 SMA (Intermediate Baseline)', linewidth=1.5, zorder=4)
    if 'SMA200' in sub.columns and not pd.isna(sub['SMA200'].iloc[-1]):
        ax.plot(sub.index, sub['SMA200'], color=sma200_color, label='200 SMA (Macro Baseline)', linewidth=1.5, linestyle='--', zorder=4)
        
    low_21 = float(sub['Low'].min())
    ax.axhspan(low_21, low_21 * 1.035, color='#00e676', alpha=0.15, label='Daily Demand Zone (<=3.5% from 21d low)', zorder=1)
    
    # Accurate Swing Points Anchor (Using Exact Bar Datetime)
    def find_idx_by_date(dt_str):
        if not dt_str or dt_str == "N/A": return None
        for idx in sub.index:
            try:
                if pd.to_datetime(idx).strftime('%Y-%m-%d') == dt_str:
                    return idx
            except Exception: pass
        return None
        
    sl1_val, sl2_val = cand_data.get('sl1', 0.0), cand_data.get('sl2', 0.0)
    sh1_val, sh2_val = cand_data.get('sh1', 0.0), cand_data.get('sh2', 0.0)
    x_sl1 = find_idx_by_date(cand_data.get('sl1_date'))
    x_sl2 = find_idx_by_date(cand_data.get('sl2_date'))
    x_sh1 = find_idx_by_date(cand_data.get('sh1_date'))
    x_sh2 = find_idx_by_date(cand_data.get('sh2_date'))
    
    # Swing Lows: Emerald Green triangles at candle wick lows
    if x_sl1 is not None and sl1_val > 0:
        ax.scatter([x_sl1], [sl1_val], color='#00e676', s=100, marker='^', zorder=5)
        ax.text(x_sl1, sl1_val * 0.985, f"SL1: ${sl1_val:.2f}", color='#00e676', fontsize=8, ha='center', weight='bold')
    if x_sl2 is not None and sl2_val > 0:
        ax.scatter([x_sl2], [sl2_val], color='#00e676', s=120, marker='^', zorder=5)
        ax.text(x_sl2, sl2_val * 0.985, f"SL2: ${sl2_val:.2f}", color='#00e676', fontsize=8, ha='center', weight='bold')
        
    # Swing Highs: Royal Blue triangles at candle wick peaks (avoids conflicting red stop-loss color)
    if x_sh1 is not None and sh1_val > 0:
        ax.scatter([x_sh1], [sh1_val], color='#2979ff', s=100, marker='v', zorder=5)
        ax.text(x_sh1, sh1_val * 1.015, f"SH1: ${sh1_val:.2f}", color='#2979ff', fontsize=8, ha='center', weight='bold')
    if x_sh2 is not None and sh2_val > 0:
        ax.scatter([x_sh2], [sh2_val], color='#2979ff', s=120, marker='v', zorder=5)
        ax.text(x_sh2, sh2_val * 1.015, f"SH2: ${sh2_val:.2f}", color='#2979ff', fontsize=8, ha='center', weight='bold')
        
    horizon_text = cand_data.get('setup_horizon', 'TIER 1')
    entry = cand_data.get('suggested_entry', float(sub['Close'].iloc[-1]))
    stop = cand_data.get('initial_stop_loss', entry * 0.93)
    t1 = cand_data.get('target_1', entry * 1.05)
    t2 = cand_data.get('target_2', entry * 1.10)
    
    entry_label = f"Trigger Entry (Sweet Spot): ${entry:.2f}" if "TIER 1" in horizon_text else f"Planned Pullback Entry (21 EMA): ${entry:.2f}"
    ax.axhline(entry, color='#00e5ff', linestyle='--', linewidth=1.5, label=entry_label)
    ax.axhline(stop, color='#ff1744', linestyle='--', linewidth=1.5, label=f"Stop Loss: ${stop:.2f} (-{cand_data.get('risk_pct', 7.0)}%)")
    ax.axhline(t1, color='#69f0ae', linestyle=':', linewidth=1.2, label=f"Target 1 (+5%): ${t1:.2f}")
    ax.axhline(t2, color='#ffd700', linestyle=':', linewidth=1.2, label=f"Target 2 (+10%): ${t2:.2f} (R:R {cand_data.get('risk_reward', 1.6)}:1)")
    
    ax.grid(True, color=grid_color, linestyle='--', alpha=0.6)
    ax.tick_params(colors=subtext_color, labelsize=9)
    for spine in ax.spines.values(): spine.set_color(border_color)
    
    category_badge = f"[{cand_data.get('category', 'INDEX')}]"
    iqs = cand_data.get('iqs_score', 85)
    grade = cand_data.get('grade', 'A')
    
    title_main = f"{symbol} {category_badge} — {horizon_text} | Grade: {grade} (IQS: {iqs}/100)"
    subtitle = f"Buy Zone: {cand_data.get('buy_zone_type', '21 EMA')} | Daily Demand: {cand_data.get('daily_demand_zone')} | Weekly Demand: {cand_data.get('weekly_demand_zone')} | Vol Pocket Pivot: {cand_data.get('volume_surge_tag')}"
    
    plt.suptitle(title_main, color=text_color, fontsize=12, fontweight='bold', y=0.96)
    plt.title(subtitle, color=subtext_color, fontsize=9, pad=6)
    ax.legend(facecolor=bg_ax, edgecolor=border_color, labelcolor=text_color, loc='upper left', fontsize=8, ncol=2)
    
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
    if show: plt.show()
    plt.close(fig)

# ================================================================================
# 6. MULTI-SHEET FORMATTED EXCEL WORKBOOK GENERATOR (CONFIGURABLE TOP N)
# ================================================================================

def export_screener_to_excel(results: List[Dict], output_path: str = "weekly_swing_screener_results.xlsx", top_n: int = 50):
    """
    Exports screened candidates to a 6-sheet institutional Excel workbook:
    - Sheet 1: 'Index_Watchlist_Top_Setups' (Top N setups from S&P 500, Nasdaq 100, Dow 30)
    - Sheet 2: 'Broader_Market_Alpha_Setups' (Top N setups outside major indices)
    - Sheet 3: 'Trigger_Ready_This_Week' (Consolidated Tier 1 candidates ready for immediate bot execution)
    - Sheet 4: 'Multi_Timeframe_Demand_Matrix' (Daily, Weekly, Monthly demand/sell zone breakdown)
    - Sheet 5: 'All_Screened_Candidates' (Full quantitative dataset)
    - Sheet 6: 'Watchlist_TXT_Export' (Top N symbols for config/watchlist.txt)
    """
    if not results:
        print("No candidates met screener criteria. Excel export skipped.")
        return
        
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    
    navy_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    gold_fill = PatternFill(start_color="B28900", end_color="B28900", fill_type="solid")
    dark_green_fill = PatternFill(start_color="1E4620", end_color="1E4620", fill_type="solid")
    purple_fill = PatternFill(start_color="4A154B", end_color="4A154B", fill_type="solid")
    slate_fill = PatternFill(start_color="333F48", end_color="333F48", fill_type="solid")
    
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    regular_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
    )
    
    headers_primary = [
        "Rank", "Symbol", "Category", "Setup Horizon", "Price ($)", "IQS Score", "Grade", "Star Rating",
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
            cell.fill = title_fill; cell.font = header_font; cell.alignment = Alignment(horizontal="center", vertical="center")
            
        for idx, r in enumerate(candidates, 1):
            row_vals = [
                idx, r['symbol'], r['category'], r['setup_horizon'], r['close'], r['iqs_score'],
                r.get('grade', 'B'), r['star_rating'], r['action_verdict'], r['buy_zone_type'],
                r['dist_to_ema21_pct'], r['dist_to_sma50_pct'], r['ema21_slope_desc'], r['sma50_slope_desc'],
                r['daily_demand_zone'], r['weekly_demand_zone'], r['volume_surge_tag'],
                r['swing_higher_low'], r['swing_contraction'], r['sl1'], r['sl2'],
                r['sh1'], r['sh2'], r['rs_score'], r['suggested_entry'], r['initial_stop_loss'],
                r['risk_pct'], r['target_1'], r['target_2'], r['target_3'], r['risk_reward']
            ]
            ws.append(row_vals)
            curr_row = ws.max_row
            for c_idx in range(1, len(row_vals) + 1):
                c = ws.cell(row=curr_row, column=c_idx)
                c.font = regular_font; c.border = thin_border
                c.alignment = Alignment(horizontal="center" if c_idx in [1, 2, 3, 4, 7, 15, 16, 17, 18, 19] else "right")
                
    sorted_all = sorted(results, key=lambda x: (
        0 if "TIER 1" in x['setup_horizon'] else (1 if "TIER 2" in x['setup_horizon'] else 2),
        -x['iqs_score']
    ))
    
    index_candidates = [c for c in sorted_all if c['category'] == "INDEX"]
    broader_candidates = [c for c in sorted_all if c['category'] == "BROADER_MARKET"]
    trigger_ready = [c for c in sorted_all if "TIER 1" in c['setup_horizon']]
    
    # 1. Index Top Setups (Top N)
    ws1 = wb.create_sheet("Index_Watchlist_Top_Setups")
    populate_sheet(ws1, index_candidates[:top_n], navy_fill)
    
    # 2. Broader Market Alpha Setups (Top N)
    ws2 = wb.create_sheet("Broader_Market_Alpha_Setups")
    populate_sheet(ws2, broader_candidates[:top_n], gold_fill)
    
    # 3. Trigger Ready This Week (Top N)
    ws3 = wb.create_sheet("Trigger_Ready_This_Week")
    populate_sheet(ws3, trigger_ready[:top_n] if trigger_ready else sorted_all[:top_n], dark_green_fill)
    
    # 4. Multi-Timeframe Demand Matrix
    ws4 = wb.create_sheet("Multi_Timeframe_Demand_Matrix")
    headers_demand = [
        "Rank", "Symbol", "Category", "Setup Horizon", "Price ($)", "Grade", "Daily Demand",
        "Weekly Demand", "Monthly Demand", "Sell Zone", "Dist to EMA21 (%)",
        "Dist to SMA50 (%)", "Volume Surge Tag", "SL2 >= SL1", "VCP Contraction", "IQS Score"
    ]
    ws4.append(headers_demand)
    for col_num in range(1, len(headers_demand) + 1):
        c = ws4.cell(row=1, column=col_num)
        c.fill = purple_fill; c.font = header_font; c.alignment = Alignment(horizontal="center", vertical="center")
    for idx, r in enumerate(sorted_all, 1):
        ws4.append([
            idx, r['symbol'], r['category'], r['setup_horizon'], r['close'], r.get('grade', 'B'),
            r['daily_demand_zone'], r['weekly_demand_zone'], r['monthly_demand_zone'],
            r['sell_zone'], r['dist_to_ema21_pct'], r['dist_to_sma50_pct'],
            r['volume_surge_tag'], r['swing_higher_low'], r['swing_contraction'], r['iqs_score']
        ])
        
    # 5. All Screened Candidates
    ws5 = wb.create_sheet("All_Screened_Candidates")
    populate_sheet(ws5, sorted_all, slate_fill)
    
    # 6. Watchlist TXT Export (Top N)
    ws6 = wb.create_sheet("Watchlist_TXT_Export")
    ws6.cell(row=1, column=1, value="Symbol (Ready to Copy to config/watchlist.txt)").font = header_font
    ws6.cell(row=1, column=1).fill = navy_fill
    ws6.cell(row=1, column=2, value="Category").font = header_font
    ws6.cell(row=1, column=2).fill = navy_fill
    ws6.cell(row=1, column=3, value="Setup Horizon").font = header_font
    ws6.cell(row=1, column=3).fill = navy_fill
    ws6.cell(row=1, column=4, value="IQS Score").font = header_font
    ws6.cell(row=1, column=4).fill = navy_fill
    ws6.cell(row=1, column=5, value="Grade").font = header_font
    ws6.cell(row=1, column=5).fill = navy_fill
    
    top_export = sorted_all[:top_n]
    for r in top_export:
        ws6.append([r['symbol'], r['category'], r['setup_horizon'], r['iqs_score'], r.get('grade', 'B')])
        
    for ws in [ws1, ws2, ws3, ws4, ws5, ws6]:
        for col in ws.columns:
            max_len = max(len(str(c.value or '')) for c in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
            
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    print(f"📊 6-Sheet Institutional Excel workbook ({top_n} setups per watchlist) exported to: {output_path}")

def export_watchlist_txt(results: List[Dict], output_txt: str = "watchlist.txt", top_n: int = 50):
    sorted_all = sorted(results, key=lambda x: (
        0 if "TIER 1" in x['setup_horizon'] else (1 if "TIER 2" in x['setup_horizon'] else 2),
        -x['iqs_score']
    ))
    top_syms = [r['symbol'] for r in sorted_all[:top_n]]
    os.makedirs(os.path.dirname(os.path.abspath(output_txt)), exist_ok=True)
    with open(output_txt, "w") as f:
        for s in top_syms:
            f.write(f"{s}\n")
    print(f"📝 Plain-text watchlist ({len(top_syms)} symbols, rated A+ to B-) exported to: {output_txt}")

# ================================================================================
# 7. SCANNER ORCHESTRATION PIPELINE
# ================================================================================

def run_screener_pipeline(universe_mode: str = "combined", custom_file: str = "",
                          output_excel: str = "weekly_swing_screener_results.xlsx",
                          output_txt: str = "watchlist.txt",
                          update_watchlist: bool = False,
                          top_n_watchlist: int = 50,
                          generate_charts: bool = False,
                          max_charts: int = 10) -> List[Dict]:
    print("=" * 80)
    print(f"🏛️ INSTITUTIONAL WEEKLY SWING TRADING RADAR (MODE: {universe_mode.upper()} | TOP {top_n_watchlist})")
    print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 80)
    
    symbols, category_map = get_segmented_universe(universe_mode)
    print(f"Total symbols in universe: {len(symbols)}")
    index_cnt = sum(1 for s in symbols if category_map.get(s) == "INDEX")
    broader_cnt = sum(1 for s in symbols if category_map.get(s) == "BROADER_MARKET")
    print(f"  • Inside Major Indices: {index_cnt}")
    print(f"  • Outside Major Indices (Broader Growth Alpha): {broader_cnt}")
    
    spy_df = None
    try:
        spy_raw = yf.download("SPY", period="2y", interval="1d", progress=False)
        if isinstance(spy_raw.columns, pd.MultiIndex): spy_raw.columns = spy_raw.columns.get_level_values(0)
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
                if len(batch) == 1: df = data.copy()
                elif sym in data.columns.levels[0]: df = data[sym].dropna()
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
    
    grade_counts = {}
    for c in candidates:
        g = c.get('grade', 'B')
        grade_counts[g] = grade_counts.get(g, 0) + 1
    grade_summary = ", ".join([f"{g}: {cnt}" for g, cnt in sorted(grade_counts.items())])
    print(f"  • Grade Distribution: {grade_summary}")
    print("=" * 80)
    
    export_screener_to_excel(candidates, output_path=output_excel, top_n=top_n_watchlist)
    export_watchlist_txt(candidates, output_txt=output_txt, top_n=top_n_watchlist)
    
    if update_watchlist and candidates:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_cfg = os.path.join(project_root, "config", "watchlist.txt")
        export_watchlist_txt(candidates, output_txt=target_cfg, top_n=top_n_watchlist)
        print(f"✅ Automatically updated live bot config at: {target_cfg}")
        
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
    parser.add_argument("--file", type=str, default="", help="Path to TradingView CSV/TXT export file")
    parser.add_argument("--universe", type=str, default="combined", choices=["combined", "indices", "broader", "dow30", "nasdaq100", "sp500"])
    parser.add_argument("--output", type=str, default="weekly_swing_screener_results.xlsx")
    parser.add_argument("--output-txt", type=str, default="watchlist.txt")
    parser.add_argument("--top", type=int, default=50, help="Number of top setups per sheet (default: 50)")
    parser.add_argument("--update-watchlist", action="store_true")
    parser.add_argument("--charts", action="store_true")
    parser.add_argument("--max-charts", type=int, default=10)
    args = parser.parse_args()
    
    run_screener_pipeline(
        universe_mode="custom" if args.file else args.universe,
        custom_file=args.file,
        output_excel=args.output,
        output_txt=args.output_txt,
        update_watchlist=args.update_watchlist,
        top_n_watchlist=args.top,
        generate_charts=args.charts,
        max_charts=args.max_charts
    )
