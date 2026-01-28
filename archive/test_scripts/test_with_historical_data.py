#!/usr/bin/env python3
"""
Test strategy with historical backtest data
"""

import sys
import pandas as pd
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.strategy.spy_spx_strategy import SPYSPXStrategy

def test_with_historical_data():
    """Test strategy with real historical option prices"""

    print("="*70)
    print("TESTING STRATEGY WITH HISTORICAL BACKTEST DATA")
    print("="*70)

    # Load historical data
    df = pd.read_csv('archive/old_code/backtest_2025_results.csv')

    print(f"\nLoaded {len(df)} historical trades from backtest")
    print(f"Date range: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}")

    # Initialize strategy
    config = {
        'min_entry_credit': 100,
        'assignment_risk_threshold': 10,
        'spy_contracts_per_spread': 10,
        'spx_contracts_per_spread': 1,
        'max_spreads_per_day': 2,
        'max_position_loss': 1000,
    }

    strategy = SPYSPXStrategy(config)

    # Test with first 10 days
    print("\n" + "="*70)
    print("TESTING FIRST 10 TRADING DAYS")
    print("="*70)

    total_credit_old = 0
    total_credit_new = 0

    for idx in range(min(10, len(df))):
        row = df.iloc[idx]

        print(f"\n{'='*70}")
        print(f"Day {idx+1}: {row['Date']}")
        print(f"{'='*70}")

        spy_price = row['SPY_Price']
        spx_price = row['SPX_Price']

        print(f"SPY: ${spy_price:.2f}, SPX: ${spx_price:.2f}, Ratio: {spx_price/spy_price:.4f}")

        # Get option prices (NOTE: historical data only has calls)
        # For testing purposes, we'll simulate put prices
        spy_call_mid = (row['SPY_Bid'] + row['SPY_Ask']) / 2
        spx_call_mid = (row['SPX_Bid'] + row['SPX_Ask']) / 2

        # Simulate put prices (typically similar to call prices for ATM 0DTE)
        # In reality, puts might be slightly different due to put-call parity
        spy_put_mid = spy_call_mid * 0.95  # Slightly cheaper
        spx_put_mid = spx_call_mid * 0.95

        print(f"\nOption Prices:")
        print(f"  SPY call: ${spy_call_mid:.2f} (× 10 = ${spy_call_mid*10:.2f})")
        print(f"  SPX call: ${spx_call_mid:.2f}")
        print(f"  SPY put:  ${spy_put_mid:.2f} (× 10 = ${spy_put_mid*10:.2f}) [simulated]")
        print(f"  SPX put:  ${spx_put_mid:.2f} [simulated]")

        # Calculate with new dynamic strategy
        credit = strategy.calculate_entry_credit(
            spy_call_mid, spx_call_mid, spy_put_mid, spx_put_mid
        )

        print(f"\nDYNAMIC STRATEGY:")
        print(f"  CALLS: {credit['calls_structure']}")
        print(f"    Credit: ${credit['calls_credit']:,.2f}")
        print(f"  PUTS:  {credit['puts_structure']}")
        print(f"    Credit: ${credit['puts_credit']:,.2f}")
        print(f"  Total Net Credit: ${credit['net_credit']:,.2f}")

        # Compare to old entry credit (from backtest)
        old_credit = row['Entry_Credit']
        print(f"\nCOMPARISON:")
        print(f"  Old strategy (calls only): ${old_credit:.2f}")
        print(f"  New strategy (calls+puts):  ${credit['net_credit']:.2f}")
        print(f"  Difference: ${credit['net_credit'] - old_credit:+,.2f}")

        total_credit_old += old_credit
        total_credit_new += credit['net_credit']

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY OF 10 DAYS")
    print(f"{'='*70}")
    print(f"\nTotal credit collected:")
    print(f"  Old strategy (calls only): ${total_credit_old:,.2f}")
    print(f"  New strategy (calls+puts):  ${total_credit_new:,.2f}")
    print(f"  Improvement: ${total_credit_new - total_credit_old:+,.2f} ({((total_credit_new/total_credit_old - 1)*100):+.1f}%)")

    print(f"\nAverage credit per trade:")
    print(f"  Old strategy: ${total_credit_old/10:,.2f}")
    print(f"  New strategy: ${total_credit_new/10:,.2f}")

    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")
    print("\nThe new double-sided strategy:")
    print("  ✅ Collects credit on both calls AND puts")
    print("  ✅ Dynamically adapts to which options are more expensive")
    print("  ✅ Should generate ~2x the credit of calls-only strategy")
    print("  ⚠️  Note: Put prices were simulated for this test")
    print("  ⚠️  Actual performance depends on real put-call price relationships")


if __name__ == "__main__":
    test_with_historical_data()
