#!/usr/bin/env python3
"""
OPTIMIZED Backtest based on real data analysis

Key learnings:
1. Early exit is CRITICAL (don't hold too long)
2. Profit targets should be modest (10-20%, not 50%)
3. Need stop losses to cut losers quickly
4. Best entries are 9:45-10:00 AM with exits within 20 minutes
"""

import pandas as pd
import numpy as np
from datetime import datetime, time

COMMISSION_PER_CONTRACT = 0.50

def estimate_bid_ask(mid_price):
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
    if symbol == 'SPY':
        return round(price)
    else:
        return round(price / 5) * 5

def get_option_price(options_df, symbol, strike, right, timestamp):
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

def run_optimized_backtest(
    starting_capital=10000,
    profit_target_pct=15,  # Much more aggressive
    stop_loss_pct=-20,     # Stop loss at -20%
    max_hold_minutes=30    # Force exit after 30 min
):
    print('=' * 80)
    print(f'OPTIMIZED BACKTEST - Capital: ${starting_capital:,.0f}')
    print('=' * 80)

    print('\nStrategy Rules (Based on Data Analysis):')
    print(f'  1. Entry window: 9:45 AM - 10:00 AM (15 min window)')
    print(f'  2. Profit target: {profit_target_pct}% (take profits quick!)')
    print(f'  3. Stop loss: {stop_loss_pct}% (cut losers fast!)')
    print(f'  4. Max hold time: {max_hold_minutes} minutes')
    print(f'  5. Position size: Conservative (1-2 spreads to start)')
    print()

    # Load data
    print('📊 Loading data...')
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    options = pd.read_csv('data/options_data_20260126.csv')

    underlying['time'] = pd.to_datetime(underlying['time'])
    options['time'] = pd.to_datetime(options['time'])

    spy_data = underlying[underlying['symbol'] == 'SPY'].copy()
    spx_data = underlying[underlying['symbol'] == 'SPX'].copy()

    merged = pd.merge(
        spy_data[['time', 'close']].rename(columns={'close': 'spy_price'}),
        spx_data[['time', 'close']].rename(columns={'close': 'spx_price'}),
        on='time'
    )

    print(f'   Total minutes: {len(merged)}')

    capital = starting_capital
    position = None
    trades = []

    print('\n' + '=' * 80)
    print('TRADING SIMULATION')
    print('=' * 80)

    for idx, row in merged.iterrows():
        current_time = row['time']
        time_only = current_time.time()

        # Entry logic - TIGHT WINDOW
        if position is None:
            if time(9, 45) <= time_only <= time(10, 0):  # Only 15 minute window
                spy_price = row['spy_price']
                spx_price = row['spx_price']

                spy_strike = find_atm_strike(spy_price, 'SPY')
                spx_strike = find_atm_strike(spx_price / 10, 'SPX') * 10

                spy_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
                spx_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)

                if spy_mid is None or spx_mid is None:
                    continue

                # Conservative position size: 1-2 spreads
                num_spreads = 2
                spy_contracts = 10 * num_spreads
                spx_contracts = num_spreads

                spy_bid, spy_ask = estimate_bid_ask(spy_mid)
                spx_bid, spx_ask = estimate_bid_ask(spx_mid)

                premium_received = spy_bid * 100 * spy_contracts
                premium_paid = spx_ask * 100 * spx_contracts
                entry_commission = COMMISSION_PER_CONTRACT * (spy_contracts + spx_contracts)
                net_credit = premium_received - premium_paid - entry_commission

                position = {
                    'entry_time': current_time,
                    'spy_strike': spy_strike,
                    'spx_strike': spx_strike,
                    'spy_contracts': spy_contracts,
                    'spx_contracts': spx_contracts,
                    'net_credit': net_credit,
                    'entry_commission': entry_commission,
                    'num_spreads': num_spreads,
                    'spy_entry_price': spy_mid,
                    'spx_entry_price': spx_mid
                }

                print(f'\n✅ ENTRY at {current_time.strftime("%H:%M:%S")}')
                print(f'   SPY ${spy_price:.2f} → Sell {spy_contracts} × {spy_strike} calls @ ${spy_bid:.2f}')
                print(f'   SPX ${spx_price:.2f} → Buy {spx_contracts} × {spx_strike} calls @ ${spx_ask:.2f}')
                print(f'   Net Credit: ${net_credit:.2f}')
                print(f'   Target: ${net_credit * (1 + profit_target_pct/100):.2f} (+{profit_target_pct}%)')

        # Exit logic - AGGRESSIVE
        elif position is not None:
            spy_strike = position['spy_strike']
            spx_strike = position['spx_strike']

            spy_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
            spx_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)

            if spy_mid is None or spx_mid is None:
                continue

            spy_bid, spy_ask = estimate_bid_ask(spy_mid)
            spx_bid, spx_ask = estimate_bid_ask(spx_mid)

            cost_spy = spy_ask * 100 * position['spy_contracts']
            received_spx = spx_bid * 100 * position['spx_contracts']
            exit_commission = COMMISSION_PER_CONTRACT * (position['spy_contracts'] + position['spx_contracts'])
            net_cost = cost_spy - received_spx + exit_commission

            net_profit = position['net_credit'] - net_cost
            profit_pct = (net_profit / position['net_credit']) * 100 if position['net_credit'] > 0 else 0

            time_held = (current_time - position['entry_time']).total_seconds() / 60

            should_exit = False
            exit_reason = ''

            # Exit conditions
            if profit_pct >= profit_target_pct:
                should_exit = True
                exit_reason = f'{profit_target_pct}% Profit Target'
            elif profit_pct <= stop_loss_pct:
                should_exit = True
                exit_reason = f'{stop_loss_pct}% Stop Loss'
            elif time_held >= max_hold_minutes:
                should_exit = True
                exit_reason = f'{max_hold_minutes}min Time Limit'

            if should_exit:
                capital += net_profit

                trade_record = {
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                    'num_spreads': position['num_spreads'],
                    'credit_received': position['net_credit'],
                    'exit_cost': net_cost,
                    'net_profit': net_profit,
                    'profit_pct': profit_pct,
                    'exit_reason': exit_reason,
                    'time_held_min': time_held,
                    'total_commission': position['entry_commission'] + exit_commission
                }

                trades.append(trade_record)

                print(f'\n❌ EXIT at {current_time.strftime("%H:%M:%S")} - {exit_reason}')
                print(f'   SPY: ${position["spy_entry_price"]:.2f} → ${spy_mid:.2f}')
                print(f'   SPX: ${position["spx_entry_price"]:.2f} → ${spx_mid:.2f}')
                print(f'   Exit Cost: ${net_cost:.2f}')
                print(f'   💰 NET PROFIT: ${net_profit:.2f} ({profit_pct:.1f}%)')
                print(f'   Time Held: {time_held:.0f} minutes')
                print(f'   New Capital: ${capital:,.2f}')

                position = None

    # Summary
    print('\n' + '=' * 80)
    print('RESULTS')
    print('=' * 80)

    if not trades:
        print('\n❌ No trades executed')
        return None

    trades_df = pd.DataFrame(trades)

    total_profit = trades_df['net_profit'].sum()
    winning_trades = len(trades_df[trades_df['net_profit'] > 0])
    win_rate = (winning_trades / len(trades)) * 100 if len(trades) > 0 else 0

    print(f'\nStarting Capital: ${starting_capital:,.2f}')
    print(f'Ending Capital: ${capital:,.2f}')
    print(f'Total P&L: ${total_profit:,.2f} ({(total_profit/starting_capital)*100:.2f}%)')
    print(f'\nTrades: {len(trades)}')
    print(f'Winners: {winning_trades}/{len(trades)} ({win_rate:.0f}%)')

    if len(trades) > 0:
        print(f'\nAverage P&L: ${trades_df["net_profit"].mean():.2f}')
        print(f'Best Trade: ${trades_df["net_profit"].max():.2f}')
        print(f'Worst Trade: ${trades_df["net_profit"].min():.2f}')
        print(f'Average Hold Time: {trades_df["time_held_min"].mean():.0f} min')

    print('\n' + '=' * 80)
    print('SCALING TO $1,000/DAY GOAL')
    print('=' * 80)

    if total_profit > 0:
        scale_factor = 1000 / total_profit
        required_capital = starting_capital * scale_factor
        required_spreads = 2 * scale_factor

        print(f'\nCurrent Results:')
        print(f'  Profit: ${total_profit:.2f}')
        print(f'  Capital: ${starting_capital:,.0f}')
        print(f'  Position: {2} spreads')

        print(f'\nTo make $1,000/day:')
        print(f'  Need to scale by: {scale_factor:.1f}x')
        print(f'  Required capital: ${required_capital:,.0f}')
        print(f'  Required position: {required_spreads:.0f} spreads')

        if required_capital > 100000:
            print(f'\n⚠️  WARNING: ${required_capital:,.0f} is a lot of capital!')
            print(f'    Consider: Multiple trades per day instead of one big trade')
    else:
        print(f'\n❌ Strategy lost ${abs(total_profit):.2f}')
        print('   Strategy needs more work')

    trades_df.to_csv('data/optimized_backtest_results.csv', index=False)
    print(f'\n✅ Saved to data/optimized_backtest_results.csv')

    return trades_df


if __name__ == '__main__':
    print('Testing optimized strategy based on historical data analysis...\n')

    # Test different parameters
    print('\n' + '='*80)
    print('TEST 1: Conservative (15% profit, -20% stop, 30 min max)')
    print('='*80)
    run_optimized_backtest(
        starting_capital=10000,
        profit_target_pct=15,
        stop_loss_pct=-20,
        max_hold_minutes=30
    )

    print('\n\n' + '='*80)
    print('TEST 2: Aggressive (10% profit, -15% stop, 20 min max)')
    print('='*80)
    run_optimized_backtest(
        starting_capital=10000,
        profit_target_pct=10,
        stop_loss_pct=-15,
        max_hold_minutes=20
    )
