"""
P&L calculation engine for options arbitrage strategies.

Contains pure functions for:
- Option P&L calculation
- Settlement value (intrinsic value) calculation
- Best/worst case scenario analysis with basis drift
"""


def calculate_option_pnl(entry_price, exit_price, action, quantity):
    """Calculate P&L for an option position"""
    if action == 'BUY':
        return (exit_price - entry_price) * quantity * 100
    else:  # SELL
        return (entry_price - exit_price) * quantity * 100


def calculate_settlement_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)


def calculate_best_worst_case_with_basis_drift(
    entry_spy_price, entry_spx_price,
    spy_strike, spx_strike,
    call_direction, put_direction,
    sell_call_price, buy_call_price, sell_calls_qty, buy_calls_qty,
    sell_put_price, buy_put_price, sell_puts_qty, buy_puts_qty,
    show_calls, show_puts,
    sym1='SPY', sym2='SPX',
    price_range_pct=0.05,  # +/-5% price range
    basis_drift_pct=0.001  # +/-0.10% basis drift
):
    """
    Calculate best/worst case P&L accounting for both price movement AND basis drift.

    The sym1/sym2 ratio can drift slightly from entry, causing P&L to fall outside
    the "lockstep" range. This function accounts for that basis risk.

    Args:
        sym1: First symbol in the pair (e.g. 'SPY', 'XSP')
        sym2: Second symbol in the pair (e.g. 'SPX')

    Returns: (best_case_dict, worst_case_dict)
    """
    entry_ratio = entry_spx_price / entry_spy_price

    best_pnl = float('-inf')
    worst_pnl = float('inf')
    best_scenario = {}
    worst_scenario = {}

    # Iterate through sym1 prices (+/-5% range)
    num_price_points = 50  # Reduced for performance since we add basis dimension
    spy_min = entry_spy_price * (1 - price_range_pct)
    spy_max = entry_spy_price * (1 + price_range_pct)
    spy_step = (spy_max - spy_min) / (num_price_points - 1)

    # Basis drift values to test
    basis_drifts = [1 - basis_drift_pct, 1.0, 1 + basis_drift_pct]

    for i in range(num_price_points):
        spy_px = spy_min + i * spy_step

        for basis_mult in basis_drifts:
            # Apply basis drift to the ratio
            spx_px = spy_px * entry_ratio * basis_mult

            # Calculate settlement values
            spy_call_val = calculate_settlement_value(spy_px, spy_strike, 'C')
            spx_call_val = calculate_settlement_value(spx_px, spx_strike, 'C')
            spy_put_val = calculate_settlement_value(spy_px, spy_strike, 'P')
            spx_put_val = calculate_settlement_value(spx_px, spx_strike, 'P')

            # Calculate P&L with per-leg breakdown
            scenario_pnl = 0.0
            call_credit_total = 0.0
            call_settle_cost = 0.0
            put_credit_total = 0.0
            put_settle_cost = 0.0
            sell_call_settle_val = 0.0
            buy_call_settle_val = 0.0
            sell_put_settle_val = 0.0
            buy_put_settle_val = 0.0

            if show_calls:
                call_credit_total = (sell_call_price * sell_calls_qty * 100) - (buy_call_price * buy_calls_qty * 100)
                if call_direction == f"Buy {sym2}, Sell {sym1}":
                    scenario_pnl += calculate_option_pnl(sell_call_price, spy_call_val, 'SELL', sell_calls_qty)
                    scenario_pnl += calculate_option_pnl(buy_call_price, spx_call_val, 'BUY', buy_calls_qty)
                    sell_call_settle_val = spy_call_val
                    buy_call_settle_val = spx_call_val
                    call_settle_cost = (spy_call_val * sell_calls_qty * 100) - (spx_call_val * buy_calls_qty * 100)
                else:
                    scenario_pnl += calculate_option_pnl(sell_call_price, spx_call_val, 'SELL', sell_calls_qty)
                    scenario_pnl += calculate_option_pnl(buy_call_price, spy_call_val, 'BUY', buy_calls_qty)
                    sell_call_settle_val = spx_call_val
                    buy_call_settle_val = spy_call_val
                    call_settle_cost = (spx_call_val * sell_calls_qty * 100) - (spy_call_val * buy_calls_qty * 100)

            if show_puts:
                put_credit_total = (sell_put_price * sell_puts_qty * 100) - (buy_put_price * buy_puts_qty * 100)
                if put_direction == f"Buy {sym1}, Sell {sym2}":
                    scenario_pnl += calculate_option_pnl(sell_put_price, spx_put_val, 'SELL', sell_puts_qty)
                    scenario_pnl += calculate_option_pnl(buy_put_price, spy_put_val, 'BUY', buy_puts_qty)
                    sell_put_settle_val = spx_put_val
                    buy_put_settle_val = spy_put_val
                    put_settle_cost = (spx_put_val * sell_puts_qty * 100) - (spy_put_val * buy_puts_qty * 100)
                else:
                    scenario_pnl += calculate_option_pnl(sell_put_price, spy_put_val, 'SELL', sell_puts_qty)
                    scenario_pnl += calculate_option_pnl(buy_put_price, spx_put_val, 'BUY', buy_puts_qty)
                    sell_put_settle_val = spy_put_val
                    buy_put_settle_val = spx_put_val
                    put_settle_cost = (spy_put_val * sell_puts_qty * 100) - (spx_put_val * buy_puts_qty * 100)

            total_credit = call_credit_total + put_credit_total
            total_settle_cost = call_settle_cost + put_settle_cost

            # Determine sell/buy symbols from direction
            if show_calls:
                if call_direction == f"Buy {sym2}, Sell {sym1}":
                    sell_call_sym, buy_call_sym = sym1, sym2
                else:
                    sell_call_sym, buy_call_sym = sym2, sym1
            else:
                sell_call_sym, buy_call_sym = '', ''

            if show_puts:
                if put_direction == f"Buy {sym1}, Sell {sym2}":
                    sell_put_sym, buy_put_sym = sym2, sym1
                else:
                    sell_put_sym, buy_put_sym = sym1, sym2
            else:
                sell_put_sym, buy_put_sym = '', ''

            breakdown = {
                'call_credit': call_credit_total,
                'put_credit': put_credit_total,
                'total_credit': total_credit,
                'call_settlement_cost': call_settle_cost,
                'put_settlement_cost': put_settle_cost,
                'total_settlement_cost': total_settle_cost,
                # Per-leg detail for display
                'sell_call_symbol': sell_call_sym,
                'buy_call_symbol': buy_call_sym,
                'sell_put_symbol': sell_put_sym,
                'buy_put_symbol': buy_put_sym,
                'sell_call_settle': sell_call_settle_val,
                'buy_call_settle': buy_call_settle_val,
                'sell_put_settle': sell_put_settle_val,
                'buy_put_settle': buy_put_settle_val,
                'sell_call_price': sell_call_price,
                'buy_call_price': buy_call_price,
                'sell_put_price': sell_put_price,
                'buy_put_price': buy_put_price,
                'sell_calls_qty': sell_calls_qty,
                'buy_calls_qty': buy_calls_qty,
                'sell_puts_qty': sell_puts_qty,
                'buy_puts_qty': buy_puts_qty,
                'spy_strike': spy_strike,
                'spx_strike': spx_strike,
            }

            if scenario_pnl > best_pnl:
                best_pnl = scenario_pnl
                best_scenario = {
                    'net_pnl': scenario_pnl,
                    'spy_price': spy_px,
                    'spx_price': spx_px,
                    'basis_drift': (basis_mult - 1) * 100,  # as percentage
                    'breakdown': breakdown,
                }

            if scenario_pnl < worst_pnl:
                worst_pnl = scenario_pnl
                worst_scenario = {
                    'net_pnl': scenario_pnl,
                    'spy_price': spy_px,
                    'spx_price': spx_px,
                    'basis_drift': (basis_mult - 1) * 100,  # as percentage
                    'breakdown': breakdown,
                }

    return best_scenario, worst_scenario
