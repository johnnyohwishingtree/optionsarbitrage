#!/usr/bin/env python3
"""
SPY/SPX 0DTE Arbitrage Strategy
Entry and exit logic
"""

import logging
from datetime import datetime, time
from typing import Optional, Dict, Any, Tuple
from ib_insync import Contract, Option

logger = logging.getLogger(__name__)


class SPYSPXStrategy:
    """SPY/SPX 0DTE Credit Spread Strategy"""

    def __init__(self, config: dict):
        """
        Initialize strategy

        Args:
            config: Strategy configuration dict
        """
        self.config = config
        self.min_entry_credit = config.get('min_entry_credit', 400)
        self.assignment_threshold = config.get('assignment_risk_threshold', 10)
        self.spy_quantity = config.get('spy_contracts_per_spread', 10)
        self.spx_quantity = config.get('spx_contracts_per_spread', 1)

    def get_atm_strike(self, price: float, round_to: int = 5) -> float:
        """
        Get ATM strike rounded to nearest increment

        Args:
            price: Current price
            round_to: Strike increment (default: 5)

        Returns:
            ATM strike price
        """
        return round(price / round_to) * round_to

    def get_0dte_expiration(self) -> str:
        """
        Get today's expiration date in YYYYMMDD format

        Returns:
            Expiration string
        """
        return datetime.now().strftime('%Y%m%d')

    def is_entry_time(self) -> bool:
        """Check if it's time to enter trades (9:35 AM ET)"""
        now = datetime.now().time()
        entry_time = time(9, 35)
        entry_window_end = time(10, 0)

        return entry_time <= now <= entry_window_end

    def is_exit_time(self) -> bool:
        """Check if it's time to force exit (3:45 PM ET)"""
        now = datetime.now().time()
        exit_time = time(15, 45)

        return now >= exit_time

    def is_market_hours(self) -> bool:
        """Check if market is open (9:30 AM - 4:00 PM ET)"""
        now = datetime.now().time()
        market_open = time(9, 30)
        market_close = time(16, 0)

        return market_open <= now <= market_close

    def calculate_entry_credit(
        self,
        spy_call_price: float,
        spx_call_price: float,
        spy_put_price: float,
        spx_put_price: float,
        spy_quantity: int = None,
        spx_quantity: int = None
    ) -> Dict[str, float]:
        """
        Calculate entry credit for the double-sided spread

        Strategy: Always sell the more expensive option and buy the cheaper one to collect credit
        - Compares SPY vs SPX on calls side (accounting for 10:1 ratio)
        - Compares SPY vs SPX on puts side (accounting for 10:1 ratio)
        - Dynamically determines which to sell and which to buy

        Args:
            spy_call_price: SPY call mid price
            spx_call_price: SPX call mid price
            spy_put_price: SPY put mid price
            spx_put_price: SPX put mid price
            spy_quantity: Number of SPY contracts (default: from config)
            spx_quantity: Number of SPX contracts (default: from config)

        Returns:
            Dict with credit calculation breakdown and trade structure
        """
        spy_qty = spy_quantity or self.spy_quantity
        spx_qty = spx_quantity or self.spx_quantity

        # CALLS SIDE: Compare effective prices (accounting for 10:1 ratio)
        # 1 SPX call vs 10 SPY calls
        spx_call_total = spx_call_price * 100 * spx_qty      # 1 SPX call value
        spy_call_total = spy_call_price * 100 * spy_qty      # 10 SPY calls value

        if spx_call_total > spy_call_total:
            # SPX calls are more expensive → Sell SPX, Buy SPY
            calls_credit = spx_call_total - spy_call_total
            calls_structure = "SELL_SPX_BUY_SPY"
        else:
            # SPY calls are more expensive → Sell SPY, Buy SPX
            calls_credit = spy_call_total - spx_call_total
            calls_structure = "SELL_SPY_BUY_SPX"

        # PUTS SIDE: Compare effective prices (accounting for 10:1 ratio)
        # 1 SPX put vs 10 SPY puts
        spx_put_total = spx_put_price * 100 * spx_qty        # 1 SPX put value
        spy_put_total = spy_put_price * 100 * spy_qty        # 10 SPY puts value

        if spy_put_total > spx_put_total:
            # SPY puts are more expensive → Sell SPY, Buy SPX
            puts_credit = spy_put_total - spx_put_total
            puts_structure = "SELL_SPY_BUY_SPX"
        else:
            # SPX puts are more expensive → Sell SPX, Buy SPY
            puts_credit = spx_put_total - spy_put_total
            puts_structure = "SELL_SPX_BUY_SPY"

        # Total gross credit
        gross_credit = calls_credit + puts_credit

        # Commissions ($0.65 per contract)
        total_contracts = (spy_qty * 2) + (spx_qty * 2)  # Both sides
        commissions = total_contracts * 0.65

        # Net credit after commissions
        net_credit = gross_credit - commissions

        return {
            'calls_credit': calls_credit,
            'calls_structure': calls_structure,
            'spy_call_total': spy_call_total,
            'spx_call_total': spx_call_total,
            'puts_credit': puts_credit,
            'puts_structure': puts_structure,
            'spy_put_total': spy_put_total,
            'spx_put_total': spx_put_total,
            'gross_credit': gross_credit,
            'commissions': commissions,
            'net_credit': net_credit,
            'spy_quantity': spy_qty,
            'spx_quantity': spx_qty,
        }

    def should_enter_trade(
        self,
        spy_price: float,
        spx_price: float,
        spy_call_price: float,
        spx_call_price: float,
        spy_put_price: float,
        spx_put_price: float,
        trades_today: int
    ) -> Tuple[bool, str]:
        """
        Determine if we should enter a trade

        Args:
            spy_price: Current SPY price
            spx_price: Current SPX price
            spy_call_price: SPY call mid price
            spx_call_price: SPX call mid price
            spy_put_price: SPY put mid price
            spx_put_price: SPX put mid price
            trades_today: Number of trades already done today

        Returns:
            (should_trade, reason)
        """
        # Check if it's the right time
        if not self.is_entry_time():
            return False, "Outside entry window (9:35-10:00 AM)"

        # Check max trades per day
        max_spreads = self.config.get('max_spreads_per_day', 2)
        if trades_today >= max_spreads:
            return False, f"Max trades per day reached ({max_spreads})"

        # Check tracking ratio (SPX should be ~10x SPY)
        ratio = spx_price / spy_price
        if not (9.95 <= ratio <= 10.05):
            return False, f"Tracking error too high (ratio: {ratio:.4f})"

        # Calculate entry credit
        credit_calc = self.calculate_entry_credit(
            spy_call_price, spx_call_price, spy_put_price, spx_put_price
        )
        net_credit = credit_calc['net_credit']

        # Check minimum credit
        if net_credit < self.min_entry_credit:
            return False, f"Entry credit too low (${net_credit:.2f} < ${self.min_entry_credit})"

        # Check individual legs have positive credit
        if credit_calc['calls_credit'] <= 0:
            return False, "Calls side has zero or negative credit"

        if credit_calc['puts_credit'] <= 0:
            return False, "Puts side has zero or negative credit"

        # All checks passed
        return True, f"Entry credit: ${net_credit:.2f} (Calls: {credit_calc['calls_structure']}, Puts: {credit_calc['puts_structure']})"

    def should_exit_position(
        self,
        spy_price: float,
        spy_call_strike: float,
        spy_put_strike: float,
        spx_price: float,
        spx_call_strike: float,
        spx_put_strike: float,
        entry_credit: float,
        current_pnl: float = None
    ) -> Tuple[bool, str]:
        """
        Determine if we should exit an open position

        Args:
            spy_price: Current SPY price
            spy_call_strike: SPY call strike
            spy_put_strike: SPY put strike
            spx_price: Current SPX price
            spx_call_strike: SPX call strike
            spx_put_strike: SPX put strike
            entry_credit: Credit received at entry
            current_pnl: Current P&L (optional)

        Returns:
            (should_exit, reason)
        """
        # Check if it's close to market close
        if self.is_exit_time():
            return True, "Pre-expiration close (3:45 PM)"

        # Check assignment risk on calls (sold SPY calls)
        # We sold 10 SPY calls, so we're SHORT SPY calls
        spy_call_itm = spy_price - spy_call_strike
        if spy_call_itm > self.assignment_threshold:
            return True, f"Assignment risk on SPY calls (${spy_call_itm:.2f} ITM)"

        # Check assignment risk on puts (sold SPY puts)
        # We sold 10 SPY puts, so we're SHORT SPY puts
        spy_put_itm = spy_put_strike - spy_price
        if spy_put_itm > self.assignment_threshold:
            return True, f"Assignment risk on SPY puts (${spy_put_itm:.2f} ITM)"

        # Check max loss
        max_loss = self.config.get('max_position_loss', 1000)
        if current_pnl and current_pnl < -max_loss:
            return True, f"Max loss hit (${current_pnl:.2f})"

        # Check for extreme tracking error (both sides losing heavily)
        # This would indicate a major market event
        if spy_call_itm > 10 and spy_put_itm > 10:
            return True, "Extreme volatility - both sides ITM"

        # No exit signal
        return False, "Position OK"

    def calculate_exit_cost(
        self,
        spy_call_price: float,
        spx_call_price: float,
        spy_put_price: float,
        spx_put_price: float,
        calls_structure: str,
        puts_structure: str,
        spy_quantity: int = None,
        spx_quantity: int = None
    ) -> Dict[str, float]:
        """
        Calculate cost to close the position

        Reverses the entry structure - if we sold X and bought Y at entry,
        we now buy back X and sell Y to close.

        Args:
            spy_call_price: SPY call mid price
            spx_call_price: SPX call mid price
            spy_put_price: SPY put mid price
            spx_put_price: SPX put mid price
            calls_structure: Entry structure for calls (SELL_SPX_BUY_SPY or SELL_SPY_BUY_SPX)
            puts_structure: Entry structure for puts (SELL_SPX_BUY_SPY or SELL_SPY_BUY_SPX)
            spy_quantity: Number of SPY contracts
            spx_quantity: Number of SPX contracts

        Returns:
            Dict with exit cost breakdown
        """
        spy_qty = spy_quantity or self.spy_quantity
        spx_qty = spx_quantity or self.spx_quantity

        # CALLS SIDE: Reverse the entry structure
        spy_call_total = spy_call_price * 100 * spy_qty
        spx_call_total = spx_call_price * 100 * spx_qty

        if calls_structure == "SELL_SPX_BUY_SPY":
            # We sold SPX, bought SPY → Now buy back SPX, sell SPY
            calls_cost = spx_call_total - spy_call_total
        else:  # SELL_SPY_BUY_SPX
            # We sold SPY, bought SPX → Now buy back SPY, sell SPX
            calls_cost = spy_call_total - spx_call_total

        # PUTS SIDE: Reverse the entry structure
        spy_put_total = spy_put_price * 100 * spy_qty
        spx_put_total = spx_put_price * 100 * spx_qty

        if puts_structure == "SELL_SPY_BUY_SPX":
            # We sold SPY, bought SPX → Now buy back SPY, sell SPX
            puts_cost = spy_put_total - spx_put_total
        else:  # SELL_SPX_BUY_SPY
            # We sold SPX, bought SPY → Now buy back SPX, sell SPY
            puts_cost = spx_put_total - spy_put_total

        # Total gross cost
        gross_cost = calls_cost + puts_cost

        # Commissions
        total_contracts = (spy_qty * 2) + (spx_qty * 2)  # All 4 legs
        commissions = total_contracts * 0.65

        # Total cost including commissions
        total_cost = gross_cost + commissions

        return {
            'calls_cost': calls_cost,
            'puts_cost': puts_cost,
            'gross_cost': gross_cost,
            'commissions': commissions,
            'total_cost': total_cost,
        }

    def calculate_final_pnl(
        self,
        entry_credit: float,
        calls_structure: str,
        puts_structure: str,
        exit_cost: float = None,
        spy_settlement: float = None,
        spx_settlement: float = None,
        spy_call_strike: float = None,
        spy_put_strike: float = None,
        spx_call_strike: float = None,
        spx_put_strike: float = None
    ) -> Dict[str, float]:
        """
        Calculate final P&L

        Args:
            entry_credit: Credit received at entry
            calls_structure: Entry structure for calls (SELL_SPX_BUY_SPY or SELL_SPY_BUY_SPX)
            puts_structure: Entry structure for puts (SELL_SPX_BUY_SPY or SELL_SPY_BUY_SPX)
            exit_cost: Cost to close early (if closed)
            spy_settlement: SPY settlement price (if held to expiry)
            spx_settlement: SPX settlement price (if held to expiry)
            spy_call_strike: SPY call strike
            spy_put_strike: SPY put strike
            spx_call_strike: SPX call strike
            spx_put_strike: SPX put strike

        Returns:
            Dict with P&L breakdown
        """
        if exit_cost is not None:
            # Closed early
            net_pnl = entry_credit - exit_cost
            return {
                'entry_credit': entry_credit,
                'exit_cost': exit_cost,
                'net_pnl': net_pnl,
                'exit_type': 'EARLY_CLOSE'
            }
        else:
            # Held to expiration - calculate settlement based on structure

            # CALLS SIDE
            spy_call_payout = max(0, spy_settlement - spy_call_strike) * 100 * self.spy_quantity
            spx_call_payout = max(0, spx_settlement - spx_call_strike) * 100 * self.spx_quantity

            if calls_structure == "SELL_SPX_BUY_SPY":
                # We're long SPY calls, short SPX calls
                calls_settlement = spy_call_payout - spx_call_payout
            else:  # SELL_SPY_BUY_SPX
                # We're long SPX calls, short SPY calls
                calls_settlement = spx_call_payout - spy_call_payout

            # PUTS SIDE
            spy_put_payout = max(0, spy_put_strike - spy_settlement) * 100 * self.spy_quantity
            spx_put_payout = max(0, spx_put_strike - spx_settlement) * 100 * self.spx_quantity

            if puts_structure == "SELL_SPY_BUY_SPX":
                # We're long SPX puts, short SPY puts
                puts_settlement = spx_put_payout - spy_put_payout
            else:  # SELL_SPX_BUY_SPY
                # We're long SPY puts, short SPX puts
                puts_settlement = spy_put_payout - spx_put_payout

            net_settlement = calls_settlement + puts_settlement
            net_pnl = entry_credit + net_settlement

            return {
                'entry_credit': entry_credit,
                'spy_call_payout': spy_call_payout,
                'spx_call_payout': spx_call_payout,
                'calls_settlement': calls_settlement,
                'spy_put_payout': spy_put_payout,
                'spx_put_payout': spx_put_payout,
                'puts_settlement': puts_settlement,
                'net_settlement': net_settlement,
                'net_pnl': net_pnl,
                'exit_type': 'HELD_TO_EXPIRY'
            }

    def create_option_contracts(
        self,
        spy_price: float,
        spx_price: float
    ) -> Dict[str, Contract]:
        """
        Create option contracts for the double-sided trade

        Structure:
        - CALLS: Sell 1 SPX call, Buy 10 SPY calls
        - PUTS: Sell 10 SPY puts, Buy 1 SPX put

        Args:
            spy_price: Current SPY price
            spx_price: Current SPX price

        Returns:
            Dict with all 4 option contracts and strikes
        """
        expiration = self.get_0dte_expiration()

        spy_strike = self.get_atm_strike(spy_price, round_to=1)  # SPY: $1 increments
        spx_strike = self.get_atm_strike(spx_price, round_to=5)  # SPX: $5 increments

        # Create all 4 contracts
        spy_call = Option(
            symbol='SPY',
            lastTradeDateOrContractMonth=expiration,
            strike=spy_strike,
            right='C',
            exchange='SMART'
        )

        spx_call = Option(
            symbol='SPX',
            lastTradeDateOrContractMonth=expiration,
            strike=spx_strike,
            right='C',
            exchange='SMART'  # Will be routed to CBOE
        )

        spy_put = Option(
            symbol='SPY',
            lastTradeDateOrContractMonth=expiration,
            strike=spy_strike,
            right='P',
            exchange='SMART'
        )

        spx_put = Option(
            symbol='SPX',
            lastTradeDateOrContractMonth=expiration,
            strike=spx_strike,
            right='P',
            exchange='SMART'  # Will be routed to CBOE
        )

        return {
            'spy_call': spy_call,
            'spx_call': spx_call,
            'spy_put': spy_put,
            'spx_put': spx_put,
            'spy_call_strike': spy_strike,
            'spy_put_strike': spy_strike,
            'spx_call_strike': spx_strike,
            'spx_put_strike': spx_strike,
            'expiration': expiration,
        }


if __name__ == "__main__":
    # Test strategy logic with dynamic price-based structure
    config = {
        'min_entry_credit': 800,
        'assignment_risk_threshold': 10,
        'spy_contracts_per_spread': 10,
        'spx_contracts_per_spread': 1,
        'max_spreads_per_day': 2,
        'max_position_loss': 1000,
    }

    strategy = SPYSPXStrategy(config)

    # Test scenario
    spy_price = 600.0
    spx_price = 6000.0

    # Example prices - strategy will dynamically determine what to sell/buy
    spy_call = 2.50
    spx_call = 30.00
    spy_put = 3.00
    spx_put = 28.00

    print("Testing dynamic price-based strategy")
    print(f"SPY: ${spy_price:.2f}, SPX: ${spx_price:.2f}")
    print(f"\nOption prices:")
    print(f"  SPY call: ${spy_call:.2f} (× 10 = ${spy_call*10:.2f})")
    print(f"  SPX call: ${spx_call:.2f}")
    print(f"  SPY put: ${spy_put:.2f} (× 10 = ${spy_put*10:.2f})")
    print(f"  SPX put: ${spx_put:.2f}")

    credit = strategy.calculate_entry_credit(spy_call, spx_call, spy_put, spx_put)

    print(f"\nCALLS structure: {credit['calls_structure']}")
    print(f"  Credit: ${credit['calls_credit']:.2f}")
    print(f"\nPUTS structure: {credit['puts_structure']}")
    print(f"  Credit: ${credit['puts_credit']:.2f}")
    print(f"\nTotal net credit: ${credit['net_credit']:.2f}")
