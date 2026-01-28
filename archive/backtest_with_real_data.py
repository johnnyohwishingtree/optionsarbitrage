#!/usr/bin/env python3
"""
Backtest the double-sided SPY/SPX strategy with REAL historical data
Tests different entry times throughout the day
"""

import pandas as pd
import numpy as np
from datetime import datetime, time

# Load historical data
df = pd.read_csv('data/historical_intraday.csv')
df['datetime'] = pd.to_datetime(df['datetime'])

# Pivot to get all 4 legs side by side
pivot = df.pivot(index='datetime', columns='contract', values='close')
pivot = pivot.reset_index()

print("="*100)
print("BACKTESTING DOUBLE-SIDED SPY/SPX STRATEGY WITH REAL DATA")
print("="*100)
print(f"\nData Range: {pivot['datetime'].min()} to {pivot['datetime'].max()}")
print(f"Total Bars: {len(pivot)}")

# Strategy parameters
SPY_QUANTITY = 10  # 10 contracts
SPX_QUANTITY = 1   # 1 contract
COMMISSION_PER_CONTRACT = 0.65
TOTAL_CONTRACTS = (SPY_QUANTITY * 2) + (SPX_QUANTITY * 2)  # 22 contracts (calls + puts)
TOTAL_COMMISSION = TOTAL_CONTRACTS * COMMISSION_PER_CONTRACT

print(f"\n📋 Strategy Configuration:")
print(f"   SPY Quantity: {SPY_QUANTITY} contracts per leg")
print(f"   SPX Quantity: {SPX_QUANTITY} contract per leg")
print(f"   Total Commission: ${TOTAL_COMMISSION:.2f}")


def calculate_entry_credit(row):
    """Calculate entry credit for a given row"""
    spy_call = row['spy_call']
    spy_put = row['spy_put']
    spx_call = row['spx_call']
    spx_put = row['spx_put']

    # Skip if any prices are NaN
    if pd.isna(spy_call) or pd.isna(spy_put) or pd.isna(spx_call) or pd.isna(spx_put):
        return None

    # CALLS SIDE: Compare effective values (accounting for 10:1 ratio)
    spy_call_total = spy_call * 100 * SPY_QUANTITY
    spx_call_total = spx_call * 100 * SPX_QUANTITY

    if spx_call_total > spy_call_total:
        # Sell SPX, Buy SPY
        calls_credit = spx_call_total - spy_call_total
        calls_structure = "SELL_SPX_BUY_SPY"
    else:
        # Sell SPY, Buy SPX
        calls_credit = spy_call_total - spx_call_total
        calls_structure = "SELL_SPY_BUY_SPX"

    # PUTS SIDE: Compare effective values
    spy_put_total = spy_put * 100 * SPY_QUANTITY
    spx_put_total = spx_put * 100 * SPX_QUANTITY

    if spx_put_total > spy_put_total:
        # Sell SPX, Buy SPY
        puts_credit = spx_put_total - spy_put_total
        puts_structure = "SELL_SPX_BUY_SPY"
    else:
        # Sell SPY, Buy SPX
        puts_credit = spy_put_total - spx_put_total
        puts_structure = "SELL_SPY_BUY_SPX"

    gross_credit = calls_credit + puts_credit
    net_credit = gross_credit - TOTAL_COMMISSION

    return {
        'spy_call': spy_call,
        'spy_put': spy_put,
        'spx_call': spx_call,
        'spx_put': spx_put,
        'calls_structure': calls_structure,
        'puts_structure': puts_structure,
        'calls_credit': calls_credit,
        'puts_credit': puts_credit,
        'gross_credit': gross_credit,
        'commission': TOTAL_COMMISSION,
        'net_credit': net_credit
    }


# Test ALL available times (every 5 minutes)
# Just use the actual times from the data
available_times = pivot['datetime'].tolist()

print("\n" + "="*100)
print("TESTING DIFFERENT ENTRY TIMES")
print("="*100)

results = []

# Sample every 6th row to show ~10 entry times instead of all 51
sample_indices = list(range(0, len(available_times), 6))

for idx in sample_indices:
    entry_time = available_times[idx]
    entry_row = pivot[pivot['datetime'] == entry_time]

    if entry_row.empty:
        continue

    entry_data = calculate_entry_credit(entry_row.iloc[0])

    if not entry_data:
        continue

    entry_time_str = entry_time.strftime('%H:%M:%S')

    print(f"\n{'─'*100}")
    print(f"📍 ENTRY TIME: {entry_time_str} ({entry_time})")
    print(f"{'─'*100}")

    print(f"\n💰 OPTION PRICES AT ENTRY:")
    print(f"   SPY Call: ${entry_data['spy_call']:.2f} × {SPY_QUANTITY} = ${entry_data['spy_call'] * 100 * SPY_QUANTITY:,.2f}")
    print(f"   SPX Call: ${entry_data['spx_call']:.2f} × {SPX_QUANTITY} = ${entry_data['spx_call'] * 100 * SPX_QUANTITY:,.2f}")
    print(f"   SPY Put:  ${entry_data['spy_put']:.2f} × {SPY_QUANTITY} = ${entry_data['spy_put'] * 100 * SPY_QUANTITY:,.2f}")
    print(f"   SPX Put:  ${entry_data['spx_put']:.2f} × {SPX_QUANTITY} = ${entry_data['spx_put'] * 100 * SPX_QUANTITY:,.2f}")

    print(f"\n🔧 STRUCTURE:")
    print(f"   Calls Side: {entry_data['calls_structure']} → Credit: ${entry_data['calls_credit']:.2f}")
    print(f"   Puts Side:  {entry_data['puts_structure']} → Credit: ${entry_data['puts_credit']:.2f}")

    print(f"\n💵 ENTRY P&L:")
    print(f"   Gross Credit:  ${entry_data['gross_credit']:,.2f}")
    print(f"   Commissions:   -${entry_data['commission']:.2f}")
    print(f"   NET CREDIT:    ${entry_data['net_credit']:,.2f}")

    if entry_data['net_credit'] > 0:
        print(f"   ✅ PROFITABLE ENTRY (collected ${entry_data['net_credit']:.2f} credit)")
    else:
        print(f"   ❌ UNPROFITABLE ENTRY (paid ${abs(entry_data['net_credit']):.2f} debit)")

    results.append({
        'entry_time': entry_time_str,
        'net_credit': entry_data['net_credit'],
        'gross_credit': entry_data['gross_credit'],
        'spy_call': entry_data['spy_call'],
        'spy_put': entry_data['spy_put'],
        'spx_call': entry_data['spx_call'],
        'spx_put': entry_data['spx_put'],
    })


# Summary
print("\n\n" + "="*100)
print("SUMMARY OF ALL ENTRY TIMES")
print("="*100)

results_df = pd.DataFrame(results)
print(f"\n{results_df.to_string(index=False)}")

print(f"\n📊 STATISTICS:")
print(f"   Average Net Credit: ${results_df['net_credit'].mean():,.2f}")
print(f"   Best Entry:         ${results_df['net_credit'].max():,.2f} at {results_df.loc[results_df['net_credit'].idxmax(), 'entry_time']}")
print(f"   Worst Entry:        ${results_df['net_credit'].min():,.2f} at {results_df.loc[results_df['net_credit'].idxmin(), 'entry_time']}")
print(f"   Profitable Entries: {len(results_df[results_df['net_credit'] > 0])} / {len(results_df)}")

print("\n" + "="*100)
print("🎯 KEY TAKEAWAYS")
print("="*100)
print("""
This backtest uses REAL market data from today to test the strategy at different entry times.

Key Observations:
1. The strategy's profitability depends on the ENTRY CREDIT collected
2. If net credit > 0: Strategy profits (assuming positions hedge to $0 at expiration)
3. If net credit < 0: Strategy loses (you paid a debit to enter)

Important Notes:
- These are MID prices (close prices from historical bars)
- In reality, you'd sell at BID and buy at ASK (slippage)
- Settlement P&L depends on how well SPY/SPX track each other
- This shows the MAXIMUM potential credit (perfect execution at mid prices)
""")
