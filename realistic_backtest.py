#!/usr/bin/env python3
"""
Realistic Backtest for SPY/SPX 0DTE Arbitrage Strategy

Rules:
1. Start with $10,000 capital
2. Entry window: 9:45 AM - 10:30 AM
3. Enter when net credit (after fees) > $25 per spread
4. Position size: Use maximum contracts that fit in capital
5. Exit when: Profit > 50% of max OR time is 3:30 PM
6. Track all fees and slippage

Commission: $0.50 per contract (IB standard for options)
"""

import pandas as pd
import numpy as np
from datetime import datetime, time

# IB Commission
COMMISSION_PER_CONTRACT = 0.50

def estimate_bid_ask(mid_price):
    """
    Estimate bid-ask spread for 0DTE ATM options
    SPY/SPX ATM options typically have 2-5 cent spreads
    """
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


def calculate_entry_cost(spy_mid, spx_mid, num_spreads):
    """
    Calculate realistic entry cost with bid/ask and fees

    Entry: Sell 10*num_spreads SPY calls, Buy num_spreads SPX calls
    """
    spy_bid, spy_ask = estimate_bid_ask(spy_mid)
    spx_bid, spx_ask = estimate_bid_ask(spx_mid)

    # Sell SPY at BID, Buy SPX at ASK
    spy_contracts = 10 * num_spreads
    spx_contracts = num_spreads

    premium_received = spy_bid * 100 * spy_contracts
    premium_paid = spx_ask * 100 * spx_contracts

    # Commissions for entry
    commission = COMMISSION_PER_CONTRACT * (spy_contracts + spx_contracts)

    net_credit = premium_received - premium_paid - commission

    return {
        'spy_bid': spy_bid,
        'spy_ask': spy_ask,
        'spx_bid': spx_bid,
        'spx_ask': spx_ask,
        'spy_contracts': spy_contracts,
        'spx_contracts': spx_contracts,
        'premium_received': premium_received,
        'premium_paid': premium_paid,
        'commission': commission,
        'net_credit': net_credit
    }


def calculate_exit_cost(spy_mid, spx_mid, spy_contracts, spx_contracts):
    """
    Calculate realistic exit cost

    Exit: Buy back SPY calls at ASK, Sell SPX calls at BID
    """
    spy_bid, spy_ask = estimate_bid_ask(spy_mid)
    spx_bid, spx_ask = estimate_bid_ask(spx_mid)

    # Buy SPY at ASK, Sell SPX at BID
    cost_spy = spy_ask * 100 * spy_contracts
    received_spx = spx_bid * 100 * spx_contracts

    # Commissions for exit
    commission = COMMISSION_PER_CONTRACT * (spy_contracts + spx_contracts)

    net_cost = cost_spy - received_spx + commission

    return {
        'spy_ask': spy_ask,
        'spx_bid': spx_bid,
        'cost_spy': cost_spy,
        'received_spx': received_spx,
        'commission': commission,
        'net_cost': net_cost
    }


def run_backtest(starting_capital=10000, min_credit_per_spread=25):
    """
    Run realistic backtest with mechanical rules
    """
    print('=' * 80)
    print(f'REALISTIC 0DTE BACKTEST - Starting Capital: ${starting_capital:,.0f}')
    print('=' * 80)

    print('\nStrategy Rules:')
    print(f'  1. Entry window: 9:45 AM - 10:30 AM')
    print(f'  2. Minimum net credit: ${min_credit_per_spread} per spread (after fees)')
    print(f'  3. Position size: Max contracts that fit in capital')
    print(f'  4. Exit when: 50% profit target hit OR 3:30 PM stop')
    print(f'  5. Commission: ${COMMISSION_PER_CONTRACT} per contract')
    print()

    # Load data
    print('📊 Loading data...')
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    options = pd.read_csv('data/options_data_20260126.csv')

    underlying['time'] = pd.to_datetime(underlying['time'])
    options['time'] = pd.to_datetime(options['time'])

    # Get all timestamps
    spy_data = underlying[underlying['symbol'] == 'SPY'].copy()
    spx_data = underlying[underlying['symbol'] == 'SPX'].copy()

    merged = pd.merge(
        spy_data[['time', 'close']].rename(columns={'close': 'spy_price'}),
        spx_data[['time', 'close']].rename(columns={'close': 'spx_price'}),
        on='time'
    )

    print(f'   Total minutes in day: {len(merged)}')

    # Trading state
    capital = starting_capital
    position = None
    trades = []

    print('\n' + '=' * 80)
    print('TRADING SIMULATION')
    print('=' * 80)

    for idx, row in merged.iterrows():
        current_time = row['time']
        time_only = current_time.time()

        # Entry logic
        if position is None:
            # Only enter during entry window
            if time(9, 45) <= time_only <= time(10, 30):
                spy_price = row['spy_price']
                spx_price = row['spx_price']

                # Find ATM strikes
                spy_strike = find_atm_strike(spy_price, 'SPY')
                spx_strike = find_atm_strike(spx_price / 10, 'SPX') * 10

                # Get option prices
                spy_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
                spx_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)

                if spy_mid is None or spx_mid is None:
                    continue

                # Calculate how many spreads we can do
                # Each spread needs margin (roughly $1000 per spread for ATM 0DTE)
                # With $10k, we can do ~10 spreads max
                max_spreads = min(10, int(capital / 1000))

                if max_spreads == 0:
                    continue

                # Calculate entry
                entry_calc = calculate_entry_cost(spy_mid, spx_mid, max_spreads)

                credit_per_spread = entry_calc['net_credit'] / max_spreads

                # Check if credit meets minimum
                if credit_per_spread >= min_credit_per_spread:
                    position = {
                        'entry_time': current_time,
                        'spy_strike': spy_strike,
                        'spx_strike': spx_strike,
                        'spy_contracts': entry_calc['spy_contracts'],
                        'spx_contracts': entry_calc['spx_contracts'],
                        'net_credit': entry_calc['net_credit'],
                        'entry_commission': entry_calc['commission'],
                        'num_spreads': max_spreads
                    }

                    print(f'\n✅ ENTRY at {current_time.strftime("%H:%M:%S")}')
                    print(f'   SPY ${spy_price:.2f} → Sell {entry_calc["spy_contracts"]} × {spy_strike} calls @ ${entry_calc["spy_bid"]:.2f} bid')
                    print(f'   SPX ${spx_price:.2f} → Buy {entry_calc["spx_contracts"]} × {spx_strike} calls @ ${entry_calc["spx_ask"]:.2f} ask')
                    print(f'   Net Credit: ${entry_calc["net_credit"]:.2f} (${credit_per_spread:.2f}/spread)')
                    print(f'   Entry Commission: ${entry_calc["commission"]:.2f}')
                    print(f'   Capital Used: ${max_spreads * 1000:,.0f}')

        # Exit logic
        elif position is not None:
            spy_strike = position['spy_strike']
            spx_strike = position['spx_strike']

            # Get current option prices
            spy_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
            spx_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)

            if spy_mid is None or spx_mid is None:
                continue

            # Calculate exit cost
            exit_calc = calculate_exit_cost(
                spy_mid, spx_mid,
                position['spy_contracts'],
                position['spx_contracts']
            )

            # Calculate P&L
            gross_profit = position['net_credit'] - exit_calc['net_cost']
            net_profit = gross_profit  # Already included commissions in entry and exit

            profit_pct = (net_profit / position['net_credit']) * 100 if position['net_credit'] > 0 else 0

            # Exit conditions
            should_exit = False
            exit_reason = ''

            # 1. Profit target: 50% of credit
            if net_profit >= position['net_credit'] * 0.5:
                should_exit = True
                exit_reason = '50% Profit Target'

            # 2. Time stop: 3:30 PM
            elif time_only >= time(15, 30):
                should_exit = True
                exit_reason = '3:30 PM Time Stop'

            if should_exit:
                capital += net_profit

                trade_record = {
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                    'num_spreads': position['num_spreads'],
                    'spy_strike': spy_strike,
                    'spx_strike': spx_strike,
                    'credit_received': position['net_credit'],
                    'exit_cost': exit_calc['net_cost'],
                    'gross_profit': gross_profit,
                    'total_commission': position['entry_commission'] + exit_calc['commission'],
                    'net_profit': net_profit,
                    'profit_pct': profit_pct,
                    'exit_reason': exit_reason,
                    'time_held_min': (current_time - position['entry_time']).total_seconds() / 60
                }

                trades.append(trade_record)

                print(f'\n❌ EXIT at {current_time.strftime("%H:%M:%S")} - {exit_reason}')
                print(f'   Buy back SPY @ ${exit_calc["spy_ask"]:.2f} ask')
                print(f'   Sell SPX @ ${exit_calc["spx_bid"]:.2f} bid')
                print(f'   Exit Cost: ${exit_calc["net_cost"]:.2f}')
                print(f'   Exit Commission: ${exit_calc["commission"]:.2f}')
                print(f'   Total Commission: ${trade_record["total_commission"]:.2f}')
                print(f'   💰 NET PROFIT: ${net_profit:.2f} ({profit_pct:.1f}%)')
                print(f'   Time Held: {trade_record["time_held_min"]:.0f} minutes')
                print(f'   Capital: ${capital:,.2f}')

                position = None

    # Summary
    print('\n' + '=' * 80)
    print('BACKTEST RESULTS')
    print('=' * 80)

    if not trades:
        print('\n❌ No trades executed')
        return

    trades_df = pd.DataFrame(trades)

    total_profit = trades_df['net_profit'].sum()
    total_commission = trades_df['total_commission'].sum()
    winning_trades = len(trades_df[trades_df['net_profit'] > 0])

    print(f'\nStarting Capital: ${starting_capital:,.2f}')
    print(f'Ending Capital: ${capital:,.2f}')
    print(f'Total P&L: ${total_profit:,.2f} ({(total_profit/starting_capital)*100:.1f}%)')
    print(f'\nTrades: {len(trades)}')
    print(f'Winners: {winning_trades}/{len(trades)} ({(winning_trades/len(trades))*100:.0f}%)')
    print(f'Total Commissions Paid: ${total_commission:.2f}')

    if winning_trades > 0:
        print(f'\nAverage Profit per Trade: ${trades_df["net_profit"].mean():.2f}')
        print(f'Best Trade: ${trades_df["net_profit"].max():.2f}')
        print(f'Worst Trade: ${trades_df["net_profit"].min():.2f}')
        print(f'Average Time Held: {trades_df["time_held_min"].mean():.0f} minutes')

    # Save results
    trades_df.to_csv('data/backtest_results_20260126.csv', index=False)
    print(f'\n✅ Saved detailed results to data/backtest_results_20260126.csv')

    # Analysis
    print('\n' + '=' * 80)
    print('ANALYSIS')
    print('=' * 80)

    print(f'\nTo make $1,000/day with ${starting_capital:,}:')
    daily_goal = 1000
    if total_profit > 0:
        multiplier = daily_goal / total_profit
        print(f'  Current strategy made: ${total_profit:.2f}')
        print(f'  Need to scale by: {multiplier:.1f}x')
        print(f'  Required capital: ${starting_capital * multiplier:,.0f}')
        print(f'  OR increase position size by {multiplier:.1f}x')
    else:
        print('  Strategy lost money - needs improvement')

    return trades_df


if __name__ == '__main__':
    # Run backtest with different parameters
    print('Testing with $10,000 capital, $25 minimum credit per spread...\n')
    trades = run_backtest(starting_capital=10000, min_credit_per_spread=25)
