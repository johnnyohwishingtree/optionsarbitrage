"""Tests for src/position.py - position construction and margin."""

import pytest
from src.position import determine_leg_setup, calculate_credit, calculate_margin_from_legs
from src.models import Leg


class TestCalculateCredit:
    def test_positive_credit(self):
        """Sell price > buy price yields positive credit."""
        credit = calculate_credit(sell_price=2.50, sell_qty=10, buy_price=2.00, buy_qty=1)
        assert credit == (2.50 * 10 * 100) - (2.00 * 1 * 100)
        assert credit == 2300.0

    def test_negative_credit(self):
        """Debit when buy side costs more."""
        credit = calculate_credit(sell_price=1.00, sell_qty=1, buy_price=2.00, buy_qty=10)
        assert credit < 0

    def test_zero_credit(self):
        """Equal prices and quantities = zero credit."""
        credit = calculate_credit(sell_price=1.50, sell_qty=1, buy_price=1.50, buy_qty=1)
        assert credit == 0.0


class TestDetermineLegSetup:
    def test_full_strategy_buy_sym2_calls(self):
        """Buy SPX, Sell SPY calls direction."""
        pos = determine_leg_setup(
            call_direction="Buy SPX, Sell SPY",
            put_direction="Buy SPY, Sell SPX",
            sym1="SPY", sym2="SPX",
            qty_ratio=10,
            sym1_strike=605, sym2_strike=6050,
            sym1_call_price=2.50, sym2_call_price=25.00,
            sym1_put_price=2.00, sym2_put_price=20.00,
            show_calls=True, show_puts=True,
        )
        assert len(pos.legs) == 4  # 2 call legs + 2 put legs

        # Check call legs
        sell_call = [l for l in pos.legs if l.right == 'C' and l.action == 'SELL'][0]
        buy_call = [l for l in pos.legs if l.right == 'C' and l.action == 'BUY'][0]
        assert sell_call.symbol == 'SPY'
        assert sell_call.quantity == 10
        assert buy_call.symbol == 'SPX'
        assert buy_call.quantity == 1

        # Check put legs
        sell_put = [l for l in pos.legs if l.right == 'P' and l.action == 'SELL'][0]
        buy_put = [l for l in pos.legs if l.right == 'P' and l.action == 'BUY'][0]
        assert sell_put.symbol == 'SPX'
        assert buy_put.symbol == 'SPY'

    def test_calls_only(self):
        """Calls only strategy produces 2 legs."""
        pos = determine_leg_setup(
            call_direction="Sell SPX, Buy SPY",
            put_direction="Sell SPY, Buy SPX",
            sym1="SPY", sym2="SPX",
            qty_ratio=10,
            sym1_strike=605, sym2_strike=6050,
            sym1_call_price=2.50, sym2_call_price=25.00,
            sym1_put_price=0.0, sym2_put_price=0.0,
            show_calls=True, show_puts=False,
        )
        assert len(pos.legs) == 2
        assert pos.put_credit == 0.0
        assert all(l.right == 'C' for l in pos.legs)

    def test_puts_only(self):
        """Puts only strategy produces 2 legs."""
        pos = determine_leg_setup(
            call_direction="Sell SPX, Buy SPY",
            put_direction="Sell SPY, Buy SPX",
            sym1="SPY", sym2="SPX",
            qty_ratio=10,
            sym1_strike=605, sym2_strike=6050,
            sym1_call_price=0.0, sym2_call_price=0.0,
            sym1_put_price=2.00, sym2_put_price=20.00,
            show_calls=False, show_puts=True,
        )
        assert len(pos.legs) == 2
        assert pos.call_credit == 0.0
        assert all(l.right == 'P' for l in pos.legs)

    def test_total_credit_equals_sum(self):
        """Total credit = call credit + put credit."""
        pos = determine_leg_setup(
            call_direction="Buy SPX, Sell SPY",
            put_direction="Buy SPY, Sell SPX",
            sym1="SPY", sym2="SPX",
            qty_ratio=10,
            sym1_strike=605, sym2_strike=6050,
            sym1_call_price=2.50, sym2_call_price=25.00,
            sym1_put_price=2.00, sym2_put_price=20.00,
            show_calls=True, show_puts=True,
        )
        assert pos.total_credit == pytest.approx(pos.call_credit + pos.put_credit)

    def test_xsp_pair_1to1_ratio(self):
        """XSP pairs use 1:1 ratio."""
        pos = determine_leg_setup(
            call_direction="Buy XSP, Sell SPY",
            put_direction="Buy SPY, Sell XSP",
            sym1="SPY", sym2="XSP",
            qty_ratio=1,
            sym1_strike=605, sym2_strike=605,
            sym1_call_price=2.50, sym2_call_price=2.40,
            sym1_put_price=0.0, sym2_put_price=0.0,
            show_calls=True, show_puts=False,
        )
        sell_leg = [l for l in pos.legs if l.action == 'SELL'][0]
        buy_leg = [l for l in pos.legs if l.action == 'BUY'][0]
        assert sell_leg.quantity == 1
        assert buy_leg.quantity == 1


class TestMarginCalculation:
    def test_margin_with_credit_offset(self):
        """Margin is reduced by credit received."""
        legs = [
            Leg('SPY', 605, 'C', 'SELL', 10, 2.50),
            Leg('SPX', 6050, 'C', 'BUY', 1, 25.00),
        ]
        call_credit = (2.50 * 10 * 100) - (25.00 * 1 * 100)
        margin = calculate_margin_from_legs(legs, call_credit=call_credit)
        # 20% of (10 * 605 * 100) = 121,000, minus credit
        expected = max(0, 10 * 605 * 100 * 0.20 - call_credit)
        assert margin == pytest.approx(expected)

    def test_margin_never_negative(self):
        """Margin cannot go below zero."""
        legs = [
            Leg('SPY', 100, 'C', 'SELL', 1, 50.00),
        ]
        # Huge credit that exceeds short notional
        margin = calculate_margin_from_legs(legs, call_credit=999999.0)
        assert margin >= 0.0

    def test_long_legs_no_margin(self):
        """Long legs don't add to margin."""
        legs = [
            Leg('SPX', 6050, 'C', 'BUY', 1, 25.00),
        ]
        margin = calculate_margin_from_legs(legs)
        assert margin == 0.0
