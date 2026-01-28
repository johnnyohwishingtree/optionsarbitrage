#!/usr/bin/env python3
"""
Analyze SPY/SPX Arbitrage Entry and Exit Opportunities

Analyzes 1-minute bar data to find:
1. Best entry times (maximum credit received)
2. Early exit opportunities (close position profitably before expiration)

Strategy:
- Sell 10 SPY ATM calls (collect premium)
- Buy 10 SPX/10 ATM calls (pay premium)
- Net credit = premium received - premium paid
- Exit when we can close for less than the credit received
"""

import pandas as pd
import numpy as np
from datetime import datetime

def load_data(date_str='20260126'):
    """Load underlying and options data"""
    underlying = pd.read_csv(f'data/underlying_prices_{date_str}.csv')
    options = pd.read_csv(f'data/options_data_{date_str}.csv')

    # Convert time to datetime
    underlying['time'] = pd.to_datetime(underlying['time'])
    options['time'] = pd.to_datetime(options['time'])

    return underlying, options


def find_atm_strike(price, symbol):
    """Find closest ATM strike for given price"""
    if symbol == 'SPY':
        return round(price)
    else:  # SPX
        return round(price / 5) * 5


def calculate_arbitrage_spread(options_df, spy_price, spx_price, time):
    """
    Calculate the arbitrage spread at a given time

    Returns:
        dict with entry details, or None if data not available
    """
    # Find ATM strikes
    spy_strike = find_atm_strike(spy_price, 'SPY')
    spx_strike = find_atm_strike(spx_price / 10, 'SPX') * 10  # SPX is 10x SPY

    # Get option prices at this time
    spy_call = options_df[
        (options_df['symbol'] == 'SPY') &
        (options_df['strike'] == spy_strike) &
        (options_df['right'] == 'C') &
        (options_df['time'] == time)
    ]

    spx_call = options_df[
        (options_df['symbol'] == 'SPX') &
        (options_df['strike'] == spx_strike) &
        (options_df['right'] == 'C') &
        (options_df['time'] == time)
    ]

    # Check if both options have data
    if spy_call.empty or spx_call.empty:
        return None

    # Use mid price (average of open and close)
    spy_call_price = (spy_call.iloc[0]['open'] + spy_call.iloc[0]['close']) / 2
    spx_call_price = (spx_call.iloc[0]['open'] + spx_call.iloc[0]['close']) / 2

    # Calculate spread (sell SPY, buy SPX/10)
    # Sell 10 SPY calls, Buy 10 SPX/10 calls
    premium_received = spy_call_price * 100 * 10  # Sell 10 contracts
    premium_paid = spx_call_price * 100  # Buy 1 contract (equivalent to 10 SPY)
    net_credit = premium_received - premium_paid

    return {
        'time': time,
        'spy_price': spy_price,
        'spx_price': spx_price,
        'spy_strike': spy_strike,
        'spx_strike': spx_strike,
        'spy_call_price': spy_call_price,
        'spx_call_price': spx_call_price,
        'net_credit': net_credit
    }


def find_exit_opportunity(entry, options_df, underlying_df):
    """
    Find if there's an opportunity to exit profitably after entry

    Returns:
        Best exit opportunity or None
    """
    # Get all times after entry
    exit_times = underlying_df[underlying_df['time'] > entry['time']]['time'].unique()

    best_exit = None
    best_profit = 0

    for exit_time in exit_times:
        # Get underlying prices at exit time
        spy_data = underlying_df[(underlying_df['symbol'] == 'SPY') & (underlying_df['time'] == exit_time)]
        spx_data = underlying_df[(underlying_df['symbol'] == 'SPX') & (underlying_df['time'] == exit_time)]

        if spy_data.empty or spx_data.empty:
            continue

        spy_price = spy_data.iloc[0]['close']
        spx_price = spx_data.iloc[0]['close']

        # Get option prices at exit time (using same strikes as entry)
        spy_call = options_df[
            (options_df['symbol'] == 'SPY') &
            (options_df['strike'] == entry['spy_strike']) &
            (options_df['right'] == 'C') &
            (options_df['time'] == exit_time)
        ]

        spx_call = options_df[
            (options_df['symbol'] == 'SPX') &
            (options_df['strike'] == entry['spx_strike']) &
            (options_df['right'] == 'C') &
            (options_df['time'] == exit_time)
        ]

        if spy_call.empty or spx_call.empty:
            continue

        # Use mid price
        spy_call_price = (spy_call.iloc[0]['open'] + spy_call.iloc[0]['close']) / 2
        spx_call_price = (spx_call.iloc[0]['open'] + spx_call.iloc[0]['close']) / 2

        # Calculate cost to close position
        # Buy back 10 SPY calls (we sold them), Sell 1 SPX call (we bought it)
        cost_to_close = (spy_call_price * 100 * 10) - (spx_call_price * 100)

        # Profit = credit received - cost to close
        profit = entry['net_credit'] - cost_to_close

        if profit > best_profit:
            best_profit = profit
            best_exit = {
                'time': exit_time,
                'spy_price': spy_price,
                'spx_price': spx_price,
                'spy_call_price': spy_call_price,
                'spx_call_price': spx_call_price,
                'cost_to_close': cost_to_close,
                'profit': profit,
                'profit_pct': (profit / abs(entry['net_credit'])) * 100 if entry['net_credit'] != 0 else 0
            }

    return best_exit


def main():
    print('=' * 80)
    print('SPY/SPX ARBITRAGE ANALYSIS - ENTRY AND EXIT OPPORTUNITIES')
    print('=' * 80)

    # Load data
    print('\n📊 Loading data...')
    underlying_df, options_df = load_data('20260126')

    print(f'   Underlying bars: {len(underlying_df):,}')
    print(f'   Options bars: {len(options_df):,}')

    # Analyze each minute throughout the day
    print('\n🔍 Analyzing every minute for arbitrage opportunities...')

    spy_data = underlying_df[underlying_df['symbol'] == 'SPY'].copy()
    spx_data = underlying_df[underlying_df['symbol'] == 'SPX'].copy()

    # Merge SPY and SPX data by time
    merged = pd.merge(
        spy_data[['time', 'close']].rename(columns={'close': 'spy_price'}),
        spx_data[['time', 'close']].rename(columns={'close': 'spx_price'}),
        on='time'
    )

    opportunities = []

    for idx, row in merged.iterrows():
        if idx % 50 == 0:
            print(f'   Processing minute {idx + 1}/{len(merged)}...', end='\r')

        spread = calculate_arbitrage_spread(
            options_df,
            row['spy_price'],
            row['spx_price'],
            row['time']
        )

        if spread:
            opportunities.append(spread)

    print(f'\n   Found {len(opportunities)} valid entry opportunities')

    if not opportunities:
        print('\n❌ No valid opportunities found')
        return

    # Convert to DataFrame and sort by net credit
    opps_df = pd.DataFrame(opportunities)
    opps_df = opps_df.sort_values('net_credit', ascending=False)

    print('\n' + '=' * 80)
    print('TOP 10 ENTRY OPPORTUNITIES (Best Net Credit)')
    print('=' * 80)

    top_entries = []

    for idx, entry in opps_df.head(10).iterrows():
        print(f'\n#{len(top_entries) + 1}. Entry at {entry["time"].strftime("%H:%M:%S")}')
        print(f'   SPY: ${entry["spy_price"]:.2f} | Strike: {entry["spy_strike"]} | Call: ${entry["spy_call_price"]:.2f}')
        print(f'   SPX: ${entry["spx_price"]:.2f} | Strike: {int(entry["spx_strike"])} | Call: ${entry["spx_call_price"]:.2f}')
        print(f'   Net Credit Received: ${entry["net_credit"]:,.2f}')

        # Find exit opportunity
        print('   Searching for exit opportunities...', end='')
        exit_opp = find_exit_opportunity(entry, options_df, underlying_df)

        if exit_opp:
            print(f' ✅ Found!')
            print(f'   Best Exit at {exit_opp["time"].strftime("%H:%M:%S")}')
            print(f'   SPY: ${exit_opp["spy_price"]:.2f} | Call: ${exit_opp["spy_call_price"]:.2f}')
            print(f'   SPX: ${exit_opp["spx_price"]:.2f} | Call: ${exit_opp["spx_call_price"]:.2f}')
            print(f'   Cost to Close: ${exit_opp["cost_to_close"]:,.2f}')
            print(f'   💰 PROFIT: ${exit_opp["profit"]:,.2f} ({exit_opp["profit_pct"]:.1f}%)')

            time_held = exit_opp['time'] - entry['time']
            minutes_held = time_held.total_seconds() / 60
            print(f'   Time Held: {int(minutes_held)} minutes')

            top_entries.append({
                'entry': entry,
                'exit': exit_opp,
                'minutes_held': minutes_held
            })
        else:
            print(' ❌ No profitable exit found')

    # Summary
    print('\n' + '=' * 80)
    print('SUMMARY')
    print('=' * 80)

    if top_entries:
        best = top_entries[0]
        print(f'\n🏆 BEST OPPORTUNITY:')
        print(f'   Entry Time: {best["entry"]["time"].strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Exit Time: {best["exit"]["time"].strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Time Held: {int(best["minutes_held"])} minutes')
        print(f'   Net Credit: ${best["entry"]["net_credit"]:,.2f}')
        print(f'   Exit Profit: ${best["exit"]["profit"]:,.2f} ({best["exit"]["profit_pct"]:.1f}%)')

        profitable_exits = sum(1 for e in top_entries if e['exit']['profit'] > 0)
        print(f'\n📈 {profitable_exits}/{len(top_entries)} top entries had profitable exit opportunities')

        avg_profit = np.mean([e['exit']['profit'] for e in top_entries])
        avg_time = np.mean([e['minutes_held'] for e in top_entries])
        print(f'   Average Profit: ${avg_profit:,.2f}')
        print(f'   Average Time Held: {int(avg_time)} minutes')

    # Save results
    results_file = 'data/entry_exit_analysis_20260126.csv'
    results = []
    for item in top_entries:
        results.append({
            'entry_time': item['entry']['time'],
            'spy_price': item['entry']['spy_price'],
            'spx_price': item['entry']['spx_price'],
            'net_credit': item['entry']['net_credit'],
            'exit_time': item['exit']['time'],
            'exit_spy_price': item['exit']['spy_price'],
            'exit_spx_price': item['exit']['spx_price'],
            'profit': item['exit']['profit'],
            'profit_pct': item['exit']['profit_pct'],
            'minutes_held': item['minutes_held']
        })

    if results:
        pd.DataFrame(results).to_csv(results_file, index=False)
        print(f'\n✅ Saved detailed results to {results_file}')


if __name__ == '__main__':
    main()
