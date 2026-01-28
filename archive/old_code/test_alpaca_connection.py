#!/usr/bin/env python3
"""
Test Alpaca Connection
Quick test to verify API keys work
"""

import os
from dotenv import load_dotenv
from alpaca_trade_api import REST

# Load environment variables
load_dotenv()

API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
BASE_URL = 'https://paper-api.alpaca.markets'  # Paper trading

print("=" * 80)
print("ALPACA CONNECTION TEST")
print("=" * 80)

print(f"\nAPI Key: {API_KEY[:20]}...")
print(f"Paper Trading: True")

try:
    # Initialize Alpaca client
    api = REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

    # Get account info
    account = api.get_account()

    print("\n✅ CONNECTION SUCCESSFUL!")
    print("\n" + "=" * 80)
    print("ACCOUNT INFO")
    print("=" * 80)

    print(f"\nAccount Status: {account.status}")
    print(f"Buying Power: ${float(account.buying_power):,.2f}")
    print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
    print(f"Cash: ${float(account.cash):,.2f}")
    print(f"Pattern Day Trader: {account.pattern_day_trader}")

    # Test getting quotes
    print("\n" + "=" * 80)
    print("TESTING MARKET DATA")
    print("=" * 80)

    print("\nFetching SPY quote...")
    spy_quote = api.get_latest_trade('SPY')
    print(f"✅ SPY: ${spy_quote.price:.2f}")

    print("\nFetching SPX quote...")
    try:
        # SPX might need different method
        spx_quote = api.get_latest_trade('SPX')
        print(f"✅ SPX: ${spx_quote.price:.2f}")
    except Exception as e:
        print(f"⚠️  SPX quote failed: {e}")
        print("   (SPX index may need special handling)")

    # Test options data availability
    print("\n" + "=" * 80)
    print("TESTING OPTIONS DATA")
    print("=" * 80)

    print("\nChecking if options data is available...")
    try:
        # Try to get options contracts
        # Note: Options API might be different endpoint
        print("⚠️  Options API endpoint to be configured")
        print("   (Will implement in main system)")
    except Exception as e:
        print(f"⚠️  Options test: {e}")

    print("\n" + "=" * 80)
    print("✅ ALPACA CONNECTION VERIFIED!")
    print("=" * 80)

    print("\nReady to build automated trading system!")

except Exception as e:
    print(f"\n❌ CONNECTION FAILED: {e}")
    print("\nPlease check:")
    print("  1. API keys are correct")
    print("  2. Paper trading is enabled")
    print("  3. Internet connection is working")
