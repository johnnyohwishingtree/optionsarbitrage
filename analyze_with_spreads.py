#!/usr/bin/env python3
"""
Analyze SPY/SPX Arbitrage with Realistic Bid-Ask Spreads

Uses bid-ask spread to calculate realistic entry and exit costs:
- Entry: Sell SPY at BID, Buy SPX at ASK (worst case for us)
- Exit: Buy SPY at ASK, Sell SPX at BID (worst case for us)

Assumes typical 0DTE ATM spread: 2-5 cents for liquid options
"""

import pandas as pd
import numpy as np
from datetime import datetime

def estimate_bid_ask(price):
    """
    Estimate bid-ask spread based on option price
    ATM 0DTE options typically have tight spreads on SPY/SPX
    """
    if price < 0.50:
        spread = 0.05  # 5 cent spread for cheap options
    elif price < 2.00:
        spread = 0.03  # 3 cent spread
    else:
        spread = 0.05  # 5 cent spread for more expensive

    bid = price - spread / 2
    ask = price + spread / 2
    return bid, ask


def load_data(date_str='20260126'):
    """Load underlying and options data"""
    underlying = pd.read_csv(f'data/underlying_prices_{date_str}.csv')
    options = pd.read_csv(f'data/options_data_{date_str}.csv')

    underlying['time'] = pd.to_datetime(underlying['time'])
    options['time'] = pd.to_datetime(options['time'])

    return underlying, options


def find_atm_strike(price, symbol):
    """Find closest ATM strike for given price"""
    if symbol == 'SPY':
        return round(price)
    else:  # SPX
        return round(price / 5) * 5


def calculate_arbitrage_spread_realistic(options_df, spy_price, spx_price, time):
    """
    Calculate the arbitrage spread with bid-ask spreads

    Returns:
        dict with entry details, or None if data not available
    """
    spy_strike = find_atm_strike(spy_price, 'SPY')
    spx_strike = find_atm_strike(spx_price / 10, 'SPX') * 10

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

    if spy_call.empty or spx_call.empty:
        return None

    spy_mid = (spy_call.iloc[0]['open'] + spy_call.iloc[0]['close']) / 2
    spx_mid = (spx_call.iloc[0]['open'] + spx_call.iloc[0]['close']) / 2

    # Calculate bid-ask for entry
    spy_bid, spy_ask = estimate_bid_ask(spy_mid)
    spx_bid, spx_ask = estimate_bid_ask(spx_mid)

    # ENTRY: Sell SPY at BID (receive less), Buy SPX at ASK (pay more)
    premium_received = spy_bid * 100 * 10  # Sell 10 SPY calls at BID
    premium_paid = spx_ask * 100  # Buy 1 SPX call at ASK
    net_credit = premium_received - premium_paid

    return {
        'time': time,
        'spy_price': spy_price,
        'spx_price': spx_price,
        'spy_strike': spy_strike,
        'spx_strike': spx_strike,
        'spy_mid': spy_mid,
        'spx_mid': spx_mid,
        'spy_bid': spy_bid,
        'spy_ask': spy_ask,
        'spx_bid': spx_bid,
        'spx_ask': spx_ask,
        'net_credit': net_credit
    }


def find_exit_opportunity_realistic(entry, options_df, underlying_df):
    """
    Find profitable exit with bid-ask spreads
    """
    exit_times = underlying_df[underlying_df['time'] > entry['time']]['time'].unique()

    best_exit = None
    best_profit = 0

    for exit_time in exit_times:
        spy_data = underlying_df[(underlying_df['symbol'] == 'SPY') & (underlying_df['time'] == exit_time)]
        spx_data = underlying_df[(underlying_df['symbol'] == 'SPX') & (underlying_df['time'] == exit_time)]

        if spy_data.empty or spx_data.empty:
            continue

        spy_price = spy_data.iloc[0]['close']
        spx_price = spx_data.iloc[0]['close']

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

        spy_mid = (spy_call.iloc[0]['open'] + spy_call.iloc[0]['close']) / 2
        spx_mid = (spx_call.iloc[0]['open'] + spx_call.iloc[0]['close']) / 2

        # Calculate bid-ask for exit
        spy_bid, spy_ask = estimate_bid_ask(spy_mid)
        spx_bid, spx_ask = estimate_bid_ask(spx_mid)

        # EXIT: Buy back SPY at ASK (pay more), Sell SPX at BID (receive less)
        cost_to_close = (spy_ask * 100 * 10) - (spx_bid * 100)

        profit = entry['net_credit'] - cost_to_close

        if profit > best_profit:
            best_profit = profit
            best_exit = {
                'time': exit_time,
                'spy_price': spy_price,
                'spx_price': spx_price,
                'spy_mid': spy_mid,
                'spx_mid': spx_mid,
                'spy_ask': spy_ask,
                'spx_bid': spx_bid,
                'cost_to_close': cost_to_close,
                'profit': profit,
                'profit_pct': (profit / abs(entry['net_credit'])) * 100 if entry['net_credit'] != 0 else 0
            }

    return best_exit


def main():
    print('=' * 80)
    print('SPY/SPX ARBITRAGE ANALYSIS - WITH REALISTIC BID-ASK SPREADS')
    print('=' * 80)
    print('\nAssumptions:')
    print('  - ATM 0DTE options have 3-5 cent spreads')
    print('  - Entry: Sell SPY at BID, Buy SPX at ASK')
    print('  - Exit: Buy SPY at ASK, Sell SPX at BID')
    print('  - This represents WORST CASE slippage')

    print('\n📊 Loading data...')
    underlying_df, options_df = load_data('20260126')

    print(f'   Underlying bars: {len(underlying_df):,}')
    print(f'   Options bars: {len(options_df):,}')

    print('\n🔍 Analyzing every minute...')

    spy_data = underlying_df[underlying_df['symbol'] == 'SPY'].copy()
    spx_data = underlying_df[underlying_df['symbol'] == 'SPX'].copy()

    merged = pd.merge(
        spy_data[['time', 'close']].rename(columns={'close': 'spy_price'}),
        spx_data[['time', 'close']].rename(columns={'close': 'spx_price'}),
        on='time'
    )

    opportunities = []

    for idx, row in merged.iterrows():
        if idx % 50 == 0:
            print(f'   Processing minute {idx + 1}/{len(merged)}...', end='\r')

        spread = calculate_arbitrage_spread_realistic(
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

    opps_df = pd.DataFrame(opportunities)
    opps_df = opps_df.sort_values('net_credit', ascending=False)

    print('\n' + '=' * 80)
    print('TOP 10 ENTRY OPPORTUNITIES (WITH BID-ASK SPREAD)')
    print('=' * 80)

    top_entries = []

    for idx, entry in opps_df.head(10).iterrows():
        print(f'\n#{len(top_entries) + 1}. Entry at {entry["time"].strftime("%H:%M:%S")}')
        print(f'   SPY: ${entry["spy_price"]:.2f} | Strike: {entry["spy_strike"]}')
        print(f'      Mid: ${entry["spy_mid"]:.2f} | Sell at BID: ${entry["spy_bid"]:.2f}')
        print(f'   SPX: ${entry["spx_price"]:.2f} | Strike: {int(entry["spx_strike"])}')
        print(f'      Mid: ${entry["spx_mid"]:.2f} | Buy at ASK: ${entry["spx_ask"]:.2f}')
        print(f'   Net Credit Received: ${entry["net_credit"]:,.2f}')

        print('   Searching for exit...', end='')
        exit_opp = find_exit_opportunity_realistic(entry, options_df, underlying_df)

        if exit_opp:
            print(f' ✅ Found!')
            print(f'   Best Exit at {exit_opp["time"].strftime("%H:%M:%S")}')
            print(f'   SPY Mid: ${exit_opp["spy_mid"]:.2f} | Buy at ASK: ${exit_opp["spy_ask"]:.2f}')
            print(f'   SPX Mid: ${exit_opp["spx_mid"]:.2f} | Sell at BID: ${exit_opp["spx_bid"]:.2f}')
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

    print('\n' + '=' * 80)
    print('COMPARISON: MID-PRICE vs REALISTIC (BID-ASK)')
    print('=' * 80)

    if top_entries:
        print('\nNote: The realistic analysis shows LOWER credits and profits due to:')
        print('  - Selling at BID instead of MID (receive less)')
        print('  - Buying at ASK instead of MID (pay more)')
        print('  - Typical cost: $10-30 per trade in slippage')

        best = top_entries[0]
        print(f'\n🏆 BEST OPPORTUNITY (with bid-ask spreads):')
        print(f'   Entry Time: {best["entry"]["time"].strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Net Credit: ${best["entry"]["net_credit"]:,.2f}')
        print(f'   Exit Time: {best["exit"]["time"].strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Profit: ${best["exit"]["profit"]:,.2f} ({best["exit"]["profit_pct"]:.1f}%)')
        print(f'   Time Held: {int(best["minutes_held"])} minutes')

        profitable_exits = sum(1 for e in top_entries if e['exit']['profit'] > 0)
        print(f'\n📈 {profitable_exits}/{len(top_entries)} top entries had profitable exits')

        if profitable_exits > 0:
            avg_profit = np.mean([e['exit']['profit'] for e in top_entries if e['exit']['profit'] > 0])
            avg_time = np.mean([e['minutes_held'] for e in top_entries if e['exit']['profit'] > 0])
            print(f'   Average Profit: ${avg_profit:,.2f}')
            print(f'   Average Time Held: {int(avg_time)} minutes')


if __name__ == '__main__':
    main()
