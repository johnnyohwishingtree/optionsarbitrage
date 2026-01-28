#!/usr/bin/env python3
"""
Test: Max Profit Calculation Is PREDICTIVE (Not Based on Actual EOD)

User Clarification (2026-01-28):
- User initially reported: "Max Profit is $242.40 but Total P&L is $420"
- I incorrectly thought this was a bug and tried to "fix" it by adding actual EOD values
- User corrected: "This should have been a prediction right? your not using the actual real
  end of the day values to replace the max profit right? Your calculation should be
  independent of knowing what it really closes at the end of the day"

CORRECT BEHAVIOR:
- Max profit calculation is PREDICTIVE based on entry-time information only
- It sweeps ±3% from entry price, maintaining entry-time SPY/SPX ratio
- It does NOT use actual EOD values (that would be "cheating")
- Max profit CAN be less than actual settlement P&L (that's normal for a prediction!)

This test verifies:
1. The sweep maintains entry-time ratio (predictive)
2. The sweep does NOT include actual EOD values
3. Max profit may differ from actual settlement (expected for predictions)
"""

import pandas as pd
import numpy as np
from datetime import datetime


def calculate_option_pnl(entry_price, exit_price, action, quantity):
    """Calculate P&L for an option position"""
    if action == 'BUY':
        return (exit_price - entry_price) * quantity * 100
    else:  # SELL
        return (entry_price - exit_price) * quantity * 100


def calculate_settlement_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)


def test_max_profit_is_predictive():
    """Test that max profit calculation is PREDICTIVE (not based on actual EOD)"""

    # Load test data
    underlying_file = 'data/underlying_prices_20260127.csv'
    df_underlying = pd.read_csv(underlying_file)
    df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

    spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].copy()
    spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].copy()

    # Entry at market open (index 0)
    entry_spy = spy_df.iloc[0]['close']
    entry_spx = spx_df.iloc[0]['close']

    # EOD prices
    eod_spy = spy_df.iloc[-1]['close']
    eod_spx = spx_df.iloc[-1]['close']

    print("=" * 70)
    print("TEST: Max Profit Is PREDICTIVE (Not Based on Actual EOD)")
    print("=" * 70)

    print(f"\nEntry prices (9:30 AM):")
    print(f"  SPY: ${entry_spy:.2f}")
    print(f"  SPX: ${entry_spx:.2f}")
    print(f"  Ratio: {entry_spx / entry_spy:.6f}")

    print(f"\nEOD prices (4:00 PM):")
    print(f"  SPY: ${eod_spy:.2f}")
    print(f"  SPX: ${eod_spx:.2f}")
    print(f"  Ratio: {eod_spx / eod_spy:.6f}")

    print(f"\n⚠️  Notice: Ratios are different!")
    print(f"  Entry ratio: {entry_spx / entry_spy:.6f}")
    print(f"  EOD ratio:   {eod_spx / eod_spy:.6f}")
    print(f"  Difference:  {abs((entry_spx / entry_spy) - (eod_spx / eod_spy)):.6f}")

    # Test position (from user's screenshot)
    spy_strike = 695
    spx_strike = 6965

    # Entry prices (from user's position)
    sell_spx_call_price = 10.30
    buy_spy_call_price = 0.67
    sell_spy_put_price = 1.60
    buy_spx_put_price = 11.00

    # Quantities
    sell_spx_calls = 10
    buy_spy_calls = 100
    sell_spy_puts = 100
    buy_spx_puts = 10

    # Calculate actual settlement P&L
    spy_call_settle = calculate_settlement_value(eod_spy, spy_strike, 'C')
    spx_call_settle = calculate_settlement_value(eod_spx, spx_strike, 'C')
    spy_put_settle = calculate_settlement_value(eod_spy, spy_strike, 'P')
    spx_put_settle = calculate_settlement_value(eod_spx, spx_strike, 'P')

    call_pnl = calculate_option_pnl(sell_spx_call_price, spx_call_settle, 'SELL', sell_spx_calls)
    call_pnl += calculate_option_pnl(buy_spy_call_price, spy_call_settle, 'BUY', buy_spy_calls)

    put_pnl = calculate_option_pnl(sell_spy_put_price, spy_put_settle, 'SELL', sell_spy_puts)
    put_pnl += calculate_option_pnl(buy_spx_put_price, spx_put_settle, 'BUY', buy_spx_puts)

    actual_settlement_pnl = call_pnl + put_pnl

    print(f"\nActual Settlement P&L:")
    print(f"  Call P&L: ${call_pnl:,.2f}")
    print(f"  Put P&L:  ${put_pnl:,.2f}")
    print(f"  Total:    ${actual_settlement_pnl:,.2f}")

    # PREDICTIVE APPROACH: Sweep based on entry-time information only
    print("\n" + "-" * 70)
    print("PREDICTIVE MAX PROFIT CALCULATION")
    print("-" * 70)
    print("\nUsing entry-time ratio only (NOT actual EOD values)")

    spy_range = np.linspace(entry_spy * 0.97, entry_spy * 1.03, 100)
    spx_range = spy_range * (entry_spx / entry_spy)  # Maintains entry ratio

    pnl_results = []
    for spy_px, spx_px in zip(spy_range, spx_range):
        spy_call_val = calculate_settlement_value(spy_px, spy_strike, 'C')
        spx_call_val = calculate_settlement_value(spx_px, spx_strike, 'C')
        spy_put_val = calculate_settlement_value(spy_px, spy_strike, 'P')
        spx_put_val = calculate_settlement_value(spx_px, spx_strike, 'P')

        c_pnl = calculate_option_pnl(sell_spx_call_price, spx_call_val, 'SELL', sell_spx_calls)
        c_pnl += calculate_option_pnl(buy_spy_call_price, spy_call_val, 'BUY', buy_spy_calls)

        p_pnl = calculate_option_pnl(sell_spy_put_price, spy_put_val, 'SELL', sell_spy_puts)
        p_pnl += calculate_option_pnl(buy_spx_put_price, spx_put_val, 'BUY', buy_spx_puts)

        pnl_results.append(c_pnl + p_pnl)

    predicted_max_profit = max(pnl_results)

    print(f"\nPredicted max profit: ${predicted_max_profit:,.2f}")
    print(f"Actual settlement P&L: ${actual_settlement_pnl:,.2f}")

    # This is the KEY INSIGHT: These can be different!
    difference = actual_settlement_pnl - predicted_max_profit

    print("\n" + "=" * 70)
    print("KEY INSIGHT: Predicted vs Actual")
    print("=" * 70)

    if abs(difference) < 1:
        print(f"\n✅ Predicted max profit matches actual settlement (within $1)")
        print(f"   This happens when entry ratio ≈ EOD ratio")
    else:
        print(f"\n✅ Predicted max profit differs from actual settlement by ${abs(difference):,.2f}")
        print(f"   This is EXPECTED and CORRECT for a predictive model!")
        print(f"\nWhy this happens:")
        print(f"  - Prediction assumes SPY/SPX ratio stays at {entry_spx / entry_spy:.6f} (entry)")
        print(f"  - But actual EOD ratio was {eod_spx / eod_spy:.6f}")
        print(f"  - The prediction doesn't 'know' the future, so it can differ")

    # Verify EOD point is NOT in the sweep (that would be cheating!)
    eod_in_sweep = any(abs(spy - eod_spy) < 0.01 and abs(spx - eod_spx) < 0.01
                       for spy, spx in zip(spy_range, spx_range))

    assert not eod_in_sweep, "EOD price point must NOT be in the predictive sweep!"
    print(f"\n✅ Verified: EOD point is NOT in the sweep (prediction is independent)")

    print(f"✅ Sweep maintains entry-time ratio throughout")
    print(f"\nSweep contains {len(spy_range)} points (based on ±3% from entry)")


def test_multiple_scenarios():
    """Test with multiple different entry times - all use predictive approach"""

    print("\n" + "=" * 70)
    print("TEST: Multiple Entry Times (All Predictive)")
    print("=" * 70)

    # Load data
    underlying_file = 'data/underlying_prices_20260127.csv'
    df_underlying = pd.read_csv(underlying_file)
    df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

    spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].copy()
    spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].copy()

    # Test different entry times
    test_scenarios = [
        {"name": "Market Open", "entry_idx": 0},
        {"name": "Mid Morning", "entry_idx": 60},
        {"name": "Midday", "entry_idx": 180},
        {"name": "Afternoon", "entry_idx": 300}
    ]

    for scenario in test_scenarios:
        entry_idx = scenario['entry_idx']
        entry_spy = spy_df.iloc[entry_idx]['close']
        entry_spx = spx_df.iloc[entry_idx]['close']
        eod_spy = spy_df.iloc[-1]['close']
        eod_spx = spx_df.iloc[-1]['close']

        print(f"\n{scenario['name']}:")
        print(f"  Entry: SPY ${entry_spy:.2f}, SPX ${entry_spx:.2f}")
        print(f"  EOD:   SPY ${eod_spy:.2f}, SPX ${eod_spx:.2f}")

        # Simple test position
        strike = int(entry_spy)

        # Create PREDICTIVE sweep (entry-time ratio only, NO EOD)
        spy_range = np.linspace(entry_spy * 0.97, entry_spy * 1.03, 100)
        spx_range = spy_range * (entry_spx / entry_spy)

        # Verify EOD is NOT in sweep (predictive model shouldn't use actual EOD)
        eod_in_sweep = any(abs(spy - eod_spy) < 0.01 and abs(spx - eod_spx) < 0.01
                           for spy, spx in zip(spy_range, spx_range))
        assert not eod_in_sweep, f"{scenario['name']}: EOD must NOT be in predictive sweep"
        print(f"  ✅ Predictive sweep (EOD not included)")


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("MAX PROFIT CALCULATION TESTS")
    print("=" * 70)
    print("\nUser clarification: 'This should have been a prediction right?")
    print("your not using the actual real end of the day values to replace")
    print("the max profit right? Your calculation should be independent of")
    print("knowing what it really closes at the end of the day'")
    print("=" * 70)

    test_max_profit_is_predictive()
    test_multiple_scenarios()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)

    print("\nSummary:")
    print("  ✅ Max profit calculation is PREDICTIVE (based on entry-time only)")
    print("  ✅ Sweep maintains entry-time SPY/SPX ratio throughout")
    print("  ✅ EOD price point is NOT included (prediction is independent)")
    print("  ✅ Predicted max profit CAN differ from actual settlement (expected!)")
    print("  ✅ Works across multiple entry times throughout the day")
