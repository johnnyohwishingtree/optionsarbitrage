"""Tests for src/config.py — business constants and helper functions."""

import pytest
from src.config import (
    QTY_RATIO_SPX, QTY_RATIO_DEFAULT,
    STRIKE_STEP_SPX, STRIKE_STEP_DEFAULT,
    MONEYNESS_WARN_THRESHOLD, SCANNER_PAIR_TOLERANCE,
    WIDE_SPREAD_THRESHOLD, DEFAULT_MIN_VOLUME,
    GRID_PRICE_POINTS, GRID_PRICE_RANGE_PCT, GRID_BASIS_DRIFT_PCT,
    MARGIN_RATE, TRADING_DAY_MINUTES,
    IB_HOST, IB_PORT, SYMBOL_PAIRS,
    get_qty_ratio, get_strike_step,
)


class TestConstants:
    """Verify business constants have expected values."""

    def test_qty_ratios(self):
        assert QTY_RATIO_SPX == 10
        assert QTY_RATIO_DEFAULT == 1

    def test_strike_steps(self):
        assert STRIKE_STEP_SPX == 5
        assert STRIKE_STEP_DEFAULT == 1

    def test_thresholds_are_positive(self):
        assert MONEYNESS_WARN_THRESHOLD > 0
        assert SCANNER_PAIR_TOLERANCE > 0
        assert WIDE_SPREAD_THRESHOLD > 0
        assert DEFAULT_MIN_VOLUME >= 0

    def test_grid_search_params(self):
        assert GRID_PRICE_POINTS == 50
        assert 0 < GRID_PRICE_RANGE_PCT < 1
        assert 0 < GRID_BASIS_DRIFT_PCT < 1

    def test_margin_rate(self):
        assert MARGIN_RATE == 0.20

    def test_trading_day(self):
        assert TRADING_DAY_MINUTES == 390  # 9:30 AM - 4:00 PM = 6.5 hours

    def test_ib_connection(self):
        assert IB_HOST == '127.0.0.1'
        assert isinstance(IB_PORT, int)

    def test_symbol_pairs_structure(self):
        assert len(SYMBOL_PAIRS) == 3
        for name, (sym1, sym2) in SYMBOL_PAIRS.items():
            assert isinstance(sym1, str)
            assert isinstance(sym2, str)
            assert '/' in name


class TestGetQtyRatio:
    def test_spx_returns_10(self):
        assert get_qty_ratio('SPX') == 10

    def test_xsp_returns_1(self):
        assert get_qty_ratio('XSP') == 1

    def test_spy_returns_1(self):
        assert get_qty_ratio('SPY') == 1

    def test_unknown_returns_default(self):
        assert get_qty_ratio('AAPL') == 1


class TestGetStrikeStep:
    def test_spx_returns_5(self):
        assert get_strike_step('SPX') == 5

    def test_xsp_returns_1(self):
        assert get_strike_step('XSP') == 1

    def test_spy_returns_1(self):
        assert get_strike_step('SPY') == 1

    def test_unknown_returns_default(self):
        assert get_strike_step('AAPL') == 1
