"""Tests for src/data_loader.py - CSV loading and date listing."""

import os
import pytest
import pandas as pd

from src.data_loader import (
    list_available_dates,
    load_underlying_prices,
    load_options_data,
    load_bidask_data,
    get_symbol_dataframes,
    get_available_pairs,
)


class TestListAvailableDates:
    def test_finds_dates_from_real_data(self):
        """Should find dates from the data/ directory."""
        dates = list_available_dates('data')
        if not dates:
            pytest.skip("No data files in data/")
        assert len(dates) > 0
        # Check format: (raw, formatted)
        raw, formatted = dates[0]
        assert len(raw) == 8  # YYYYMMDD
        assert '-' in formatted  # YYYY-MM-DD

    def test_returns_empty_for_missing_dir(self):
        dates = list_available_dates('/nonexistent/path')
        assert dates == []

    def test_chronological_order(self):
        dates = list_available_dates('data')
        if len(dates) < 2:
            pytest.skip("Need at least 2 dates")
        raw_dates = [d[0] for d in dates]
        assert raw_dates == sorted(raw_dates)


class TestLoadData:
    @pytest.fixture
    def any_date(self):
        dates = list_available_dates('data')
        if not dates:
            pytest.skip("No data files in data/")
        return dates[-1][0]  # Most recent date

    def test_load_underlying(self, any_date):
        df = load_underlying_prices(any_date)
        assert not df.empty
        assert 'symbol' in df.columns
        assert 'time' in df.columns
        assert 'close' in df.columns
        assert df['time'].dtype.name.startswith('datetime')

    def test_load_underlying_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_underlying_prices('99991231')

    def test_load_options(self, any_date):
        df = load_options_data(any_date)
        if df is None:
            pytest.skip("No options data for this date")
        assert 'strike' in df.columns
        assert 'right' in df.columns

    def test_load_options_missing_returns_none(self):
        assert load_options_data('99991231') is None

    def test_load_bidask(self, any_date):
        df = load_bidask_data(any_date)
        if df is None:
            pytest.skip("No bidask data for this date")
        assert 'bid' in df.columns
        assert 'ask' in df.columns
        assert 'midpoint' in df.columns


class TestGetSymbolDataframes:
    def test_splits_by_symbol(self):
        dates = list_available_dates('data')
        if not dates:
            pytest.skip("No data files")
        df = load_underlying_prices(dates[-1][0])
        symbols = df['symbol'].unique()
        if 'SPY' not in symbols or 'SPX' not in symbols:
            pytest.skip("Need SPY and SPX data")

        spy_df, spx_df = get_symbol_dataframes(df, 'SPY', 'SPX')
        assert all(spy_df['symbol'] == 'SPY')
        assert all(spx_df['symbol'] == 'SPX')
        assert 'time_et' in spy_df.columns
        assert 'time_label' in spy_df.columns
        assert 'time_short' in spy_df.columns


class TestGetAvailablePairs:
    def test_filters_to_available_symbols(self):
        df = pd.DataFrame({'symbol': ['SPY', 'SPX']})
        pairs = get_available_pairs(df)
        # Should include pairs with SPY and SPX
        assert 'SPY / SPX' in pairs
        # Should not include XSP pairs (not in data)
        assert 'XSP / SPX' not in pairs

    def test_all_symbols_available(self):
        df = pd.DataFrame({'symbol': ['SPY', 'SPX', 'XSP']})
        pairs = get_available_pairs(df)
        assert len(pairs) == 3

    def test_no_symbols_available(self):
        df = pd.DataFrame({'symbol': ['AAPL']})
        pairs = get_available_pairs(df)
        assert len(pairs) == 0
