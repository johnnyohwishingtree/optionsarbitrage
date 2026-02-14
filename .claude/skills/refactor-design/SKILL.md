---
name: refactor-design
description: Design and execute a refactoring to make the codebase extensible and testable
---

Design a refactoring plan for the options arbitrage codebase, then execute it incrementally. The goal is a system an expert solution architect would approve: clear separation of concerns, testable business logic, practical extensibility, and a Dash (Plotly) frontend replacing Streamlit.

Target area (optional): $ARGUMENTS

## Current State (read this first)

Before planning, read `CLAUDE.md` and `docs/architecture/system-overview.mmd` for context. The key issues:

1. **`strategy_calculator_simple.py` (~3400 lines)** — a Streamlit monolith mixing:
   - UI rendering (tabs, widgets, layouts)
   - Data loading and caching (CSV reads, DataFrame manipulation)
   - Position construction logic (direction, quantities, credits)
   - Scanner logic (pair matching, spread calculation, ranking)
   - Price overlay analysis (normalization, gap finding)
   - Divergence charting
   - Live trading tab (IB connection, position display)
   - Session state management
   - Almost zero function definitions — mostly top-level procedural script

2. **`collect_market_data.py` (~660 lines)** — mixes CLI parsing, IB connection, data fetching, CSV I/O

3. **Already extracted (good):** `src/pnl.py`, `src/pricing.py`, `src/broker/ibkr_client.py`

4. **No interfaces** — `IBKRClient` is concrete, can't mock for testing

5. **No domain models** — positions, strategies, scan results are ad-hoc dicts and DataFrames

6. **Business constants scattered** — hardcoded in multiple files

## Why Dash over Streamlit

Streamlit's rerun model (entire script re-executes on every widget interaction) is the root cause of the monolith. It prevents clean separation of concerns.

**Dash's callback model solves this by design:**
- Each interaction is an explicit callback: `@app.callback(Output(...), Input(...))` → pure function → return value
- Callbacks are individually testable — they're just functions with typed inputs and outputs
- Layout is declarative (like React components), separate from logic
- No session state hacks — Dash manages state properly
- Already using Plotly for all charts — zero visualization migration cost
- Still Python-only — no JS build chain needed

## Target Architecture

```
app.py                              # Dash app entry point (~50 lines)
                                    # Creates app, registers pages, runs server

src/
  config.py                         # All business constants in one place
  models.py                         # Dataclasses: Position, ScanResult, PriceQuote, StrategyConfig

  # Pure business logic (no UI imports)
  pnl.py                            # P&L calculations (exists)
  pricing.py                        # Price lookup with liquidity (exists)
  position.py                       # Position construction, credit calc, margin
  scanner_engine.py                 # Pair matching, spread calc, ranking
  normalization.py                  # Price normalization, spread calculation
  data_loader.py                    # CSV loading, validation, caching

  # Broker abstraction
  broker/
    protocol.py                     # BrokerProtocol (Python Protocol class)
    ibkr_client.py                  # IB implementation (exists)
    mock_broker.py                  # Mock for testing

  # Dash UI layer (thin — calls src/ functions)
  pages/
    __init__.py
    sidebar.py                      # Shared sidebar config component
    historical.py                   # Tab 1: layout + callbacks
    live_trading.py                 # Tab 2: layout + callbacks
    price_overlay.py                # Tab 3: layout + callbacks
    divergence.py                   # Tab 4: layout + callbacks
    scanner.py                      # Tab 5: layout + callbacks

collect_market_data.py              # Data collection CLI (refactored)
tests/
  test_pnl_calculations.py
  test_worst_case_consistency.py
  test_worst_case_lockstep.py
  test_architecture_sync.py
  test_position.py                  # NEW: position construction
  test_scanner_engine.py            # NEW: scanner logic
  test_data_loader.py               # NEW: data loading
  test_callbacks.py                 # NEW: Dash callbacks with mock data
```

## Design Principles (in priority order)

### 1. Separate UI from Logic (highest priority)
Every callback follows the same pattern:
```python
# src/pages/historical.py
@app.callback(Output('pnl-display', 'children'), Input('entry-time', 'value'), ...)
def update_pnl(entry_time, symbol_pair, ...):
    config = StrategyConfig(...)
    prices = get_option_price_with_liquidity(df_options, df_bidask, ...)
    position = build_position(config, prices)
    best, worst = calculate_best_worst_case_with_basis_drift(...)
    return render_pnl_card(position, best, worst)  # returns Dash components
```
The business logic functions (`build_position`, `calculate_best_worst_case_with_basis_drift`) are imported from `src/` and have zero knowledge of Dash.

### 2. Domain Models over Dicts
```python
# src/models.py
@dataclass
class StrategyConfig:
    sym1: str                    # e.g. 'SPY'
    sym2: str                    # e.g. 'SPX'
    qty_ratio: int               # 10 for SPX, 1 for XSP
    strike_step: int             # 5 for SPX, 1 for SPY/XSP
    strategy_type: str           # 'full', 'calls_only', 'puts_only'
    call_direction: str
    put_direction: str

@dataclass
class PriceQuote:
    price: float
    source: str                  # 'midpoint' or 'trade'
    volume: int
    bid: float | None
    ask: float | None
    spread_pct: float | None
    is_stale: bool
    liquidity_warning: str | None

@dataclass
class Leg:
    symbol: str
    strike: float
    right: str                   # 'C' or 'P'
    action: str                  # 'BUY' or 'SELL'
    quantity: int
    entry_price: float

@dataclass
class Position:
    legs: list[Leg]
    call_credit: float
    put_credit: float
    total_credit: float
    estimated_margin: float

@dataclass
class ScanResult:
    sym1_strike: float
    sym2_strike: float
    max_spread: float
    max_spread_time: str
    credit: float
    best_worst_pnl: float
    best_worst_time: str
    direction: str
```

### 3. Configuration in One Place
```python
# src/config.py
QTY_RATIO_SPX = 10
QTY_RATIO_DEFAULT = 1
STRIKE_STEP_SPX = 5
STRIKE_STEP_DEFAULT = 1
MONEYNESS_WARN_THRESHOLD = 0.05      # percent
SCANNER_PAIR_TOLERANCE = 0.005        # 0.5%
WIDE_SPREAD_THRESHOLD = 20            # percent
MARGIN_RATE = 0.20                    # 20% of short notional
GRID_PRICE_POINTS = 50
GRID_PRICE_RANGE_PCT = 0.05           # ±5%
GRID_BASIS_DRIFT_PCT = 0.001          # ±0.10%
DEFAULT_MIN_VOLUME = 10
IB_HOST = '127.0.0.1'
IB_PORT = 4002
```

### 4. Protocol-Based Broker Abstraction
```python
# src/broker/protocol.py
from typing import Protocol

class BrokerProtocol(Protocol):
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def get_current_price(self, symbol: str) -> float | None: ...
    def get_account_summary(self) -> dict: ...
    def get_positions(self) -> list[dict]: ...
    def close_position(self, contract, quantity: int): ...
```
`IBKRClient` already satisfies this interface. `MockBroker` returns canned data for tests.

### 5. Testable Scanner Engine
```python
# src/scanner_engine.py
def match_strike_pairs(
    sym1_strikes: list[float],
    sym2_strikes: list[float],
    open_ratio: float,
    tolerance: float = SCANNER_PAIR_TOLERANCE,
) -> list[tuple[float, float]]: ...

def calculate_spreads(
    df_options: pd.DataFrame,
    df_bidask: pd.DataFrame | None,
    sym1: str, sym2: str,
    sym1_strike: float, sym2_strike: float,
    open_ratio: float,
    min_volume: int = DEFAULT_MIN_VOLUME,
) -> pd.DataFrame: ...

def scan_all_pairs(
    df_options: pd.DataFrame,
    df_bidask: pd.DataFrame | None,
    config: StrategyConfig,
    entry_prices: dict,
    min_volume: int = DEFAULT_MIN_VOLUME,
    progress_callback: Callable | None = None,  # optional, for UI progress bars
) -> list[ScanResult]: ...
```
No Dash imports. No Streamlit imports. Pure data in, pure data out.

### 6. Dash Page Structure
Each page module follows this pattern:
```python
# src/pages/scanner.py
from dash import html, dcc, dash_table, callback, Input, Output, State
from src.scanner_engine import scan_all_pairs, match_strike_pairs
from src.models import StrategyConfig, ScanResult

def layout():
    """Return the layout for this page/tab."""
    return html.Div([
        html.H3("Strike Scanner"),
        # ... Dash components ...
    ])

@callback(Output('scan-results', 'data'), Input('scan-button', 'n_clicks'), ...)
def run_scan(n_clicks, option_type, min_volume, ...):
    """Callback: runs scanner and returns results."""
    config = StrategyConfig(...)
    results = scan_all_pairs(df_options, df_bidask, config, ...)
    return [asdict(r) for r in results]
```

### 7. Practical Extensibility (don't over-engineer)
- **DO**: Protocols, dataclasses, pure functions, explicit callbacks
- **DON'T**: Dependency injection frameworks, plugin systems, abstract factories, ORMs
- **DON'T**: Deep class hierarchies, metaclasses, decorators-on-decorators
- **Rule**: If a pattern wouldn't make sense for a team of 1-3 people, skip it
- **Adding a new tab** = create `src/pages/new_tab.py` with `layout()` + callbacks, register in `app.py`
- **Adding a new broker** = implement `BrokerProtocol` in `src/broker/new_broker.py`
- **Adding a new strategy metric** = add function to `src/pnl.py`, call from relevant callback

## Execution Plan

Each phase is independently deployable and testable.

### Phase 1: Foundation (no behavior change, no UI change)
1. Create `src/config.py` — centralize all business constants
2. Create `src/models.py` — dataclasses for Position, ScanResult, PriceQuote, StrategyConfig, Leg
3. Create `src/broker/protocol.py` — BrokerProtocol
4. Create `src/broker/mock_broker.py` — MockBroker for tests
5. Update `src/pnl.py` and `src/pricing.py` to import constants from config
6. Update `tests/test_architecture_sync.py` to verify constants from config.py
7. All existing tests pass — no behavior change
8. Commit: "refactor: add config, models, broker protocol"

### Phase 2: Extract Business Logic (no UI change yet)
9. Create `src/data_loader.py` — extract CSV loading, date listing, validation
10. Create `src/position.py` — extract position construction, credit calc, margin
11. Create `src/scanner_engine.py` — extract pair matching, spread calc, ranking
12. Create `src/normalization.py` — extract price normalization
13. Write `tests/test_position.py`, `tests/test_scanner_engine.py`, `tests/test_data_loader.py`
14. Streamlit app still works — it now imports from these modules
15. Commit: "refactor: extract business logic to src/"

### Phase 3: Migrate to Dash
16. `pip install dash` and add to requirements.txt
17. Create `app.py` — Dash app with tab navigation
18. Create `src/pages/sidebar.py` — shared config panel
19. Migrate tabs one at a time (historical first, it's the most important):
    - `src/pages/historical.py` — layout + callbacks calling `src/position.py`, `src/pnl.py`
    - `src/pages/live_trading.py` — layout + callbacks calling `BrokerProtocol`
    - `src/pages/price_overlay.py` — layout + callbacks calling `src/normalization.py`
    - `src/pages/divergence.py` — layout + callbacks
    - `src/pages/scanner.py` — layout + callbacks calling `src/scanner_engine.py`
20. Test each tab visually: `python app.py` → open browser
21. Once all tabs work in Dash, archive `strategy_calculator_simple.py`
22. Commit: "refactor: migrate UI from Streamlit to Dash"

### Phase 4: Polish
23. Write `tests/test_callbacks.py` — test Dash callbacks with mock data (no browser needed)
24. Add `MockBroker` tests for live trading logic
25. Update all architecture diagrams: `/update-architecture`
26. Update `CLAUDE.md` — new project structure, run commands (`python app.py` instead of `streamlit run`)
27. Update `tests/test_architecture_sync.py` — new modules, new node IDs
28. Verify all tests pass
29. Commit: "refactor: add tests, update architecture docs"

## Important Rules

- **Never change business logic during UI migration** — same inputs must produce same outputs
- **Run tests after every step** — `python -m pytest tests/ -v`
- **Commit after each phase** — so you can revert if something breaks
- **Keep the old Streamlit app working until Dash is fully migrated** — both can coexist during transition
- **Don't refactor and add features simultaneously** — pure refactor first, features after
- **If `$ARGUMENTS` specifies a target area**, only refactor that area (e.g., "scanner" = extract scanner engine + its Dash page only)
- **Dash callbacks must never contain business logic** — they assemble inputs, call a `src/` function, format the output. That's it.
