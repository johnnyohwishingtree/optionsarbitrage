#!/usr/bin/env python3
"""
Fetch historical intraday options data from IB
Pulls data from market open to now at specified intervals
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')

from src.broker.ibkr_client import IBKRClient
from ib_insync import Option
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """Fetch historical intraday options data"""

    def __init__(self, db_path: str = 'data/market_data.db'):
        self.db_path = db_path
        self.client = None

    def connect(self) -> bool:
        """Connect to IB Gateway"""
        host = os.getenv('IB_HOST', '127.0.0.1')
        port = int(os.getenv('IB_PORT', 4002))
        client_id = 101  # Different ID from collector

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

    def get_historical_bars(self, contract, duration: str = "1 D", bar_size: str = "5 mins"):
        """
        Get historical bars for a contract

        Args:
            contract: IB contract
            duration: How far back (e.g., "1 D", "2 D", "1 W")
            bar_size: Bar size (e.g., "1 min", "5 mins", "15 mins")

        Returns:
            List of bars
        """
        try:
            logger.info(f"Requesting historical data for {contract.symbol}...")

            bars = self.client.ib.reqHistoricalData(
                contract,
                endDateTime='',  # Current time
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )

            logger.info(f"Received {len(bars)} bars for {contract.symbol}")
            return bars

        except Exception as e:
            logger.error(f"Error getting historical data for {contract.symbol}: {e}")
            return []

    def fetch_todays_data(self):
        """Fetch all intraday data from today"""
        logger.info("Fetching historical intraday data from today...")

        # Get today's date
        today = datetime.now().strftime('%Y%m%d')

        # Get current SPY/SPX prices to determine strikes
        spy_price = self.client.get_current_price('SPY')
        spx_price = self.client.get_current_price('SPX')

        if not spy_price or not spx_price:
            logger.error("Could not get current prices")
            return

        logger.info(f"Current prices: SPY=${spy_price:.2f}, SPX=${spx_price:.2f}")

        # Calculate ATM strikes
        spy_strike = round(spy_price)
        spx_strike = round(spx_price / 5) * 5

        logger.info(f"Using strikes: SPY {spy_strike}, SPX {spx_strike}")

        # Create option contracts for 0DTE
        spy_call = Option('SPY', today, spy_strike, 'C', 'SMART')
        spy_put = Option('SPY', today, spy_strike, 'P', 'SMART')
        spx_call = Option('SPX', today, spx_strike, 'C', 'SMART')
        spx_put = Option('SPX', today, spx_strike, 'P', 'SMART')

        # Qualify contracts
        logger.info("Qualifying contracts...")
        self.client.ib.qualifyContracts(spy_call, spy_put, spx_call, spx_put)

        # Get historical bars for each
        results = {}

        logger.info("\n📊 Fetching SPY Call historical data...")
        results['spy_call'] = self.get_historical_bars(spy_call, duration="1 D", bar_size="5 mins")

        logger.info("\n📊 Fetching SPY Put historical data...")
        results['spy_put'] = self.get_historical_bars(spy_put, duration="1 D", bar_size="5 mins")

        logger.info("\n📊 Fetching SPX Call historical data...")
        results['spx_call'] = self.get_historical_bars(spx_call, duration="1 D", bar_size="5 mins")

        logger.info("\n📊 Fetching SPX Put historical data...")
        results['spx_put'] = self.get_historical_bars(spx_put, duration="1 D", bar_size="5 mins")

        return results

    def display_results(self, results: Dict):
        """Display the historical data"""
        if not results:
            return

        logger.info("\n" + "="*80)
        logger.info("HISTORICAL INTRADAY DATA SUMMARY")
        logger.info("="*80)

        for key, bars in results.items():
            if bars:
                logger.info(f"\n{key.upper()}: {len(bars)} bars")
                logger.info(f"  First: {bars[0].date} - Open: ${bars[0].open:.2f}, Close: ${bars[0].close:.2f}")
                logger.info(f"  Last:  {bars[-1].date} - Open: ${bars[-1].open:.2f}, Close: ${bars[-1].close:.2f}")

                # Show a few sample bars
                logger.info(f"\n  Sample bars:")
                for i, bar in enumerate(bars[:5]):  # First 5 bars
                    logger.info(f"    {bar.date}: Open=${bar.open:.2f}, High=${bar.high:.2f}, Low=${bar.low:.2f}, Close=${bar.close:.2f}, Vol={bar.volume}")
            else:
                logger.warning(f"\n{key.upper()}: No data")

    def save_to_csv(self, results: Dict, output_file: str = 'data/historical_intraday.csv'):
        """Save historical data to CSV"""
        import pandas as pd

        all_data = []

        for key, bars in results.items():
            if bars:
                for bar in bars:
                    all_data.append({
                        'contract': key,
                        'datetime': bar.date,
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': bar.volume,
                        'average': bar.average,
                        'barCount': bar.barCount
                    })

        if all_data:
            df = pd.DataFrame(all_data)
            df.to_csv(output_file, index=False)
            logger.info(f"\n✅ Saved {len(all_data)} bars to {output_file}")
        else:
            logger.warning("No data to save")


def main():
    fetcher = HistoricalDataFetcher()

    if not fetcher.connect():
        logger.error("Failed to connect to IB Gateway")
        return

    try:
        results = fetcher.fetch_todays_data()

        if results:
            fetcher.display_results(results)
            fetcher.save_to_csv(results)
        else:
            logger.error("No results returned")

    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    main()
