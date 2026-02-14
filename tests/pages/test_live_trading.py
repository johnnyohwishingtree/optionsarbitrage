"""Tests for src/pages/live_trading.py — live trading callbacks."""

import pytest


class TestToggleAutoRefresh:
    def test_empty_list_disables(self):
        from src.pages.live_trading import toggle_auto_refresh
        assert toggle_auto_refresh([]) is True  # disabled = True

    def test_on_enables(self):
        from src.pages.live_trading import toggle_auto_refresh
        assert toggle_auto_refresh(['on']) is False  # disabled = False

    def test_none_disables(self):
        from src.pages.live_trading import toggle_auto_refresh
        assert toggle_auto_refresh(None) is True


class TestUpdateLiveTrading:
    def test_initial_load_no_crash(self):
        """n_clicks=0 should return prompt, not attempt IB connection."""
        from src.pages.live_trading import update_live_trading
        content, timestamp = update_live_trading(0, None, {})
        assert 'Click Refresh' in content.children
        assert timestamp == ""

    def test_none_clicks_no_crash(self):
        from src.pages.live_trading import update_live_trading
        content, timestamp = update_live_trading(None, None, None)
        assert 'Click Refresh' in content.children

    def test_returns_2_tuple(self):
        """Must always return (content, timestamp) — 2 outputs."""
        from src.pages.live_trading import update_live_trading
        result = update_live_trading(0, None, {})
        assert isinstance(result, tuple)
        assert len(result) == 2
