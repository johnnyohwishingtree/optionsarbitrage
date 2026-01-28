#!/usr/bin/env python3
"""
Test script for double-sided SPY/SPX strategy
"""

import sys
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.strategy.spy_spx_strategy import SPYSPXStrategy

def test_strategy():
    """Test the double-sided strategy logic"""

    print("="*70)
    print("DOUBLE-SIDED SPY/SPX STRATEGY TEST")
    print("="*70)

    config = {
        'min_entry_credit': 800,
        'assignment_risk_threshold': 10,
        'spy_contracts_per_spread': 10,
        'spx_contracts_per_spread': 1,
        'max_spreads_per_day': 2,
        'max_position_loss': 1000,
    }

    strategy = SPYSPXStrategy(config)

    # Test scenario
    print("\n--- TEST SCENARIO ---")
    spy_price = 600.0
    spx_price = 6000.0
    print(f"SPY Price: ${spy_price:.2f}")
    print(f"SPX Price: ${spx_price:.2f}")
    print(f"Ratio: {spx_price/spy_price:.4f} (should be ~10.00)")

    # Example option prices
    # CALLS: We sell expensive SPX, buy cheap SPY (collect credit)
    spy_call_bid = 2.50   # We buy SPY calls at bid
    spx_call_ask = 30.00  # We sell SPX calls at ask

    # PUTS: We sell cheap SPY, buy expensive SPX (collect credit)
    # For this to collect credit: (SPY put price * 10) > (SPX put price * 1)
    spy_put_ask = 3.00    # We sell SPY puts at ask
    spx_put_bid = 28.00   # We buy SPX puts at bid

    print("\n--- OPTION PRICES ---")
    print("CALLS side:")
    print(f"  SPY call (buy at bid): ${spy_call_bid:.2f}")
    print(f"  SPX call (sell at ask): ${spx_call_ask:.2f}")
    print("\nPUTS side:")
    print(f"  SPY put (sell at ask): ${spy_put_ask:.2f}")
    print(f"  SPX put (buy at bid): ${spx_put_bid:.2f}")

    # Calculate entry credit
    print("\n" + "="*70)
    print("ENTRY CREDIT CALCULATION")
    print("="*70)

    credit = strategy.calculate_entry_credit(
        spy_call_bid, spx_call_ask, spy_put_ask, spx_put_bid
    )

    print("\nCALLS SIDE:")
    print(f"  Sell 1 SPX call @ ${spx_call_ask:.2f}")
    print(f"    Revenue: ${credit['spx_call_revenue']:,.2f}")
    print(f"  Buy 10 SPY calls @ ${spy_call_bid:.2f}")
    print(f"    Cost: -${credit['spy_call_cost']:,.2f}")
    print(f"  CALLS Credit: ${credit['calls_credit']:,.2f}")

    print("\nPUTS SIDE:")
    print(f"  Sell 10 SPY puts @ ${spy_put_ask:.2f}")
    print(f"    Revenue: ${credit['spy_put_revenue']:,.2f}")
    print(f"  Buy 1 SPX put @ ${spx_put_bid:.2f}")
    print(f"    Cost: -${credit['spx_put_cost']:,.2f}")
    print(f"  PUTS Credit: ${credit['puts_credit']:,.2f}")

    print("\nTOTAL:")
    print(f"  Gross credit: ${credit['gross_credit']:,.2f}")
    print(f"  Commissions (22 contracts @ $0.65): -${credit['commissions']:,.2f}")
    print(f"  NET CREDIT: ${credit['net_credit']:,.2f}")

    # Test exit logic
    print("\n" + "="*70)
    print("EXIT LOGIC TEST")
    print("="*70)

    # Scenario 1: Price unchanged
    print("\nScenario 1: Price unchanged at expiration")
    should_exit, reason = strategy.should_exit_position(
        spy_price=600.0,
        spy_call_strike=600.0,
        spy_put_strike=600.0,
        spx_price=6000.0,
        spx_call_strike=6000.0,
        spx_put_strike=6000.0,
        entry_credit=credit['net_credit'],
        current_pnl=None
    )
    print(f"  Should exit: {should_exit}")
    print(f"  Reason: {reason}")

    # Scenario 2: SPY moves up (calls side in trouble)
    print("\nScenario 2: SPY rises to $612 (calls $12 ITM)")
    should_exit, reason = strategy.should_exit_position(
        spy_price=612.0,
        spy_call_strike=600.0,
        spy_put_strike=600.0,
        spx_price=6120.0,
        spx_call_strike=6000.0,
        spx_put_strike=6000.0,
        entry_credit=credit['net_credit'],
        current_pnl=None
    )
    print(f"  Should exit: {should_exit}")
    print(f"  Reason: {reason}")

    # Scenario 3: SPY moves down (puts side in trouble)
    print("\nScenario 3: SPY falls to $588 (puts $12 ITM)")
    should_exit, reason = strategy.should_exit_position(
        spy_price=588.0,
        spy_call_strike=600.0,
        spy_put_strike=600.0,
        spx_price=5880.0,
        spx_call_strike=6000.0,
        spx_put_strike=6000.0,
        entry_credit=credit['net_credit'],
        current_pnl=None
    )
    print(f"  Should exit: {should_exit}")
    print(f"  Reason: {reason}")

    # Test contract creation
    print("\n" + "="*70)
    print("CONTRACT CREATION TEST")
    print("="*70)

    contracts = strategy.create_option_contracts(spy_price, spx_price)
    print(f"\nExpiration: {contracts['expiration']}")
    print(f"\nSPY Call Strike: ${contracts['spy_call_strike']:.2f}")
    print(f"SPY Put Strike: ${contracts['spy_put_strike']:.2f}")
    print(f"SPX Call Strike: ${contracts['spx_call_strike']:.2f}")
    print(f"SPX Put Strike: ${contracts['spx_put_strike']:.2f}")

    print("\n" + "="*70)
    print("STRATEGY STRUCTURE SUMMARY")
    print("="*70)
    print("\nOPENING POSITIONS (Entry):")
    print("  CALLS: Sell 1 SPX call, Buy 10 SPY calls")
    print("  PUTS:  Sell 10 SPY puts, Buy 1 SPX put")
    print("  Total: 22 contracts")

    print("\nRISK PROFILE:")
    print("  - Profit if SPY/SPX track closely")
    print("  - Loss if tracking error exceeds premium collected")
    print("  - Max profit: Entry credit (if both sides expire worthless)")
    print("  - Max loss: Difference in settlement * contract size - credit")

    print("\nEXIT CONDITIONS:")
    print("  1. Time: Force close at 3:45 PM")
    print("  2. Assignment risk: SPY calls or puts >$10 ITM")
    print("  3. Max loss: Current loss >$1,000")
    print("  4. Extreme volatility: Both sides heavily ITM")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    test_strategy()
