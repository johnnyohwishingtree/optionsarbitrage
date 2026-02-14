"""
Broker protocol for abstracting broker interactions.

IBKRClient already satisfies this interface. MockBroker provides canned data for tests.
"""

from typing import Protocol, Any


class BrokerProtocol(Protocol):
    """Protocol that any broker implementation must satisfy."""

    def connect(self) -> bool:
        """Connect to the broker. Returns True on success."""
        ...

    def disconnect(self) -> None:
        """Disconnect from the broker."""
        ...

    def is_connected(self) -> bool:
        """Check if currently connected."""
        ...

    def get_current_price(self, symbol: str) -> float | None:
        """Get current market price for a symbol."""
        ...

    def get_account_summary(self) -> dict[str, Any]:
        """Get account summary (net_liquidation, available_funds, buying_power, etc.)."""
        ...

    def get_positions(self) -> list[dict[str, Any]]:
        """Get current positions as list of position dicts."""
        ...

    def close_position(self, contract: Any, quantity: int) -> Any:
        """Close a position by placing an opposing order."""
        ...
