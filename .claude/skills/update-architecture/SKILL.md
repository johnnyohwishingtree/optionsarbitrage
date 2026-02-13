---
name: update-architecture
description: Update architecture diagrams after code changes
---

Update architecture diagrams to reflect recent code changes.

Steps:
1. Run `git diff HEAD~1` (or `git diff --cached` if there are staged changes) to identify what files changed and how.
2. Read `docs/architecture/README.md` for diagram conventions (node ID prefixes, style classes, edge semantics).
3. Map each changed file to the diagrams it affects:
   - `collect_market_data.py` -> `system-overview.mmd`, `module-dependencies.mmd`, `flow-data-collection.mmd`
   - `strategy_calculator_simple.py` -> `system-overview.mmd`, `module-dependencies.mmd`, `flow-strategy-analysis.mmd`, `flow-strike-scanner.mmd`, `flow-price-discovery.mmd`, `flow-live-trading.mmd`
   - `src/broker/ibkr_client.py` -> `system-overview.mmd`, `module-dependencies.mmd`, `flow-live-trading.mmd`
   - `data/*.csv` schema changes -> `data-model.mmd`
   - New Python files -> `module-dependencies.mmd`, possibly `system-overview.mmd`
   - Test files -> `module-dependencies.mmd` (dashed edges)
4. For each affected diagram, read it and apply changes:
   - **New function/class/module**: Add a node with the correct `PREFIX_name` ID and appropriate style class.
   - **Removed function/class/module**: Remove the node and all connected edges.
   - **Renamed**: Update the node ID and label.
   - **New dependency**: Add an edge with the correct style (solid=runtime, dashed=test, thick=data).
   - **Removed dependency**: Remove the edge.
   - **New Streamlit tab**: Add to the StreamlitTabs subgraph in `system-overview.mmd`.
5. Update the `%% Updated:` timestamp in the header of each modified `.mmd` file to today's date.
6. If a major new feature was added (new module, new tab, new data pipeline), create a new `flow-*.mmd` diagram following the conventions, and add it to the diagram index in `docs/architecture/README.md`.
7. Show a summary of what changed:
   - Which diagrams were updated
   - Nodes added/removed/renamed
   - Edges added/removed
   - Any new diagrams created
