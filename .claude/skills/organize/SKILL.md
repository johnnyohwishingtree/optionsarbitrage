---
name: organize
description: Reorganize file structure so it aligns with the architecture diagrams
---

Audit and reorganize the project file structure so it's clean, logical, and matches the architecture diagrams.

## Target Structure

The canonical structure (from CLAUDE.md and system-overview.mmd):

```
collect_market_data.py            # Data collection CLI
strategy_calculator_simple.py     # Streamlit dashboard (5 tabs)
src/
  __init__.py
  pnl.py                          # P&L calculations (pure functions)
  pricing.py                      # Price discovery (pure functions)
  broker/
    __init__.py
    ibkr_client.py                # IB API wrapper
tests/
  test_pnl_calculations.py
  test_worst_case_consistency.py
  test_worst_case_lockstep.py
  test_architecture_sync.py
data/                             # CSV files (gitignored except structure)
  underlying_prices_*.csv
  options_data_*.csv
  options_bidask_*.csv
docs/
  architecture/                   # Mermaid diagrams + viewer
scripts/
  gen_arch_deps.py                # Auto-generates module-dependencies.mmd
.claude/
  skills/                         # Claude Code slash commands
CLAUDE.md
requirements.txt
.env.example
README.md
.gitignore
```

## Steps

1. Run `git ls-files` to see all tracked files.
2. Run `ls -R` (excluding `data/`, `venv/`, `__pycache__/`, `.git/`, `node_modules/`) to see all files on disk.
3. Compare against the target structure above. Identify:

   **Misplaced files** — files that belong in a different directory:
   - Python modules with reusable functions should be under `src/`
   - Test files should be under `tests/`
   - Scripts/tooling should be under `scripts/`
   - Documentation should be under `docs/`

   **Missing `__init__.py`** — any Python package directory that lacks one

   **Flat files that should be grouped** — if there are multiple related files at the root that belong together

4. For each misplaced file:
   - Move it to the correct location using `git mv`
   - Update all imports that reference it (search with grep)
   - Update `docs/architecture/README.md` node ID table if a module moved
   - Update `tests/test_architecture_sync.py` mappings
   - Update `scripts/gen_arch_deps.py` MODULE_MAP if applicable

5. Run `python -m pytest tests/test_architecture_sync.py -v` to verify nothing broke.

6. Run `python3 scripts/gen_arch_deps.py` to regenerate the dependency graph.

7. Show a summary:
   - Files moved (old path -> new path)
   - Imports updated
   - Diagrams/tests updated
   - Any files that look out of place but you weren't sure about (ask before moving)
