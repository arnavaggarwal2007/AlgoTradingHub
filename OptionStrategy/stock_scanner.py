"""
================================================================================
STOCK SCANNER — Find Best Candidates for Options Premium Strategies
================================================================================

Scans a watchlist of liquid, optionable stocks and ranks them by suitability
for each of the 4 options strategies based on:

1. Liquidity (average volume, bid-ask spreads)
2. IV Rank / IV Percentile  (higher = better for selling)
3. Sector diversification
4. Earnings timing (avoid earnings proximity)
5. ATR / realized volatility  (stability for condors, movement for wheel)
6. Price range (suitable for capital size)
7. Technical setup (trend, support levels)

Usage:
    python stock_scanner.py                    # Full scan
    python stock_scanner.py --strategy wheel   # Scan for specific strategy
    python stock_scanner.py --min-iv-rank 30   # Filter by IV rank
================================================================================
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Universe of optionable, liquid stocks
# ──────────────────────────────────────────────────────────────

SCAN_UNIVERSE = {
    'mega_cap': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B'],
    'large_cap_tech': ['AMD', 'CRM', 'INTC', 'ORCL', 'ADBE', 'NFLX', 'PYPL', 'SQ', 'SHOP'],
    'financials': ['JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'AXP', 'V', 'MA'],
    'healthcare': ['JNJ', 'UNH', 'PFE', 'MRK', 'ABBV', 'LLY', 'BMY', 'AMGN'],
    'energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY', 'MPC', 'VLO'],
    'consumer': ['WMT', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'COST', 'DIS'],
    'industrial': ['CAT', 'BA', 'DE', 'UNP', 'GE', 'HON', 'MMM', 'LMT'],
    'etfs': ['SPY', 'QQQ', 'IWM', 'DIA', 'XLF', 'XLE', 'XLK', 'EEM', 'GLD', 'TLT'],
}


def get_full_universe() -> List[str]:
    """Return flattened list of all scannable symbols."""
    symbols = []
    for group in SCAN_UNIVERSE.values():
        symbols.extend(group)
    return list(set(symbols))


# ──────────────────────────────────────────────────────────────
# Data Collection
# ──────────────────────────────────────────────────────────────

def fetch_stock_data(symbol: str, period: str = '1y') -> Optional[pd.DataFrame]:
    """Fetch OHLCV data for a single stock."""
    try:
        raw = yf.download(symbol, period=period, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        if raw.empty or len(raw) < 60:
            return None
        return raw
    except Exception as e:
        logger.warning(f"Failed to fetch {symbol}: {e}")
        return None


def compute_metrics(symbol: str, df: pd.DataFrame) -> Dict:
    """Compute all scanner metrics for a stock."""
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    current_price = float(close.iloc[-1])

    # Average volume (20-day)
    avg_vol_20 = float(volume.tail(20).mean())

    # Dollar volume
    dollar_vol = avg_vol_20 * current_price

    # ATR 14
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr_14 = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = atr_14 / current_price * 100

    # Realized (historical) volatility — 30-day and 60-day
    log_ret = np.log(close / close.shift(1))
    hv_30 = float(log_ret.tail(30).std() * np.sqrt(252) * 100)
    hv_60 = float(log_ret.tail(60).std() * np.sqrt(252) * 100)

    # IV Rank approximation (using HV as proxy since actual IV needs options data)
    hv_1y = log_ret.std() * np.sqrt(252) * 100
    hv_vals = log_ret.rolling(30).std() * np.sqrt(252) * 100
    hv_vals = hv_vals.dropna()
    if len(hv_vals) > 0:
        hv_low = float(hv_vals.min())
        hv_high = float(hv_vals.max())
        current_hv = float(hv_vals.iloc[-1])
        iv_rank = ((current_hv - hv_low) / (hv_high - hv_low) * 100) if hv_high > hv_low else 50
        iv_percentile = float((hv_vals < current_hv).sum() / len(hv_vals) * 100)
    else:
        iv_rank = 50
        iv_percentile = 50
        current_hv = float(hv_1y)

    # Trend metrics
    ma_20 = float(close.rolling(20).mean().iloc[-1])
    ma_50 = float(close.rolling(50).mean().iloc[-1])
    ma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else ma_50

    trend_score = 0
    if current_price > ma_20:
        trend_score += 1
    if current_price > ma_50:
        trend_score += 1
    if current_price > ma_200:
        trend_score += 1
    if ma_20 > ma_50:
        trend_score += 1

    # 30-day and 90-day returns
    ret_30 = float((close.iloc[-1] / close.iloc[-min(30, len(close))] - 1) * 100)
    ret_90 = float((close.iloc[-1] / close.iloc[-min(90, len(close))] - 1) * 100) if len(close) >= 90 else ret_30

    # Support / resistance proximity
    lows_20 = float(low.tail(20).min())
    highs_20 = float(high.tail(20).max())
    range_pct = (highs_20 - lows_20) / current_price * 100

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = float(100 - (100 / (1 + rs.iloc[-1]))) if loss.iloc[-1] != 0 else 50

    # Sector
    sector = _get_sector(symbol)

    return {
        'symbol': symbol,
        'price': round(current_price, 2),
        'avg_volume_20d': int(avg_vol_20),
        'dollar_volume': round(dollar_vol, 0),
        'atr_14': round(atr_14, 2),
        'atr_pct': round(atr_pct, 2),
        'hv_30': round(hv_30, 1),
        'hv_60': round(hv_60, 1),
        'iv_rank_proxy': round(iv_rank, 1),
        'iv_percentile_proxy': round(iv_percentile, 1),
        'ma_20': round(ma_20, 2),
        'ma_50': round(ma_50, 2),
        'ma_200': round(ma_200, 2),
        'trend_score': trend_score,
        'ret_30d': round(ret_30, 2),
        'ret_90d': round(ret_90, 2),
        'rsi_14': round(rsi, 1),
        'range_pct_20d': round(range_pct, 2),
        'support_20d': round(lows_20, 2),
        'resistance_20d': round(highs_20, 2),
        'sector': sector,
    }


def _get_sector(symbol: str) -> str:
    for sector, syms in SCAN_UNIVERSE.items():
        if symbol in syms:
            return sector
    return 'unknown'


# ──────────────────────────────────────────────────────────────
# Strategy Suitability Scoring
# ──────────────────────────────────────────────────────────────

def score_for_wheel(m: Dict) -> float:
    """Score a stock for the Wheel Strategy (CSP + CC).
    Best: high IV, liquid, moderate price, uptrend or sideways.
    """
    score = 0

    # Liquidity — must be high
    if m['avg_volume_20d'] > 1_000_000:
        score += 20
    elif m['avg_volume_20d'] > 500_000:
        score += 10

    # IV rank > 30 is ideal for premium selling
    if m['iv_rank_proxy'] > 50:
        score += 25
    elif m['iv_rank_proxy'] > 30:
        score += 15
    elif m['iv_rank_proxy'] > 20:
        score += 5

    # Price range: $20-$300 ideal (need capital for CSPs)
    if 20 <= m['price'] <= 300:
        score += 15
    elif 10 <= m['price'] <= 500:
        score += 5

    # Trend: want uptrend or sideways for CSPs
    if m['trend_score'] >= 3:
        score += 15  # Uptrend
    elif m['trend_score'] == 2:
        score += 10  # Sideways/neutral

    # RSI: not overbought/oversold — sweet spot 35-65
    if 35 <= m['rsi_14'] <= 65:
        score += 10
    elif 30 <= m['rsi_14'] <= 70:
        score += 5

    # ATR: moderate — not too low (no premium) not too high (risky)
    if 1.0 <= m['atr_pct'] <= 3.0:
        score += 10
    elif 0.5 <= m['atr_pct'] <= 4.0:
        score += 5

    # Penalize extreme recent moves
    if abs(m['ret_30d']) > 20:
        score -= 10

    return max(score, 0)


def score_for_spreads(m: Dict) -> float:
    """Score for SPX-style bull put spreads.
    Best: high IV, very liquid, not in downtrend.
    """
    score = 0

    # Liquidity
    if m['avg_volume_20d'] > 5_000_000:
        score += 20
    elif m['avg_volume_20d'] > 1_000_000:
        score += 10

    # High volume premium
    if m['dollar_volume'] > 1e9:
        score += 10

    # IV rank
    if m['iv_rank_proxy'] > 50:
        score += 25
    elif m['iv_rank_proxy'] > 30:
        score += 15

    # Trend: strongly prefer uptrend
    if m['trend_score'] >= 3:
        score += 20
    elif m['trend_score'] >= 2:
        score += 10

    # Penalize downtrend
    if m['trend_score'] == 0:
        score -= 15
    if m['ret_30d'] < -10:
        score -= 10

    # RSI: not oversold extreme
    if m['rsi_14'] > 40:
        score += 10

    return max(score, 0)


def score_for_iron_condors(m: Dict) -> float:
    """Score for iron condors.
    Best: sideways market, contained range, decent IV.
    """
    score = 0

    # Liquidity
    if m['avg_volume_20d'] > 1_000_000:
        score += 15
    elif m['avg_volume_20d'] > 500_000:
        score += 8

    # IV rank — want moderate to high (20-60 ideal)
    if 30 <= m['iv_rank_proxy'] <= 60:
        score += 25
    elif 20 <= m['iv_rank_proxy'] <= 70:
        score += 15
    elif m['iv_rank_proxy'] > 70:
        score += 10  # too much vol can be risky

    # Sideways: range-bound is KEY
    if m['range_pct_20d'] < 8:
        score += 20
    elif m['range_pct_20d'] < 12:
        score += 10

    # Trend: prefer sideways (score 2)
    if m['trend_score'] == 2:
        score += 15
    elif m['trend_score'] in (1, 3):
        score += 5

    # RSI near 50 = balanced
    rsi_dist = abs(m['rsi_14'] - 50)
    if rsi_dist < 10:
        score += 15
    elif rsi_dist < 20:
        score += 8

    # Low ATR preferred
    if m['atr_pct'] < 2.0:
        score += 10

    return max(score, 0)


def score_for_regime_adaptive(m: Dict) -> float:
    """Score for VIX-regime adaptive strategy.
    This works on index ETFs — preference for SPY/QQQ/IWM.
    """
    score = 0

    # Index ETFs get big bonus
    if m['symbol'] in ['SPY', 'QQQ', 'IWM', 'DIA']:
        score += 30
    elif m['symbol'] in ['XLF', 'XLE', 'XLK']:
        score += 15

    # Liquidity — very high required
    if m['avg_volume_20d'] > 10_000_000:
        score += 20
    elif m['avg_volume_20d'] > 2_000_000:
        score += 10

    # IV rank — works across ranges but higher is better
    if m['iv_rank_proxy'] > 40:
        score += 20
    elif m['iv_rank_proxy'] > 25:
        score += 10

    # Any trend OK (adaptive)
    score += 10

    # Dollar volume
    if m['dollar_volume'] > 5e9:
        score += 10
    elif m['dollar_volume'] > 1e9:
        score += 5

    return max(score, 0)


# ──────────────────────────────────────────────────────────────
# Scanner Entry Point
# ──────────────────────────────────────────────────────────────

def run_scan(
    symbols: List[str] = None,
    min_iv_rank: float = 0,
    min_volume: int = 0,
    max_price: float = float('inf'),
    min_price: float = 0,
    strategy: str = None,
) -> pd.DataFrame:
    """Run the full scanner and return ranked results."""
    if symbols is None:
        symbols = get_full_universe()

    logger.info(f"Scanning {len(symbols)} symbols...")

    results = []
    failed = []
    for sym in symbols:
        try:
            df = fetch_stock_data(sym)
            if df is None:
                failed.append(sym)
                continue
            m = compute_metrics(sym, df)

            # Filters
            if m['iv_rank_proxy'] < min_iv_rank:
                continue
            if m['avg_volume_20d'] < min_volume:
                continue
            if not (min_price <= m['price'] <= max_price):
                continue

            # Strategy scores
            m['wheel_score'] = score_for_wheel(m)
            m['spread_score'] = score_for_spreads(m)
            m['condor_score'] = score_for_iron_condors(m)
            m['regime_score'] = score_for_regime_adaptive(m)
            m['composite_score'] = (
                m['wheel_score'] + m['spread_score'] +
                m['condor_score'] + m['regime_score']
            ) / 4

            results.append(m)
        except Exception as e:
            logger.warning(f"Error scanning {sym}: {e}")
            failed.append(sym)

    if failed:
        logger.info(f"Failed symbols: {failed}")

    scan_df = pd.DataFrame(results)
    if scan_df.empty:
        return scan_df

    # Sort by requested strategy or composite
    sort_col = {
        'wheel': 'wheel_score',
        'spreads': 'spread_score',
        'condors': 'condor_score',
        'condor': 'condor_score',
        'regime': 'regime_score',
        'adaptive': 'regime_score',
    }.get(strategy, 'composite_score')

    scan_df = scan_df.sort_values(sort_col, ascending=False)

    return scan_df


def print_scan_results(scan_df: pd.DataFrame, strategy: str = None, top_n: int = 20):
    """Print scanner results to console."""
    if scan_df.empty:
        print("No results found.")
        return

    print("\n" + "=" * 120)
    print(f"STOCK SCANNER RESULTS — {'ALL STRATEGIES' if not strategy else strategy.upper()}")
    print(f"Scanned {len(scan_df)} stocks | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 120)

    cols = ['symbol', 'price', 'iv_rank_proxy', 'atr_pct', 'trend_score', 'rsi_14',
            'avg_volume_20d', 'sector',
            'wheel_score', 'spread_score', 'condor_score', 'regime_score', 'composite_score']

    display = scan_df[cols].head(top_n)
    display = display.rename(columns={
        'iv_rank_proxy': 'IV Rank',
        'atr_pct': 'ATR%',
        'trend_score': 'Trend',
        'rsi_14': 'RSI',
        'avg_volume_20d': 'Avg Vol',
        'wheel_score': 'Wheel',
        'spread_score': 'Spread',
        'condor_score': 'Condor',
        'regime_score': 'Regime',
        'composite_score': 'Total',
    })

    print(display.to_string(index=False))

    # Sector distribution
    print("\nSECTOR DISTRIBUTION (Top 20):")
    top = scan_df.head(top_n)
    print(top['sector'].value_counts().to_string())

    # Strategy-specific recommendations
    print("\n" + "-" * 60)
    print("TOP PICKS PER STRATEGY:")
    for strat, col in [('Wheel', 'wheel_score'), ('Spreads', 'spread_score'),
                       ('Condors', 'condor_score'), ('Regime', 'regime_score')]:
        top3 = scan_df.nlargest(3, col)['symbol'].tolist()
        print(f"  {strat:<10}: {', '.join(top3)}")
    print("-" * 60)


def save_scan_results(scan_df: pd.DataFrame, output_dir: str = 'scan_results'):
    """Save scan results to CSV and JSON."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    csv_path = os.path.join(output_dir, f'scan_{timestamp}.csv')
    scan_df.to_csv(csv_path, index=False)

    json_path = os.path.join(output_dir, f'scan_{timestamp}.json')
    scan_df.head(20).to_json(json_path, orient='records', indent=2)

    logger.info(f"Scan results saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Options Stock Scanner')
    parser.add_argument('--strategy', default=None,
                        choices=['wheel', 'spreads', 'condors', 'regime'])
    parser.add_argument('--min-iv-rank', type=float, default=0)
    parser.add_argument('--min-volume', type=int, default=100000)
    parser.add_argument('--min-price', type=float, default=10)
    parser.add_argument('--max-price', type=float, default=600)
    parser.add_argument('--top', type=int, default=20)
    parser.add_argument('--output', default='scan_results')
    parser.add_argument('--symbols', nargs='+', default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    scan_df = run_scan(
        symbols=args.symbols,
        min_iv_rank=args.min_iv_rank,
        min_volume=args.min_volume,
        max_price=args.max_price,
        min_price=args.min_price,
        strategy=args.strategy,
    )

    print_scan_results(scan_df, strategy=args.strategy, top_n=args.top)
    save_scan_results(scan_df, args.output)


if __name__ == '__main__':
    main()
