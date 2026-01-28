#!/usr/bin/env python3
"""
Analyze P&L under REALISTIC price movement scenarios
SPY and SPX move the same percentage (as they do in real life)
"""

import sys
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.strategy.spy_spx_strategy import SPYSPXStrategy

def analyze_scenario(scenario_name, spy_entry, spx_entry, price_change_pct,
                     spy_call_price, spx_call_price, spy_put_price, spx_put_price):
    """Analyze a specific price movement scenario with realistic tracking"""

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

    # Calculate exit prices (same percentage move)
    spy_exit = spy_entry * (1 + price_change_pct/100)
    spx_exit = spx_entry * (1 + price_change_pct/100)

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

    # Exit (same percentage move for both)
    spy_change = spy_exit - spy_entry
    spx_change = spx_exit - spx_entry

    print(f"\nEXIT (4:00 PM - Expiration):")
    print(f"  SPY Price: ${spy_exit:.2f} ({spy_change:+.2f}, {price_change_pct:+.2f}%)")
    print(f"  SPX Price: ${spx_exit:.2f} ({spx_change:+.2f}, {price_change_pct:+.2f}%)")
    print(f"  📊 Both moved {price_change_pct:+.2f}% (perfect tracking)")

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
        print(f"    Calls P&L: -${spy_call_payout:,.2f} (short 10 SPY) + ${spx_call_payout:,.2f} (long 1 SPX) = ${calls_pnl:+,.2f}")
    else:
        # We're short SPX, long SPY
        calls_pnl = spy_call_payout - spx_call_payout
        print(f"    Calls P&L: ${spy_call_payout:,.2f} (long 10 SPY) - ${spx_call_payout:,.2f} (short 1 SPX) = ${calls_pnl:+,.2f}")

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
        print(f"    Puts P&L: -${spy_put_payout:,.2f} (short 10 SPY) + ${spx_put_payout:,.2f} (long 1 SPX) = ${puts_pnl:+,.2f}")
    else:
        # We're short SPX, long SPY
        puts_pnl = spy_put_payout - spx_put_payout
        print(f"    Puts P&L: ${spy_put_payout:,.2f} (long 10 SPY) - ${spx_put_payout:,.2f} (short 1 SPX) = ${puts_pnl:+,.2f}")

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
    print("SPY/SPX STRATEGY: REALISTIC PRICE MOVEMENT ANALYSIS")
    print("="*80)
    print("\nKey Assumption: SPY and SPX move the SAME percentage (as in real life)")
    print("Assuming structure: SELL 10 SPY, BUY 1 SPX (most common based on historical data)")

    # Entry prices (same for all scenarios)
    spy_entry = 600.0
    spx_entry = 6000.0

    # Option prices at entry
    # Based on historical data: SPY * 10 > SPX, so we sell SPY and buy SPX
    spy_call = 2.50  # SPY call @ $2.50 × 10 = $25
    spx_call = 30.00  # SPX call @ $30
    spy_put = 2.50   # SPY put @ $2.50 × 10 = $25
    spx_put = 30.00  # SPX put @ $30

    results = []

    # Scenario 1: No movement
    results.append(("No Movement (0%)", analyze_scenario(
        "SCENARIO 1: No Movement - Sideways Day",
        spy_entry, spx_entry,
        0.0,  # 0% change
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 2: Slight move up
    results.append(("Slight Up (+0.33%)", analyze_scenario(
        "SCENARIO 2: Slight Move Up (+0.33%)",
        spy_entry, spx_entry,
        0.33,  # +0.33%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 3: Slight move down
    results.append(("Slight Down (-0.33%)", analyze_scenario(
        "SCENARIO 3: Slight Move Down (-0.33%)",
        spy_entry, spx_entry,
        -0.33,  # -0.33%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 4: Moderate move up
    results.append(("Moderate Up (+1%)", analyze_scenario(
        "SCENARIO 4: Moderate Move Up (+1%)",
        spy_entry, spx_entry,
        1.0,  # +1%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 5: Moderate move down
    results.append(("Moderate Down (-1%)", analyze_scenario(
        "SCENARIO 5: Moderate Move Down (-1%)",
        spy_entry, spx_entry,
        -1.0,  # -1%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 6: Large move up
    results.append(("Large Up (+2%)", analyze_scenario(
        "SCENARIO 6: Large Move Up (+2%) - Volatile Day",
        spy_entry, spx_entry,
        2.0,  # +2%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 7: Large move down
    results.append(("Large Down (-2%)", analyze_scenario(
        "SCENARIO 7: Large Move Down (-2%) - Volatile Day",
        spy_entry, spx_entry,
        -2.0,  # -2%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 8: Very large move up
    results.append(("Very Large Up (+3%)", analyze_scenario(
        "SCENARIO 8: Very Large Move Up (+3%) - Major Rally",
        spy_entry, spx_entry,
        3.0,  # +3%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Scenario 9: Very large move down
    results.append(("Very Large Down (-3%)", analyze_scenario(
        "SCENARIO 9: Very Large Move Down (-3%) - Major Selloff",
        spy_entry, spx_entry,
        -3.0,  # -3%
        spy_call, spx_call, spy_put, spx_put
    )))

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY OF ALL SCENARIOS (REALISTIC TRACKING)")
    print(f"{'='*80}")

    for name, pnl in results:
        status = "✅ PROFIT" if pnl > 0 else "❌ LOSS"
        print(f"{name:30} ${pnl:+10,.2f}  {status}")

    print(f"\n{'='*80}")
    print("KEY INSIGHTS WITH REALISTIC TRACKING")
    print(f"{'='*80}")
    print("""
🎯 THE CORE EDGE:
   When SPY and SPX track perfectly (same %), the settlement P&L ≈ $0
   You keep the FULL entry credit as profit!

📊 WHAT REALLY HAPPENS:

   Structure: SELL 10 SPY, BUY 1 SPX (both calls & puts)

   When price moves (same % for both):
   - If UP: Calls go ITM
     * You lose on 10 SHORT SPY calls
     * You gain on 1 LONG SPX call
     * These roughly cancel out (SPX ≈ 10 × SPY)
     * Puts expire worthless

   - If DOWN: Puts go ITM
     * You lose on 10 SHORT SPY puts
     * You gain on 1 LONG SPX put
     * These roughly cancel out (SPX ≈ 10 × SPY)
     * Calls expire worthless

   - If SIDEWAYS: Both expire worthless
     * Keep full credit

💡 WHY IT WORKS:
   1. SPX ≈ 10 × SPY (by design)
   2. Your positions are balanced: 10 SPY vs 1 SPX
   3. When tracking is perfect → settlement ≈ $0
   4. Entry credit = pure profit

⚠️  THE REAL RISK:
   - Tracking error (SPY/SPX ratio changes)
   - Assignment risk on SPY (American style)
   - Gap risk at market open/close
   - Pin risk near strikes at expiration

🎲 WIN RATE:
   High! As long as:
   - No major tracking disruption
   - No early assignment
   - Exit before settlement if too deep ITM
""")

    # Calculate average profit
    avg_pnl = sum(pnl for _, pnl in results) / len(results)
    print(f"\n📈 Average P&L across all scenarios: ${avg_pnl:,.2f}")
    print(f"   (Expected daily profit if all days are equally likely)")


if __name__ == "__main__":
    main()
