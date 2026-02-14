---
name: update-architecture
description: Update architecture diagrams after code changes
---

Update architecture diagrams to reflect recent code changes. This covers BOTH code structure diagrams AND business logic diagrams.

## Context

This is a market-neutral 0DTE options arbitrage system. Diagrams document:
- **Strategy logic**: how positions are constructed, P&L calculated, risk assessed
- **Business constants**: quantity ratios (10:1 SPX, 1:1 XSP), thresholds (20% spread, 0.05% moneyness), grid search params (50 prices × 3 drifts)
- **Code architecture**: modules, dependencies, data flows

## Steps

1. Run `git diff HEAD~1` (or `git diff --cached` if there are staged changes) to identify what files changed and how.
2. Read `docs/architecture/README.md` for diagram conventions (node ID prefixes, style classes, edge semantics).
3. Map each changed file to the diagrams it affects:

   **Code structure diagrams:**
   - `collect_market_data.py` -> `system-overview.mmd`, `flow-data-collection.mmd`
   - `app.py` / `src/pages/*.py` -> `system-overview.mmd`, `flow-strategy-analysis.mmd`, `flow-strike-scanner.mmd`, `flow-live-trading.mmd`, `flow-position-construction.mmd`
   - `src/broker/ibkr_client.py` -> `system-overview.mmd`, `flow-live-trading.mmd`
   - `data/*.csv` schema changes -> `data-model.mmd`
   - New Python files -> `module-dependencies.mmd` (auto-generated), `system-overview.mmd`
   - Test files -> `module-dependencies.mmd`

   **Business logic diagrams:**
   - `src/pnl.py` -> `flow-pnl-settlement.mmd`, `flow-best-worst-case.mmd`
   - `src/pricing.py` -> `flow-price-discovery.mmd`
   - Changes to quantity ratios, thresholds, grid params -> `strategy-overview.mmd`, `flow-position-construction.mmd`, `CLAUDE.md` Business Constants table
   - Changes to scanner ranking/filtering -> `flow-strike-scanner.mmd`

4. For each affected diagram, read it and apply changes:
   - **New function/class/module**: Add a node with the correct `PREFIX_name` ID and appropriate style class.
   - **Removed function/class/module**: Remove the node and all connected edges.
   - **Renamed**: Update the node ID and label.
   - **New dependency**: Add an edge with the correct style (solid=runtime, dashed=test, thick=data).
   - **Removed dependency**: Remove the edge.
   - **Changed business constant**: Update the value in the diagram AND in CLAUDE.md Business Constants table.
   - **Changed P&L formula**: Update `flow-pnl-settlement.mmd` and/or `flow-best-worst-case.mmd`.
   - **New Streamlit tab**: Add to the StreamlitTabs subgraph in `system-overview.mmd`.
5. Update the `%% Updated:` timestamp in the header of each modified `.mmd` file to today's date.
6. If a major new feature was added (new module, new tab, new data pipeline), create a new `flow-*.mmd` diagram following the conventions, and add it to the diagram index in `docs/architecture/README.md` AND the CLAUDE.md diagram tables.
7. Update `tests/test_architecture_sync.py` if new node IDs, modules, functions, or business constants were added.
8. Run `python -m pytest tests/test_architecture_sync.py -v` to verify diagrams are in sync.
9. Show a summary of what changed:
   - Which diagrams were updated
   - Nodes added/removed/renamed
   - Edges added/removed
   - Business constants changed
   - Any new diagrams created
