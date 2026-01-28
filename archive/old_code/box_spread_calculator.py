#!/usr/bin/env python3
"""
Box Spread Calculator
Calculates potential returns from box spread arbitrage on SPX options
"""

from datetime import datetime, timedelta
from typing import Dict, Optional


class BoxSpreadCalculator:
    """Calculator for box spread arbitrage opportunities"""

    def __init__(self, risk_free_rate: float = 0.04):
        """
        Initialize calculator

        Args:
            risk_free_rate: Current risk-free rate (e.g., 0.04 for 4%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_box_value(
        self,
        strike_low: float,
        strike_high: float,
        call_low_bid: float,
        call_low_ask: float,
        call_high_bid: float,
        call_high_ask: float,
        put_low_bid: float,
        put_low_ask: float,
        put_high_bid: float,
        put_high_ask: float,
        days_to_expiration: int
    ) -> Dict:
        """
        Calculate box spread value and returns

        Box Spread Components:
        - Buy call at strike_low (pay call_low_ask)
        - Sell call at strike_high (receive call_high_bid)
        - Sell put at strike_low (receive put_low_bid)
        - Buy put at strike_high (pay put_high_ask)

        Args:
            strike_low: Lower strike price
            strike_high: Higher strike price
            call/put_low/high_bid/ask: Option prices
            days_to_expiration: Days until expiration

        Returns:
            Dictionary with box spread analysis
        """

        # Calculate cost to enter box spread (pay asks, receive bids)
        cost_to_enter = (
            call_low_ask         # Pay for long call at low strike
            - call_high_bid      # Receive for short call at high strike
            - put_low_bid        # Receive for short put at low strike
            + put_high_ask       # Pay for long put at high strike
        )

        # Box spread guaranteed value at expiration
        guaranteed_value = strike_high - strike_low

        # Calculate profit
        profit = guaranteed_value - cost_to_enter

        # Calculate returns
        if cost_to_enter > 0:
            roi_percent = (profit / cost_to_enter) * 100

            # Annualized return
            years_to_exp = days_to_expiration / 365.0
            if years_to_exp > 0:
                annualized_return = ((guaranteed_value / cost_to_enter) ** (1 / years_to_exp) - 1) * 100
            else:
                annualized_return = 0.0
        else:
            roi_percent = 0.0
            annualized_return = 0.0

        # Calculate risk-free rate equivalent
        years_to_exp = days_to_expiration / 365.0
        risk_free_value = cost_to_enter * (1 + self.risk_free_rate * years_to_exp)

        # Edge over risk-free rate
        edge_dollars = guaranteed_value - risk_free_value
        edge_bps = ((guaranteed_value / risk_free_value - 1) * 10000) if risk_free_value > 0 else 0

        # Is this worth it?
        is_arbitrage = profit > 0
        is_worthwhile = edge_bps > 25  # At least 25 basis points edge

        return {
            "strike_low": strike_low,
            "strike_high": strike_high,
            "spread_width": guaranteed_value,
            "cost_to_enter": cost_to_enter,
            "guaranteed_value": guaranteed_value,
            "profit": profit,
            "roi_percent": roi_percent,
            "annualized_return": annualized_return,
            "days_to_expiration": days_to_expiration,
            "years_to_expiration": years_to_exp,
            "risk_free_rate": self.risk_free_rate,
            "risk_free_value": risk_free_value,
            "edge_dollars": edge_dollars,
            "edge_basis_points": edge_bps,
            "is_arbitrage": is_arbitrage,
            "is_worthwhile": is_worthwhile,
            "recommendation": self._get_recommendation(is_arbitrage, is_worthwhile, edge_bps)
        }

    def _get_recommendation(self, is_arbitrage: bool, is_worthwhile: bool, edge_bps: float) -> str:
        """Get trading recommendation"""
        if not is_arbitrage:
            return "❌ NO ARBITRAGE - Cost exceeds guaranteed value"

        if edge_bps < 10:
            return "⚠️  EDGE TOO SMALL - Transaction costs will eat profit"
        elif edge_bps < 25:
            return "⚠️  MARGINAL - Only worth it with low commissions"
        elif edge_bps < 50:
            return "✅ DECENT - Worth considering for large capital"
        else:
            return "🔥 EXCELLENT - Strong edge, investigate immediately"

    def calculate_breakeven_cost(
        self,
        strike_low: float,
        strike_high: float,
        days_to_expiration: int,
        target_return: float = 0.04
    ) -> float:
        """
        Calculate maximum cost to pay for box spread given target return

        Args:
            strike_low: Lower strike
            strike_high: Higher strike
            days_to_expiration: Days until expiration
            target_return: Desired annualized return (e.g., 0.04 for 4%)

        Returns:
            Maximum price to pay for box spread
        """
        guaranteed_value = strike_high - strike_low
        years_to_exp = days_to_expiration / 365.0

        # Calculate max cost: PV of guaranteed value
        max_cost = guaranteed_value / (1 + target_return * years_to_exp)

        return max_cost

    def print_analysis(self, result: Dict):
        """Print formatted analysis"""
        print("\n" + "=" * 70)
        print("BOX SPREAD ANALYSIS")
        print("=" * 70)

        print(f"\n📊 Spread Structure:")
        print(f"  Lower Strike:  ${result['strike_low']:,.2f}")
        print(f"  Higher Strike: ${result['strike_high']:,.2f}")
        print(f"  Spread Width:  ${result['spread_width']:,.2f}")

        print(f"\n💰 Financial Analysis:")
        print(f"  Cost to Enter:       ${result['cost_to_enter']:,.2f}")
        print(f"  Guaranteed Value:    ${result['guaranteed_value']:,.2f}")
        print(f"  Profit:              ${result['profit']:,.2f}")

        print(f"\n📈 Returns:")
        print(f"  ROI:                 {result['roi_percent']:.2f}%")
        print(f"  Annualized Return:   {result['annualized_return']:.2f}%")
        print(f"  Days to Expiration:  {result['days_to_expiration']}")

        print(f"\n🎯 Comparison to Risk-Free:")
        print(f"  Risk-Free Rate:      {result['risk_free_rate'] * 100:.2f}%")
        print(f"  Risk-Free Value:     ${result['risk_free_value']:,.2f}")
        print(f"  Edge over Risk-Free: ${result['edge_dollars']:.2f}")
        print(f"  Edge (basis points): {result['edge_basis_points']:.0f} bps")

        print(f"\n✅ Recommendation:")
        print(f"  {result['recommendation']}")

        print("\n" + "=" * 70 + "\n")


def example_usage():
    """Example usage of box spread calculator"""

    calc = BoxSpreadCalculator(risk_free_rate=0.04)

    print("Example 1: Typical Box Spread on SPX")
    print("-" * 70)

    # Example: SPX 5900/6100 box spread, 365 days to expiration
    result = calc.calculate_box_value(
        strike_low=5900,
        strike_high=6100,
        call_low_bid=210.50,
        call_low_ask=211.00,      # Buy at ask
        call_high_bid=11.00,      # Sell at bid
        call_high_ask=11.50,
        put_low_bid=10.50,        # Sell at bid
        put_low_ask=11.00,
        put_high_bid=210.00,
        put_high_ask=210.50,      # Buy at ask
        days_to_expiration=365
    )

    calc.print_analysis(result)

    # Calculate what we should pay for 4.5% return
    print("\n" + "=" * 70)
    print("Target Return Analysis")
    print("=" * 70)

    max_cost_4pct = calc.calculate_breakeven_cost(5900, 6100, 365, 0.04)
    max_cost_5pct = calc.calculate_breakeven_cost(5900, 6100, 365, 0.05)

    print(f"\nFor a 5900/6100 box spread (365 days):")
    print(f"  Max cost for 4.0% return: ${max_cost_4pct:.2f}")
    print(f"  Max cost for 5.0% return: ${max_cost_5pct:.2f}")
    print(f"  Current market cost:      ${result['cost_to_enter']:.2f}")

    if result['cost_to_enter'] < max_cost_5pct:
        print(f"  ✅ Current cost is BELOW 5% threshold - Good deal!")
    elif result['cost_to_enter'] < max_cost_4pct:
        print(f"  ✅ Current cost gives >4% but <5% return - Decent")
    else:
        print(f"  ❌ Current cost is too high for target returns")

    print("\n" + "=" * 70)
    print("⚠️  IMPORTANT REMINDERS")
    print("=" * 70)
    print("1. Use EUROPEAN options only (SPX, NDX, XSP)")
    print("2. Never use American options (SPY, QQQ, IWM) - assignment risk!")
    print("3. Portfolio margin account recommended for capital efficiency")
    print("4. Account for transaction costs (~$0.50-$1.00 per leg)")
    print("5. Ensure sufficient margin and don't over-leverage")
    print("6. This is synthetic borrowing, not free money")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    example_usage()
