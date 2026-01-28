#!/usr/bin/env python3
"""
Test: Compare Call-Only vs Put-Only vs Both Sides

This test runs the backtest three ways:
1. CALLS ONLY - Just the call spread
2. PUTS ONLY - Just the put spread
3. BOTH SIDES - Both calls and puts (current strategy)

Shows different entries chosen and P&L for each approach.
"""

import pandas as pd
import numpy as np
from datetime import datetime

COMMISSION_PER_CONTRACT = 0.50

def estimate_bid_ask(mid_price):
    """Estimate bid-ask spread"""
    if mid_price < 0.50:
        spread = 0.05
    elif mid_price < 2.00:
        spread = 0.03
    else:
        spread = 0.05
    bid = mid_price - spread / 2
    ask = mid_price + spread / 2
    return bid, ask


def get_option_price(options_df, symbol, strike, right, timestamp):
    """Get option price at specific time"""
    opt = options_df[
        (options_df['symbol'] == symbol) &
        (options_df['strike'] == strike) &
        (options_df['right'] == right) &
        (options_df['time'] == timestamp)
    ]
    if opt.empty:
        return None
    mid = (opt.iloc[0]['open'] + opt.iloc[0]['close']) / 2
    return mid


def calculate_settlement(spy_close, spx_close, spy_strike, spx_strike, num_spreads,
                        call_direction=None, put_direction=None, side='both'):
    """Calculate settlement for specific side(s)"""
    spy_contracts = 10 * num_spreads
    spx_contracts = num_spreads

    # Intrinsic values
    spy_call_intrinsic = max(0, spy_close - spy_strike)
    spx_call_intrinsic = max(0, spx_close - spx_strike)
    spy_put_intrinsic = max(0, spy_strike - spy_close)
    spx_put_intrinsic = max(0, spx_strike - spx_close)

    result = {
        'spy_call_intrinsic': spy_call_intrinsic,
        'spx_call_intrinsic': spx_call_intrinsic,
        'spy_put_intrinsic': spy_put_intrinsic,
        'spx_put_intrinsic': spx_put_intrinsic,
    }

    # Calculate call settlement if needed
    if side in ['both', 'calls']:
        if call_direction == 'Sell SPY, Buy SPX':
            call_net = (spx_call_intrinsic * 100 * spx_contracts) - (spy_call_intrinsic * 100 * spy_contracts)
        else:  # 'Sell SPX, Buy SPY'
            call_net = (spy_call_intrinsic * 100 * spy_contracts) - (spx_call_intrinsic * 100 * spx_contracts)
        result['call_net_settlement'] = call_net
    else:
        result['call_net_settlement'] = 0

    # Calculate put settlement if needed
    if side in ['both', 'puts']:
        if put_direction == 'Sell SPY, Buy SPX':
            put_net = (spx_put_intrinsic * 100 * spx_contracts) - (spy_put_intrinsic * 100 * spy_contracts)
        else:  # 'Sell SPX, Buy SPY'
            put_net = (spy_put_intrinsic * 100 * spy_contracts) - (spx_put_intrinsic * 100 * spx_contracts)
        result['put_net_settlement'] = put_net
    else:
        result['put_net_settlement'] = 0

    # Exit commission
    contracts_count = 0
    if side in ['both', 'calls']:
        contracts_count += (spy_contracts + spx_contracts)
    if side in ['both', 'puts']:
        contracts_count += (spy_contracts + spx_contracts)

    result['exit_commission'] = COMMISSION_PER_CONTRACT * contracts_count
    result['total_net_settlement'] = result['call_net_settlement'] + result['put_net_settlement'] - result['exit_commission']

    return result


def run_backtest_for_side(side='both', starting_capital=10000):
    """
    Run backtest for specific side(s)

    side: 'calls', 'puts', or 'both'
    """
    print('=' * 100)
    print(f'BACKTEST: {side.upper()} {"ONLY" if side != "both" else ""}')
    print('=' * 100)

    # Load data
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    options = pd.read_csv('data/options_data_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    options['time'] = pd.to_datetime(options['time'], utc=True)

    spy_data = underlying[underlying['symbol'] == 'SPY'].copy()
    spx_data = underlying[underlying['symbol'] == 'SPX'].copy()

    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']
    spy_close = spy_data.iloc[-1]['close']
    spx_close = spx_data.iloc[-1]['close']

    # Strikes will be calculated DYNAMICALLY at each timestamp (not based on opening)

    merged = pd.merge(
        spy_data[['time', 'close']].rename(columns={'close': 'spy_price'}),
        spx_data[['time', 'close']].rename(columns={'close': 'spx_price'}),
        on='time'
    )

    # Entry window
    entry_start = datetime.strptime('2026-01-26 09:45:00-05:00', '%Y-%m-%d %H:%M:%S%z')
    entry_end = datetime.strptime('2026-01-26 10:30:00-05:00', '%Y-%m-%d %H:%M:%S%z')
    window_data = merged[(merged['time'] >= entry_start) & (merged['time'] <= entry_end)]

    best_entry = None
    best_expected_pnl = -float('inf')

    # Track all valid entries for analysis
    all_valid_entries = []

    for idx, row in window_data.iterrows():
        current_time = row['time']
        spy_price = row['spy_price']
        spx_price = row['spx_price']

        # DYNAMIC: Calculate strikes that bracket CURRENT price at this timestamp
        spy_strike_below = int(spy_price)
        spy_strike_above = spy_strike_below + 1
        spx_strike_below = int(spx_price / 5) * 5
        spx_strike_above = spx_strike_below + 5

        spy_strikes = [spy_strike_below, spy_strike_above]
        spx_strikes = [spx_strike_below, spx_strike_above]

        for spy_strike in spy_strikes:
            for spx_strike in spx_strikes:
                # Get option prices
                spy_call_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
                spx_call_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)
                spy_put_mid = get_option_price(options, 'SPY', spy_strike, 'P', current_time)
                spx_put_mid = get_option_price(options, 'SPX', spx_strike, 'P', current_time)

                # Check what data we need
                if side in ['both', 'calls'] and (spy_call_mid is None or spx_call_mid is None):
                    continue
                if side in ['both', 'puts'] and (spy_put_mid is None or spx_put_mid is None):
                    continue

                num_spreads = min(10, int(starting_capital / 1000))
                spy_contracts = 10 * num_spreads
                spx_contracts = num_spreads

                # Get bid/ask
                if spy_call_mid:
                    spy_call_bid, spy_call_ask = estimate_bid_ask(spy_call_mid)
                    spx_call_bid, spx_call_ask = estimate_bid_ask(spx_call_mid)
                if spy_put_mid:
                    spy_put_bid, spy_put_ask = estimate_bid_ask(spy_put_mid)
                    spx_put_bid, spx_put_ask = estimate_bid_ask(spx_put_mid)

                # Calculate call side if needed
                call_credit = 0
                call_direction = None
                if side in ['both', 'calls']:
                    call_credit_A = (spy_call_bid * 100 * spy_contracts) - (spx_call_ask * 100 * spx_contracts)
                    call_credit_B = (spx_call_bid * 100 * spx_contracts) - (spy_call_ask * 100 * spy_contracts)

                    if call_credit_A > call_credit_B:
                        call_credit = call_credit_A
                        call_direction = 'Sell SPY, Buy SPX'
                    else:
                        call_credit = call_credit_B
                        call_direction = 'Sell SPX, Buy SPY'

                    if call_credit <= 0:
                        continue

                # Calculate put side if needed
                put_credit = 0
                put_direction = None
                if side in ['both', 'puts']:
                    put_credit_A = (spy_put_bid * 100 * spy_contracts) - (spx_put_ask * 100 * spx_contracts)
                    put_credit_B = (spx_put_bid * 100 * spx_contracts) - (spy_put_ask * 100 * spy_contracts)

                    if put_credit_A > put_credit_B:
                        put_credit = put_credit_A
                        put_direction = 'Sell SPY, Buy SPX'
                    else:
                        put_credit = put_credit_B
                        put_direction = 'Sell SPX, Buy SPY'

                    if put_credit <= 0:
                        continue

                # Calculate net credit
                contracts_count = 0
                if side in ['both', 'calls']:
                    contracts_count += (spy_contracts + spx_contracts)
                if side in ['both', 'puts']:
                    contracts_count += (spy_contracts + spx_contracts)

                entry_commission = COMMISSION_PER_CONTRACT * contracts_count
                exit_commission = entry_commission
                net_credit = call_credit + put_credit - entry_commission

                # Calculate expected settlement
                spy_call_intrinsic_now = max(0, spy_price - spy_strike)
                spx_call_intrinsic_now = max(0, spx_price - spx_strike)
                spy_put_intrinsic_now = max(0, spy_strike - spy_price)
                spx_put_intrinsic_now = max(0, spx_strike - spx_price)

                expected_call_settlement = 0
                if side in ['both', 'calls']:
                    if call_direction == 'Sell SPY, Buy SPX':
                        expected_call_settlement = (spx_call_intrinsic_now * 100 * spx_contracts) - (spy_call_intrinsic_now * 100 * spy_contracts)
                    else:
                        expected_call_settlement = (spy_call_intrinsic_now * 100 * spy_contracts) - (spx_call_intrinsic_now * 100 * spx_contracts)

                expected_put_settlement = 0
                if side in ['both', 'puts']:
                    if put_direction == 'Sell SPY, Buy SPX':
                        expected_put_settlement = (spx_put_intrinsic_now * 100 * spx_contracts) - (spy_put_intrinsic_now * 100 * spy_contracts)
                    else:
                        expected_put_settlement = (spy_put_intrinsic_now * 100 * spy_contracts) - (spx_put_intrinsic_now * 100 * spx_contracts)

                expected_settlement = expected_call_settlement + expected_put_settlement - exit_commission
                expected_pnl = net_credit + expected_settlement

                # Track this as a valid entry
                entry_info = {
                    'time': current_time,
                    'spy_price': spy_price,
                    'spx_price': spx_price,
                    'spy_strike': spy_strike,
                    'spx_strike': spx_strike,
                    'call_credit': call_credit,
                    'put_credit': put_credit,
                    'call_direction': call_direction,
                    'put_direction': put_direction,
                    'num_spreads': num_spreads,
                    'net_credit': net_credit,
                    'expected_pnl': expected_pnl,
                    'entry_commission': entry_commission,
                }
                all_valid_entries.append(entry_info)

                if expected_pnl > best_expected_pnl:
                    best_expected_pnl = expected_pnl
                    best_entry = entry_info

    if best_entry is None:
        print('\n❌ No valid entries found')
        return None

    # Display entry
    print(f'\n✅ ENTRY at {best_entry["time"].strftime("%H:%M:%S")}')
    print(f'   Strikes: SPY {best_entry["spy_strike"]} / SPX {best_entry["spx_strike"]}')
    print(f'   Underlying: SPY ${best_entry["spy_price"]:.2f}, SPX ${best_entry["spx_price"]:.2f}')

    if side in ['both', 'calls']:
        print(f'\n   📞 CALLS: {best_entry["call_direction"]}')
        print(f'      Credit: ${best_entry["call_credit"]:,.2f}')

    if side in ['both', 'puts']:
        print(f'\n   📉 PUTS: {best_entry["put_direction"]}')
        print(f'      Credit: ${best_entry["put_credit"]:,.2f}')

    print(f'\n   Net Credit: ${best_entry["net_credit"]:,.2f}')
    print(f'   Expected P&L: ${best_entry["expected_pnl"]:,.2f}')

    # Show all valid strike combinations at this timestamp
    entries_at_best_time = [e for e in all_valid_entries if e['time'] == best_entry['time']]
    if len(entries_at_best_time) > 1:
        print(f'\n📋 ALL VALID STRIKE COMBINATIONS AT {best_entry["time"].strftime("%H:%M:%S")}:')
        print(f'   (Showing why SPY {best_entry["spy_strike"]}/SPX {best_entry["spx_strike"]} was chosen)')
        print(f'\n   {"SPY Strike":<12} {"SPX Strike":<12} {"Direction":<20} {"Credit":<12} {"Expected P&L":<15}')
        print('   ' + '-'*75)

        for e in sorted(entries_at_best_time, key=lambda x: x['expected_pnl'], reverse=True):
            direction = e['call_direction'] if side in ['calls', 'both'] else e['put_direction']
            credit = e['call_credit'] if side == 'calls' else (e['put_credit'] if side == 'puts' else e['net_credit'])

            marker = ' ← CHOSEN' if e['spy_strike'] == best_entry['spy_strike'] and e['spx_strike'] == best_entry['spx_strike'] else ''

            print(f'   {e["spy_strike"]:<12} {e["spx_strike"]:<12} {direction:<20} ${credit:<11,.0f} ${e["expected_pnl"]:<14,.0f}{marker}')

    # Calculate actual settlement
    settlement = calculate_settlement(
        spy_close, spx_close,
        best_entry['spy_strike'], best_entry['spx_strike'],
        best_entry['num_spreads'],
        best_entry['call_direction'],
        best_entry['put_direction'],
        side
    )

    actual_pnl = best_entry['net_credit'] + settlement['total_net_settlement']

    print(f'\n📊 SETTLEMENT at 4:00 PM')
    print(f'   SPY close: ${spy_close:.2f}, SPX close: ${spx_close:.2f}')

    if side in ['both', 'calls']:
        print(f'\n   Calls settlement: ${settlement["call_net_settlement"]:,.2f}')
        print(f'      SPY call intrinsic: ${settlement["spy_call_intrinsic"]:.2f}')
        print(f'      SPX call intrinsic: ${settlement["spx_call_intrinsic"]:.2f}')

    if side in ['both', 'puts']:
        print(f'\n   Puts settlement: ${settlement["put_net_settlement"]:,.2f}')
        print(f'      SPY put intrinsic: ${settlement["spy_put_intrinsic"]:.2f}')
        print(f'      SPX put intrinsic: ${settlement["spx_put_intrinsic"]:.2f}')

    print(f'\n   Exit commission: ${settlement["exit_commission"]:.2f}')
    print(f'   Total settlement: ${settlement["total_net_settlement"]:,.2f}')

    print(f'\n💰 FINAL P&L: ${actual_pnl:,.2f}')
    print(f'   Return: {(actual_pnl/starting_capital)*100:.2f}%')

    return {
        'side': side,
        'entry_time': best_entry['time'],
        'spy_strike': best_entry['spy_strike'],
        'spx_strike': best_entry['spx_strike'],
        'call_direction': best_entry['call_direction'],
        'put_direction': best_entry['put_direction'],
        'net_credit': best_entry['net_credit'],
        'settlement': settlement['total_net_settlement'],
        'pnl': actual_pnl,
        'return_pct': (actual_pnl/starting_capital)*100
    }


def main():
    print('\n🧪 TESTING: CALLS ONLY vs PUTS ONLY vs BOTH SIDES\n')

    results = []

    # Test each approach
    for side in ['calls', 'puts', 'both']:
        result = run_backtest_for_side(side)
        if result:
            results.append(result)
        print('\n')

    # Comparison
    print('=' * 100)
    print('COMPARISON')
    print('=' * 100)

    print(f'\n{"Strategy":<15} {"Entry Time":<12} {"Strikes":<15} {"Credit":<12} {"Settlement":<12} {"P&L":<12} {"Return":<10}')
    print('-' * 100)

    for r in results:
        strikes = f"{r['spy_strike']}/{r['spx_strike']}"
        print(f'{r["side"].upper():<15} {r["entry_time"].strftime("%H:%M:%S"):<12} {strikes:<15} '
              f'${r["net_credit"]:<11,.0f} ${r["settlement"]:<11,.0f} ${r["pnl"]:<11,.0f} {r["return_pct"]:<9.2f}%')

    # Analysis
    print('\n' + '=' * 100)
    print('ANALYSIS')
    print('=' * 100)

    calls_result = next((r for r in results if r['side'] == 'calls'), None)
    puts_result = next((r for r in results if r['side'] == 'puts'), None)
    both_result = next((r for r in results if r['side'] == 'both'), None)

    if calls_result and puts_result and both_result:
        print(f'\n1. Entry Timing:')
        print(f'   Calls-only entered at: {calls_result["entry_time"].strftime("%H:%M:%S")}')
        print(f'   Puts-only entered at: {puts_result["entry_time"].strftime("%H:%M:%S")}')
        print(f'   Both sides entered at: {both_result["entry_time"].strftime("%H:%M:%S")}')

        if calls_result['entry_time'] != both_result['entry_time']:
            print(f'   ⚠️  Different entry times! Both-sides waits for BOTH to have credit')

        print(f'\n2. Strike Selection:')
        print(f'   Calls-only: SPY {calls_result["spy_strike"]}/SPX {calls_result["spx_strike"]}')
        print(f'   Puts-only: SPY {puts_result["spy_strike"]}/SPX {puts_result["spx_strike"]}')
        print(f'   Both sides: SPY {both_result["spy_strike"]}/SPX {both_result["spx_strike"]}')

        print(f'\n3. P&L Contribution:')
        print(f'   Calls-only P&L: ${calls_result["pnl"]:,.2f}')
        print(f'   Puts-only P&L:  ${puts_result["pnl"]:,.2f}')
        print(f'   Both sides P&L:  ${both_result["pnl"]:,.2f}')

        # Check if both sides P&L equals sum of individual sides (it shouldn't due to different entries)
        expected_sum = calls_result['pnl'] + puts_result['pnl']
        diff = both_result['pnl'] - expected_sum
        print(f'\n   Sum of individuals: ${expected_sum:,.2f}')
        print(f'   Actual (both):      ${both_result["pnl"]:,.2f}')
        print(f'   Difference:         ${diff:,.2f}')

        if abs(diff) > 100:
            print(f'\n   ⚠️  Significant difference! This is because:')
            print(f'      - Different entry times (different strikes/prices)')
            print(f'      - Both-sides strategy requires BOTH to give credit')
            print(f'      - This creates different entry opportunities')

    print('\n' + '=' * 100)


if __name__ == '__main__':
    main()
