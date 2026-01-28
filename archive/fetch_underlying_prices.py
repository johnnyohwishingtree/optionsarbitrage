#!/usr/bin/env python3
"""
Fetch historical intraday prices for SPY and SPX
Get 5-minute bars to match the options data
"""

import sys
import os
import sqlite3
from datetime import datetime
import logging

sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.broker.ibkr_client import IBKRClient
from ib_insync import Stock, Contract
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnderlyingPriceFetcher:
    """Fetch historical underlying prices"""

    def __init__(self, db_path: str = 'data/market_data.db'):
        self.db_path = db_path
        self.client = None

    def connect(self) -> bool:
        """Connect to IB Gateway"""
        host = os.getenv('IB_HOST', '127.0.0.1')
        port = int(os.getenv('IB_PORT', 4002))
        client_id = 103

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

    def fetch_historical_prices(self):
        """Fetch historical intraday prices for SPY and SPX"""
        logger.info("Fetching historical intraday prices...")

        # SPY (stock)
        logger.info("\n📊 Fetching SPY historical prices...")
        spy_contract = Stock('SPY', 'SMART', 'USD')
        self.client.ib.qualifyContracts(spy_contract)

        spy_bars = self.client.ib.reqHistoricalData(
            spy_contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='5 mins',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        logger.info(f"✅ Received {len(spy_bars)} SPY bars")

        # SPX (index)
        logger.info("\n📊 Fetching SPX historical prices...")
        spx_contract = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
        self.client.ib.qualifyContracts(spx_contract)

        spx_bars = self.client.ib.reqHistoricalData(
            spx_contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='5 mins',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        logger.info(f"✅ Received {len(spx_bars)} SPX bars")

        return {
            'SPY': spy_bars,
            'SPX': spx_bars
        }

    def save_to_database(self, results):
        """Save underlying prices to database"""
        logger.info("\n" + "="*80)
        logger.info("SAVING TO DATABASE")
        logger.info("="*80)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear old underlying prices
        cursor.execute("DELETE FROM underlying_prices")

        total_saved = 0

        for symbol, bars in results.items():
            logger.info(f"\nSaving {symbol}: {len(bars)} bars")

            for bar in bars:
                timestamp = bar.date.isoformat()

                try:
                    cursor.execute('''
                        INSERT INTO underlying_prices
                        (timestamp, symbol, price, bid, ask, volume)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        timestamp,
                        symbol,
                        bar.close,  # Use close as the main price
                        None,  # No bid in historical bars
                        None,  # No ask in historical bars
                        int(bar.volume) if bar.volume else None
                    ))
                    total_saved += 1
                except Exception as e:
                    logger.error(f"Error inserting bar: {e}")

        conn.commit()
        conn.close()

        logger.info(f"\n✅ Saved {total_saved} underlying price bars to database")

    def save_to_csv(self, results, output_file: str = 'data/underlying_prices.csv'):
        """Save to CSV"""
        import pandas as pd

        all_data = []

        for symbol, bars in results.items():
            for bar in bars:
                all_data.append({
                    'symbol': symbol,
                    'datetime': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'average': bar.average,
                })

        if all_data:
            df = pd.DataFrame(all_data)
            df.to_csv(output_file, index=False)
            logger.info(f"✅ Saved {len(all_data)} bars to {output_file}")

    def calculate_correlation(self):
        """Calculate correlation between SPY and SPX movements"""
        import pandas as pd

        logger.info("\n" + "="*80)
        logger.info("CALCULATING SPY/SPX CORRELATION")
        logger.info("="*80)

        conn = sqlite3.connect(self.db_path)

        # Get SPY prices
        spy_df = pd.read_sql_query(
            "SELECT timestamp, price FROM underlying_prices WHERE symbol='SPY' ORDER BY timestamp",
            conn
        )
        spy_df['datetime'] = pd.to_datetime(spy_df['timestamp'])
        spy_df = spy_df.set_index('datetime')

        # Get SPX prices
        spx_df = pd.read_sql_query(
            "SELECT timestamp, price FROM underlying_prices WHERE symbol='SPX' ORDER BY timestamp",
            conn
        )
        spx_df['datetime'] = pd.to_datetime(spx_df['timestamp'])
        spx_df = spx_df.set_index('datetime')

        conn.close()

        # Calculate returns
        spy_df['returns'] = spy_df['price'].pct_change()
        spx_df['returns'] = spx_df['price'].pct_change()

        # Merge on timestamp
        merged = spy_df[['price', 'returns']].join(
            spx_df[['price', 'returns']],
            rsuffix='_spx',
            how='inner'
        )

        # Calculate correlation
        correlation = merged['returns'].corr(merged['returns_spx'])

        logger.info(f"\n📊 SPY/SPX Correlation: {correlation:.6f}")
        logger.info(f"   Data points: {len(merged)}")

        # Calculate tracking error (difference in % returns)
        merged['tracking_error'] = merged['returns'] - merged['returns_spx']
        avg_tracking_error = merged['tracking_error'].abs().mean()
        max_tracking_error = merged['tracking_error'].abs().max()

        logger.info(f"\n📉 Tracking Error:")
        logger.info(f"   Average: {avg_tracking_error*100:.4f}%")
        logger.info(f"   Maximum: {max_tracking_error*100:.4f}%")

        # Show some examples
        logger.info(f"\n📋 Sample Price Movements:")
        logger.info(f"{'Time':<20} {'SPY':<10} {'SPX':<12} {'SPY %':<10} {'SPX %':<10} {'Diff':<10}")
        logger.info("-" * 80)

        for i in range(0, min(10, len(merged)), 1):
            row = merged.iloc[i]
            time_str = row.name.strftime('%H:%M:%S')
            spy_ret = row['returns'] * 100
            spx_ret = row['returns_spx'] * 100
            diff = row['tracking_error'] * 100

            logger.info(
                f"{time_str:<20} "
                f"${row['price']:<9.2f} "
                f"${row['price_spx']:<11.2f} "
                f"{spy_ret:>9.4f}% "
                f"{spx_ret:>9.4f}% "
                f"{diff:>9.4f}%"
            )

        return correlation


def main():
    fetcher = UnderlyingPriceFetcher()

    if not fetcher.connect():
        logger.error("Failed to connect to IB Gateway")
        return

    try:
        results = fetcher.fetch_historical_prices()

        if results:
            fetcher.save_to_database(results)
            fetcher.save_to_csv(results)

            # Calculate correlation
            correlation = fetcher.calculate_correlation()

            logger.info("\n" + "="*80)
            logger.info("SUMMARY")
            logger.info("="*80)
            logger.info(f"SPY bars: {len(results['SPY'])}")
            logger.info(f"SPX bars: {len(results['SPX'])}")
            logger.info(f"Correlation: {correlation:.6f}")
            logger.info("\n✅ All data saved to database and CSV")

        else:
            logger.error("No results returned")

    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    main()
