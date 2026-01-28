#!/usr/bin/env python3
"""
Hold-to-Expiration Strategy Analysis
What if you DON'T close early, but let both sides settle?
"""

def analyze_hold_to_expiration():
    """
    Analyze what happens if you hold SPY/SPX spread to expiration
    """

    print("=" * 80)
    print("HOLD-TO-EXPIRATION STRATEGY ANALYSIS")
    print("=" * 80)

    print("\n🎯 THE KEY INSIGHT:")
    print("If you hold to expiration, you DON'T pay exit bid-ask spreads!")
    print("Settlement is automatic - no trading needed.")

    # Example setup
    spy_price = 600.00
    spx_price = 6005.00
    strike = 600  # ATM

    # Entry prices (from our earlier analysis)
    spy_call_ask = 3.01
    spx_call_bid = 23.05

    print("\n" + "=" * 80)
    print("ENTRY (Today)")
    print("=" * 80)

    print(f"\nCurrent Prices:")
    print(f"  SPY: ${spy_price:.2f}")
    print(f"  SPX: ${spx_price:.2f}")

    print(f"\nThe Trade (for {strike} strike):")
    print(f"  Buy 10 SPY {strike} calls @ ${spy_call_ask:.2f} ask")
    print(f"  Sell 1 SPX {strike*10} call @ ${spx_call_bid:.2f} bid")

    # Calculate entry cost
    spy_cost = spy_call_ask * 10 * 100  # 10 contracts, $100 multiplier
    spx_credit = spx_call_bid * 100  # 1 contract, $100 multiplier

    net_debit = spy_cost - spx_credit
    commissions_entry = 11 * 0.65
    total_entry_cost = net_debit + commissions_entry

    print(f"\nEntry Costs:")
    print(f"  Pay for SPY calls:  ${spy_cost:,.2f}")
    print(f"  Receive for SPX:    ${spx_credit:,.2f}")
    print(f"  Net debit:          ${net_debit:,.2f}")
    print(f"  Commissions:        ${commissions_entry:.2f}")
    print(f"  ────────────────────────────────")
    print(f"  Total cost to enter: ${total_entry_cost:,.2f}")

    print("\n" + "=" * 80)
    print("EXPIRATION (Friday)")
    print("=" * 80)

    # Scenario 1: Both expire ITM
    expiration_price_spy = 620.00
    expiration_price_spx = 6200.00  # Assume perfect 10:1 tracking

    print(f"\nScenario 1: Market rallies to SPY ${expiration_price_spy}, SPX ${expiration_price_spx}")
    print("-" * 80)

    # SPY settlement (automatic exercise)
    spy_intrinsic = expiration_price_spy - strike
    spy_profit_per_call = spy_intrinsic * 100  # $100 multiplier
    spy_total_profit = spy_profit_per_call * 10  # 10 contracts

    # SPX settlement (cash settled)
    spx_strike = strike * 10
    spx_intrinsic = expiration_price_spx - spx_strike
    spx_loss = spx_intrinsic * 100  # You're SHORT, so this is a loss

    print(f"\nSPY Calls (Long 10 contracts):")
    print(f"  Strike: ${strike}")
    print(f"  Expiration: ${expiration_price_spy}")
    print(f"  Intrinsic value: ${spy_intrinsic} per share")
    print(f"  Profit per call: ${spy_profit_per_call:,.2f}")
    print(f"  Total profit: ${spy_total_profit:,.2f} ✅")

    print(f"\nSPX Call (Short 1 contract):")
    print(f"  Strike: ${spx_strike}")
    print(f"  Expiration: ${expiration_price_spx}")
    print(f"  Intrinsic value: ${spx_intrinsic}")
    print(f"  Cash settlement: ${spx_loss:,.2f} (you pay) ❌")

    net_pnl = spy_total_profit - spx_loss - total_entry_cost

    print(f"\n📊 NET P&L:")
    print(f"  SPY profit:      +${spy_total_profit:,.2f}")
    print(f"  SPX loss:        -${spx_loss:,.2f}")
    print(f"  Entry costs:     -${total_entry_cost:,.2f}")
    print(f"  ────────────────────────────────")
    print(f"  NET RESULT:       ${net_pnl:,.2f}")

    print("\n💡 KEY OBSERVATION:")
    if abs(net_pnl) < 100:
        print(f"  With perfect 10:1 tracking, you roughly BREAK EVEN!")
        print(f"  You only lose your entry costs (${total_entry_cost:,.2f})")

    # Scenario 2: Price doesn't move (both expire worthless)
    print("\n" + "=" * 80)
    print(f"Scenario 2: Market stays flat at SPY ${spy_price}, SPX ${spx_price}")
    print("-" * 80)

    print(f"\nBoth options expire worthless (OTM)")
    print(f"  SPY calls: Expire worthless, you lose ${spy_cost:,.2f}")
    print(f"  SPX call: Expires worthless, you keep ${spx_credit:,.2f}")
    print(f"  Net: -${net_debit:,.2f} - ${commissions_entry:.2f} = -${total_entry_cost:,.2f}")

    # Scenario 3: Market drops
    expiration_price_down_spy = 580.00
    expiration_price_down_spx = 5800.00

    print("\n" + "=" * 80)
    print(f"Scenario 3: Market drops to SPY ${expiration_price_down_spy}, SPX ${expiration_price_down_spx}")
    print("-" * 80)

    print(f"\nBoth options expire worthless (OTM)")
    print(f"  Your loss: ${total_entry_cost:,.2f} (entry cost only)")

    # THE CRITICAL ISSUE: Tracking error
    print("\n" + "=" * 80)
    print("🚨 THE CRITICAL RISK: TRACKING ERROR")
    print("=" * 80)

    print("\nWhat if SPX and SPY DON'T track at exactly 10:1?")
    print("-" * 80)

    # Scenario 4: Tracking error
    expiration_spy_4 = 620.00
    expiration_spx_4 = 6210.00  # SPX is $10 higher than expected!

    print(f"\nScenario 4: Tracking error at expiration")
    print(f"  SPY expires at: ${expiration_spy_4}")
    print(f"  SPX expires at: ${expiration_spx_4} (expected ${expiration_spy_4 * 10})")
    print(f"  Tracking error: ${expiration_spx_4 - (expiration_spy_4 * 10):.2f}")

    spy_profit_4 = (expiration_spy_4 - strike) * 100 * 10
    spx_loss_4 = (expiration_spx_4 - spx_strike) * 100

    net_pnl_4 = spy_profit_4 - spx_loss_4 - total_entry_cost

    print(f"\n  SPY profit: ${spy_profit_4:,.2f}")
    print(f"  SPX loss: ${spx_loss_4:,.2f}")
    print(f"  Net P&L: ${net_pnl_4:,.2f}")
    print(f"\n  Tracking error cost you: ${abs(net_pnl_4 - net_pnl):,.2f}!")

    # THE BIGGEST RISK
    print("\n" + "=" * 80)
    print("☠️  THE BIGGEST RISK: SETTLEMENT TIMING")
    print("=" * 80)

    print("\n⚠️  CRITICAL DIFFERENCE:")
    print("  SPX: Settles at FRIDAY OPENING PRICE (AM settlement)")
    print("  SPY: Settles at FRIDAY CLOSING PRICE (PM settlement)")
    print("\n  That's 6.5 HOURS of market movement between settlements!")

    print("\n💀 NIGHTMARE SCENARIO:")
    print("-" * 80)
    print("  Thursday 4pm: Market closes at SPY $620, SPX $6200")
    print("  Friday 9:30am: Market GAPS DOWN to $6150 (SPX settlement)")
    print("                 → Your short SPX call settles at $15k loss")
    print("  Friday 4:00pm: Market RECOVERS to $625 (SPY settlement)")
    print("                 → Your long SPY calls settle at $25k profit")
    print("\n  You got lucky! But it could easily go the other way:")
    print("\n  Friday 9:30am: SPX opens at $6250 (gap up)")
    print("                 → Your short SPX call: $25k loss")
    print("  Friday 4:00pm: SPY closes at $615 (dropped during day)")
    print("                 → Your long SPY calls: $15k profit")
    print("\n  NET LOSS: $10,000 from settlement timing alone!")

    print("\n" + "=" * 80)
    print("📊 SUMMARY: DOES THIS STRATEGY WORK?")
    print("=" * 80)

    print("\n✅ WHAT YOU GOT RIGHT:")
    print("  1. Holding to expiration avoids exit bid-ask spreads")
    print("  2. If SPX and SPY track perfectly, you break even (minus entry)")
    print("  3. Entry cost is much lower than constant trading")

    print("\n❌ WHAT KILLS THIS STRATEGY:")
    print("  1. SETTLEMENT TIMING: 6.5 hours between SPX and SPY settlement")
    print("     → Massive gap risk on Friday")
    print("  2. TRACKING ERROR: SPX ≠ 10x SPY (can be $5-20 different)")
    print("     → Each $1 tracking error = $100 profit/loss")
    print("  3. ENTRY COSTS: Still need $700+ to enter")
    print("     → All scenarios lose at least this much")

    print("\n📈 EXPECTED VALUE:")
    print(f"  Best case (perfect tracking): -${total_entry_cost:,.2f}")
    print(f"  Typical case (small tracking error): -${total_entry_cost + 500:,.2f}")
    print(f"  Worst case (settlement timing): -${total_entry_cost + 5000:,.2f}+")

    print("\n💡 THE VERDICT:")
    print("  Better than constant trading (saves exit costs)")
    print("  But still NOT profitable due to:")
    print("    • Entry costs ($700+)")
    print("    • Settlement timing risk (6.5 hour gap)")
    print("    • Tracking error")

    print("\n  You're essentially paying $700+ for a coin flip on settlement timing.")

    print("\n" + "=" * 80)
    print("🎓 WHAT PROFESSIONALS DO INSTEAD")
    print("=" * 80)

    print("\nMarket makers CAN profit from this because they:")
    print("  1. Pay $0.10/contract (vs your $0.65)")
    print("  2. Can hedge intraday during Friday's session")
    print("  3. Have direct exchange access (no slippage)")
    print("  4. Do thousands of these trades (law of large numbers)")

    print("\nFor retail traders:")
    print("  → This is BETTER than your original idea (constant trading)")
    print("  → But still not profitable due to costs and timing risk")
    print("  → Settlement timing risk alone can wipe you out")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_hold_to_expiration()
