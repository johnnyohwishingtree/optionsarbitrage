#!/usr/bin/env python3
"""
Fetch Real SPY/SPX Options Data
Verify our assumptions with actual market data
"""

import yfinance as yf
from datetime import datetime
import time

def fetch_real_spy_spx_data():
    """Fetch real options data for SPY and SPX"""

    print("=" * 80)
    print("FETCHING REAL MARKET DATA")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S ET"))
    print("=" * 80)

    try:
        # Fetch SPY
        print("\nFetching SPY data...")
        spy = yf.Ticker("SPY")
        spy_price = spy.history(period="1d")['Close'].iloc[-1] if len(spy.history(period="1d")) > 0 else None

        if spy_price:
            print(f"✅ SPY Current Price: ${spy_price:.2f}")
        else:
            print("❌ Could not fetch SPY price (market closed?)")
            return

        # Fetch SPX
        print("\nFetching SPX data...")
        spx = yf.Ticker("^SPX")
        spx_price = spx.history(period="1d")['Close'].iloc[-1] if len(spx.history(period="1d")) > 0 else None

        if spx_price:
            print(f"✅ SPX Current Price: ${spx_price:.2f}")
            print(f"   Ratio: {spx_price / spy_price:.4f}x (expected 10.0000x)")
        else:
            print("❌ Could not fetch SPX price (market closed?)")
            return

        # Get expiration dates
        print("\nFetching options expirations...")
        spy_expirations = spy.options
        spx_expirations = spx.options

        if not spy_expirations or not spx_expirations:
            print("❌ No options data available (market may be closed)")
            return

        print(f"✅ SPY expirations available: {len(spy_expirations)}")
        print(f"   Nearest: {spy_expirations[0] if spy_expirations else 'None'}")
        print(f"✅ SPX expirations available: {len(spx_expirations)}")
        print(f"   Nearest: {spx_expirations[0] if spx_expirations else 'None'}")

        # Find 0DTE or nearest expiration
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Try to find 0DTE
        use_exp = spy_expirations[0]  # Use nearest

        print(f"\nUsing expiration: {use_exp}")

        # Fetch options chains
        print("\nFetching options chains...")
        spy_chain = spy.option_chain(use_exp)
        spx_chain = spx.option_chain(use_exp)

        spy_calls = spy_chain.calls
        spx_calls = spx_chain.calls

        print(f"✅ SPY calls: {len(spy_calls)} strikes")
        print(f"✅ SPX calls: {len(spx_calls)} strikes")

        # Find ATM strikes
        spy_atm_strike = round(spy_price / 5) * 5  # Round to nearest $5
        spx_atm_strike = spy_atm_strike * 10

        print(f"\nLooking for ATM strikes:")
        print(f"  SPY: ${spy_atm_strike}")
        print(f"  SPX: ${spx_atm_strike}")

        # Find matching SPY option
        spy_atm = spy_calls[spy_calls['strike'] == spy_atm_strike]
        if len(spy_atm) == 0:
            print(f"❌ No SPY option at ${spy_atm_strike}")
            # Try nearby strikes
            nearby = spy_calls[(spy_calls['strike'] >= spy_atm_strike - 5) &
                              (spy_calls['strike'] <= spy_atm_strike + 5)]
            if len(nearby) > 0:
                spy_atm = nearby.iloc[[0]]
                spy_atm_strike = spy_atm['strike'].iloc[0]
                print(f"   Using nearby strike: ${spy_atm_strike}")

        # Find matching SPX option
        spx_atm_strike = spy_atm_strike * 10
        spx_atm = spx_calls[(spx_calls['strike'] >= spx_atm_strike - 10) &
                           (spx_calls['strike'] <= spx_atm_strike + 10)]
        if len(spx_atm) == 0:
            print(f"❌ No SPX option near ${spx_atm_strike}")
            return

        spx_atm = spx_atm.iloc[[0]]

        # Extract pricing
        print("\n" + "=" * 80)
        print("REAL MARKET PRICING")
        print("=" * 80)

        spy_bid = spy_atm['bid'].iloc[0]
        spy_ask = spy_atm['ask'].iloc[0]
        spy_last = spy_atm['lastPrice'].iloc[0]
        spy_vol = spy_atm.get('volume', [0]).iloc[0] if 'volume' in spy_atm else 0
        spy_oi = spy_atm.get('openInterest', [0]).iloc[0] if 'openInterest' in spy_atm else 0

        spx_bid = spx_atm['bid'].iloc[0]
        spx_ask = spx_atm['ask'].iloc[0]
        spx_last = spx_atm['lastPrice'].iloc[0]
        spx_vol = spx_atm.get('volume', [0]).iloc[0] if 'volume' in spx_atm else 0
        spx_oi = spx_atm.get('openInterest', [0]).iloc[0] if 'openInterest' in spx_atm else 0

        print(f"\nSPY ${spy_atm_strike:.0f} Call:")
        print(f"  Bid: ${spy_bid:.2f}")
        print(f"  Ask: ${spy_ask:.2f}")
        print(f"  Last: ${spy_last:.2f}")
        print(f"  Spread: ${spy_ask - spy_bid:.2f}")
        print(f"  Volume: {spy_vol}")
        print(f"  Open Interest: {spy_oi}")

        print(f"\nSPX ${spx_atm['strike'].iloc[0]:.0f} Call:")
        print(f"  Bid: ${spx_bid:.2f}")
        print(f"  Ask: ${spx_ask:.2f}")
        print(f"  Last: ${spx_last:.2f}")
        print(f"  Spread: ${spx_ask - spx_bid:.2f}")
        print(f"  Volume: {spx_vol}")
        print(f"  Open Interest: {spx_oi}")

        # Calculate the trade
        print("\n" + "=" * 80)
        print("THE TRADE (Using Real Prices)")
        print("=" * 80)

        print(f"\nEntry:")
        print(f"  BUY 1 SPX ${spx_atm['strike'].iloc[0]:.0f} call @ ${spx_ask:.2f} ask")
        print(f"  SELL 10 SPY ${spy_atm_strike:.0f} calls @ ${spy_bid:.2f} bid")

        entry_cost_spx = spx_ask * 100
        entry_credit_spy = spy_bid * 100 * 10
        entry_net = entry_credit_spy - entry_cost_spx
        commissions = 11 * 0.65
        net_credit = entry_net - commissions

        print(f"\nCash Flow:")
        print(f"  Pay for SPX:      -${entry_cost_spx:,.2f}")
        print(f"  Receive for SPY:  +${entry_credit_spy:,.2f}")
        print(f"  Net credit:       +${entry_net:,.2f}")
        print(f"  Commissions:      -${commissions:.2f}")
        print(f"  ────────────────────────────────")
        print(f"  NET CREDIT:       +${net_credit:,.2f}")

        if net_credit > 0:
            print(f"\n  ✅ PROFITABLE ENTRY! You collect ${net_credit:.2f}")
        else:
            print(f"\n  ❌ NOT PROFITABLE. You pay ${abs(net_credit):.2f}")

        # Compare to expected
        expected_credit = 637.85
        print(f"\n📊 Comparison:")
        print(f"  Expected (from analysis): ${expected_credit:.2f}")
        print(f"  Actual (from real data):  ${net_credit:.2f}")
        print(f"  Difference: ${net_credit - expected_credit:.2f}")

        if abs(net_credit - expected_credit) / expected_credit < 0.20:
            print(f"  ✅ Within 20% - analysis is accurate!")
        else:
            print(f"  ⚠️  Significant difference - market conditions may have changed")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nThis is likely because:")
        print("  1. Market is closed (data is stale/unavailable)")
        print("  2. yfinance API issues")
        print("  3. Network connectivity")
        print("\nRun this during market hours (9:30am-4pm ET) for live data")


if __name__ == "__main__":
    fetch_real_spy_spx_data()
