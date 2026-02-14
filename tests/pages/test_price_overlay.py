"""Tests for src/pages/price_overlay.py — price overlay callbacks."""

import pytest
from dash import html, no_update


class TestUpdateOverlay:
    def test_empty_config(self):
        from src.pages.price_overlay import update_overlay
        result = update_overlay({}, 'P', 'price_overlay')
        assert isinstance(result, html.P)

    def test_tab_guard(self):
        """Returns no_update when tab is not 'price_overlay'."""
        from src.pages.price_overlay import update_overlay
        result = update_overlay({'date': '20260207'}, 'P', 'historical')
        assert result is no_update

    def test_bad_date_caught(self):
        from src.pages.price_overlay import update_overlay
        bad_config = {
            'date': '99999999',
            'sym1': 'SPY', 'sym2': 'SPX',
            'sym1_strike': 600, 'sym2_strike': 6000,
            'qty_ratio': 10,
        }
        result = update_overlay(bad_config, 'P', 'price_overlay')
        assert isinstance(result, (html.P, html.Div))
