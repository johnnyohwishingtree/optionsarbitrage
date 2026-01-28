#!/usr/bin/env python3
"""
Show where CALLS ONLY strategy actually LOSES money
The key is what structure you have (sell SPY vs sell SPX)
"""

def analyze_sell_spy_calls(scenario_name, pct_change):
    """Structure: SELL 10 SPY calls, BUY 1 SPX call"""

    print(f"\n{'='*80}")
    print(f"{scenario_name}")
    print(f"{'='*80}")

    spy_entry = 600.0
    spx_entry = 6000.0
    spy_exit = spy_entry * (1 + pct_change/100)
    spx_exit = spx_entry * (1 + pct_change/100)

    spy_strike = 600
    spx_strike = 6000

    print(f"\n📍 STRUCTURE: SELL 10 SPY calls, BUY 1 SPX call")
    print(f"   (This is what historical data showed - SPY calls were more expensive)")

    print(f"\n💰 ENTRY:")
    print(f"   You SELL 10 SPY {spy_strike} calls @ $2.50 each = Collect $2,500")
    print(f"   You BUY 1 SPX {spx_strike} call @ $30.00     = Pay $3,000")
    print(f"   Net: You PAY $500 to enter (DEBIT spread)")
    print(f"   Entry Cost: -$500")

    print(f"\n📍 EXIT ({pct_change:+.1f}% move):")
    print(f"   SPY: ${spy_exit:.2f}")
    print(f"   SPX: ${spx_exit:.2f}")

    if pct_change > 0:
        # Calls go ITM
        spy_call_itm = spy_exit - spy_strike
        spx_call_itm = spx_exit - spx_strike

        spy_loss = spy_call_itm * 100 * 10  # You're SHORT, you lose
        spx_gain = spx_call_itm * 100 * 1   # You're LONG, you gain

        settlement = spx_gain - spy_loss

        print(f"\n🔍 SETTLEMENT (Market UP):")
        print(f"   Your SHORT 10 SPY calls (you OWE): -${spy_loss:,.2f}")
        print(f"   Your LONG 1 SPX call (you GET):    +${spx_gain:,.2f}")
        print(f"   Settlement: ${settlement:+,.2f}")

    else:
        # Calls expire worthless
        settlement = 0
        print(f"\n🔍 SETTLEMENT (Market DOWN):")
        print(f"   All calls expire worthless")
        print(f"   Settlement: $0.00")

    total_pnl = -500 + settlement  # Note: -500 entry cost

    print(f"\n💵 FINAL P&L:")
    print(f"   Entry Cost:   -$500.00  (you PAID to enter)")
    print(f"   Settlement:   ${settlement:+,.2f}")
    print(f"   ══════════════════════════")
    print(f"   TOTAL P&L:    ${total_pnl:+,.2f}")

    return total_pnl


def analyze_sell_spx_calls(scenario_name, pct_change):
    """Structure: SELL 1 SPX call, BUY 10 SPY calls"""

    print(f"\n{'='*80}")
    print(f"{scenario_name}")
    print(f"{'='*80}")

    spy_entry = 600.0
    spx_entry = 6000.0
    spy_exit = spy_entry * (1 + pct_change/100)
    spx_exit = spx_entry * (1 + pct_change/100)

    spy_strike = 600
    spx_strike = 6000

    print(f"\n📍 STRUCTURE: SELL 1 SPX call, BUY 10 SPY calls")
    print(f"   (Alternative scenario - if SPX call was more expensive)")

    print(f"\n💰 ENTRY:")
    print(f"   You SELL 1 SPX {spx_strike} call @ $30.00     = Collect $3,000")
    print(f"   You BUY 10 SPY {spy_strike} calls @ $2.50 each = Pay $2,500")
    print(f"   Net: You COLLECT $500 (CREDIT spread)")
    print(f"   Entry Credit: +$500")

    print(f"\n📍 EXIT ({pct_change:+.1f}% move):")
    print(f"   SPY: ${spy_exit:.2f}")
    print(f"   SPX: ${spx_exit:.2f}")

    if pct_change > 0:
        # Calls go ITM
        spy_call_itm = spy_exit - spy_strike
        spx_call_itm = spx_exit - spx_strike

        spy_gain = spy_call_itm * 100 * 10  # You're LONG, you gain
        spx_loss = spx_call_itm * 100 * 1   # You're SHORT, you lose

        settlement = spy_gain - spx_loss

        print(f"\n🔍 SETTLEMENT (Market UP):")
        print(f"   Your LONG 10 SPY calls (you GET):  +${spy_gain:,.2f}")
        print(f"   Your SHORT 1 SPX call (you OWE):   -${spx_loss:,.2f}")
        print(f"   Settlement: ${settlement:+,.2f}")

    else:
        # Calls expire worthless
        settlement = 0
        print(f"\n🔍 SETTLEMENT (Market DOWN):")
        print(f"   All calls expire worthless")
        print(f"   Settlement: $0.00")

    total_pnl = 500 + settlement  # Note: +500 entry credit

    print(f"\n💵 FINAL P&L:")
    print(f"   Entry Credit: +$500.00  (you COLLECTED at entry)")
    print(f"   Settlement:   ${settlement:+,.2f}")
    print(f"   ══════════════════════════")
    print(f"   TOTAL P&L:    ${total_pnl:+,.2f}")

    return total_pnl


def main():
    print("="*80)
    print("CALLS ONLY: WHERE YOU ACTUALLY LOSE MONEY")
    print("="*80)
    print("\nThe answer depends on which side is more expensive!")
    print("Historical data shows: SPY calls > SPX calls (in dollar terms)")
    print("So you would SELL SPY and BUY SPX")

    scenarios = [
        ("Market Up +2%", 2.0),
        ("No Movement", 0.0),
        ("Market Down -2%", -2.0),
    ]

    print("\n\n" + "█"*80)
    print("STRUCTURE 1: SELL 10 SPY calls, BUY 1 SPX call")
    print("(This is what really happens - SPY calls are more expensive)")
    print("█"*80)

    results1 = []
    for name, pct in scenarios:
        pnl = analyze_sell_spy_calls(f"SELL SPY - {name}", pct)
        results1.append((name, pnl))

    print("\n\n" + "█"*80)
    print("STRUCTURE 2: SELL 1 SPX call, BUY 10 SPY calls")
    print("(Hypothetical - if SPX call was more expensive)")
    print("█"*80)

    results2 = []
    for name, pct in scenarios:
        pnl = analyze_sell_spx_calls(f"SELL SPX - {name}", pct)
        results2.append((name, pnl))

    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print("\nStructure 1: SELL SPY calls, BUY SPX call (REAL scenario)")
    for name, pnl in results1:
        status = "✅" if pnl > 0 else "❌"
        print(f"  {name:20} ${pnl:+10,.2f}  {status}")

    print("\nStructure 2: SELL SPX call, BUY SPY calls (Hypothetical)")
    for name, pnl in results2:
        status = "✅" if pnl > 0 else "❌"
        print(f"  {name:20} ${pnl:+10,.2f}  {status}")

    print("\n" + "="*80)
    print("🎯 THE REAL ISSUE WITH CALLS ONLY")
    print("="*80)
    print("""
Based on REAL historical data:
- 10 SPY calls cost MORE than 1 SPX call (e.g., $25 vs $30 total)
- So you would SELL the expensive SPY calls and BUY the cheap SPX call
- This is a DEBIT spread (you PAY $500 to enter)

What happens:
✅ Market UP +2%:   LOSE $500 (settlement = $0, you paid $500 to enter)
✅ Sideways:        LOSE $500 (all expire worthless, you paid $500)
❌ Market DOWN -2%: LOSE $500 (all expire worthless, you paid $500)

YOU ALWAYS LOSE $500!

This is because you're buying a spread that doesn't pay off.
The hedge is perfect (settlement = $0) but you PAID for it.

Compare to CALLS + PUTS:
- You COLLECT $985.70 at entry (not pay!)
- Settlement = $0 (hedged)
- You KEEP the $985.70

The double-sided strategy works because:
1. You collect credit on BOTH the calls side AND puts side
2. Total entry credit is positive ($985.70)
3. When hedged positions settle to $0, you keep the credit

With calls only:
1. You might collect credit on calls OR pay a debit
2. In reality (based on prices), you PAY a debit
3. Even though positions hedge to $0, you're down the debit amount
""")


if __name__ == "__main__":
    main()
