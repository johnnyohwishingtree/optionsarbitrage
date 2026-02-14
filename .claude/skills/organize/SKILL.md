---
name: organize
description: Reorganize file structure so it aligns with the architecture diagrams
---

Audit and reorganize the project file structure so it's clean, logical, and matches the architecture diagrams. This includes ensuring **tests mirror the source structure**.

Target area (optional): $ARGUMENTS

## Target Structure

The canonical structure (from CLAUDE.md and system-overview.mmd):

```
app.py                            # Dash entry point (tab navigation, shared stores)
collect_market_data.py            # Data collection CLI
src/
  __init__.py
  config.py                       # All business constants centralized
  models.py                       # Dataclasses: Position, ScanResult, PriceQuote, etc.
  data_loader.py                  # CSV loading, date listing, symbol filtering
  position.py                     # Position construction, credit calc, margin
  scanner_engine.py               # Strike pair matching, spread calc, ranking
  normalization.py                # Price normalization, divergence calculation
  pnl.py                          # P&L calculations (pure functions)
  pricing.py                      # Price discovery (pure functions)
  broker/
    __init__.py
    protocol.py                   # BrokerProtocol (Python Protocol class)
    ibkr_client.py                # IB Gateway implementation
    mock_broker.py                # Mock for testing
  pages/
    __init__.py
    components.py                 # Shared UI components and style constants
    sidebar.py                    # Shared config panel (date, pair, strikes, direction)
    historical.py                 # Tab 1: position, P&L, scenario analysis
    live_trading.py               # Tab 2: IB positions, settlement P&L
    price_overlay.py              # Tab 3: normalized option price comparison
    divergence.py                 # Tab 4: underlying price divergence
    scanner.py                    # Tab 5: strike pair scanner
tests/
  # ── Unit tests (1:1 mirror of src/) ──
  test_config.py                  # ← src/config.py
  test_models.py                  # ← src/models.py
  test_data_loader.py             # ← src/data_loader.py
  test_position.py                # ← src/position.py
  test_scanner_engine.py          # ← src/scanner_engine.py
  test_normalization.py           # ← src/normalization.py
  test_pnl.py                    # ← src/pnl.py (rename from test_pnl_calculations.py)
  test_pricing.py                 # ← src/pricing.py
  # ── Broker tests (mirror src/broker/) ──
  broker/
    __init__.py
    test_ibkr_client.py           # ← src/broker/ibkr_client.py
    test_mock_broker.py           # ← src/broker/mock_broker.py
  # ── Page/callback tests (mirror src/pages/) ──
  pages/
    __init__.py
    test_sidebar.py               # ← src/pages/sidebar.py
    test_historical.py            # ← src/pages/historical.py
    test_live_trading.py          # ← src/pages/live_trading.py
    test_price_overlay.py         # ← src/pages/price_overlay.py
    test_divergence.py            # ← src/pages/divergence.py
    test_scanner.py               # ← src/pages/scanner.py
    test_components.py            # ← src/pages/components.py
  # ── Cross-cutting tests (no single source file) ──
  test_collect_market_data.py     # ← collect_market_data.py (rename from test_data_collection.py)
  test_app.py                     # ← app.py (rename from test_integration.py)
  test_architecture_sync.py       # meta: diagram ↔ code sync
  test_worst_case_consistency.py  # cross-cutting: price consistency across views
  test_worst_case_lockstep.py     # cross-cutting: lockstep scenario validation
data/
  underlying_prices_{date}.csv
  options_data_{date}.csv
  options_bidask_{date}.csv
docs/
  architecture/                   # Mermaid diagrams + viewer
scripts/
  gen_arch_deps.py                # Auto-generates module-dependencies.mmd
.claude/
  skills/                         # Claude Code slash commands
.github/
  workflows/
    test.yml                      # Run tests on push/PR
    collect-data.yml              # Daily data collection
    collect-underlying.yml        # Underlying price collection
CLAUDE.md
requirements.txt
.env.example
README.md
.gitignore
```

## Test Naming Convention

**Rule: every source file gets a test file with a matching name.**

| Source file | Test file | Notes |
|---|---|---|
| `src/pnl.py` | `tests/test_pnl.py` | Name matches exactly |
| `src/broker/ibkr_client.py` | `tests/broker/test_ibkr_client.py` | Subdirectory mirrors source |
| `src/pages/scanner.py` | `tests/pages/test_scanner.py` | Subdirectory mirrors source |
| `collect_market_data.py` | `tests/test_collect_market_data.py` | Root-level source → root-level test |
| `app.py` | `tests/test_app.py` | Root-level source → root-level test |

**Cross-cutting tests** (span multiple modules) go in `tests/` root with descriptive names:
- `test_worst_case_consistency.py` — validates consistency across views
- `test_worst_case_lockstep.py` — validates lockstep scenarios
- `test_architecture_sync.py` — validates diagrams match code

**What NOT to do:**
- `test_pnl_calculations.py` — should be `test_pnl.py` (match the module name)
- `test_data_collection.py` — should be `test_collect_market_data.py` (match the file name)
- `test_integration.py` — should be `test_app.py` (match what it's actually testing)
- `test_dash_callbacks.py` — should be split into `tests/pages/test_sidebar.py`, `test_scanner.py`, etc.

## Steps

1. Run `git ls-files` to see all tracked files.
2. Run `ls -R` (excluding `data/`, `venv/`, `__pycache__/`, `.git/`, `node_modules/`) to see all files on disk.
3. Compare against the target structure above. Identify:

   **Misplaced source files** — files that belong in a different directory:
   - Python modules with reusable functions should be under `src/`
   - Test files should be under `tests/`
   - Scripts/tooling should be under `scripts/`
   - Documentation should be under `docs/`

   **Misplaced or misnamed tests:**
   - Every `src/*.py` should have a matching `tests/test_*.py`
   - Every `src/broker/*.py` should have a matching `tests/broker/test_*.py`
   - Every `src/pages/*.py` should have a matching `tests/pages/test_*.py`
   - Tests named differently from their source file should be renamed
   - Monolithic test files (like `test_dash_callbacks.py`) should be split

   **Missing `__init__.py`** — any Python package directory that lacks one (including `tests/broker/`, `tests/pages/`)

   **Missing test files** — source files with no corresponding test file

4. For misplaced/misnamed files:
   - Move or rename using `git mv`
   - Update all imports that reference it
   - Update `docs/architecture/README.md` node ID table if a module moved
   - Update `tests/test_architecture_sync.py` mappings
   - Update `scripts/gen_arch_deps.py` MODULE_MAP if applicable

5. For missing test files:
   - Create stub test files with a placeholder class:
     ```python
     """Tests for src/config.py"""
     import pytest
     from src.config import *

     class TestConfig:
         def test_placeholder(self):
             """TODO: Add tests for config constants."""
             pass
     ```
   - This makes the gap visible without blocking CI

6. Run `python -m pytest tests/ -v` to verify nothing broke.
7. Run `python3 scripts/gen_arch_deps.py` to regenerate the dependency graph.

8. Show a summary:
   - Files moved (old path → new path)
   - Files renamed (old name → new name)
   - Test files created (stubs)
   - Missing test coverage (source files with only stub tests)
   - Imports updated
   - Diagrams/tests updated
