"""Tests for src/pages/historical.py — historical analysis callbacks."""

import pytest
from dash import html, no_update


class TestUpdateHistoricalAnalysis:
    def test_empty_config(self):
        from src.pages.historical import update_historical_analysis
        result = update_historical_analysis({}, 'full', 'historical')
        assert isinstance(result, html.Div)

    def test_none_config(self):
        from src.pages.historical import update_historical_analysis
        result = update_historical_analysis(None, 'full', 'historical')
        assert isinstance(result, html.Div)

    def test_tab_guard_returns_no_update(self):
        """Should return no_update when tab is not 'historical'."""
        from src.pages.historical import update_historical_analysis
        result = update_historical_analysis({'date': '20260207'}, 'full', 'scanner')
        assert result is no_update

    def test_bad_date_caught_gracefully(self):
        """Nonexistent date triggers error caught by exception handler."""
        from src.pages.historical import update_historical_analysis
        bad_config = {
            'date': '99999999',
            'sym1': 'SPY', 'sym2': 'SPX',
            'qty_ratio': 10, 'entry_time_idx': 0,
            'sym1_strike': 600, 'sym2_strike': 6000,
            'call_direction': 'Sell SPX, Buy SPY',
            'put_direction': 'Sell SPY, Buy SPX',
            'entry_sym1_price': 600.0, 'entry_sym2_price': 6000.0,
            'entry_time_label': '10:00',
        }
        result = update_historical_analysis(bad_config, 'full', 'historical')
        assert isinstance(result, html.Div)
