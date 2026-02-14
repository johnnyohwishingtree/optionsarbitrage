"""
Domain models for the options arbitrage trading system.

Dataclasses replacing ad-hoc dicts and DataFrames for typed, self-documenting data flow.
"""

from dataclasses import dataclass, field


@dataclass
class StrategyConfig:
    """Configuration for a single arbitrage strategy analysis."""
    sym1: str                    # e.g. 'SPY', 'XSP'
    sym2: str                    # e.g. 'SPX'
    qty_ratio: int               # 10 for SPX pairs, 1 for XSP pairs
    strike_step: int             # 5 for SPX, 1 for SPY/XSP
    strategy_type: str           # 'full', 'calls_only', 'puts_only'
    call_direction: str          # e.g. 'Sell SPX, Buy SPY'
    put_direction: str           # e.g. 'Buy SPY, Sell SPX'


@dataclass
class PriceQuote:
    """Liquidity-aware option price with metadata."""
    price: float
    source: str                  # 'midpoint' or 'trade'
    volume: int
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    spread_pct: float | None = None
    is_stale: bool = False
    liquidity_warning: str | None = None


@dataclass
class Leg:
    """A single leg of an options position."""
    symbol: str
    strike: float
    right: str                   # 'C' or 'P'
    action: str                  # 'BUY' or 'SELL'
    quantity: int
    entry_price: float


@dataclass
class Position:
    """A complete multi-leg options position with computed values."""
    legs: list[Leg] = field(default_factory=list)
    call_credit: float = 0.0
    put_credit: float = 0.0
    total_credit: float = 0.0
    estimated_margin: float = 0.0


@dataclass
class ScanResult:
    """Result from scanning a single strike pair."""
    sym1_strike: float
    sym2_strike: float
    moneyness: str               # formatted string, e.g. '+0.15%'
    max_gap: float               # absolute spread at max gap time
    max_gap_time: str            # ET time string, e.g. '10:30'
    credit: float                # estimated credit in dollars
    worst_case_pnl: float        # accurate grid-search worst-case P&L
    best_wc_time: str            # ET time of best worst-case entry
    direction: str               # e.g. 'Sell SPX' or 'Sell SPY'
    sym1_vol: int = 0
    sym2_vol: int = 0
    liquidity: str = 'OK'
    price_source: str = 'trade'  # 'midpoint' or 'trade'
    risk_reward: float = 0.0     # credit / abs(worst_case_pnl), inf if no risk
    max_risk: float = 0.0        # min(worst_case_pnl, 0)
