#!/usr/bin/env python3
"""Auto-generate docs/architecture/module-dependencies.mmd from actual Python imports.

Uses ast (stdlib) to parse imports — no external dependencies required.
Run manually or via the pre-commit hook.
"""

import ast
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files to scan and their node IDs
MODULE_MAP = {
    "collect_market_data.py": "MOD_collect",
    "app.py": "MOD_app",
    "src/broker/ibkr_client.py": "MOD_ibkrClient",
    "src/broker/protocol.py": "MOD_protocol",
    "src/broker/mock_broker.py": "MOD_mock_broker",
    "src/pnl.py": "MOD_pnl",
    "src/pricing.py": "MOD_pricing",
    "src/config.py": "MOD_config",
    "src/models.py": "MOD_models",
    "src/data_loader.py": "MOD_data_loader",
    "src/position.py": "MOD_position",
    "src/scanner_engine.py": "MOD_scanner_engine",
    "src/normalization.py": "MOD_normalization",
    "src/pages/components.py": "MOD_components",
    "src/pages/sidebar.py": "MOD_sidebar",
    "src/pages/historical.py": "MOD_historical",
    "src/pages/live_trading.py": "MOD_live_trading",
    "src/pages/price_overlay.py": "MOD_price_overlay",
    "src/pages/divergence.py": "MOD_divergence",
    "src/pages/scanner.py": "MOD_scanner",
}

# Test files
TEST_MAP = {
    "tests/test_pnl_calculations.py": "TEST_pnl",
    "tests/test_worst_case_consistency.py": "TEST_consistency",
    "tests/test_worst_case_lockstep.py": "TEST_lockstep",
    "tests/test_architecture_sync.py": "TEST_arch_sync",
    "tests/test_dash_callbacks.py": "TEST_dash_callbacks",
    "tests/test_data_collection.py": "TEST_data_collection",
    "tests/test_data_loader.py": "TEST_data_loader",
    "tests/test_integration.py": "TEST_integration",
    "tests/test_normalization.py": "TEST_normalization",
    "tests/test_position.py": "TEST_position",
    "tests/test_pricing.py": "TEST_pricing",
    "tests/test_scanner_engine.py": "TEST_scanner_engine",
}

# External libraries we care about (skip stdlib)
KNOWN_LIBS = {
    "ib_insync": "LIB_ibAsync",
    "ib_async": "LIB_ibAsync",
    "pandas": "LIB_pandas",
    "numpy": "LIB_numpy",
    "dash": "LIB_dash",
    "plotly": "LIB_plotly",
    "asyncio": "LIB_asyncio",
}

# Labels for library nodes
LIB_LABELS = {
    "LIB_ibAsync": "ib_async / ib_insync",
    "LIB_pandas": "pandas",
    "LIB_numpy": "numpy",
    "LIB_dash": "dash",
    "LIB_plotly": "plotly",
    "LIB_asyncio": "asyncio",
}

# Local import patterns that map to our modules
LOCAL_IMPORT_MAP = {
    "src.broker.ibkr_client": "MOD_ibkrClient",
    "src.broker.protocol": "MOD_protocol",
    "src.broker.mock_broker": "MOD_mock_broker",
    "src.broker": "MOD_ibkrClient",
    "src.pnl": "MOD_pnl",
    "src.pricing": "MOD_pricing",
    "src.config": "MOD_config",
    "src.models": "MOD_models",
    "src.data_loader": "MOD_data_loader",
    "src.position": "MOD_position",
    "src.scanner_engine": "MOD_scanner_engine",
    "src.normalization": "MOD_normalization",
    "src.pages.components": "MOD_components",
    "src.pages.sidebar": "MOD_sidebar",
    "src.pages.historical": "MOD_historical",
    "src.pages.live_trading": "MOD_live_trading",
    "src.pages.price_overlay": "MOD_price_overlay",
    "src.pages.divergence": "MOD_divergence",
    "src.pages.scanner": "MOD_scanner",
}


def extract_imports(filepath: Path) -> set[str]:
    """Parse a Python file and return set of top-level module names imported."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
                imports.add(alias.name)  # full dotted name too
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
                imports.add(node.module)  # full dotted name
    return imports


def resolve_import(raw_import: str, source_file: str) -> str | None:
    """Map a raw import string to a node ID, or None if we don't care about it."""
    # Check local imports first
    for pattern, node_id in LOCAL_IMPORT_MAP.items():
        if raw_import == pattern or raw_import.startswith(pattern + "."):
            return node_id

    # Check known libraries
    top_level = raw_import.split(".")[0]
    if top_level in KNOWN_LIBS:
        return KNOWN_LIBS[top_level]

    return None


def build_graph() -> str:
    """Scan all Python files and build the Mermaid dependency graph."""
    edges: list[tuple[str, str, bool]] = []  # (source_node, target_node, is_test)
    used_modules: set[str] = set()
    used_libs: set[str] = set()

    # Scan main modules
    for relpath, node_id in MODULE_MAP.items():
        filepath = ROOT / relpath
        if not filepath.exists():
            continue

        used_modules.add(node_id)
        raw_imports = extract_imports(filepath)

        for raw in raw_imports:
            target = resolve_import(raw, relpath)
            if target and target != node_id:
                edges.append((node_id, target, False))
                if target.startswith("LIB_"):
                    used_libs.add(target)
                else:
                    used_modules.add(target)

    # Scan test files
    for relpath, node_id in TEST_MAP.items():
        filepath = ROOT / relpath
        if not filepath.exists():
            continue

        used_modules.add(node_id)
        raw_imports = extract_imports(filepath)

        targets = set()
        for raw in raw_imports:
            target = resolve_import(raw, relpath)
            if target and target != node_id:
                targets.add(target)

        for target in targets:
            edges.append((node_id, target, True))
            if target.startswith("LIB_"):
                used_libs.add(target)
            else:
                used_modules.add(target)

    # Deduplicate edges
    seen = set()
    unique_edges = []
    for src, tgt, is_test in edges:
        key = (src, tgt)
        if key not in seen:
            seen.add(key)
            unique_edges.append((src, tgt, is_test))

    return render_mermaid(used_modules, used_libs, unique_edges)


def render_mermaid(
    used_modules: set[str],
    used_libs: set[str],
    edges: list[tuple[str, str, bool]],
) -> str:
    today = date.today().isoformat()
    lines = [
        f"%% Module Dependencies — Import/dependency graph",
        f"%% Auto-generated by scripts/gen_arch_deps.py on {today}",
        f"%% Do not edit manually — changes will be overwritten on next commit",
        "",
        "graph LR",
    ]

    # Module nodes
    lines.append("    %% Modules")
    module_labels = {v: k for k, v in MODULE_MAP.items()}
    test_labels = {v: k for k, v in TEST_MAP.items()}

    for node_id in sorted(used_modules):
        if node_id in module_labels:
            lines.append(f'    {node_id}["{module_labels[node_id]}"]:::module')
        elif node_id in test_labels:
            lines.append(f'    {node_id}["{test_labels[node_id]}"]:::function')

    # Library nodes
    lines.append("")
    lines.append("    %% External libraries")
    for lib_id in sorted(used_libs):
        label = LIB_LABELS.get(lib_id, lib_id)
        lines.append(f'    {lib_id}["{label}"]:::external')

    # Edges
    lines.append("")
    lines.append("    %% Module → Module imports")
    for src, tgt, is_test in sorted(edges):
        if not tgt.startswith("LIB_") and not is_test:
            lines.append(f'    {src} -->|"imports"| {tgt}')

    lines.append("")
    lines.append("    %% Module → Library imports")
    for src, tgt, is_test in sorted(edges):
        if tgt.startswith("LIB_") and not is_test:
            lines.append(f"    {src} --> {tgt}")

    lines.append("")
    lines.append("    %% Test → Module dependencies (dashed)")
    for src, tgt, is_test in sorted(edges):
        if is_test:
            lines.append(f'    {src} -.->|"imports"| {tgt}')

    # Style definitions
    lines.append("")
    lines.append("    %% Style definitions")
    lines.append("    classDef external  fill:#f9d0d0,stroke:#c0392b,color:#333")
    lines.append("    classDef module    fill:#d0e0f9,stroke:#2471a3,color:#333")
    lines.append("    classDef function  fill:#d0f9d0,stroke:#27ae60,color:#333")
    lines.append("    classDef data      fill:#f9e4d0,stroke:#e67e22,color:#333")
    lines.append("    classDef tab       fill:#e0d0f9,stroke:#8e44ad,color:#333")

    return "\n".join(lines) + "\n"


def main():
    output_path = ROOT / "docs" / "architecture" / "module-dependencies.mmd"
    mermaid = build_graph()

    # Check if content changed
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        # Compare ignoring the date line
        existing_lines = [l for l in existing.splitlines() if not l.startswith("%% Auto-generated")]
        new_lines = [l for l in mermaid.splitlines() if not l.startswith("%% Auto-generated")]
        if existing_lines == new_lines:
            print("module-dependencies.mmd: no changes detected")
            return False

    output_path.write_text(mermaid, encoding="utf-8")
    print(f"module-dependencies.mmd: updated ({output_path})")
    return True


if __name__ == "__main__":
    changed = main()
    sys.exit(0)
