---
name: refactor-design
description: Identify and fix remaining architecture issues in the codebase
---

Audit the codebase architecture and fix remaining structural issues. The major refactoring (Streamlit → Dash, business logic extraction, domain models, broker protocol) is complete. This skill handles ongoing architectural hygiene.

Target area (optional): $ARGUMENTS

## Current Architecture (already in place)

```
app.py                              # Dash entry point (~110 lines)
src/
  config.py                         # Business constants
  models.py                         # Dataclasses: Position, ScanResult, Leg, etc.
  pnl.py                            # P&L calculations (pure functions)
  pricing.py                        # Price lookup with liquidity (pure functions)
  position.py                       # Position construction, credit, margin
  scanner_engine.py                 # Pair matching, spread calc, ranking
  normalization.py                  # Price normalization, spread calculation
  data_loader.py                    # CSV loading, validation, caching
  broker/
    protocol.py                     # BrokerProtocol (Python Protocol class)
    ibkr_client.py                  # IB implementation
    mock_broker.py                  # Mock for testing
  pages/
    sidebar.py                      # Shared sidebar config
    historical.py                   # Tab 1: position + P&L analysis
    live_trading.py                 # Tab 2: IB connection + live positions
    price_overlay.py                # Tab 3: normalized price overlay
    divergence.py                   # Tab 4: underlying divergence
    scanner.py                      # Tab 5: strike scanner
```

## What to Check

Before planning changes, read `CLAUDE.md` and `docs/architecture/system-overview.mmd`.

### Separation of Concerns
- [ ] Callbacks in `src/pages/*.py` should only: unpack inputs → call `src/` functions → format output
- [ ] No business logic (calculations, data filtering, decision logic) should live in page files
- [ ] `src/` modules should have zero imports from `dash`
- [ ] Check for business logic that crept into callbacks during development

### Domain Models
- [ ] Are all ad-hoc dicts replaced with dataclasses from `src/models.py`?
- [ ] Are function signatures using domain types instead of raw dicts/DataFrames where practical?
- [ ] Check `config-store` data — it passes a raw dict through `dcc.Store`. Should it use a typed config?

### Configuration
- [ ] Are all magic numbers centralized in `src/config.py`?
- [ ] Search for hardcoded thresholds, ratios, and ports across all files
- [ ] `tests/test_architecture_sync.py::TestBusinessConstants` should catch drift — verify it's up to date

### Testability
- [ ] Can each `src/` module be tested independently (no file I/O, no network, no UI)?
- [ ] Are Dash callbacks testable by calling the function directly with mock data?
- [ ] Does `MockBroker` cover all `BrokerProtocol` methods?
- [ ] Missing test files: `tests/test_position.py`, `tests/test_scanner_engine.py`, `tests/test_callbacks.py`

### Module Boundaries
- [ ] Is `data_loader.py` doing too much? (CSV loading + date listing + symbol resolution + caching)
- [ ] Is `scanner_engine.py` coupled to DataFrame internals, or does it work with domain types?
- [ ] Does `collect_market_data.py` share any logic with the Dash app that should be in `src/`?

## Design Principles

1. **Separate UI from Logic** — callbacks are thin wrappers, business logic is in `src/`
2. **Domain Models over Dicts** — use dataclasses for structured data flowing between modules
3. **Configuration in One Place** — `src/config.py` is the single source of truth for constants
4. **Protocol-Based Abstraction** — `BrokerProtocol` for testable broker integration
5. **Practical Extensibility** — no frameworks, no plugin systems, no abstract factories
   - Adding a new tab = `src/pages/new_tab.py` + register in `app.py`
   - Adding a new broker = implement `BrokerProtocol`
   - Adding a new metric = function in `src/pnl.py`, call from callback

## Execution Steps

1. Run `python -m pytest tests/ -v` to establish baseline
2. Audit against the checklist above
3. For each issue found:
   - Describe the problem and proposed fix
   - Make the change
   - Verify tests still pass
4. If new tests are needed, write them
5. Run `/update-architecture` to update diagrams
6. Commit: "refactor: [description of changes]"

## Important Rules

- **Never change business logic during refactoring** — same inputs must produce same outputs
- **Run tests after every change** — `python -m pytest tests/ -v`
- **If `$ARGUMENTS` specifies a target area**, only audit that area
- **Don't refactor and add features simultaneously**
- **Don't over-engineer** — if a pattern wouldn't make sense for 1-3 people, skip it
