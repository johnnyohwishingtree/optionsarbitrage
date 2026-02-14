"""Tests for src/broker/ibkr_client.py — IB Gateway client.

These tests verify the client class structure without requiring IB Gateway.
Connection-dependent tests are skipped if ib_insync/ib_async is not installed.
"""

import pytest


class TestIBKRClientImport:
    def test_module_importable(self):
        """ibkr_client module should import (ib_insync or ib_async must be installed)."""
        try:
            from src.broker.ibkr_client import IBKRClient
        except ImportError:
            pytest.skip("ib_insync/ib_async not installed")

    def test_client_instantiation(self):
        """IBKRClient can be created without connecting."""
        try:
            from src.broker.ibkr_client import IBKRClient
        except ImportError:
            pytest.skip("ib_insync/ib_async not installed")

        client = IBKRClient(host='127.0.0.1', port=4002, client_id=999)
        assert client.host == '127.0.0.1'
        assert client.port == 4002
        assert client.client_id == 999
        assert client.connected is False

    def test_has_required_methods(self):
        """IBKRClient must implement all broker methods."""
        try:
            from src.broker.ibkr_client import IBKRClient
        except ImportError:
            pytest.skip("ib_insync/ib_async not installed")

        required_methods = [
            'connect', 'disconnect', 'is_connected',
            'get_current_price', 'get_account_summary', 'get_positions',
        ]
        for method in required_methods:
            assert hasattr(IBKRClient, method), f"IBKRClient missing method: {method}"

    def test_connect_returns_false_when_gateway_down(self):
        """connect() should return False (not raise) when IB Gateway isn't running."""
        try:
            from src.broker.ibkr_client import IBKRClient
        except ImportError:
            pytest.skip("ib_insync/ib_async not installed")

        client = IBKRClient(host='127.0.0.1', port=19999, client_id=999)  # bad port
        result = client.connect()
        assert result is False
        assert client.connected is False
