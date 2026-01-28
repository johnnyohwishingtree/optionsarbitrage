#!/usr/bin/env python3
"""
BOTH SIDES Backtest: Hold-to-Expiration Arbitrage Strategy

The Insight:
- Trade BOTH calls AND puts at the same strike
- Collect credit on BOTH sides at entry
- At expiration, only ONE side is ITM (pay settlement)
- OTHER side expires worthless (keep that credit as profit!)
- This DOUBLES the edge while risk stays the same

Strategy:
1. At market open, determine strikes from opening prices
   - SPY opens at $690.47 → use $690 strike
   - SPX opens at $6923.23 → use $6925 strike (nearest $5)
2. Enter BOTH sides in morning window:
   CALLS: Sell SPY calls, Buy SPX calls (credit)
   PUTS: Sell SPY puts, Buy SPX puts (credit)
3. HOLD until 4 PM
4. At expiration:
   - If market UP: Calls settle (cost), Puts expire (profit)
   - If market DOWN: Puts settle (cost), Calls expire (profit)
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


def calculate_expiration_value(spy_close, spx_close, spy_strike, spx_strike, num_spreads,
                               call_direction, put_direction):
    """
    Calculate P&L at expiration (4 PM) for BOTH SIDES

    At expiration, options settle to intrinsic value:
    - Calls: max(0, close - strike)
    - Puts: max(0, strike - close)

    Direction can be:
    - 'Sell SPY, Buy SPX': Short SPY, Long SPX
    - 'Sell SPX, Buy SPY': Short SPX, Long SPY
    """
    spy_contracts = 10 * num_spreads
    spx_contracts = num_spreads

    # Calculate intrinsic values
    spy_call_intrinsic = max(0, spy_close - spy_strike)
    spx_call_intrinsic = max(0, spx_close - spx_strike)
    spy_put_intrinsic = max(0, spy_strike - spy_close)
    spx_put_intrinsic = max(0, spx_strike - spx_close)

    # CALL settlement based on direction
    if call_direction == 'Sell SPY, Buy SPX':
        # Short SPY calls, Long SPX calls
        spy_call_obligation = spy_call_intrinsic * 100 * spy_contracts
        spx_call_receipt = spx_call_intrinsic * 100 * spx_contracts
        call_net_settlement = spx_call_receipt - spy_call_obligation
    else:
        # Short SPX calls, Long SPY calls
        spx_call_obligation = spx_call_intrinsic * 100 * spx_contracts
        spy_call_receipt = spy_call_intrinsic * 100 * spy_contracts
        call_net_settlement = spy_call_receipt - spx_call_obligation

    # PUT settlement based on direction
    if put_direction == 'Sell SPY, Buy SPX':
        # Short SPY puts, Long SPX puts
        spy_put_obligation = spy_put_intrinsic * 100 * spy_contracts
        spx_put_receipt = spx_put_intrinsic * 100 * spx_contracts
        put_net_settlement = spx_put_receipt - spy_put_obligation
    else:
        # Short SPX puts, Long SPY puts
        spx_put_obligation = spx_put_intrinsic * 100 * spx_contracts
        spy_put_receipt = spy_put_intrinsic * 100 * spy_contracts
        put_net_settlement = spy_put_receipt - spx_put_obligation

    # Exit commission for BOTH sides (220 contracts total)
    total_contracts = (spy_contracts + spx_contracts) * 2
    exit_commission = COMMISSION_PER_CONTRACT * total_contracts

    # Total settlement
    total_net_settlement = call_net_settlement + put_net_settlement - exit_commission

    return {
        'spy_call_intrinsic': spy_call_intrinsic,
        'spx_call_intrinsic': spx_call_intrinsic,
        'spy_put_intrinsic': spy_put_intrinsic,
        'spx_put_intrinsic': spx_put_intrinsic,
        'call_net_settlement': call_net_settlement,
        'put_net_settlement': put_net_settlement,
        'exit_commission': exit_commission,
        'total_net_settlement': total_net_settlement
    }


def run_hold_to_expiration_backtest(starting_capital=10000, entry_window_start='09:45', entry_window_end='10:30'):
    """
    Run CORRECT backtest: Hold to expiration
    """
    print('=' * 80)
    print(f'HOLD-TO-EXPIRATION BACKTEST - Capital: ${starting_capital:,.0f}')
    print('=' * 80)

    print('\nStrategy (DYNAMIC STRIKES):')
    print(f'  1. Entry window: {entry_window_start} - {entry_window_end}')
    print(f'  2. Test strikes that BRACKET CURRENT prices at each timestamp (2×2 = 4 combos)')
    print(f'  3. Enter with BEST expected P&L (credit - estimated settlement)')
    print(f'  4. HOLD until 4:00 PM (NO EXITS!)')
    print(f'  5. Let options expire and settle')
    print(f'  6. Profit = Credit - Settlement - Fees')
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

    # Opening prices (for reference only, not used for strike selection)
    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    print(f'   Opening prices at 9:30 AM:')
    print(f'     SPY: ${spy_open:.2f}')
    print(f'     SPX: ${spx_open:.2f}')
    print(f'\n   ⚠️  Strikes will be calculated DYNAMICALLY at each timestamp')
    print(f'   Each timestamp tests strikes that bracket the CURRENT price')

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
    best_expected_pnl = -float('inf')  # Track best expected P&L, not just credit

    timestamps_checked = 0
    timestamps_skipped_no_data = 0
    timestamps_skipped_negative_credit = 0

    for idx, row in window_data.iterrows():
        current_time = row['time']
        spy_price = row['spy_price']
        spx_price = row['spx_price']

        timestamps_checked += 1

        # DYNAMIC: Calculate strikes that bracket CURRENT price at this timestamp
        spy_strike_below = int(spy_price)  # floor
        spy_strike_above = spy_strike_below + 1
        spx_strike_below = int(spx_price / 5) * 5
        spx_strike_above = spx_strike_below + 5

        spy_strikes_to_test = [spy_strike_below, spy_strike_above]
        spx_strikes_to_test = [spx_strike_below, spx_strike_above]

        # Try all strike combinations
        for spy_strike in spy_strikes_to_test:
            for spx_strike in spx_strikes_to_test:
                # Get option prices for this strike combo
                spy_call_mid = get_option_price(options, 'SPY', spy_strike, 'C', current_time)
                spx_call_mid = get_option_price(options, 'SPX', spx_strike, 'C', current_time)
                spy_put_mid = get_option_price(options, 'SPY', spy_strike, 'P', current_time)
                spx_put_mid = get_option_price(options, 'SPX', spx_strike, 'P', current_time)

                if any(x is None for x in [spy_call_mid, spx_call_mid, spy_put_mid, spx_put_mid]):
                    continue

                # Calculate credit for max position
                num_spreads = min(10, int(starting_capital / 1000))
                spy_contracts = 10 * num_spreads
                spx_contracts = num_spreads

                spy_call_bid, spy_call_ask = estimate_bid_ask(spy_call_mid)
                spx_call_bid, spx_call_ask = estimate_bid_ask(spx_call_mid)
                spy_put_bid, spy_put_ask = estimate_bid_ask(spy_put_mid)
                spx_put_bid, spx_put_ask = estimate_bid_ask(spx_put_mid)

                # CALL SIDE: Try BOTH directions, pick the one that gives credit
                call_credit_A = (spy_call_bid * 100 * spy_contracts) - (spx_call_ask * 100 * spx_contracts)
                call_credit_B = (spx_call_bid * 100 * spx_contracts) - (spy_call_ask * 100 * spy_contracts)

                if call_credit_A > call_credit_B:
                    call_credit = call_credit_A
                    call_direction = 'Sell SPY, Buy SPX'
                else:
                    call_credit = call_credit_B
                    call_direction = 'Sell SPX, Buy SPY'

                # PUT SIDE: Try BOTH directions, pick the one that gives credit
                put_credit_A = (spy_put_bid * 100 * spy_contracts) - (spx_put_ask * 100 * spx_contracts)
                put_credit_B = (spx_put_bid * 100 * spx_contracts) - (spy_put_ask * 100 * spy_contracts)

                if put_credit_A > put_credit_B:
                    put_credit = put_credit_A
                    put_direction = 'Sell SPY, Buy SPX'
                else:
                    put_credit = put_credit_B
                    put_direction = 'Sell SPX, Buy SPY'

                # CRITICAL: BOTH sides must give credit, or skip this strike combo!
                if call_credit <= 0 or put_credit <= 0:
                    continue

                # Both sides give credit, calculate net credit
                total_contracts = (spy_contracts + spx_contracts) * 2  # calls + puts
                entry_commission = COMMISSION_PER_CONTRACT * total_contracts
                exit_commission = entry_commission  # same for exit
                net_credit = call_credit + put_credit - entry_commission

                # ESTIMATE settlement cost based on CURRENT prices at entry
                spy_call_intrinsic_now = max(0, spy_price - spy_strike)
                spx_call_intrinsic_now = max(0, spx_price - spx_strike)
                spy_put_intrinsic_now = max(0, spy_strike - spy_price)
                spx_put_intrinsic_now = max(0, spx_strike - spx_price)

                # Calculate expected settlement based on direction
                if call_direction == 'Sell SPY, Buy SPX':
                    expected_call_settlement = (spx_call_intrinsic_now * 100 * spx_contracts) - (spy_call_intrinsic_now * 100 * spy_contracts)
                else:
                    expected_call_settlement = (spy_call_intrinsic_now * 100 * spy_contracts) - (spx_call_intrinsic_now * 100 * spx_contracts)

                if put_direction == 'Sell SPY, Buy SPX':
                    expected_put_settlement = (spx_put_intrinsic_now * 100 * spx_contracts) - (spy_put_intrinsic_now * 100 * spy_contracts)
                else:
                    expected_put_settlement = (spy_put_intrinsic_now * 100 * spy_contracts) - (spx_put_intrinsic_now * 100 * spx_contracts)

                expected_settlement = expected_call_settlement + expected_put_settlement - exit_commission
                expected_pnl = net_credit + expected_settlement

                # Optimize for EXPECTED P&L (credit - estimated settlement), not just credit
                if expected_pnl > best_expected_pnl:
                    best_expected_pnl = expected_pnl
                    best_entry = {
                        'time': current_time,
                        'spy_price': spy_price,
                        'spx_price': spx_price,
                        'spy_strike': spy_strike,
                        'spx_strike': spx_strike,
                        'spy_call_mid': spy_call_mid,
                        'spx_call_mid': spx_call_mid,
                        'spy_put_mid': spy_put_mid,
                        'spx_put_mid': spx_put_mid,
                        'spy_call_bid': spy_call_bid,
                        'spx_call_ask': spx_call_ask,
                        'spy_put_bid': spy_put_bid,
                        'spx_put_ask': spx_put_ask,
                        'call_credit': call_credit,
                        'put_credit': put_credit,
                        'call_direction': call_direction,
                        'put_direction': put_direction,
                        'enter_calls': True,
                        'enter_puts': True,
                        'num_spreads': num_spreads,
                        'spy_contracts': spy_contracts,
                        'spx_contracts': spx_contracts,
                        'net_credit': net_credit,
                        'entry_commission': entry_commission,
                        'expected_settlement': expected_settlement,
                        'expected_pnl': expected_pnl
                    }

        # Update skip counters (now done per timestamp, not per strike combo)
        if best_entry is None or best_entry['time'] != current_time:
            timestamps_skipped_negative_credit += 1

    # Print summary
    print(f'\n   Timestamps in window: {len(window_data)}')
    print(f'   Timestamps checked: {timestamps_checked}')
    print(f'   Skipped (no data): {timestamps_skipped_no_data}')
    print(f'   Skipped (negative credit): {timestamps_skipped_negative_credit}')
    print(f'   Valid entries: {1 if best_entry else 0}')

    if best_entry is None:
        print('\n❌ No valid entries found in window')
        print('   This means at NO timestamp did BOTH call AND put spreads give credit')
        return None

    # Display entry
    print('\n' + '=' * 80)
    print('ENTRY (Best Expected P&L in Window) - BOTH SIDES')
    print('=' * 80)
    print(f'\n✅ ENTERED at {best_entry["time"].strftime("%H:%M:%S")}')
    print(f'\n   Underlying Prices:')
    print(f'     SPY: ${best_entry["spy_price"]:.2f}')
    print(f'     SPX: ${best_entry["spx_price"]:.2f}')

    # Calculate bid/ask from mid for display
    spy_call_bid, spy_call_ask = estimate_bid_ask(best_entry["spy_call_mid"])
    spx_call_bid, spx_call_ask = estimate_bid_ask(best_entry["spx_call_mid"])
    spy_put_bid, spy_put_ask = estimate_bid_ask(best_entry["spy_put_mid"])
    spx_put_bid, spx_put_ask = estimate_bid_ask(best_entry["spx_put_mid"])

    print(f'\n   📞 CALL SIDE:')
    print(f'     Direction: {best_entry["call_direction"]}')
    if best_entry["call_direction"] == 'Sell SPY, Buy SPX':
        print(f'     Sell {best_entry["spy_contracts"]} SPY ${best_entry["spy_strike"]} calls @ ${spy_call_bid:.2f} bid')
        print(f'     Buy {best_entry["spx_contracts"]} SPX ${best_entry["spx_strike"]} calls @ ${spx_call_ask:.2f} ask')
    else:
        print(f'     Sell {best_entry["spx_contracts"]} SPX ${best_entry["spx_strike"]} calls @ ${spx_call_bid:.2f} bid')
        print(f'     Buy {best_entry["spy_contracts"]} SPY ${best_entry["spy_strike"]} calls @ ${spy_call_ask:.2f} ask')
    print(f'     Call Credit: ${best_entry["call_credit"]:,.2f}')

    print(f'\n   📉 PUT SIDE:')
    print(f'     Direction: {best_entry["put_direction"]}')
    if best_entry["put_direction"] == 'Sell SPY, Buy SPX':
        print(f'     Sell {best_entry["spy_contracts"]} SPY ${best_entry["spy_strike"]} puts @ ${spy_put_bid:.2f} bid')
        print(f'     Buy {best_entry["spx_contracts"]} SPX ${best_entry["spx_strike"]} puts @ ${spx_put_ask:.2f} ask')
    else:
        print(f'     Sell {best_entry["spx_contracts"]} SPX ${best_entry["spx_strike"]} puts @ ${spx_put_bid:.2f} bid')
        print(f'     Buy {best_entry["spy_contracts"]} SPY ${best_entry["spy_strike"]} puts @ ${spy_put_ask:.2f} ask')
    print(f'     Put Credit: ${best_entry["put_credit"]:,.2f}')

    print(f'\n   Entry Commission: ${best_entry["entry_commission"]:.2f} (220 contracts)')
    print(f'   TOTAL NET CREDIT: ${best_entry["net_credit"]:,.2f}')
    print(f'\n   📊 Expected Settlement (at entry prices): ${best_entry["expected_settlement"]:,.2f}')
    print(f'   💰 Expected P&L: ${best_entry["expected_pnl"]:,.2f}')
    print(f'\n   Position: {best_entry["num_spreads"]} spreads on BOTH sides')
    print(f'   Credit per spread: ${best_entry["net_credit"] / best_entry["num_spreads"]:.2f}')
    print(f'   Expected P&L per spread: ${best_entry["expected_pnl"] / best_entry["num_spreads"]:.2f}')

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
        best_entry['num_spreads'],
        best_entry['call_direction'],
        best_entry['put_direction']
    )

    print(f'\n📊 Closing Prices:')
    print(f'   SPY: ${spy_close:.2f} (strike was ${best_entry["spy_strike"]})')
    print(f'   SPX: ${spx_close:.2f} (strike was ${best_entry["spx_strike"]})')

    market_direction = "UP ⬆️" if spy_close > best_entry["spy_strike"] else "DOWN ⬇️"
    print(f'\n   Market moved {market_direction}')

    print(f'\n💰 Intrinsic Values:')
    print(f'   CALLS:')
    print(f'     SPY Call: ${settlement["spy_call_intrinsic"]:.2f} per share')
    print(f'     SPX Call: ${settlement["spx_call_intrinsic"]:.2f} per point')
    print(f'   PUTS:')
    print(f'     SPY Put: ${settlement["spy_put_intrinsic"]:.2f} per share')
    print(f'     SPX Put: ${settlement["spx_put_intrinsic"]:.2f} per point')

    print(f'\n📤 Settlement:')
    print(f'   📞 CALL Side: ${settlement["call_net_settlement"]:,.2f}')
    if spy_close > best_entry["spy_strike"]:
        print(f'      (Calls are ITM - settlement cost)')
    else:
        print(f'      (Calls expired worthless - keep the credit!)')

    print(f'   📉 PUT Side: ${settlement["put_net_settlement"]:,.2f}')
    if spy_close < best_entry["spy_strike"]:
        print(f'      (Puts are ITM - settlement cost)')
    else:
        print(f'      (Puts expired worthless - keep the credit!)')

    print(f'   Exit Commission: -${settlement["exit_commission"]:.2f}')
    print(f'   Total Net Settlement: ${settlement["total_net_settlement"]:,.2f}')

    # Calculate final P&L
    total_pnl = best_entry['net_credit'] + settlement['total_net_settlement']
    pnl_pct = (total_pnl / best_entry['net_credit']) * 100 if best_entry['net_credit'] > 0 else 0

    final_capital = starting_capital + total_pnl

    print('\n' + '=' * 80)
    print('FINAL RESULTS')
    print('=' * 80)

    print(f'\n💵 P&L Breakdown:')
    print(f'   Entry Credit (BOTH sides): +${best_entry["net_credit"]:,.2f}')
    print(f'     Call credit: +${best_entry["call_credit"]:,.2f}')
    print(f'     Put credit: +${best_entry["put_credit"]:,.2f}')
    print(f'   Settlement Cost: ${settlement["total_net_settlement"]:,.2f}')
    print(f'     Call settlement: ${settlement["call_net_settlement"]:,.2f}')
    print(f'     Put settlement: ${settlement["put_net_settlement"]:,.2f}')
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
        'call_direction': best_entry['call_direction'],
        'put_direction': best_entry['put_direction'],
        'credit_received': best_entry['net_credit'],
        'settlement_cost': settlement['total_net_settlement'],
        'total_pnl': total_pnl,
        'return_pct': pnl_pct
    }

    pd.DataFrame([results]).to_csv('data/hold_to_expiration_results.csv', index=False)
    print(f'\n✅ Saved results to data/hold_to_expiration_results.csv')

    return results


if __name__ == '__main__':
    print('Running CORRECT backtest: Hold-to-Expiration Arbitrage\n')
    run_hold_to_expiration_backtest(starting_capital=10000)
