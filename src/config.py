"""
Centralized business constants for the options arbitrage trading system.

All hardcoded values that drive strategy logic are defined here.
Import from this module instead of hardcoding values in business logic.
"""

# --- Quantity & Strike Ratios ---

# SPY:SPX uses 10:1 ratio because SPX has $5 strike increments (10x SPY's $1)
QTY_RATIO_SPX = 10
# SPY:XSP and XSP:SPX use 1:1 ratio (both have $1 strikes, or pair uses 1:1)
QTY_RATIO_DEFAULT = 1

# SPX options use $5 strike increments
STRIKE_STEP_SPX = 5
# SPY and XSP options use $1 strike increments
STRIKE_STEP_DEFAULT = 1


# --- Moneyness & Matching ---

# Strike pairs with moneyness difference above this threshold trigger a warning
MONEYNESS_WARN_THRESHOLD = 0.05  # percent

# Scanner: strike pairs must be within this tolerance of (SYM1_strike * open_ratio)
SCANNER_PAIR_TOLERANCE = 0.005  # 0.5%


# --- Liquidity ---

# Bid-ask spread above this percentage of midpoint triggers a liquidity warning
WIDE_SPREAD_THRESHOLD = 20  # percent

# Default minimum total daily volume for scanner liquidity filtering
DEFAULT_MIN_VOLUME = 10


# --- Grid Search (Best/Worst Case Scenario Analysis) ---

# Number of SYM1 price points to evaluate across the price range
GRID_PRICE_POINTS = 50

# Price range: ±5% from entry price
GRID_PRICE_RANGE_PCT = 0.05

# Basis drift: ±0.10% (SYM2/SYM1 ratio can shift this much intraday)
GRID_BASIS_DRIFT_PCT = 0.001


# --- Margin ---

# Margin estimate: 20% of short notional value minus credit received
MARGIN_RATE = 0.20


# --- Trading Day ---

# Trading day: 9:30 AM to 4:00 PM ET = 390 minutes
TRADING_DAY_MINUTES = 390


# --- Data Collection ---

# Strike range for collecting option data: ±3% from current price
COLLECTION_STRIKE_RANGE_PCT = 0.03


# --- IB Connection ---

IB_HOST = '127.0.0.1'
IB_PORT = 4002


# --- Symbol Pair Definitions ---

SYMBOL_PAIRS = {
    "XSP / SPX": ("XSP", "SPX"),
    "SPY / SPX": ("SPY", "SPX"),
    "SPY / XSP": ("SPY", "XSP"),
}


def get_qty_ratio(sym2: str) -> int:
    """Return the quantity ratio for a symbol pair based on SYM2."""
    return QTY_RATIO_SPX if sym2 == 'SPX' else QTY_RATIO_DEFAULT


def get_strike_step(sym2: str) -> int:
    """Return the strike step size for SYM2."""
    return STRIKE_STEP_SPX if sym2 == 'SPX' else STRIKE_STEP_DEFAULT
