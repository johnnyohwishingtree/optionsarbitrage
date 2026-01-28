#!/usr/bin/env python3
"""
Standard Data Collection Script for SPY/SPX Options Arbitrage

Collects full-day historical data:
- SPY and SPX underlying prices (1-minute bars)
- SPY and SPX options within ±3% of opening price (1-minute bars)

Features:
- Uses 1-minute bars for high-resolution data
- Incremental updates: Only fetches new data since last run
- Automatically resumes from where it left off

Usage:
    python collect_market_data.py                    # Collect/update today's data
    python collect_market_data.py --date 20260126    # Collect specific date
    python collect_market_data.py --full             # Force full re-fetch (ignore existing)

Output files saved to data/:
    - underlying_prices_{date}.csv    (SPY/SPX stock prices)
    - options_data_{date}.csv         (all options within ±3%)
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.broker.ibkr_client import IBKRClient
from ib_insync import Option, Stock, Index


def get_last_timestamp(file_path):
    """Get the last timestamp from existing data file"""
    if not os.path.exists(file_path):
        return None

    try:
        df = pd.read_csv(file_path)
        if len(df) == 0:
            return None

        df['time'] = pd.to_datetime(df['time'])
        return df['time'].max()
    except Exception as e:
        print(f'   Warning: Could not read existing file: {e}')
        return None


def collect_daily_data(date_str=None, strike_range_pct=0.03, force_full=False):
    """
    Collect full-day historical data for SPY/SPX stocks and options

    Args:
        date_str: Date in YYYYMMDD format (default: today)
        strike_range_pct: Strike range as percentage (default: 0.03 for ±3%)
        force_full: If True, re-fetch all data (ignore existing)
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')

    print('='*70)
    print(f'📊 COLLECTING MARKET DATA FOR {date_str}')
    print('='*70)

    # Define output file paths
    underlying_file = f'data/underlying_prices_{date_str}.csv'
    options_file = f'data/options_data_{date_str}.csv'

    # Check for existing data (incremental mode)
    last_underlying_time = None
    last_options_time = None

    if not force_full:
        last_underlying_time = get_last_timestamp(underlying_file)
        last_options_time = get_last_timestamp(options_file)

        if last_underlying_time:
            print(f'\n📁 Found existing data')
            print(f'   Underlying last update: {last_underlying_time}')
        if last_options_time:
            print(f'   Options last update: {last_options_time}')

    # Connect to IB Gateway
    client = IBKRClient(port=4002, client_id=600)
    if not client.connect():
        print('❌ Failed to connect to IB Gateway')
        return

    try:
        # Step 1: Get current/reference prices to determine strike range
        print('\n1️⃣  Fetching reference prices...')
        spy_price = client.get_current_price('SPY')
        spx_price = client.get_current_price('SPX')

        if not spy_price or not spx_price:
            print('❌ Could not fetch reference prices')
            return

        print(f'   SPY: ${spy_price:.2f}')
        print(f'   SPX: ${spx_price:.2f}')

        # Step 2: Fetch underlying historical prices
        print('\n2️⃣  Fetching underlying stock prices (1-minute bars)...')
        underlying_data = []

        for symbol in ['SPY', 'SPX']:
            print(f'   Fetching {symbol}...', end=' ')

            # SPX is an index, SPY is a stock
            if symbol == 'SPX':
                contract = Index('SPX', 'CBOE', 'USD')
            else:
                contract = Stock(symbol, 'SMART', 'USD')

            client.ib.qualifyContracts(contract)

            bars = client.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            print(f'{len(bars)} bars')

            for bar in bars:
                bar_time = pd.to_datetime(bar.date)

                # Skip if we already have this data (incremental mode)
                if last_underlying_time and bar_time <= last_underlying_time:
                    continue

                underlying_data.append({
                    'symbol': symbol,
                    'time': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                })

        # Save or append underlying prices
        if underlying_data:
            new_df = pd.DataFrame(underlying_data)

            if os.path.exists(underlying_file) and not force_full:
                # Append to existing data
                existing_df = pd.read_csv(underlying_file)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_csv(underlying_file, index=False)
                print(f'   ✅ Appended {len(new_df)} new bars to {underlying_file}')
            else:
                # Create new file
                new_df.to_csv(underlying_file, index=False)
                print(f'   ✅ Saved {len(new_df)} bars to {underlying_file}')
        else:
            print(f'   ℹ️  No new underlying data to add')

        # Step 3: Calculate strike ranges (±3%)
        print(f'\n3️⃣  Calculating strike ranges (±{strike_range_pct*100:.0f}%)...')

        spy_min = round(spy_price * (1 - strike_range_pct))
        spy_max = round(spy_price * (1 + strike_range_pct))
        spy_strikes = list(range(spy_min, spy_max + 1, 1))

        spx_min = round((spx_price * (1 - strike_range_pct)) / 5) * 5
        spx_max = round((spx_price * (1 + strike_range_pct)) / 5) * 5
        spx_strikes = list(range(int(spx_min), int(spx_max) + 5, 5))

        print(f'   SPY strikes: {spy_min} - {spy_max} ({len(spy_strikes)} strikes)')
        print(f'   SPX strikes: {int(spx_min)} - {int(spx_max)} ({len(spx_strikes)} strikes)')

        total_contracts = (len(spy_strikes) + len(spx_strikes)) * 2
        print(f'   Total contracts to fetch: {total_contracts}')

        # Step 4: Fetch options historical data
        print(f'\n4️⃣  Fetching options data (1-minute bars)...')
        options_data = []
        current = 0

        # Fetch SPY options
        for strike in spy_strikes:
            for right in ['C', 'P']:
                current += 1
                print(f'   [{current}/{total_contracts}] SPY {strike} {right}', end=' ')

                try:
                    contract = Option('SPY', date_str, strike, right, 'SMART')
                    client.ib.qualifyContracts(contract)

                    bars = client.ib.reqHistoricalData(
                        contract,
                        endDateTime='',
                        durationStr='1 D',
                        barSizeSetting='1 min',
                        whatToShow='TRADES',
                        useRTH=True,
                        formatDate=1
                    )

                    new_bars = 0
                    for bar in bars:
                        bar_time = pd.to_datetime(bar.date)

                        # Skip if we already have this data (incremental mode)
                        if last_options_time and bar_time <= last_options_time:
                            continue

                        options_data.append({
                            'symbol': 'SPY',
                            'strike': strike,
                            'right': right,
                            'time': bar.date,
                            'open': bar.open,
                            'high': bar.high,
                            'low': bar.low,
                            'close': bar.close,
                            'volume': bar.volume
                        })
                        new_bars += 1

                    if new_bars > 0:
                        print(f'→ {new_bars} new bars')
                    else:
                        print(f'→ {len(bars)} total (0 new)')

                except Exception as e:
                    print(f'→ Error: {e}')

        # Fetch SPX options
        for strike in spx_strikes:
            for right in ['C', 'P']:
                current += 1
                print(f'   [{current}/{total_contracts}] SPX {strike} {right}', end=' ')

                try:
                    contract = Option('SPX', date_str, strike, right, 'SMART')
                    client.ib.qualifyContracts(contract)

                    bars = client.ib.reqHistoricalData(
                        contract,
                        endDateTime='',
                        durationStr='1 D',
                        barSizeSetting='1 min',
                        whatToShow='TRADES',
                        useRTH=True,
                        formatDate=1
                    )

                    new_bars = 0
                    for bar in bars:
                        bar_time = pd.to_datetime(bar.date)

                        # Skip if we already have this data (incremental mode)
                        if last_options_time and bar_time <= last_options_time:
                            continue

                        options_data.append({
                            'symbol': 'SPX',
                            'strike': strike,
                            'right': right,
                            'time': bar.date,
                            'open': bar.open,
                            'high': bar.high,
                            'low': bar.low,
                            'close': bar.close,
                            'volume': bar.volume
                        })
                        new_bars += 1

                    if new_bars > 0:
                        print(f'→ {new_bars} new bars')
                    else:
                        print(f'→ {len(bars)} total (0 new)')

                except Exception as e:
                    print(f'→ Error: {e}')

        # Save or append options data
        if options_data:
            new_df = pd.DataFrame(options_data)

            if os.path.exists(options_file) and not force_full:
                # Append to existing data
                existing_df = pd.read_csv(options_file)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_csv(options_file, index=False)

                print(f'\n✅ COLLECTION COMPLETE (INCREMENTAL UPDATE)')
                print(f'   Options file: {options_file}')
                print(f'   New bars added: {len(new_df):,}')
                print(f'   Total bars now: {len(combined_df):,}')
                print(f'   Underlying file: {underlying_file}')
            else:
                # Create new file
                new_df.to_csv(options_file, index=False)

                print(f'\n✅ COLLECTION COMPLETE')
                print(f'   Options file: {options_file}')
                print(f'   Total bars: {len(new_df):,}')
                print(f'   Unique contracts: {len(new_df.groupby(["symbol", "strike", "right"]))}')
                print(f'   Underlying file: {underlying_file}')
        else:
            print('\n✅ COLLECTION COMPLETE')
            print(f'   ℹ️  No new options data to add')
            print(f'   All data is up to date!')

    finally:
        client.disconnect()
        print('\n✅ Disconnected from IB Gateway')


def main():
    parser = argparse.ArgumentParser(
        description='Collect full-day historical data for SPY/SPX stocks and options (1-minute bars)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python collect_market_data.py                    # Collect/update today's data (incremental)
  python collect_market_data.py --date 20260126    # Collect specific date (incremental)
  python collect_market_data.py --full             # Force full re-fetch (ignore existing data)
  python collect_market_data.py --range 0.05       # Use ±5% strike range

Incremental Mode (default):
  - Script checks existing data files
  - Only fetches new bars since last timestamp
  - Appends new data to existing files
  - Run multiple times per day to keep data current

Full Mode (--full flag):
  - Ignores existing data
  - Fetches all data from scratch
  - Overwrites existing files
        """
    )

    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Date in YYYYMMDD format (default: today)'
    )

    parser.add_argument(
        '--range',
        type=float,
        default=0.03,
        help='Strike range as decimal (default: 0.03 for ±3%%)'
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Force full re-fetch, ignore existing data'
    )

    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)

    # Collect data
    collect_daily_data(
        date_str=args.date,
        strike_range_pct=args.range,
        force_full=args.full
    )


if __name__ == "__main__":
    main()
