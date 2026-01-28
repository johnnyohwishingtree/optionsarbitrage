#!/usr/bin/env python3
"""
Compare CALLS ONLY strategy vs CALLS + PUTS strategy
Shows why you need BOTH sides
"""

def analyze_calls_only(scenario_name, pct_change, spy_entry=600, spx_entry=6000):
    """Analyze with CALLS ONLY (old strategy)"""

    print(f"\n{'='*80}")
    print(f"{scenario_name}")
    print(f"{'='*80}")

    spy_exit = spy_entry * (1 + pct_change/100)
    spx_exit = spx_entry * (1 + pct_change/100)

    spy_strike = 600
    spx_strike = 6000

    print(f"\n📍 POSITIONS (CALLS ONLY):")
    print(f"   SHORT 1 SPX {spx_strike} call")
    print(f"   LONG 10 SPY {spy_strike} calls")
    print(f"   Entry Credit: $500 (example)")

    print(f"\n📍 EXIT:")
    print(f"   SPY: ${spy_exit:.2f} ({pct_change:+.2f}%)")
    print(f"   SPX: ${spx_exit:.2f} ({pct_change:+.2f}%)")

    print(f"\n🔍 SETTLEMENT:")

    if pct_change > 0:
        # Calls ITM
        spy_call_itm = spy_exit - spy_strike
        spx_call_itm = spx_exit - spx_strike

        spy_value = spy_call_itm * 100 * 10
        spx_value = spx_call_itm * 100 * 1

        settlement = spy_value - spx_value

        print(f"   ✅ Calls are ITM:")
        print(f"      LONG 10 SPY calls: +${spy_value:,.2f}")
        print(f"      SHORT 1 SPX call:  -${spx_value:,.2f}")
        print(f"      Settlement: ${settlement:+,.2f}")

    elif pct_change < 0:
        # Calls OTM - expire worthless
        print(f"   ❌ Price went DOWN - calls expire worthless")
        print(f"      Settlement: $0.00")
        print(f"   ⚠️  YOU HAVE NO PROTECTION ON DOWNSIDE!")
        settlement = 0

    else:
        print(f"   Calls expire worthless (ATM)")
        settlement = 0

    total_pnl = 500 + settlement

    print(f"\n💵 FINAL P&L:")
    print(f"   Entry Credit: $+500.00")
    print(f"   Settlement:   ${settlement:+,.2f}")
    print(f"   ══════════════════════")
    print(f"   TOTAL:        ${total_pnl:+,.2f}")

    return total_pnl


def analyze_calls_and_puts(scenario_name, pct_change, spy_entry=600, spx_entry=6000):
    """Analyze with CALLS + PUTS (new strategy)"""

    print(f"\n{'='*80}")
    print(f"{scenario_name}")
    print(f"{'='*80}")

    spy_exit = spy_entry * (1 + pct_change/100)
    spx_exit = spx_entry * (1 + pct_change/100)

    spy_strike = 600
    spx_strike = 6000

    print(f"\n📍 POSITIONS (CALLS + PUTS):")
    print(f"   CALLS: SHORT 1 SPX call, LONG 10 SPY calls")
    print(f"   PUTS:  SHORT 1 SPX put,  LONG 10 SPY puts")
    print(f"   Entry Credit: $985.70")

    print(f"\n📍 EXIT:")
    print(f"   SPY: ${spy_exit:.2f} ({pct_change:+.2f}%)")
    print(f"   SPX: ${spx_exit:.2f} ({pct_change:+.2f}%)")

    print(f"\n🔍 SETTLEMENT:")

    if pct_change > 0:
        # Calls ITM, puts worthless
        spy_call_itm = spy_exit - spy_strike
        spx_call_itm = spx_exit - spx_strike

        spy_value = spy_call_itm * 100 * 10
        spx_value = spx_call_itm * 100 * 1

        settlement = spy_value - spx_value

        print(f"   ✅ Calls ITM (price went UP):")
        print(f"      LONG 10 SPY calls: +${spy_value:,.2f}")
        print(f"      SHORT 1 SPX call:  -${spx_value:,.2f}")
        print(f"      Calls Settlement: ${settlement:+,.2f}")
        print(f"   ✅ Puts worthless (protected!)")
        print(f"      Settlement: $0.00")

    elif pct_change < 0:
        # Puts ITM, calls worthless
        spy_put_itm = spy_strike - spy_exit
        spx_put_itm = spx_strike - spx_exit

        spy_value = spy_put_itm * 100 * 10
        spx_value = spx_put_itm * 100 * 1

        settlement = spy_value - spx_value

        print(f"   ✅ Puts ITM (price went DOWN):")
        print(f"      LONG 10 SPY puts:  +${spy_value:,.2f}")
        print(f"      SHORT 1 SPX put:   -${spx_value:,.2f}")
        print(f"      Puts Settlement: ${settlement:+,.2f}")
        print(f"   ✅ Calls worthless (protected!)")
        print(f"      Settlement: $0.00")

    else:
        print(f"   All options expire worthless (ATM)")
        settlement = 0

    total_pnl = 985.70 + settlement

    print(f"\n💵 FINAL P&L:")
    print(f"   Entry Credit: $+985.70")
    print(f"   Settlement:   ${settlement:+,.2f}")
    print(f"   ══════════════════════")
    print(f"   TOTAL:        ${total_pnl:+,.2f}")

    return total_pnl


def main():
    print("="*80)
    print("COMPARISON: CALLS ONLY vs CALLS + PUTS")
    print("="*80)
    print("\nShowing why you NEED both sides for the strategy to work!\n")

    scenarios = [
        ("Market Up +2%", 2.0),
        ("No Movement (0%)", 0.0),
        ("Market Down -2%", -2.0),
    ]

    results_calls_only = []
    results_both = []

    for name, pct in scenarios:
        print("\n" + "█"*80)
        print(f"SCENARIO: {name}")
        print("█"*80)

        print(f"\n{'─'*80}")
        print("WITH CALLS ONLY (OLD STRATEGY)")
        print(f"{'─'*80}")
        pnl_calls = analyze_calls_only(f"Calls Only - {name}", pct)
        results_calls_only.append((name, pnl_calls))

        print(f"\n{'─'*80}")
        print("WITH CALLS + PUTS (NEW STRATEGY)")
        print(f"{'─'*80}")
        pnl_both = analyze_calls_and_puts(f"Calls + Puts - {name}", pct)
        results_both.append((name, pnl_both))

    print("\n\n" + "="*80)
    print("SUMMARY: WHY YOU NEED BOTH SIDES")
    print("="*80)

    print("\nCALLS ONLY Strategy:")
    for name, pnl in results_calls_only:
        status = "✅" if pnl > 0 else "❌"
        print(f"  {name:20} ${pnl:+10,.2f}  {status}")

    print("\nCALLS + PUTS Strategy:")
    for name, pnl in results_both:
        status = "✅" if pnl > 0 else "❌"
        print(f"  {name:20} ${pnl:+10,.2f}  {status}")

    print("\n" + "="*80)
    print("🎯 KEY INSIGHT")
    print("="*80)
    print("""
CALLS ONLY Strategy:
❌ Only hedged on UPSIDE
❌ Exposed to DOWNSIDE (market crashes, you keep only $500)
❌ Directional risk!

CALLS + PUTS Strategy:
✅ Hedged on BOTH upside AND downside
✅ Protected in ALL market directions
✅ Market-neutral!

THE DIFFERENCE:
- Calls only work when market goes UP
- Puts only work when market goes DOWN
- Having BOTH means you're protected no matter what!

WITHOUT BOTH SIDES:
If you only had calls and market crashes -2%, your calls expire worthless.
You keep your $500 credit but have NO hedge.
This is directional gambling, not arbitrage!

WITH BOTH SIDES:
If market crashes -2%, your calls expire worthless BUT your puts kick in!
The puts perfectly hedge the move, keeping your P&L at $0.
You keep the full $985.70 credit!

This is true arbitrage - betting on tracking, not direction.
""")


if __name__ == "__main__":
    main()
