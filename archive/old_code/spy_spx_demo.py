#!/usr/bin/env python3
"""
SPY vs SPX Options Demo with Realistic Data
Shows what arbitrage analysis looks like with real market conditions
"""

import pandas as pd
import numpy as np


def generate_realistic_options_data():
    """
    Generate realistic options data based on actual market conditions
    Data modeled after typical SPY/SPX pricing patterns
    """

    # Current prices (typical mid-day values)
    spy_price = 600.00
    spx_price = 6005.00  # Slightly more than 10x (this is realistic!)

    print("=" * 70)
    print("SPY vs SPX OPTIONS ARBITRAGE ANALYSIS")
    print("Using Realistic Market Data")
    print("=" * 70)
    print(f"\nCurrent Prices:")
    print(f"  SPY: ${spy_price:.2f}")
    print(f"  SPX: ${spx_price:.2f}")
    print(f"  Ratio: {spx_price / spy_price:.4f}x (vs expected 10.0000x)")
    print(f"  Index premium: ${spx_price - (spy_price * 10):.2f}")

    # Generate realistic call options data
    # SPY strikes around $600
    spy_strikes = [595, 597, 599, 600, 601, 603, 605]

    results = []

    for spy_strike in spy_strikes:
        # Calculate realistic option prices
        # Using simplified Black-Scholes-ish pricing

        moneyness_spy = (spy_price - spy_strike)
        spx_strike = spy_strike * 10

        # SPY option pricing (tight $0.01 spreads)
        if moneyness_spy > 0:  # ITM
            spy_intrinsic = moneyness_spy
            spy_extrinsic = max(0.50, 2.0 - abs(moneyness_spy) * 0.2)
            spy_mid = spy_intrinsic + spy_extrinsic
        else:  # OTM
            spy_intrinsic = 0
            spy_extrinsic = max(0.10, 3.0 - abs(moneyness_spy) * 0.3)
            spy_mid = spy_extrinsic

        spy_bid = spy_mid - 0.01
        spy_ask = spy_mid + 0.01

        # SPX option pricing (wider ~$0.40 spreads)
        # Key insight: SPX options trade slightly different due to:
        # 1. European vs American exercise
        # 2. Tax advantages (Section 1256)
        # 3. Dividend considerations
        # 4. Wider spreads

        moneyness_spx = (spx_price - spx_strike)

        if moneyness_spx > 0:  # ITM
            spx_intrinsic = moneyness_spx
            # European options trade at discount to intrinsic (cost of carry)
            spx_extrinsic = max(5.0, 20.0 - abs(moneyness_spx) * 0.15)
            spx_mid = spx_intrinsic + spx_extrinsic - 1.0  # Discount for cost of carry
        else:  # OTM
            spx_intrinsic = 0
            spx_extrinsic = max(1.0, 30.0 - abs(moneyness_spx) * 0.25)
            spx_mid = spx_extrinsic * 1.02  # Slight premium for tax advantages

        spx_bid = spx_mid - 0.20
        spx_ask = spx_mid + 0.20

        # Calculate expected SPX price (simply 10x SPY)
        expected_spx_mid = spy_mid * 10

        # Actual discrepancy
        discrepancy_dollars = spx_mid - expected_spx_mid
        discrepancy_pct = (discrepancy_dollars / expected_spx_mid) * 100

        # Arbitrage strategies
        # Strategy 1: Sell SPX, Buy 10x SPY (if SPX overpriced)
        # Strategy 2: Buy SPX, Sell 10x SPY (if SPX underpriced)

        if discrepancy_dollars > 0:
            # SPX is more expensive
            strategy = "Sell 1 SPX, Buy 10 SPY"
            # You receive SPX bid, pay SPY ask
            gross_profit = spx_bid - (spy_ask * 10)
        else:
            # SPX is cheaper
            strategy = "Buy 1 SPX, Sell 10 SPY"
            # You pay SPX ask, receive SPY bid
            gross_profit = (spy_bid * 10) - spx_ask

        # Transaction costs
        commission_per_leg = 0.65
        total_commissions = 11 * commission_per_leg  # 11 legs total
        exchange_fees = 11 * 0.05  # ~$0.05 per contract
        slippage = 0.50  # Realistic slippage on execution

        total_costs = total_commissions + exchange_fees + slippage

        net_profit = gross_profit - total_costs

        results.append({
            'SPY_Strike': spy_strike,
            'SPX_Strike': spx_strike,
            'SPY_Bid': f"${spy_bid:.2f}",
            'SPY_Ask': f"${spy_ask:.2f}",
            'SPY_Mid': spy_mid,
            'SPY_Spread': spy_ask - spy_bid,
            'SPX_Bid': f"${spx_bid:.2f}",
            'SPX_Ask': f"${spx_ask:.2f}",
            'SPX_Mid': spx_mid,
            'SPX_Spread': spx_ask - spx_bid,
            'Expected_SPX': expected_spx_mid,
            'Discrepancy_$': discrepancy_dollars,
            'Discrepancy_%': discrepancy_pct,
            'Strategy': strategy,
            'Gross_Profit': gross_profit,
            'Commissions': total_commissions,
            'Fees': exchange_fees,
            'Slippage': slippage,
            'Total_Costs': total_costs,
            'Net_Profit': net_profit,
            'Profitable?': '✅' if net_profit > 0 else '❌'
        })

    return pd.DataFrame(results)


def print_detailed_analysis(df):
    """Print detailed analysis of opportunities"""

    print("\n" + "=" * 70)
    print("DETAILED COMPARISON")
    print("=" * 70)

    # Show sample calculations for one strike
    sample = df.iloc[3]  # ATM option

    print(f"\n📊 EXAMPLE: {sample['SPY_Strike']} Strike (At-The-Money)")
    print("-" * 70)
    print(f"SPY Option:")
    print(f"  Bid: {sample['SPY_Bid']}  |  Ask: {sample['SPY_Ask']}  |  Spread: ${sample['SPY_Spread']:.2f}")
    print(f"\nSPX Option:")
    print(f"  Bid: {sample['SPX_Bid']}  |  Ask: {sample['SPX_Ask']}  |  Spread: ${sample['SPX_Spread']:.2f}")
    print(f"\nExpected vs Actual:")
    print(f"  Expected SPX (10x SPY mid): ${sample['Expected_SPX']:.2f}")
    print(f"  Actual SPX mid:             ${sample['SPX_Mid']:.2f}")
    print(f"  Discrepancy:                ${sample['Discrepancy_$']:.2f} ({sample['Discrepancy_%']:.2f}%)")

    print(f"\n💰 Arbitrage Calculation:")
    print(f"  Strategy: {sample['Strategy']}")
    print(f"  Gross profit:    ${sample['Gross_Profit']:.2f}")
    print(f"  Less:")
    print(f"    Commissions:   ${sample['Commissions']:.2f} (11 contracts x $0.65)")
    print(f"    Exchange fees: ${sample['Fees']:.2f}")
    print(f"    Slippage:      ${sample['Slippage']:.2f}")
    print(f"  Total costs:     ${sample['Total_Costs']:.2f}")
    print(f"  ───────────────────")
    print(f"  NET PROFIT:      ${sample['Net_Profit']:.2f} {sample['Profitable?']}")

    print("\n" + "=" * 70)
    print("ALL STRIKES COMPARISON")
    print("=" * 70)

    # Print summary table
    print(f"\n{'Strike':<8} {'Discrepancy':<12} {'Gross':<10} {'Costs':<10} {'Net':<10} {'Result':<8}")
    print("-" * 70)

    for _, row in df.iterrows():
        print(f"${row['SPY_Strike']:<7.0f} "
              f"{row['Discrepancy_%']:>6.2f}%      "
              f"${row['Gross_Profit']:>7.2f}   "
              f"${row['Total_Costs']:>7.2f}   "
              f"${row['Net_Profit']:>7.2f}   "
              f"{row['Profitable?']}")

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    profitable = df[df['Net_Profit'] > 0]
    print(f"\nOpportunities analyzed: {len(df)}")
    print(f"Profitable after costs: {len(profitable)} ({len(profitable)/len(df)*100:.1f}%)")

    if len(profitable) > 0:
        print(f"\n✅ PROFITABLE OPPORTUNITIES FOUND:")
        print(f"  Total net profit available: ${profitable['Net_Profit'].sum():.2f}")
        print(f"  Best opportunity: ${profitable['Net_Profit'].max():.2f}")
        print(f"  Average profit per trade: ${profitable['Net_Profit'].mean():.2f}")

        print(f"\n💡 With $10K capital:")
        capital = 10000
        # Assume each trade requires ~$500 in margin for the spread
        num_trades = capital // 500
        potential_profit = num_trades * profitable['Net_Profit'].mean()
        print(f"  Can execute ~{num_trades} simultaneous spreads")
        print(f"  Potential profit: ${potential_profit:.2f}")
        print(f"  Return: {potential_profit/capital*100:.2f}%")
    else:
        print(f"\n❌ NO PROFITABLE OPPORTUNITIES")
        print(f"  Average net loss: ${df['Net_Profit'].mean():.2f}")

        # Show what kills the profit
        avg_gross = df['Gross_Profit'].mean()
        avg_costs = df['Total_Costs'].mean()
        print(f"\n  Why no profit:")
        print(f"    Average gross profit: ${avg_gross:.2f}")
        print(f"    Average costs: ${avg_costs:.2f}")
        print(f"    Costs eat {avg_costs/abs(avg_gross)*100:.1f}% of gross profit")

    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)

    print("\n1. BID-ASK SPREADS:")
    avg_spy_spread = df['SPY_Spread'].mean()
    avg_spx_spread = df['SPX_Spread'].mean()
    print(f"   SPY spread: ${avg_spy_spread:.2f} (very tight)")
    print(f"   SPX spread: ${avg_spx_spread:.2f} ({avg_spx_spread/avg_spy_spread:.0f}x wider!)")
    print(f"   → The wide SPX spread kills most arbitrage opportunities")

    print("\n2. TRANSACTION COSTS:")
    print(f"   11 contracts x $0.65 = ${11 * 0.65:.2f} in commissions")
    print(f"   Plus exchange fees and slippage = ${df['Total_Costs'].mean():.2f} total")
    print(f"   → Need ${df['Total_Costs'].mean():.2f}+ gross profit just to break even")

    print("\n3. MARKET EFFICIENCY:")
    print(f"   Average price discrepancy: {df['Discrepancy_%'].abs().mean():.2f}%")
    print(f"   → Markets are pretty efficient! Discrepancies are small")

    print("\n4. WHY DISCREPANCIES EXIST (and aren't really arbitrage):")
    print("   ✓ European vs American exercise (cost of carry)")
    print("   ✓ Section 1256 tax treatment (SPX has advantage)")
    print("   ✓ Dividend considerations (SPY pays, SPX doesn't)")
    print("   ✓ Different market participant profiles")
    print("   → These are STRUCTURAL DIFFERENCES, not mispricing")


def print_reality_check():
    """Print the harsh reality"""
    print("\n" + "=" * 70)
    print("⚠️  THE REALITY CHECK")
    print("=" * 70)

    print("\nEven IF you find positive net profit in this analysis:")

    print("\n1. THIS DATA IS NOT REAL-TIME")
    print("   Real arbitrage requires microsecond execution")
    print("   By the time you see it, it's gone")

    print("\n2. YOU'RE COMPETING WITH:")
    print("   → Market makers with direct exchange connections")
    print("   → HFT firms with custom hardware")
    print("   → Algorithms that see orders before you")
    print("   → Firms with better commission rates ($0.10/contract)")

    print("\n3. EXECUTION RISK:")
    print("   → You might get filled on one side but not the other")
    print("   → Prices move while you're entering the spread")
    print("   → Early assignment risk on SPY (it's American style!)")
    print("   → Settlement risk on SPX (AM settlement is dangerous)")

    print("\n4. EVEN IF IT WORKS:")
    print("   → Profit is tiny ($1-3 per spread typically)")
    print("   → Need to do 100+ trades to make meaningful money")
    print("   → Any mistake = losses exceed all profits")

    print("\n" + "=" * 70)
    print("💡 WHAT THIS REALLY MEANS")
    print("=" * 70)

    print("\nThe 'arbitrage' you spotted is mostly:")
    print("  1. Correct pricing of structural differences")
    print("  2. Compensation for different risks (exercise, settlement)")
    print("  3. Too small to profit from after costs")

    print("\nREAL opportunities that DO exist:")
    print("  ✅ Box spreads (synthetic borrowing at 4-4.5%)")
    print("  ✅ Volatility arbitrage (sell overpriced IV)")
    print("  ✅ Using SPX for tax benefits on directional trades")

    print("\nWhat WON'T work:")
    print("  ❌ Simple SPY vs SPX call arbitrage (shown above)")
    print("  ❌ Holding index options into settlement")
    print("  ❌ Competing with market makers on spread")


def main():
    """Main execution"""

    # Generate realistic data
    df = generate_realistic_options_data()

    # Print detailed analysis
    print_detailed_analysis(df)

    # Reality check
    print_reality_check()

    # Export
    df.to_csv('spy_spx_demo_results.csv', index=False)
    print(f"\n✅ Results exported to spy_spx_demo_results.csv")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("\nTo get REAL data:")
    print("  1. Open a Tradier brokerage account (free)")
    print("  2. Use their API for real-time options data")
    print("  3. Or pay for Polygon.io ($199/mo)")
    print("  4. Run this analysis during market hours")

    print("\nTo test your hypothesis:")
    print("  1. Modify this script with real bid/ask data")
    print("  2. Account for all transaction costs")
    print("  3. If net profit > $0, investigate further")
    print("  4. Paper trade before using real money")

    print("\nHonest advice:")
    print("  The juice probably isn't worth the squeeze.")
    print("  Focus on box spreads or volatility arbitrage instead.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
