"""Tests for src/pages/divergence.py — divergence callbacks."""

import pytest
from dash import html, no_update


class TestUpdateDivergence:
    def test_empty_config(self):
        from src.pages.divergence import update_divergence
        result = update_divergence({}, 'divergence')
        assert isinstance(result, html.P)

    def test_tab_guard(self):
        """Returns no_update when tab is not 'divergence'."""
        from src.pages.divergence import update_divergence
        result = update_divergence({'date': '20260207'}, 'historical')
        assert result is no_update
