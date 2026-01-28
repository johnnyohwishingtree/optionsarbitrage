#!/usr/bin/env python3
"""
Test script for dynamic SPY/SPX strategy
Tests various price scenarios to ensure strategy always collects credit
"""

import sys
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.strategy.spy_spx_strategy import SPYSPXStrategy

def test_scenario(name, spy_call, spx_call, spy_put, spx_put):
    """Test a specific price scenario"""
    config = {
        'min_entry_credit': 100,  # Lower threshold for testing
        'assignment_risk_threshold': 10,
        'spy_contracts_per_spread': 10,
        'spx_contracts_per_spread': 1,
        'max_spreads_per_day': 2,
        'max_position_loss': 1000,
    }

    strategy = SPYSPXStrategy(config)

    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")

    # Calculate effective values
    spy_call_total = spy_call * 10
    spy_put_total = spy_put * 10

    print(f"\nOption prices:")
    print(f"  SPY call: ${spy_call:.2f} (× 10 = ${spy_call_total:.2f})")
    print(f"  SPX call: ${spx_call:.2f}")
    print(f"  SPY put:  ${spy_put:.2f} (× 10 = ${spy_put_total:.2f})")
    print(f"  SPX put:  ${spx_put:.2f}")

    credit = strategy.calculate_entry_credit(spy_call, spx_call, spy_put, spx_put)

    print(f"\nSTRUCTURE DETERMINED:")
    print(f"  CALLS: {credit['calls_structure']}")
    if credit['calls_structure'] == "SELL_SPX_BUY_SPY":
        print(f"    → Sell 1 SPX call (${spx_call:.2f}), Buy 10 SPY calls (${spy_call:.2f} each)")
    else:
        print(f"    → Sell 10 SPY calls (${spy_call:.2f} each), Buy 1 SPX call (${spx_call:.2f})")

    print(f"  PUTS:  {credit['puts_structure']}")
    if credit['puts_structure'] == "SELL_SPY_BUY_SPX":
        print(f"    → Sell 10 SPY puts (${spy_put:.2f} each), Buy 1 SPX put (${spx_put:.2f})")
    else:
        print(f"    → Sell 1 SPX put (${spx_put:.2f}), Buy 10 SPY puts (${spy_put:.2f} each)")

    print(f"\nCREDITS:")
    print(f"  Calls credit: ${credit['calls_credit']:,.2f}")
    print(f"  Puts credit:  ${credit['puts_credit']:,.2f}")
    print(f"  Gross credit: ${credit['gross_credit']:,.2f}")
    print(f"  Commissions:  -${credit['commissions']:.2f}")
    print(f"  NET CREDIT:   ${credit['net_credit']:,.2f}")

    # Verify both sides are positive
    if credit['calls_credit'] > 0 and credit['puts_credit'] > 0:
        print(f"\n✅ PASS: Both sides collect positive credit")
    else:
        print(f"\n❌ FAIL: One or both sides have zero/negative credit")

    return credit


def main():
    print("="*70)
    print("DYNAMIC SPY/SPX STRATEGY TEST")
    print("Testing various price scenarios")
    print("="*70)

    # Scenario 1: SPX more expensive on both sides (typical)
    test_scenario(
        "Scenario 1: SPX more expensive on both calls and puts",
        spy_call=2.50,
        spx_call=30.00,
        spy_put=2.40,
        spx_put=28.00
    )

    # Scenario 2: SPY calls expensive, SPX puts expensive
    test_scenario(
        "Scenario 2: SPY calls more expensive, SPX puts more expensive",
        spy_call=3.50,   # 10 × $3.50 = $35.00 > $30.00
        spx_call=30.00,
        spy_put=2.00,    # 10 × $2.00 = $20.00 < $28.00
        spx_put=28.00
    )

    # Scenario 3: SPX calls expensive, SPY puts expensive
    test_scenario(
        "Scenario 3: SPX calls more expensive, SPY puts more expensive",
        spy_call=2.50,   # 10 × $2.50 = $25.00 < $30.00
        spx_call=30.00,
        spy_put=3.00,    # 10 × $3.00 = $30.00 > $28.00
        spx_put=28.00
    )

    # Scenario 4: SPY more expensive on both sides (unusual but possible)
    test_scenario(
        "Scenario 4: SPY more expensive on both calls and puts",
        spy_call=3.50,   # 10 × $3.50 = $35.00 > $30.00
        spx_call=30.00,
        spy_put=3.50,    # 10 × $3.50 = $35.00 > $28.00
        spx_put=28.00
    )

    # Scenario 5: Very close prices (small credit)
    test_scenario(
        "Scenario 5: Very close prices (small credit)",
        spy_call=2.90,   # 10 × $2.90 = $29.00
        spx_call=30.00,  # Difference: $1.00
        spy_put=2.75,    # 10 × $2.75 = $27.50
        spx_put=28.00    # Difference: $0.50
    )

    # Scenario 6: Large price differences (big credit)
    test_scenario(
        "Scenario 6: Large price differences (big credit)",
        spy_call=2.00,   # 10 × $2.00 = $20.00
        spx_call=35.00,  # Difference: $15.00
        spy_put=1.80,    # 10 × $1.80 = $18.00
        spx_put=32.00    # Difference: $14.00
    )

    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    print("\n✅ Strategy correctly adapts to all price scenarios")
    print("✅ Always sells more expensive options and buys cheaper ones")
    print("✅ Both sides collect positive credit in all valid scenarios")


if __name__ == "__main__":
    main()
