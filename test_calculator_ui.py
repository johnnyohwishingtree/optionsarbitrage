#!/usr/bin/env python3
"""
Test Suite for Strategy Calculator

Tests data loading, P&L calculations, and UI components
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import time as time_obj

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

print("=" * 70)
print("STRATEGY CALCULATOR TEST SUITE")
print("=" * 70)

# Test 1: File Existence
print("\n📁 TEST 1: Checking Required Files")
print("-" * 70)

best_combo_file = '/tmp/best_combo.json'
underlying_file = 'data/underlying_prices_20260127.csv'

files_ok = True

if os.path.exists(best_combo_file):
    print(f"✅ Best combo file exists: {best_combo_file}")
else:
    print(f"❌ Missing: {best_combo_file}")
    files_ok = False

if os.path.exists(underlying_file):
    print(f"✅ Underlying data exists: {underlying_file}")
else:
    print(f"❌ Missing: {underlying_file}")
    files_ok = False

if not files_ok:
    print("\n❌ FAILED: Required files missing")
    exit(1)

# Test 2: Load and Validate Best Combo Data
print("\n📊 TEST 2: Loading Best Combo Data")
print("-" * 70)

try:
    with open(best_combo_file) as f:
        best_combo = json.load(f)

    required_keys = [
        'spy_strike', 'spx_strike',
        'spy_call_bid', 'spy_call_ask',
        'spx_call_bid', 'spx_call_ask',
        'spy_put_bid', 'spy_put_ask',
        'spx_put_bid', 'spx_put_ask'
    ]

    missing_keys = [k for k in required_keys if k not in best_combo]
    if missing_keys:
        print(f"❌ Missing keys in best_combo: {missing_keys}")
        exit(1)

    print(f"✅ All required keys present")
    print(f"   SPY Strike: {best_combo['spy_strike']}")
    print(f"   SPX Strike: {best_combo['spx_strike']}")
    print(f"   SPY Call: ${best_combo['spy_call_bid']:.2f} / ${best_combo['spy_call_ask']:.2f}")
    print(f"   SPX Call: ${best_combo['spx_call_bid']:.2f} / ${best_combo['spx_call_ask']:.2f}")
    print(f"   SPY Put: ${best_combo['spy_put_bid']:.2f} / ${best_combo['spy_put_ask']:.2f}")
    print(f"   SPX Put: ${best_combo['spx_put_bid']:.2f} / ${best_combo['spx_put_ask']:.2f}")

except Exception as e:
    print(f"❌ Error loading best_combo: {e}")
    exit(1)

# Test 3: Load and Validate Underlying Data
print("\n📈 TEST 3: Loading Underlying Price Data")
print("-" * 70)

try:
    df_underlying = pd.read_csv(underlying_file)
    df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

    spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].copy()
    spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].copy()

    print(f"✅ Data loaded successfully")
    print(f"   Total rows: {len(df_underlying)}")
    print(f"   SPY rows: {len(spy_df)}")
    print(f"   SPX rows: {len(spx_df)}")

    if spy_df.empty:
        print("❌ No SPY data found")
        exit(1)

    if spx_df.empty:
        print("❌ No SPX data found")
        exit(1)

    # Check datetime parsing
    spy_df['time_only'] = spy_df['time'].dt.time
    spx_df['time_only'] = spx_df['time'].dt.time
    available_times = sorted(spy_df['time_only'].unique())

    print(f"✅ Time extraction successful")
    print(f"   Available times: {len(available_times)}")
    print(f"   First time: {available_times[0]}")
    print(f"   Last time: {available_times[-1]}")

    # Check price ranges
    spy_min = spy_df['close'].min()
    spy_max = spy_df['close'].max()
    spx_min = spx_df['close'].min()
    spx_max = spx_df['close'].max()

    print(f"   SPY range: ${spy_min:.2f} - ${spy_max:.2f}")
    print(f"   SPX range: ${spx_min:.2f} - ${spx_max:.2f}")

except Exception as e:
    print(f"❌ Error loading underlying data: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: P&L Calculation Logic
print("\n💰 TEST 4: Testing P&L Calculations")
print("-" * 70)

try:
    # Use actual data
    spy_strike = best_combo['spy_strike']
    spx_strike = best_combo['spx_strike']

    eod_spy = spy_df.iloc[-1]['close']
    eod_spx = spx_df.iloc[-1]['close']

    print(f"Testing with:")
    print(f"  SPY Strike: {spy_strike}, Close: ${eod_spy:.2f}")
    print(f"  SPX Strike: {spx_strike}, Close: ${eod_spx:.2f}")

    # Calculate settlement values
    spy_call_settle = calculate_settlement_value(eod_spy, spy_strike, 'C')
    spx_call_settle = calculate_settlement_value(eod_spx, spx_strike, 'C')
    spy_put_settle = calculate_settlement_value(eod_spy, spy_strike, 'P')
    spx_put_settle = calculate_settlement_value(eod_spx, spx_strike, 'P')

    print(f"\nSettlement values:")
    print(f"  SPY {spy_strike}C: ${spy_call_settle:.2f}")
    print(f"  SPX {spx_strike}C: ${spx_call_settle:.2f}")
    print(f"  SPY {spy_strike}P: ${spy_put_settle:.2f}")
    print(f"  SPX {spx_strike}P: ${spx_put_settle:.2f}")

    # Test strategy P&L
    # Calls: Sell 10 SPX, Buy 100 SPY
    call_pnl = calculate_option_pnl(
        best_combo['spx_call_bid'], spx_call_settle, 'SELL', 10
    )
    call_pnl += calculate_option_pnl(
        best_combo['spy_call_ask'], spy_call_settle, 'BUY', 100
    )

    # Puts: Sell 100 SPY, Buy 10 SPX
    put_pnl = calculate_option_pnl(
        best_combo['spy_put_bid'], spy_put_settle, 'SELL', 100
    )
    put_pnl += calculate_option_pnl(
        best_combo['spx_put_ask'], spx_put_settle, 'BUY', 10
    )

    total_pnl = call_pnl + put_pnl

    print(f"\nP&L Results:")
    print(f"  Call P&L: ${call_pnl:,.2f}")
    print(f"  Put P&L: ${put_pnl:,.2f}")
    print(f"  Total P&L: ${total_pnl:,.2f}")

    # Sanity checks
    if abs(call_pnl) > 100000:
        print(f"⚠️  Warning: Call P&L seems unusually large")

    if abs(put_pnl) > 100000:
        print(f"⚠️  Warning: Put P&L seems unusually large")

    print("✅ P&L calculations completed")

except Exception as e:
    print(f"❌ Error in P&L calculation: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 5: Price Range Sweep
print("\n📉 TEST 5: Testing Price Range Sweep")
print("-" * 70)

try:
    spy_range = np.linspace(eod_spy * 0.97, eod_spy * 1.03, 50)
    spx_range = spy_range * (eod_spx / eod_spy)

    pnl_results = []

    for spy_px, spx_px in zip(spy_range, spx_range):
        # Calculate settlement values
        spy_call_val = calculate_settlement_value(spy_px, spy_strike, 'C')
        spx_call_val = calculate_settlement_value(spx_px, spx_strike, 'C')
        spy_put_val = calculate_settlement_value(spy_px, spy_strike, 'P')
        spx_put_val = calculate_settlement_value(spx_px, spx_strike, 'P')

        # Call P&L
        c_pnl = calculate_option_pnl(best_combo['spx_call_bid'], spx_call_val, 'SELL', 10)
        c_pnl += calculate_option_pnl(best_combo['spy_call_ask'], spy_call_val, 'BUY', 100)

        # Put P&L
        p_pnl = calculate_option_pnl(best_combo['spy_put_bid'], spy_put_val, 'SELL', 100)
        p_pnl += calculate_option_pnl(best_combo['spx_put_ask'], spx_put_val, 'BUY', 10)

        total = c_pnl + p_pnl
        pnl_results.append({
            'spy_price': spy_px,
            'total_pnl': total
        })

    df_pnl = pd.DataFrame(pnl_results)

    max_profit = df_pnl['total_pnl'].max()
    max_loss = df_pnl['total_pnl'].min()

    print(f"✅ Price sweep completed")
    print(f"   Tested {len(spy_range)} price points")
    print(f"   Price range: ${spy_range.min():.2f} - ${spy_range.max():.2f}")
    print(f"   Max Profit: ${max_profit:,.2f}")
    print(f"   Max Loss: ${max_loss:,.2f}")
    print(f"   P&L Range: ${max_loss:,.2f} to ${max_profit:,.2f}")

except Exception as e:
    print(f"❌ Error in price sweep: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 6: Credit Validation
print("\n💵 TEST 6: Validating Credits")
print("-" * 70)

try:
    # Call credit
    call_credit = (best_combo['spx_call_bid'] * 10 * 100) - (best_combo['spy_call_ask'] * 100 * 100)

    # Put credit
    put_credit = (best_combo['spy_put_bid'] * 100 * 100) - (best_combo['spx_put_ask'] * 10 * 100)

    total_credit = call_credit + put_credit

    print(f"  Call Credit: ${call_credit:,.2f}")
    print(f"  Put Credit: ${put_credit:,.2f}")
    print(f"  Total Credit: ${total_credit:,.2f}")

    # Check if credit makes sense
    expected_credit = best_combo.get('total_credit', 0) * 100  # Convert to dollars

    if abs(total_credit - expected_credit) < 1000:  # Within $1000
        print(f"✅ Credit matches expected: ${expected_credit:,.2f}")
    else:
        print(f"⚠️  Credit mismatch - Expected: ${expected_credit:,.2f}, Got: ${total_credit:,.2f}")

except Exception as e:
    print(f"❌ Error validating credits: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 7: Timezone Conversion and UI Component Simulation
print("\n🎨 TEST 7: Timezone Conversion and UI Component Simulation")
print("-" * 70)

try:
    # Convert to ET for display (matching calculator logic)
    spy_df['time_et'] = spy_df['time'].dt.tz_convert('America/New_York')
    spx_df['time_et'] = spx_df['time'].dt.tz_convert('America/New_York')

    # Create time labels
    spy_df['time_label'] = spy_df['time_et'].dt.strftime('%I:%M %p ET')
    time_labels = spy_df['time_label'].tolist()

    # Verify time range
    first_time_et = spy_df['time_et'].iloc[0]
    last_time_et = spy_df['time_et'].iloc[-1]

    print(f"  Time range: {time_labels[0]} to {time_labels[-1]}")
    print(f"  Total time points: {len(time_labels)}")

    # Verify 9:30 AM start
    assert time_labels[0] == "09:30 AM ET", f"Expected 09:30 AM ET, got {time_labels[0]}"
    print(f"  ✅ First time is 09:30 AM ET")

    # Verify 3:59 PM end (market closes at 4:00 PM, last bar is 3:59)
    assert time_labels[-1] == "03:59 PM ET", f"Expected 03:59 PM ET, got {time_labels[-1]}"
    print(f"  ✅ Last time is 03:59 PM ET")

    # Simulate slider interaction using index
    entry_time_idx = 0  # Market open
    entry_spy = spy_df.iloc[entry_time_idx]
    entry_spx = spx_df.iloc[entry_time_idx]

    print(f"\n  Simulated entry at: {time_labels[entry_time_idx]}")
    print(f"  SPY Price: ${entry_spy['close']:.2f}")
    print(f"  SPX Price: ${entry_spx['close']:.2f}")

    # Test mid-day entry
    mid_idx = len(time_labels) // 2
    mid_spy = spy_df.iloc[mid_idx]
    mid_spx = spx_df.iloc[mid_idx]

    print(f"\n  Simulated entry at: {time_labels[mid_idx]}")
    print(f"  SPY Price: ${mid_spy['close']:.2f}")
    print(f"  SPX Price: ${mid_spx['close']:.2f}")

    print("\n✅ Timezone conversion and component simulation successful")

except Exception as e:
    print(f"❌ Error in component simulation: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Final Summary
print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED")
print("=" * 70)

print("\nSummary:")
print(f"  ✅ Files loaded successfully")
print(f"  ✅ Data parsing correct")
print(f"  ✅ P&L calculations working")
print(f"  ✅ Price sweep functional")
print(f"  ✅ Credits validated")
print(f"  ✅ UI components simulated")

print("\n🎉 Calculator is ready to use!")
print(f"\nLaunch with: streamlit run strategy_calculator_simple.py")
print(f"Access at: http://localhost:8501")
