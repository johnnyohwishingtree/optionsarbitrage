"""
Position construction for options arbitrage strategies.

Pure functions for determining leg setup, calculating credits, and estimating margin.
No UI imports.
"""

from src.config import MARGIN_RATE
from src.models import Leg, Position


def determine_leg_setup(
    call_direction: str,
    put_direction: str,
    sym1: str,
    sym2: str,
    qty_ratio: int,
    sym1_strike: float,
    sym2_strike: float,
    sym1_call_price: float,
    sym2_call_price: float,
    sym1_put_price: float,
    sym2_put_price: float,
    show_calls: bool,
    show_puts: bool,
) -> Position:
    """
    Build a Position from strategy parameters.

    Determines which symbol is sold/bought for calls and puts based on direction strings,
    assigns quantities based on qty_ratio, and calculates credits and margin.

    Args:
        call_direction: e.g. "Buy SPX, Sell SPY" or "Sell SPX, Buy SPY"
        put_direction: e.g. "Buy SPY, Sell SPX" or "Sell SPY, Buy SPX"
        sym1, sym2: Symbol names
        qty_ratio: Quantity ratio (10 for SPX, 1 for XSP)
        sym1_strike, sym2_strike: Strike prices
        sym1_call_price, sym2_call_price: Call option prices
        sym1_put_price, sym2_put_price: Put option prices
        show_calls, show_puts: Which legs to include

    Returns:
        Position with legs, credits, and margin.
    """
    legs = []
    call_credit = 0.0
    put_credit = 0.0

    if show_calls:
        if call_direction == f"Buy {sym2}, Sell {sym1}":
            # Sell SYM1 calls, Buy SYM2 calls
            sell_qty = qty_ratio
            buy_qty = 1
            sell_price = sym1_call_price
            buy_price = sym2_call_price
            sell_sym = sym1
            buy_sym = sym2
            sell_strike = sym1_strike
            buy_strike = sym2_strike
        else:  # f"Sell {sym2}, Buy {sym1}"
            # Sell SYM2 calls, Buy SYM1 calls
            sell_qty = 1
            buy_qty = qty_ratio
            sell_price = sym2_call_price
            buy_price = sym1_call_price
            sell_sym = sym2
            buy_sym = sym1
            sell_strike = sym2_strike
            buy_strike = sym1_strike

        legs.append(Leg(sell_sym, sell_strike, 'C', 'SELL', sell_qty, sell_price))
        legs.append(Leg(buy_sym, buy_strike, 'C', 'BUY', buy_qty, buy_price))
        call_credit = calculate_credit(sell_price, sell_qty, buy_price, buy_qty)

    if show_puts:
        if put_direction == f"Buy {sym1}, Sell {sym2}":
            # Sell SYM2 puts, Buy SYM1 puts
            sell_qty = 1
            buy_qty = qty_ratio
            sell_price = sym2_put_price
            buy_price = sym1_put_price
            sell_sym = sym2
            buy_sym = sym1
            sell_strike = sym2_strike
            buy_strike = sym1_strike
        else:  # f"Sell {sym1}, Buy {sym2}"
            # Sell SYM1 puts, Buy SYM2 puts
            sell_qty = qty_ratio
            buy_qty = 1
            sell_price = sym1_put_price
            buy_price = sym2_put_price
            sell_sym = sym1
            buy_sym = sym2
            sell_strike = sym1_strike
            buy_strike = sym2_strike

        legs.append(Leg(sell_sym, sell_strike, 'P', 'SELL', sell_qty, sell_price))
        legs.append(Leg(buy_sym, buy_strike, 'P', 'BUY', buy_qty, buy_price))
        put_credit = calculate_credit(sell_price, sell_qty, buy_price, buy_qty)

    total_credit = call_credit + put_credit
    margin = calculate_margin_from_legs(legs, call_credit, put_credit)

    return Position(
        legs=legs,
        call_credit=call_credit,
        put_credit=put_credit,
        total_credit=total_credit,
        estimated_margin=margin,
    )


def calculate_credit(sell_price: float, sell_qty: int,
                     buy_price: float, buy_qty: int) -> float:
    """Calculate net credit from selling and buying options."""
    return (sell_price * sell_qty * 100) - (buy_price * buy_qty * 100)


def calculate_margin_from_legs(
    legs: list[Leg],
    call_credit: float = 0.0,
    put_credit: float = 0.0,
    margin_rate: float = MARGIN_RATE,
) -> float:
    """
    Estimate margin requirement from position legs.

    Margin = 20% of short notional value minus credit received.
    Long legs don't require additional margin (protective).
    """
    call_margin = 0.0
    put_margin = 0.0

    for leg in legs:
        if leg.action == 'SELL':
            short_notional = leg.quantity * leg.strike * 100 * margin_rate
            if leg.right == 'C':
                call_margin += short_notional
            else:
                put_margin += short_notional

    call_margin = max(0, call_margin - call_credit)
    put_margin = max(0, put_margin - put_credit)

    return call_margin + put_margin
