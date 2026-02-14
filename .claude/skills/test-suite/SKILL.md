---
name: test-suite
description: Find and fix gaps in the test suite — UI callbacks, business logic, and integration
---

Audit the test suite for gaps, write missing tests, and fix any bugs the tests reveal. Covers three layers: Dash UI (callbacks + layout), business logic (calculations + data), and integration (app boot + data flow).

Target area (optional): $ARGUMENTS

## Test Structure Convention

Tests mirror the source structure. See `/organize` for the full mapping.

```
tests/
  # ── Unit tests (1:1 with src/) ──
  test_config.py                    # ← src/config.py
  test_models.py                    # ← src/models.py
  test_pnl.py                      # ← src/pnl.py
  test_pricing.py                   # ← src/pricing.py
  test_data_loader.py               # ← src/data_loader.py
  test_position.py                  # ← src/position.py
  test_scanner_engine.py            # ← src/scanner_engine.py
  test_normalization.py             # ← src/normalization.py
  broker/
    test_ibkr_client.py             # ← src/broker/ibkr_client.py
    test_mock_broker.py             # ← src/broker/mock_broker.py
  pages/
    test_sidebar.py                 # ← src/pages/sidebar.py
    test_historical.py              # ← src/pages/historical.py
    test_live_trading.py            # ← src/pages/live_trading.py
    test_price_overlay.py           # ← src/pages/price_overlay.py
    test_divergence.py              # ← src/pages/divergence.py
    test_scanner.py                 # ← src/pages/scanner.py
    test_components.py              # ← src/pages/components.py
  # ── Cross-cutting ──
  test_collect_market_data.py       # ← collect_market_data.py
  test_app.py                       # ← app.py
  test_architecture_sync.py         # meta: diagram ↔ code sync
  test_worst_case_consistency.py    # cross-cutting: price consistency
  test_worst_case_lockstep.py       # cross-cutting: lockstep scenarios
```

**Rule:** Every `src/foo.py` gets a `tests/test_foo.py`. Every `src/bar/baz.py` gets a `tests/bar/test_baz.py`. If a test file doesn't exist, create a stub so the gap is visible.

**What's missing:**
- `tests/broker/` directory and broker tests
- `tests/pages/` directory and per-page callback tests
- `test_config.py`, `test_models.py` for foundation modules
- Several existing tests have mismatched names (e.g., `test_pnl_calculations.py` should be `test_pnl.py`)

## Layer 1: Dash UI Tests (`tests/test_dash_callbacks.py`)

These tests validate that the Dash app is correctly wired — no browser needed.

### 1a. Layout ID Validation

Every `Input`, `Output`, and `State` in a callback must reference a component ID that exists somewhere in the layout (either static or dynamically created by another callback).

```python
# tests/test_dash_callbacks.py
"""Tests for Dash callback wiring and layout consistency."""

import pytest
from app import app


class TestLayoutIds:
    """Verify all callback-referenced IDs exist in the layout or are dynamically created."""

    def _get_all_static_ids(self):
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

    def _get_all_callback_ids(self):
        """Extract all IDs referenced by callbacks (Inputs, Outputs, States)."""
        ids = set()
        for callback in app.callback_map.values():
            for dep in callback.get('inputs', []):
                ids.add(dep['id'])
            for dep in callback.get('state', []):
                ids.add(dep['id'])
        for output_id in app.callback_map.keys():
            # output_id format: "component-id.property"
            ids.add(output_id.split('.')[0])
        return ids

    def _get_dynamically_created_ids(self):
        """IDs that are created by callbacks at runtime, not in the static layout.
        These must be documented here so tests know they're expected."""
        return {
            # Created by scanner.py update_ranking_table callback
            'scanner-table-safety',
            'scanner-table-profit',
            'scanner-table-risk_reward',
            # Add more here as dynamic components are created
        }

    def test_no_orphaned_callback_ids(self):
        """Every ID in a callback must be in the layout or known-dynamic."""
        static_ids = self._get_all_static_ids()
        dynamic_ids = self._get_dynamically_created_ids()
        all_known = static_ids | dynamic_ids
        callback_ids = self._get_all_callback_ids()

        missing = callback_ids - all_known
        assert missing == set(), (
            f"Callback references IDs not in layout or known-dynamic: {missing}"
        )
```

### 1b. Dynamic Component Pattern Validation

The scanner page creates tables dynamically with IDs like `scanner-table-{rank_by}`. The `apply_scan_result` callback then references all three as Inputs. This is a known Dash anti-pattern — the callback fires before the components exist.

**The correct fix is one of:**
1. Create all three tables in the initial layout (hidden), not dynamically
2. Use Dash pattern-matching callbacks (`MATCH`, `ALL`) instead of hardcoded IDs
3. Use a single table that re-sorts in place (no dynamic ID creation)

Test for this:
```python
    def test_scanner_tables_exist_at_startup(self):
        """Scanner tables must exist in static layout for apply_scan_result callback."""
        static_ids = self._get_all_static_ids()
        required = {'scanner-table-safety', 'scanner-table-profit', 'scanner-table-risk_reward'}
        missing = required - static_ids
        assert missing == set(), (
            f"Scanner tables missing from static layout: {missing}. "
            f"The apply_scan_result callback references these as Inputs."
        )
```

### 1c. Callback Return Shape Tests

Each callback should return the correct number of outputs. Test by calling the callback function directly with mock data.

```python
class TestCallbackReturnShapes:
    """Verify callbacks return the right number/type of outputs."""

    def test_update_controls_returns_12_values(self):
        """update_controls must return exactly 12 values."""
        from src.pages.sidebar import update_controls
        result = update_controls(None, None)  # Empty inputs
        assert len(result) == 12

    def test_update_config_returns_3_values(self):
        """update_config_store must return (time_display, prices_display, config_dict)."""
        from src.pages.sidebar import update_config_store
        result = update_config_store(None, None, None, None, None, None, None)
        assert len(result) == 3

    def test_historical_analysis_returns_div(self):
        """update_historical_analysis returns a Dash Div on empty config."""
        from src.pages.historical import update_historical_analysis
        result = update_historical_analysis({}, 'full')
        from dash import html
        assert isinstance(result, (html.Div, type(None)))
```

### 1d. Page Import Tests

Every page module should import cleanly and define a `layout()` function.

```python
class TestPageImports:
    """Verify all page modules import and have layout()."""

    @pytest.mark.parametrize("module_name", [
        'src.pages.sidebar',
        'src.pages.historical',
        'src.pages.live_trading',
        'src.pages.price_overlay',
        'src.pages.divergence',
        'src.pages.scanner',
    ])
    def test_page_has_layout(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        assert hasattr(mod, 'layout'), f"{module_name} missing layout()"
        assert callable(mod.layout)
```

## Layer 2: Business Logic Tests

### What exists (verify these still pass):
- `test_pnl_calculations.py` — settlement, intrinsic, per-leg P&L
- `test_worst_case_consistency.py` — same price/direction across all views
- `test_worst_case_lockstep.py` — real-data scenario validation
- `test_position.py` — leg construction, credit, margin
- `test_scanner_engine.py` — pair matching, liquidity, ranking
- `test_data_loader.py` — CSV loading, date listing

### What to add:

**`src/pricing.py` tests** — price discovery is critical and untested directly:
```python
# tests/test_pricing.py
class TestGetOptionPriceWithLiquidity:
    def test_prefers_volume_bars(self): ...
    def test_falls_back_to_bidask(self): ...
    def test_returns_none_for_missing(self): ...
    def test_stale_detection(self): ...
    def test_wide_spread_warning(self): ...
```

**`src/normalization.py` tests** — normalization logic:
```python
# tests/test_normalization.py
class TestNormalizeOptionPrices:
    def test_normalization_scales_by_ratio(self): ...
    def test_empty_input(self): ...

class TestCalculateSpread:
    def test_spread_sign(self): ...

class TestCalculateWorstCaseQuick:
    def test_matches_full_grid_search(self): ...
```

**Edge cases across modules:**
- Zero option prices (both symbols)
- Empty DataFrames (no data for a date)
- Missing bidask data (only TRADES available)
- Single time point (only one bar for the day)
- Extremely wide spreads (50%+)

## Layer 3: Integration Tests (`tests/test_integration.py`)

### App Boot
```python
class TestAppBoot:
    def test_app_imports_without_error(self):
        """The app module should import cleanly."""
        import app
        assert app.app is not None

    def test_app_has_layout(self):
        import app
        assert app.app.layout is not None

    def test_all_tabs_registered(self):
        """All 5 tabs should be in the layout."""
        import app
        # Check tab values exist
        ...
```

### Data Flow (requires test data)
```python
class TestDataFlow:
    """End-to-end flow: load data → build position → calculate P&L."""

    @pytest.fixture
    def test_date(self):
        from src.data_loader import list_available_dates
        dates = list_available_dates('data')
        if not dates:
            pytest.skip("No test data available")
        return dates[-1][0]

    def test_historical_flow(self, test_date):
        """Load data, build position, calculate P&L — the full Historical tab flow."""
        from src.data_loader import load_underlying_prices, load_options_data, load_bidask_data, get_symbol_dataframes
        from src.pricing import get_option_price_with_liquidity
        from src.position import determine_leg_setup
        from src.pnl import calculate_best_worst_case_with_basis_drift

        df_underlying = load_underlying_prices(test_date)
        df_options = load_options_data(test_date)
        df_bidask = load_bidask_data(test_date)
        spy_df, spx_df = get_symbol_dataframes(df_underlying, 'SPY', 'SPX')

        if spy_df.empty or spx_df.empty:
            pytest.skip("No SPY/SPX data")

        # This should complete without error — validates the full pipeline
        entry_time = spy_df.iloc[0]['time']
        spy_strike = int(round(spy_df.iloc[0]['close']))
        spx_strike = int(round(spx_df.iloc[0]['close'] / 5) * 5)

        info = get_option_price_with_liquidity(df_options, df_bidask, 'SPY', spy_strike, 'P', entry_time)
        assert info is None or isinstance(info, dict)
```

## Execution Steps

1. **Run existing tests** to establish baseline:
   ```
   python -m pytest tests/ -v
   ```

2. **Create `tests/test_dash_callbacks.py`** with layout ID validation
   - This will immediately catch the `scanner-table-profit` bug

3. **Fix bugs found by tests:**
   - Scanner dynamic table IDs → create all three in static layout
   - Any other wiring issues

4. **Create `tests/test_integration.py`** with app boot and data flow tests

5. **Create `tests/test_pricing.py`** and `tests/test_normalization.py`** for uncovered business logic

6. **Run full suite:**
   ```
   python -m pytest tests/ -v --tb=short
   ```

7. **Report coverage gaps** — list what's still untested

## Known Bugs to Catch

1. **`scanner-table-profit` / `scanner-table-risk_reward` not in layout** — `scanner.py:327-335` references these as callback Inputs but they're created dynamically by `update_ranking_table`. Fix: create all three `DataTable` components in the static layout inside `scanner.py:layout()`, or use a single table that re-sorts.

2. **`suppress_callback_exceptions=True`** in `app.py:15` masks these errors at runtime. Tests should validate regardless of this flag.

## Important Rules

- **Tests must not require a running Dash server** — test callback functions directly, validate layout as data structures
- **Tests must not require IB Gateway** — skip or mock broker calls
- **Tests that need market data should skip gracefully** if `data/` is empty
- **Don't test Plotly chart rendering** — just verify the callback returns a Figure object, not that it looks correct
- **Run `python -m pytest tests/ -v` after every change**
- **If `$ARGUMENTS` specifies a layer**, only audit/write that layer (e.g., "dash" = Layer 1 only, "business" = Layer 2 only)
