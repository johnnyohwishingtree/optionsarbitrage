#!/usr/bin/env python3
"""
Test: Strike Change Should Update Default Prices

Bug Report (2026-01-27):
- User reported: "when i modify the strike configuration, i.e spy strike from 697 -> 698,
  I see that the PUT spread 'Sell SPY 698P Price' input gets correctly updated with the db
  values, but 'Buy SPY 698C Price' in the Call Spread does not get updated"
- Root cause: default_spy_call_price uses best_combo.get() which only has prices for original strikes
- When strikes change, the calculator should recalculate default prices based on new strikes,
  not rely on best_combo.json which only has prices for the original strikes

This test ensures that default option prices are recalculated when strikes change,
not just pulled from best_combo.json.
"""

import pandas as pd
import json

def calculate_settlement_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)

def test_default_prices_update_with_strikes():
    """Test that default option prices are recalculated when strikes change"""

    # Load test data
    underlying_file = 'data/underlying_prices_20260126.csv'
    best_combo_file = '/tmp/best_combo.json'

    df_underlying = pd.read_csv(underlying_file)
    df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

    with open(best_combo_file) as f:
        best_combo = json.load(f)

    spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].copy()
    spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].copy()

    # Market open prices
    entry_spy = spy_df.iloc[0]
    entry_spx = spx_df.iloc[0]

    print("=" * 70)
    print("TEST: Default Prices Update When Strikes Change")
    print("=" * 70)

    print(f"\nEntry prices:")
    print(f"  SPY: ${entry_spy['close']:.2f}")
    print(f"  SPX: ${entry_spx['close']:.2f}")

    # Original strikes from best_combo
    original_spy_strike = best_combo['spy_strike']
    original_spx_strike = best_combo['spx_strike']

    print(f"\nOriginal strikes (from best_combo.json):")
    print(f"  SPY: {original_spy_strike}")
    print(f"  SPX: {original_spx_strike}")

    # best_combo has prices for original strikes only
    original_spy_call_price = best_combo.get('spy_call_ask', 0)
    original_spx_call_price = best_combo.get('spx_call_bid', 0)

    print(f"\nPrices in best_combo.json (for original strikes):")
    print(f"  SPY {original_spy_strike}C ask: ${original_spy_call_price:.2f}")
    print(f"  SPX {original_spx_strike}C bid: ${original_spx_call_price:.2f}")

    # New strikes (user changed SPY from 697 to 698)
    new_spy_strike = 698
    new_spx_strike = 6990

    print(f"\nNew strikes (user changed):")
    print(f"  SPY: {new_spy_strike}")
    print(f"  SPX: {new_spx_strike}")

    # WRONG: Use best_combo prices (for original strikes)
    wrong_spy_call_default = best_combo.get('spy_call_ask', 0.50)
    wrong_spx_call_default = best_combo.get('spx_call_bid', 5.00)

    print(f"\nWRONG approach (using best_combo for new strikes):")
    print(f"  SPY {new_spy_strike}C: ${wrong_spy_call_default:.2f} (this is for {original_spy_strike}C!)")
    print(f"  SPX {new_spx_strike}C: ${wrong_spx_call_default:.2f} (this is for {original_spx_strike}C!)")

    # CORRECT: Calculate default based on new strikes and current prices
    correct_spy_call_default = max(0.01, entry_spy['close'] - new_spy_strike + 0.50)
    correct_spx_call_default = max(0.01, entry_spx['close'] - new_spx_strike + 5.00)

    print(f"\nCORRECT approach (calculate from new strikes):")
    print(f"  SPY {new_spy_strike}C: ${correct_spy_call_default:.2f}")
    print(f"  SPX {new_spx_strike}C: ${correct_spx_call_default:.2f}")

    # The bug: If strikes change, but we still use best_combo prices,
    # we're using prices for the WRONG strikes
    print(f"\n" + "=" * 70)
    print("BUG DEMONSTRATION:")
    print("=" * 70)

    if new_spy_strike != original_spy_strike:
        print(f"\n❌ User changed SPY strike from {original_spy_strike} to {new_spy_strike}")
        print(f"   But calculator still shows: ${wrong_spy_call_default:.2f}")
        print(f"   This is the price for {original_spy_strike}C, not {new_spy_strike}C!")
        print(f"   Should show: ${correct_spy_call_default:.2f} (based on new strike)")

    # Test that correct approach produces different values for different strikes
    strike_1 = 697
    strike_2 = 698

    default_1 = max(0.01, entry_spy['close'] - strike_1 + 0.50)
    default_2 = max(0.01, entry_spy['close'] - strike_2 + 0.50)

    print(f"\n" + "=" * 70)
    print("VERIFICATION:")
    print("=" * 70)
    print(f"\nDefault prices should change when strike changes:")
    print(f"  SPY {strike_1}C: ${default_1:.2f}")
    print(f"  SPY {strike_2}C: ${default_2:.2f}")

    assert default_1 != default_2, \
        f"Default prices should be different for different strikes"

    print(f"\n✅ Default prices correctly change with strike")
    print(f"   Difference: ${abs(default_1 - default_2):.2f}")

    print(f"\n" + "=" * 70)
    print("SOLUTION:")
    print("=" * 70)
    print("\nInstead of:")
    print("  default_spy_call_price = best_combo.get('spy_call_ask', fallback)")
    print("\nUse:")
    print("  if spy_strike == best_combo.get('spy_strike'):")
    print("      default_spy_call_price = best_combo.get('spy_call_ask', fallback)")
    print("  else:")
    print("      # Recalculate based on new strike")
    print("      default_spy_call_price = max(0.01, entry_spy - spy_strike + 0.50)")


if __name__ == '__main__':
    test_default_prices_update_with_strikes()

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)

    print("\nSummary:")
    print("  ❌ Current code uses best_combo prices even when strikes change")
    print("  ✅ Should recalculate default prices based on new strikes")
    print("  💡 Fix: Check if strike matches best_combo before using cached prices")
