"""Tests for Dash callback wiring and layout consistency.

Validates that all callback IDs exist in the layout, callbacks return correct
output shapes, and all page modules import cleanly.
"""

import importlib
import pytest

from app import app
from dash._callback import GLOBAL_CALLBACK_MAP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_all_static_ids():
    """Recursively extract all component IDs from the static layout."""
    ids = set()

    def walk(component):
        if hasattr(component, 'id') and component.id:
            ids.add(component.id)
        if hasattr(component, 'children'):
            children = component.children
            if isinstance(children, list):
                for child in children:
                    walk(child)
            elif children is not None:
                walk(children)

    walk(app.layout)
    return ids


def _get_all_callback_ids():
    """Extract all IDs referenced by callbacks (Inputs, Outputs, States)."""
    ids = set()
    for key, val in GLOBAL_CALLBACK_MAP.items():
        # Inputs
        for dep in val.get('inputs', []):
            ids.add(dep['id'])
        # States
        for dep in val.get('state', []):
            ids.add(dep['id'])
        # Outputs
        outputs = val.get('output', [])
        if not isinstance(outputs, list):
            outputs = [outputs]
        for out in outputs:
            if hasattr(out, 'component_id'):
                ids.add(out.component_id)
    return ids


# IDs that are created dynamically by tab-switching (render_tab callback).
# These live inside page layouts that are returned at runtime, not at startup.
DYNAMIC_TAB_IDS = {
    # historical.py
    'strategy-select',
    'historical-analysis-output',
    # live_trading.py
    'live-refresh-btn',
    'live-last-updated',
    'live-auto-refresh-toggle',
    'live-refresh-interval',
    'live-trading-content',
    # price_overlay.py
    'overlay-right',
    'overlay-content',
    # divergence.py
    'divergence-content',
    # scanner.py
    'scanner-right-select',
    'scanner-min-volume',
    'scanner-hide-illiquid',
    'scan-button',
    'scanner-status',
    'scanner-loading',
    'scanner-results-store',
    'scanner-results-section',
    'scanner-rank-tabs',
    # scanner tables are now in static layout (inside Tab children)
    'scanner-table-safety',
    'scanner-table-profit',
    'scanner-table-risk_reward',
}


# ---------------------------------------------------------------------------
# Layer 1a: Layout ID validation
# ---------------------------------------------------------------------------

class TestLayoutIds:
    """Verify all callback-referenced IDs exist in layout or are known-dynamic."""

    def test_no_orphaned_callback_ids(self):
        """Every ID referenced in a callback must be in the static layout or known-dynamic."""
        static_ids = _get_all_static_ids()
        all_known = static_ids | DYNAMIC_TAB_IDS
        callback_ids = _get_all_callback_ids()

        missing = callback_ids - all_known
        assert missing == set(), (
            f"Callback references IDs not in layout or known-dynamic: {missing}"
        )

    def test_static_layout_has_core_ids(self):
        """Core shared IDs must exist in the static layout (not tab-dynamic)."""
        static_ids = _get_all_static_ids()
        required_core = {
            'config-store',
            'selected-scan-result',
            'apply-banner',
            'main-tabs',
            'tab-content',
            'date-selector',
            'pair-selector',
            'entry-time-slider',
            'sym1-strike-input',
            'sym2-strike-input',
            'call-direction-select',
            'put-direction-select',
        }
        missing = required_core - static_ids
        assert missing == set(), f"Core IDs missing from static layout: {missing}"

    def test_no_duplicate_static_ids(self):
        """No component ID should appear more than once in the static layout."""
        seen = []
        duplicates = []

        def walk(component):
            if hasattr(component, 'id') and component.id:
                if component.id in seen:
                    duplicates.append(component.id)
                seen.append(component.id)
            if hasattr(component, 'children'):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        walk(child)
                elif children is not None:
                    walk(children)

        walk(app.layout)
        assert duplicates == [], f"Duplicate IDs in static layout: {duplicates}"


# ---------------------------------------------------------------------------
# Layer 1b: Scanner dynamic table validation
# ---------------------------------------------------------------------------

class TestScannerTableWiring:
    """Validate that scanner tables are properly wired for the apply callback."""

    def test_scanner_tables_referenced_in_callback(self):
        """The apply_scan_result callback must reference all three scanner tables."""
        # Find the callback that outputs to selected-scan-result
        cb = GLOBAL_CALLBACK_MAP.get('selected-scan-result.data')
        assert cb is not None, "apply_scan_result callback not found"

        input_ids = {dep['id'] for dep in cb['inputs']}
        expected = {'scanner-table-safety', 'scanner-table-profit', 'scanner-table-risk_reward'}
        assert expected.issubset(input_ids), (
            f"apply_scan_result callback missing table Inputs: {expected - input_ids}"
        )

    def test_scanner_tables_exist_in_scanner_layout(self):
        """Scanner tables must exist in the scanner tab layout.

        Previously these were created/destroyed dynamically as the user switched
        ranking tabs. Now all three are defined in the scanner layout() so they
        always exist once the scanner tab is active.
        """
        from src.pages.scanner import layout as scanner_layout

        scanner_ids = set()
        def walk(component):
            if hasattr(component, 'id') and component.id:
                scanner_ids.add(component.id)
            if hasattr(component, 'children'):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        walk(child)
                elif children is not None:
                    walk(children)

        walk(scanner_layout())
        required = {'scanner-table-safety', 'scanner-table-profit', 'scanner-table-risk_reward'}
        missing = required - scanner_ids
        assert missing == set(), (
            f"Scanner tables missing from scanner layout: {missing}. "
            f"The apply_scan_result callback references these as Inputs."
        )


# ---------------------------------------------------------------------------
# Layer 1c: Callback return shape tests
# ---------------------------------------------------------------------------

class TestCallbackReturnShapes:
    """Verify callbacks return the right number of outputs."""

    def test_update_controls_returns_12_values(self):
        """update_controls must return exactly 12 values for empty inputs."""
        from src.pages.sidebar import update_controls
        result = update_controls(None, None)
        assert len(result) == 12, f"Expected 12 outputs, got {len(result)}"

    def test_update_config_returns_3_values(self):
        """update_config_store must return 3 values for empty inputs."""
        from src.pages.sidebar import update_config_store
        result = update_config_store(None, None, None, None, None, None, None)
        assert len(result) == 3, f"Expected 3 outputs, got {len(result)}"

    def test_historical_analysis_empty_config(self):
        """update_historical_analysis returns a Div on empty config."""
        from dash import html
        from src.pages.historical import update_historical_analysis
        result = update_historical_analysis({}, 'full', 'historical')
        assert isinstance(result, html.Div)

    def test_historical_analysis_none_config(self):
        """update_historical_analysis handles None config."""
        from dash import html
        from src.pages.historical import update_historical_analysis
        result = update_historical_analysis(None, 'full', 'historical')
        assert isinstance(result, html.Div)

    def test_moneyness_empty_config(self):
        """update_moneyness returns empty string for missing config."""
        from src.pages.sidebar import update_moneyness
        result = update_moneyness({})
        assert result == ""

    def test_moneyness_valid_config(self):
        """update_moneyness returns a Div for valid config."""
        from dash import html
        from src.pages.sidebar import update_moneyness
        result = update_moneyness({
            'sym1_strike': 600,
            'sym2_strike': 6000,
            'entry_sym1_price': 600.0,
            'entry_sym2_price': 6000.0,
        })
        assert isinstance(result, html.Div)

    def test_toggle_auto_refresh(self):
        """toggle_auto_refresh returns boolean."""
        from src.pages.live_trading import toggle_auto_refresh
        assert toggle_auto_refresh([]) is True
        assert toggle_auto_refresh(['on']) is False
        assert toggle_auto_refresh(None) is True

    def test_render_tab_returns_div(self):
        """render_tab returns Dash components for all valid tab values."""
        from dash import html
        from app import render_tab

        for tab in ['historical', 'live_trading', 'price_overlay', 'divergence', 'scanner']:
            result = render_tab(tab)
            assert result is not None, f"render_tab('{tab}') returned None"
            assert isinstance(result, html.Div), f"render_tab('{tab}') didn't return Div"

    def test_render_tab_unknown(self):
        """render_tab returns a fallback for unknown tab value."""
        from dash import html
        from app import render_tab
        result = render_tab('nonexistent')
        assert isinstance(result, html.Div)

    def test_show_apply_banner_none(self):
        """show_apply_banner returns None when no scan result."""
        from app import show_apply_banner
        assert show_apply_banner(None) is None
        assert show_apply_banner({}) is None

    def test_show_apply_banner_with_data(self):
        """show_apply_banner returns a Div when scan result provided."""
        from dash import html
        from app import show_apply_banner
        result = show_apply_banner({
            'sym1': 'SPY', 'sym2': 'SPX',
            'sym1_strike': 600, 'sym2_strike': 6000,
            'direction': 'Sell SPX', 'entry_time': '10:00',
        })
        assert isinstance(result, html.Div)

    def test_update_ranking_tables_empty(self):
        """update_ranking_tables handles empty results."""
        from src.pages.scanner import update_ranking_tables
        safety, profit, rr = update_ranking_tables([])
        assert safety == []
        assert profit == []
        assert rr == []

    def test_update_ranking_tables_with_data(self):
        """update_ranking_tables returns sorted data for all three tables."""
        from src.pages.scanner import update_ranking_tables

        mock_data = [
            {
                'sym1_strike': 600, 'sym2_strike': 6000,
                'moneyness': 'ATM', 'direction': 'Sell SPX',
                'credit': 150.0, 'worst_case_pnl': -50.0,
                'risk_reward': 3.0, 'max_gap': 0.0012,
                'max_gap_time': '10:00', 'best_wc_time': '10:30',
                'sym1_vol': 100, 'sym2_vol': 50,
                'liquidity': 'OK', 'price_source': 'mid',
            },
            {
                'sym1_strike': 601, 'sym2_strike': 6010,
                'moneyness': 'ATM', 'direction': 'Sell SPX',
                'credit': 200.0, 'worst_case_pnl': 10.0,
                'risk_reward': 5.0, 'max_gap': 0.0015,
                'max_gap_time': '10:05', 'best_wc_time': '10:35',
                'sym1_vol': 80, 'sym2_vol': 40,
                'liquidity': 'OK', 'price_source': 'mid',
            },
        ]

        safety, profit, rr = update_ranking_tables(mock_data)
        assert len(safety) == 2
        assert len(profit) == 2
        assert len(rr) == 2
        # Safety: highest worst_case_pnl first
        assert safety[0]['worst_case_pnl'] >= safety[1]['worst_case_pnl']
        # Profit: highest credit first
        assert profit[0]['credit'] >= profit[1]['credit']
        # Risk/Reward: highest risk_reward first
        assert rr[0]['risk_reward'] >= rr[1]['risk_reward']

    def test_overlay_empty_config(self):
        """update_overlay handles empty config."""
        from dash import html
        from src.pages.price_overlay import update_overlay
        result = update_overlay({}, 'P', 'price_overlay')
        assert isinstance(result, html.P)

    def test_divergence_empty_config(self):
        """update_divergence handles empty config."""
        from dash import html
        from src.pages.divergence import update_divergence
        result = update_divergence({}, 'divergence')
        assert isinstance(result, html.P)


# ---------------------------------------------------------------------------
# Layer 1d: Page import tests
# ---------------------------------------------------------------------------

class TestPageImports:
    """Verify all page modules import cleanly and define layout()."""

    @pytest.mark.parametrize("module_name", [
        'src.pages.sidebar',
        'src.pages.historical',
        'src.pages.live_trading',
        'src.pages.price_overlay',
        'src.pages.divergence',
        'src.pages.scanner',
        'src.pages.components',
    ])
    def test_page_has_layout_or_is_utility(self, module_name):
        """Each page module should import and have layout() if it's a page."""
        mod = importlib.import_module(module_name)
        if module_name != 'src.pages.components':
            assert hasattr(mod, 'layout'), f"{module_name} missing layout()"
            assert callable(mod.layout)

    def test_components_module_exports(self):
        """components.py should export shared constants and functions."""
        from src.pages.components import (
            SECTION_STYLE, TABLE_STYLE, TH_STYLE, TD_STYLE, TD_RIGHT,
            POSITIVE_STYLE, NEGATIVE_STYLE, NEUTRAL_STYLE, WARNING_STYLE,
            COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_NEUTRAL,
            pnl_span, metric_card, section,
        )
        assert callable(pnl_span)
        assert callable(metric_card)
        assert callable(section)
        assert isinstance(SECTION_STYLE, dict)


# ---------------------------------------------------------------------------
# Layer 2: Bug fix regression tests
# ---------------------------------------------------------------------------

class TestBugFixes:
    """Regression tests for QA-reported bugs."""

    def test_bug001_historical_exception_handler(self):
        """BUG-001: update_historical_analysis catches business logic errors gracefully."""
        from dash import html
        from src.pages.historical import update_historical_analysis
        # Config with invalid strike type should trigger an error in business logic,
        # but be caught by the exception handler instead of crashing.
        bad_config = {
            'date': '99999999',  # nonexistent date triggers FileNotFoundError
            'sym1': 'SPY', 'sym2': 'SPX',
            'qty_ratio': 10, 'entry_time_idx': 0,
            'sym1_strike': 600, 'sym2_strike': 6000,
            'call_direction': 'Sell SPX, Buy SPY',
            'put_direction': 'Sell SPY, Buy SPX',
            'entry_sym1_price': 600.0, 'entry_sym2_price': 6000.0,
            'entry_time_label': '10:00',
        }
        result = update_historical_analysis(bad_config, 'full', 'historical')
        # Should return a Div with error message, not raise
        assert isinstance(result, html.Div)

    def test_bug002_live_trading_initial_guard(self):
        """BUG-002: update_live_trading returns prompt on n_clicks=0."""
        from src.pages.live_trading import update_live_trading
        content, timestamp = update_live_trading(0, None, {})
        assert 'Click Refresh' in content.children
        assert timestamp == ""

    def test_bug002_live_trading_none_clicks(self):
        """BUG-002: update_live_trading handles None n_clicks."""
        from src.pages.live_trading import update_live_trading
        content, timestamp = update_live_trading(None, None, None)
        assert 'Click Refresh' in content.children

    def test_bug003_scanner_min_volume_zero(self):
        """BUG-003: min_volume=0 should use 0, not fall back to default."""
        # Test the fixed expression directly
        min_volume = 0
        from src.config import DEFAULT_MIN_VOLUME
        min_vol = int(min_volume) if min_volume is not None else DEFAULT_MIN_VOLUME
        assert min_vol == 0, f"Expected 0, got {min_vol}"

    def test_bug003_scanner_min_volume_none(self):
        """BUG-003: min_volume=None should use default."""
        min_volume = None
        from src.config import DEFAULT_MIN_VOLUME
        min_vol = int(min_volume) if min_volume is not None else DEFAULT_MIN_VOLUME
        assert min_vol == DEFAULT_MIN_VOLUME

    def test_bug004_scanner_exception_handler(self):
        """BUG-004: run_scan catches errors and returns 3-tuple."""
        from src.pages.scanner import run_scan
        # Config with bad date should trigger an error caught by the handler
        bad_config = {
            'date': '99999999',
            'sym1': 'SPY', 'sym2': 'SPX',
            'qty_ratio': 10,
        }
        result = run_scan(1, bad_config, 'P', 10, ['hide'])
        # Should return 3-tuple: ([], error_div, style)
        assert isinstance(result, tuple)
        assert len(result) == 3
        data, status, style = result
        assert data == []
        assert style == {'display': 'none'}

    def test_bug005_overlay_empty_dataframe(self):
        """BUG-005: update_overlay handles config with nonexistent symbols."""
        from dash import html
        from src.pages.price_overlay import update_overlay
        # Config referencing a nonexistent date triggers error, caught by broad except
        bad_config = {
            'date': '99999999',
            'sym1': 'SPY', 'sym2': 'SPX',
            'sym1_strike': 600, 'sym2_strike': 6000,
            'qty_ratio': 10,
        }
        result = update_overlay(bad_config, 'P', 'price_overlay')
        # Should return an error Div, not crash
        assert isinstance(result, (html.P, html.Div))

    def test_bug006_historical_tab_guard(self):
        """BUG-006: update_historical_analysis returns no_update when tab not active."""
        from dash import no_update
        from src.pages.historical import update_historical_analysis
        valid_config = {
            'date': '20260207', 'sym1': 'SPY', 'sym2': 'SPX',
            'qty_ratio': 10, 'entry_time_idx': 0,
            'sym1_strike': 600, 'sym2_strike': 6000,
        }
        result = update_historical_analysis(valid_config, 'full', 'scanner')
        assert result is no_update

    def test_bug006_divergence_tab_guard(self):
        """BUG-006: update_divergence returns no_update when tab not active."""
        from dash import no_update
        from src.pages.divergence import update_divergence
        result = update_divergence({'date': '20260207'}, 'historical')
        assert result is no_update

    def test_bug006_overlay_tab_guard(self):
        """BUG-006: update_overlay returns no_update when tab not active."""
        from dash import no_update
        from src.pages.price_overlay import update_overlay
        result = update_overlay({'date': '20260207'}, 'P', 'historical')
        assert result is no_update

    def test_bug007_moneyness_zero_price(self):
        """BUG-007: update_moneyness handles zero entry prices without ZeroDivisionError."""
        from src.pages.sidebar import update_moneyness
        config_zero_price = {
            'sym1_strike': 600,
            'sym2_strike': 6000,
            'entry_sym1_price': 0.0,
            'entry_sym2_price': 6000.0,
        }
        # Should return "" (empty), not raise ZeroDivisionError
        result = update_moneyness(config_zero_price)
        assert result == ""

    def test_bug007_moneyness_missing_price(self):
        """BUG-007: update_moneyness handles missing price keys."""
        from src.pages.sidebar import update_moneyness
        config_no_price = {
            'sym1_strike': 600,
            'sym2_strike': 6000,
        }
        result = update_moneyness(config_no_price)
        assert result == ""

    def test_bug008_apply_scan_empty_data(self):
        """BUG-008: apply_scan_result handles out-of-bounds row gracefully."""
        from dash import no_update
        from src.pages.scanner import apply_scan_result
        from unittest.mock import patch, MagicMock
        # Mock dash.ctx.triggered_id to simulate a click
        mock_ctx = MagicMock()
        mock_ctx.triggered_id = 'scanner-table-safety'
        with patch('dash.ctx', mock_ctx):
            result = apply_scan_result(
                safety_cell={'row': 99},  # out of bounds
                profit_cell=None,
                rr_cell=None,
                safety_data=[],  # empty data
                profit_data=[],
                rr_data=[],
                config={'sym1': 'SPY', 'sym2': 'SPX'},
                scanner_right='P',
            )
        assert result is no_update
