#!/usr/bin/env python3
"""
Synchronous Strategy Execution for Paper Trading

Execution Order (All-or-Nothing):
1. SELL for Credit (collect premium first)
   - Sell SPX Calls
   - Sell SPY Puts
2. BUY for Protection (use collected premium)
   - Buy SPY Calls
   - Buy SPX Puts

If ANY order fails, CANCEL ALL orders and exit.
"""

import sys
import json
import logging
from datetime import datetime
from ib_insync import Option

# Add src to path
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')
from src.broker.ibkr_client import IBKRClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Execute strategy synchronously in paper trading account"""

    print("=" * 70)
    print("SYNCHRONOUS STRATEGY EXECUTION - PAPER TRADING")
    print("=" * 70)

    # Load strategy from best_combo.json
    try:
        with open('/tmp/best_combo.json', 'r') as f:
            strategy = json.load(f)
    except Exception as e:
        print(f"❌ Error loading strategy: {e}")
        return

    print(f"\n📋 Strategy Details:")
    print(f"  SPY Strike: {strategy['spy_strike']}")
    print(f"  SPX Strike: {strategy['spx_strike']}")
    print(f"  Call Direction: {strategy['call_direction']}")
    print(f"  Put Direction: {strategy['put_direction']}")
    print(f"  Expected Call Credit: ${strategy['call_credit']:.2f}")
    print(f"  Expected Put Credit: ${strategy['put_credit']:.2f}")
    print(f"  Total Expected Credit: ${strategy['total_credit']:.2f}")

    # Connect to IB Gateway (Paper Trading)
    print(f"\n🔌 Connecting to IB Gateway (Paper Trading Port 4002)...")
    client = IBKRClient(port=4002, client_id=999)

    if not client.connect():
        print("❌ Failed to connect to IB Gateway")
        print("\nMake sure:")
        print("  1. IB Gateway is running")
        print("  2. Port 4002 (Paper Trading) is accessible")
        print("  3. API connections are enabled")
        return

    # Get account info
    account = client.get_account_summary()
    print(f"\n💰 Account: {account.get('account_id', 'Unknown')}")
    print(f"  Net Liquidation: ${account.get('net_liquidation', 0):,.2f}")
    print(f"  Available Funds: ${account.get('available_funds', 0):,.2f}")

    # Get expiration date (today for 0DTE)
    today = datetime.now().strftime('%Y%m%d')

    # Create option contracts
    print(f"\n📄 Creating option contracts for {today}...")

    spy_call = Option('SPY', today, strategy['spy_strike'], 'C', 'SMART')
    spx_call = Option('SPX', today, strategy['spx_strike'], 'C', 'SMART')
    spy_put = Option('SPY', today, strategy['spy_strike'], 'P', 'SMART')
    spx_put = Option('SPX', today, strategy['spx_strike'], 'P', 'SMART')

    # Qualify all contracts
    print("  Qualifying contracts...")
    try:
        client.ib.qualifyContracts(spy_call, spx_call, spy_put, spx_put)
        print("  ✅ All contracts qualified")
    except Exception as e:
        print(f"  ❌ Error qualifying contracts: {e}")
        client.disconnect()
        return

    # Get current quotes
    print(f"\n📊 Getting current market quotes...")

    def get_quote(contract, name):
        """Get quote with error handling"""
        try:
            ticker = client.ib.reqMktData(contract)
            client.ib.sleep(2)

            if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
                print(f"  {name}: Bid ${ticker.bid:.2f} / Ask ${ticker.ask:.2f}")
                return ticker.bid, ticker.ask
            else:
                print(f"  ⚠️  {name}: No valid quotes")
                return None, None
        except Exception as e:
            print(f"  ❌ {name}: Error getting quote: {e}")
            return None, None

    spy_call_bid, spy_call_ask = get_quote(spy_call, f"SPY {strategy['spy_strike']}C")
    spx_call_bid, spx_call_ask = get_quote(spx_call, f"SPX {strategy['spx_strike']}C")
    spy_put_bid, spy_put_ask = get_quote(spy_put, f"SPY {strategy['spy_strike']}P")
    spx_put_bid, spx_put_ask = get_quote(spx_put, f"SPX {strategy['spx_strike']}P")

    # Check if all quotes are valid
    if None in [spy_call_bid, spy_call_ask, spx_call_bid, spx_call_ask,
                spy_put_bid, spy_put_ask, spx_put_bid, spx_put_ask]:
        print("\n❌ Not all quotes available - cannot execute")
        client.disconnect()
        return

    # Determine order sequence based on directions
    # Call direction: "Buy SPX, Sell SPY" means sell SPY calls, buy SPX calls
    #                 "Sell SPX, Buy SPY" means sell SPX calls, buy SPY calls
    # Put direction: "Buy SPY, Sell SPX" means buy SPY puts, sell SPX puts
    #                "Sell SPY, Buy SPX" means sell SPY puts, buy SPX puts

    # Get quantities (default to 100/10 for backwards compatibility)
    spy_qty = strategy.get('spy_qty', 100)
    spx_qty = strategy.get('spx_qty', 10)

    print(f"\n📊 Position Size:")
    print(f"  SPY: {spy_qty} contracts")
    print(f"  SPX: {spx_qty} contracts")
    if 'note' in strategy:
        print(f"  Note: {strategy['note']}")

    # Calculate expected P&L based on actual directions
    if strategy['call_direction'] == "Buy SPX, Sell SPY":
        # Sell SPY calls, Buy SPX calls
        call_credit = (spy_call_bid * spy_qty * 100) - (spx_call_ask * spx_qty * 100)
        call_orders = [
            ('SELL', spy_qty, spy_call, spy_call_bid, f"SPY {strategy['spy_strike']}C"),
            ('BUY', spx_qty, spx_call, spx_call_ask, f"SPX {strategy['spx_strike']}C")
        ]
    else:  # "Sell SPX, Buy SPY"
        # Sell SPX calls, Buy SPY calls
        call_credit = (spx_call_bid * spx_qty * 100) - (spy_call_ask * spy_qty * 100)
        call_orders = [
            ('SELL', spx_qty, spx_call, spx_call_bid, f"SPX {strategy['spx_strike']}C"),
            ('BUY', spy_qty, spy_call, spy_call_ask, f"SPY {strategy['spy_strike']}C")
        ]

    if strategy['put_direction'] == "Buy SPY, Sell SPX":
        # Buy SPY puts, Sell SPX puts
        put_credit = (spx_put_bid * spx_qty * 100) - (spy_put_ask * spy_qty * 100)
        put_orders = [
            ('SELL', spx_qty, spx_put, spx_put_bid, f"SPX {strategy['spx_strike']}P"),
            ('BUY', spy_qty, spy_put, spy_put_ask, f"SPY {strategy['spy_strike']}P")
        ]
    else:  # "Sell SPY, Buy SPX"
        # Sell SPY puts, Buy SPX puts
        put_credit = (spy_put_bid * spy_qty * 100) - (spx_put_ask * spx_qty * 100)
        put_orders = [
            ('SELL', spy_qty, spy_put, spy_put_bid, f"SPY {strategy['spy_strike']}P"),
            ('BUY', spx_qty, spx_put, spx_put_ask, f"SPX {strategy['spx_strike']}P")
        ]

    total_credit = call_credit + put_credit

    print(f"\n💵 Expected P&L:")
    print(f"  Call Spread Credit: ${call_credit:,.2f}")
    print(f"  Put Spread Credit:  ${put_credit:,.2f}")
    print(f"  Total Credit:       ${total_credit:,.2f}")

    if total_credit <= 0:
        print(f"\n⚠️  WARNING: Total credit is ${total_credit:,.2f} (not positive)")
        print("❌ Execution cancelled - need positive credit")
        client.disconnect()
        return

    # Confirm execution
    print(f"\n" + "=" * 70)
    print("EXECUTION PLAN (ALL-OR-NOTHING)")
    print("=" * 70)
    print(f"\nSTEP 1: SELL for Credit (collect premium)")

    # Find SELL orders
    sell_orders = [o for o in call_orders + put_orders if o[0] == 'SELL']
    for i, (action, qty, contract, price, name) in enumerate(sell_orders, 1):
        print(f"  1{chr(96+i)}. SELL {qty} {name} @ ${price:.2f}")

    print(f"\nSTEP 2: BUY for Protection")

    # Find BUY orders
    buy_orders = [o for o in call_orders + put_orders if o[0] == 'BUY']
    for i, (action, qty, contract, price, name) in enumerate(buy_orders, 1):
        print(f"  2{chr(96+i)}. BUY {qty} {name} @ ${price:.2f}")

    print(f"\n⚠️  Execute in PAPER TRADING account?")
    print(f"Press Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Execution cancelled by user")
        client.disconnect()
        return

    # Track all trades for potential rollback
    all_trades = []

    print(f"\n" + "=" * 70)
    print("EXECUTING ORDERS")
    print("=" * 70)

    try:
        # Execute all SELL orders first (collect premium)
        # Using MARKET orders for paper trading (delayed data makes limit orders unreliable)
        for i, (action, qty, contract, price, name) in enumerate(sell_orders, 1):
            print(f"\n[{i}/{len(sell_orders)+len(buy_orders)}] SELL {qty} {name} (MARKET ORDER)")
            print(f"  Reference price: ${price:.2f}")
            trade = client.place_option_order(
                contract=contract,
                action='SELL',
                quantity=qty,
                order_type='MKT'
            )

            if not trade or trade.orderStatus.status not in ['Filled', 'PreSubmitted', 'Submitted']:
                raise Exception(f"Order {i} failed: {trade.orderStatus.status if trade else 'No trade'}")

            all_trades.append(trade)
            print(f"  ✅ Order placed: {trade.orderStatus.status}")

            # Wait for fill
            for j in range(30):
                client.ib.sleep(1)
                if trade.orderStatus.status == 'Filled':
                    print(f"  ✅ FILLED at ${trade.orderStatus.avgFillPrice:.2f}")
                    break
            else:
                raise Exception(f"Order {i} timed out waiting for fill")

        print(f"\n✅ Credit collected! Now buying protective positions...")

        # Execute all BUY orders (protection)
        for i, (action, qty, contract, price, name) in enumerate(buy_orders, len(sell_orders)+1):
            print(f"\n[{i}/{len(sell_orders)+len(buy_orders)}] BUY {qty} {name} (MARKET ORDER)")
            print(f"  Reference price: ${price:.2f}")
            trade = client.place_option_order(
                contract=contract,
                action='BUY',
                quantity=qty,
                order_type='MKT'
            )

            if not trade or trade.orderStatus.status not in ['Filled', 'PreSubmitted', 'Submitted']:
                raise Exception(f"Order {i} failed: {trade.orderStatus.status if trade else 'No trade'}")

            all_trades.append(trade)
            print(f"  ✅ Order placed: {trade.orderStatus.status}")

            # Wait for fill
            for j in range(30):
                client.ib.sleep(1)
                if trade.orderStatus.status == 'Filled':
                    print(f"  ✅ FILLED at ${trade.orderStatus.avgFillPrice:.2f}")
                    break
            else:
                raise Exception(f"Order {i} timed out waiting for fill")

        # SUCCESS!
        print(f"\n" + "=" * 70)
        print("✅ ALL ORDERS FILLED SUCCESSFULLY!")
        print("=" * 70)

        # Calculate actual P&L
        actual_call_credit = 0
        actual_put_credit = 0

        # Sum up actual fills based on call orders
        for i, (action, qty, contract, price, name) in enumerate(call_orders):
            fill_price = all_trades[sell_orders.index((action, qty, contract, price, name)) if (action, qty, contract, price, name) in sell_orders else len(sell_orders) + buy_orders.index((action, qty, contract, price, name))].orderStatus.avgFillPrice
            if action == 'SELL':
                actual_call_credit += fill_price * qty * 100
            else:
                actual_call_credit -= fill_price * qty * 100

        # Sum up actual fills based on put orders
        for i, (action, qty, contract, price, name) in enumerate(put_orders):
            fill_price = all_trades[sell_orders.index((action, qty, contract, price, name)) if (action, qty, contract, price, name) in sell_orders else len(sell_orders) + buy_orders.index((action, qty, contract, price, name))].orderStatus.avgFillPrice
            if action == 'SELL':
                actual_put_credit += fill_price * qty * 100
            else:
                actual_put_credit -= fill_price * qty * 100

        actual_total = actual_call_credit + actual_put_credit

        print(f"\n💰 Actual P&L:")
        print(f"  Call Spread Credit: ${actual_call_credit:,.2f}")
        print(f"  Put Spread Credit:  ${actual_put_credit:,.2f}")
        print(f"  Total Credit:       ${actual_total:,.2f}")

        # Show positions
        print(f"\n📊 Current Positions:")
        positions = client.get_positions()
        for pos in positions:
            if pos['sec_type'] == 'OPT':
                print(f"  {pos['symbol']} {pos['position']:+,.0f} contracts")

    except Exception as e:
        # ROLLBACK: Cancel any unfilled orders
        print(f"\n❌ ERROR: {e}")
        print(f"\n⚠️  ROLLING BACK - Cancelling all unfilled orders...")

        for trade in all_trades:
            if trade.orderStatus.status not in ['Filled', 'Cancelled']:
                try:
                    client.cancel_order(trade)
                    print(f"  Cancelled order: {trade.order.orderId}")
                except Exception as cancel_error:
                    print(f"  Error cancelling order {trade.order.orderId}: {cancel_error}")

        print(f"\n❌ EXECUTION FAILED - All unfilled orders cancelled")
        print(f"   Note: Any filled orders remain (cannot be automatically reversed)")

    finally:
        client.disconnect()
        print(f"\n👋 Disconnected from IB Gateway")


if __name__ == '__main__':
    main()
