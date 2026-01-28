#!/usr/bin/env python3
"""
Alternative methods to download real SPY/SPX price data for 2025
Try multiple approaches since yfinance is failing
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def method1_pandas_datareader():
    """Try pandas_datareader with Yahoo Finance"""
    print("\n" + "="*80)
    print("METHOD 1: pandas_datareader")
    print("="*80)

    try:
        import pandas_datareader as pdr

        start = "2025-01-01"
        end = datetime.now().strftime("%Y-%m-%d")

        print(f"Downloading SPY from {start} to {end}...")
        spy = pdr.get_data_yahoo('SPY', start=start, end=end)

        print(f"Downloading ^SPX from {start} to {end}...")
        spx = pdr.get_data_yahoo('^SPX', start=start, end=end)

        if len(spy) > 0 and len(spx) > 0:
            print(f"✅ SUCCESS! Got {len(spy)} days of SPY data")
            print(f"✅ SUCCESS! Got {len(spx)} days of SPX data")
            return spy, spx
        else:
            print("❌ No data returned")
            return None, None

    except ImportError:
        print("❌ pandas_datareader not installed")
        print("   Install with: pip install pandas-datareader")
        return None, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def method2_yfinance_simple():
    """Try yfinance with simpler approach"""
    print("\n" + "="*80)
    print("METHOD 2: yfinance (simple)")
    print("="*80)

    try:
        import yfinance as yf

        print("Downloading SPY...")
        spy = yf.download('SPY', start='2025-01-01', progress=False)

        print("Downloading ^SPX...")
        spx = yf.download('^SPX', start='2025-01-01', progress=False)

        if len(spy) > 0 and len(spx) > 0:
            print(f"✅ SUCCESS! Got {len(spy)} days of SPY data")
            print(f"✅ SUCCESS! Got {len(spx)} days of SPX data")
            return spy, spx
        else:
            print("❌ No data returned")
            return None, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def method3_manual_csv():
    """Try direct CSV download from Yahoo Finance"""
    print("\n" + "="*80)
    print("METHOD 3: Direct CSV download from Yahoo Finance")
    print("="*80)

    try:
        import requests
        from io import StringIO

        # Yahoo Finance uses Unix timestamps
        start_date = int(datetime(2025, 1, 1).timestamp())
        end_date = int(datetime.now().timestamp())

        symbols = {
            'SPY': 'SPY',
            'SPX': '%5ESPX'  # ^SPX URL encoded
        }

        data = {}

        for name, symbol in symbols.items():
            url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}"
            params = {
                'period1': start_date,
                'period2': end_date,
                'interval': '1d',
                'events': 'history'
            }

            print(f"Downloading {name}...")
            response = requests.get(url, params=params)

            if response.status_code == 200:
                df = pd.read_csv(StringIO(response.text))
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.set_index('Date')
                data[name] = df
                print(f"✅ Got {len(df)} days of {name} data")
            else:
                print(f"❌ Failed to download {name}: HTTP {response.status_code}")
                return None, None

        if 'SPY' in data and 'SPX' in data:
            return data['SPY'], data['SPX']
        else:
            return None, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def method4_2024_data():
    """Fallback to 2024 data if 2025 fails"""
    print("\n" + "="*80)
    print("METHOD 4: Try 2024 data instead")
    print("="*80)

    try:
        import yfinance as yf

        print("Downloading SPY (2024)...")
        spy = yf.download('SPY', start='2024-01-01', end='2024-12-31', progress=False)

        print("Downloading ^SPX (2024)...")
        spx = yf.download('^SPX', start='2024-01-01', end='2024-12-31', progress=False)

        if len(spy) > 0 and len(spx) > 0:
            print(f"✅ SUCCESS! Got {len(spy)} days of SPY data (2024)")
            print(f"✅ SUCCESS! Got {len(spx)} days of SPX data (2024)")
            return spy, spx, 2024
        else:
            print("❌ No data returned")
            return None, None, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def main():
    """Try all methods until one works"""
    print("="*80)
    print("ATTEMPTING TO DOWNLOAD REAL SPY/SPX PRICE DATA")
    print("="*80)

    # Try method 1
    spy, spx = method1_pandas_datareader()
    if spy is not None and spx is not None:
        save_data(spy, spx, 2025)
        return spy, spx, 2025

    # Try method 2
    spy, spx = method2_yfinance_simple()
    if spy is not None and spx is not None:
        save_data(spy, spx, 2025)
        return spy, spx, 2025

    # Try method 3
    spy, spx = method3_manual_csv()
    if spy is not None and spx is not None:
        save_data(spy, spx, 2025)
        return spy, spx, 2025

    # Try method 4 (2024 data)
    result = method4_2024_data()
    if result[0] is not None and result[1] is not None:
        save_data(result[0], result[1], result[2])
        return result

    print("\n" + "="*80)
    print("❌ ALL METHODS FAILED")
    print("="*80)
    print("\nPossible reasons:")
    print("  1. Market is closed / weekend")
    print("  2. Yahoo Finance API is down")
    print("  3. Network connectivity issues")
    print("  4. Rate limiting")
    print("\nTry running this during market hours or wait a few minutes and retry.")

    return None, None, None

def save_data(spy, spx, year):
    """Save downloaded data to CSV"""
    print("\n" + "="*80)
    print(f"SAVING {year} DATA TO CSV")
    print("="*80)

    spy.to_csv(f'spy_prices_{year}.csv')
    spx.to_csv(f'spx_prices_{year}.csv')

    print(f"✅ Saved: spy_prices_{year}.csv ({len(spy)} days)")
    print(f"✅ Saved: spx_prices_{year}.csv ({len(spx)} days)")

    # Show sample
    print(f"\n📊 Sample data (first 5 days):")
    print("\nSPY:")
    print(spy.head())
    print("\nSPX:")
    print(spx.head())

if __name__ == "__main__":
    spy, spx, year = main()

    if spy is not None:
        print(f"\n✅ Successfully downloaded {year} price data!")
        print(f"   SPY: {len(spy)} trading days")
        print(f"   SPX: {len(spx)} trading days")
    else:
        print("\n❌ Could not download data - will need to use simulated data")
