#!/usr/bin/env python3
"""
Test: Is the strategy price agnostic?

IMPORTANT: This tests a strategy that trades BOTH CALLS AND PUTS
- Not just calls alone - we have positions in both calls and puts
- Tests whether P&L changes based on final price level
- Checks if strategy has directional bias

Tests P&L at different ending prices to see if the strategy
has directional exposure or if it's truly market-neutral.
"""

import pandas as pd
from hold_to_expiration_backtest_both_sides import calculate_expiration_value

def test_different_ending_prices():
    """
    Test P&L sensitivity to ending price

    We'll use the actual backtest entry and test different ending scenarios:
    1. Market down 1%
    2. Market flat
    3. Market up 0.5% (actual)
    4. Market up 1%
    5. Market up 2%
    """

    # Load actual backtest results
    results = pd.read_csv('data/hold_to_expiration_results.csv')
    latest = results.iloc[-1]

    print('=' * 80)
    print('PRICE SENSITIVITY TEST (CALLS + PUTS)')
    print('=' * 80)

    # ASSERT: Verify we have both call and put directions
    assert 'call_direction' in latest.index, "Missing call_direction - not testing both sides!"
    assert 'put_direction' in latest.index, "Missing put_direction - not testing both sides!"

    print(f'\n⚠️  IMPORTANT: This tests a position with BOTH calls AND puts')
    print(f'   - We are NOT testing calls-only')
    print(f'   - We have simultaneous positions in calls and puts')

    print(f'\nActual Backtest Entry (BOTH SIDES):')
    print(f'  SPY entry: ${latest["spy_entry"]:.2f}')
    print(f'  SPX entry: ${latest["spx_entry"]:.2f}')
    print(f'  SPY strike: {int(latest["spy_strike"])}')
    print(f'  SPX strike: {int(latest["spx_strike"])}')
    print(f'  Entry credit: ${latest["credit_received"]:,.2f}')
    print(f'  Num spreads: {int(latest["num_spreads"])}')
    print(f'  Call direction: {latest["call_direction"]}')
    print(f'  Put direction: {latest["put_direction"]}')

    # Opening prices (for percentage calculations)
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    spy_data = underlying[underlying['symbol'] == 'SPY']
    spx_data = underlying[underlying['symbol'] == 'SPX']
    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    print(f'\nOpening Prices:')
    print(f'  SPY: ${spy_open:.2f}')
    print(f'  SPX: ${spx_open:.2f}')

    # Test different scenarios
    scenarios = [
        ('Down 1%', spy_open * 0.99, spx_open * 0.99),
        ('Flat', spy_open, spx_open),
        ('Up 0.5% (actual)', latest["spy_close"], latest["spx_close"]),
        ('Up 1%', spy_open * 1.01, spx_open * 1.01),
        ('Up 2%', spy_open * 1.02, spx_open * 1.02),
    ]

    print('\n' + '=' * 80)
    print('TESTING DIFFERENT ENDING PRICES (Perfect Tracking)')
    print('=' * 80)
    print(f'\n{"Scenario":<20} {"SPY Close":<12} {"SPX Close":<12} {"Settlement":<15} {"Net P&L":<15}')
    print('-' * 80)

    results_list = []

    for scenario_name, spy_close, spx_close in scenarios:
        settlement = calculate_expiration_value(
            spy_close, spx_close,
            int(latest['spy_strike']), int(latest['spx_strike']),
            int(latest['num_spreads']),
            latest['call_direction'],
            latest['put_direction']
        )

        net_pnl = latest['credit_received'] + settlement['total_net_settlement']

        print(f'{scenario_name:<20} ${spy_close:<11.2f} ${spx_close:<11.2f} '
              f'${settlement["total_net_settlement"]:<14,.2f} ${net_pnl:<14,.2f}')

        results_list.append({
            'scenario': scenario_name,
            'spy_close': spy_close,
            'spx_close': spx_close,
            'pnl': net_pnl
        })

    # Check if P&L is constant
    pnls = [r['pnl'] for r in results_list]
    pnl_range = max(pnls) - min(pnls)

    print('\n' + '=' * 80)
    print('ANALYSIS')
    print('=' * 80)
    print(f'\nP&L Range: ${pnl_range:,.2f} (from ${min(pnls):,.2f} to ${max(pnls):,.2f})')

    if pnl_range < 100:
        print('\n✅ Strategy is relatively PRICE AGNOSTIC (P&L varies by < $100)')
        print('   This means the strategy is market-neutral when SPY and SPX track perfectly')
    else:
        print(f'\n⚠️  Strategy has DIRECTIONAL EXPOSURE (P&L varies by ${pnl_range:,.2f})')
        print('   P&L changes based on ending price level')

        # Analyze the trend
        if pnls[0] < pnls[-1]:
            print('   → P&L INCREASES as market goes UP (bullish bias)')
        else:
            print('   → P&L DECREASES as market goes UP (bearish bias)')


    # Now test with IMPERFECT tracking
    print('\n' + '=' * 80)
    print('TESTING WITH IMPERFECT TRACKING (SPX outperforms SPY by 0.1%)')
    print('=' * 80)
    print(f'\n{"Scenario":<20} {"SPY Close":<12} {"SPX Close":<12} {"Settlement":<15} {"Net P&L":<15}')
    print('-' * 80)

    scenarios_imperfect = [
        ('Down 1% + skew', spy_open * 0.99, spx_open * 0.991),
        ('Flat + skew', spy_open, spx_open * 1.001),
        ('Up 0.5% + skew', spy_open * 1.005, spx_open * 1.006),
        ('Up 1% + skew', spy_open * 1.01, spx_open * 1.011),
        ('Up 2% + skew', spy_open * 1.02, spx_open * 1.021),
    ]

    results_imperfect = []

    for scenario_name, spy_close, spx_close in scenarios_imperfect:
        settlement = calculate_expiration_value(
            spy_close, spx_close,
            int(latest['spy_strike']), int(latest['spx_strike']),
            int(latest['num_spreads']),
            latest['call_direction'],
            latest['put_direction']
        )

        net_pnl = latest['credit_received'] + settlement['total_net_settlement']

        print(f'{scenario_name:<20} ${spy_close:<11.2f} ${spx_close:<11.2f} '
              f'${settlement["total_net_settlement"]:<14,.2f} ${net_pnl:<14,.2f}')

        results_imperfect.append({
            'scenario': scenario_name,
            'spy_close': spy_close,
            'spx_close': spx_close,
            'pnl': net_pnl
        })

    print('\n' + '=' * 80)
    print('KEY INSIGHT')
    print('=' * 80)
    print('\nThe strategy P&L depends on TWO factors:')
    print('  1. Absolute price level (if SPX/SPY contract ratio ≠ 10.0)')
    print('  2. Relative performance (SPX vs SPY tracking error)')
    print('\nWith our position:')
    print(f'  - Sell {int(latest["num_spreads"])} SPX, Buy {int(latest["num_spreads"])*10} SPY')
    print('  - If SPX outperforms SPY → we LOSE')
    print('  - If SPY outperforms SPX → we WIN')
    print('  - Perfect tracking → P&L depends on strike selection vs final price')


if __name__ == '__main__':
    test_different_ending_prices()
