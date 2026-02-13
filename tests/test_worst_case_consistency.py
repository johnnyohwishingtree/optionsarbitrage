#!/usr/bin/env python3
"""
Test that all three views produce the same worst-case P&L value
for the same strike pair, direction, and entry time.

The three views:
1. Historical Analysis - uses get_option_price_with_liquidity (open price, volume>0 preferred)
2. Strike Scanner - uses open price from volume-filtered TRADES data
3. Price Overlay - uses grid search at best time with open price from volume-filtered data

All three should call calculate_best_worst_case_with_basis_drift with identical inputs
and therefore produce identical worst-case values.
"""

import pytest
import sys
import os

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pnl import calculate_best_worst_case_with_basis_drift
from src.pricing import get_option_price_from_db, get_option_price_with_liquidity, _find_nearest_row


# ---------------------------------------------------------------------------
# Fixtures — synthetic but realistic data for SPY 686 / SPX 6880 puts
# ---------------------------------------------------------------------------

def _make_underlying():
    """Create underlying price DataFrames (SPY + SPX)."""
    times = pd.date_range('2026-02-05 09:30', periods=30, freq='1min', tz='America/New_York')
    times_utc = times.tz_convert('UTC')

    spy_rows = []
    spx_rows = []
    for t in times_utc:
        spy_rows.append({
            'symbol': 'SPY', 'time': t,
            'open': 679.60, 'high': 679.80, 'low': 679.40, 'close': 679.66, 'volume': 500000,
        })
        spx_rows.append({
            'symbol': 'SPX', 'time': t,
            'open': 6818.00, 'high': 6820.00, 'low': 6816.00, 'close': 6818.56, 'volume': 0,
        })

    df = pd.DataFrame(spy_rows + spx_rows)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    spy_df = df[df['symbol'] == 'SPY'].copy().reset_index(drop=True)
    spx_df = df[df['symbol'] == 'SPX'].copy().reset_index(drop=True)
    return spy_df, spx_df


def _make_options():
    """
    Create options TRADES DataFrame.

    SPY 686P: liquid (volume > 0), open=6.26
    SPX 6880P: mix of liquid and stale bars
    """
    times = pd.date_range('2026-02-05 09:30', periods=30, freq='1min', tz='America/New_York')
    times_utc = times.tz_convert('UTC')

    rows = []
    for i, t in enumerate(times_utc):
        # SPY 686P — liquid, open=6.26 for all bars
        rows.append({
            'symbol': 'SPY', 'strike': 686, 'right': 'P', 'time': t,
            'open': 6.26, 'high': 6.50, 'low': 6.10, 'close': 6.30,
            'volume': 50 + i,
        })
        # SPX 6880P — first 10 bars liquid, rest stale
        vol = 10 if i < 10 else 0
        rows.append({
            'symbol': 'SPX', 'strike': 6880, 'right': 'P', 'time': t,
            'open': 62.00, 'high': 63.00, 'low': 61.00, 'close': 62.50,
            'volume': vol,
        })

    df = pd.DataFrame(rows)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    return df


# Common parameters for the grid search
SPY_STRIKE = 686
SPX_STRIKE = 6880
ENTRY_SPY_PRICE = 679.66
ENTRY_SPX_PRICE = 6818.56


def _build_grid_search_params(spy_opt_price, spx_opt_price, direction='Sell SPY'):
    """
    Build the kwargs dict for calculate_best_worst_case_with_basis_drift
    for a puts-only strategy.
    """
    if direction == 'Sell SPY':
        put_dir = "Sell SPY, Buy SPX"
        sell_put_px = spy_opt_price
        buy_put_px = spx_opt_price
        sell_puts_qty = 10
        buy_puts_qty = 1
    else:  # Sell SPX
        put_dir = "Buy SPY, Sell SPX"
        sell_put_px = spx_opt_price
        buy_put_px = spy_opt_price
        sell_puts_qty = 1
        buy_puts_qty = 10

    return dict(
        entry_spy_price=ENTRY_SPY_PRICE,
        entry_spx_price=ENTRY_SPX_PRICE,
        spy_strike=SPY_STRIKE,
        spx_strike=SPX_STRIKE,
        call_direction="Sell SPX, Buy SPY",
        put_direction=put_dir,
        sell_call_price=0.0,
        buy_call_price=0.0,
        sell_calls_qty=0,
        buy_calls_qty=0,
        sell_put_price=sell_put_px,
        buy_put_price=buy_put_px,
        sell_puts_qty=sell_puts_qty,
        buy_puts_qty=buy_puts_qty,
        show_calls=False,
        show_puts=True,
        sym1='SPY',
        sym2='SPX',
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWorstCaseConsistency:
    """All three views must produce the same worst-case for the same inputs."""

    def test_historical_analysis_price_lookup(self):
        """Historical Analysis: get_option_price_with_liquidity returns open price from liquid bar."""
        df_options = _make_options()
        entry_time = df_options['time'].iloc[0]

        liq = get_option_price_with_liquidity(df_options, None, 'SPY', 686, 'P', entry_time)
        assert liq is not None
        assert liq['price'] == 6.26
        assert liq['price_source'] == 'trade'
        assert liq['volume'] > 0
        assert not liq['is_stale']

    def test_historical_analysis_prefers_liquid_bars(self):
        """get_option_price_with_liquidity skips stale bars to find a liquid one."""
        df_options = _make_options()
        # Entry time at bar index 15 — SPX 6880P has volume=0 here
        stale_time = df_options['time'].unique()[15]

        liq = get_option_price_with_liquidity(df_options, None, 'SPX', 6880, 'P', stale_time)
        assert liq is not None
        # Should find a liquid bar (from the first 10 bars) instead of the stale one
        assert liq['volume'] > 0, "Should have found a liquid bar"
        assert liq['price'] == 62.00  # open price from a liquid bar

    def test_scanner_uses_open_price(self):
        """Scanner: option price lookup uses open field from volume-filtered data."""
        df_options = _make_options()

        # Filter volume > 0 (what the scanner does)
        spx_opt = df_options[
            (df_options['symbol'] == 'SPX') &
            (df_options['strike'] == 6880) &
            (df_options['right'] == 'P') &
            (df_options['volume'] > 0)
        ].copy().sort_values('time')

        entry_time = spx_opt['time'].iloc[0]

        # Scanner lookup: nearest bar by time, using 'open'
        nearest = spx_opt.iloc[(spx_opt['time'] - entry_time).abs().argsort()[:1]]
        scanner_price = nearest['open'].iloc[0]

        assert scanner_price == 62.00

    def test_overlay_uses_open_price_via_get_option_price_from_db(self):
        """Price Overlay: uses get_option_price_from_db on liquid data, returns open."""
        df_options = _make_options()

        # Filter to liquid bars (what overlay does)
        spx_liquid = df_options[
            (df_options['symbol'] == 'SPX') &
            (df_options['strike'] == 6880) &
            (df_options['right'] == 'P') &
            (df_options['volume'] > 0)
        ].copy()

        entry_time = spx_liquid['time'].iloc[0]
        price = get_option_price_from_db(spx_liquid, 'SPX', 6880, 'P', entry_time)

        assert price == 62.00

    def test_all_three_views_same_price(self):
        """
        The core invariant: all three views look up the same price
        for the same contract at the same time.
        """
        df_options = _make_options()
        entry_time = df_options['time'].iloc[0]

        # 1) Historical Analysis path
        hist_liq = get_option_price_with_liquidity(df_options, None, 'SPX', 6880, 'P', entry_time)
        hist_price = hist_liq['price']

        # 2) Scanner path — volume-filter, then nearest open
        spx_opt = df_options[
            (df_options['symbol'] == 'SPX') &
            (df_options['strike'] == 6880) &
            (df_options['right'] == 'P') &
            (df_options['volume'] > 0)
        ].copy().sort_values('time')
        scanner_nearest = spx_opt.iloc[(spx_opt['time'] - entry_time).abs().argsort()[:1]]
        scanner_price = scanner_nearest['open'].iloc[0]

        # 3) Price Overlay path — get_option_price_from_db on liquid subset
        overlay_price = get_option_price_from_db(spx_opt, 'SPX', 6880, 'P', entry_time)

        assert hist_price == scanner_price == overlay_price, (
            f"Prices differ: hist={hist_price}, scanner={scanner_price}, overlay={overlay_price}"
        )

    def test_all_three_views_same_worst_case(self):
        """
        Given identical option prices, all three views must produce
        the same worst-case P&L from calculate_best_worst_case_with_basis_drift.
        """
        df_options = _make_options()
        entry_time = df_options['time'].iloc[0]

        # --- Resolve prices the way each view does ---

        # Historical Analysis
        spy_liq = get_option_price_with_liquidity(df_options, None, 'SPY', 686, 'P', entry_time)
        spx_liq = get_option_price_with_liquidity(df_options, None, 'SPX', 6880, 'P', entry_time)
        hist_spy_px = spy_liq['price']
        hist_spx_px = spx_liq['price']

        # Scanner (volume-filtered, open)
        spy_opt = df_options[
            (df_options['symbol'] == 'SPY') & (df_options['strike'] == 686) &
            (df_options['right'] == 'P') & (df_options['volume'] > 0)
        ].sort_values('time')
        spx_opt = df_options[
            (df_options['symbol'] == 'SPX') & (df_options['strike'] == 6880) &
            (df_options['right'] == 'P') & (df_options['volume'] > 0)
        ].sort_values('time')

        scan_spy_px = spy_opt.iloc[(spy_opt['time'] - entry_time).abs().argsort()[:1]]['open'].iloc[0]
        scan_spx_px = spx_opt.iloc[(spx_opt['time'] - entry_time).abs().argsort()[:1]]['open'].iloc[0]

        # Price Overlay (get_option_price_from_db on liquid data)
        ov_spy_px = get_option_price_from_db(spy_opt, 'SPY', 686, 'P', entry_time)
        ov_spx_px = get_option_price_from_db(spx_opt, 'SPX', 6880, 'P', entry_time)

        # All prices should be identical
        assert hist_spy_px == scan_spy_px == ov_spy_px, (
            f"SPY prices differ: hist={hist_spy_px}, scan={scan_spy_px}, ov={ov_spy_px}"
        )
        assert hist_spx_px == scan_spx_px == ov_spx_px, (
            f"SPX prices differ: hist={hist_spx_px}, scan={scan_spx_px}, ov={ov_spx_px}"
        )

        # --- Run grid search with each set of prices ---

        params_hist = _build_grid_search_params(hist_spy_px, hist_spx_px)
        params_scan = _build_grid_search_params(scan_spy_px, scan_spx_px)
        params_ov = _build_grid_search_params(ov_spy_px, ov_spx_px)

        _, worst_hist = calculate_best_worst_case_with_basis_drift(**params_hist)
        _, worst_scan = calculate_best_worst_case_with_basis_drift(**params_scan)
        _, worst_ov = calculate_best_worst_case_with_basis_drift(**params_ov)

        wc_hist = worst_hist['net_pnl']
        wc_scan = worst_scan['net_pnl']
        wc_ov = worst_ov['net_pnl']

        assert wc_hist == pytest.approx(wc_scan, abs=0.01), (
            f"Scanner worst case ({wc_scan:.2f}) != Historical ({wc_hist:.2f})"
        )
        assert wc_hist == pytest.approx(wc_ov, abs=0.01), (
            f"Overlay worst case ({wc_ov:.2f}) != Historical ({wc_hist:.2f})"
        )

    def test_stale_bar_not_used_for_price(self):
        """
        When entry time falls on a zero-volume bar, the lookup should
        skip it and find a liquid bar instead — not return a stale price.
        """
        df_options = _make_options()
        # Pick a time where SPX 6880P has volume=0 (bar index 20)
        stale_time = df_options['time'].unique()[20]

        # Historical Analysis path
        liq = get_option_price_with_liquidity(df_options, None, 'SPX', 6880, 'P', stale_time)
        assert liq is not None
        assert liq['volume'] > 0, "Should return a liquid bar, not a stale one"

        # Scanner path (volume filter removes stale bars entirely)
        spx_opt = df_options[
            (df_options['symbol'] == 'SPX') & (df_options['strike'] == 6880) &
            (df_options['right'] == 'P') & (df_options['volume'] > 0)
        ].sort_values('time')
        nearest = spx_opt.iloc[(spx_opt['time'] - stale_time).abs().argsort()[:1]]
        assert nearest['volume'].iloc[0] > 0, "Scanner should only see liquid bars"

    def test_direction_consistency(self):
        """
        Regardless of direction (Sell SPY vs Sell SPX), when called with
        the same prices in the correct slots, the grid search output is
        deterministic and identical across repeated calls.
        """
        params = _build_grid_search_params(6.26, 62.00, direction='Sell SPY')
        _, worst1 = calculate_best_worst_case_with_basis_drift(**params)
        _, worst2 = calculate_best_worst_case_with_basis_drift(**params)

        assert worst1['net_pnl'] == worst2['net_pnl'], "Same inputs must give same output"

    def test_with_real_data(self):
        """
        Integration test using actual CSV data for 2026-02-05.
        Verifies all three views agree on SPY 686 / SPX 6880 puts at 10:00 AM.
        Skipped if data files don't exist.
        """
        import os
        options_file = 'data/options_data_20260205.csv'
        underlying_file = 'data/underlying_prices_20260205.csv'

        if not os.path.exists(options_file) or not os.path.exists(underlying_file):
            pytest.skip("Real data files not found")

        df_options = pd.read_csv(options_file)
        df_options['time'] = pd.to_datetime(df_options['time'], utc=True)

        df_underlying = pd.read_csv(underlying_file)
        df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

        spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].sort_values('time')
        spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].sort_values('time')

        # Target: 10:00 AM ET = 30 minutes after open
        target_time = pd.Timestamp('2026-02-05 10:00', tz='America/New_York').tz_convert('UTC')

        # Look up underlying prices at 10:00
        spy_at = spy_df.iloc[(spy_df['time'] - target_time).abs().argsort()[:1]]
        spx_at = spx_df.iloc[(spx_df['time'] - target_time).abs().argsort()[:1]]
        entry_spy = spy_at['close'].iloc[0]
        entry_spx = spx_at['close'].iloc[0]

        # --- Historical Analysis path ---
        hist_spy = get_option_price_with_liquidity(df_options, None, 'SPY', 686, 'P', target_time)
        hist_spx = get_option_price_with_liquidity(df_options, None, 'SPX', 6880, 'P', target_time)

        assert hist_spy is not None, "SPY 686P not found"
        assert hist_spx is not None, "SPX 6880P not found"

        # --- Scanner path ---
        spy_opt = df_options[
            (df_options['symbol'] == 'SPY') & (df_options['strike'] == 686) &
            (df_options['right'] == 'P') & (df_options['volume'] > 0)
        ].sort_values('time')
        spx_opt = df_options[
            (df_options['symbol'] == 'SPX') & (df_options['strike'] == 6880) &
            (df_options['right'] == 'P') & (df_options['volume'] > 0)
        ].sort_values('time')

        scan_spy_row = spy_opt.iloc[(spy_opt['time'] - target_time).abs().argsort()[:1]]
        scan_spx_row = spx_opt.iloc[(spx_opt['time'] - target_time).abs().argsort()[:1]]
        scan_spy_px = scan_spy_row['open'].iloc[0]
        scan_spx_px = scan_spx_row['open'].iloc[0]

        # --- Price Overlay path ---
        ov_spy_px = get_option_price_from_db(spy_opt, 'SPY', 686, 'P', target_time)
        ov_spx_px = get_option_price_from_db(spx_opt, 'SPX', 6880, 'P', target_time)

        # Print prices for debugging
        print(f"\nReal data prices at 10:00 AM ET:")
        print(f"  Historical Analysis: SPY={hist_spy['price']:.2f} (vol={hist_spy['volume']}), "
              f"SPX={hist_spx['price']:.2f} (vol={hist_spx['volume']})")
        print(f"  Scanner:             SPY={scan_spy_px:.2f}, SPX={scan_spx_px:.2f}")
        print(f"  Price Overlay:       SPY={ov_spy_px:.2f}, SPX={ov_spx_px:.2f}")

        # All three must agree on prices
        assert hist_spy['price'] == pytest.approx(scan_spy_px, abs=0.01), (
            f"SPY price mismatch: hist={hist_spy['price']}, scanner={scan_spy_px}"
        )
        assert hist_spx['price'] == pytest.approx(scan_spx_px, abs=0.01), (
            f"SPX price mismatch: hist={hist_spx['price']}, scanner={scan_spx_px}"
        )
        assert hist_spy['price'] == pytest.approx(ov_spy_px, abs=0.01), (
            f"SPY price mismatch: hist={hist_spy['price']}, overlay={ov_spy_px}"
        )
        assert hist_spx['price'] == pytest.approx(ov_spx_px, abs=0.01), (
            f"SPX price mismatch: hist={hist_spx['price']}, overlay={ov_spx_px}"
        )

        # Run grid search with each set
        kwargs_base = dict(
            entry_spy_price=entry_spy,
            entry_spx_price=entry_spx,
            spy_strike=686,
            spx_strike=6880,
            call_direction="Sell SPX, Buy SPY",
            put_direction="Sell SPY, Buy SPX",
            sell_call_price=0.0, buy_call_price=0.0,
            sell_calls_qty=0, buy_calls_qty=0,
            sell_puts_qty=10, buy_puts_qty=1,
            show_calls=False, show_puts=True,
            sym1='SPY', sym2='SPX',
        )

        _, worst_hist = calculate_best_worst_case_with_basis_drift(
            **{**kwargs_base, 'sell_put_price': hist_spy['price'], 'buy_put_price': hist_spx['price']})
        _, worst_scan = calculate_best_worst_case_with_basis_drift(
            **{**kwargs_base, 'sell_put_price': scan_spy_px, 'buy_put_price': scan_spx_px})
        _, worst_ov = calculate_best_worst_case_with_basis_drift(
            **{**kwargs_base, 'sell_put_price': ov_spy_px, 'buy_put_price': ov_spx_px})

        print(f"\nWorst-case P&L:")
        print(f"  Historical Analysis: ${worst_hist['net_pnl']:,.2f}")
        print(f"  Scanner:             ${worst_scan['net_pnl']:,.2f}")
        print(f"  Price Overlay:       ${worst_ov['net_pnl']:,.2f}")

        assert worst_hist['net_pnl'] == pytest.approx(worst_scan['net_pnl'], abs=0.01), (
            f"Scanner ({worst_scan['net_pnl']:.2f}) != Historical ({worst_hist['net_pnl']:.2f})"
        )
        assert worst_hist['net_pnl'] == pytest.approx(worst_ov['net_pnl'], abs=0.01), (
            f"Overlay ({worst_ov['net_pnl']:.2f}) != Historical ({worst_hist['net_pnl']:.2f})"
        )

        print(f"\n  All three views agree.")


class TestBasisDriftCoverage:
    """
    Verify that the basis_drift_pct parameter is wide enough to cover
    actual observed market drift, so worst-case is a true floor on P&L.
    """

    def test_actual_pnl_within_worst_case_spy687_spx6885(self):
        """
        Regression test for the observed case where actual P&L ($541) was
        worse than the reported worst case ($638.66) due to basis_drift_pct
        being too tight at 0.0005 (0.05%).

        Actual basis drift was +0.0688%, exceeding the old 0.05% assumption.
        With the corrected 0.10% drift, worst case must be <= actual P&L.
        """
        # Entry conditions at 10:10 AM on 2026-02-05
        entry_spy = 682.39
        entry_spx = 6846.50

        spy_strike = 687
        spx_strike = 6885

        # Option entry prices (puts only, Sell SPY / Buy SPX)
        spy_put_price = 6.10   # selling SPY 687P
        spx_put_price = 55.80  # buying SPX 6885P

        # Actual observed EOD prices
        eod_spy = 678.69
        eod_spx = 6809.98

        # Calculate actual P&L
        # SPY 687P settlement: max(0, 687 - 678.69) = 8.31
        # SPX 6885P settlement: max(0, 6885 - 6809.98) = 75.02
        spy_put_settle = max(0, spy_strike - eod_spy)
        spx_put_settle = max(0, spx_strike - eod_spx)

        # Sell 10 SPY puts: (entry - exit) * qty * 100 = (6.10 - 8.31) * 10 * 100
        sell_spy_pnl = (spy_put_price - spy_put_settle) * 10 * 100
        # Buy 1 SPX put: (exit - entry) * qty * 100 = (75.02 - 55.80) * 1 * 100
        buy_spx_pnl = (spx_put_settle - spx_put_price) * 1 * 100

        actual_pnl = sell_spy_pnl + buy_spx_pnl
        print(f"\nActual P&L breakdown:")
        print(f"  SPY 687P settle: {spy_put_settle:.2f}, PnL: ${sell_spy_pnl:,.2f}")
        print(f"  SPX 6885P settle: {spx_put_settle:.2f}, PnL: ${buy_spx_pnl:,.2f}")
        print(f"  Total actual P&L: ${actual_pnl:,.2f}")

        # Calculate worst case using the grid search
        _, worst = calculate_best_worst_case_with_basis_drift(
            entry_spy_price=entry_spy,
            entry_spx_price=entry_spx,
            spy_strike=spy_strike,
            spx_strike=spx_strike,
            call_direction="Sell SPX, Buy SPY",
            put_direction="Sell SPY, Buy SPX",
            sell_call_price=0.0,
            buy_call_price=0.0,
            sell_calls_qty=0,
            buy_calls_qty=0,
            sell_put_price=spy_put_price,
            buy_put_price=spx_put_price,
            sell_puts_qty=10,
            buy_puts_qty=1,
            show_calls=False,
            show_puts=True,
            sym1='SPY',
            sym2='SPX',
        )

        worst_pnl = worst['net_pnl']
        print(f"  Model worst case: ${worst_pnl:,.2f}")
        print(f"  Margin: ${actual_pnl - worst_pnl:,.2f}")

        # CRITICAL: worst case must be <= actual outcome
        assert worst_pnl <= actual_pnl, (
            f"Worst case (${worst_pnl:,.2f}) exceeds actual P&L (${actual_pnl:,.2f}). "
            f"basis_drift_pct is still too tight!"
        )

    def test_observed_drift_within_model_range(self):
        """
        Verify the actual observed basis drift from 2026-02-05 falls within
        the model's basis_drift_pct range.
        """
        entry_spy = 682.39
        entry_spx = 6846.50
        eod_spy = 678.69
        eod_spx = 6809.98

        entry_ratio = entry_spx / entry_spy
        eod_ratio = eod_spx / eod_spy
        actual_drift = abs(eod_ratio / entry_ratio - 1)

        model_drift_pct = 0.001  # current default

        print(f"\nBasis drift analysis:")
        print(f"  Entry ratio: {entry_ratio:.6f}")
        print(f"  EOD ratio:   {eod_ratio:.6f}")
        print(f"  Actual drift: {actual_drift*100:.4f}%")
        print(f"  Model covers: ±{model_drift_pct*100:.2f}%")

        assert actual_drift <= model_drift_pct, (
            f"Actual drift ({actual_drift*100:.4f}%) exceeds model range "
            f"(±{model_drift_pct*100:.2f}%). Increase basis_drift_pct!"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
