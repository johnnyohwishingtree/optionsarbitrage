"""
Price normalization and spread calculation for overlay and divergence analysis.

Pure functions for normalizing option prices across correlated symbols,
calculating spreads, and computing quick worst-case estimates.
No UI imports.
"""

import pandas as pd

from src.config import GRID_BASIS_DRIFT_PCT


def normalize_option_prices(
    sym1_opt: pd.DataFrame,
    sym2_opt: pd.DataFrame,
    open_ratio: float,
    price_col: str,
) -> pd.DataFrame:
    """
    Normalize SYM2 option prices by dividing by open_ratio, then merge with SYM1 on time.

    Args:
        sym1_opt: SYM1 option data (already filtered to contract + liquid bars)
        sym2_opt: SYM2 option data (already filtered to contract + liquid bars)
        open_ratio: SYM2/SYM1 price ratio at market open
        price_col: Column name for price ('close' for TRADES, 'midpoint' for BID_ASK)

    Returns:
        DataFrame with columns: time, spy_price, spx_normalized
    """
    sym2_copy = sym2_opt.copy()
    norm_col = f'normalized_{price_col}'
    sym2_copy[norm_col] = sym2_copy[price_col] / open_ratio

    merged = pd.merge(
        sym1_opt[['time', price_col]].rename(columns={price_col: 'spy_price'}),
        sym2_copy[['time', norm_col]].rename(columns={norm_col: 'spx_normalized'}),
        on='time',
        how='inner'
    )
    return merged


def calculate_spread(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate spread and spread percentage from merged price data.

    Adds columns: spread, spread_pct

    Positive spread = SYM2 more expensive (sell SYM2, buy SYM1)
    Negative spread = SYM1 more expensive (sell SYM1, buy SYM2)
    """
    merged = merged.copy()
    merged['spread'] = merged['spx_normalized'] - merged['spy_price']
    merged['spread_pct'] = (merged['spread'] / merged['spy_price']) * 100
    return merged


def calculate_worst_case_quick(
    merged: pd.DataFrame,
    open_ratio: float,
    sym1_strike: float,
    qty_ratio: int,
    sym1_moneyness_pct: float,
    sym2_moneyness_pct: float,
    basis_drift_pct: float = GRID_BASIS_DRIFT_PCT,
) -> pd.DataFrame:
    """
    Calculate quick worst-case P&L for each time point.

    This is the simplified formula used for ranking and overlay display.
    For accurate P&L, use calculate_best_worst_case_with_basis_drift() from pnl.py.

    Adds 'worst_case_pnl' column to merged DataFrame.
    """
    moneyness_diff = abs(sym1_moneyness_pct - sym2_moneyness_pct)

    def calc_worst_case(row):
        spread = row['spread']
        credit = abs(spread) * qty_ratio * 100
        max_basis_cost = open_ratio * basis_drift_pct * sym1_strike * qty_ratio * 100
        moneyness_cost = moneyness_diff / 100 * sym1_strike * qty_ratio * 100
        return credit - max_basis_cost - moneyness_cost

    merged = merged.copy()
    merged['worst_case_pnl'] = merged.apply(calc_worst_case, axis=1)
    return merged


def calculate_underlying_divergence(
    sym1_df: pd.DataFrame,
    sym2_df: pd.DataFrame,
    qty_ratio: int,
) -> pd.DataFrame:
    """
    Calculate underlying price divergence between two symbols.

    Computes % change from open for each symbol, then the gap between them.

    Args:
        sym1_df: SYM1 underlying data with 'time', 'time_label', 'close'
        sym2_df: SYM2 underlying data with 'time', 'close'
        qty_ratio: Quantity ratio for dollar gap normalization

    Returns:
        DataFrame with columns:
            time, time_label, close_sym1, close_sym2,
            pct_change_sym1, pct_change_sym2, pct_gap, dollar_gap
    """
    sym1_open = sym1_df.iloc[0]['close']
    sym2_open = sym2_df.iloc[0]['close']

    sym1_div = sym1_df[['time', 'time_label', 'close']].copy()
    sym2_div = sym2_df[['time', 'close']].copy()

    sym1_div['pct_change'] = (sym1_div['close'] - sym1_open) / sym1_open * 100
    sym2_div['pct_change'] = (sym2_div['close'] - sym2_open) / sym2_open * 100

    merged = pd.merge(
        sym1_div[['time', 'time_label', 'close', 'pct_change']],
        sym2_div[['time', 'close', 'pct_change']],
        on='time',
        suffixes=('_sym1', '_sym2')
    )

    merged['pct_gap'] = merged['pct_change_sym2'] - merged['pct_change_sym1']
    merged['dollar_gap'] = merged['close_sym2'] / qty_ratio - merged['close_sym1']

    return merged
