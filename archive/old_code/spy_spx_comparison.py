#!/usr/bin/env python3
"""
SPY vs SPX Options Comparison Tool
Fetches real options data and looks for arbitrage opportunities
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class SPYvsSPXAnalyzer:
    """Analyzes SPY vs SPX options for arbitrage opportunities"""

    def __init__(self, commission_per_contract: float = 0.65):
        """
        Initialize analyzer

        Args:
            commission_per_contract: Trading commission per contract
        """
        self.commission = commission_per_contract
        self.spy_data = None
        self.spx_data = None
        self.spy_price = None
        self.spx_price = None

    def fetch_data(self, expiration_date: Optional[str] = None):
        """
        Fetch SPY and SPX options data

        Args:
            expiration_date: Specific expiration date (YYYY-MM-DD) or None for nearest
        """
        print("Fetching SPY and SPX data...")
        print("-" * 70)

        # Fetch SPY
        spy = yf.Ticker("SPY")
        self.spy_price = spy.history(period="1d")['Close'].iloc[-1]
        print(f"SPY Current Price: ${self.spy_price:.2f}")

        # Fetch SPX (use ^SPX for index)
        spx = yf.Ticker("^SPX")
        self.spx_price = spx.history(period="1d")['Close'].iloc[-1]
        print(f"SPX Current Price: ${self.spx_price:.2f}")

        # Get available expirations
        spy_expirations = spy.options
        spx_expirations = spx.options

        if not spy_expirations or not spx_expirations:
            print("\n❌ ERROR: Could not fetch options expirations")
            return False

        # Find matching expiration date
        if expiration_date:
            if expiration_date not in spy_expirations or expiration_date not in spx_expirations:
                print(f"\n❌ ERROR: Expiration {expiration_date} not available for both SPY and SPX")
                return False
            selected_exp = expiration_date
        else:
            # Find common expiration dates
            common_exps = set(spy_expirations) & set(spx_expirations)
            if not common_exps:
                print("\n❌ ERROR: No common expiration dates found")
                return False
            selected_exp = sorted(common_exps)[0]  # Use nearest expiration

        print(f"Using Expiration: {selected_exp}")

        # Fetch options chains
        spy_options = spy.option_chain(selected_exp)
        spx_options = spx.option_chain(selected_exp)

        self.spy_calls = spy_options.calls
        self.spy_puts = spy_options.puts
        self.spx_calls = spx_options.calls
        self.spx_puts = spx_options.puts

        print(f"✅ Fetched {len(self.spy_calls)} SPY call options")
        print(f"✅ Fetched {len(self.spx_calls)} SPX call options")
        print(f"✅ Fetched {len(self.spy_puts)} SPY put options")
        print(f"✅ Fetched {len(self.spx_puts)} SPX put options\n")

        return True

    def compare_calls(self, strike_range_pct: float = 0.10) -> pd.DataFrame:
        """
        Compare SPY vs SPX call options at equivalent strikes

        Args:
            strike_range_pct: Range around current price to analyze (0.10 = ±10%)

        Returns:
            DataFrame with comparison results
        """
        results = []

        # Filter strikes around current price
        spy_min = self.spy_price * (1 - strike_range_pct)
        spy_max = self.spy_price * (1 + strike_range_pct)

        spy_calls_filtered = self.spy_calls[
            (self.spy_calls['strike'] >= spy_min) &
            (self.spy_calls['strike'] <= spy_max)
        ].copy()

        for _, spy_row in spy_calls_filtered.iterrows():
            spy_strike = spy_row['strike']
            spx_strike = spy_strike * 10  # SPX is 10x SPY

            # Find matching SPX strike (within $5 tolerance)
            spx_matches = self.spx_calls[
                (self.spx_calls['strike'] >= spx_strike - 5) &
                (self.spx_calls['strike'] <= spx_strike + 5)
            ]

            if len(spx_matches) == 0:
                continue

            spx_row = spx_matches.iloc[0]

            # Get bid/ask prices
            spy_bid = spy_row.get('bid', 0)
            spy_ask = spy_row.get('ask', 0)
            spx_bid = spx_row.get('bid', 0)
            spx_ask = spx_row.get('ask', 0)

            # Skip if no valid prices
            if spy_bid == 0 or spy_ask == 0 or spx_bid == 0 or spx_ask == 0:
                continue

            # Calculate expected SPX price (10x SPY)
            expected_spx_mid = (spy_bid + spy_ask) / 2 * 10
            actual_spx_mid = (spx_bid + spx_ask) / 2

            # Calculate discrepancy
            discrepancy_dollars = actual_spx_mid - expected_spx_mid
            discrepancy_pct = (discrepancy_dollars / expected_spx_mid) * 100

            # Calculate potential arbitrage
            # Strategy: If SPX is overpriced, sell 1 SPX call, buy 10 SPY calls
            # Strategy: If SPX is underpriced, buy 1 SPX call, sell 10 SPY calls

            if discrepancy_dollars > 0:
                # SPX is more expensive
                strategy = "Sell SPX, Buy 10x SPY"
                profit_potential = spx_bid - (spy_ask * 10)
                all_in_cost = self.commission * 11  # 1 SPX + 10 SPY contracts
                net_profit = profit_potential - all_in_cost
            else:
                # SPX is cheaper
                strategy = "Buy SPX, Sell 10x SPY"
                profit_potential = (spy_bid * 10) - spx_ask
                all_in_cost = self.commission * 11
                net_profit = profit_potential - all_in_cost

            results.append({
                'SPY_Strike': spy_strike,
                'SPX_Strike': spx_row['strike'],
                'SPY_Bid': spy_bid,
                'SPY_Ask': spy_ask,
                'SPY_Mid': (spy_bid + spy_ask) / 2,
                'SPX_Bid': spx_bid,
                'SPX_Ask': spx_ask,
                'SPX_Mid': actual_spx_mid,
                'Expected_SPX': expected_spx_mid,
                'Discrepancy_$': discrepancy_dollars,
                'Discrepancy_%': discrepancy_pct,
                'SPY_Spread': spy_ask - spy_bid,
                'SPX_Spread': spx_ask - spx_bid,
                'Strategy': strategy,
                'Gross_Profit': profit_potential,
                'Commissions': all_in_cost,
                'Net_Profit': net_profit,
                'SPY_Volume': spy_row.get('volume', 0),
                'SPX_Volume': spx_row.get('volume', 0),
                'SPY_OI': spy_row.get('openInterest', 0),
                'SPX_OI': spx_row.get('openInterest', 0)
            })

        return pd.DataFrame(results)

    def find_arbitrage_opportunities(self, results_df: pd.DataFrame, min_profit: float = 1.0) -> pd.DataFrame:
        """
        Filter for actual arbitrage opportunities

        Args:
            results_df: DataFrame from compare_calls()
            min_profit: Minimum net profit per spread to consider

        Returns:
            DataFrame with arbitrage opportunities only
        """
        opportunities = results_df[results_df['Net_Profit'] > min_profit].copy()
        opportunities = opportunities.sort_values('Net_Profit', ascending=False)

        return opportunities

    def print_summary(self, results_df: pd.DataFrame):
        """Print summary of analysis"""
        print("\n" + "=" * 70)
        print("ANALYSIS SUMMARY")
        print("=" * 70)

        print(f"\nMarket Conditions:")
        print(f"  SPY Price: ${self.spy_price:.2f}")
        print(f"  SPX Price: ${self.spx_price:.2f}")
        print(f"  Ratio: {self.spx_price / self.spy_price:.2f}x (expected 10.0x)")

        if len(results_df) == 0:
            print("\n❌ No valid comparisons found (missing bid/ask data)")
            return

        print(f"\nOptions Analyzed:")
        print(f"  Strike pairs compared: {len(results_df)}")

        print(f"\nPrice Discrepancies:")
        avg_disc = results_df['Discrepancy_%'].mean()
        max_disc = results_df['Discrepancy_%'].max()
        min_disc = results_df['Discrepancy_%'].min()
        print(f"  Average: {avg_disc:.2f}%")
        print(f"  Maximum: {max_disc:.2f}%")
        print(f"  Minimum: {min_disc:.2f}%")

        print(f"\nBid-Ask Spreads:")
        avg_spy_spread = results_df['SPY_Spread'].mean()
        avg_spx_spread = results_df['SPX_Spread'].mean()
        print(f"  Average SPY spread: ${avg_spy_spread:.2f}")
        print(f"  Average SPX spread: ${avg_spx_spread:.2f}")
        print(f"  SPX spread is {avg_spx_spread / avg_spy_spread:.1f}x wider than SPY")

        # Find opportunities
        opportunities = results_df[results_df['Net_Profit'] > 0]
        print(f"\nArbitrage Opportunities:")
        print(f"  Positive net profit: {len(opportunities)} out of {len(results_df)}")

        if len(opportunities) > 0:
            total_profit = opportunities['Net_Profit'].sum()
            best_profit = opportunities['Net_Profit'].max()
            print(f"  Total available profit: ${total_profit:.2f}")
            print(f"  Best opportunity: ${best_profit:.2f}")

            print("\n🎯 TOP 5 OPPORTUNITIES:")
            print("-" * 70)
            top_5 = opportunities.head(5)
            for idx, row in top_5.iterrows():
                print(f"\n  Strike: SPY ${row['SPY_Strike']:.2f} / SPX ${row['SPX_Strike']:.2f}")
                print(f"  Strategy: {row['Strategy']}")
                print(f"  Gross Profit: ${row['Gross_Profit']:.2f}")
                print(f"  Commissions: ${row['Commissions']:.2f}")
                print(f"  NET PROFIT: ${row['Net_Profit']:.2f}")
                print(f"  Discrepancy: {row['Discrepancy_%']:.2f}%")
        else:
            print(f"  ❌ NO PROFITABLE ARBITRAGE FOUND after commissions")
            print(f"\n  Why? Bid-ask spreads and commissions eat the edge.")
            print(f"  Average SPX spread (${avg_spx_spread:.2f}) is too wide.")

    def export_results(self, results_df: pd.DataFrame, filename: str = "spy_spx_comparison.csv"):
        """Export results to CSV"""
        if len(results_df) > 0:
            results_df.to_csv(filename, index=False)
            print(f"\n✅ Results exported to {filename}")


def main():
    """Main execution"""
    print("=" * 70)
    print("SPY vs SPX OPTIONS ARBITRAGE ANALYZER")
    print("=" * 70)
    print()

    analyzer = SPYvsSPXAnalyzer(commission_per_contract=0.65)

    # Fetch data (will use nearest common expiration)
    success = analyzer.fetch_data()

    if not success:
        print("\n❌ Failed to fetch options data")
        print("Note: yfinance may have rate limits or delays")
        return

    # Compare call options
    print("\nAnalyzing call options...")
    results = analyzer.compare_calls(strike_range_pct=0.05)  # ±5% from current price

    if len(results) == 0:
        print("\n❌ No results to analyze")
        print("This could mean:")
        print("  1. No matching strikes found")
        print("  2. Missing bid/ask data (common with yfinance)")
        print("  3. Market is closed")
        return

    # Print summary
    analyzer.print_summary(results)

    # Export detailed results
    analyzer.export_results(results)

    print("\n" + "=" * 70)
    print("⚠️  IMPORTANT CAVEATS")
    print("=" * 70)
    print("1. This uses delayed/free data (may be 15-20 min old)")
    print("2. yfinance data quality varies - some bid/ask may be stale")
    print("3. Real arbitrage requires REAL-TIME data")
    print("4. Even if opportunities exist, they disappear in seconds")
    print("5. You're competing with algos that see data microseconds faster")
    print("6. Don't forget: SPX is European, SPY is American (different risk)")
    print("=" * 70)


if __name__ == "__main__":
    main()
