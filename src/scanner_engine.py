"""
Strike scanner engine for finding arbitrage opportunities.

Pure functions for pair matching, liquidity filtering, price normalization,
and worst-case P&L ranking. No UI imports.
"""

import pandas as pd

from src.config import (
    SCANNER_PAIR_TOLERANCE,
    DEFAULT_MIN_VOLUME,
    GRID_BASIS_DRIFT_PCT,
)
from src.models import ScanResult
from src.pnl import calculate_best_worst_case_with_basis_drift


def match_strike_pairs(
    sym1_strikes: list[float],
    sym2_strikes: list[float],
    open_ratio: float,
    tolerance: float = SCANNER_PAIR_TOLERANCE,
) -> list[tuple[float, float]]:
    """
    Find all SYM1/SYM2 strike pairs within tolerance of the open ratio.

    For each SYM1 strike, finds SYM2 strikes where:
        abs(sym2_strike - sym1_strike * open_ratio) / (sym1_strike * open_ratio) < tolerance

    Returns:
        List of (sym1_strike, sym2_strike) pairs.
    """
    pairs = []
    for sym1_s in sym1_strikes:
        target = sym1_s * open_ratio
        for sym2_s in sym2_strikes:
            if abs(sym2_s - target) / target < tolerance:
                pairs.append((sym1_s, sym2_s))
    return pairs


def filter_by_liquidity(
    df_source: pd.DataFrame,
    symbol: str,
    strike: float,
    right: str,
    has_volume: bool,
    min_volume: int = DEFAULT_MIN_VOLUME,
    hide_illiquid: bool = True,
) -> tuple[pd.DataFrame, int]:
    """
    Filter option data for a single contract by liquidity.

    Args:
        df_source: Options data (TRADES or BID_ASK)
        symbol, strike, right: Contract identifiers
        has_volume: True if TRADES data (has 'volume' column)
        min_volume: Minimum total daily volume
        hide_illiquid: Whether to skip contracts below min_volume

    Returns:
        (filtered_df, total_volume) - filtered DataFrame and total volume count.
        Returns (empty DataFrame, 0) if contract fails liquidity filter.
    """
    contract_data = df_source[
        (df_source['symbol'] == symbol) &
        (df_source['strike'] == strike) &
        (df_source['right'] == right)
    ].copy()

    if contract_data.empty:
        return contract_data, 0

    if has_volume:
        total_vol = int(contract_data['volume'].sum())
        if hide_illiquid and total_vol < min_volume:
            return pd.DataFrame(), total_vol
        # Keep only bars with actual trades
        contract_data = contract_data[contract_data['volume'] > 0].copy()
    else:
        # BID_ASK: filter by valid quotes
        contract_data = contract_data[
            (contract_data['bid'] > 0) & (contract_data['ask'] > 0)
        ].copy()
        total_vol = len(contract_data)

    return contract_data, total_vol


def normalize_and_merge(
    sym1_opt: pd.DataFrame,
    sym2_opt: pd.DataFrame,
    df_bidask: pd.DataFrame | None,
    sym1: str,
    sym2: str,
    sym1_strike: float,
    sym2_strike: float,
    right: str,
    open_ratio: float,
    has_volume: bool,
    price_col: str,
) -> tuple[pd.DataFrame, bool]:
    """
    Normalize SYM2 prices and merge with SYM1 on time.

    When both TRADES and BID_ASK data exist, uses BID_ASK midpoint at times
    with actual trade volume (more accurate pricing).

    Returns:
        (merged_df, using_midpoint) - merged DataFrame with columns:
            time, spy_price, spx_normalized, spread
        and whether midpoint pricing was used.
    """
    using_midpoint = False

    if has_volume and df_bidask is not None:
        sym1_ba = df_bidask[
            (df_bidask['symbol'] == sym1) &
            (df_bidask['strike'] == sym1_strike) &
            (df_bidask['right'] == right)
        ].copy()
        sym2_ba = df_bidask[
            (df_bidask['symbol'] == sym2) &
            (df_bidask['strike'] == sym2_strike) &
            (df_bidask['right'] == right)
        ].copy()

        if not sym1_ba.empty and not sym2_ba.empty:
            sym1_ba = sym1_ba.sort_values('time')
            sym2_ba = sym2_ba.sort_values('time')

            # Only keep BID_ASK bars at times with actual trade volume
            sym1_liquid_times = set(sym1_opt['time'])
            sym2_liquid_times = set(sym2_opt['time'])
            sym1_ba = sym1_ba[sym1_ba['time'].isin(sym1_liquid_times)].copy()
            sym2_ba = sym2_ba[sym2_ba['time'].isin(sym2_liquid_times)].copy()

            sym2_ba['normalized_mid'] = sym2_ba['midpoint'] / open_ratio

            merged = pd.merge(
                sym1_ba[['time', 'midpoint']].rename(columns={'midpoint': 'spy_price'}),
                sym2_ba[['time', 'normalized_mid']].rename(columns={'normalized_mid': 'spx_normalized'}),
                on='time',
                how='inner'
            )
            using_midpoint = True
            return merged, using_midpoint

    # Fallback: use primary data source directly
    sym2_opt_copy = sym2_opt.copy()
    norm_col = f'normalized_{price_col}'
    sym2_opt_copy[norm_col] = sym2_opt_copy[price_col] / open_ratio

    merged = pd.merge(
        sym1_opt[['time', price_col]].rename(columns={price_col: 'spy_price'}),
        sym2_opt_copy[['time', norm_col]].rename(columns={norm_col: 'spx_normalized'}),
        on='time',
        how='inner'
    )
    return merged, using_midpoint


def calculate_scan_worst_case(
    merged: pd.DataFrame,
    sym1_strike: float,
    open_ratio: float,
    open_sym1: float,
    open_sym2: float,
    qty_ratio: int,
    basis_drift_pct: float = GRID_BASIS_DRIFT_PCT,
) -> pd.DataFrame:
    """
    Calculate quick worst-case P&L for each time point in merged data.

    This is the simplified formula used for ranking (not the full grid search).
    The full grid search is run on the best result for accurate P&L.

    Returns:
        merged DataFrame with 'worst_case_pnl' column added.
    """
    sym1_moneyness = ((sym1_strike - open_sym1) / open_sym1) * 100
    sym2_strike_from_data = sym1_strike * open_ratio  # approximate
    sym2_moneyness = ((sym2_strike_from_data - open_sym2) / open_sym2) * 100
    moneyness_diff = abs(sym1_moneyness - sym2_moneyness)

    def calc_worst_case(row):
        spread_val = row['spread']
        credit_val = abs(spread_val) * qty_ratio * 100
        max_basis_cost = open_ratio * basis_drift_pct * sym1_strike * qty_ratio * 100
        moneyness_cost = moneyness_diff / 100 * sym1_strike * qty_ratio * 100
        return credit_val - max_basis_cost - moneyness_cost

    merged = merged.copy()
    merged['worst_case_pnl'] = merged.apply(calc_worst_case, axis=1)
    return merged


def scan_single_pair(
    df_options: pd.DataFrame | None,
    df_bidask: pd.DataFrame | None,
    sym1_df: pd.DataFrame,
    sym2_df: pd.DataFrame,
    sym1: str,
    sym2: str,
    sym1_strike: float,
    sym2_strike: float,
    scanner_right: str,
    open_ratio: float,
    open_sym1: float,
    open_sym2: float,
    qty_ratio: int,
    has_volume: bool,
    price_col: str,
    min_volume: int = DEFAULT_MIN_VOLUME,
    hide_illiquid: bool = True,
) -> ScanResult | None:
    """
    Scan a single strike pair and return a ScanResult or None if insufficient data.

    Performs:
    1. Liquidity filtering
    2. Price normalization and merge
    3. Spread calculation
    4. Quick worst-case estimation for ranking
    5. Accurate grid search at the best time
    """
    # Determine data source
    source = df_options if df_options is not None else df_bidask
    if source is None:
        return None

    # Filter by liquidity
    sym1_opt, sym1_vol = filter_by_liquidity(
        source, sym1, sym1_strike, scanner_right, has_volume, min_volume, hide_illiquid
    )
    sym2_opt, sym2_vol = filter_by_liquidity(
        source, sym2, sym2_strike, scanner_right, has_volume, min_volume, hide_illiquid
    )

    if sym1_opt.empty or sym2_opt.empty:
        return None

    # Sort by time
    sym1_opt = sym1_opt.sort_values('time')
    sym2_opt = sym2_opt.sort_values('time')

    # Normalize and merge
    merged, using_midpoint = normalize_and_merge(
        sym1_opt, sym2_opt, df_bidask,
        sym1, sym2, sym1_strike, sym2_strike, scanner_right,
        open_ratio, has_volume, price_col
    )

    if merged.empty or len(merged) < 5:
        return None

    # Calculate spread
    merged['spread'] = merged['spx_normalized'] - merged['spy_price']

    # Moneyness
    sym1_moneyness = ((sym1_strike - open_sym1) / open_sym1) * 100

    # Quick worst-case for ranking
    merged = calculate_scan_worst_case(
        merged, sym1_strike, open_ratio, open_sym1, open_sym2, qty_ratio
    )

    # Find max spread and best worst-case
    max_spread_idx = merged['spread'].abs().idxmax()
    max_spread_row = merged.loc[max_spread_idx]

    best_worst_idx = merged['worst_case_pnl'].idxmax()
    best_worst_row = merged.loc[best_worst_idx]

    # Get actual SYM2 price for credit calculation
    if using_midpoint:
        sym2_ba = df_bidask[
            (df_bidask['symbol'] == sym2) &
            (df_bidask['strike'] == sym2_strike) &
            (df_bidask['right'] == scanner_right)
        ]
        sym2_at_max = sym2_ba[sym2_ba['time'] == max_spread_row['time']]
        if not sym2_at_max.empty:
            sym2_price_at_max = sym2_at_max['midpoint'].iloc[0]
        else:
            sym2_price_at_max = sym2_opt[sym2_opt['time'] == max_spread_row['time']][price_col].iloc[0]
    else:
        sym2_price_at_max = sym2_opt[sym2_opt['time'] == max_spread_row['time']][price_col].iloc[0]

    if max_spread_row['spread'] > 0:
        credit = (sym2_price_at_max * 1 * 100) - (max_spread_row['spy_price'] * qty_ratio * 100)
    else:
        credit = (max_spread_row['spy_price'] * qty_ratio * 100) - (sym2_price_at_max * 1 * 100)

    # Time labels
    max_time_et = max_spread_row['time'].tz_convert('America/New_York').strftime('%H:%M')
    best_worst_time_et = best_worst_row['time'].tz_convert('America/New_York').strftime('%H:%M')

    # Accurate grid search at best worst-case time
    best_worst_time = best_worst_row['time']

    sym1_at_time = sym1_df.iloc[(sym1_df['time'] - best_worst_time).abs().argsort()[:1]]
    sym2_at_time = sym2_df.iloc[(sym2_df['time'] - best_worst_time).abs().argsort()[:1]]
    entry_sym1_price = sym1_at_time['close'].iloc[0]
    entry_sym2_price = sym2_at_time['close'].iloc[0]

    # Look up option prices at best worst-case time
    if using_midpoint:
        sym1_ba = df_bidask[
            (df_bidask['symbol'] == sym1) &
            (df_bidask['strike'] == sym1_strike) &
            (df_bidask['right'] == scanner_right)
        ]
        sym1_ba_at = sym1_ba.iloc[(sym1_ba['time'] - best_worst_time).abs().argsort()[:1]]
        sym2_ba = df_bidask[
            (df_bidask['symbol'] == sym2) &
            (df_bidask['strike'] == sym2_strike) &
            (df_bidask['right'] == scanner_right)
        ]
        sym2_ba_at = sym2_ba.iloc[(sym2_ba['time'] - best_worst_time).abs().argsort()[:1]]
        sym1_opt_price = sym1_ba_at['midpoint'].iloc[0]
        sym2_opt_price = sym2_ba_at['midpoint'].iloc[0]
    else:
        sym1_opt_at = sym1_opt.iloc[(sym1_opt['time'] - best_worst_time).abs().argsort()[:1]]
        sym2_opt_at = sym2_opt.iloc[(sym2_opt['time'] - best_worst_time).abs().argsort()[:1]]
        sym1_opt_price = sym1_opt_at[price_col].iloc[0]
        sym2_opt_price = sym2_opt_at[price_col].iloc[0]

    # Direction
    scan_direction = f'Sell {sym2}' if max_spread_row['spread'] > 0 else f'Sell {sym1}'

    # Build grid search params
    scan_show_calls = (scanner_right == 'C')
    scan_show_puts = (scanner_right == 'P')

    if scanner_right == 'P':
        if scan_direction == f'Sell {sym2}':
            scan_put_direction = f"Buy {sym1}, Sell {sym2}"
            scan_sell_put_price = sym2_opt_price
            scan_buy_put_price = sym1_opt_price
            scan_sell_puts_qty = 1
            scan_buy_puts_qty = qty_ratio
        else:
            scan_put_direction = f"Sell {sym1}, Buy {sym2}"
            scan_sell_put_price = sym1_opt_price
            scan_buy_put_price = sym2_opt_price
            scan_sell_puts_qty = qty_ratio
            scan_buy_puts_qty = 1
        scan_call_direction = f"Sell {sym2}, Buy {sym1}"
        scan_sell_call_price = scan_buy_call_price = 0.0
        scan_sell_calls_qty = scan_buy_calls_qty = 0
    else:  # Calls
        if scan_direction == f'Sell {sym2}':
            scan_call_direction = f"Sell {sym2}, Buy {sym1}"
            scan_sell_call_price = sym2_opt_price
            scan_buy_call_price = sym1_opt_price
            scan_sell_calls_qty = 1
            scan_buy_calls_qty = qty_ratio
        else:
            scan_call_direction = f"Buy {sym2}, Sell {sym1}"
            scan_sell_call_price = sym1_opt_price
            scan_buy_call_price = sym2_opt_price
            scan_sell_calls_qty = qty_ratio
            scan_buy_calls_qty = 1
        scan_put_direction = f"Sell {sym1}, Buy {sym2}"
        scan_sell_put_price = scan_buy_put_price = 0.0
        scan_sell_puts_qty = scan_buy_puts_qty = 0

    _, accurate_worst = calculate_best_worst_case_with_basis_drift(
        entry_spy_price=entry_sym1_price,
        entry_spx_price=entry_sym2_price,
        spy_strike=sym1_strike,
        spx_strike=sym2_strike,
        call_direction=scan_call_direction,
        put_direction=scan_put_direction,
        sell_call_price=scan_sell_call_price,
        buy_call_price=scan_buy_call_price,
        sell_calls_qty=scan_sell_calls_qty,
        buy_calls_qty=scan_buy_calls_qty,
        sell_put_price=scan_sell_put_price,
        buy_put_price=scan_buy_put_price,
        sell_puts_qty=scan_sell_puts_qty,
        buy_puts_qty=scan_buy_puts_qty,
        show_calls=scan_show_calls,
        show_puts=scan_show_puts,
        sym1=sym1, sym2=sym2,
    )
    accurate_worst_pnl = accurate_worst.get('net_pnl', best_worst_row['worst_case_pnl'])

    # Liquidity status
    liq_ok = sym1_vol >= min_volume and sym2_vol >= min_volume
    liq_label = "OK" if liq_ok else "LOW"

    # Risk/reward
    if accurate_worst_pnl >= 0:
        risk_reward = float('inf')
    else:
        risk_reward = credit / abs(accurate_worst_pnl)

    return ScanResult(
        sym1_strike=sym1_strike,
        sym2_strike=sym2_strike,
        moneyness=f"{sym1_moneyness:+.2f}%",
        max_gap=abs(max_spread_row['spread']),
        max_gap_time=max_time_et,
        credit=credit,
        worst_case_pnl=accurate_worst_pnl,
        best_wc_time=best_worst_time_et,
        direction=scan_direction,
        sym1_vol=sym1_vol,
        sym2_vol=sym2_vol,
        liquidity=liq_label,
        price_source='midpoint' if using_midpoint else 'trade',
        risk_reward=risk_reward,
        max_risk=min(accurate_worst_pnl, 0),
    )


def scan_all_pairs(
    df_options: pd.DataFrame | None,
    df_bidask: pd.DataFrame | None,
    sym1_df: pd.DataFrame,
    sym2_df: pd.DataFrame,
    sym1: str,
    sym2: str,
    scanner_right: str,
    open_ratio: float,
    open_sym1: float,
    open_sym2: float,
    qty_ratio: int,
    has_volume: bool,
    price_col: str,
    min_volume: int = DEFAULT_MIN_VOLUME,
    hide_illiquid: bool = True,
    progress_callback=None,
) -> list[ScanResult]:
    """
    Scan all matching strike pairs and return ranked results.

    Args:
        progress_callback: Optional callable(current, total) for progress updates.

    Returns:
        List of ScanResult, sorted by worst_case_pnl descending (safest first).
    """
    source = df_options if df_options is not None else df_bidask
    if source is None:
        return []

    sym1_strikes = sorted(source[source['symbol'] == sym1]['strike'].unique())
    sym2_strikes = sorted(source[source['symbol'] == sym2]['strike'].unique())

    pairs = match_strike_pairs(sym1_strikes, sym2_strikes, open_ratio)
    results = []

    for idx, (sym1_s, sym2_s) in enumerate(pairs):
        if progress_callback:
            progress_callback(idx + 1, len(pairs))

        result = scan_single_pair(
            df_options, df_bidask, sym1_df, sym2_df,
            sym1, sym2, sym1_s, sym2_s, scanner_right,
            open_ratio, open_sym1, open_sym2, qty_ratio,
            has_volume, price_col, min_volume, hide_illiquid,
        )
        if result is not None:
            results.append(result)

    # Sort by safety (worst-case P&L descending)
    results.sort(key=lambda r: r.worst_case_pnl, reverse=True)
    return results


def rank_results(
    results: list[ScanResult],
    sort_by: str = 'safety',
) -> list[ScanResult]:
    """
    Re-rank scan results by different criteria.

    Args:
        sort_by: 'safety' (worst-case P&L), 'profit' (credit), 'risk_reward'
    """
    if sort_by == 'profit':
        return sorted(results, key=lambda r: r.credit, reverse=True)
    elif sort_by == 'risk_reward':
        return sorted(results, key=lambda r: r.risk_reward, reverse=True)
    else:  # safety
        return sorted(results, key=lambda r: r.worst_case_pnl, reverse=True)
