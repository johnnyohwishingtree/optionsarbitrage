#!/usr/bin/env python3
"""
Analyze P&L under different price movement scenarios
Shows what happens when prices move up/down/sideways at expiration
"""

import sys
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.strategy.spy_spx_strategy import SPYSPXStrategy

def analyze_scenario(scenario_name, spy_entry, spx_entry, spy_exit, spx_exit,
                     spy_call_price, spx_call_price, spy_put_price, spx_put_price):
    """Analyze a specific price movement scenario"""

    config = {
        'min_entry_credit': 100,
        'assignment_risk_threshold': 10,
        'spy_contracts_per_spread': 10,
        'spx_contracts_per_spread': 1,
        'max_spreads_per_day': 2,
        'max_position_loss': 1000,
    }

    strategy = SPYSPXStrategy(config)

    print(f"\n{'='*80}")
    print(f"{scenario_name}")
    print(f"{'='*80}")

    # Entry
    spy_call_strike = round(spy_entry)
    spy_put_strike = round(spy_entry)
    spx_call_strike = round(spx_entry / 5) * 5
    spx_put_strike = round(spx_entry / 5) * 5

    print(f"\nENTRY (9:35 AM):")
    print(f"  SPY Price: ${spy_entry:.2f}")
    print(f"  SPX Price: ${spx_entry:.2f}")
    print(f"  Strikes: SPY ${spy_call_strike}, SPX ${spx_call_strike}")

    # Calculate entry credit and structure
    credit_calc = strategy.calculate_entry_credit(
        spy_call_price, spx_call_price, spy_put_price, spx_put_price
    )

    calls_structure = credit_calc['calls_structure']
    puts_structure = credit_calc['puts_structure']
    entry_credit = credit_calc['net_credit']

    print(f"\nPOSITIONS OPENED:")
    print(f"  CALLS: {calls_structure}")
    if calls_structure == "SELL_SPY_BUY_SPX":
        print(f"    - SHORT 10 SPY {spy_call_strike} calls")
        print(f"    - LONG 1 SPX {spx_call_strike} call")
    else:
        print(f"    - SHORT 1 SPX {spx_call_strike} call")
        print(f"    - LONG 10 SPY {spy_call_strike} calls")

    print(f"  PUTS: {puts_structure}")
    if puts_structure == "SELL_SPY_BUY_SPX":
        print(f"    - SHORT 10 SPY {spy_put_strike} puts")
        print(f"    - LONG 1 SPX {spx_put_strike} put")
    else:
        print(f"    - SHORT 1 SPX {spx_put_strike} put")
        print(f"    - LONG 10 SPY {spy_put_strike} puts")

    print(f"\n  Entry Credit Collected: ${entry_credit:,.2f}")

    # Exit
    price_change_spy = spy_exit - spy_entry
    price_change_spx = spx_exit - spx_entry
    price_change_pct = (price_change_spy / spy_entry) * 100

    print(f"\nEXIT (4:00 PM - Expiration):")
    print(f"  SPY Price: ${spy_exit:.2f} ({price_change_spy:+.2f}, {price_change_pct:+.2f}%)")
    print(f"  SPX Price: ${spx_exit:.2f} ({price_change_spx:+.2f})")

    # Calculate settlement values
    print(f"\nSETTLEMENT CALCULATIONS:")

    # CALLS
    spy_call_itm = max(0, spy_exit - spy_call_strike)
    spx_call_itm = max(0, spx_exit - spx_call_strike)

    print(f"\n  CALLS (Strike: SPY ${spy_call_strike}, SPX ${spx_call_strike}):")
    print(f"    SPY calls ITM by: ${spy_call_itm:.2f}")
    print(f"    SPX calls ITM by: ${spx_call_itm:.2f}")

    spy_call_payout = spy_call_itm * 100 * 10  # 10 contracts
    spx_call_payout = spx_call_itm * 100 * 1   # 1 contract

    print(f"    SPY call value: ${spy_call_payout:,.2f}")
    print(f"    SPX call value: ${spx_call_payout:,.2f}")

    if calls_structure == "SELL_SPY_BUY_SPX":
        # We're short SPY, long SPX
        calls_pnl = -spy_call_payout + spx_call_payout
        print(f"    Calls P&L: -${spy_call_payout:,.2f} (short SPY) + ${spx_call_payout:,.2f} (long SPX) = ${calls_pnl:+,.2f}")
    else:
        # We're short SPX, long SPY
        calls_pnl = spy_call_payout - spx_call_payout
        print(f"    Calls P&L: ${spy_call_payout:,.2f} (long SPY) - ${spx_call_payout:,.2f} (short SPX) = ${calls_pnl:+,.2f}")

    # PUTS
    spy_put_itm = max(0, spy_put_strike - spy_exit)
    spx_put_itm = max(0, spx_put_strike - spx_exit)

    print(f"\n  PUTS (Strike: SPY ${spy_put_strike}, SPX ${spx_put_strike}):")
    print(f"    SPY puts ITM by: ${spy_put_itm:.2f}")
    print(f"    SPX puts ITM by: ${spx_put_itm:.2f}")

    spy_put_payout = spy_put_itm * 100 * 10  # 10 contracts
    spx_put_payout = spx_put_itm * 100 * 1   # 1 contract

    print(f"    SPY put value: ${spy_put_payout:,.2f}")
    print(f"    SPX put value: ${spx_put_payout:,.2f}")

    if puts_structure == "SELL_SPY_BUY_SPX":
        # We're short SPY, long SPX
        puts_pnl = -spy_put_payout + spx_put_payout
        print(f"    Puts P&L: -${spy_put_payout:,.2f} (short SPY) + ${spx_put_payout:,.2f} (long SPX) = ${puts_pnl:+,.2f}")
    else:
        # We're short SPX, long SPY
        puts_pnl = spy_put_payout - spx_put_payout
        print(f"    Puts P&L: ${spy_put_payout:,.2f} (long SPY) - ${spx_put_payout:,.2f} (short SPX) = ${puts_pnl:+,.2f}")

    # Total P&L
    settlement_pnl = calls_pnl + puts_pnl
    total_pnl = entry_credit + settlement_pnl

    print(f"\n{'='*80}")
    print(f"FINAL P&L:")
    print(f"  Entry Credit:     ${entry_credit:+,.2f}")
    print(f"  Settlement P&L:   ${settlement_pnl:+,.2f}")
    print(f"  ────────────────────────────")
    print(f"  TOTAL P&L:        ${total_pnl:+,.2f}")
    print(f"{'='*80}")

    return total_pnl


def main():
    print("="*80)
    print("SPY/SPX STRATEGY: PRICE MOVEMENT SCENARIOS")
    print("="*80)
    print("\nAssuming structure: SELL 10 SPY (both calls & puts), BUY 1 SPX (both calls & puts)")
    print("This is the most common scenario based on historical data.")

    # Entry prices (same for all scenarios)
    spy_entry = 600.0
    spx_entry = 6000.0

    # Option prices at entry
    spy_call = 2.50  # SPY call @ $2.50 × 10 = $25
    spx_call = 30.00  # SPX call @ $30
    spy_put = 2.50   # SPY put @ $2.50 × 10 = $25
    spx_put = 30.00  # SPX put @ $30

    results = []

    # Scenario 1: No movement (perfect tracking)
    results.append(("No Movement", analyze_scenario(
        "SCENARIO 1: No Movement (Perfect Day)",
        spy_entry, spx_entry,
        600.0, 6000.0,  # Same prices
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 2: Small move up with perfect tracking
    results.append(("Small Up (Perfect)", analyze_scenario(
        "SCENARIO 2: Small Move Up (+$2, +$20) - Perfect Tracking",
        spy_entry, spx_entry,
        602.0, 6020.0,  # +$2 SPY, +$20 SPX (perfect 10:1)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 3: Small move down with perfect tracking
    results.append(("Small Down (Perfect)", analyze_scenario(
        "SCENARIO 3: Small Move Down (-$2, -$20) - Perfect Tracking",
        spy_entry, spx_entry,
        598.0, 5980.0,  # -$2 SPY, -$20 SPX (perfect 10:1)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 4: Large move up with perfect tracking
    results.append(("Large Up (Perfect)", analyze_scenario(
        "SCENARIO 4: Large Move Up (+$10, +$100) - Perfect Tracking",
        spy_entry, spx_entry,
        610.0, 6100.0,  # +$10 SPY, +$100 SPX (perfect 10:1)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 5: Large move down with perfect tracking
    results.append(("Large Down (Perfect)", analyze_scenario(
        "SCENARIO 5: Large Move Down (-$10, -$100) - Perfect Tracking",
        spy_entry, spx_entry,
        590.0, 5900.0,  # -$10 SPY, -$100 SPX (perfect 10:1)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 6: Tracking error - SPY rises more than SPX (BAD)
    results.append(("Tracking Error Up (BAD)", analyze_scenario(
        "SCENARIO 6: Tracking Error - SPY Rises More (Worst Case)",
        spy_entry, spx_entry,
        610.0, 6050.0,  # SPY +$10, SPX only +$50 (should be +$100)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 7: Tracking error - SPY falls more than SPX (BAD)
    results.append(("Tracking Error Down (BAD)", analyze_scenario(
        "SCENARIO 7: Tracking Error - SPY Falls More (Worst Case)",
        spy_entry, spx_entry,
        590.0, 5950.0,  # SPY -$10, SPX only -$50 (should be -$100)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 8: Tracking error - SPX moves more than SPY (GOOD)
    results.append(("Tracking Error (GOOD)", analyze_scenario(
        "SCENARIO 8: Tracking Error - SPX Moves More (Best Case)",
        spy_entry, spx_entry,
        605.0, 6100.0,  # SPY +$5, SPX +$100 (should only be +$50)
        spy_call, spx_call, spy_put, spx_put
    )))

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY OF ALL SCENARIOS")
    print(f"{'='*80}")

    for name, pnl in results:
        status = "✅ PROFIT" if pnl > 0 else "❌ LOSS"
        print(f"{name:30} ${pnl:+10,.2f}  {status}")

    print(f"\n{'='*80}")
    print("KEY INSIGHTS")
    print(f"{'='*80}")
    print("""
1. WHEN WE WIN:
   - Price stays near ATM (sideways) → Keep full credit
   - Perfect tracking on moves → Keep full credit
   - SPX moves MORE than SPY → Extra profit (we're long SPX, short SPY)

2. WHEN WE LOSE:
   - SPY moves MORE than SPX → Loss (our short SPY gets hit harder)
   - Large tracking errors → Can wipe out credit

3. THE EDGE:
   - SPY and SPX track very closely (99.9% correlation)
   - Entry credit is pure profit if tracking holds
   - We're betting on mean reversion of tracking error

4. RISK MANAGEMENT:
   - Exit if SPY moves >$10 from strike (assignment risk)
   - Exit at 3:45 PM regardless (avoid settlement risk)
   - Max loss limit: $1,000 per position
""")


if __name__ == "__main__":
    main()
