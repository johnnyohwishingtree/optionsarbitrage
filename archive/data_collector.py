#!/usr/bin/env python3
"""
Data Collector for SPY/SPX Options
Collects real-time option prices from IB Gateway and stores in SQLite
"""

import sys
import os
import time
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.broker.ibkr_client import IBKRClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and stores SPY/SPX option data"""

    def __init__(self, db_path: str = 'data/market_data.db'):
        """Initialize data collector"""
        self.db_path = db_path
        self.client = None
        self._setup_database()

    def _setup_database(self):
        """Create database tables if they don't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Underlying prices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS underlying_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                bid REAL,
                ask REAL,
                volume INTEGER,
                UNIQUE(timestamp, symbol)
            )
        ''')

        # Options prices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS option_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                expiration TEXT NOT NULL,
                strike REAL NOT NULL,
                right TEXT NOT NULL,
                bid REAL,
                ask REAL,
                last REAL,
                volume INTEGER,
                open_interest INTEGER,
                implied_vol REAL,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL,
                underlying_price REAL,
                UNIQUE(timestamp, symbol, expiration, strike, right)
            )
        ''')

        # Daily snapshot table (captures ATM options at specific time)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                snapshot_time TEXT NOT NULL,
                spy_price REAL NOT NULL,
                spx_price REAL NOT NULL,
                spy_call_strike REAL NOT NULL,
                spy_call_bid REAL,
                spy_call_ask REAL,
                spy_put_strike REAL NOT NULL,
                spy_put_bid REAL,
                spy_put_ask REAL,
                spx_call_strike REAL NOT NULL,
                spx_call_bid REAL,
                spx_call_ask REAL,
                spx_put_strike REAL NOT NULL,
                spx_put_bid REAL,
                spx_put_ask REAL,
                expiration TEXT NOT NULL,
                UNIQUE(date, snapshot_time)
            )
        ''')

        conn.commit()
        conn.close()

        logger.info(f"Database initialized at {self.db_path}")

    def connect(self) -> bool:
        """Connect to IB Gateway"""
        host = os.getenv('IB_HOST', '127.0.0.1')
        port = int(os.getenv('IB_PORT', 4002))
        client_id = 100  # Use unique ID for data collector

        logger.info(f"Connecting to IB Gateway at {host}:{port}...")
        self.client = IBKRClient(host=host, port=port, client_id=client_id)

        if self.client.connect():
            logger.info("✅ Connected to IB Gateway")
            return True
        else:
            logger.error("❌ Failed to connect to IB Gateway")
            return False

    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.client:
            self.client.disconnect()
            logger.info("Disconnected from IB Gateway")

    def collect_underlying_prices(self):
        """Collect current SPY and SPX prices"""
        timestamp = datetime.now().isoformat()

        spy_price = self.client.get_current_price('SPY')
        spx_price = self.client.get_current_price('SPX')

        if not spy_price or not spx_price:
            logger.warning("Could not fetch underlying prices")
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Store SPY
        cursor.execute('''
            INSERT OR REPLACE INTO underlying_prices
            (timestamp, symbol, price, bid, ask)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, 'SPY', spy_price, None, None))

        # Store SPX
        cursor.execute('''
            INSERT OR REPLACE INTO underlying_prices
            (timestamp, symbol, price, bid, ask)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, 'SPX', spx_price, None, None))

        conn.commit()
        conn.close()

        logger.info(f"Stored prices: SPY=${spy_price:.2f}, SPX=${spx_price:.2f}")

        return {'SPY': spy_price, 'SPX': spx_price}

    def get_atm_strike(self, price: float, round_to: int) -> float:
        """Get ATM strike"""
        return round(price / round_to) * round_to

    def collect_option_chain(self, symbol: str, expiration: str, strikes: List[float], right: str):
        """Collect option prices for a chain"""
        timestamp = datetime.now().isoformat()
        underlying_price = self.client.get_current_price(symbol)

        if not underlying_price:
            logger.warning(f"Could not fetch {symbol} price")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for strike in strikes:
            quote = self.client.get_option_quote(symbol, strike, right, expiration)

            if quote:
                cursor.execute('''
                    INSERT OR REPLACE INTO option_prices
                    (timestamp, symbol, expiration, strike, right,
                     bid, ask, last, volume, open_interest, implied_vol,
                     delta, gamma, theta, vega, underlying_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp, symbol, expiration, strike, right,
                    quote.get('bid'), quote.get('ask'), quote.get('last'),
                    quote.get('volume'), quote.get('open_interest'),
                    quote.get('implied_vol'), quote.get('delta'),
                    quote.get('gamma'), quote.get('theta'), quote.get('vega'),
                    underlying_price
                ))

                logger.info(f"Stored: {symbol} {strike} {right} bid={quote.get('bid')} ask={quote.get('ask')}")
            else:
                logger.warning(f"No quote for {symbol} {strike} {right}")

            time.sleep(0.5)  # Rate limiting

        conn.commit()
        conn.close()

    def collect_daily_snapshot(self):
        """Collect a daily snapshot of ATM options (for backtesting)"""
        timestamp = datetime.now().isoformat()
        date = datetime.now().strftime('%Y-%m-%d')
        snapshot_time = datetime.now().strftime('%H:%M:%S')

        # Get expiration (today for 0DTE)
        expiration = datetime.now().strftime('%Y%m%d')

        # Get underlying prices
        prices = self.collect_underlying_prices()
        if not prices:
            return

        spy_price = prices['SPY']
        spx_price = prices['SPX']

        # Calculate ATM strikes
        spy_call_strike = self.get_atm_strike(spy_price, 1)
        spy_put_strike = self.get_atm_strike(spy_price, 1)
        spx_call_strike = self.get_atm_strike(spx_price, 5)
        spx_put_strike = self.get_atm_strike(spx_price, 5)

        logger.info(f"Collecting ATM options: SPY {spy_call_strike}, SPX {spx_call_strike}")

        # Get option quotes
        spy_call = self.client.get_option_quote('SPY', spy_call_strike, 'C', expiration)
        spy_put = self.client.get_option_quote('SPY', spy_put_strike, 'P', expiration)
        spx_call = self.client.get_option_quote('SPX', spx_call_strike, 'C', expiration)
        spx_put = self.client.get_option_quote('SPX', spx_put_strike, 'P', expiration)

        # Store snapshot
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO daily_snapshots
            (date, snapshot_time, spy_price, spx_price,
             spy_call_strike, spy_call_bid, spy_call_ask,
             spy_put_strike, spy_put_bid, spy_put_ask,
             spx_call_strike, spx_call_bid, spx_call_ask,
             spx_put_strike, spx_put_bid, spx_put_ask,
             expiration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date, snapshot_time, spy_price, spx_price,
            spy_call_strike,
            spy_call.get('bid') if spy_call else None,
            spy_call.get('ask') if spy_call else None,
            spy_put_strike,
            spy_put.get('bid') if spy_put else None,
            spy_put.get('ask') if spy_put else None,
            spx_call_strike,
            spx_call.get('bid') if spx_call else None,
            spx_call.get('ask') if spx_call else None,
            spx_put_strike,
            spx_put.get('bid') if spx_put else None,
            spx_put.get('ask') if spx_put else None,
            expiration
        ))

        conn.commit()
        conn.close()

        logger.info(f"✅ Daily snapshot saved for {date} {snapshot_time}")

    def run_continuous_collection(self, interval_seconds: int = 300):
        """Run continuous data collection"""
        logger.info(f"Starting continuous collection (every {interval_seconds}s)")

        while True:
            try:
                self.collect_daily_snapshot()
                logger.info(f"Sleeping for {interval_seconds} seconds...")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                logger.info("Stopping data collection...")
                break
            except Exception as e:
                logger.error(f"Error during collection: {e}")
                time.sleep(60)  # Wait a minute on error

    def export_to_csv(self, table_name: str, output_file: str):
        """Export table to CSV"""
        import pandas as pd

        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()

        df.to_csv(output_file, index=False)
        logger.info(f"Exported {len(df)} rows to {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Collect SPY/SPX market data')
    parser.add_argument('--mode', choices=['snapshot', 'continuous'], default='snapshot',
                        help='Collection mode')
    parser.add_argument('--interval', type=int, default=300,
                        help='Collection interval in seconds (for continuous mode)')
    parser.add_argument('--export', type=str, help='Export table to CSV')

    args = parser.parse_args()

    collector = DataCollector()

    if args.export:
        collector.export_to_csv(args.export, f'data/{args.export}.csv')
        return

    if not collector.connect():
        logger.error("Failed to connect to IB Gateway")
        return

    try:
        if args.mode == 'snapshot':
            logger.info("Collecting single snapshot...")
            collector.collect_daily_snapshot()
            logger.info("✅ Snapshot complete")

        elif args.mode == 'continuous':
            logger.info(f"Starting continuous collection (every {args.interval}s)")
            logger.info("Press Ctrl+C to stop")
            collector.run_continuous_collection(args.interval)

    finally:
        collector.disconnect()


if __name__ == "__main__":
    main()
