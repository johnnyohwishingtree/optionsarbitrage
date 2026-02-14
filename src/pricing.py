"""
Price discovery and lookup for options data.

Contains pure functions for:
- Looking up option prices from trade/bid-ask DataFrames
- Finding nearest data rows with liquidity preference
- Liquidity-aware price resolution
"""

from src.config import WIDE_SPREAD_THRESHOLD


def get_option_price_from_db(df_options, symbol, strike, right, entry_time):
    """
    Look up option price from database at specified time.
    If exact time not found, returns price from nearest available time >= entry_time.

    Works with both TRADES data (uses 'open' column) and BID_ASK data (uses 'midpoint' column).

    Returns:
        float: Option price at entry time or nearest after
        None if contract not found in database
    """
    # Filter to contract (symbol, strike, right)
    contract_mask = (
        (df_options['symbol'] == symbol) &
        (df_options['strike'] == strike) &
        (df_options['right'] == right)
    )

    contract_data = df_options[contract_mask]

    if len(contract_data) == 0:
        return None

    # Use 'midpoint' for BID_ASK data, 'open' for TRADES data
    price_col = 'midpoint' if 'midpoint' in df_options.columns else 'open'

    # Try exact time match first
    exact_match = contract_data[contract_data['time'] == entry_time]
    if len(exact_match) > 0:
        return exact_match.iloc[0][price_col]

    # If no exact match, find nearest timestamp >= entry_time
    future_data = contract_data[contract_data['time'] >= entry_time]
    if len(future_data) > 0:
        nearest = future_data.sort_values('time').iloc[0]
        return nearest[price_col]

    # If no future data, use the last available data point
    nearest = contract_data.sort_values('time').iloc[-1]
    return nearest[price_col]


def _find_nearest_row(data, entry_time, prefer_liquid=False, volume_col='volume'):
    """Find nearest row at/after entry_time, preferring bars with volume > 0."""
    if prefer_liquid and volume_col in data.columns:
        liquid = data[data[volume_col] > 0]
        if len(liquid) > 0:
            exact = liquid[liquid['time'] == entry_time]
            if len(exact) > 0:
                return exact.iloc[0], True
            future = liquid[liquid['time'] >= entry_time]
            if len(future) > 0:
                return future.sort_values('time').iloc[0], True
            # All liquid bars are before entry_time — use the latest one
            return liquid.sort_values('time').iloc[-1], True

    # Fallback: any bar (including zero-volume)
    exact = data[data['time'] == entry_time]
    if len(exact) > 0:
        return exact.iloc[0], False
    future = data[data['time'] >= entry_time]
    if len(future) > 0:
        return future.sort_values('time').iloc[0], False
    return data.sort_values('time').iloc[-1], False


def get_option_price_with_liquidity(df_options, df_bidask, symbol, strike, right, entry_time):
    """
    Look up option price with liquidity metadata.

    Prefers bars with volume > 0 to avoid stale carried-forward prices.
    If BID_ASK data exists, uses midpoint as price (at a liquid time).
    Otherwise falls back to TRADES open price.

    Returns:
        dict with keys: price, price_source, volume, bid, ask, spread,
                        spread_pct, is_stale, liquidity_warning
        None if contract not found
    """
    result = {
        'price': None,
        'price_source': 'trade',
        'volume': 0,
        'bid': None,
        'ask': None,
        'spread': None,
        'spread_pct': None,
        'is_stale': False,
        'liquidity_warning': None,
    }

    # Get TRADES data — prefer bars with volume > 0
    trade_row = None
    found_liquid = False
    contract_data = None
    if df_options is not None:
        contract_mask = (
            (df_options['symbol'] == symbol) &
            (df_options['strike'] == strike) &
            (df_options['right'] == right)
        )
        contract_data = df_options[contract_mask]

        if len(contract_data) > 0:
            trade_row, found_liquid = _find_nearest_row(
                contract_data, entry_time, prefer_liquid=True
            )

    if trade_row is not None:
        result['volume'] = int(trade_row.get('volume', 0))

    # Try BID_ASK data — but only at times where TRADES had volume
    if df_bidask is not None:
        ba_mask = (
            (df_bidask['symbol'] == symbol) &
            (df_bidask['strike'] == strike) &
            (df_bidask['right'] == right)
        )
        ba_data = df_bidask[ba_mask]

        if len(ba_data) > 0:
            # Restrict to times with trade volume if we have that info
            if contract_data is not None and len(contract_data) > 0:
                liquid_times = set(contract_data[contract_data['volume'] > 0]['time'])
                ba_liquid = ba_data[ba_data['time'].isin(liquid_times)]
                if len(ba_liquid) > 0:
                    ba_data = ba_liquid

            ba_row, _ = _find_nearest_row(ba_data, entry_time)

            bid = ba_row['bid']
            ask = ba_row['ask']
            midpoint = ba_row['midpoint']

            result['price'] = midpoint
            result['price_source'] = 'midpoint'
            result['bid'] = bid
            result['ask'] = ask

            if bid > 0 and ask > 0:
                result['spread'] = ask - bid
                result['spread_pct'] = (ask - bid) / midpoint * 100 if midpoint > 0 else None

            if result['volume'] == 0:
                if bid > 0 and ask > 0:
                    # Valid bid/ask quotes exist — price is usable, just no trades
                    result['liquidity_warning'] = f"No trades (vol=0), bid/ask={bid:.2f}/{ask:.2f}"
                else:
                    result['is_stale'] = True
                    result['liquidity_warning'] = f"STALE (vol=0, no valid quotes)"
            elif result['spread_pct'] is not None and result['spread_pct'] > WIDE_SPREAD_THRESHOLD:
                result['liquidity_warning'] = f"Wide spread: {result['spread_pct']:.1f}%"

            return result

    # Fallback: TRADES only
    if trade_row is not None:
        result['price'] = trade_row['open']
        result['price_source'] = 'trade'

        if result['volume'] == 0:
            result['is_stale'] = True
            result['liquidity_warning'] = "STALE (vol=0, no bid/ask data)"

        return result

    return None
