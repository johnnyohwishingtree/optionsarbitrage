#!/usr/bin/env python3
"""
Test strategy with live data from IB Gateway
"""

import sys
import os
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.broker.ibkr_client import IBKRClient
from src.strategy.spy_spx_strategy import SPYSPXStrategy
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def test_with_live_data():
    """Test strategy with current market prices from IB Gateway"""

    print("="*70)
    print("TESTING STRATEGY WITH LIVE IB GATEWAY DATA")
    print("="*70)

    # Connect to IB Gateway
    host = os.getenv('IB_HOST', '127.0.0.1')
    port = int(os.getenv('IB_PORT', 4002))

    print(f"\nConnecting to IB Gateway at {host}:{port}...")
    client = IBKRClient(host=host, port=port, client_id=10)

    if not client.connect():
        print("❌ Failed to connect to IB Gateway")
        print("Make sure IB Gateway is running and API is enabled")
        return

    print("✅ Connected to IB Gateway")

    # Get current underlying prices
    print("\n" + "="*70)
    print("FETCHING UNDERLYING PRICES")
    print("="*70)

    spy_price = client.get_current_price('SPY')
    spx_price = client.get_current_price('SPX')

    if not spy_price or not spx_price:
        print("❌ Could not fetch underlying prices (market may be closed)")
        client.disconnect()
        return

    print(f"\nSPY Price: ${spy_price:.2f}")
    print(f"SPX Price: ${spx_price:.2f}")
    print(f"Ratio: {spx_price/spy_price:.4f} (should be ~10.00)")

    # Calculate ATM strikes
    spy_strike = round(spy_price)
    spx_strike = round(spx_price / 5) * 5

    print(f"\nATM Strikes:")
    print(f"  SPY: ${spy_strike:.0f}")
    print(f"  SPX: ${spx_strike:.0f}")

    # Get 0DTE expiration (today)
    expiration = datetime.now().strftime('%Y%m%d')
    print(f"\nExpiration: {expiration}")

    # Get option quotes
    print("\n" + "="*70)
    print("FETCHING OPTION QUOTES")
    print("="*70)

    print("\nFetching SPY options...")
    spy_call_quote = client.get_option_quote('SPY', spy_strike, 'C', expiration)
    spy_put_quote = client.get_option_quote('SPY', spy_strike, 'P', expiration)

    print("Fetching SPX options...")
    spx_call_quote = client.get_option_quote('SPX', spx_strike, 'C', expiration)
    spx_put_quote = client.get_option_quote('SPX', spx_strike, 'P', expiration)

    # Check if we got all quotes
    if not all([spy_call_quote, spy_put_quote, spx_call_quote, spx_put_quote]):
        print("\n⚠️  Could not fetch all option quotes")
        print("This is normal if:")
        print("  - Market is closed")
        print("  - 0DTE options don't exist today")
        print("  - Strikes are too far from current price")

        # Try with simulated data instead
        print("\n" + "="*70)
        print("USING SIMULATED OPTION PRICES BASED ON UNDERLYING")
        print("="*70)

        # Simulate reasonable option prices
        spy_call_price = spy_price * 0.004  # ~0.4% of underlying
        spx_call_price = spx_price * 0.005  # ~0.5% of underlying
        spy_put_price = spy_price * 0.004
        spx_put_price = spx_price * 0.005

    else:
        print("\n✅ Got all option quotes!")
        spy_call_price = (spy_call_quote['bid'] + spy_call_quote['ask']) / 2
        spx_call_price = (spx_call_quote['bid'] + spx_call_quote['ask']) / 2
        spy_put_price = (spy_put_quote['bid'] + spy_put_quote['ask']) / 2
        spx_put_price = (spx_put_quote['bid'] + spx_put_quote['ask']) / 2

    print(f"\nOption Mid Prices:")
    print(f"  SPY {spy_strike:.0f} Call: ${spy_call_price:.2f}")
    print(f"  SPX {spx_strike:.0f} Call: ${spx_call_price:.2f}")
    print(f"  SPY {spy_strike:.0f} Put:  ${spy_put_price:.2f}")
    print(f"  SPX {spx_strike:.0f} Put:  ${spx_put_price:.2f}")

    # Test strategy
    print("\n" + "="*70)
    print("TESTING STRATEGY")
    print("="*70)

    config = {
        'min_entry_credit': 100,
        'assignment_risk_threshold': 10,
        'spy_contracts_per_spread': 10,
        'spx_contracts_per_spread': 1,
        'max_spreads_per_day': 2,
        'max_position_loss': 1000,
    }

    strategy = SPYSPXStrategy(config)

    # Calculate entry credit
    credit = strategy.calculate_entry_credit(
        spy_call_price, spx_call_price, spy_put_price, spx_put_price
    )

    print(f"\nSTRATEGY STRUCTURE:")
    print(f"  CALLS: {credit['calls_structure']}")
    print(f"    Credit: ${credit['calls_credit']:,.2f}")
    print(f"  PUTS:  {credit['puts_structure']}")
    print(f"    Credit: ${credit['puts_credit']:,.2f}")

    print(f"\nTOTAL CREDIT:")
    print(f"  Gross credit: ${credit['gross_credit']:,.2f}")
    print(f"  Commissions:  -${credit['commissions']:.2f}")
    print(f"  NET CREDIT:   ${credit['net_credit']:,.2f}")

    # Check if would enter
    should_enter, reason = strategy.should_enter_trade(
        spy_price, spx_price,
        spy_call_price, spx_call_price,
        spy_put_price, spx_put_price,
        trades_today=0
    )

    print(f"\n" + "="*70)
    print("ENTRY DECISION")
    print("="*70)
    print(f"\nShould enter trade: {should_enter}")
    print(f"Reason: {reason}")

    if credit['calls_credit'] > 0 and credit['puts_credit'] > 0:
        print(f"\n✅ Both sides would collect positive credit")
    else:
        print(f"\n⚠️  One or both sides would not collect credit")

    # Disconnect
    client.disconnect()
    print(f"\n{'='*70}")
    print("TEST COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    test_with_live_data()
