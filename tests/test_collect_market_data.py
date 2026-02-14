"""
Tests for data collection logic in collect_market_data.py.

Covers:
- Contract qualification filtering (conId check)
- Per-symbol stats tracking

Note: collect_market_data.py imports ib_async/ib_insync at module level.
These tests are skipped on CI where IB libraries aren't installed.
"""

import sys
import os
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# collect_market_data.py does `import ib_async` at module level.
# Skip the entire module if the IB library is not installed.
try:
    from collect_market_data import filter_qualified_contracts
except (ImportError, ModuleNotFoundError):
    pytest.skip("ib_async/ib_insync not installed", allow_module_level=True)


def _make_contract(con_id):
    """Create a mock IB contract with the given conId."""
    return SimpleNamespace(conId=con_id)


class TestFilterQualifiedContracts:

    def test_all_qualified(self):
        """All contracts with valid conId pass through."""
        all_contracts = [
            ('SPY', 697, 'C'),
            ('SPY', 697, 'P'),
            ('SPX', 6970, 'C'),
        ]
        contracts = [_make_contract(100), _make_contract(101), _make_contract(102)]

        qualified, stats = filter_qualified_contracts(all_contracts, contracts)

        assert len(qualified) == 3
        assert stats['ok'] == {'SPY': 2, 'SPX': 1}
        assert stats['failed'] == {}

    def test_all_failed(self):
        """All contracts with conId=0 are filtered out."""
        all_contracts = [
            ('SPY', 697, 'C'),
            ('SPY', 697, 'P'),
            ('SPY', 698, 'C'),
        ]
        contracts = [_make_contract(0), _make_contract(0), _make_contract(0)]

        qualified, stats = filter_qualified_contracts(all_contracts, contracts)

        assert len(qualified) == 0
        assert stats['ok'] == {}
        assert stats['failed'] == {'SPY': 3}

    def test_mixed_qualification(self):
        """SPY fails while SPX and XSP succeed — the observed bug scenario."""
        all_contracts = [
            ('SPY', 697, 'C'),
            ('SPY', 697, 'P'),
            ('SPX', 6970, 'C'),
            ('SPX', 6970, 'P'),
            ('XSP', 697, 'C'),
            ('XSP', 697, 'P'),
        ]
        contracts = [
            _make_contract(0),    # SPY fails
            _make_contract(0),    # SPY fails
            _make_contract(200),  # SPX ok
            _make_contract(201),  # SPX ok
            _make_contract(300),  # XSP ok
            _make_contract(301),  # XSP ok
        ]

        qualified, stats = filter_qualified_contracts(all_contracts, contracts)

        assert len(qualified) == 4
        assert stats['ok'] == {'SPX': 2, 'XSP': 2}
        assert stats['failed'] == {'SPY': 2}

        # Verify only SPX and XSP contracts are in the qualified list
        syms = [sym for (sym, _, _), _ in qualified]
        assert 'SPY' not in syms
        assert syms.count('SPX') == 2
        assert syms.count('XSP') == 2

    def test_conid_none_treated_as_failed(self):
        """Contract with conId=None (unset) is treated as failed."""
        all_contracts = [('SPY', 697, 'C')]
        contracts = [_make_contract(None)]

        qualified, stats = filter_qualified_contracts(all_contracts, contracts)

        assert len(qualified) == 0
        assert stats['failed'] == {'SPY': 1}

    def test_negative_conid_treated_as_failed(self):
        """Contract with negative conId is treated as failed."""
        all_contracts = [('SPY', 697, 'C')]
        contracts = [_make_contract(-1)]

        qualified, stats = filter_qualified_contracts(all_contracts, contracts)

        assert len(qualified) == 0
        assert stats['failed'] == {'SPY': 1}

    def test_preserves_contract_object(self):
        """The original contract object is preserved in the output tuple."""
        all_contracts = [('SPX', 6970, 'C')]
        contract = _make_contract(12345)
        contracts = [contract]

        qualified, _ = filter_qualified_contracts(all_contracts, contracts)

        assert len(qualified) == 1
        (sym, strike, right), returned_contract = qualified[0]
        assert sym == 'SPX'
        assert strike == 6970
        assert right == 'C'
        assert returned_contract is contract

    def test_empty_input(self):
        """Empty input returns empty output."""
        qualified, stats = filter_qualified_contracts([], [])

        assert qualified == []
        assert stats == {'ok': {}, 'failed': {}}
