"""Tests for src/scanner_engine.py - pair matching, scanning, ranking."""

import pytest
import pandas as pd
import numpy as np

from src.scanner_engine import (
    match_strike_pairs,
    filter_by_liquidity,
    rank_results,
)
from src.models import ScanResult


class TestMatchStrikePairs:
    def test_exact_ratio_match(self):
        """Exact matches should be found."""
        sym1_strikes = [600.0, 605.0, 610.0]
        sym2_strikes = [6000.0, 6050.0, 6100.0]
        open_ratio = 10.0

        pairs = match_strike_pairs(sym1_strikes, sym2_strikes, open_ratio)
        assert (600.0, 6000.0) in pairs
        assert (605.0, 6050.0) in pairs
        assert (610.0, 6100.0) in pairs

    def test_within_tolerance(self):
        """Pairs within 0.5% tolerance should match."""
        sym1_strikes = [600.0]
        sym2_strikes = [5985.0, 6000.0, 6015.0, 6100.0]
        open_ratio = 10.0

        pairs = match_strike_pairs(sym1_strikes, sym2_strikes, open_ratio, tolerance=0.005)
        # 6000 is exact, 5985 and 6015 are within 0.5% of 6000
        assert (600.0, 6000.0) in pairs
        # 6100 is 1.67% off, should NOT match
        assert (600.0, 6100.0) not in pairs

    def test_empty_strikes(self):
        pairs = match_strike_pairs([], [6000.0], 10.0)
        assert pairs == []

    def test_no_matches(self):
        """Far-apart strikes should produce no pairs."""
        pairs = match_strike_pairs([100.0], [9000.0], 10.0, tolerance=0.005)
        assert pairs == []


class TestFilterByLiquidity:
    def _make_trades_df(self, volumes):
        """Create a TRADES DataFrame with given volumes."""
        return pd.DataFrame({
            'symbol': ['SPY'] * len(volumes),
            'strike': [605.0] * len(volumes),
            'right': ['P'] * len(volumes),
            'time': pd.date_range('2026-01-02 14:30', periods=len(volumes), freq='1min', tz='UTC'),
            'open': [2.50] * len(volumes),
            'volume': volumes,
        })

    def test_filters_zero_volume_bars(self):
        df = self._make_trades_df([10, 0, 5, 0, 8])
        filtered, total_vol = filter_by_liquidity(df, 'SPY', 605.0, 'P', has_volume=True)
        assert len(filtered) == 3  # Only bars with volume > 0
        assert total_vol == 23

    def test_skips_illiquid_contracts(self):
        df = self._make_trades_df([2, 3])  # total = 5, below default min_volume=10
        filtered, total_vol = filter_by_liquidity(
            df, 'SPY', 605.0, 'P', has_volume=True, min_volume=10, hide_illiquid=True
        )
        assert filtered.empty
        assert total_vol == 5

    def test_keeps_illiquid_when_not_hiding(self):
        df = self._make_trades_df([2, 3])
        filtered, total_vol = filter_by_liquidity(
            df, 'SPY', 605.0, 'P', has_volume=True, min_volume=10, hide_illiquid=False
        )
        # Still filters zero-vol bars, but total = 5 doesn't block it
        assert not filtered.empty

    def test_empty_contract(self):
        df = self._make_trades_df([10])
        filtered, total_vol = filter_by_liquidity(df, 'SPX', 605.0, 'P', has_volume=True)
        assert filtered.empty
        assert total_vol == 0

    def test_bidask_mode(self):
        """BID_ASK mode filters by valid quotes."""
        df = pd.DataFrame({
            'symbol': ['SPY', 'SPY', 'SPY'],
            'strike': [605.0, 605.0, 605.0],
            'right': ['P', 'P', 'P'],
            'time': pd.date_range('2026-01-02 14:30', periods=3, freq='1min', tz='UTC'),
            'bid': [2.40, 0.0, 2.45],
            'ask': [2.60, 0.0, 2.65],
            'midpoint': [2.50, 0.0, 2.55],
        })
        filtered, total_vol = filter_by_liquidity(df, 'SPY', 605.0, 'P', has_volume=False)
        assert len(filtered) == 2  # Only rows with bid > 0 and ask > 0
        assert total_vol == 2


class TestRankResults:
    @pytest.fixture
    def sample_results(self):
        return [
            ScanResult(sym1_strike=605, sym2_strike=6050, moneyness='+0.10%',
                       max_gap=0.15, max_gap_time='10:30', credit=500,
                       worst_case_pnl=-200, best_wc_time='11:00',
                       direction='Sell SPX', risk_reward=2.5, max_risk=-200),
            ScanResult(sym1_strike=606, sym2_strike=6060, moneyness='+0.20%',
                       max_gap=0.20, max_gap_time='10:45', credit=800,
                       worst_case_pnl=100, best_wc_time='11:15',
                       direction='Sell SPX', risk_reward=float('inf'), max_risk=0),
            ScanResult(sym1_strike=604, sym2_strike=6040, moneyness='+0.05%',
                       max_gap=0.10, max_gap_time='10:15', credit=300,
                       worst_case_pnl=-50, best_wc_time='10:45',
                       direction='Sell SPY', risk_reward=6.0, max_risk=-50),
        ]

    def test_rank_by_safety(self, sample_results):
        ranked = rank_results(sample_results, 'safety')
        # Highest worst-case P&L first
        assert ranked[0].worst_case_pnl == 100  # guaranteed profit
        assert ranked[1].worst_case_pnl == -50
        assert ranked[2].worst_case_pnl == -200

    def test_rank_by_profit(self, sample_results):
        ranked = rank_results(sample_results, 'profit')
        assert ranked[0].credit == 800
        assert ranked[1].credit == 500
        assert ranked[2].credit == 300

    def test_rank_by_risk_reward(self, sample_results):
        ranked = rank_results(sample_results, 'risk_reward')
        assert ranked[0].risk_reward == float('inf')
        assert ranked[1].risk_reward == 6.0
        assert ranked[2].risk_reward == 2.5
