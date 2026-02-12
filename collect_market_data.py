#!/usr/bin/env python3
"""
Standard Data Collection Script for SPY/SPX/XSP Options Arbitrage

Collects full-day historical data:
- SPY, SPX, and XSP underlying prices (1-minute bars)
- SPY, SPX, and XSP options within ±3% of opening price (1-minute bars)

Features:
- Uses 1-minute bars for high-resolution data
- Incremental updates: Only fetches new data since last run
- Automatically resumes from where it left off

Usage:
    python collect_market_data.py                    # Collect/update today's data
    python collect_market_data.py --date 20260126    # Collect specific date
    python collect_market_data.py --full             # Force full re-fetch (ignore existing)
    python collect_market_data.py --data-type bidask # Collect BID_ASK data only
    python collect_market_data.py --data-type both   # Collect TRADES + BID_ASK
    python collect_market_data.py --symbols XSP      # Collect only XSP
    python collect_market_data.py --symbols SPY,XSP  # Collect SPY + XSP

Output files saved to data/:
    - underlying_prices_{date}.csv    (SPY/SPX/XSP underlying prices)
    - options_data_{date}.csv         (all options within ±3% - TRADES)
    - options_bidask_{date}.csv       (bid/ask/midpoint data)
"""

import sys
import os
import time
import asyncio
import argparse
from datetime import datetime, timedelta
import pandas as pd

# ib_insync is unmaintained; use ib_async as drop-in replacement
import ib_async
sys.modules['ib_insync'] = ib_async

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.broker.ibkr_client import IBKRClient
from ib_async import Option, Stock, Index


def get_last_timestamp(file_path):
    """Get the last timestamp from existing data file"""
    if not os.path.exists(file_path):
        return None

    try:
        df = pd.read_csv(file_path)
        if len(df) == 0:
            return None

        # Use utc=True to handle mixed timezones, then convert to tz-naive for comparison
        df['time'] = pd.to_datetime(df['time'], utc=True)
        return df['time'].max()
    except Exception as e:
        print(f'   Warning: Could not read existing file: {e}')
        return None


def collect_daily_data(date_str=None, strike_range_pct=0.03, force_full=False, data_type='trades', symbols=None):
    """
    Collect full-day historical data for stocks and options

    Args:
        date_str: Date in YYYYMMDD format (default: today)
        strike_range_pct: Strike range as percentage (default: 0.03 for ±3%)
        force_full: If True, re-fetch all data (ignore existing)
        data_type: 'trades' (default), 'bidask', or 'both'
        symbols: List of symbols to collect (default: ['SPY', 'SPX'])
    """
    if symbols is None:
        symbols = ['SPY', 'SPX', 'XSP']
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')

    print('='*70)
    print(f'📊 COLLECTING MARKET DATA FOR {date_str}')
    print('='*70)

    collect_trades = data_type in ('trades', 'both')
    collect_bidask = data_type in ('bidask', 'both')

    # Define output file paths
    underlying_file = f'data/underlying_prices_{date_str}.csv'
    options_file = f'data/options_data_{date_str}.csv'
    bidask_file = f'data/options_bidask_{date_str}.csv'

    # Check for existing data (incremental mode)
    last_underlying_time = None
    last_options_time = None
    last_bidask_time = None

    if not force_full:
        last_underlying_time = get_last_timestamp(underlying_file)
        last_options_time = get_last_timestamp(options_file)
        if collect_bidask:
            last_bidask_time = get_last_timestamp(bidask_file)

        if last_underlying_time:
            print(f'\n📁 Found existing data')
            print(f'   Underlying last update: {last_underlying_time}')
        if last_options_time:
            print(f'   Options last update: {last_options_time}')
        if last_bidask_time:
            print(f'   BID_ASK last update: {last_bidask_time}')

    # Connect to IB Gateway
    client = IBKRClient(port=4002, client_id=600)
    if not client.connect():
        print('❌ Failed to connect to IB Gateway')
        return

    try:
        # Index-type symbols (use Index contract for underlying)
        INDEX_SYMBOLS = {'SPX', 'XSP'}

        # Step 1: Fetch underlying historical prices (done first so we can derive reference prices)
        print('\n1️⃣  Fetching underlying stock prices (1-minute bars)...')
        underlying_data = []
        _underlying_bars = {}  # sym -> list of bars (for reference price fallback)

        for symbol in symbols:
            print(f'   Fetching {symbol}...', end=' ')

            if symbol in INDEX_SYMBOLS:
                contract = Index(symbol, 'CBOE', 'USD')
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
            _underlying_bars[symbol] = bars

            for bar in bars:
                bar_time = pd.to_datetime(bar.date, utc=True)

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

        # Step 2: Determine reference prices for strike range calculation
        # Use live market data if available, otherwise fall back to underlying bar data
        print('\n2️⃣  Determining reference prices for strike ranges...')
        ref_prices = {}

        # Try live/delayed market data first (parallel — single sleep for all symbols)
        _ref_contracts = {}
        for sym in symbols:
            if sym in INDEX_SYMBOLS:
                c = Index(sym, 'CBOE', 'USD')
            else:
                c = Stock(sym, 'SMART', 'USD')
            client.ib.qualifyContracts(c)
            _ref_contracts[sym] = c

        _ref_tickers = {sym: client.ib.reqMktData(c) for sym, c in _ref_contracts.items()}
        client.ib.sleep(3)  # Single wait for all symbols

        for sym in symbols:
            ticker = _ref_tickers[sym]
            price = ticker.marketPrice()
            if not price or price != price or price <= 0:  # NaN check
                price = ticker.last if (ticker.last and ticker.last == ticker.last and ticker.last > 0) else None
            if not price or price <= 0:
                price = ticker.close if (ticker.close and ticker.close == ticker.close and ticker.close > 0) else None

            # Fallback: use the first bar's close from the underlying data we just fetched
            if not price or price <= 0:
                bars = _underlying_bars.get(sym, [])
                if bars:
                    price = bars[0].close
                    print(f'   {sym}: ${price:.2f} (from historical bars)')
                else:
                    print(f'❌ Could not determine reference price for {sym}')
                    return
            else:
                print(f'   {sym}: ${price:.2f}')

            ref_prices[sym] = price

        # Step 3: Calculate strike ranges (±3%)
        print(f'\n3️⃣  Calculating strike ranges (±{strike_range_pct*100:.0f}%)...')

        # Strike config: SPX uses $5 increments, everything else uses $1
        strike_configs = {}
        all_contracts = []
        total_contracts = 0

        for sym in symbols:
            price = ref_prices[sym]
            if sym == 'SPX':
                step = 5
                s_min = round((price * (1 - strike_range_pct)) / step) * step
                s_max = round((price * (1 + strike_range_pct)) / step) * step
                strikes = list(range(int(s_min), int(s_max) + step, step))
            else:
                # SPY, XSP, and other $1-increment symbols
                step = 1
                s_min = round(price * (1 - strike_range_pct))
                s_max = round(price * (1 + strike_range_pct))
                strikes = list(range(s_min, s_max + 1, step))

            strike_configs[sym] = strikes
            print(f'   {sym} strikes: {s_min} - {s_max} ({len(strikes)} strikes)')

            for strike in strikes:
                for right in ['C', 'P']:
                    all_contracts.append((sym, strike, right))

        total_contracts = len(all_contracts)
        print(f'   Total contracts to fetch: {total_contracts}')

        # Step 4: Fetch options historical data (concurrent batches)
        data_types_label = ' + '.join(filter(None, ['TRADES' if collect_trades else '', 'BID_ASK' if collect_bidask else '']))
        # IB allows ~50 concurrent historical data requests
        # When collecting both types, fire TRADES + BID_ASK together (N contracts × 2 = 2N requests)
        if collect_trades and collect_bidask:
            BATCH_SIZE = 22  # 22 × 2 = 44 concurrent requests (under ~50 limit)
        else:
            BATCH_SIZE = 45
        print(f'\n4️⃣  Fetching {data_types_label} options data (1-minute bars, batch size {BATCH_SIZE})...')

        options_data = []
        bidask_data = []

        # Qualify all contracts upfront in larger batches (qualification is lightweight)
        QUAL_BATCH = 50
        print(f'   Qualifying {total_contracts} contracts...', end=' ')
        qualified_contracts = []
        for i in range(0, total_contracts, QUAL_BATCH):
            batch = all_contracts[i:i+QUAL_BATCH]
            contracts = [Option(sym, date_str, strike, right, 'SMART') for sym, strike, right in batch]
            client.ib.qualifyContracts(*contracts)
            qualified_contracts.extend(zip(batch, contracts))
        print('done')

        # Suppress noisy "no data" errors (Error 162) from IB during batch collection
        _orig_error_handler = client.ib.errorEvent
        _suppressed_errors = []
        def _quiet_error(reqId, errorCode, errorString, contract):
            if errorCode == 162:  # "HMDS query returned no data" — expected for illiquid strikes
                _suppressed_errors.append((reqId, errorString))
            else:
                print(f'   IB Error {errorCode}: {errorString}')
        client.ib.errorEvent.clear()
        client.ib.errorEvent += _quiet_error

        # Check if async API is available
        use_async = hasattr(client.ib, 'reqHistoricalDataAsync')
        if not use_async:
            print('   ⚠️  Async API not available, falling back to sequential mode')
            BATCH_SIZE = 1

        # Process in batches — fire ALL request types in a single gather per batch
        total_batches = (total_contracts + BATCH_SIZE - 1) // BATCH_SIZE
        error_count = 0
        for batch_idx in range(total_batches):
            batch_start = batch_idx * BATCH_SIZE
            batch_end = min(batch_start + BATCH_SIZE, total_contracts)
            batch = qualified_contracts[batch_start:batch_end]

            print(f'   Batch {batch_idx+1}/{total_batches} [{batch_start+1}-{batch_end}/{total_contracts}]', end=' ')

            if use_async:
                # Fire TRADES and BID_ASK together in a single asyncio.gather
                futures = []
                request_meta = []  # Track (type, sym, strike, right) per future
                for (sym, strike, right), contract in batch:
                    if collect_trades:
                        futures.append(
                            client.ib.reqHistoricalDataAsync(
                                contract, endDateTime='', durationStr='1 D',
                                barSizeSetting='1 min', whatToShow='TRADES',
                                useRTH=True, formatDate=1
                            )
                        )
                        request_meta.append(('T', sym, strike, right))
                    if collect_bidask:
                        futures.append(
                            client.ib.reqHistoricalDataAsync(
                                contract, endDateTime='', durationStr='1 D',
                                barSizeSetting='1 min', whatToShow='BID_ASK',
                                useRTH=True, formatDate=1
                            )
                        )
                        request_meta.append(('BA', sym, strike, right))

                results = client.ib.run(asyncio.gather(*futures, return_exceptions=True))

                trade_bar_count = 0
                ba_bar_count = 0
                for meta, bars in zip(request_meta, results):
                    req_type, sym, strike, right = meta
                    if isinstance(bars, Exception):
                        error_count += 1
                        continue
                    if not bars:
                        continue
                    if req_type == 'T':
                        for bar in bars:
                            bar_time = pd.to_datetime(bar.date, utc=True)
                            if last_options_time and bar_time <= last_options_time:
                                continue
                            options_data.append({
                                'symbol': sym, 'strike': strike, 'right': right,
                                'time': bar.date, 'open': bar.open, 'high': bar.high,
                                'low': bar.low, 'close': bar.close, 'volume': bar.volume
                            })
                            trade_bar_count += 1
                    else:  # BA
                        for bar in bars:
                            bar_time = pd.to_datetime(bar.date, utc=True)
                            if last_bidask_time and bar_time <= last_bidask_time:
                                continue
                            bidask_data.append({
                                'symbol': sym, 'strike': strike, 'right': right,
                                'time': bar.date, 'bid': bar.low, 'ask': bar.high,
                                'midpoint': bar.close
                            })
                            ba_bar_count += 1

                if collect_trades:
                    print(f'T:{trade_bar_count}', end=' ')
                if collect_bidask:
                    print(f'BA:{ba_bar_count}', end='')
            else:
                # Sequential fallback
                if collect_trades:
                    trade_bar_count = 0
                    for (sym, strike, right), contract in batch:
                        try:
                            bars = client.ib.reqHistoricalData(
                                contract, endDateTime='', durationStr='1 D',
                                barSizeSetting='1 min', whatToShow='TRADES',
                                useRTH=True, formatDate=1
                            )
                        except Exception as e:
                            bars = e
                        if isinstance(bars, Exception):
                            error_count += 1
                        elif bars:
                            for bar in bars:
                                bar_time = pd.to_datetime(bar.date, utc=True)
                                if last_options_time and bar_time <= last_options_time:
                                    continue
                                options_data.append({
                                    'symbol': sym, 'strike': strike, 'right': right,
                                    'time': bar.date, 'open': bar.open, 'high': bar.high,
                                    'low': bar.low, 'close': bar.close, 'volume': bar.volume
                                })
                                trade_bar_count += 1
                        time.sleep(0.5)
                    print(f'T:{trade_bar_count}', end=' ')

                if collect_bidask:
                    ba_bar_count = 0
                    for (sym, strike, right), contract in batch:
                        try:
                            bars = client.ib.reqHistoricalData(
                                contract, endDateTime='', durationStr='1 D',
                                barSizeSetting='1 min', whatToShow='BID_ASK',
                                useRTH=True, formatDate=1
                            )
                        except Exception as e:
                            bars = e
                        if isinstance(bars, Exception):
                            error_count += 1
                        elif bars:
                            for bar in bars:
                                bar_time = pd.to_datetime(bar.date, utc=True)
                                if last_bidask_time and bar_time <= last_bidask_time:
                                    continue
                                bidask_data.append({
                                    'symbol': sym, 'strike': strike, 'right': right,
                                    'time': bar.date, 'bid': bar.low, 'ask': bar.high,
                                    'midpoint': bar.close
                                })
                                ba_bar_count += 1
                        time.sleep(0.5)
                    print(f'BA:{ba_bar_count}', end='')

            print()

            # Brief pause between batches to avoid pacing violations
            if batch_idx < total_batches - 1:
                time.sleep(1)

        # Restore original error handler
        client.ib.errorEvent.clear()
        client.ib.errorEvent = _orig_error_handler

        if error_count > 0:
            print(f'   ⚠️  {error_count} requests failed (contract not found or pacing violation)')
        if _suppressed_errors:
            print(f'   ℹ️  {len(_suppressed_errors)} contracts had no data (illiquid/no trades)')

        # Save or append TRADES options data
        if collect_trades:
            if options_data:
                new_df = pd.DataFrame(options_data)

                if os.path.exists(options_file) and not force_full:
                    existing_df = pd.read_csv(options_file)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    combined_df.to_csv(options_file, index=False)

                    print(f'\n   ✅ TRADES: Appended {len(new_df):,} new bars to {options_file}')
                    print(f'   Total bars now: {len(combined_df):,}')
                else:
                    new_df.to_csv(options_file, index=False)

                    print(f'\n   ✅ TRADES: Saved {len(new_df):,} bars to {options_file}')
                    print(f'   Unique contracts: {len(new_df.groupby(["symbol", "strike", "right"]))}')
            else:
                print(f'\n   ℹ️  No new TRADES data to add')

        # Save or append BID_ASK data
        if collect_bidask:
            if bidask_data:
                new_df = pd.DataFrame(bidask_data)

                if os.path.exists(bidask_file) and not force_full:
                    existing_df = pd.read_csv(bidask_file)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    combined_df.to_csv(bidask_file, index=False)

                    print(f'\n   ✅ BID_ASK: Appended {len(new_df):,} new bars to {bidask_file}')
                    print(f'   Total bars now: {len(combined_df):,}')
                else:
                    new_df.to_csv(bidask_file, index=False)

                    print(f'\n   ✅ BID_ASK: Saved {len(new_df):,} bars to {bidask_file}')
                    print(f'   Unique contracts: {len(new_df.groupby(["symbol", "strike", "right"]))}')
            else:
                print(f'\n   ℹ️  No new BID_ASK data to add')

        print(f'\n✅ COLLECTION COMPLETE')
        print(f'   Underlying file: {underlying_file}')
        if collect_trades:
            print(f'   TRADES file: {options_file}')
        if collect_bidask:
            print(f'   BID_ASK file: {bidask_file}')

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
  python collect_market_data.py --data-type bidask # Collect BID_ASK data only
  python collect_market_data.py --data-type both   # Collect TRADES + BID_ASK data
  python collect_market_data.py --symbols XSP      # Collect only XSP
  python collect_market_data.py --symbols SPY,XSP  # Collect SPY + XSP

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

    parser.add_argument(
        '--data-type',
        type=str,
        default='trades',
        choices=['trades', 'bidask', 'both'],
        help='Data type to collect: trades (default), bidask, or both'
    )

    parser.add_argument(
        '--symbols',
        type=str,
        default=None,
        help='Comma-separated symbols to collect (default: SPY,SPX,XSP). Example: --symbols SPY,XSP'
    )

    args = parser.parse_args()

    # Parse symbols list
    symbols_list = None
    if args.symbols:
        symbols_list = [s.strip().upper() for s in args.symbols.split(',')]

    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)

    # Collect data
    collect_daily_data(
        date_str=args.date,
        strike_range_pct=args.range,
        force_full=args.full,
        data_type=args.data_type,
        symbols=symbols_list
    )


if __name__ == "__main__":
    main()
