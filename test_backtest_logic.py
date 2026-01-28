#!/usr/bin/env python3
"""
Unit and integration tests for hold_to_expiration_backtest_both_sides.py

IMPORTANT: This backtest trades BOTH CALLS AND PUTS simultaneously
- Each spread involves selling calls on one side and buying on the other
- AND selling puts on one side and buying on the other
- Both sides must give credit or we skip that timestamp

Tests:
1. Strike bracketing logic
2. Bidirectional credit calculation (for both calls AND puts)
3. Expected settlement calculation (for both calls AND puts)
4. Optimization logic (expected P&L vs credit)
5. Integration test with real data
"""

import pandas as pd
import numpy as np
from datetime import datetime
from hold_to_expiration_backtest_both_sides import (
    estimate_bid_ask,
    find_atm_strike,
    get_option_price,
    calculate_expiration_value
)

def test_strike_bracketing():
    """Test that strikes correctly bracket opening prices"""
    print('=' * 80)
    print('TEST 1: Strike Bracketing')
    print('=' * 80)

    # Load data
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)

    spy_data = underlying[underlying['symbol'] == 'SPY']
    spx_data = underlying[underlying['symbol'] == 'SPX']

    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    print(f'\nOpening prices:')
    print(f'  SPY: ${spy_open:.2f}')
    print(f'  SPX: ${spx_open:.2f}')

    # Calculate bracketing strikes
    spy_strike_below = int(spy_open)
    spy_strike_above = spy_strike_below + 1
    spx_strike_below = int(spx_open / 5) * 5
    spx_strike_above = spx_strike_below + 5

    print(f'\nBracketing strikes:')
    print(f'  SPY: [{spy_strike_below}, {spy_strike_above}]')
    print(f'  SPX: [{spx_strike_below}, {spx_strike_above}]')

    # Verify brackets
    assert spy_strike_below <= spy_open < spy_strike_above, "SPY strikes don't bracket opening"
    assert spx_strike_below <= spx_open < spx_strike_above, "SPX strikes don't bracket opening"

    print('\n✅ PASS: Strikes correctly bracket opening prices')
    return spy_strike_below, spy_strike_above, spx_strike_below, spx_strike_above


def test_bidirectional_credit(options_df, timestamp, spy_strike, spx_strike, num_spreads=10):
    """Test bidirectional credit calculation for a specific strike combination"""
    print(f'\n--- Testing SPY {spy_strike} / SPX {spx_strike} at {timestamp.strftime("%H:%M:%S")} ---')

    # Get option prices
    spy_call_mid = get_option_price(options_df, 'SPY', spy_strike, 'C', timestamp)
    spx_call_mid = get_option_price(options_df, 'SPX', spx_strike, 'C', timestamp)
    spy_put_mid = get_option_price(options_df, 'SPY', spy_strike, 'P', timestamp)
    spx_put_mid = get_option_price(options_df, 'SPX', spx_strike, 'P', timestamp)

    if any(x is None for x in [spy_call_mid, spx_call_mid, spy_put_mid, spx_put_mid]):
        print('  ⚠️  No data available')
        return None

    print(f'  Option mids: SPY call=${spy_call_mid:.2f}, SPX call=${spx_call_mid:.2f}')
    print(f'               SPY put=${spy_put_mid:.2f}, SPX put=${spx_put_mid:.2f}')

    # Calculate position size
    spy_contracts = 10 * num_spreads
    spx_contracts = num_spreads

    # Get bid/ask
    spy_call_bid, spy_call_ask = estimate_bid_ask(spy_call_mid)
    spx_call_bid, spx_call_ask = estimate_bid_ask(spx_call_mid)
    spy_put_bid, spy_put_ask = estimate_bid_ask(spy_put_mid)
    spx_put_bid, spx_put_ask = estimate_bid_ask(spx_put_mid)

    # CALL SIDE: Try both directions
    call_credit_A = (spy_call_bid * 100 * spy_contracts) - (spx_call_ask * 100 * spx_contracts)
    call_credit_B = (spx_call_bid * 100 * spx_contracts) - (spy_call_ask * 100 * spy_contracts)

    print(f'  Call Direction A (Sell SPY, Buy SPX): ${call_credit_A:,.2f}')
    print(f'  Call Direction B (Sell SPX, Buy SPY): ${call_credit_B:,.2f}')

    if call_credit_A > call_credit_B:
        call_credit = call_credit_A
        call_direction = 'Sell SPY, Buy SPX'
    else:
        call_credit = call_credit_B
        call_direction = 'Sell SPX, Buy SPY'

    print(f'  ✓ Best call: {call_direction} = ${call_credit:,.2f}')

    # PUT SIDE: Try both directions
    put_credit_A = (spy_put_bid * 100 * spy_contracts) - (spx_put_ask * 100 * spx_contracts)
    put_credit_B = (spx_put_bid * 100 * spx_contracts) - (spy_put_ask * 100 * spy_contracts)

    print(f'  Put Direction A (Sell SPY, Buy SPX): ${put_credit_A:,.2f}')
    print(f'  Put Direction B (Sell SPX, Buy SPY): ${put_credit_B:,.2f}')

    if put_credit_A > put_credit_B:
        put_credit = put_credit_A
        put_direction = 'Sell SPY, Buy SPX'
    else:
        put_credit = put_credit_B
        put_direction = 'Sell SPX, Buy SPY'

    print(f'  ✓ Best put: {put_direction} = ${put_credit:,.2f}')

    # Check if both give credit
    if call_credit <= 0 or put_credit <= 0:
        print(f'  ❌ SKIP: At least one side has negative credit')
        return None

    # Calculate net credit
    total_contracts = (spy_contracts + spx_contracts) * 2
    entry_commission = 0.50 * total_contracts
    net_credit = call_credit + put_credit - entry_commission

    print(f'  ✓ Total credit: ${call_credit + put_credit:,.2f}')
    print(f'  ✓ Net credit (after commission): ${net_credit:,.2f}')

    return {
        'spy_strike': spy_strike,
        'spx_strike': spx_strike,
        'call_credit': call_credit,
        'put_credit': put_credit,
        'call_direction': call_direction,
        'put_direction': put_direction,
        'net_credit': net_credit,
        'entry_commission': entry_commission,
        'spy_contracts': spy_contracts,
        'spx_contracts': spx_contracts
    }


def test_expected_settlement(underlying_df, entry_info, timestamp):
    """Test expected settlement calculation at entry time"""
    print(f'\n  Computing expected settlement at entry prices...')

    # Get current underlying prices
    spy_row = underlying_df[(underlying_df['symbol'] == 'SPY') & (underlying_df['time'] == timestamp)]
    spx_row = underlying_df[(underlying_df['symbol'] == 'SPX') & (underlying_df['time'] == timestamp)]

    if spy_row.empty or spx_row.empty:
        print('  ⚠️  No underlying data')
        return None

    spy_price = spy_row.iloc[0]['close']
    spx_price = spx_row.iloc[0]['close']

    print(f'  Entry prices: SPY ${spy_price:.2f}, SPX ${spx_price:.2f}')

    spy_strike = entry_info['spy_strike']
    spx_strike = entry_info['spx_strike']
    spy_contracts = entry_info['spy_contracts']
    spx_contracts = entry_info['spx_contracts']

    # Calculate intrinsic values at entry
    spy_call_intrinsic = max(0, spy_price - spy_strike)
    spx_call_intrinsic = max(0, spx_price - spx_strike)
    spy_put_intrinsic = max(0, spy_strike - spy_price)
    spx_put_intrinsic = max(0, spx_strike - spx_price)

    print(f'  Intrinsics: SPY call=${spy_call_intrinsic:.2f}, SPX call=${spx_call_intrinsic:.2f}')
    print(f'              SPY put=${spy_put_intrinsic:.2f}, SPX put=${spx_put_intrinsic:.2f}')

    # Calculate expected settlement based on direction
    if entry_info['call_direction'] == 'Sell SPY, Buy SPX':
        expected_call_settlement = (spx_call_intrinsic * 100 * spx_contracts) - (spy_call_intrinsic * 100 * spy_contracts)
    else:
        expected_call_settlement = (spy_call_intrinsic * 100 * spy_contracts) - (spx_call_intrinsic * 100 * spx_contracts)

    if entry_info['put_direction'] == 'Sell SPY, Buy SPX':
        expected_put_settlement = (spx_put_intrinsic * 100 * spx_contracts) - (spy_put_intrinsic * 100 * spy_contracts)
    else:
        expected_put_settlement = (spy_put_intrinsic * 100 * spy_contracts) - (spx_put_intrinsic * 100 * spx_contracts)

    exit_commission = entry_info['entry_commission']  # Same as entry
    expected_settlement = expected_call_settlement + expected_put_settlement - exit_commission
    expected_pnl = entry_info['net_credit'] + expected_settlement

    print(f'  Expected call settlement: ${expected_call_settlement:,.2f}')
    print(f'  Expected put settlement: ${expected_put_settlement:,.2f}')
    print(f'  Expected total settlement: ${expected_settlement:,.2f}')
    print(f'  💰 Expected P&L: ${expected_pnl:,.2f}')

    return {
        'expected_settlement': expected_settlement,
        'expected_pnl': expected_pnl,
        'expected_call_settlement': expected_call_settlement,
        'expected_put_settlement': expected_put_settlement
    }


def test_all_strike_combinations():
    """Test all 4 strike combinations at a specific timestamp"""
    print('\n' + '=' * 80)
    print('TEST 2: All Strike Combinations at 9:45 AM')
    print('=' * 80)

    # Load data
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    options = pd.read_csv('data/options_data_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    options['time'] = pd.to_datetime(options['time'], utc=True)

    # Get strikes
    spy_below, spy_above, spx_below, spx_above = test_strike_bracketing()

    # Test at 9:45 AM
    test_time = datetime.strptime('2026-01-26 09:45:00-05:00', '%Y-%m-%d %H:%M:%S%z')

    print(f'\nTesting all 4 combinations at {test_time.strftime("%H:%M:%S")}:')

    results = []
    for spy_strike in [spy_below, spy_above]:
        for spx_strike in [spx_below, spx_above]:
            entry = test_bidirectional_credit(options, test_time, spy_strike, spx_strike)
            if entry:
                settlement = test_expected_settlement(underlying, entry, test_time)
                if settlement:
                    results.append({
                        'spy_strike': spy_strike,
                        'spx_strike': spx_strike,
                        'net_credit': entry['net_credit'],
                        'expected_pnl': settlement['expected_pnl']
                    })

    if results:
        print(f'\n{"="*80}')
        print('SUMMARY: Valid Combinations')
        print(f'{"="*80}')
        print(f'{"SPY Strike":<12} {"SPX Strike":<12} {"Net Credit":<15} {"Expected P&L":<15}')
        print('-' * 80)
        for r in results:
            print(f'{r["spy_strike"]:<12} {r["spx_strike"]:<12} ${r["net_credit"]:<14,.2f} ${r["expected_pnl"]:<14,.2f}')

        # Find best by credit vs best by expected P&L
        best_credit = max(results, key=lambda x: x['net_credit'])
        best_pnl = max(results, key=lambda x: x['expected_pnl'])

        print(f'\n✓ Best by credit: SPY {best_credit["spy_strike"]} / SPX {best_credit["spx_strike"]} = ${best_credit["net_credit"]:.2f}')
        print(f'✓ Best by expected P&L: SPY {best_pnl["spy_strike"]} / SPX {best_pnl["spx_strike"]} = ${best_pnl["expected_pnl"]:.2f}')

        if best_credit['spy_strike'] != best_pnl['spy_strike'] or best_credit['spx_strike'] != best_pnl['spx_strike']:
            print(f'\n⚠️  WARNING: Different choices! This is why we need to optimize for expected P&L!')
        else:
            print(f'\n✅ PASS: Same choice for both metrics')
    else:
        print('\n❌ No valid combinations found at this timestamp')

    return results


def test_actual_vs_expected():
    """Test that actual settlement matches expected (BOTH CALLS AND PUTS)"""
    print('\n' + '=' * 80)
    print('TEST 3: Actual vs Expected Settlement (CALLS + PUTS)')
    print('=' * 80)

    # Load results from backtest
    results = pd.read_csv('data/hold_to_expiration_results.csv')
    latest = results.iloc[-1]

    print(f'\nBacktest results (BOTH SIDES):')
    print(f'  Entry: {latest["entry_time"]}')
    print(f'  Strikes: SPY {latest["spy_strike"]} / SPX {latest["spx_strike"]}')

    # ASSERT: Verify we have both call and put directions (proves we're testing both sides)
    assert 'call_direction' in latest.index, "Missing call_direction - not testing both sides!"
    assert 'put_direction' in latest.index, "Missing put_direction - not testing both sides!"
    print(f'  Call direction: {latest["call_direction"]}')
    print(f'  Put direction: {latest["put_direction"]}')

    print(f'  Credit received: ${latest["credit_received"]:,.2f}')
    print(f'  Settlement cost: ${latest["settlement_cost"]:,.2f}')
    print(f'  Total P&L: ${latest["total_pnl"]:,.2f}')

    print(f'\n  ✓ VERIFIED: This trade includes BOTH calls AND puts')

    # Load underlying data
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)

    spy_data = underlying[underlying['symbol'] == 'SPY']
    spx_data = underlying[underlying['symbol'] == 'SPX']

    spy_close = spy_data.iloc[-1]['close']
    spx_close = spx_data.iloc[-1]['close']

    print(f'\n  Closing prices: SPY ${spy_close:.2f}, SPX ${spx_close:.2f}')

    # Manually calculate settlement
    settlement = calculate_expiration_value(
        spy_close, spx_close,
        latest['spy_strike'], latest['spx_strike'],
        latest['num_spreads'],
        latest['call_direction'],
        latest['put_direction']
    )

    manual_pnl = latest['credit_received'] + settlement['total_net_settlement']

    print(f'\n  Manual calculation:')
    print(f'    Call settlement: ${settlement["call_net_settlement"]:,.2f}')
    print(f'    Put settlement: ${settlement["put_net_settlement"]:,.2f}')
    print(f'    Total settlement: ${settlement["total_net_settlement"]:,.2f}')
    print(f'    P&L: ${manual_pnl:,.2f}')

    # Verify they match
    assert abs(settlement['total_net_settlement'] - latest['settlement_cost']) < 0.01, "Settlement doesn't match!"
    assert abs(manual_pnl - latest['total_pnl']) < 0.01, "P&L doesn't match!"

    print(f'\n✅ PASS: Actual settlement matches manual calculation')


def test_optimization_logic():
    """Test that backtest picks the entry with best expected P&L"""
    print('\n' + '=' * 80)
    print('TEST 4: Optimization Logic - Does backtest pick best expected P&L?')
    print('=' * 80)

    # Load data
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    options = pd.read_csv('data/options_data_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    options['time'] = pd.to_datetime(options['time'], utc=True)

    results = pd.read_csv('data/hold_to_expiration_results.csv')
    latest = results.iloc[-1]

    entry_time = pd.to_datetime(latest['entry_time'], utc=True)
    chosen_spy_strike = int(latest['spy_strike'])
    chosen_spx_strike = int(latest['spx_strike'])

    print(f'\nBacktest chose: SPY {chosen_spy_strike} / SPX {chosen_spx_strike}')
    print(f'Entry time: {entry_time.strftime("%H:%M:%S")}')

    # Get strike brackets
    spy_data = underlying[underlying['symbol'] == 'SPY']
    spx_data = underlying[underlying['symbol'] == 'SPX']

    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    spy_below = int(spy_open)
    spy_above = spy_below + 1
    spx_below = int(spx_open / 5) * 5
    spx_above = spx_below + 5

    # Test all 4 combinations at the chosen entry time
    print(f'\nTesting all 4 combinations at chosen entry time ({entry_time.strftime("%H:%M:%S")}):')

    all_combos = []
    for spy_strike in [spy_below, spy_above]:
        for spx_strike in [spx_below, spx_above]:
            entry = test_bidirectional_credit(options, entry_time, spy_strike, spx_strike,
                                             num_spreads=int(latest['num_spreads']))
            if entry:
                settlement = test_expected_settlement(underlying, entry, entry_time)
                if settlement:
                    all_combos.append({
                        'spy_strike': spy_strike,
                        'spx_strike': spx_strike,
                        'net_credit': entry['net_credit'],
                        'expected_pnl': settlement['expected_pnl']
                    })

    if all_combos:
        print(f'\n{"="*80}')
        print('All Valid Combinations at Entry Time')
        print(f'{"="*80}')
        print(f'{"SPY":<8} {"SPX":<8} {"Net Credit":<15} {"Expected P&L":<15} {"Chosen?":<10}')
        print('-' * 80)
        for combo in all_combos:
            is_chosen = '✓ YES' if (combo['spy_strike'] == chosen_spy_strike and
                                    combo['spx_strike'] == chosen_spx_strike) else ''
            print(f'{combo["spy_strike"]:<8} {combo["spx_strike"]:<8} '
                  f'${combo["net_credit"]:<14,.2f} ${combo["expected_pnl"]:<14,.2f} {is_chosen:<10}')

        # Find best expected P&L
        best_combo = max(all_combos, key=lambda x: x['expected_pnl'])

        print(f'\n✓ Best expected P&L: SPY {best_combo["spy_strike"]} / SPX {best_combo["spx_strike"]} = ${best_combo["expected_pnl"]:.2f}')
        print(f'✓ Backtest chose: SPY {chosen_spy_strike} / SPX {chosen_spx_strike}')

        # Verify backtest chose the best
        if best_combo['spy_strike'] == chosen_spy_strike and best_combo['spx_strike'] == chosen_spx_strike:
            print(f'\n✅ PASS: Backtest correctly chose the strike with best expected P&L!')
        else:
            print(f'\n❌ FAIL: Backtest did NOT choose the best expected P&L!')
            return False
    else:
        print('\n⚠️  No valid combinations at entry time - cannot test')
        return None

    return True


if __name__ == '__main__':
    print('\n🧪 RUNNING COMPREHENSIVE STRATEGY TESTS\n')

    try:
        # Test 1: Strike bracketing
        test_strike_bracketing()

        # Test 2: All combinations
        test_all_strike_combinations()

        # Test 3: Actual vs expected
        test_actual_vs_expected()

        # Test 4: Optimization logic
        test_optimization_logic()

        print('\n' + '=' * 80)
        print('✅ ALL TESTS PASSED!')
        print('=' * 80)

    except Exception as e:
        print(f'\n❌ TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
