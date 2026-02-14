"""Tests for src/normalization.py — price normalization, spread, divergence.

Covers:
- normalize_option_prices: ratio scaling, merge on time
- calculate_spread: sign convention, percentage
- calculate_worst_case_quick: formula correctness, edge cases
- calculate_underlying_divergence: pct change, gap sign, dollar gap
"""

import pandas as pd
import pytest
from datetime import datetime, timezone

from src.normalization import (
    normalize_option_prices,
    calculate_spread,
    calculate_worst_case_quick,
    calculate_underlying_divergence,
)
from src.config import GRID_BASIS_DRIFT_PCT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(hour, minute=0):
    return pd.Timestamp(datetime(2026, 2, 7, hour, minute, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# Tests: normalize_option_prices
# ---------------------------------------------------------------------------

class TestNormalizeOptionPrices:
    """Tests for normalizing SYM2 prices by open ratio."""

    def test_normalization_scales_by_ratio(self):
        """SYM2 price should be divided by open_ratio."""
        t1 = _ts(10, 0)
        sym1 = pd.DataFrame({'time': [t1], 'close': [3.00]})
        sym2 = pd.DataFrame({'time': [t1], 'close': [30.00]})
        open_ratio = 10.0

        result = normalize_option_prices(sym1, sym2, open_ratio, 'close')
        assert len(result) == 1
        assert result.iloc[0]['spy_price'] == 3.00
        assert result.iloc[0]['spx_normalized'] == pytest.approx(3.00)

    def test_inner_join_on_time(self):
        """Only overlapping times should appear in result."""
        t1 = _ts(10, 0)
        t2 = _ts(10, 5)
        t3 = _ts(10, 10)
        sym1 = pd.DataFrame({'time': [t1, t2], 'close': [3.00, 3.10]})
        sym2 = pd.DataFrame({'time': [t2, t3], 'close': [31.00, 32.00]})
        open_ratio = 10.0

        result = normalize_option_prices(sym1, sym2, open_ratio, 'close')
        assert len(result) == 1  # only t2 overlaps
        assert result.iloc[0]['spy_price'] == 3.10

    def test_empty_input_returns_empty(self):
        """Empty DataFrames should produce empty result."""
        sym1 = pd.DataFrame({'time': [], 'close': []})
        sym2 = pd.DataFrame({'time': [], 'close': []})
        result = normalize_option_prices(sym1, sym2, 10.0, 'close')
        assert len(result) == 0

    def test_no_overlap_returns_empty(self):
        """No common times → empty result."""
        t1 = _ts(10, 0)
        t2 = _ts(11, 0)
        sym1 = pd.DataFrame({'time': [t1], 'close': [3.00]})
        sym2 = pd.DataFrame({'time': [t2], 'close': [30.00]})
        result = normalize_option_prices(sym1, sym2, 10.0, 'close')
        assert len(result) == 0

    def test_works_with_midpoint_column(self):
        """Should work with 'midpoint' as price_col."""
        t1 = _ts(10, 0)
        sym1 = pd.DataFrame({'time': [t1], 'midpoint': [3.00]})
        sym2 = pd.DataFrame({'time': [t1], 'midpoint': [30.00]})
        result = normalize_option_prices(sym1, sym2, 10.0, 'midpoint')
        assert len(result) == 1
        assert result.iloc[0]['spy_price'] == 3.00


# ---------------------------------------------------------------------------
# Tests: calculate_spread
# ---------------------------------------------------------------------------

class TestCalculateSpread:
    """Tests for spread calculation."""

    def test_positive_spread_means_sym2_expensive(self):
        """Positive spread = SYM2 normalized price > SYM1 price."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
        })
        result = calculate_spread(merged)
        assert result.iloc[0]['spread'] == pytest.approx(0.50)
        assert result.iloc[0]['spread_pct'] > 0

    def test_negative_spread_means_sym1_expensive(self):
        """Negative spread = SYM1 price > SYM2 normalized price."""
        merged = pd.DataFrame({
            'spy_price': [3.50],
            'spx_normalized': [3.00],
        })
        result = calculate_spread(merged)
        assert result.iloc[0]['spread'] == pytest.approx(-0.50)
        assert result.iloc[0]['spread_pct'] < 0

    def test_zero_spread(self):
        """Equal prices → zero spread."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.00],
        })
        result = calculate_spread(merged)
        assert result.iloc[0]['spread'] == pytest.approx(0.0)

    def test_spread_pct_formula(self):
        """spread_pct = spread / spy_price * 100."""
        merged = pd.DataFrame({
            'spy_price': [4.00],
            'spx_normalized': [4.20],
        })
        result = calculate_spread(merged)
        assert result.iloc[0]['spread_pct'] == pytest.approx(0.20 / 4.00 * 100)

    def test_does_not_modify_input(self):
        """Should return a copy, not modify the input."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
        })
        result = calculate_spread(merged)
        assert 'spread' not in merged.columns


# ---------------------------------------------------------------------------
# Tests: calculate_worst_case_quick
# ---------------------------------------------------------------------------

class TestCalculateWorstCaseQuick:
    """Tests for the quick worst-case estimator."""

    def test_adds_worst_case_column(self):
        """Should add 'worst_case_pnl' column to merged DataFrame."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
            'spread': [0.50],
        })
        result = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=0.0, sym2_moneyness_pct=0.0,
        )
        assert 'worst_case_pnl' in result.columns

    def test_credit_component(self):
        """Credit = |spread| * qty_ratio * 100."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
            'spread': [0.50],
        })
        result = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=0.0, sym2_moneyness_pct=0.0,
            basis_drift_pct=0.0,  # eliminate drift
        )
        # credit = 0.50 * 10 * 100 = 500
        assert result.iloc[0]['worst_case_pnl'] == pytest.approx(500.0)

    def test_basis_drift_reduces_pnl(self):
        """Basis drift should reduce worst-case P&L."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
            'spread': [0.50],
        })
        no_drift = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=0.0, sym2_moneyness_pct=0.0,
            basis_drift_pct=0.0,
        )
        with_drift = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=0.0, sym2_moneyness_pct=0.0,
            basis_drift_pct=0.001,
        )
        assert with_drift.iloc[0]['worst_case_pnl'] < no_drift.iloc[0]['worst_case_pnl']

    def test_moneyness_mismatch_reduces_pnl(self):
        """Moneyness mismatch between strikes should reduce worst-case P&L."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
            'spread': [0.50],
        })
        matched = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=1.0, sym2_moneyness_pct=1.0,
            basis_drift_pct=0.0,
        )
        mismatched = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=1.0, sym2_moneyness_pct=1.5,
            basis_drift_pct=0.0,
        )
        assert mismatched.iloc[0]['worst_case_pnl'] < matched.iloc[0]['worst_case_pnl']

    def test_does_not_modify_input(self):
        """Should return a copy."""
        merged = pd.DataFrame({
            'spy_price': [3.00],
            'spx_normalized': [3.50],
            'spread': [0.50],
        })
        result = calculate_worst_case_quick(
            merged, open_ratio=10.0, sym1_strike=600, qty_ratio=10,
            sym1_moneyness_pct=0.0, sym2_moneyness_pct=0.0,
        )
        assert 'worst_case_pnl' not in merged.columns


# ---------------------------------------------------------------------------
# Tests: calculate_underlying_divergence
# ---------------------------------------------------------------------------

class TestCalculateUnderlyingDivergence:
    """Tests for underlying price divergence calculation."""

    def test_basic_divergence(self):
        """When both move up equally, gap should be ~0."""
        t1 = _ts(10, 0)
        t2 = _ts(10, 5)
        sym1 = pd.DataFrame({
            'time': [t1, t2],
            'time_label': ['10:00', '10:05'],
            'close': [600.0, 603.0],  # +0.5%
        })
        sym2 = pd.DataFrame({
            'time': [t1, t2],
            'close': [6000.0, 6030.0],  # +0.5%
        })
        result = calculate_underlying_divergence(sym1, sym2, qty_ratio=10)

        assert len(result) == 2
        # At open (t1), both are at 0% change → gap = 0
        assert result.iloc[0]['pct_gap'] == pytest.approx(0.0)
        # At t2, both moved +0.5% → gap still ~0
        assert result.iloc[1]['pct_gap'] == pytest.approx(0.0)

    def test_sym2_leads_positive_gap(self):
        """When SYM2 moves up more than SYM1, gap is positive."""
        t1 = _ts(10, 0)
        t2 = _ts(10, 5)
        sym1 = pd.DataFrame({
            'time': [t1, t2],
            'time_label': ['10:00', '10:05'],
            'close': [600.0, 600.0],  # flat
        })
        sym2 = pd.DataFrame({
            'time': [t1, t2],
            'close': [6000.0, 6060.0],  # +1%
        })
        result = calculate_underlying_divergence(sym1, sym2, qty_ratio=10)
        assert result.iloc[1]['pct_gap'] == pytest.approx(1.0)

    def test_dollar_gap_uses_qty_ratio(self):
        """dollar_gap = close_sym2 / qty_ratio - close_sym1."""
        t1 = _ts(10, 0)
        sym1 = pd.DataFrame({
            'time': [t1],
            'time_label': ['10:00'],
            'close': [600.0],
        })
        sym2 = pd.DataFrame({
            'time': [t1],
            'close': [6010.0],
        })
        result = calculate_underlying_divergence(sym1, sym2, qty_ratio=10)
        # dollar_gap = 6010/10 - 600 = 601 - 600 = 1.0
        assert result.iloc[0]['dollar_gap'] == pytest.approx(1.0)

    def test_empty_on_no_overlap(self):
        """No overlapping times → empty result."""
        t1 = _ts(10, 0)
        t2 = _ts(11, 0)
        sym1 = pd.DataFrame({
            'time': [t1], 'time_label': ['10:00'], 'close': [600.0],
        })
        sym2 = pd.DataFrame({
            'time': [t2], 'close': [6000.0],
        })
        result = calculate_underlying_divergence(sym1, sym2, qty_ratio=10)
        assert len(result) == 0

    def test_output_columns(self):
        """Result should have all expected columns."""
        t1 = _ts(10, 0)
        sym1 = pd.DataFrame({
            'time': [t1], 'time_label': ['10:00'], 'close': [600.0],
        })
        sym2 = pd.DataFrame({
            'time': [t1], 'close': [6000.0],
        })
        result = calculate_underlying_divergence(sym1, sym2, qty_ratio=10)
        expected_cols = {
            'time', 'time_label', 'close_sym1', 'close_sym2',
            'pct_change_sym1', 'pct_change_sym2', 'pct_gap', 'dollar_gap',
        }
        assert expected_cols.issubset(set(result.columns))
