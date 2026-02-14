"""Tests for src/pricing.py — price discovery and liquidity detection.

Covers:
- get_option_price_from_db: basic lookup, nearest time, fallback
- _find_nearest_row: liquid preference, exact match, future/past fallback
- get_option_price_with_liquidity: midpoint preference, stale detection,
  wide spread warnings, trade-only fallback, missing data
"""

import pandas as pd
import pytest
from datetime import datetime, timezone

from src.pricing import (
    get_option_price_from_db,
    _find_nearest_row,
    get_option_price_with_liquidity,
)
from src.config import WIDE_SPREAD_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(hour, minute=0):
    """Create a UTC timestamp for testing."""
    return pd.Timestamp(datetime(2026, 2, 7, hour, minute, tzinfo=timezone.utc))


def _make_trades_df(rows):
    """Build a TRADES-style DataFrame.

    Each row: (time, symbol, strike, right, open, volume)
    """
    data = []
    for t, sym, strike, right, open_px, vol in rows:
        data.append({
            'time': t, 'symbol': sym, 'strike': strike,
            'right': right, 'open': open_px, 'close': open_px,
            'volume': vol,
        })
    return pd.DataFrame(data)


def _make_bidask_df(rows):
    """Build a BID_ASK-style DataFrame.

    Each row: (time, symbol, strike, right, bid, ask, midpoint)
    """
    data = []
    for t, sym, strike, right, bid, ask, mid in rows:
        data.append({
            'time': t, 'symbol': sym, 'strike': strike,
            'right': right, 'bid': bid, 'ask': ask, 'midpoint': mid,
        })
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Tests: get_option_price_from_db
# ---------------------------------------------------------------------------

class TestGetOptionPriceFromDb:
    """Tests for the simpler price lookup (used by scanner/overlay)."""

    def test_exact_time_match(self):
        t1 = _ts(10, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        price = get_option_price_from_db(df, 'SPY', 600, 'P', t1)
        assert price == 3.50

    def test_nearest_future_time(self):
        t1 = _ts(10, 0)
        t2 = _ts(10, 5)
        df = _make_trades_df([
            (t2, 'SPY', 600, 'P', 3.50, 100),
        ])
        price = get_option_price_from_db(df, 'SPY', 600, 'P', t1)
        assert price == 3.50

    def test_fallback_to_last_when_no_future(self):
        t1 = _ts(10, 0)
        t2 = _ts(11, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        # Request time after all data
        price = get_option_price_from_db(df, 'SPY', 600, 'P', t2)
        assert price == 3.50

    def test_returns_none_for_missing_contract(self):
        t1 = _ts(10, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        price = get_option_price_from_db(df, 'SPX', 6000, 'P', t1)
        assert price is None

    def test_uses_midpoint_for_bidask_data(self):
        t1 = _ts(10, 0)
        df = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 3.40, 3.60, 3.50),
        ])
        price = get_option_price_from_db(df, 'SPY', 600, 'P', t1)
        assert price == 3.50

    def test_multiple_contracts_returns_correct_one(self):
        t1 = _ts(10, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'C', 5.00, 50),
            (t1, 'SPY', 600, 'P', 3.50, 100),
            (t1, 'SPY', 601, 'P', 4.00, 80),
        ])
        assert get_option_price_from_db(df, 'SPY', 600, 'P', t1) == 3.50
        assert get_option_price_from_db(df, 'SPY', 600, 'C', t1) == 5.00
        assert get_option_price_from_db(df, 'SPY', 601, 'P', t1) == 4.00


# ---------------------------------------------------------------------------
# Tests: _find_nearest_row
# ---------------------------------------------------------------------------

class TestFindNearestRow:
    """Tests for the internal row finder with liquid preference."""

    def test_exact_match_no_preference(self):
        t1 = _ts(10, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 0),
        ])
        row, liquid = _find_nearest_row(df, t1)
        assert row['open'] == 3.50
        assert liquid is False

    def test_prefers_liquid_bars(self):
        t1 = _ts(10, 0)
        t2 = _ts(10, 5)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 0),   # stale
            (t2, 'SPY', 600, 'P', 3.60, 100),  # liquid
        ])
        row, liquid = _find_nearest_row(df, t1, prefer_liquid=True)
        assert row['open'] == 3.60
        assert liquid is True

    def test_liquid_preference_exact_match(self):
        t1 = _ts(10, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        row, liquid = _find_nearest_row(df, t1, prefer_liquid=True)
        assert row['open'] == 3.50
        assert liquid is True

    def test_falls_back_to_latest_liquid_if_all_before(self):
        t1 = _ts(10, 0)
        t2 = _ts(11, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        # All liquid bars are before request time
        row, liquid = _find_nearest_row(df, t2, prefer_liquid=True)
        assert row['open'] == 3.50
        assert liquid is True

    def test_no_liquid_bars_falls_back(self):
        t1 = _ts(10, 0)
        df = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 0),
        ])
        row, liquid = _find_nearest_row(df, t1, prefer_liquid=True)
        assert row['open'] == 3.50
        assert liquid is False


# ---------------------------------------------------------------------------
# Tests: get_option_price_with_liquidity
# ---------------------------------------------------------------------------

class TestGetOptionPriceWithLiquidity:
    """Tests for the full liquidity-aware price resolver."""

    def test_prefers_bidask_midpoint(self):
        """When both TRADES and BID_ASK exist, should use midpoint."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 3.40, 3.60, 3.50),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['price'] == 3.50
        assert result['price_source'] == 'midpoint'
        assert result['bid'] == 3.40
        assert result['ask'] == 3.60

    def test_falls_back_to_trade_when_no_bidask(self):
        """Without BID_ASK data, use TRADES open price."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        result = get_option_price_with_liquidity(
            df_trades, None, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['price'] == 3.50
        assert result['price_source'] == 'trade'

    def test_returns_none_for_missing_contract(self):
        """No data at all for this contract."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        result = get_option_price_with_liquidity(
            df_trades, None, 'SPX', 6000, 'P', t1
        )
        assert result is None

    def test_stale_detection_no_volume_no_quotes(self):
        """volume=0 AND no valid bid/ask → stale."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 0),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 0.0, 0.0, 0.0),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['is_stale'] is True
        assert 'STALE' in result['liquidity_warning']

    def test_no_volume_but_valid_quotes_not_stale(self):
        """volume=0 but valid bid/ask quotes → usable, just a warning."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 0),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 3.40, 3.60, 3.50),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['is_stale'] is False
        assert result['liquidity_warning'] is not None
        assert 'vol=0' in result['liquidity_warning']

    def test_wide_spread_warning(self):
        """Bid-ask spread >20% of midpoint triggers warning."""
        t1 = _ts(10, 0)
        # Spread = 2.00, midpoint = 2.00 → 100% spread
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 2.00, 100),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 1.00, 3.00, 2.00),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['spread_pct'] == 100.0
        assert result['liquidity_warning'] is not None
        assert 'Wide spread' in result['liquidity_warning']

    def test_narrow_spread_no_warning(self):
        """Normal spread should not trigger a warning."""
        t1 = _ts(10, 0)
        # Spread = 0.10, midpoint = 3.50 → ~2.9%
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 3.45, 3.55, 3.50),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['liquidity_warning'] is None

    def test_trade_only_stale(self):
        """TRADES-only with volume=0 → stale."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 0),
        ])
        result = get_option_price_with_liquidity(
            df_trades, None, 'SPY', 600, 'P', t1
        )
        assert result is not None
        assert result['is_stale'] is True
        assert result['price'] == 3.50
        assert result['price_source'] == 'trade'

    def test_both_none_returns_none(self):
        """Both df_options and df_bidask are None → None."""
        result = get_option_price_with_liquidity(
            None, None, 'SPY', 600, 'P', _ts(10, 0)
        )
        assert result is None

    def test_volume_reported_from_trades(self):
        """Volume field comes from TRADES data."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 42),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 3.40, 3.60, 3.50),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result['volume'] == 42

    def test_spread_calculation(self):
        """Spread and spread_pct are calculated correctly."""
        t1 = _ts(10, 0)
        df_trades = _make_trades_df([
            (t1, 'SPY', 600, 'P', 3.50, 100),
        ])
        df_bidask = _make_bidask_df([
            (t1, 'SPY', 600, 'P', 3.00, 4.00, 3.50),
        ])
        result = get_option_price_with_liquidity(
            df_trades, df_bidask, 'SPY', 600, 'P', t1
        )
        assert result['spread'] == pytest.approx(1.00)
        assert result['spread_pct'] == pytest.approx(1.00 / 3.50 * 100)
