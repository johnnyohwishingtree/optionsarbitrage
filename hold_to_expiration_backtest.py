#!/usr/bin/env python3
"""
CORRECT Backtest: Hold-to-Expiration Arbitrage Strategy

The Truth:
- This is NOT a day-trading strategy
- This IS a hold-to-expiration arbitrage
- Strikes MUST be matched based on OPENING PRICES (not current price × 10)
- SPY and SPX move at similar percentages, but not perfectly
- Settlement P&L = Entry Credit - Expiration Settlement Cost

Strategy:
1. At market open, determine strikes from opening prices
   - SPY opens at $690.47 → use $690 strike
   - SPX opens at $6923.23 → use $6925 strike (nearest $5)
2. Enter in morning window (9:45-10:30) with best credit
3. HOLD until 4 PM (don't touch it!)
4. Let options expire and settle
5. P&L = Entry Credit - Settlement Cost
"""

import pandas as pd
import numpy as np
from datetime import datetime, time

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


def find_atm_strike(price, symbol):
    """Find ATM strike"""
    if symbol == 'SPY':
        return round(price)
    else:
        return round(price / 5) * 5


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


def calculate_expiration_value(spy_close, spx_close, spy_strike, spx_strike, num_spreads):
    """
    Calculate P&L at expiration (4 PM)

    At expiration, options settle to intrinsic value:
    - SPY call value: max(0, SPY_close - SPY_strike) per share
    - SPX call value: max(0, SPX_close - SPX_strike) per point

    We are:
    - SHORT 10*num_spreads SPY calls (we owe this)
    - LONG num_spreads SPX calls (we receive this)
    """
    spy_contracts = 10 * num_spreads
    spx_contracts = num_spreads

    # Calculate intrinsic values
    spy_intrinsic = max(0, spy_close - spy_strike)
    spx_intrinsic = max(0, spx_close - spx_strike)

    # Our obligations/receipts
    spy_obligation = spy_intrinsic * 100 * spy_contracts  # We owe this (short calls)
    spx_receipt = spx_intrinsic * 100 * spx_contracts     # We receive this (long calls)

    # Exit commission (to close positions at expiration)
    exit_commission = COMMISSION_PER_CONTRACT * (spy_contracts + spx_contracts)

    # Net settlement
    net_settlement = spx_receipt - spy_obligation - exit_commission

    return {
        'spy_intrinsic': spy_intrinsic,
        'spx_intrinsic': spx_intrinsic,
        'spy_obligation': spy_obligation,
        'spx_receipt': spx_receipt,
        'exit_commission': exit_commission,
        'net_settlement': net_settlement
    }


def run_hold_to_expiration_backtest(starting_capital=10000, entry_window_start='09:45', entry_window_end='10:30'):
    """
    Run CORRECT backtest: Hold to expiration
    """
    print('=' * 80)
    print(f'HOLD-TO-EXPIRATION BACKTEST - Capital: ${starting_capital:,.0f}')
    print('=' * 80)

    print('\nStrategy (CORRECT):')
    print(f'  1. Entry window: {entry_window_start} - {entry_window_end}')
    print(f'  2. Enter with BEST credit available')
    print(f'  3. HOLD until 4:00 PM (NO EXITS!)')
    print(f'  4. Let options expire and settle')
    print(f'  5. Profit = Credit - Settlement - Fees')
    print()

    # Load data
    print('📊 Loading data...')
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    options = pd.read_csv('data/options_data_20260126.csv')

    # CRITICAL: Normalize timezones (SPX has different TZ than SPY in data)
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    options['time'] = pd.to_datetime(options['time'], utc=True)

    spy_data = underlying[underlying['symbol'] == 'SPY'].copy()
    spx_data = underlying[underlying['symbol'] == 'SPX'].copy()

    # Find opening prices (first bar of the day) - CRITICAL for strike selection
    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    print(f'   Opening prices at 9:30 AM:')
    print(f'     SPY: ${spy_open:.2f}')
    print(f'     SPX: ${spx_open:.2f}')

    # Determine strikes based on opening prices (per user's guidance)
    spy_strike = round(spy_open)  # SPY strikes are $1 increments
    spx_strike = round(spx_open / 5) * 5  # SPX strikes are $5 increments

    print(f'\n   Selected strikes (based on opening):')
    print(f'     SPY: ${spy_strike}')
    print(f'     SPX: ${spx_strike}')

    merged = pd.merge(
        spy_data[['time', 'close']].rename(columns={'close': 'spy_price'}),
        spx_data[['time', 'close']].rename(columns={'close': 'spx_price'}),
        on='time'
    )

    # Find 4 PM closing prices
    spy_close = spy_data.iloc[-1]['close']
    spx_close = spx_data.iloc[-1]['close']
    closing_time = spy_data.iloc[-1]['time']

    print(f'\n   Closing prices at {closing_time.strftime("%H:%M:%S")}:')
    print(f'     SPY: ${spy_close:.2f}')
    print(f'     SPX: ${spx_close:.2f}')

    # Find best entry in window
    print(f'\n🔍 Scanning {entry_window_start}-{entry_window_end} for best entry...')

    entry_start = datetime.strptime(f'2026-01-26 {entry_window_start}:00-05:00', '%Y-%m-%d %H:%M:%S%z')
    entry_end = datetime.strptime(f'2026-01-26 {entry_window_end}:00-05:00', '%Y-%m-%d %H:%M:%S%z')

    window_data = merged[(merged['time'] >= entry_start) & (merged['time'] <= entry_end)]

    best_entry = None
    best_credit = 0

    for idx, row in window_data.iterrows():
        current_time = row['time']
        spy_price = row['spy_price']
        spx_price = row['spx_price']

        # Use strikes determined from opening prices (not current price!)
        spy_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
        spx_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)

        if spy_mid is None or spx_mid is None:
            continue

        # Calculate credit for max position (10 spreads = 100 SPY contracts, 10 SPX contracts)
        num_spreads = min(10, int(starting_capital / 1000))

        spy_bid, spy_ask = estimate_bid_ask(spy_mid)
        spx_bid, spx_ask = estimate_bid_ask(spx_mid)

        spy_contracts = 10 * num_spreads
        spx_contracts = num_spreads

        premium_received = spy_bid * 100 * spy_contracts
        premium_paid = spx_ask * 100 * spx_contracts
        entry_commission = COMMISSION_PER_CONTRACT * (spy_contracts + spx_contracts)

        net_credit = premium_received - premium_paid - entry_commission

        if net_credit > best_credit:
            best_credit = net_credit
            best_entry = {
                'time': current_time,
                'spy_price': spy_price,
                'spx_price': spx_price,
                'spy_strike': spy_strike,
                'spx_strike': spx_strike,
                'spy_mid': spy_mid,
                'spx_mid': spx_mid,
                'spy_bid': spy_bid,
                'spx_ask': spx_ask,
                'num_spreads': num_spreads,
                'spy_contracts': spy_contracts,
                'spx_contracts': spx_contracts,
                'net_credit': net_credit,
                'entry_commission': entry_commission
            }

    if best_entry is None:
        print('❌ No valid entries found in window')
        return None

    # Display entry
    print('\n' + '=' * 80)
    print('ENTRY (Best Credit in Window)')
    print('=' * 80)
    print(f'\n✅ ENTERED at {best_entry["time"].strftime("%H:%M:%S")}')
    print(f'\n   SPY: ${best_entry["spy_price"]:.2f}')
    print(f'     Sell {best_entry["spy_contracts"]} × ${best_entry["spy_strike"]} calls @ ${best_entry["spy_bid"]:.2f} bid')
    print(f'     Premium Received: ${best_entry["spy_bid"] * 100 * best_entry["spy_contracts"]:,.2f}')
    print(f'\n   SPX: ${best_entry["spx_price"]:.2f}')
    print(f'     Buy {best_entry["spx_contracts"]} × ${best_entry["spx_strike"]} calls @ ${best_entry["spx_ask"]:.2f} ask')
    print(f'     Premium Paid: ${best_entry["spx_ask"] * 100 * best_entry["spx_contracts"]:,.2f}')
    print(f'\n   Entry Commission: ${best_entry["entry_commission"]:.2f}')
    print(f'   NET CREDIT: ${best_entry["net_credit"]:,.2f}')
    print(f'\n   Position: {best_entry["num_spreads"]} spreads')
    print(f'   Credit per spread: ${best_entry["net_credit"] / best_entry["num_spreads"]:.2f}')

    # Hold until expiration (do nothing!)
    print('\n⏳ HOLDING until 4:00 PM expiration...')
    print('   (No exits, no stops, no panic - just hold)')

    # Calculate expiration settlement
    print('\n' + '=' * 80)
    print('EXPIRATION SETTLEMENT (4:00 PM)')
    print('=' * 80)

    settlement = calculate_expiration_value(
        spy_close, spx_close,
        best_entry['spy_strike'], best_entry['spx_strike'],
        best_entry['num_spreads']
    )

    print(f'\n📊 Closing Prices:')
    print(f'   SPY: ${spy_close:.2f} (strike was ${best_entry["spy_strike"]})')
    print(f'   SPX: ${spx_close:.2f} (strike was ${best_entry["spx_strike"]})')

    print(f'\n💰 Intrinsic Values:')
    print(f'   SPY Call: ${settlement["spy_intrinsic"]:.2f} per share')
    print(f'   SPX Call: ${settlement["spx_intrinsic"]:.2f} per point')

    print(f'\n📤 Settlement:')
    print(f'   SPY Obligation (short {best_entry["spy_contracts"]} calls): -${settlement["spy_obligation"]:,.2f}')
    print(f'   SPX Receipt (long {best_entry["spx_contracts"]} calls): +${settlement["spx_receipt"]:,.2f}')
    print(f'   Exit Commission: -${settlement["exit_commission"]:.2f}')
    print(f'   Net Settlement: ${settlement["net_settlement"]:,.2f}')

    # Calculate final P&L
    total_pnl = best_entry['net_credit'] + settlement['net_settlement']
    pnl_pct = (total_pnl / best_entry['net_credit']) * 100 if best_entry['net_credit'] > 0 else 0

    final_capital = starting_capital + total_pnl

    print('\n' + '=' * 80)
    print('FINAL RESULTS')
    print('=' * 80)

    print(f'\n💵 P&L Breakdown:')
    print(f'   Credit Received: +${best_entry["net_credit"]:,.2f}')
    print(f'   Settlement Cost: ${settlement["net_settlement"]:,.2f}')
    print(f'   Total Commissions: ${best_entry["entry_commission"] + settlement["exit_commission"]:.2f}')
    print(f'\n   {"="*40}')
    print(f'   NET PROFIT: ${total_pnl:,.2f} ({pnl_pct:+.2f}%)')

    print(f'\n📊 Account:')
    print(f'   Starting Capital: ${starting_capital:,.2f}')
    print(f'   Ending Capital: ${final_capital:,.2f}')
    print(f'   Return: {((final_capital - starting_capital) / starting_capital) * 100:+.2f}%')

    # Scaling analysis
    print('\n' + '=' * 80)
    print('SCALING TO $1,000/DAY GOAL')
    print('=' * 80)

    if total_pnl > 0:
        scale_factor = 1000 / total_pnl
        required_capital = starting_capital * scale_factor
        required_spreads = best_entry['num_spreads'] * scale_factor

        print(f'\n✅ This strategy is PROFITABLE!')
        print(f'\n   Today\'s Results:')
        print(f'     Profit: ${total_pnl:.2f}')
        print(f'     Capital: ${starting_capital:,.0f}')
        print(f'     Spreads: {best_entry["num_spreads"]}')

        print(f'\n   To Make $1,000/day:')
        print(f'     Scale by: {scale_factor:.2f}x')
        print(f'     Required Capital: ${required_capital:,.0f}')
        print(f'     Required Spreads: {required_spreads:.0f}')

        if required_capital <= 50000:
            print(f'\n   ✅ Very achievable with moderate capital!')
        elif required_capital <= 100000:
            print(f'\n   ⚠️  Requires significant capital but realistic')
        else:
            print(f'\n   ⚠️  Requires substantial capital')
    else:
        print(f'\n❌ Strategy lost ${abs(total_pnl):.2f}')
        print('   This means SPY/SPX tracking was imperfect today')
        print('   OR commission fees exceeded the arbitrage profit')

    # Save results
    results = {
        'date': '2026-01-26',
        'entry_time': best_entry['time'],
        'spy_entry': best_entry['spy_price'],
        'spx_entry': best_entry['spx_price'],
        'spy_close': spy_close,
        'spx_close': spx_close,
        'spy_strike': best_entry['spy_strike'],
        'spx_strike': best_entry['spx_strike'],
        'num_spreads': best_entry['num_spreads'],
        'credit_received': best_entry['net_credit'],
        'settlement_cost': settlement['net_settlement'],
        'total_pnl': total_pnl,
        'return_pct': pnl_pct
    }

    pd.DataFrame([results]).to_csv('data/hold_to_expiration_results.csv', index=False)
    print(f'\n✅ Saved results to data/hold_to_expiration_results.csv')

    return results


if __name__ == '__main__':
    print('Running CORRECT backtest: Hold-to-Expiration Arbitrage\n')
    run_hold_to_expiration_backtest(starting_capital=10000)
