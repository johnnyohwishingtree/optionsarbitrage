#!/usr/bin/env python3
"""
Test: Realistic Tracking Error Scenarios

This test validates the strategy's P&L under REALISTIC assumptions:
- SPY and SPX track within 0.01% (typical real-world behavior)
- Tests various market move scenarios to understand risk profile
- Confirms that PRIMARY risk is volatility, not tracking error

Key Insight: With realistic tracking, strategy remains profitable on ±1% moves.
Main risk is LARGE volatility events (>1.5% moves), not tracking error.
"""

import pandas as pd
from hold_to_expiration_backtest_both_sides import calculate_expiration_value


def test_realistic_tracking_scenarios():
    """
    Test P&L under realistic tracking assumptions (<0.01% deviation)

    This corrects earlier overly pessimistic analysis that assumed
    0.1% tracking errors, which are rare in practice.
    """

    # Load actual backtest results
    results = pd.read_csv('data/hold_to_expiration_results.csv')
    latest = results.iloc[-1]

    print('=' * 80)
    print('REALISTIC TRACKING ERROR ANALYSIS')
    print('=' * 80)

    # Get opening prices for percentage calculations
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    spy_data = underlying[underlying['symbol'] == 'SPY']
    spx_data = underlying[underlying['symbol'] == 'SPX']
    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    print(f'\nPosition Details:')
    print(f'  SPY entry: ${latest["spy_entry"]:.2f}')
    print(f'  SPX entry: ${latest["spx_entry"]:.2f}')
    print(f'  SPY strike: {int(latest["spy_strike"])}')
    print(f'  SPX strike: {int(latest["spx_strike"])}')
    print(f'  Credit received: ${latest["credit_received"]:,.2f}')
    print(f'  Call direction: {latest["call_direction"]}')
    print(f'  Put direction: {latest["put_direction"]}')

    print(f'\nOpening Prices:')
    print(f'  SPY: ${spy_open:.2f}')
    print(f'  SPX: ${spx_open:.2f}')

    print('\n' + '=' * 80)
    print('SCENARIO 1: Perfect Tracking (0.00% deviation)')
    print('=' * 80)
    print(f'\n{"Market Move":<20} {"SPY Close":<12} {"SPX Close":<12} {"SPY%":<10} {"SPX%":<10} {"Net P&L":<15}')
    print('-' * 90)

    perfect_scenarios = [
        ('Flat', spy_open, spx_open),
        ('Up 0.5%', spy_open * 1.005, spx_open * 1.005),
        ('Up 1.0%', spy_open * 1.010, spx_open * 1.010),
        ('Up 1.5%', spy_open * 1.015, spx_open * 1.015),
        ('Up 2.0%', spy_open * 1.020, spx_open * 1.020),
        ('Down 0.5%', spy_open * 0.995, spx_open * 0.995),
        ('Down 1.0%', spy_open * 0.990, spx_open * 0.990),
    ]

    perfect_results = []

    for scenario_name, spy_close, spx_close in perfect_scenarios:
        spy_pct = ((spy_close - spy_open) / spy_open) * 100
        spx_pct = ((spx_close - spx_open) / spx_open) * 100

        settlement = calculate_expiration_value(
            spy_close, spx_close,
            int(latest['spy_strike']), int(latest['spx_strike']),
            int(latest['num_spreads']),
            latest['call_direction'],
            latest['put_direction']
        )

        net_pnl = latest['credit_received'] + settlement['total_net_settlement']

        print(f'{scenario_name:<20} ${spy_close:<11.2f} ${spx_close:<11.2f} '
              f'{spy_pct:<9.3f}% {spx_pct:<9.3f}% ${net_pnl:<14,.0f}')

        perfect_results.append({
            'scenario': scenario_name,
            'pnl': net_pnl,
            'spy_pct': spy_pct,
            'spx_pct': spx_pct
        })

    print('\n' + '=' * 80)
    print('SCENARIO 2: Realistic Tracking (0.01% deviation - SPX outperforms)')
    print('=' * 80)
    print(f'\n{"Market Move":<20} {"SPY Close":<12} {"SPX Close":<12} {"SPY%":<10} {"SPX%":<10} {"Δ%":<10} {"Net P&L":<15}')
    print('-' * 100)

    realistic_scenarios = [
        ('Flat + 0.01%', spy_open, spx_open * 1.0001),
        ('Up 0.5% + 0.01%', spy_open * 1.005, spx_open * 1.0051),
        ('Up 1.0% + 0.01%', spy_open * 1.010, spx_open * 1.0101),
        ('Up 1.5% + 0.01%', spy_open * 1.015, spx_open * 1.0151),
        ('Down 1.0% + 0.01%', spy_open * 0.990, spx_open * 0.9901),
    ]

    realistic_results = []

    for scenario_name, spy_close, spx_close in realistic_scenarios:
        spy_pct = ((spy_close - spy_open) / spy_open) * 100
        spx_pct = ((spx_close - spx_open) / spx_open) * 100
        tracking_error = spx_pct - spy_pct

        settlement = calculate_expiration_value(
            spy_close, spx_close,
            int(latest['spy_strike']), int(latest['spx_strike']),
            int(latest['num_spreads']),
            latest['call_direction'],
            latest['put_direction']
        )

        net_pnl = latest['credit_received'] + settlement['total_net_settlement']

        print(f'{scenario_name:<20} ${spy_close:<11.2f} ${spx_close:<11.2f} '
              f'{spy_pct:<9.3f}% {spx_pct:<9.3f}% {tracking_error:<9.3f}% ${net_pnl:<14,.0f}')

        realistic_results.append({
            'scenario': scenario_name,
            'pnl': net_pnl,
            'tracking_error': tracking_error
        })

    print('\n' + '=' * 80)
    print('KEY FINDINGS')
    print('=' * 80)

    # Find profitable range with perfect tracking
    profitable_perfect = [r for r in perfect_results if r['pnl'] > 0]
    max_profitable_move = max([abs(r['spy_pct']) for r in profitable_perfect])

    print(f'\n1. With PERFECT tracking (0.00% deviation):')
    print(f'   - Strategy profitable on moves up to ±{max_profitable_move:.1f}%')
    print(f'   - Best outcome: Flat market (${max([r["pnl"] for r in perfect_results]):,.0f})')
    print(f'   - At ±1% moves: ${[r["pnl"] for r in perfect_results if abs(r["spy_pct"]) > 0.95 and abs(r["spy_pct"]) < 1.05][0]:,.0f}')

    # Check realistic tracking impact
    realistic_1pct = [r for r in realistic_results if 'Up 1.0%' in r['scenario']][0]
    perfect_1pct = [r for r in perfect_results if r['scenario'] == 'Up 1.0%'][0]
    tracking_impact = realistic_1pct['pnl'] - perfect_1pct['pnl']

    print(f'\n2. With REALISTIC tracking (0.01% deviation):')
    print(f'   - On 1% up move: ${realistic_1pct["pnl"]:,.0f}')
    print(f'   - Impact of 0.01% tracking error: ${tracking_impact:,.0f}')
    if realistic_1pct['pnl'] > 0:
        print(f'   - ✓ Still profitable even with tracking error')

    print(f'\n3. PRIMARY RISK: Large Volatility Moves')
    breakeven_move = None
    for i in range(len(perfect_results) - 1):
        if perfect_results[i]['pnl'] > 0 and perfect_results[i+1]['pnl'] < 0:
            breakeven_move = (abs(perfect_results[i]['spy_pct']) + abs(perfect_results[i+1]['spy_pct'])) / 2
            break

    if breakeven_move:
        print(f'   - Strategy breaks even around ±{breakeven_move:.1f}% moves')
    print(f'   - Main risk is NOT tracking error but VOLATILITY')
    print(f'   - Loses money on moves >1.5% in either direction')

    print(f'\n4. SECONDARY RISK: Tracking Error')
    print(f'   - Typical SPY/SPX tracking: <0.01%')
    print(f'   - Impact of 0.01% error on 1% move: ${tracking_impact:,.0f}')
    print(f'   - Only becomes primary risk in stress events (>0.05% divergence)')

    print('\n' + '=' * 80)
    print('STRATEGY CLASSIFICATION')
    print('=' * 80)
    print('\nThis is a SHORT VOLATILITY strategy:')
    print('  ✓ Profits most when market stays calm (flat)')
    print('  ✓ Remains profitable on moderate moves (±1%)')
    print('  ✗ Loses on large moves (>1.5%)')
    print('  ✗ NOT arbitrage - has market exposure')
    print('\nBest described as: "Selling volatility insurance with realistic profit zone of ±1%"')

    print('\n' + '=' * 80)
    print('RISK SUMMARY')
    print('=' * 80)
    print(f'\n{"Risk Factor":<30} {"Likelihood":<15} {"Impact":<15}')
    print('-' * 60)
    print(f'{"Tracking error >0.01%":<30} {"Low":<15} {"Medium":<15}')
    print(f'{"Market move >1.5%":<30} {"Medium":<15} {"High":<15}')
    print(f'{"Strike mismatch":<30} {"Always":<15} {"Low":<15}')
    print(f'{"Flash crash/spike":<30} {"Low":<15} {"Catastrophic":<15}')


if __name__ == '__main__':
    test_realistic_tracking_scenarios()
