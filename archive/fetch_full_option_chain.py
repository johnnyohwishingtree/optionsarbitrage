#!/usr/bin/env python3
"""
Fetch full options chain with multiple strikes for today
Gets historical intraday data for all reasonable strikes
"""

import sys
import os
import sqlite3
from datetime import datetime
from typing import List
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


class FullChainFetcher:
    """Fetch full options chain with multiple strikes"""

    def __init__(self, db_path: str = 'data/market_data.db'):
        self.db_path = db_path
        self.client = None

    def connect(self) -> bool:
        """Connect to IB Gateway"""
        host = os.getenv('IB_HOST', '127.0.0.1')
        port = int(os.getenv('IB_PORT', 4002))
        client_id = 102  # Different ID

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

    def get_strike_range(self, current_price: float, symbol: str) -> List[float]:
        """
        Get a reasonable range of strikes around current price

        For SPY: $1 increments, ±3% range
        For SPX: $5 increments, ±3% range
        """
        if symbol == 'SPY':
            increment = 1
            range_pct = 0.03  # ±3%
        else:  # SPX
            increment = 5
            range_pct = 0.03  # ±3%

        min_strike = current_price * (1 - range_pct)
        max_strike = current_price * (1 + range_pct)

        # Round to nearest increment
        min_strike = round(min_strike / increment) * increment
        max_strike = round(max_strike / increment) * increment

        strikes = []
        strike = min_strike
        while strike <= max_strike:
            strikes.append(strike)
            strike += increment

        return strikes

    def fetch_full_chain(self):
        """Fetch full options chain for multiple strikes"""
        logger.info("Fetching full options chain...")

        # Get today's date
        today = datetime.now().strftime('%Y%m%d')

        # Get current prices
        spy_price = self.client.get_current_price('SPY')
        spx_price = self.client.get_current_price('SPX')

        if not spy_price or not spx_price:
            logger.error("Could not get current prices")
            return

        logger.info(f"Current prices: SPY=${spy_price:.2f}, SPX=${spx_price:.2f}")

        # Get strike ranges
        spy_strikes = self.get_strike_range(spy_price, 'SPY')
        spx_strikes = self.get_strike_range(spx_price, 'SPX')

        logger.info(f"\n📊 SPY Strikes: {len(spy_strikes)} strikes from ${spy_strikes[0]:.0f} to ${spy_strikes[-1]:.0f}")
        logger.info(f"📊 SPX Strikes: {len(spx_strikes)} strikes from ${spx_strikes[0]:.0f} to ${spx_strikes[-1]:.0f}")

        total_contracts = (len(spy_strikes) * 2) + (len(spx_strikes) * 2)  # calls + puts for each
        logger.info(f"\n🔄 Will fetch historical data for {total_contracts} option contracts")
        logger.info(f"⏱️  This may take a few minutes...\n")

        all_results = []

        # Fetch SPY options
        logger.info("="*80)
        logger.info("FETCHING SPY OPTIONS")
        logger.info("="*80)

        for i, strike in enumerate(spy_strikes, 1):
            logger.info(f"\n[{i}/{len(spy_strikes)}] SPY Strike ${strike:.0f}")

            # Calls
            spy_call = Option('SPY', today, strike, 'C', 'SMART')
            self.client.ib.qualifyContracts(spy_call)
            call_bars = self.get_historical_bars(spy_call, f'SPY_{strike}_C')
            if call_bars:
                all_results.append({'contract': spy_call, 'bars': call_bars, 'type': 'spy_call', 'strike': strike})

            # Puts
            spy_put = Option('SPY', today, strike, 'P', 'SMART')
            self.client.ib.qualifyContracts(spy_put)
            put_bars = self.get_historical_bars(spy_put, f'SPY_{strike}_P')
            if put_bars:
                all_results.append({'contract': spy_put, 'bars': put_bars, 'type': 'spy_put', 'strike': strike})

        # Fetch SPX options
        logger.info("\n" + "="*80)
        logger.info("FETCHING SPX OPTIONS")
        logger.info("="*80)

        for i, strike in enumerate(spx_strikes, 1):
            logger.info(f"\n[{i}/{len(spx_strikes)}] SPX Strike ${strike:.0f}")

            # Calls
            spx_call = Option('SPX', today, strike, 'C', 'SMART')
            self.client.ib.qualifyContracts(spx_call)
            call_bars = self.get_historical_bars(spx_call, f'SPX_{strike}_C')
            if call_bars:
                all_results.append({'contract': spx_call, 'bars': call_bars, 'type': 'spx_call', 'strike': strike})

            # Puts
            spx_put = Option('SPX', today, strike, 'P', 'SMART')
            self.client.ib.qualifyContracts(spx_put)
            put_bars = self.get_historical_bars(spx_put, f'SPX_{strike}_P')
            if put_bars:
                all_results.append({'contract': spx_put, 'bars': put_bars, 'type': 'spx_put', 'strike': strike})

        return all_results

    def get_historical_bars(self, contract, label: str):
        """Get historical bars for a contract"""
        try:
            bars = self.client.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr="1 D",
                barSizeSetting="5 mins",
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            logger.info(f"  ✓ {label}: {len(bars)} bars")
            return bars

        except Exception as e:
            logger.error(f"  ✗ {label}: {e}")
            return []

    def save_to_database(self, results):
        """Save all results to database"""
        logger.info("\n" + "="*80)
        logger.info("SAVING TO DATABASE")
        logger.info("="*80)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        total_bars = 0
        today = datetime.now().strftime('%Y%m%d')

        for result in results:
            contract = result['contract']
            bars = result['bars']
            strike = result['strike']

            symbol = contract.symbol
            right = contract.right

            for bar in bars:
                timestamp = bar.date.isoformat()

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
                        today,
                        strike,
                        right,
                        None,
                        None,
                        bar.close,
                        int(bar.volume) if bar.volume else None,
                        None, None, None, None, None, None, None
                    ))
                    total_bars += 1
                except Exception as e:
                    logger.error(f"Error inserting bar: {e}")

        conn.commit()
        conn.close()

        logger.info(f"✅ Saved {total_bars} bars to database")

    def save_to_csv(self, results, output_file: str = 'data/full_option_chain.csv'):
        """Save to CSV"""
        import pandas as pd

        all_data = []

        for result in results:
            contract = result['contract']
            bars = result['bars']
            strike = result['strike']

            for bar in bars:
                all_data.append({
                    'symbol': contract.symbol,
                    'strike': strike,
                    'right': contract.right,
                    'datetime': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                })

        if all_data:
            df = pd.DataFrame(all_data)
            df.to_csv(output_file, index=False)
            logger.info(f"✅ Saved {len(all_data)} bars to {output_file}")


def main():
    fetcher = FullChainFetcher()

    if not fetcher.connect():
        logger.error("Failed to connect to IB Gateway")
        return

    try:
        results = fetcher.fetch_full_chain()

        if results:
            logger.info(f"\n✅ Fetched data for {len(results)} option contracts")

            fetcher.save_to_database(results)
            fetcher.save_to_csv(results)

            # Summary
            logger.info("\n" + "="*80)
            logger.info("SUMMARY")
            logger.info("="*80)

            spy_calls = len([r for r in results if r['type'] == 'spy_call'])
            spy_puts = len([r for r in results if r['type'] == 'spy_put'])
            spx_calls = len([r for r in results if r['type'] == 'spx_call'])
            spx_puts = len([r for r in results if r['type'] == 'spx_put'])

            logger.info(f"SPY Calls: {spy_calls} strikes")
            logger.info(f"SPY Puts:  {spy_puts} strikes")
            logger.info(f"SPX Calls: {spx_calls} strikes")
            logger.info(f"SPX Puts:  {spx_puts} strikes")
            logger.info(f"Total:     {len(results)} option contracts")

        else:
            logger.error("No results returned")

    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    main()
