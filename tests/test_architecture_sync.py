"""Test that architecture diagrams stay in sync with the actual codebase.

Parses .mmd files for node IDs (FN_, CLS_, MOD_, TAB_) and verifies
the referenced code actually exists. Also verifies business constants
in the code match what's documented in diagrams and CLAUDE.md.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ARCH_DIR = ROOT / "docs" / "architecture"

# ── Node ID → code location mapping ──────────────────────────────────
# Mirrors docs/architecture/README.md — if the README changes, update here.

MODULE_NODES = {
    "MOD_collect": "collect_market_data.py",
    "MOD_strategy": "strategy_calculator_simple.py",
    "MOD_ibkrClient": "src/broker/ibkr_client.py",
    "MOD_pnl": "src/pnl.py",
    "MOD_pricing": "src/pricing.py",
}

CLASS_NODES = {
    "CLS_IBKRClient": ("src/broker/ibkr_client.py", "IBKRClient"),
}

FUNCTION_NODES = {
    "FN_collectDailyData": ("collect_market_data.py", "collect_daily_data"),
    "FN_getLastTimestamp": ("collect_market_data.py", "get_last_timestamp"),
    "FN_calcOptionPnl": ("src/pnl.py", "calculate_option_pnl"),
    "FN_calcSettlement": ("src/pnl.py", "calculate_settlement_value"),
    "FN_calcBestWorst": ("src/pnl.py", "calculate_best_worst_case_with_basis_drift"),
    "FN_getPriceWithLiquidity": ("src/pricing.py", "get_option_price_with_liquidity"),
    "FN_getPriceFromDb": ("src/pricing.py", "get_option_price_from_db"),
    "FN_findNearestRow": ("src/pricing.py", "_find_nearest_row"),
}

TAB_NODES = {
    "TAB_historical": "Historical Analysis",
    "TAB_liveTrade": "Live Paper Trading",
    "TAB_priceOverlay": "Price Overlay",
    "TAB_divergence": "Underlying Divergence",
    "TAB_scanner": "Strike Scanner",
}


def _get_ast(filepath: Path) -> ast.Module | None:
    """Parse a Python file into an AST, or None on failure."""
    try:
        return ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except (SyntaxError, FileNotFoundError):
        return None


def _get_defined_names(tree: ast.Module) -> set[str]:
    """Return all top-level function and class names defined in a module."""
    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _extract_node_ids_from_mmd(filepath: Path) -> set[str]:
    """Extract all node IDs that use our prefix convention from a .mmd file."""
    text = filepath.read_text(encoding="utf-8")
    # Match MOD_xxx, CLS_xxx, FN_xxx, TAB_xxx, DATA_xxx, EXT_xxx
    return set(re.findall(r'\b(MOD_\w+|CLS_\w+|FN_\w+|TAB_\w+|DATA_\w+|EXT_\w+)\b', text))


def _get_tab_names_from_code() -> list[str]:
    """Extract the main st.tabs() call labels from strategy_calculator_simple.py."""
    source = (ROOT / "strategy_calculator_simple.py").read_text(encoding="utf-8")
    # Find the main tabs line: st.tabs(["...", "...", ...])
    match = re.search(r'st\.tabs\(\[([^\]]+)\]', source)
    if not match:
        return []
    raw = match.group(1)
    # Extract quoted strings, strip emoji prefixes
    labels = re.findall(r'"([^"]+)"', raw)
    # Remove leading emoji + space (e.g., "📊 Historical Analysis" -> "Historical Analysis")
    cleaned = []
    for label in labels:
        # Strip any non-ASCII prefix characters and whitespace
        text = re.sub(r'^[^\w]+', '', label).strip()
        cleaned.append(text)
    return cleaned


# ── Tests ─────────────────────────────────────────────────────────────

class TestModulesExist:
    """Verify every MOD_ node references a file that exists."""

    @pytest.mark.parametrize("node_id, filepath", MODULE_NODES.items())
    def test_module_file_exists(self, node_id, filepath):
        full_path = ROOT / filepath
        assert full_path.exists(), (
            f"Diagram node {node_id} references {filepath}, but the file does not exist. "
            f"Update docs/architecture/README.md and the .mmd diagrams."
        )


class TestClassesExist:
    """Verify every CLS_ node references a class that exists in the expected file."""

    @pytest.mark.parametrize("node_id, location", CLASS_NODES.items())
    def test_class_exists(self, node_id, location):
        filepath, class_name = location
        tree = _get_ast(ROOT / filepath)
        assert tree is not None, f"Could not parse {filepath}"
        names = _get_defined_names(tree)
        assert class_name in names, (
            f"Diagram node {node_id} references class '{class_name}' in {filepath}, "
            f"but it was not found. Defined names: {sorted(names)}"
        )


class TestFunctionsExist:
    """Verify every FN_ node references a function that exists in the expected file."""

    @pytest.mark.parametrize("node_id, location", FUNCTION_NODES.items())
    def test_function_exists(self, node_id, location):
        filepath, func_name = location
        tree = _get_ast(ROOT / filepath)
        assert tree is not None, f"Could not parse {filepath}"
        # Check all function defs at any nesting level
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.add(node.name)
        assert func_name in found, (
            f"Diagram node {node_id} references function '{func_name}' in {filepath}, "
            f"but it was not found. Did it get renamed or deleted?"
        )


class TestTabsExist:
    """Verify every TAB_ node references a Streamlit tab that exists in the code."""

    def test_tab_names_match(self):
        code_tabs = _get_tab_names_from_code()
        assert len(code_tabs) > 0, "Could not find st.tabs() call in strategy_calculator_simple.py"

        for node_id, expected_label in TAB_NODES.items():
            found = any(expected_label in tab for tab in code_tabs)
            assert found, (
                f"Diagram node {node_id} references tab '{expected_label}', "
                f"but it was not found in st.tabs(). Current tabs: {code_tabs}"
            )

    def test_no_undocumented_tabs(self):
        """Check that all tabs in the code have a corresponding TAB_ node."""
        code_tabs = _get_tab_names_from_code()
        documented_labels = set(TAB_NODES.values())

        for tab in code_tabs:
            found = any(label in tab for label in documented_labels)
            assert found, (
                f"Tab '{tab}' exists in code but has no TAB_ node in the architecture diagrams. "
                f"Add it to docs/architecture/README.md and system-overview.mmd."
            )


class TestDiagramsReferenceValidNodes:
    """Verify that node IDs used in .mmd files are all documented in README."""

    def _all_known_node_ids(self) -> set[str]:
        known = set()
        known.update(MODULE_NODES.keys())
        known.update(CLASS_NODES.keys())
        known.update(FUNCTION_NODES.keys())
        known.update(TAB_NODES.keys())
        # DATA_ and EXT_ nodes are valid but not code-verifiable
        known.update([
            "DATA_underlying", "DATA_optTrades", "DATA_optBidask",
            "EXT_ibGateway", "EXT_browser",
        ])
        return known

    @pytest.mark.parametrize("mmd_file", sorted(ARCH_DIR.glob("*.mmd")))
    def test_node_ids_are_known(self, mmd_file):
        """Every prefixed node ID in a diagram should be in the known set."""
        known = self._all_known_node_ids()
        node_ids = _extract_node_ids_from_mmd(mmd_file)

        # Filter to only IDs that use our convention prefixes
        prefixed = {n for n in node_ids if any(
            n.startswith(p) for p in ("MOD_", "CLS_", "FN_", "TAB_", "DATA_", "EXT_")
        )}

        unknown = prefixed - known
        # Allow auto-generated module-dependencies.mmd to have extra nodes
        # (LIB_ prefixed nodes from gen_arch_deps.py, TEST_ prefixed)
        unknown = {n for n in unknown if not n.startswith(("LIB_", "TEST_"))}

        assert not unknown, (
            f"{mmd_file.name} references unknown node IDs: {sorted(unknown)}. "
            f"Add them to docs/architecture/README.md and tests/test_architecture_sync.py."
        )


class TestDiagramFilesExist:
    """Verify every diagram listed in README.md actually exists."""

    def test_all_indexed_diagrams_exist(self):
        readme = (ARCH_DIR / "README.md").read_text(encoding="utf-8")
        # Extract .mmd filenames from the index table
        filenames = re.findall(r'`([^`]+\.mmd)`', readme)
        assert len(filenames) > 0, "No .mmd files found in README diagram index"

        for fname in filenames:
            path = ARCH_DIR / fname
            assert path.exists(), (
                f"README.md lists {fname} in the diagram index, but the file does not exist."
            )

    def test_no_orphan_diagrams(self):
        """Every .mmd file in the directory should be listed in README."""
        readme = (ARCH_DIR / "README.md").read_text(encoding="utf-8")
        indexed = set(re.findall(r'`([^`]+\.mmd)`', readme))

        for mmd_file in ARCH_DIR.glob("*.mmd"):
            assert mmd_file.name in indexed, (
                f"{mmd_file.name} exists but is not listed in README.md diagram index. "
                f"Add it to the index table."
            )


# ── Business Constants Sync ───────────────────────────────────────────

def _read_source(relpath: str) -> str:
    """Read a source file and return its text."""
    return (ROOT / relpath).read_text(encoding="utf-8")


class TestBusinessConstants:
    """Verify business constants in the code match what diagrams document.

    If someone changes a threshold, ratio, or grid param in the code,
    this test fails until the diagrams/CLAUDE.md are updated too.
    """

    def test_qty_ratio_spx(self):
        """QTY_RATIO = 10 when SYM2 == SPX."""
        source = _read_source("strategy_calculator_simple.py")
        match = re.search(r'QTY_RATIO\s*=\s*10\s+if\s+SYM2\s*==\s*[\'"]SPX[\'"]', source)
        assert match, (
            "Expected QTY_RATIO = 10 for SPX in strategy_calculator_simple.py. "
            "If this changed, update strategy-overview.mmd, flow-position-construction.mmd, "
            "and CLAUDE.md Business Constants table."
        )

    def test_qty_ratio_non_spx(self):
        """QTY_RATIO = 1 for non-SPX pairs (else branch)."""
        source = _read_source("strategy_calculator_simple.py")
        # The pattern: QTY_RATIO = 10 if SYM2 == 'SPX' else 1
        match = re.search(r'QTY_RATIO\s*=\s*10\s+if\s+.*else\s+1', source)
        assert match, (
            "Expected QTY_RATIO else 1 for non-SPX in strategy_calculator_simple.py. "
            "If this changed, update strategy-overview.mmd and CLAUDE.md."
        )

    def test_strike_step_spx(self):
        """SPX uses $5 strike steps."""
        source = _read_source("strategy_calculator_simple.py")
        match = re.search(r'SYM2_STRIKE_STEP\s*=\s*5\s+if\s+SYM2\s*==\s*[\'"]SPX[\'"]', source)
        assert match, (
            "Expected SYM2_STRIKE_STEP = 5 for SPX. "
            "If this changed, update flow-position-construction.mmd and CLAUDE.md."
        )

    def test_wide_spread_threshold(self):
        """Wide spread warning triggers at >20%."""
        source = _read_source("src/pricing.py")
        match = re.search(r'spread_pct.*>\s*20', source)
        assert match, (
            "Expected wide spread threshold of 20% in src/pricing.py. "
            "If this changed, update flow-price-discovery.mmd and CLAUDE.md."
        )

    def test_grid_search_price_points(self):
        """Grid search uses 50 price points."""
        source = _read_source("src/pnl.py")
        match = re.search(r'num_price_points\s*=\s*50', source)
        assert match, (
            "Expected num_price_points = 50 in src/pnl.py. "
            "If this changed, update flow-best-worst-case.mmd, strategy-overview.mmd, "
            "and CLAUDE.md."
        )

    def test_grid_search_price_range(self):
        """Grid search covers ±5% price range."""
        source = _read_source("src/pnl.py")
        match = re.search(r'price_range_pct\s*=\s*0\.05', source)
        assert match, (
            "Expected price_range_pct = 0.05 (±5%) in src/pnl.py. "
            "If this changed, update flow-best-worst-case.mmd and CLAUDE.md."
        )

    def test_grid_search_basis_drift(self):
        """Grid search tests ±0.10% basis drift."""
        source = _read_source("src/pnl.py")
        match = re.search(r'basis_drift_pct\s*=\s*0\.001', source)
        assert match, (
            "Expected basis_drift_pct = 0.001 (±0.10%) in src/pnl.py. "
            "If this changed, update flow-best-worst-case.mmd, strategy-overview.mmd, "
            "and CLAUDE.md."
        )

    def test_basis_drift_levels(self):
        """Grid search uses 3 basis drift levels."""
        source = _read_source("src/pnl.py")
        match = re.search(r'basis_drifts\s*=\s*\[.*1\.0.*\]', source)
        assert match, (
            "Expected 3 basis drift levels in src/pnl.py. "
            "If this changed, update flow-best-worst-case.mmd and CLAUDE.md."
        )

    def test_moneyness_warning_threshold(self):
        """Moneyness mismatch warns at >0.05%."""
        source = _read_source("strategy_calculator_simple.py")
        match = re.search(r'moneyness_diff\s*>\s*0\.05', source)
        assert match, (
            "Expected moneyness warning threshold of 0.05% in strategy_calculator_simple.py. "
            "If this changed, update strategy-overview.mmd and CLAUDE.md."
        )

    def test_scanner_pair_tolerance(self):
        """Scanner matches strike pairs within 0.5% tolerance."""
        source = _read_source("strategy_calculator_simple.py")
        match = re.search(r'<\s*0\.005', source)
        assert match, (
            "Expected scanner pair tolerance of 0.005 (0.5%) in strategy_calculator_simple.py. "
            "If this changed, update flow-strike-scanner.mmd, strategy-overview.mmd, "
            "and CLAUDE.md."
        )

    def test_margin_rate(self):
        """Margin estimate uses 20% of short notional."""
        source = _read_source("strategy_calculator_simple.py")
        match = re.search(r'\*\s*0\.20', source)
        assert match, (
            "Expected 0.20 (20%) margin rate in strategy_calculator_simple.py. "
            "If this changed, update flow-position-construction.mmd and CLAUDE.md."
        )

    def test_settlement_formula_call(self):
        """Call settlement = max(0, price - strike)."""
        source = _read_source("src/pnl.py")
        match = re.search(r'max\(0,\s*underlying_price\s*-\s*strike\)', source)
        assert match, (
            "Expected call settlement formula max(0, underlying_price - strike) in src/pnl.py. "
            "If this changed, update flow-pnl-settlement.mmd."
        )

    def test_settlement_formula_put(self):
        """Put settlement = max(0, strike - price)."""
        source = _read_source("src/pnl.py")
        match = re.search(r'max\(0,\s*strike\s*-\s*underlying_price\)', source)
        assert match, (
            "Expected put settlement formula max(0, strike - underlying_price) in src/pnl.py. "
            "If this changed, update flow-pnl-settlement.mmd."
        )
