#!/usr/bin/env python3
"""
Test for corrected worst-case calculation with lockstep movement.

This test verifies that:
1. SPY and SPX move together with the same percentage change (lockstep)
2. Worst case is the minimum P&L across the ±3% range
3. No incorrect divergence assumptions are made
"""

import pytest
import sys
import numpy as np
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')


def calculate_settlement_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)


def calculate_option_pnl(entry_price, exit_price, action, quantity):
    """Calculate P&L for an option position"""
    if action == 'BUY':
        return (exit_price - entry_price) * quantity * 100
    else:  # SELL
        return (entry_price - exit_price) * quantity * 100


def test_lockstep_worst_case_jan29():
    """
    Test worst-case calculation with Jan 29 data using lockstep movement.

    This should show profitable outcomes across the range, NOT -$400k losses.
    """
    # Jan 29 opening prices
    spy_opening = 696.39
    spx_opening = 6977.74

    # Strikes
    spy_strike = 696
    spx_strike = 6980

    # Option prices at market open
    spy_call_price = 1.97
    spx_call_price = 22.50
    spy_put_price = 1.71
    spx_put_price = 13.30

    # Strategy: Sell SPX Calls/Buy SPY Calls | Sell SPY Puts/Buy SPX Puts
    sell_spx_calls = 10
    buy_spy_calls = 100
    sell_spy_puts = 100
    buy_spx_puts = 10

    # Calculate initial credit
    call_credit = (spx_call_price * sell_spx_calls * 100) - (spy_call_price * buy_spy_calls * 100)
    put_credit = (spy_put_price * sell_spy_puts * 100) - (spx_put_price * buy_spx_puts * 100)
    total_credit = call_credit + put_credit

    assert total_credit == 6600.0, f"Expected credit $6,600, got ${total_credit:,.2f}"

    # Test lockstep movement across ±3% range
    pnl_results = []

    for pct_move in np.linspace(-0.03, 0.03, 100):
        # SPY and SPX move together (same percentage)
        spy_price = spy_opening * (1 + pct_move)
        spx_price = spx_opening * (1 + pct_move)

        # Calculate settlement values
        spy_call_settle = calculate_settlement_value(spy_price, spy_strike, 'C')
        spx_call_settle = calculate_settlement_value(spx_price, spx_strike, 'C')
        spy_put_settle = calculate_settlement_value(spy_price, spy_strike, 'P')
        spx_put_settle = calculate_settlement_value(spx_price, spx_strike, 'P')

        # Calculate P&L for calls
        call_pnl = calculate_option_pnl(spx_call_price, spx_call_settle, 'SELL', sell_spx_calls)
        call_pnl += calculate_option_pnl(spy_call_price, spy_call_settle, 'BUY', buy_spy_calls)

        # Calculate P&L for puts
        put_pnl = calculate_option_pnl(spy_put_price, spy_put_settle, 'SELL', sell_spy_puts)
        put_pnl += calculate_option_pnl(spx_put_price, spx_put_settle, 'BUY', buy_spx_puts)

        # Total P&L including credit
        total_pnl = total_credit + call_pnl + put_pnl

        pnl_results.append({
            'pct_move': pct_move * 100,
            'spy_price': spy_price,
            'spx_price': spx_price,
            'total_pnl': total_pnl
        })

    # Find worst and best case
    worst_pnl = min(r['total_pnl'] for r in pnl_results)
    best_pnl = max(r['total_pnl'] for r in pnl_results)

    print(f"\nLockstep Worst Case Test Results:")
    print(f"Initial Credit: ${total_credit:,.2f}")
    print(f"Worst Case P&L: ${worst_pnl:,.2f}")
    print(f"Best Case P&L:  ${best_pnl:,.2f}")
    print(f"P&L Range:      ${best_pnl - worst_pnl:,.2f}")

    # CRITICAL ASSERTIONS
    # With lockstep movement, worst case should be profitable (around +$19k)
    # NOT a huge loss like -$400k
    assert worst_pnl > 15000, f"Worst case should be >$15k profit, got ${worst_pnl:,.2f}"
    assert worst_pnl < 25000, f"Worst case should be <$25k profit, got ${worst_pnl:,.2f}"

    # Best case should also be profitable (around +$20k)
    assert best_pnl > 15000, f"Best case should be >$15k profit, got ${best_pnl:,.2f}"
    assert best_pnl < 25000, f"Best case should be <$25k profit, got ${best_pnl:,.2f}"

    # P&L range should be small (<$2k) since strikes are nearly matched
    pnl_range = best_pnl - worst_pnl
    assert pnl_range < 2000, f"P&L range should be <$2k with lockstep, got ${pnl_range:,.2f}"

    print(f"\n✅ All assertions passed!")
    print(f"   Strategy is profitable across entire ±3% range")
    print(f"   P&L variance is small (${pnl_range:,.2f}) due to lockstep movement")


def test_incorrect_divergence_assumption():
    """
    Show what happens with the INCORRECT divergence assumption.

    This should produce the -$400k result (which is wrong).
    """
    # Same setup as above
    spy_opening = 696.39
    spx_opening = 6977.74
    spy_strike = 696
    spx_strike = 6980

    spy_call_price = 1.97
    spx_call_price = 22.50
    spy_put_price = 1.71
    spx_put_price = 13.30

    sell_spx_calls = 10
    buy_spy_calls = 100
    sell_spy_puts = 100
    buy_spx_puts = 10

    call_credit = (spx_call_price * sell_spx_calls * 100) - (spy_call_price * buy_spy_calls * 100)
    put_credit = (spy_put_price * sell_spy_puts * 100) - (spx_put_price * buy_spx_puts * 100)
    total_credit = call_credit + put_credit

    # INCORRECT CALCULATION: Assume divergence
    # Calls: SPX up 3%, SPY calls worthless
    spx_up = spx_opening * 1.03
    spx_call_settle = calculate_settlement_value(spx_up, spx_strike, 'C')
    call_pnl_wrong = calculate_option_pnl(spx_call_price, spx_call_settle, 'SELL', sell_spx_calls)
    call_pnl_wrong += calculate_option_pnl(spy_call_price, 0, 'BUY', buy_spy_calls)

    # Puts: SPY down 3%, SPX puts worthless
    spy_down = spy_opening * 0.97
    spy_put_settle = calculate_settlement_value(spy_down, spy_strike, 'P')
    put_pnl_wrong = calculate_option_pnl(spy_put_price, spy_put_settle, 'SELL', sell_spy_puts)
    put_pnl_wrong += calculate_option_pnl(spx_put_price, 0, 'BUY', buy_spx_puts)

    wrong_worst_case = total_credit + call_pnl_wrong + put_pnl_wrong

    print(f"\nIncorrect Divergence Assumption:")
    print(f"Wrong Worst Case: ${wrong_worst_case:,.2f}")

    # This should be around -$400k (the bug)
    assert wrong_worst_case < -300000, f"Bug test: should show huge loss, got ${wrong_worst_case:,.2f}"

    print(f"✅ Confirmed: divergence assumption produces incorrect -${abs(wrong_worst_case):,.0f} result")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
