"""
Mock broker for testing. Returns canned data without needing IB Gateway.
"""

from types import SimpleNamespace
from typing import Any


class MockBroker:
    """Mock broker that satisfies BrokerProtocol for testing."""

    def __init__(self, prices: dict[str, float] | None = None,
                 positions: list[dict[str, Any]] | None = None,
                 account: dict[str, Any] | None = None):
        self._connected = False
        self._prices = prices or {'SPY': 605.50, 'SPX': 6055.00, 'XSP': 605.50}
        self._positions = positions or []
        self._account = account or {
            'account_id': 'DU_MOCK',
            'net_liquidation': 100000.00,
            'total_cash': 95000.00,
            'available_funds': 80000.00,
            'buying_power': 320000.00,
        }
        self._closed_positions: list[tuple[Any, int]] = []

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_current_price(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def get_account_summary(self) -> dict[str, Any]:
        return dict(self._account)

    def get_positions(self) -> list[dict[str, Any]]:
        return list(self._positions)

    def close_position(self, contract: Any, quantity: int) -> Any:
        self._closed_positions.append((contract, quantity))
        return SimpleNamespace(
            orderStatus=SimpleNamespace(status='Filled', avgFillPrice=0.0)
        )
