#!/usr/bin/env python3
"""
Find Today's Best 0DTE Strategy and Execute

This script:
1. Gets current SPY/SPX prices
2. Finds ATM strikes
3. Tests all 4 combinations of strikes (floor/ceiling for both)
4. Tests both directions for calls and puts
5. Finds best combination with positive credit on BOTH sides
6. Saves to best_combo.json
7. Optionally executes the strategy
"""

import sys
import json
import logging
from datetime import datetime
from ib_insync import Option

sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')
from src.broker.ibkr_client import IBKRClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_best_strategy(client, today):
    """Find best strategy for today"""

    print("\n" + "=" * 70)
    print("FINDING BEST 0DTE STRATEGY FOR TODAY")
    print("=" * 70)

    # Get current prices
    print("\n📊 Getting current market prices...")
    spy_price = client.get_current_price('SPY')
    spx_price = client.get_current_price('SPX')

    if not spy_price or not spx_price:
        print("❌ Could not get current prices")
        return None

    print(f"  SPY: ${spy_price:.2f}")
    print(f"  SPX: ${spx_price:.2f}")

    # Calculate strike brackets (floor and ceiling)
    spy_floor = int(spy_price)
    spy_ceiling = spy_floor + 1

    spx_floor = int(spx_price / 5) * 5
    spx_ceiling = spx_floor + 5

    print(f"\n🎯 Strike Brackets:")
    print(f"  SPY: {spy_floor} (floor) / {spy_ceiling} (ceiling)")
    print(f"  SPX: {spx_floor} (floor) / {spx_ceiling} (ceiling)")

    # Test all 4 strike combinations
    strike_combinations = [
        (spy_floor, spx_floor),
        (spy_floor, spx_ceiling),
        (spy_ceiling, spx_floor),
        (spy_ceiling, spx_ceiling),
    ]

    best_combo = None
    best_credit = -float('inf')

    print(f"\n🔍 Testing {len(strike_combinations)} strike combinations...")

    for i, (spy_strike, spx_strike) in enumerate(strike_combinations, 1):
        print(f"\n[{i}/4] Testing SPY {spy_strike} / SPX {spx_strike}")

        # Create contracts
        spy_call = Option('SPY', today, spy_strike, 'C', 'SMART')
        spx_call = Option('SPX', today, spx_strike, 'C', 'SMART')
        spy_put = Option('SPY', today, spy_strike, 'P', 'SMART')
        spx_put = Option('SPX', today, spx_strike, 'P', 'SMART')

        # Qualify contracts
        try:
            client.ib.qualifyContracts(spy_call, spx_call, spy_put, spx_put)
        except Exception as e:
            print(f"  ⚠️  Could not qualify contracts: {e}")
            continue

        # Get quotes
        print("  Getting quotes...")
        spy_call_ticker = client.ib.reqMktData(spy_call)
        spx_call_ticker = client.ib.reqMktData(spx_call)
        spy_put_ticker = client.ib.reqMktData(spy_put)
        spx_put_ticker = client.ib.reqMktData(spx_put)

        client.ib.sleep(3)  # Wait for quotes

        # Check if we have valid quotes
        if not all([
            spy_call_ticker.bid and spy_call_ticker.ask,
            spx_call_ticker.bid and spx_call_ticker.ask,
            spy_put_ticker.bid and spy_put_ticker.ask,
            spx_put_ticker.bid and spx_put_ticker.ask
        ]):
            print("  ⚠️  Missing quotes, skipping...")
            continue

        print(f"  SPY {spy_strike}C: ${spy_call_ticker.bid:.2f} / ${spy_call_ticker.ask:.2f}")
        print(f"  SPX {spx_strike}C: ${spx_call_ticker.bid:.2f} / ${spx_call_ticker.ask:.2f}")
        print(f"  SPY {spy_strike}P: ${spy_put_ticker.bid:.2f} / ${spy_put_ticker.ask:.2f}")
        print(f"  SPX {spx_strike}P: ${spx_put_ticker.bid:.2f} / ${spx_put_ticker.ask:.2f}")

        # Test both call directions
        call_dir_1 = "Sell SPX, Buy SPY"
        call_credit_1 = (spx_call_ticker.bid * 10 * 100) - (spy_call_ticker.ask * 100 * 100)

        call_dir_2 = "Buy SPX, Sell SPY"
        call_credit_2 = (spy_call_ticker.bid * 100 * 100) - (spx_call_ticker.ask * 10 * 100)

        # Test both put directions
        put_dir_1 = "Sell SPY, Buy SPX"
        put_credit_1 = (spy_put_ticker.bid * 100 * 100) - (spx_put_ticker.ask * 10 * 100)

        put_dir_2 = "Buy SPY, Sell SPX"
        put_credit_2 = (spx_put_ticker.bid * 10 * 100) - (spy_put_ticker.ask * 100 * 100)

        # Find best combination with positive credit on BOTH sides
        for call_dir, call_credit in [(call_dir_1, call_credit_1), (call_dir_2, call_credit_2)]:
            for put_dir, put_credit in [(put_dir_1, put_credit_1), (put_dir_2, put_credit_2)]:
                total_credit = call_credit + put_credit

                # Must have positive credit on BOTH sides
                if call_credit > 0 and put_credit > 0:
                    if total_credit > best_credit:
                        best_credit = total_credit
                        best_combo = {
                            'spy_strike': spy_strike,
                            'spx_strike': spx_strike,
                            'call_direction': call_dir,
                            'put_direction': put_dir,
                            'call_credit': call_credit,
                            'put_credit': put_credit,
                            'total_credit': total_credit,
                            'spy_call_bid': spy_call_ticker.bid,
                            'spy_call_ask': spy_call_ticker.ask,
                            'spx_call_bid': spx_call_ticker.bid,
                            'spx_call_ask': spx_call_ticker.ask,
                            'spy_put_bid': spy_put_ticker.bid,
                            'spy_put_ask': spy_put_ticker.ask,
                            'spx_put_bid': spx_put_ticker.bid,
                            'spx_put_ask': spx_put_ticker.ask,
                        }
                        print(f"  ✅ New best: {call_dir} + {put_dir} = ${total_credit:.2f}")

    return best_combo


def main():
    """Main execution"""

    print("\n" + "=" * 70)
    print("0DTE STRATEGY FINDER & EXECUTOR")
    print("=" * 70)
    print(f"\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to IB
    print("\n🔌 Connecting to IB Gateway (Paper Trading)...")
    client = IBKRClient(port=4002, client_id=998)

    if not client.connect():
        print("❌ Failed to connect to IB Gateway")
        return

    # Get account info
    account = client.get_account_summary()
    print(f"\n💰 Account: {account.get('account_id', 'Unknown')}")
    print(f"  Net Liquidation: ${account.get('net_liquidation', 0):,.2f}")

    # Get today's date
    today = datetime.now().strftime('%Y%m%d')
    print(f"\n📅 Trading date: {today}")

    # Find best strategy
    best_combo = find_best_strategy(client, today)

    if not best_combo:
        print("\n❌ No valid strategy found")
        client.disconnect()
        return

    # Display results
    print("\n" + "=" * 70)
    print("BEST STRATEGY FOUND")
    print("=" * 70)
    print(f"\n📋 Details:")
    print(f"  SPY Strike: {best_combo['spy_strike']}")
    print(f"  SPX Strike: {best_combo['spx_strike']}")
    print(f"  Call Direction: {best_combo['call_direction']}")
    print(f"  Put Direction: {best_combo['put_direction']}")
    print(f"\n💵 Expected P&L:")
    print(f"  Call Credit: ${best_combo['call_credit']:,.2f}")
    print(f"  Put Credit:  ${best_combo['put_credit']:,.2f}")
    print(f"  Total Credit: ${best_combo['total_credit']:,.2f}")

    # Save to file
    output_file = '/tmp/best_combo.json'
    with open(output_file, 'w') as f:
        json.dump(best_combo, f, indent=2)

    print(f"\n✅ Strategy saved to {output_file}")

    # Ask if user wants to execute
    print("\n" + "=" * 70)
    response = input("Execute this strategy now? (yes/no): ")

    if response.lower() == 'yes':
        print("\n📤 Executing strategy...")
        print("Please run: python3 execute_sync_strategy.py")
    else:
        print("\n✅ Strategy saved. Execute later with: python3 execute_sync_strategy.py")

    client.disconnect()


if __name__ == '__main__':
    main()
