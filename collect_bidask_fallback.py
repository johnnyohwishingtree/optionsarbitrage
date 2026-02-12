#!/usr/bin/env python3
"""
Fallback collection for expired 0DTE options via BID_ASK data.

IB's HMDS is unreliable for batch TRADES requests on expired options,
but BID_ASK works one-at-a-time. This script:
  1. Fetches BID_ASK data in small batches (5 contracts)
  2. Saves options_bidask_{date}.csv
  3. Also generates options_data_{date}.csv using midpoint as close price
"""

import sys, os, time, asyncio, argparse
import pandas as pd

import ib_async
sys.modules['ib_insync'] = ib_async
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.broker.ibkr_client import IBKRClient
from ib_async import Option, Stock, Index

INDEX_SYMBOLS = {'SPX', 'XSP'}
BATCH_SIZE = 5  # Small batches for reliability with expired options


def collect(date_str, symbols, strike_range_pct=0.03):
    underlying_file = f'data/underlying_prices_{date_str}.csv'
    options_file = f'data/options_data_{date_str}.csv'
    bidask_file = f'data/options_bidask_{date_str}.csv'

    # Get reference prices from underlying data
    if not os.path.exists(underlying_file):
        print(f'❌ No underlying data: {underlying_file}')
        return
    df_u = pd.read_csv(underlying_file)
    ref_prices = {}
    for sym in symbols:
        rows = df_u[df_u['symbol'] == sym]
        if rows.empty:
            print(f'❌ No underlying data for {sym}')
            return
        ref_prices[sym] = rows.iloc[0]['close']
        print(f'   {sym}: ${ref_prices[sym]:.2f} (from open bar)')

    # Build contract list
    all_contracts = []
    for sym in symbols:
        price = ref_prices[sym]
        step = 5 if sym == 'SPX' else 1
        s_min = round((price * (1 - strike_range_pct)) / step) * step
        s_max = round((price * (1 + strike_range_pct)) / step) * step
        strikes = list(range(int(s_min), int(s_max) + step, step))
        print(f'   {sym}: {len(strikes)} strikes ({s_min}-{s_max})')
        for strike in strikes:
            for right in ['C', 'P']:
                all_contracts.append((sym, strike, right))

    total = len(all_contracts)
    print(f'\n📊 Total contracts: {total}')

    client = IBKRClient(port=4002, client_id=605)
    if not client.connect():
        print('❌ Failed to connect')
        return

    try:
        # Suppress Error 162
        _suppressed = []
        def _quiet(reqId, errorCode, errorString, contract):
            if errorCode == 162:
                _suppressed.append(errorCode)
            else:
                print(f'   IB Error {errorCode}: {errorString}')
        client.ib.errorEvent.clear()
        client.ib.errorEvent += _quiet

        # Qualify all contracts first
        print('   Qualifying contracts...', end=' ')
        qualified = []
        for i in range(0, total, 50):
            batch = all_contracts[i:i+50]
            contracts = [Option(sym, date_str, strike, right, 'SMART') for sym, strike, right in batch]
            client.ib.qualifyContracts(*contracts)
            qualified.extend(zip(batch, contracts))
        print('done')

        # Fetch BID_ASK sequentially (one at a time — reliable for expired options)
        bidask_data = []
        options_data = []
        errors = 0
        no_data = 0

        for idx, ((sym, strike, right), contract) in enumerate(qualified):
            pct = (idx + 1) / total * 100
            print(f'\r   [{idx+1}/{total}] ({pct:.0f}%) {sym} {strike}{right}', end='', flush=True)

            try:
                bars = client.ib.reqHistoricalData(
                    contract, endDateTime='', durationStr='1 D',
                    barSizeSetting='1 min', whatToShow='BID_ASK',
                    useRTH=True, formatDate=1, timeout=20
                )
            except Exception as e:
                errors += 1
                continue

            if not bars:
                no_data += 1
                continue

            for bar in bars:
                bid = bar.low
                ask = bar.high
                mid = bar.close

                bidask_data.append({
                    'symbol': sym, 'strike': strike, 'right': right,
                    'time': bar.date, 'bid': bid, 'ask': ask, 'midpoint': mid
                })
                # Also create TRADES-format row using midpoint
                options_data.append({
                    'symbol': sym, 'strike': strike, 'right': right,
                    'time': bar.date, 'open': mid, 'high': ask,
                    'low': bid, 'close': mid, 'volume': 0
                })

        print()  # newline after progress

        print(f'\n   {len(_suppressed)} "no data" responses suppressed')
        if errors:
            print(f'   {errors} request errors')

        # Save bidask
        if bidask_data:
            df_ba = pd.DataFrame(bidask_data)
            df_ba.to_csv(bidask_file, index=False)
            print(f'\n✅ BID_ASK: {len(df_ba):,} bars -> {bidask_file}')
            print(f'   Contracts: {len(df_ba.groupby(["symbol","strike","right"]))}')

        # Save options_data (midpoint-based)
        if options_data:
            df_opt = pd.DataFrame(options_data)
            df_opt.to_csv(options_file, index=False)
            print(f'✅ OPTIONS (midpoint): {len(df_opt):,} bars -> {options_file}')
            print(f'   Contracts: {len(df_opt.groupby(["symbol","strike","right"]))}')

    finally:
        client.disconnect()
        print('\n✅ Done')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default='20260209')
    parser.add_argument('--symbols', default='XSP,SPX')
    parser.add_argument('--range', type=float, default=0.03)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    os.makedirs('data', exist_ok=True)
    collect(args.date, symbols, args.range)
