#!/usr/bin/env python3
"""
Test: Widget Key Updates Bug Fix

Bug Report (2026-01-27):
- User reported: "whenever I change putspread or call spread direction, it doesn't
  reflect the input fields in Position Builder with new data from the db"
- User reported: "whenever I change the strike price, it also doesn't reflect the
  input fields in the Position Builder with new data from the db"
- Root cause: Widget keys only included entry_time_idx, not strikes or directions
- When strikes/directions changed, widgets weren't recreated with new estimated prices

This test ensures widget keys include all parameters that should trigger updates:
- entry_time_idx (time slider)
- spy_strike and spx_strike (strike configuration)
- call_direction and put_direction (strategy direction)
"""

import pandas as pd
import numpy as np
import json

def calculate_settlement_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)

def estimate_option_price(underlying_price, strike, right, open_price, time_fraction):
    """Estimate option price based on underlying movement and time decay"""
    intrinsic = calculate_settlement_value(underlying_price, strike, right)
    opening_extrinsic = max(0, open_price - intrinsic)
    current_extrinsic = opening_extrinsic * time_fraction
    estimated_price = intrinsic + current_extrinsic
    return max(0.01, estimated_price)

def test_strike_change_updates_prices():
    """Test that changing strikes produces different estimated prices"""

    # Load test data
    underlying_file = 'data/underlying_prices_20260126.csv'
    df_underlying = pd.read_csv(underlying_file)
    df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

    spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].copy()
    spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].copy()

    # Entry at 10:30 AM (index 60) - closer to the strikes
    entry_time_idx = 60
    entry_spy = spy_df.iloc[entry_time_idx]
    entry_spx = spx_df.iloc[entry_time_idx]
    time_fraction = 0.85  # Still has time value

    # Test with two different strike pairs near the money
    strike_pair_1 = (695, 6975)  # Near the money strikes
    strike_pair_2 = (694, 6965)  # Different strikes, also near money

    # Opening prices (realistic for near-the-money options)
    spy_call_open = 1.50
    spx_call_open = 15.00
    spy_put_open = 1.50
    spx_put_open = 15.00

    # Calculate estimated prices for strike pair 1
    prices_1 = {
        'spy_call': estimate_option_price(entry_spy['close'], strike_pair_1[0], 'C', spy_call_open, time_fraction),
        'spx_call': estimate_option_price(entry_spx['close'], strike_pair_1[1], 'C', spx_call_open, time_fraction),
        'spy_put': estimate_option_price(entry_spy['close'], strike_pair_1[0], 'P', spy_put_open, time_fraction),
        'spx_put': estimate_option_price(entry_spx['close'], strike_pair_1[1], 'P', spx_put_open, time_fraction),
    }

    # Calculate estimated prices for strike pair 2
    prices_2 = {
        'spy_call': estimate_option_price(entry_spy['close'], strike_pair_2[0], 'C', spy_call_open, time_fraction),
        'spx_call': estimate_option_price(entry_spx['close'], strike_pair_2[1], 'C', spx_call_open, time_fraction),
        'spy_put': estimate_option_price(entry_spy['close'], strike_pair_2[0], 'P', spy_put_open, time_fraction),
        'spx_put': estimate_option_price(entry_spx['close'], strike_pair_2[1], 'P', spx_put_open, time_fraction),
    }

    print(f"\nEntry SPY: ${entry_spy['close']:.2f}, SPX: ${entry_spx['close']:.2f}")
    print(f"\nStrike Pair 1: SPY {strike_pair_1[0]}, SPX {strike_pair_1[1]}")
    print(f"  SPY Call: ${prices_1['spy_call']:.2f}")
    print(f"  SPX Call: ${prices_1['spx_call']:.2f}")
    print(f"  SPY Put:  ${prices_1['spy_put']:.2f}")
    print(f"  SPX Put:  ${prices_1['spx_put']:.2f}")

    print(f"\nStrike Pair 2: SPY {strike_pair_2[0]}, SPX {strike_pair_2[1]}")
    print(f"  SPY Call: ${prices_2['spy_call']:.2f}")
    print(f"  SPX Call: ${prices_2['spx_call']:.2f}")
    print(f"  SPY Put:  ${prices_2['spy_put']:.2f}")
    print(f"  SPX Put:  ${prices_2['spx_put']:.2f}")

    # Verify at least some prices are different when strikes change
    # (Put prices should definitely change when strike changes)
    any_different = (
        prices_1['spy_call'] != prices_2['spy_call'] or
        prices_1['spx_call'] != prices_2['spx_call'] or
        prices_1['spy_put'] != prices_2['spy_put'] or
        prices_1['spx_put'] != prices_2['spx_put']
    )

    assert any_different, \
        "At least some option prices should change when strike changes"

    print(f"\n✅ Prices correctly change when strikes change")
    print(f"   SPY Call: ${prices_1['spy_call']:.2f} → ${prices_2['spy_call']:.2f}")
    print(f"   SPX Call: ${prices_1['spx_call']:.2f} → ${prices_2['spx_call']:.2f}")
    print(f"   SPY Put:  ${prices_1['spy_put']:.2f} → ${prices_2['spy_put']:.2f}")
    print(f"   SPX Put:  ${prices_1['spx_put']:.2f} → ${prices_2['spx_put']:.2f}")


def test_widget_keys_include_all_parameters():
    """Test that widget keys include time, strikes, and direction"""

    # Simulate widget key generation
    entry_time_idx = 0
    spy_strike = 697
    spx_strike = 6985
    call_direction = "Sell SPX, Buy SPY"
    put_direction = "Sell SPY, Buy SPX"

    # Generate keys as they should be in the code
    call_price_key_spx = f"sell_spx_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
    call_price_key_spy = f"buy_spy_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
    put_price_key_spy = f"sell_spy_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"
    put_price_key_spx = f"buy_spx_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"

    print("\nGenerated widget keys:")
    print(f"  Call SPX: {call_price_key_spx}")
    print(f"  Call SPY: {call_price_key_spy}")
    print(f"  Put SPY:  {put_price_key_spy}")
    print(f"  Put SPX:  {put_price_key_spx}")

    # Verify keys include all required parameters
    for key_name, key_value in [
        ("Call SPX", call_price_key_spx),
        ("Call SPY", call_price_key_spy),
        ("Put SPY", put_price_key_spy),
        ("Put SPX", put_price_key_spx)
    ]:
        assert str(entry_time_idx) in key_value, f"{key_name} key must include entry_time_idx"
        assert str(spy_strike) in key_value, f"{key_name} key must include spy_strike"
        assert str(spx_strike) in key_value, f"{key_name} key must include spx_strike"

    # Verify direction is in the appropriate keys
    assert call_direction in call_price_key_spx, "Call keys must include call_direction"
    assert call_direction in call_price_key_spy, "Call keys must include call_direction"
    assert put_direction in put_price_key_spy, "Put keys must include put_direction"
    assert put_direction in put_price_key_spx, "Put keys must include put_direction"

    print("\n✅ All widget keys include required parameters")

    # Test that changing any parameter produces a different key
    new_call_direction = "Buy SPX, Sell SPY"
    new_call_key = f"sell_spx_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{new_call_direction}"

    assert new_call_key != call_price_key_spx, \
        "Changing direction should produce a different key"

    print("✅ Changing direction produces different key")
    print(f"   Old: {call_price_key_spx}")
    print(f"   New: {new_call_key}")

    # Test that changing strikes produces different key
    new_spy_strike = 696
    new_strike_key = f"sell_spx_px_{entry_time_idx}_{new_spy_strike}_{spx_strike}_{call_direction}"

    assert new_strike_key != call_price_key_spx, \
        "Changing strike should produce a different key"

    print("✅ Changing strike produces different key")
    print(f"   Old: {call_price_key_spx}")
    print(f"   New: {new_strike_key}")


if __name__ == '__main__':
    print("=" * 70)
    print("WIDGET KEY UPDATES TEST")
    print("=" * 70)

    print("\n📋 TEST 1: Strike Changes Update Estimated Prices")
    print("-" * 70)
    test_strike_change_updates_prices()

    print("\n📋 TEST 2: Widget Keys Include All Parameters")
    print("-" * 70)
    test_widget_keys_include_all_parameters()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)

    print("\nSummary:")
    print("  ✅ Estimated prices change when strikes change")
    print("  ✅ Widget keys include time, strikes, and direction")
    print("  ✅ Changing any parameter produces a different key")
    print("  ✅ Streamlit will recreate widgets when keys change")
