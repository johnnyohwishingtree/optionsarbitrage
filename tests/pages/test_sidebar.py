"""Tests for src/pages/sidebar.py — sidebar config callbacks."""

import pytest
from dash import html


class TestUpdateControls:
    def test_returns_12_values_empty_inputs(self):
        """update_controls must return exactly 12 values for empty inputs."""
        from src.pages.sidebar import update_controls
        result = update_controls(None, None)
        assert len(result) == 12

    def test_returns_12_values_with_date(self):
        """update_controls returns 12 values when given a valid date."""
        from src.data_loader import list_available_dates
        dates = list_available_dates()
        if not dates:
            pytest.skip("No data files")
        from src.pages.sidebar import update_controls
        result = update_controls(dates[-1][0], None)
        assert len(result) == 12


class TestUpdateConfigStore:
    def test_returns_3_values_empty(self):
        """update_config_store must return 3 values for empty inputs."""
        from src.pages.sidebar import update_config_store
        result = update_config_store(None, None, None, None, None, None, None)
        assert len(result) == 3

    def test_returns_3_values_with_none_config(self):
        from src.pages.sidebar import update_config_store
        result = update_config_store(0, 'SPY / SPX', 600, 6000, 'Sell SPX, Buy SPY', 'Sell SPY, Buy SPX', None)
        assert len(result) == 3


class TestUpdateMoneyness:
    def test_empty_config(self):
        from src.pages.sidebar import update_moneyness
        assert update_moneyness({}) == ""

    def test_valid_config(self):
        from src.pages.sidebar import update_moneyness
        result = update_moneyness({
            'sym1_strike': 600,
            'sym2_strike': 6000,
            'entry_sym1_price': 600.0,
            'entry_sym2_price': 6000.0,
        })
        assert isinstance(result, html.Div)

    def test_zero_price_no_crash(self):
        """Zero entry price should not raise ZeroDivisionError."""
        from src.pages.sidebar import update_moneyness
        result = update_moneyness({
            'sym1_strike': 600,
            'sym2_strike': 6000,
            'entry_sym1_price': 0.0,
            'entry_sym2_price': 6000.0,
        })
        assert result == ""

    def test_missing_price_keys(self):
        from src.pages.sidebar import update_moneyness
        result = update_moneyness({'sym1_strike': 600, 'sym2_strike': 6000})
        assert result == ""
