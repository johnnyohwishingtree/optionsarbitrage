---
name: cleanup
description: Find and remove unused, temporary, or accidentally committed files
---

Scan the repo for files that shouldn't be there — temporary files, debug artifacts, accidentally committed data, dead code, and orphaned files.

## What to Look For

### Temporary / debug files
- `*.tmp`, `*.bak`, `*.swp`, `*.swo`, `*~`
- `*.pyc`, `__pycache__/` directories (should be gitignored)
- `untitled*`, `test_*scratch*`, `*_old.*`, `*_backup.*`, `*_copy.*`
- `Untitled*.ipynb`, `*.ipynb_checkpoints/`
- Files with names like `temp`, `tmp`, `debug`, `scratch`, `draft`, `wip`

### Accidentally committed data
- `.env` files (secrets — should NEVER be committed)
- `*.db`, `*.sqlite` files that are tracked (should be gitignored)
- Large CSV files in tracked directories (data/ files should generally be gitignored)
- `*.key`, `*.pem`, `*.cert` files
- `node_modules/`, `venv/`, `.venv/` if tracked

### Dead / orphaned code
- Python files that are not imported by anything and not in `tests/` or `scripts/`
- Empty `__init__.py` files in directories with no other Python files
- Commented-out code blocks longer than 10 lines (flag but don't auto-remove)

### Build / IDE artifacts
- `.vscode/`, `.idea/` if tracked (should be gitignored)
- `dist/`, `build/`, `*.egg-info/` if tracked
- `*.DS_Store`, `Thumbs.db` if tracked

### Duplicate or superseded files
- Files with very similar names (e.g., `strategy.py` and `strategy_v2.py`)
- Old config files that have been replaced

## Steps

1. Run `git ls-files` to list all tracked files.
2. Run a broad search for suspicious patterns:
   - Files matching temp/debug naming patterns
   - Files matching secret/credential patterns
   - Files that are large (> 1MB) and tracked
   - Files outside the expected directory structure
3. For each suspicious file, check:
   - Is it imported or referenced by any other file? (grep for the filename/module name)
   - Is it in `.gitignore` already? If so, it was accidentally committed.
   - Was it recently modified, or is it stale?
4. Present findings in categories:
   - **Safe to delete** — clearly temporary/dead files, with justification
   - **Probably safe** — likely unnecessary but need confirmation
   - **Needs review** — could be important, ask before touching
5. For "safe to delete" files, ask for confirmation, then:
   - `git rm <file>` for tracked files
   - `rm <file>` for untracked files
   - Update `.gitignore` if a pattern should be excluded going forward
6. After cleanup:
   - Run `python -m pytest tests/ -v` to verify nothing broke
   - Run `python3 scripts/gen_arch_deps.py` to update dependency graph
   - Show summary: files removed, .gitignore additions, bytes recovered
