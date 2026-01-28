#!/usr/bin/env python3
"""
SPY/SPX Options Arbitrage Strategy
Main execution script for the double-sided pseudo-arbitrage strategy

Strategy:
- Sell expensive options (SPX or SPY depending on prices)
- Buy cheaper options (SPY or SPX)
- Collect credit from pricing inefficiency
- Market-neutral, hedged position

Usage:
    python run_strategy.py --mode paper    # Paper trading
    python run_strategy.py --mode live     # Live trading (be careful!)
    python run_strategy.py --mode analyze  # Analyze current opportunity
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.broker.ibkr_client import IBKRClient
from src.strategy.spy_spx_strategy import SPYSPXStrategy
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for auto-confirmation
AUTO_CONFIRM = False


def analyze_opportunity():
    """Analyze current arbitrage opportunity without trading"""
    logger.info("="*80)
    logger.info("ANALYZING CURRENT SPY/SPX ARBITRAGE OPPORTUNITY")
    logger.info("="*80)

    client = IBKRClient(client_id=300)
    if not client.connect():
        logger.error("Failed to connect to IB Gateway")
        return

    try:
        # Get current prices
        spy_price = client.get_current_price('SPY')
        spx_price = client.get_current_price('SPX')

        if not spy_price or not spx_price:
            logger.error("Could not fetch prices")
            return

        logger.info(f"\n📍 Current Prices:")
        logger.info(f"   SPY: ${spy_price:.2f}")
        logger.info(f"   SPX: ${spx_price:.2f}")
        logger.info(f"   Ratio: {spx_price/spy_price:.4f} (should be ~10.0)")

        # Calculate ATM strikes
        spy_strike = round(spy_price)
        spx_strike = round(spx_price / 5) * 5

        # Get today's expiration
        from datetime import datetime
        expiration = datetime.now().strftime('%Y%m%d')

        logger.info(f"\n📊 ATM Strikes (0DTE):")
        logger.info(f"   SPY: ${spy_strike}")
        logger.info(f"   SPX: ${spx_strike}")

        # Get option quotes
        logger.info(f"\n💰 Fetching option quotes...")

        spy_call = client.get_option_quote('SPY', spy_strike, 'C', expiration)
        spy_put = client.get_option_quote('SPY', spy_strike, 'P', expiration)
        spx_call = client.get_option_quote('SPX', spx_strike, 'C', expiration)
        spx_put = client.get_option_quote('SPX', spx_strike, 'P', expiration)

        if not all([spy_call, spy_put, spx_call, spx_put]):
            logger.error("Could not fetch all option quotes")
            return

        # Display quotes
        logger.info(f"\n   SPY {spy_strike} Call: Bid ${spy_call['bid']:.2f} / Ask ${spy_call['ask']:.2f}")
        logger.info(f"   SPY {spy_strike} Put:  Bid ${spy_put['bid']:.2f} / Ask ${spy_put['ask']:.2f}")
        logger.info(f"   SPX {spx_strike} Call: Bid ${spx_call['bid']:.2f} / Ask ${spx_call['ask']:.2f}")
        logger.info(f"   SPX {spx_strike} Put:  Bid ${spx_put['bid']:.2f} / Ask ${spx_put['ask']:.2f}")

        # Calculate theoretical credit
        SPY_QTY = 10
        SPX_QTY = 1

        # CALLS SIDE
        spy_call_total = spy_call['ask'] * 100 * SPY_QTY  # We buy at ask
        spx_call_total = spx_call['bid'] * 100 * SPX_QTY  # We sell at bid

        if spx_call_total > spy_call_total:
            calls_credit = spx_call_total - spy_call_total
            calls_action = "SELL SPX, BUY SPY"
        else:
            calls_credit = spy_call_total - spx_call_total
            calls_action = "SELL SPY, BUY SPX"

        # PUTS SIDE
        spy_put_total = spy_put['ask'] * 100 * SPY_QTY
        spx_put_total = spx_put['bid'] * 100 * SPX_QTY

        if spx_put_total > spy_put_total:
            puts_credit = spx_put_total - spy_put_total
            puts_action = "SELL SPX, BUY SPY"
        else:
            puts_credit = spy_put_total - spx_put_total
            puts_action = "SELL SPY, BUY SPX"

        gross_credit = calls_credit + puts_credit
        commissions = 22 * 0.65  # 22 contracts
        net_credit = gross_credit - commissions

        logger.info(f"\n🔧 Recommended Structure:")
        logger.info(f"   Calls: {calls_action} → Credit: ${calls_credit:.2f}")
        logger.info(f"   Puts:  {puts_action} → Credit: ${puts_credit:.2f}")

        logger.info(f"\n💵 Potential P&L:")
        logger.info(f"   Gross Credit:  ${gross_credit:.2f}")
        logger.info(f"   Commissions:   -${commissions:.2f}")
        logger.info(f"   NET CREDIT:    ${net_credit:.2f}")

        if net_credit > 0:
            logger.info(f"\n✅ PROFITABLE OPPORTUNITY DETECTED")
            logger.info(f"   Entry credit of ${net_credit:.2f}")
            logger.info(f"   Assuming perfect tracking, this is your profit")
        else:
            logger.info(f"\n❌ NO PROFITABLE OPPORTUNITY")
            logger.info(f"   Would cost ${abs(net_credit):.2f} to enter")

    finally:
        client.disconnect()


def run_paper_trading():
    """Run strategy in paper trading mode"""
    logger.info("="*80)
    logger.info("🚀 EXECUTING PAPER TRADING STRATEGY")
    logger.info("="*80)

    client = IBKRClient(client_id=500)
    if not client.connect():
        logger.error("Failed to connect to IB Gateway")
        return

    try:
        # Get account info
        account = client.get_account_summary()
        logger.info(f"\n📊 Account: {account.get('account_id', 'Unknown')}")
        logger.info(f"   Net Liquidation: ${account.get('net_liquidation', 0):,.2f}")
        logger.info(f"   Buying Power: ${account.get('buying_power', 0):,.2f}")

        # Get current prices
        spy_price = client.get_current_price('SPY')
        spx_price = client.get_current_price('SPX')

        if not spy_price or not spx_price:
            logger.error("Could not fetch prices")
            return

        logger.info(f"\n📍 Current Prices:")
        logger.info(f"   SPY: ${spy_price:.2f}")
        logger.info(f"   SPX: ${spx_price:.2f}")
        logger.info(f"   Ratio: {spx_price/spy_price:.4f} (should be ~10.0)")

        # Calculate ATM strikes
        spy_strike = round(spy_price)
        spx_strike = round(spx_price / 5) * 5

        # Get today's expiration
        from datetime import datetime
        expiration = datetime.now().strftime('%Y%m%d')

        logger.info(f"\n📊 ATM Strikes (0DTE):")
        logger.info(f"   SPY: ${spy_strike}")
        logger.info(f"   SPX: ${spx_strike}")

        # Get option quotes
        logger.info(f"\n💰 Fetching option quotes...")

        spy_call = client.get_option_quote('SPY', spy_strike, 'C', expiration)
        spy_put = client.get_option_quote('SPY', spy_strike, 'P', expiration)
        spx_call = client.get_option_quote('SPX', spx_strike, 'C', expiration)
        spx_put = client.get_option_quote('SPX', spx_strike, 'P', expiration)

        if not all([spy_call, spy_put, spx_call, spx_put]):
            logger.error("Could not fetch all option quotes")
            return

        # Display quotes
        logger.info(f"\n   SPY {spy_strike} Call: Bid ${spy_call['bid']:.2f} / Ask ${spy_call['ask']:.2f}")
        logger.info(f"   SPY {spy_strike} Put:  Bid ${spy_put['bid']:.2f} / Ask ${spy_put['ask']:.2f}")
        logger.info(f"   SPX {spx_strike} Call: Bid ${spx_call['bid']:.2f} / Ask ${spx_call['ask']:.2f}")
        logger.info(f"   SPX {spx_strike} Put:  Bid ${spx_put['bid']:.2f} / Ask ${spx_put['ask']:.2f}")

        # Calculate optimal structure
        SPY_QTY = 10
        SPX_QTY = 1

        # CALLS SIDE
        # For conservative credit calculation, use bid/ask spread
        spy_call_total = spy_call['ask'] * 100 * SPY_QTY  # We buy at ask
        spx_call_total = spx_call['bid'] * 100 * SPX_QTY  # We sell at bid

        if spx_call_total > spy_call_total:
            calls_credit = spx_call_total - spy_call_total
            calls_structure = ("SELL", "SPX", "MARKET", "BUY", "SPY", "MARKET")
        else:
            calls_credit = spy_call_total - spx_call_total
            calls_structure = ("SELL", "SPY", "MARKET", "BUY", "SPX", "MARKET")

        # PUTS SIDE
        spy_put_total = spy_put['ask'] * 100 * SPY_QTY
        spx_put_total = spx_put['bid'] * 100 * SPX_QTY

        if spx_put_total > spy_put_total:
            puts_credit = spx_put_total - spy_put_total
            puts_structure = ("SELL", "SPX", "MARKET", "BUY", "SPY", "MARKET")
        else:
            puts_credit = spy_put_total - spx_put_total
            puts_structure = ("SELL", "SPY", "MARKET", "BUY", "SPX", "MARKET")

        gross_credit = calls_credit + puts_credit
        commissions = 22 * 0.65  # 22 contracts
        net_credit = gross_credit - commissions

        logger.info(f"\n🔧 Recommended Structure (Using MARKET orders for immediate fills):")
        logger.info(f"   Calls: {calls_structure[0]} {calls_structure[1]} {calls_structure[2]}, {calls_structure[3]} {calls_structure[4]} {calls_structure[5]} → Expected Credit: ${calls_credit:.2f}")
        logger.info(f"   Puts:  {puts_structure[0]} {puts_structure[1]} {puts_structure[2]}, {puts_structure[3]} {puts_structure[4]} {puts_structure[5]} → Expected Credit: ${puts_credit:.2f}")

        logger.info(f"\n💵 Expected P&L:")
        logger.info(f"   Gross Credit:  ${gross_credit:.2f}")
        logger.info(f"   Commissions:   -${commissions:.2f}")
        logger.info(f"   NET CREDIT:    ${net_credit:.2f}")

        if net_credit <= 0:
            logger.warning(f"\n❌ NO PROFITABLE OPPORTUNITY")
            logger.warning(f"   Would cost ${abs(net_credit):.2f} to enter")
            logger.info("\nNot executing trade.")
            return

        logger.info(f"\n✅ PROFITABLE OPPORTUNITY: ${net_credit:.2f}")

        # Confirm execution
        if not AUTO_CONFIRM:
            response = input("\n⚠️  Execute this trade on paper account? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Trade cancelled by user")
                return
        else:
            logger.info("\n✅ Auto-confirm enabled - executing trade...")

        # Execute the trades
        logger.info("\n🚀 EXECUTING TRADES...")
        from ib_insync import Option

        trades = []

        # CALLS - Execute sell side first
        logger.info(f"\n1️⃣  CALLS (MARKET ORDERS):")
        if calls_structure[0] == "SELL" and calls_structure[1] == "SPX":
            # Sell SPX calls
            spx_call_contract = Option('SPX', expiration, spx_strike, 'C', 'SMART')
            client.ib.qualifyContracts(spx_call_contract)
            logger.info(f"   Selling {SPX_QTY} SPX {spx_strike} Call @ MARKET...")
            trade = client.place_option_order(spx_call_contract, 'SELL', SPX_QTY, 'MKT', None)
            if trade:
                trades.append(trade)

            # Buy SPY calls
            spy_call_contract = Option('SPY', expiration, spy_strike, 'C', 'SMART')
            client.ib.qualifyContracts(spy_call_contract)
            logger.info(f"   Buying {SPY_QTY} SPY {spy_strike} Call @ MARKET...")
            trade = client.place_option_order(spy_call_contract, 'BUY', SPY_QTY, 'MKT', None)
            if trade:
                trades.append(trade)
        else:
            # Sell SPY calls
            spy_call_contract = Option('SPY', expiration, spy_strike, 'C', 'SMART')
            client.ib.qualifyContracts(spy_call_contract)
            logger.info(f"   Selling {SPY_QTY} SPY {spy_strike} Call @ MARKET...")
            trade = client.place_option_order(spy_call_contract, 'SELL', SPY_QTY, 'MKT', None)
            if trade:
                trades.append(trade)

            # Buy SPX calls
            spx_call_contract = Option('SPX', expiration, spx_strike, 'C', 'SMART')
            client.ib.qualifyContracts(spx_call_contract)
            logger.info(f"   Buying {SPX_QTY} SPX {spx_strike} Call @ MARKET...")
            trade = client.place_option_order(spx_call_contract, 'BUY', SPX_QTY, 'MKT', None)
            if trade:
                trades.append(trade)

        # PUTS - Execute sell side first
        logger.info(f"\n2️⃣  PUTS (MARKET ORDERS):")
        if puts_structure[0] == "SELL" and puts_structure[1] == "SPX":
            # Sell SPX puts
            spx_put_contract = Option('SPX', expiration, spx_strike, 'P', 'SMART')
            client.ib.qualifyContracts(spx_put_contract)
            logger.info(f"   Selling {SPX_QTY} SPX {spx_strike} Put @ MARKET...")
            trade = client.place_option_order(spx_put_contract, 'SELL', SPX_QTY, 'MKT', None)
            if trade:
                trades.append(trade)

            # Buy SPY puts
            spy_put_contract = Option('SPY', expiration, spy_strike, 'P', 'SMART')
            client.ib.qualifyContracts(spy_put_contract)
            logger.info(f"   Buying {SPY_QTY} SPY {spy_strike} Put @ MARKET...")
            trade = client.place_option_order(spy_put_contract, 'BUY', SPY_QTY, 'MKT', None)
            if trade:
                trades.append(trade)
        else:
            # Sell SPY puts
            spy_put_contract = Option('SPY', expiration, spy_strike, 'P', 'SMART')
            client.ib.qualifyContracts(spy_put_contract)
            logger.info(f"   Selling {SPY_QTY} SPY {spy_strike} Put @ MARKET...")
            trade = client.place_option_order(spy_put_contract, 'SELL', SPY_QTY, 'MKT', None)
            if trade:
                trades.append(trade)

            # Buy SPX puts
            spx_put_contract = Option('SPX', expiration, spx_strike, 'P', 'SMART')
            client.ib.qualifyContracts(spx_put_contract)
            logger.info(f"   Buying {SPX_QTY} SPX {spx_strike} Put @ MARKET...")
            trade = client.place_option_order(spx_put_contract, 'BUY', SPX_QTY, 'MKT', None)
            if trade:
                trades.append(trade)

        # Summary
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 TRADE EXECUTION SUMMARY")
        logger.info(f"{'='*80}")

        filled = sum(1 for t in trades if t and t.orderStatus.status == 'Filled')
        logger.info(f"\n✅ Orders Placed: {len(trades)}")
        logger.info(f"✅ Orders Filled: {filled}")

        if filled == len(trades):
            logger.info(f"\n🎉 ALL ORDERS FILLED!")
            logger.info(f"   Expected Profit: ${net_credit:.2f}")
            logger.info(f"   Position: Market-neutral, fully hedged")
            logger.info(f"   Expiration: Today (0DTE)")
        else:
            logger.warning(f"\n⚠️  Some orders not filled yet")
            logger.info(f"   Check IB Gateway for order status")

        # Show current positions
        positions = client.get_positions()
        if positions:
            logger.info(f"\n📍 Current Positions:")
            for pos in positions:
                if pos['sec_type'] == 'OPT':
                    logger.info(f"   {pos['symbol']}: {pos['position']} contracts")

    finally:
        client.disconnect()


def run_live_trading():
    """Run strategy in live trading mode"""
    logger.info("="*80)
    logger.warning("LIVE TRADING MODE - REAL MONEY AT RISK")
    logger.info("="*80)

    response = input("Are you sure you want to trade with real money? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Cancelled")
        return

    # TODO: Implement live trading execution
    logger.warning("Live trading mode not yet implemented")
    logger.info("Use --mode analyze to see current opportunity first")


def main():
    parser = argparse.ArgumentParser(description='Run SPY/SPX arbitrage strategy')
    parser.add_argument('--mode', choices=['analyze', 'paper', 'live'], default='analyze',
                        help='Execution mode')
    parser.add_argument('--auto-confirm', action='store_true',
                        help='Skip confirmation prompt (for automated execution)')

    args = parser.parse_args()

    # Store auto_confirm flag globally for access in other functions
    global AUTO_CONFIRM
    AUTO_CONFIRM = args.auto_confirm

    if args.mode == 'analyze':
        analyze_opportunity()
    elif args.mode == 'paper':
        run_paper_trading()
    elif args.mode == 'live':
        run_live_trading()


if __name__ == "__main__":
    main()
