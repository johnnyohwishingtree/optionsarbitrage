"""Integration tests — app boot, tab routing, and end-to-end data flow.

These verify that the full pipeline works: import → load data → build position
→ calculate P&L. Tests that require market data skip gracefully if no CSVs exist.
"""

import pytest
from dash import html


# ---------------------------------------------------------------------------
# App Boot
# ---------------------------------------------------------------------------

class TestAppBoot:
    """Verify the Dash app initializes correctly."""

    def test_app_imports_without_error(self):
        import app
        assert app.app is not None

    def test_app_has_layout(self):
        import app
        assert app.app.layout is not None

    def test_all_tabs_registered(self):
        """All 5 tab values should appear in the Tabs component."""
        import app

        expected_tabs = {'historical', 'live_trading', 'price_overlay', 'divergence', 'scanner'}

        def find_tabs(component):
            from dash import dcc
            if isinstance(component, dcc.Tabs):
                return {child.value for child in component.children if hasattr(child, 'value')}
            if hasattr(component, 'children'):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        result = find_tabs(child)
                        if result:
                            return result
                elif children is not None:
                    return find_tabs(children)
            return None

        found = find_tabs(app.app.layout)
        assert found == expected_tabs, f"Expected {expected_tabs}, found {found}"

    def test_suppress_callback_exceptions_is_true(self):
        """Required for dynamic tab content pattern."""
        import app
        assert app.app.config.suppress_callback_exceptions is True


# ---------------------------------------------------------------------------
# Data Flow
# ---------------------------------------------------------------------------

class TestDataFlow:
    """End-to-end data flow: load → position → P&L."""

    @pytest.fixture
    def test_date(self):
        from src.data_loader import list_available_dates
        dates = list_available_dates()
        if not dates:
            pytest.skip("No test data available in data/")
        return dates[-1][0]  # oldest date (most stable for testing)

    def test_underlying_prices_load(self, test_date):
        """Can load underlying prices for a date."""
        from src.data_loader import load_underlying_prices
        df = load_underlying_prices(test_date)
        assert len(df) > 0
        assert 'symbol' in df.columns
        assert 'close' in df.columns
        assert 'time' in df.columns

    def test_symbol_pairs_resolve(self, test_date):
        """Can resolve available symbol pairs."""
        from src.data_loader import load_underlying_prices, get_available_pairs
        df = load_underlying_prices(test_date)
        pairs = get_available_pairs(df)
        assert len(pairs) > 0
        for pair_name, (sym1, sym2) in pairs.items():
            assert isinstance(sym1, str)
            assert isinstance(sym2, str)

    def test_symbol_dataframes_split(self, test_date):
        """Can split underlying data into per-symbol DataFrames."""
        from src.data_loader import (
            load_underlying_prices, get_available_pairs, get_symbol_dataframes,
        )
        df = load_underlying_prices(test_date)
        pairs = get_available_pairs(df)
        pair_name = list(pairs.keys())[0]
        sym1, sym2 = pairs[pair_name]

        sym1_df, sym2_df = get_symbol_dataframes(df, sym1, sym2)
        assert len(sym1_df) > 0
        assert len(sym2_df) > 0
        assert all(sym1_df['symbol'] == sym1)
        assert all(sym2_df['symbol'] == sym2)

    def test_position_construction(self, test_date):
        """Can build a position from loaded data."""
        from src.data_loader import (
            load_underlying_prices, get_available_pairs, get_symbol_dataframes,
        )
        from src.position import determine_leg_setup
        from src.config import get_qty_ratio, get_strike_step

        df = load_underlying_prices(test_date)
        pairs = get_available_pairs(df)
        pair_name = list(pairs.keys())[0]
        sym1, sym2 = pairs[pair_name]
        sym1_df, sym2_df = get_symbol_dataframes(df, sym1, sym2)

        qty_ratio = get_qty_ratio(sym2)
        strike_step = get_strike_step(sym2)
        sym1_strike = int(round(sym1_df.iloc[0]['close']))
        sym2_strike = int(round(sym2_df.iloc[0]['close'] / strike_step) * strike_step)

        # Use asymmetric prices to ensure a non-zero credit
        position = determine_leg_setup(
            call_direction=f"Sell {sym2}, Buy {sym1}",
            put_direction=f"Sell {sym1}, Buy {sym2}",
            sym1=sym1, sym2=sym2,
            qty_ratio=qty_ratio,
            sym1_strike=sym1_strike, sym2_strike=sym2_strike,
            sym1_call_price=2.50, sym2_call_price=28.00,
            sym1_put_price=2.00, sym2_put_price=23.00,
            show_calls=True, show_puts=True,
        )

        assert len(position.legs) == 4
        assert isinstance(position.total_credit, float)

    def test_pnl_grid_search(self, test_date):
        """Can run the full best/worst case grid search."""
        from src.data_loader import (
            load_underlying_prices, get_available_pairs, get_symbol_dataframes,
        )
        from src.pnl import calculate_best_worst_case_with_basis_drift
        from src.config import get_qty_ratio

        df = load_underlying_prices(test_date)
        pairs = get_available_pairs(df)
        pair_name = list(pairs.keys())[0]
        sym1, sym2 = pairs[pair_name]
        sym1_df, sym2_df = get_symbol_dataframes(df, sym1, sym2)

        qty_ratio = get_qty_ratio(sym2)
        entry_sym1 = sym1_df.iloc[0]['close']
        entry_sym2 = sym2_df.iloc[0]['close']
        sym1_strike = int(round(entry_sym1))
        sym2_strike = int(round(entry_sym2 / 5) * 5) if sym2 == 'SPX' else int(round(entry_sym2))

        best, worst = calculate_best_worst_case_with_basis_drift(
            entry_spy_price=entry_sym1,
            entry_spx_price=entry_sym2,
            spy_strike=sym1_strike,
            spx_strike=sym2_strike,
            call_direction=f"Sell {sym2}, Buy {sym1}",
            put_direction=f"Sell {sym1}, Buy {sym2}",
            sell_call_price=25.00, buy_call_price=2.50,
            sell_calls_qty=1, buy_calls_qty=qty_ratio,
            sell_put_price=20.00, buy_put_price=2.00,
            sell_puts_qty=1, buy_puts_qty=qty_ratio,
            show_calls=True, show_puts=True,
            sym1=sym1, sym2=sym2,
        )

        assert 'net_pnl' in best
        assert 'net_pnl' in worst
        assert best['net_pnl'] >= worst['net_pnl']

    def test_price_lookup_pipeline(self, test_date):
        """Can look up option prices with liquidity (full pipeline)."""
        from src.data_loader import (
            load_underlying_prices, load_options_data, load_bidask_data,
            get_available_pairs, get_symbol_dataframes,
        )
        from src.pricing import get_option_price_with_liquidity
        from src.config import get_strike_step

        df = load_underlying_prices(test_date)
        df_options = load_options_data(test_date)
        df_bidask = load_bidask_data(test_date)

        if df_options is None and df_bidask is None:
            pytest.skip("No options data for this date")

        pairs = get_available_pairs(df)
        pair_name = list(pairs.keys())[0]
        sym1, sym2 = pairs[pair_name]
        sym1_df, sym2_df = get_symbol_dataframes(df, sym1, sym2)

        entry_time = sym1_df.iloc[0]['time']
        sym1_strike = int(round(sym1_df.iloc[0]['close']))

        # This should not raise, even if it returns None for the contract
        result = get_option_price_with_liquidity(
            df_options, df_bidask, sym1, sym1_strike, 'P', entry_time
        )
        # Result is either None (contract not found) or a dict
        assert result is None or isinstance(result, dict)
        if result is not None:
            assert 'price' in result
            assert 'price_source' in result
            assert 'is_stale' in result


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases in business logic: zero prices, empty data, etc."""

    def test_pnl_with_zero_entry_price(self):
        """P&L calculation should handle zero entry price."""
        from src.pnl import calculate_option_pnl
        # Selling at 0, settling at 1 → loss
        pnl = calculate_option_pnl(0.0, 1.0, 'SELL', 1)
        assert pnl == -100.0

    def test_pnl_with_zero_exit_price(self):
        """P&L when option expires worthless."""
        from src.pnl import calculate_option_pnl
        # Sold at 2.00, expires at 0 → keep premium
        pnl = calculate_option_pnl(2.0, 0.0, 'SELL', 1)
        assert pnl == 200.0

    def test_settlement_value_at_strike(self):
        """Settlement at exactly the strike → 0 intrinsic."""
        from src.pnl import calculate_settlement_value
        assert calculate_settlement_value(600.0, 600.0, 'C') == 0.0
        assert calculate_settlement_value(600.0, 600.0, 'P') == 0.0

    def test_position_with_zero_prices(self):
        """Position construction should handle zero option prices."""
        from src.position import determine_leg_setup
        position = determine_leg_setup(
            call_direction="Buy SPX, Sell SPY",
            put_direction="Buy SPY, Sell SPX",
            sym1='SPY', sym2='SPX',
            qty_ratio=10,
            sym1_strike=600, sym2_strike=6000,
            sym1_call_price=0.0, sym2_call_price=0.0,
            sym1_put_price=0.0, sym2_put_price=0.0,
            show_calls=True, show_puts=True,
        )
        assert position.total_credit == 0.0
        assert len(position.legs) == 4

    def test_grid_search_with_zero_prices(self):
        """Grid search should handle zero option prices gracefully."""
        from src.pnl import calculate_best_worst_case_with_basis_drift
        best, worst = calculate_best_worst_case_with_basis_drift(
            entry_spy_price=600.0, entry_spx_price=6000.0,
            spy_strike=600, spx_strike=6000,
            call_direction="Buy SPX, Sell SPY",
            put_direction="Buy SPY, Sell SPX",
            sell_call_price=0.0, buy_call_price=0.0,
            sell_calls_qty=10, buy_calls_qty=1,
            sell_put_price=0.0, buy_put_price=0.0,
            sell_puts_qty=1, buy_puts_qty=10,
            show_calls=True, show_puts=True,
        )
        assert 'net_pnl' in best
        assert 'net_pnl' in worst

    def test_credit_calculation_with_asymmetric_qty(self):
        """Credit calc with 10:1 ratio."""
        from src.position import calculate_credit
        # Sell 1 SPX @ $25 (1*25*100=2500), Buy 10 SPY @ $2.50 (10*2.50*100=2500)
        credit = calculate_credit(25.0, 1, 2.50, 10)
        assert credit == pytest.approx(0.0)

        # Sell 1 SPX @ $26 (2600), Buy 10 SPY @ $2.50 (2500) → credit = $100
        credit = calculate_credit(26.0, 1, 2.50, 10)
        assert credit == pytest.approx(100.0)

    def test_margin_with_no_short_legs(self):
        """All-long position should have zero margin."""
        from src.position import calculate_margin_from_legs
        from src.models import Leg
        legs = [
            Leg('SPY', 600, 'C', 'BUY', 10, 2.50),
            Leg('SPX', 6000, 'C', 'BUY', 1, 25.00),
        ]
        margin = calculate_margin_from_legs(legs)
        assert margin == 0.0

    def test_missing_date_raises(self):
        """Loading data for a nonexistent date should raise FileNotFoundError."""
        from src.data_loader import load_underlying_prices
        with pytest.raises(FileNotFoundError):
            load_underlying_prices('99999999')
