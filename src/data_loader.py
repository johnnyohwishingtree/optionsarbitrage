"""
Data loading and validation for CSV market data files.

Pure functions for listing available dates, loading DataFrames,
and preparing symbol-specific data.
"""

import os
import pandas as pd

from src.config import SYMBOL_PAIRS


def list_available_dates(data_dir: str = 'data') -> list[tuple[str, str]]:
    """
    List available trading dates from underlying price CSVs.

    Returns:
        List of (raw_date, formatted_date) tuples, e.g. [('20260213', '2026-02-13')]
        Sorted chronologically (oldest first).
    """
    available_dates = []
    if os.path.exists(data_dir):
        for file in sorted(os.listdir(data_dir)):
            if file.startswith('underlying_prices_') and file.endswith('.csv'):
                date_str = file.replace('underlying_prices_', '').replace('.csv', '')
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                available_dates.append((date_str, formatted_date))
    return available_dates


def load_underlying_prices(date_str: str, data_dir: str = 'data') -> pd.DataFrame:
    """
    Load underlying price data for a date.

    Returns:
        DataFrame with columns: symbol, time, open, high, low, close, volume
        Time column is parsed as UTC datetime.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    filepath = os.path.join(data_dir, f'underlying_prices_{date_str}.csv')
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Underlying price data not found: {filepath}")

    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    return df


def load_options_data(date_str: str, data_dir: str = 'data') -> pd.DataFrame | None:
    """
    Load options TRADES data for a date.

    Returns:
        DataFrame with columns: symbol, strike, right, time, open, volume
        Or None if file doesn't exist.
    """
    filepath = os.path.join(data_dir, f'options_data_{date_str}.csv')
    if not os.path.exists(filepath):
        return None

    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    return df


def load_bidask_data(date_str: str, data_dir: str = 'data') -> pd.DataFrame | None:
    """
    Load options BID_ASK data for a date.

    Returns:
        DataFrame with columns: symbol, strike, right, time, bid, ask, midpoint
        Or None if file doesn't exist.
    """
    filepath = os.path.join(data_dir, f'options_bidask_{date_str}.csv')
    if not os.path.exists(filepath):
        return None

    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    return df


def get_symbol_dataframes(
    df_underlying: pd.DataFrame,
    sym1: str,
    sym2: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split underlying DataFrame into per-symbol DataFrames with ET time labels.

    Returns:
        (sym1_df, sym2_df) with added columns: time_et, time_label, time_short
    """
    sym1_df = df_underlying[df_underlying['symbol'] == sym1].copy()
    sym2_df = df_underlying[df_underlying['symbol'] == sym2].copy()

    for df in (sym1_df, sym2_df):
        df['time_et'] = df['time'].dt.tz_convert('America/New_York')
        df['time_label'] = df['time_et'].dt.strftime('%I:%M %p ET')
        df['time_short'] = df['time_et'].dt.strftime('%H:%M')

    return sym1_df, sym2_df


def get_available_pairs(
    df_underlying: pd.DataFrame,
    symbol_pairs: dict[str, tuple[str, str]] | None = None
) -> dict[str, tuple[str, str]]:
    """
    Filter symbol pairs to only those where both symbols have underlying data.

    Args:
        df_underlying: DataFrame with 'symbol' column
        symbol_pairs: Dict of label -> (sym1, sym2). Defaults to SYMBOL_PAIRS.

    Returns:
        Dict of available pairs (subset of input).
    """
    if symbol_pairs is None:
        symbol_pairs = SYMBOL_PAIRS

    available_symbols = set(df_underlying['symbol'].unique())
    return {
        label: syms
        for label, syms in symbol_pairs.items()
        if syms[0] in available_symbols and syms[1] in available_symbols
    }
