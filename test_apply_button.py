#!/usr/bin/env python3
"""
Test to verify the Apply button session state flow.
This simulates what should happen when Apply is clicked.
"""

import pandas as pd
import sys
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

# Simulate session state
class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value

def test_apply_button_flow():
    """Test the session state flow when Apply button is clicked"""

    # Initialize session state (simulating Streamlit)
    session_state = MockSessionState()
    session_state.selected_spy_strike = None
    session_state.selected_spx_strike = None
    session_state.selected_entry_time = None
    session_state.strikes_just_applied = False
    session_state.applied_spy_strike = None
    session_state.applied_spx_strike = None
    session_state.applied_direction = None
    session_state.applied_entry_time = None
    session_state.scan_results = None

    print("=== Initial Session State ===")
    print(f"selected_spy_strike: {session_state.selected_spy_strike}")
    print(f"selected_spx_strike: {session_state.selected_spx_strike}")
    print(f"selected_entry_time: {session_state.selected_entry_time}")
    print(f"strikes_just_applied: {session_state.strikes_just_applied}")
    print()

    # Simulate a scan result row
    row = {
        'SPY Strike': 702,
        'SPX Strike': 7040,
        'Moneyness': '+1.75%',
        'Credit $': '$9,020',
        'Max Gap Time': '12:50',
        'Best Worst-Case': 5229,
        'Best WC $': '$5,229',
        'Best WC Time': '12:50',
        'Direction': 'Sell SPY'
    }

    print("=== Simulating Apply Button Click ===")
    print(f"Row data: SPY {row['SPY Strike']} / SPX {row['SPX Strike']}")
    print(f"Best WC Time: {row['Best WC Time']}")
    print()

    # This is what the Apply button should do:
    session_state.selected_spy_strike = int(row['SPY Strike'])
    session_state.selected_spx_strike = int(row['SPX Strike'])
    session_state.selected_entry_time = row['Best WC Time']  # e.g., "12:50"
    session_state.strikes_just_applied = True
    session_state.applied_spy_strike = int(row['SPY Strike'])
    session_state.applied_spx_strike = int(row['SPX Strike'])
    session_state.applied_direction = row['Direction']
    session_state.applied_entry_time = row['Best WC Time']

    print("=== After Apply Button Click ===")
    print(f"selected_spy_strike: {session_state.selected_spy_strike}")
    print(f"selected_spx_strike: {session_state.selected_spx_strike}")
    print(f"selected_entry_time: {session_state.selected_entry_time}")
    print(f"strikes_just_applied: {session_state.strikes_just_applied}")
    print(f"applied_entry_time: {session_state.applied_entry_time}")
    print()

    # Simulate what happens after rerun - check if values would be used

    # 1. Check banner display (happens early in the code)
    print("=== Simulating Banner Check (after rerun) ===")
    if session_state.strikes_just_applied:
        applied_spy = session_state.applied_spy_strike
        applied_spx = session_state.applied_spx_strike
        applied_dir = session_state.applied_direction
        applied_time = session_state.applied_entry_time

        print(f"✅ Banner would show: SPY {applied_spy} / SPX {applied_spx} | {applied_dir} | Entry Time: {applied_time}")
        session_state.strikes_just_applied = False  # Clear after showing
    else:
        print("❌ Banner would NOT show - strikes_just_applied is False")
    print()

    # 2. Check strike input defaults
    print("=== Simulating Strike Input Defaults ===")
    if session_state.selected_spy_strike is not None:
        default_spy_strike = session_state.selected_spy_strike
        print(f"✅ SPY strike would default to: {default_spy_strike}")
    else:
        print("❌ SPY strike would use fallback default")

    if session_state.selected_spx_strike is not None:
        default_spx_strike = session_state.selected_spx_strike
        print(f"✅ SPX strike would default to: {default_spx_strike}")
    else:
        print("❌ SPX strike would use fallback default")
    print()

    # 3. Check entry time slider default
    print("=== Simulating Entry Time Slider Default ===")
    # Simulate time_short_labels from the data
    time_short_labels = ['09:30', '09:31', '09:32', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '12:50', '13:00', '13:30', '14:00', '15:00', '15:30', '16:00']

    default_entry_idx = 0
    if session_state.selected_entry_time is not None:
        selected_time = session_state.selected_entry_time
        print(f"Looking for time: '{selected_time}' in {time_short_labels}")
        if selected_time in time_short_labels:
            default_entry_idx = time_short_labels.index(selected_time)
            print(f"✅ Entry time slider would default to index {default_entry_idx} (time: {selected_time})")
        else:
            print(f"❌ Time '{selected_time}' NOT FOUND in time_short_labels!")
            print(f"   Available times: {time_short_labels}")
        session_state.selected_entry_time = None  # Clear after using
    else:
        print("❌ Entry time would use fallback default (index 0)")
    print()

    # Summary
    print("=== SUMMARY ===")
    all_passed = True

    if default_spy_strike == 702:
        print("✅ SPY strike: PASS")
    else:
        print(f"❌ SPY strike: FAIL (got {default_spy_strike}, expected 702)")
        all_passed = False

    if default_spx_strike == 7040:
        print("✅ SPX strike: PASS")
    else:
        print(f"❌ SPX strike: FAIL (got {default_spx_strike}, expected 7040)")
        all_passed = False

    if default_entry_idx > 0:
        print(f"✅ Entry time index: PASS (index {default_entry_idx})")
    else:
        print(f"❌ Entry time index: FAIL (got index 0, should be > 0)")
        all_passed = False

    print()
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("💥 Some tests failed!")

    return all_passed


def test_time_format_matching():
    """Test that the time format from scanner matches the sidebar time format"""
    print("\n=== Testing Time Format Matching ===\n")

    # Load actual data to check time formats
    import os
    data_dir = '/Users/johnnyhuang/personal/optionsarbitrage/data'

    # Find a data file
    for f in os.listdir(data_dir):
        if f.startswith('underlying_prices_') and f.endswith('.csv'):
            filepath = os.path.join(data_dir, f)
            print(f"Loading: {filepath}")

            df = pd.read_csv(filepath)
            df['time'] = pd.to_datetime(df['time'], utc=True)

            spy_df = df[df['symbol'] == 'SPY'].copy()
            spy_df['time_et'] = spy_df['time'].dt.tz_convert('America/New_York')
            spy_df['time_short'] = spy_df['time_et'].dt.strftime('%H:%M')

            time_short_labels = spy_df['time_short'].tolist()

            print(f"Number of time points: {len(time_short_labels)}")
            print(f"First 10 times: {time_short_labels[:10]}")
            print(f"Sample times around noon: {[t for t in time_short_labels if t.startswith('12:')]}")

            # Check if "12:50" would be found
            test_time = "12:50"
            if test_time in time_short_labels:
                idx = time_short_labels.index(test_time)
                print(f"\n✅ Time '{test_time}' found at index {idx}")
            else:
                print(f"\n❌ Time '{test_time}' NOT found!")
                print(f"   Closest times: {[t for t in time_short_labels if '12:4' in t or '12:5' in t]}")

            break


if __name__ == "__main__":
    test_apply_button_flow()
    test_time_format_matching()
