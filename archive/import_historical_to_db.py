#!/usr/bin/env python3
"""
Import historical intraday CSV data into SQLite database
"""

import pandas as pd
import sqlite3
from datetime import datetime

# Load the CSV
df = pd.read_csv('data/historical_intraday.csv')

print(f"Loading {len(df)} rows from historical_intraday.csv")

# Connect to database
conn = sqlite3.connect('data/market_data.db')
cursor = conn.cursor()

# Parse the data
imported = 0
for _, row in df.iterrows():
    contract_type = row['contract']  # e.g., 'spy_call', 'spx_put'

    # Parse contract type
    parts = contract_type.split('_')
    symbol = parts[0].upper()  # SPY or SPX
    right = 'C' if parts[1] == 'call' else 'P'

    # Use close price as the main price
    price = row['close']

    # Convert datetime
    timestamp = pd.to_datetime(row['datetime']).isoformat()

    # Determine strikes (using today's ATM)
    if symbol == 'SPY':
        strike = 694.0  # ATM strike used in historical fetch
    else:  # SPX
        strike = 6960.0  # ATM strike used in historical fetch

    expiration = '20260126'  # Today's date

    # Insert into option_prices table
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO option_prices
            (timestamp, symbol, expiration, strike, right,
             bid, ask, last, volume, open_interest, implied_vol,
             delta, gamma, theta, vega, underlying_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            symbol,
            expiration,
            strike,
            right,
            None,  # No bid data in historical bars
            None,  # No ask data in historical bars
            price,  # Using close as last price
            int(row['volume']) if pd.notna(row['volume']) else None,
            None,  # No open interest in bars
            None,  # No IV in bars
            None, None, None, None,  # No greeks in bars
            None  # No underlying price stored
        ))
        imported += 1
    except Exception as e:
        print(f"Error inserting row: {e}")
        continue

conn.commit()
conn.close()

print(f"✅ Imported {imported} option prices into database")

# Verify
conn = sqlite3.connect('data/market_data.db')
cursor = conn.cursor()

print("\n📊 Database Summary:")
cursor.execute("SELECT COUNT(*) FROM option_prices")
total = cursor.fetchone()[0]
print(f"   Total option_prices rows: {total}")

cursor.execute("SELECT COUNT(DISTINCT symbol) FROM option_prices")
symbols = cursor.fetchone()[0]
print(f"   Unique symbols: {symbols}")

cursor.execute("SELECT COUNT(DISTINCT timestamp) FROM option_prices")
timestamps = cursor.fetchone()[0]
print(f"   Unique timestamps: {timestamps}")

cursor.execute("SELECT symbol, right, COUNT(*) as count FROM option_prices GROUP BY symbol, right")
for row in cursor.fetchall():
    print(f"   {row[0]} {row[1]}: {row[2]} rows")

conn.close()
