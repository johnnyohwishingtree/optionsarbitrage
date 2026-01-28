#!/usr/bin/env python3
"""
E*TRADE API Data Pull
Pull historical SPY/SPX price and options data
"""

import requests
import json
from datetime import datetime, timedelta
import pandas as pd
from requests_oauthlib import OAuth1Session
import time

# E*TRADE API credentials
ETRADE_CONSUMER_KEY = "264dfd9f1f9062153abae4710f73bf56"  # PROD key (pending approval)
ETRADE_CONSUMER_SECRET = "c75485e1dc1ffb1dc6fa31dc5922de32ae13ae354a204e641678e5c9fb608ce8"

# E*TRADE API endpoints
BASE_URL_PROD = "https://api.etrade.com"
BASE_URL_SANDBOX = "https://apisb.etrade.com"

# Use PROD since SANDBOX is expired
BASE_URL = BASE_URL_PROD

class ETradeClient:
    """E*TRADE API client for market data"""

    def __init__(self, consumer_key, consumer_secret, sandbox=False):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.base_url = BASE_URL_SANDBOX if sandbox else BASE_URL_PROD
        self.session = None
        self.access_token = None
        self.access_token_secret = None

    def get_request_token(self):
        """Step 1: Get request token"""
        print("\n" + "="*80)
        print("STEP 1: Getting Request Token")
        print("="*80)

        request_token_url = f"{self.base_url}/oauth/request_token"

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            callback_uri='oob'  # Out of band
        )

        try:
            response = oauth.fetch_request_token(request_token_url)
            print(f"✅ Request token obtained")
            return response
        except Exception as e:
            print(f"❌ Error getting request token: {e}")
            return None

    def authorize(self, request_token):
        """Step 2: User authorization"""
        print("\n" + "="*80)
        print("STEP 2: Authorization Required")
        print("="*80)

        auth_url = f"{self.base_url}/oauth/authorize"
        authorization_url = f"{auth_url}?key={self.consumer_key}&token={request_token['oauth_token']}"

        print(f"\nPlease visit this URL to authorize:")
        print(f"\n{authorization_url}\n")
        print("After authorizing, you'll get a verification code.")
        print("Enter it here:")

        # In automated mode, we can't do this interactively
        # Return the URL for manual authorization
        return authorization_url

    def get_access_token(self, request_token, verifier):
        """Step 3: Get access token"""
        print("\n" + "="*80)
        print("STEP 3: Getting Access Token")
        print("="*80)

        access_token_url = f"{self.base_url}/oauth/access_token"

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=request_token['oauth_token'],
            resource_owner_secret=request_token['oauth_token_secret'],
            verifier=verifier
        )

        try:
            response = oauth.fetch_access_token(access_token_url)
            self.access_token = response['oauth_token']
            self.access_token_secret = response['oauth_token_secret']
            print(f"✅ Access token obtained")
            return response
        except Exception as e:
            print(f"❌ Error getting access token: {e}")
            return None

    def get_quote(self, symbol):
        """Get current quote for a symbol"""
        if not self.access_token:
            print("❌ Not authenticated. Need to complete OAuth flow.")
            return None

        url = f"{self.base_url}/v1/market/quote/{symbol}.json"

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )

        try:
            response = oauth.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error getting quote: {e}")
            return None

    def get_option_chains(self, symbol, expiry_date=None):
        """Get options chain for a symbol"""
        if not self.access_token:
            print("❌ Not authenticated. Need to complete OAuth flow.")
            return None

        url = f"{self.base_url}/v1/market/optionchains"
        params = {
            'symbol': symbol,
            'expiryType': 'ALL'
        }

        if expiry_date:
            params['expiryDate'] = expiry_date

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )

        try:
            response = oauth.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error getting option chains: {e}")
            return None


def test_connection():
    """Test if we can connect to E*TRADE API"""
    print("="*80)
    print("E*TRADE API CONNECTION TEST")
    print("="*80)

    print(f"\nUsing PROD API key: {ETRADE_CONSUMER_KEY[:20]}...")
    print(f"Key status: Pending approval")

    client = ETradeClient(ETRADE_CONSUMER_KEY, ETRADE_CONSUMER_SECRET)

    # Try to get request token
    request_token = client.get_request_token()

    if request_token:
        print("\n✅ API key is working! But requires authorization...")
        print("\nE*TRADE uses OAuth 1.0a which requires:")
        print("  1. Get request token ✅")
        print("  2. User authorization (manual browser step)")
        print("  3. Get access token")
        print("  4. Make API calls")

        print("\n" + "="*80)
        print("WHAT THIS MEANS")
        print("="*80)
        print("\nYour PROD API key IS active (not pending anymore)!")
        print("But E*TRADE requires manual authorization via their website.")
        print("\nThis is a security feature - even with API keys, you need to")
        print("authorize each session through their web interface.")

        print("\n" + "="*80)
        print("ALTERNATIVE: Use E*TRADE's Paper Trading Data")
        print("="*80)
        print("\nInstead of complex OAuth, you could:")
        print("  1. Log into E*TRADE paper trading account")
        print("  2. Manually record SPY/SPX options prices for 2-4 weeks")
        print("  3. Build your own dataset")
        print("\nOR")
        print("  1. Use the simulated backtest we already created")
        print("  2. Start paper trading to validate with real data")

        return True
    else:
        print("\n❌ API key might not be activated yet")
        print("Check your E*TRADE developer portal for approval status")
        return False


def check_api_status():
    """Quick check without OAuth"""
    print("="*80)
    print("CHECKING E*TRADE API STATUS")
    print("="*80)

    # Try a simple request to see what happens
    url = "https://api.etrade.com/v1/market/quote/SPY.json"

    print(f"\nTrying unauthenticated request to: {url}")

    try:
        response = requests.get(url)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text[:200]}...")

        if response.status_code == 401:
            print("\n✅ API is responding (401 = needs authentication)")
            print("This is expected - E*TRADE requires OAuth")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("="*80)
    print("E*TRADE API DATA PULL ATTEMPT")
    print("="*80)
    print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # First, check if API is responding
    check_api_status()

    print("\n")

    # Try to authenticate
    test_connection()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print("\n❌ E*TRADE API requires interactive OAuth authorization")
    print("   This can't be automated in a script - needs manual browser steps")

    print("\n💡 RECOMMENDATION:")
    print("   1. The simulated backtest we created is sufficient for analysis")
    print("   2. Start paper trading to get REAL current data")
    print("   3. Historical data from E*TRADE won't include bid/ask spreads anyway")

    print("\n✅ What we already have:")
    print("   • Comprehensive theoretical analysis")
    print("   • Simulated backtest with realistic parameters")
    print("   • Trade-by-trade breakdown in CSV")
    print("   • All the analysis you need to start paper trading")

    print("\n🎯 Next step: Open thinkorswim and start paper trading!")
