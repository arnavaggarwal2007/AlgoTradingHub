import json
import time
import math
import pandas as pd
import pandas_ta as ta
import pytz
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- LOAD CONFIGURATION ---
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print("CRITICAL ERROR: config.json not found.")
    exit()

# --- SETUP CLIENTS ---
API_KEY = config['api']['key_id']
SECRET_KEY = config['api']['secret_key']
PAPER = True if "paper" in config['api']['base_url'] else False

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# --- UTILITY FUNCTIONS ---

def get_current_est_time():
    return datetime.now(pytz.timezone('US/Eastern'))

def is_market_open():
    now = get_current_est_time()
    # Simple check: Mon-Fri, 9:30 AM to 4:00 PM EST
    if now.weekday() > 4: return False # Weekend
    market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_start <= now <= market_end

def is_buy_window():
    """Checks if we are in the last hour (or configured window)"""
    now = get_current_est_time()
    start_str = config['trading_rules']['buy_window_start_time']
    end_str = config['trading_rules']['buy_window_end_time']
    
    start_h, start_m = map(int, start_str.split(':'))
    end_h, end_m = map(int, end_str.split(':'))
    
    start_time = now.replace(hour=start_h, minute=start_m, second=0)
    end_time = now.replace(hour=end_h, minute=end_m, second=0)
    
    return start_time <= now <= end_time

def get_market_data(symbol, days=365):
    """Fetches Daily data and calculates Weekly/Monthly aggregates"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        params = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start_date)
        bars = data_client.get_stock_bars(params)
        if not bars.data: return None, None, None
        
        df = bars.df.loc[symbol]
        
        # Calculate Weekly and Monthly
        logic = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        
        # Resample to Weekly (W-FRI means week ending Friday)
        df_weekly = df.resample('W-FRI').agg(logic)
        df_monthly = df.resample('ME').agg(logic)
        
        return df, df_weekly, df_monthly
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None, None, None

def check_patterns(df):
    """Checks for Engulfing, Piercing, Tweezer"""
    # Get last 2 candles
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    is_green = curr['close'] > curr['open']
    if not is_green: return False

    # 1. Engulfing
    is_engulfing = (curr['close'] >= prev['open']) and \
                   (prev['close'] < prev['open']) and \
                   (curr['close'] > prev['open'])

    # 2. Piercing (Explosive)
    midpoint = (prev['open'] + prev['close']) / 2
    is_piercing = (curr['close'] > midpoint) and \
                  (curr['close'] < prev['open']) and \
                  (prev['close'] < prev['open'])

    # 3. Tweezer Bottom
    is_tweezer = abs(curr['low'] - prev['low']) <= (curr['low'] * 0.002) and \
                 (prev['close'] < prev['open'])

    return is_engulfing or is_piercing or is_tweezer

# --- CORE LOGIC ---

def analyze_buy_signal(symbol):
    """
    Implements Rajat Alpha v67 Logic
    """
    df, df_w, df_m = get_market_data(symbol)
    if df is None or len(df) < 200: return False # Maturity check

    # 1. Indicators
    df['SMA50'] = df.ta.sma(close='close', length=50)
    df['SMA200'] = df.ta.sma(close='close', length=200)
    df['EMA21'] = df.ta.ema(close='close', length=21)
    
    # Weekly/Monthly Checks
    df_w['EMA21'] = df_w.ta.ema(close='close', length=21)
    df_m['EMA10'] = df_m.ta.ema(close='close', length=10)
    
    curr = df.iloc[-1]
    curr_w = df_w.iloc[-1]
    curr_m = df_m.iloc[-1]

    # 2. Market Structure (Bullish Alignment)
    # SMA50 > SMA200 AND EMA21 > SMA50
    structure_ok = (curr['SMA50'] > curr['SMA200']) and (curr['EMA21'] > curr['SMA50'])
    
    # 3. Multi-Timeframe Confirmation
    weekly_ok = curr_w['close'] > curr_w['EMA21']
    monthly_ok = curr_m['close'] > curr_m['EMA10']

    if not (structure_ok and weekly_ok and monthly_ok):
        return False

    # 4. Pullback & Touch Logic
    # Price is near EMA21 (within margin) OR Just pulled back
    dist_ema21 = abs(curr['close'] - curr['EMA21']) / curr['EMA21']
    is_near_ma = dist_ema21 <= 0.025 # 2.5% tolerance
    
    # 5. Pattern Check
    pattern_ok = check_patterns(df)

    # 6. Final Trigger
    if is_near_ma and pattern_ok:
        print(f"[{symbol}] VALID BUY SIGNAL FOUND!")
        return True
    
    return False

def run_guardian_sell_logic():
    """
    Checks ALL existing positions for:
    1. Time Exit (TES)
    2. Dynamic Trailing Stop Loss
    3. Profit Targets (Optional if not using Limit orders)
    """
    print("--- Guardian: Checking Positions ---")
    positions = trading_client.get_all_positions()
    
    for pos in positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        entry_price = float(pos.avg_entry_price)
        current_price = float(pos.current_price)
        
        # Calculate Gain/Loss %
        pct_gain = (current_price - entry_price) / entry_price
        
        # 1. Time Exit Check (TES)
        # Note: This is an approximation. Alpaca doesn't give exact 'days held' easily via API without order history.
        # We assume strict monitoring or external DB for perfect TES. 
        # For this script, we rely on price action primarily.
        
        # 2. Dynamic Trailing Stop Loss Logic (Tiered)
        # Logic: Determine what the SL *should* be based on current profit
        sl_pct = config['risk_management']['initial_stop_loss_pct'] # Default 17%
        
        if pct_gain >= config['risk_management']['tier_2_profit_pct']: # If up 10%
            sl_pct = config['risk_management']['tier_2_stop_loss_pct'] # SL becomes 1%
        elif pct_gain >= config['risk_management']['tier_1_profit_pct']: # If up 5%
            sl_pct = config['risk_management']['tier_1_stop_loss_pct'] # SL becomes 9%
            
        stop_price = entry_price * (1 - sl_pct)
        
        if current_price <= stop_price:
            print(f"!!! SELL TRIGGER: {symbol} hit Dynamic SL (Gain: {pct_gain*100:.2f}%)")
            trading_client.close_position(symbol)
            continue
            
        # 3. Partial Profit Taking (Logic for 'Layman' - Simplified)
        # If we hit Target 1 (10%) and we still have full position, sell 1/3
        # Implementation: Check if unrealized_plpc > target
        # Note: Partial exits in a stateless script are risky without a database. 
        # We will use the Dynamic SL to lock in profits instead, as it is safer for this setup.
        
        print(f"Guardian: {symbol} | P/L: {pct_gain*100:.2f}% | SL Level: {stop_price:.2f} | Action: HOLD")

def run_hunter_buy_logic():
    """
    Scans watchlist for entries. 
    Only runs if 'is_buy_window()' is True.
    """
    if not is_buy_window():
        print("Hunter: Market open, but not in Buy Window (Waiting for last hour...)")
        return

    print("--- Hunter: Scanning Watchlist ---")
    
    # Check Max Positions
    positions = trading_client.get_all_positions()
    if len(positions) >= config['trading_rules']['max_open_positions']:
        print("Hunter: Max positions reached. No new buys.")
        return

    # Load Watchlist
    try:
        with open('watchlist.txt', 'r') as f:
            watchlist = [line.strip() for line in f if line.strip()]
    except:
        return

    for symbol in watchlist:
        # Skip if we already own it (and reached max accumulations)
        already_owned = any(p.symbol == symbol for p in positions)
        if already_owned:
            # Check accumulation limit if you want to implement pyramiding
            # For now, strict '1 trade per stock' to be safe
            continue
            
        try:
            signal = analyze_buy_signal(symbol)
            if signal:
                # Calculate Quantity based on Risk
                account = trading_client.get_account()
                equity = float(account.equity)
                trade_amt = equity * config['trading_rules']['position_size_pct']
                # Get current price to calc qty
                bars = data_client.get_stock_latest_bar(StockBarsRequest(symbol_or_symbols=symbol))
                curr_price = bars[symbol].close
                qty_to_buy = int(trade_amt / curr_price)
                
                if qty_to_buy > 0:
                    print(f"!!! EXECUTING BUY: {symbol} x {qty_to_buy} shares")
                    req = MarketOrderRequest(symbol=symbol, qty=qty_to_buy, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
                    trading_client.submit_order(req)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")

# --- MAIN EXECUTION LOOP ---
def main():
    print("Rajat Alpha Bot v67 - INITIALIZED")
    print(f"Mode: {'PAPER' if PAPER else 'REAL MONEY'}")
    
    while True:
        try:
            if is_market_open():
                # 1. Always Run Guardian (Sell Logic)
                run_guardian_sell_logic()
                
                # 2. Run Hunter (Buy Logic) - Internal check for window
                run_hunter_buy_logic()
                
                # 3. Sleep Interval
                # If in Buy Window (Last Hour), scan faster (1 min)
                # Otherwise scan slower (2 min)
                if is_buy_window():
                    print("... Power Hour! Sleeping 60s ...")
                    time.sleep(60)
                else:
                    print("... Mid-Day. Sleeping 120s ...")
                    time.sleep(120)
            else:
                print("Market Closed. Sleeping 5 minutes...")
                time.sleep(300)
                
        except Exception as e:
            print(f"CRITICAL MAIN LOOP ERROR: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()