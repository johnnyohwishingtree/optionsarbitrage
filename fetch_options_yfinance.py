#!/usr/bin/env python3
"""
Fetch options and underlying price data using yfinance.

IMPORTANT LIMITATIONS:
- yfinance provides 1-minute historical bars for underlying (SPY, ^GSPC)
- yfinance provides current options chain snapshots (bid/ask, volume, OI, Greeks)
- yfinance does NOT provide historical intraday bars for individual options contracts

This script fetches:
1. 1-minute underlying prices for SPY and SPX (^GSPC)
2. Current options chain snapshots for SPY and SPX

Usage:
    python fetch_options_yfinance.py                    # Fetch today's data
    python fetch_options_yfinance.py --date 20260130    # Fetch specific date
    python fetch_options_yfinance.py --range 0.03       # Custom strike range (default: 3%)
"""

import argparse
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os
import time

# Data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def get_underlying_1min_data(symbol: str, date_str: str) -> pd.DataFrame:
    """
    Fetch 1-minute historical data for underlying symbol.

    Args:
        symbol: Ticker symbol (SPY, ^GSPC for SPX)
        date_str: Date in YYYYMMDD format

    Returns:
        DataFrame with OHLCV data
    """
    ticker = yf.Ticker(symbol)

    # Parse date
    date = datetime.strptime(date_str, '%Y%m%d')
    start_date = date.strftime('%Y-%m-%d')
    end_date = (date + timedelta(days=1)).strftime('%Y-%m-%d')

    print(f"Fetching 1-min data for {symbol} on {start_date}...")

    # Fetch 1-minute data
    # yfinance requires period="1d" or start/end for intraday
    # For a specific date, we use start and end
    df = ticker.history(start=start_date, end=end_date, interval='1m')

    if df.empty:
        print(f"  Warning: No data returned for {symbol}")
        return pd.DataFrame()

    # Reset index to get datetime as column
    df = df.reset_index()

    # Rename columns to match existing format
    df = df.rename(columns={
        'Datetime': 'time',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })

    # Add symbol column
    display_symbol = 'SPX' if symbol == '^GSPC' else symbol
    df['symbol'] = display_symbol

    # Select and order columns to match existing format
    df = df[['symbol', 'time', 'open', 'high', 'low', 'close', 'volume']]

    print(f"  Retrieved {len(df)} bars for {display_symbol}")
    return df


def get_options_chain_snapshot(symbol: str, date_str: str, strike_range: float = 0.03) -> pd.DataFrame:
    """
    Fetch current options chain snapshot for a symbol.

    Note: This fetches the CURRENT chain, not historical.
    yfinance does not support historical options data.

    Args:
        symbol: Ticker symbol (SPY, ^GSPC for SPX)
        date_str: Date in YYYYMMDD format (used for expiration filtering)
        strike_range: Range around ATM price (e.g., 0.03 = 3%)

    Returns:
        DataFrame with options chain data
    """
    ticker = yf.Ticker(symbol)
    display_symbol = 'SPX' if symbol == '^GSPC' else symbol

    print(f"Fetching options chain for {display_symbol}...")

    # Get current price for ATM calculation
    try:
        current_price = ticker.info.get('regularMarketPrice') or ticker.info.get('previousClose')
        if current_price is None:
            hist = ticker.history(period='1d')
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
    except Exception as e:
        print(f"  Error getting price for {symbol}: {e}")
        return pd.DataFrame()

    if current_price is None:
        print(f"  Warning: Could not get current price for {symbol}")
        return pd.DataFrame()

    print(f"  Current price: ${current_price:.2f}")

    # Calculate strike range
    min_strike = current_price * (1 - strike_range)
    max_strike = current_price * (1 + strike_range)

    # Get available expirations
    try:
        expirations = ticker.options
    except Exception as e:
        print(f"  Error getting expirations for {symbol}: {e}")
        return pd.DataFrame()

    if not expirations:
        print(f"  Warning: No expirations available for {symbol}")
        return pd.DataFrame()

    # Parse target date
    target_date = datetime.strptime(date_str, '%Y%m%d').date()

    # Find expiration matching or closest to target date
    matching_exp = None
    for exp in expirations:
        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        if exp_date == target_date:
            matching_exp = exp
            break

    # If no exact match, use the closest expiration
    if matching_exp is None:
        closest_exp = min(expirations, key=lambda x: abs(datetime.strptime(x, '%Y-%m-%d').date() - target_date))
        matching_exp = closest_exp
        print(f"  No expiration on {target_date}, using closest: {matching_exp}")
    else:
        print(f"  Using expiration: {matching_exp}")

    # Get options chain for the expiration
    try:
        opt_chain = ticker.option_chain(matching_exp)
    except Exception as e:
        print(f"  Error getting option chain: {e}")
        return pd.DataFrame()

    all_options = []
    now = datetime.now(pytz.timezone('US/Eastern'))

    # Process calls
    calls = opt_chain.calls
    calls = calls[(calls['strike'] >= min_strike) & (calls['strike'] <= max_strike)]
    for _, row in calls.iterrows():
        all_options.append({
            'symbol': display_symbol,
            'strike': row['strike'],
            'right': 'C',
            'time': now.strftime('%Y-%m-%d %H:%M:%S%z'),
            'expiration': matching_exp,
            'bid': row.get('bid', 0),
            'ask': row.get('ask', 0),
            'last': row.get('lastPrice', 0),
            'volume': row.get('volume', 0),
            'openInterest': row.get('openInterest', 0),
            'impliedVolatility': row.get('impliedVolatility', 0),
        })

    # Process puts
    puts = opt_chain.puts
    puts = puts[(puts['strike'] >= min_strike) & (puts['strike'] <= max_strike)]
    for _, row in puts.iterrows():
        all_options.append({
            'symbol': display_symbol,
            'strike': row['strike'],
            'right': 'P',
            'time': now.strftime('%Y-%m-%d %H:%M:%S%z'),
            'expiration': matching_exp,
            'bid': row.get('bid', 0),
            'ask': row.get('ask', 0),
            'last': row.get('lastPrice', 0),
            'volume': row.get('volume', 0),
            'openInterest': row.get('openInterest', 0),
            'impliedVolatility': row.get('impliedVolatility', 0),
        })

    df = pd.DataFrame(all_options)
    print(f"  Retrieved {len(df)} option contracts ({len(calls)} calls, {len(puts)} puts)")
    return df


def main():
    parser = argparse.ArgumentParser(description='Fetch options data using yfinance')
    parser.add_argument('--date', type=str, default=None,
                        help='Date in YYYYMMDD format (default: today)')
    parser.add_argument('--range', type=float, default=0.03,
                        help='Strike range around ATM (default: 0.03 = 3%%)')
    args = parser.parse_args()

    # Determine date
    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now().strftime('%Y%m%d')

    print(f"\n{'='*60}")
    print(f"Fetching data for {date_str} using yfinance")
    print(f"Strike range: ±{args.range*100:.1f}%")
    print(f"{'='*60}\n")

    # Create data directory if needed
    os.makedirs(DATA_DIR, exist_ok=True)

    # Fetch underlying 1-minute data
    print("\n--- Fetching Underlying 1-Minute Data ---\n")

    spy_underlying = get_underlying_1min_data('SPY', date_str)
    time.sleep(0.5)  # Rate limiting
    spx_underlying = get_underlying_1min_data('^GSPC', date_str)

    # Combine underlying data
    underlying_df = pd.concat([spy_underlying, spx_underlying], ignore_index=True)

    if not underlying_df.empty:
        underlying_file = os.path.join(DATA_DIR, f'underlying_prices_{date_str}.csv')
        underlying_df.to_csv(underlying_file, index=False)
        print(f"\nSaved underlying data to: {underlying_file}")
        print(f"Total underlying bars: {len(underlying_df)}")

    # Fetch options chain snapshots
    print("\n--- Fetching Options Chain Snapshots ---\n")
    print("NOTE: yfinance provides current chain snapshots, not historical intraday bars.")
    print("      For historical options intraday data, use IBKR (collect_market_data.py)\n")

    time.sleep(0.5)  # Rate limiting
    spy_options = get_options_chain_snapshot('SPY', date_str, args.range)
    time.sleep(0.5)  # Rate limiting
    spx_options = get_options_chain_snapshot('^GSPC', date_str, args.range)

    # Combine options data
    options_df = pd.concat([spy_options, spx_options], ignore_index=True)

    if not options_df.empty:
        options_file = os.path.join(DATA_DIR, f'options_chain_snapshot_{date_str}.csv')
        options_df.to_csv(options_file, index=False)
        print(f"\nSaved options chain snapshot to: {options_file}")
        print(f"Total option contracts: {len(options_df)}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Underlying 1-min bars: {len(underlying_df)}")
    print(f"Options contracts: {len(options_df)}")
    print(f"\nFiles saved to: {DATA_DIR}/")

    if not underlying_df.empty:
        print(f"\n--- Underlying Price Preview ---")
        print(underlying_df.head(10).to_string(index=False))

    if not options_df.empty:
        print(f"\n--- Options Chain Preview ---")
        print(options_df.head(10).to_string(index=False))

    print(f"\n{'='*60}")
    print("IMPORTANT NOTES:")
    print("- Underlying data: 1-minute historical bars (OHLCV)")
    print("- Options data: Current chain snapshot (bid/ask, not historical bars)")
    print("- For 1-min historical options bars, use IBKR via collect_market_data.py")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
