"""
Historical Analysis tab for the Dash dashboard.

Displays position construction, margin requirements, EOD settlement P&L,
and best/worst case scenario analysis from grid search with basis drift.
"""

from dash import html, dcc, callback, Input, Output, no_update

from src.data_loader import (
    load_underlying_prices,
    load_options_data,
    load_bidask_data,
    get_symbol_dataframes,
)
from src.pricing import get_option_price_with_liquidity
from src.position import determine_leg_setup
from src.pnl import (
    calculate_option_pnl,
    calculate_settlement_value,
    calculate_best_worst_case_with_basis_drift,
)
from src.pages.components import (
    SECTION_STYLE, TABLE_STYLE, TH_STYLE, TD_STYLE, TD_RIGHT,
    POSITIVE_STYLE, NEGATIVE_STYLE, NEUTRAL_STYLE, WARNING_STYLE,
    COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_NEUTRAL,
    pnl_span,
)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout():
    """Return the Historical Analysis tab layout."""
    return html.Div([
        # Strategy selector — flex row with vertical centering
        html.Div([
            html.Label(
                "Strategy Type",
                style={'fontWeight': 'bold', 'marginRight': '10px', 'whiteSpace': 'nowrap'},
            ),
            html.Div(
                dcc.Dropdown(
                    id='strategy-select',
                    options=[
                        {'label': 'Full (Calls + Puts)', 'value': 'full'},
                        {'label': 'Calls Only', 'value': 'calls_only'},
                        {'label': 'Puts Only', 'value': 'puts_only'},
                    ],
                    value='full',
                    clearable=False,
                ),
                style={'width': '250px'},
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '20px'}),

        # Main analysis output
        dcc.Loading(html.Div(id='historical-analysis-output')),
    ])


# ---------------------------------------------------------------------------
# Helpers for building display components
# ---------------------------------------------------------------------------

def _pnl_span(value):
    """Return a styled span for a P&L dollar value."""
    return pnl_span(value)


def _price_info_cell(info, label):
    """Build a table cell with price + liquidity metadata."""
    if info is None:
        return html.Td(
            html.Span("No data", style={'color': '#dc3545'}),
            style=TD_RIGHT,
        )

    parts = [html.Span(f"${info['price']:.2f}")]

    source_label = "mid" if info['price_source'] == 'midpoint' else "trade"
    parts.append(html.Span(f" ({source_label})", style={'color': '#6c757d', 'fontSize': '12px'}))

    if info.get('liquidity_warning'):
        parts.append(html.Br())
        parts.append(html.Span(info['liquidity_warning'], style={'color': '#856404', 'fontSize': '11px'}))

    return html.Td(parts, style=TD_RIGHT)


def _build_position_table(position, price_infos):
    """Build the position legs table."""
    header = html.Tr([
        html.Th("Action", style=TH_STYLE),
        html.Th("Symbol", style=TH_STYLE),
        html.Th("Strike", style={**TH_STYLE, 'textAlign': 'right'}),
        html.Th("Right", style=TH_STYLE),
        html.Th("Qty", style={**TH_STYLE, 'textAlign': 'right'}),
        html.Th("Price", style={**TH_STYLE, 'textAlign': 'right'}),
        html.Th("Notional", style={**TH_STYLE, 'textAlign': 'right'}),
    ])

    rows = [header]
    for leg in position.legs:
        action_style = {'color': '#dc3545', 'fontWeight': 'bold'} if leg.action == 'SELL' else {'color': '#28a745'}
        key = (leg.symbol, leg.right, leg.action)
        info = price_infos.get(key)

        # Build price cell with liquidity info
        price_parts = [html.Span(f"${leg.entry_price:.2f}")]
        if info and info.get('price_source'):
            source_label = "mid" if info['price_source'] == 'midpoint' else "trade"
            price_parts.append(html.Span(f" ({source_label})", style={'color': '#6c757d', 'fontSize': '11px'}))
        if info and info.get('liquidity_warning'):
            price_parts.append(html.Br())
            price_parts.append(html.Span(info['liquidity_warning'], style={'color': '#856404', 'fontSize': '11px'}))

        notional = leg.entry_price * leg.quantity * 100
        rows.append(html.Tr([
            html.Td(leg.action, style={**TD_STYLE, **action_style}),
            html.Td(leg.symbol, style=TD_STYLE),
            html.Td(f"${leg.strike:.0f}", style=TD_RIGHT),
            html.Td("Call" if leg.right == 'C' else "Put", style=TD_STYLE),
            html.Td(str(leg.quantity), style=TD_RIGHT),
            html.Td(price_parts, style=TD_RIGHT),
            html.Td(f"${notional:,.0f}", style=TD_RIGHT),
        ]))

    return html.Table(rows, style=TABLE_STYLE)


def _build_credit_summary(position, show_calls, show_puts):
    """Build the credit and margin summary."""
    items = []

    if show_calls and show_puts:
        items.append(html.Div([
            html.Span("Call Credit: ", style={'fontWeight': 'bold'}),
            _pnl_span(position.call_credit),
        ]))
        items.append(html.Div([
            html.Span("Put Credit: ", style={'fontWeight': 'bold'}),
            _pnl_span(position.put_credit),
        ]))
        items.append(html.Hr(style={'margin': '8px 0'}))

    items.append(html.Div([
        html.Span("Total Credit: ", style={'fontWeight': 'bold', 'fontSize': '20px'}),
        html.Span(
            f"${position.total_credit:,.2f}" if position.total_credit >= 0 else f"-${abs(position.total_credit):,.2f}",
            style={
                'fontSize': '20px',
                'fontWeight': 'bold',
                'fontFamily': 'monospace',
                'color': COLOR_POSITIVE if position.total_credit >= 0 else COLOR_NEGATIVE,
            },
        ),
    ]))

    items.append(html.Div([
        html.Span("Estimated Margin: ", style={'fontWeight': 'bold'}),
        html.Span(f"${position.estimated_margin:,.0f}", style={'fontFamily': 'monospace'}),
    ], style={'marginTop': '8px'}))

    if position.estimated_margin > 0 and position.total_credit > 0:
        roi = (position.total_credit / position.estimated_margin) * 100
        items.append(html.Div([
            html.Span("ROI on Margin: ", style={'fontWeight': 'bold'}),
            html.Span(f"{roi:.2f}%", style={'fontFamily': 'monospace'}),
        ]))

    return html.Div(items)


def _build_settlement_table(position, eod_sym1_price, eod_sym2_price, sym1, sym2):
    """Build the EOD settlement P&L table."""
    header = html.Tr([
        html.Th("Leg", style=TH_STYLE),
        html.Th("Entry", style={**TH_STYLE, 'textAlign': 'right'}),
        html.Th("Settlement", style={**TH_STYLE, 'textAlign': 'right'}),
        html.Th("P&L", style={**TH_STYLE, 'textAlign': 'right'}),
    ])

    rows = [header]
    total_pnl = 0.0

    for leg in position.legs:
        # Determine which underlying price to use for settlement
        underlying_price = eod_sym1_price if leg.symbol == sym1 else eod_sym2_price
        settlement_val = calculate_settlement_value(underlying_price, leg.strike, leg.right)
        leg_pnl = calculate_option_pnl(leg.entry_price, settlement_val, leg.action, leg.quantity)
        total_pnl += leg_pnl

        right_label = "Call" if leg.right == 'C' else "Put"
        action_prefix = "Short" if leg.action == 'SELL' else "Long"
        leg_label = f"{action_prefix} {leg.symbol} {leg.strike:.0f} {right_label}"

        rows.append(html.Tr([
            html.Td(leg_label, style=TD_STYLE),
            html.Td(f"${leg.entry_price:.2f}", style=TD_RIGHT),
            html.Td(f"${settlement_val:.2f}", style=TD_RIGHT),
            html.Td(_pnl_span(leg_pnl), style={**TD_STYLE, 'textAlign': 'right'}),
        ]))

    # Total row
    rows.append(html.Tr([
        html.Td(html.Strong("TOTAL"), style={**TD_STYLE, 'borderTop': '2px solid #dee2e6'}),
        html.Td("", style={**TD_STYLE, 'borderTop': '2px solid #dee2e6'}),
        html.Td("", style={**TD_STYLE, 'borderTop': '2px solid #dee2e6'}),
        html.Td(
            html.Strong(_pnl_span(total_pnl)),
            style={**TD_STYLE, 'textAlign': 'right', 'borderTop': '2px solid #dee2e6'},
        ),
    ]))

    return html.Table(rows, style=TABLE_STYLE), total_pnl


def _build_scenario_block(label, scenario, sym1, sym2):
    """Build a best or worst case scenario display block."""
    if not scenario:
        return html.Div(f"No {label.lower()} data available.", style={'color': '#6c757d'})

    pnl = scenario['net_pnl']
    drift = scenario['basis_drift']
    bd = scenario.get('breakdown', {})

    items = [
        html.Div([
            html.Span(f"{label} P&L: ", style={'fontWeight': 'bold', 'fontSize': '18px'}),
            html.Span(
                f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}",
                style={
                    'fontSize': '18px',
                    'fontWeight': 'bold',
                    'fontFamily': 'monospace',
                    'color': COLOR_POSITIVE if pnl >= 0 else COLOR_NEGATIVE,
                },
            ),
        ]),
        html.Div([
            html.Span(f"{sym1}: ", style={'fontWeight': 'bold'}),
            html.Span(f"${scenario['spy_price']:,.2f}", style={'fontFamily': 'monospace'}),
            html.Span(f"  |  {sym2}: ", style={'fontWeight': 'bold', 'marginLeft': '12px'}),
            html.Span(f"${scenario['spx_price']:,.2f}", style={'fontFamily': 'monospace'}),
            html.Span(f"  |  Basis drift: ", style={'fontWeight': 'bold', 'marginLeft': '12px'}),
            html.Span(f"{drift:+.3f}%", style={'fontFamily': 'monospace'}),
        ], style={'marginTop': '6px', 'fontSize': '13px'}),
    ]

    # Credit vs settlement cost breakdown
    if bd:
        total_credit = bd.get('total_credit', 0)
        total_settle = bd.get('total_settlement_cost', 0)
        items.append(html.Div([
            html.Span("Credit collected: ", style={'fontSize': '13px'}),
            html.Span(f"${total_credit:,.2f}", style={'fontFamily': 'monospace', 'fontSize': '13px'}),
            html.Span("  |  Settlement cost: ", style={'fontSize': '13px', 'marginLeft': '12px'}),
            html.Span(f"${total_settle:,.2f}", style={'fontFamily': 'monospace', 'fontSize': '13px'}),
        ], style={'marginTop': '4px'}))

    return html.Div(items)


# ---------------------------------------------------------------------------
# Main callback
# ---------------------------------------------------------------------------

@callback(
    Output('historical-analysis-output', 'children'),
    Input('config-store', 'data'),
    Input('strategy-select', 'value'),
    Input('main-tabs', 'value'),
)
def update_historical_analysis(config, strategy_type, active_tab):
    """
    Main callback: load data, build position, calculate P&L, render everything.
    """
    if active_tab != 'historical':
        return no_update

    if not config or not config.get('date'):
        return html.Div(
            "Configure date, pair, and strikes in the sidebar to begin analysis.",
            style={'color': '#6c757d', 'padding': '40px', 'textAlign': 'center'},
        )

    try:
        return _run_historical_analysis(config, strategy_type)
    except Exception as e:
        import traceback
        return html.Div([
            html.P(f"Analysis error: {e}", style={'color': '#dc3545'}),
            html.Pre(traceback.format_exc(), style={'fontSize': '11px'}),
        ])


def _run_historical_analysis(config, strategy_type):
    """Core historical analysis logic, extracted for exception handling."""
    # -----------------------------------------------------------------------
    # Unpack config
    # -----------------------------------------------------------------------
    date_str = config['date']
    sym1 = config['sym1']
    sym2 = config['sym2']
    qty_ratio = config['qty_ratio']
    entry_time_idx = config['entry_time_idx']
    sym1_strike = config.get('sym1_strike')
    sym2_strike = config.get('sym2_strike')
    call_direction = config.get('call_direction')
    put_direction = config.get('put_direction')
    entry_sym1_price = config.get('entry_sym1_price')
    entry_sym2_price = config.get('entry_sym2_price')
    entry_time_label = config.get('entry_time_label', '')

    if sym1_strike is None or sym2_strike is None:
        return html.Div("Set strikes in the sidebar.", style={'color': '#6c757d'})

    show_calls = strategy_type in ('full', 'calls_only')
    show_puts = strategy_type in ('full', 'puts_only')

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------
    try:
        df_underlying = load_underlying_prices(date_str)
        df_options = load_options_data(date_str)
        df_bidask = load_bidask_data(date_str)
    except FileNotFoundError as e:
        return html.Div(f"Data error: {e}", style={'color': '#dc3545'})

    sym1_df, sym2_df = get_symbol_dataframes(df_underlying, sym1, sym2)
    if sym1_df.empty or sym2_df.empty:
        return html.Div("No underlying data for selected symbols.", style={'color': '#dc3545'})

    entry_time_idx = min(entry_time_idx, len(sym1_df) - 1)
    entry_time = sym1_df.iloc[entry_time_idx]['time']

    # -----------------------------------------------------------------------
    # Look up option prices
    # -----------------------------------------------------------------------
    if df_options is None and df_bidask is None:
        return html.Div(
            "No options data available for this date. Collect data first.",
            style={'color': '#dc3545'},
        )

    sym1_call_info = get_option_price_with_liquidity(df_options, df_bidask, sym1, sym1_strike, 'C', entry_time)
    sym2_call_info = get_option_price_with_liquidity(df_options, df_bidask, sym2, sym2_strike, 'C', entry_time)
    sym1_put_info = get_option_price_with_liquidity(df_options, df_bidask, sym1, sym1_strike, 'P', entry_time)
    sym2_put_info = get_option_price_with_liquidity(df_options, df_bidask, sym2, sym2_strike, 'P', entry_time)

    # Check for missing data
    warnings = []
    price_infos = {}  # keyed by (symbol, right, action) for display lookup

    def _extract_price(info, label):
        if info is None:
            warnings.append(f"{label}: No data found")
            return 0.0
        if info.get('is_stale'):
            warnings.append(f"{label}: {info.get('liquidity_warning', 'Stale price')}")
        elif info.get('liquidity_warning'):
            warnings.append(f"{label}: {info['liquidity_warning']}")
        return info['price']

    sym1_call_price = _extract_price(sym1_call_info, f"{sym1} {sym1_strike} Call")
    sym2_call_price = _extract_price(sym2_call_info, f"{sym2} {sym2_strike} Call")
    sym1_put_price = _extract_price(sym1_put_info, f"{sym1} {sym1_strike} Put")
    sym2_put_price = _extract_price(sym2_put_info, f"{sym2} {sym2_strike} Put")

    # -----------------------------------------------------------------------
    # Build position
    # -----------------------------------------------------------------------
    position = determine_leg_setup(
        call_direction=call_direction or f"Buy {sym2}, Sell {sym1}",
        put_direction=put_direction or f"Buy {sym1}, Sell {sym2}",
        sym1=sym1,
        sym2=sym2,
        qty_ratio=qty_ratio,
        sym1_strike=sym1_strike,
        sym2_strike=sym2_strike,
        sym1_call_price=sym1_call_price,
        sym2_call_price=sym2_call_price,
        sym1_put_price=sym1_put_price,
        sym2_put_price=sym2_put_price,
        show_calls=show_calls,
        show_puts=show_puts,
    )

    # Map price infos to legs for display
    for leg in position.legs:
        if leg.symbol == sym1 and leg.right == 'C':
            price_infos[(leg.symbol, leg.right, leg.action)] = sym1_call_info
        elif leg.symbol == sym2 and leg.right == 'C':
            price_infos[(leg.symbol, leg.right, leg.action)] = sym2_call_info
        elif leg.symbol == sym1 and leg.right == 'P':
            price_infos[(leg.symbol, leg.right, leg.action)] = sym1_put_info
        elif leg.symbol == sym2 and leg.right == 'P':
            price_infos[(leg.symbol, leg.right, leg.action)] = sym2_put_info

    # -----------------------------------------------------------------------
    # EOD settlement P&L
    # -----------------------------------------------------------------------
    eod_sym1_price = sym1_df.iloc[-1]['close']
    eod_sym2_price = sym2_df.iloc[-1]['close']

    settlement_table, total_eod_pnl = _build_settlement_table(
        position, eod_sym1_price, eod_sym2_price, sym1, sym2,
    )

    # -----------------------------------------------------------------------
    # Best/worst case grid search
    # -----------------------------------------------------------------------
    # Extract sell/buy prices and quantities for the grid search function
    sell_call_price = 0.0
    buy_call_price = 0.0
    sell_calls_qty = 0
    buy_calls_qty = 0
    sell_put_price = 0.0
    buy_put_price = 0.0
    sell_puts_qty = 0
    buy_puts_qty = 0

    for leg in position.legs:
        if leg.right == 'C' and leg.action == 'SELL':
            sell_call_price = leg.entry_price
            sell_calls_qty = leg.quantity
        elif leg.right == 'C' and leg.action == 'BUY':
            buy_call_price = leg.entry_price
            buy_calls_qty = leg.quantity
        elif leg.right == 'P' and leg.action == 'SELL':
            sell_put_price = leg.entry_price
            sell_puts_qty = leg.quantity
        elif leg.right == 'P' and leg.action == 'BUY':
            buy_put_price = leg.entry_price
            buy_puts_qty = leg.quantity

    best_case, worst_case = calculate_best_worst_case_with_basis_drift(
        entry_spy_price=entry_sym1_price,
        entry_spx_price=entry_sym2_price,
        spy_strike=sym1_strike,
        spx_strike=sym2_strike,
        call_direction=call_direction or f"Buy {sym2}, Sell {sym1}",
        put_direction=put_direction or f"Buy {sym1}, Sell {sym2}",
        sell_call_price=sell_call_price,
        buy_call_price=buy_call_price,
        sell_calls_qty=sell_calls_qty,
        buy_calls_qty=buy_calls_qty,
        sell_put_price=sell_put_price,
        buy_put_price=buy_put_price,
        sell_puts_qty=sell_puts_qty,
        buy_puts_qty=buy_puts_qty,
        show_calls=show_calls,
        show_puts=show_puts,
        sym1=sym1,
        sym2=sym2,
    )

    # -----------------------------------------------------------------------
    # Assemble output
    # -----------------------------------------------------------------------
    sections = []

    # Warnings
    if warnings:
        sections.append(
            html.Div(
                [html.Div(w) for w in warnings],
                style=WARNING_STYLE,
            )
        )

    # Section 1: Position
    strategy_label = {'full': 'Full (Calls + Puts)', 'calls_only': 'Calls Only', 'puts_only': 'Puts Only'}
    sections.append(
        html.Div([
            html.H4(f"Position  --  {strategy_label.get(strategy_type, strategy_type)}"),
            html.Div(
                f"Entry: {entry_time_label}  |  "
                f"{sym1}: ${entry_sym1_price:.2f}  |  {sym2}: ${entry_sym2_price:.2f}  |  "
                f"Strikes: {sym1} ${sym1_strike:.0f} / {sym2} ${sym2_strike:.0f}",
                style={'fontSize': '13px', 'color': '#6c757d', 'marginBottom': '12px'},
            ),
            _build_position_table(position, price_infos),
        ], style=SECTION_STYLE)
    )

    # Section 2: Credit & Margin
    sections.append(
        html.Div([
            html.H4("Credit & Margin"),
            _build_credit_summary(position, show_calls, show_puts),
        ], style=SECTION_STYLE)
    )

    # Section 3: EOD Settlement P&L
    sections.append(
        html.Div([
            html.H4("EOD Settlement P&L"),
            html.Div(
                f"Settlement prices  --  {sym1}: ${eod_sym1_price:.2f}  |  {sym2}: ${eod_sym2_price:.2f}",
                style={'fontSize': '13px', 'color': '#6c757d', 'marginBottom': '12px'},
            ),
            settlement_table,
        ], style=SECTION_STYLE)
    )

    # Section 4: Scenario Analysis
    sections.append(
        html.Div([
            html.H4("Scenario Analysis (Grid Search)"),
            html.Div(
                "50 price points x 3 basis drift levels = 150 scenarios",
                style={'fontSize': '13px', 'color': '#6c757d', 'marginBottom': '16px'},
            ),
            html.Div([
                html.Div([
                    _build_scenario_block("Best Case", best_case, sym1, sym2),
                ], style={'flex': '1', 'padding': '12px', 'backgroundColor': '#d4edda', 'borderRadius': '6px'}),
                html.Div(style={'width': '16px'}),
                html.Div([
                    _build_scenario_block("Worst Case", worst_case, sym1, sym2),
                ], style={'flex': '1', 'padding': '12px', 'backgroundColor': '#f8d7da', 'borderRadius': '6px'}),
            ], style={'display': 'flex'}),
            # Risk/reward summary
            _build_risk_reward_summary(position, best_case, worst_case),
        ], style=SECTION_STYLE)
    )

    return html.Div(sections)


def _build_risk_reward_summary(position, best_case, worst_case):
    """Build a compact risk/reward summary below the scenario blocks."""
    if not worst_case or not best_case:
        return html.Div()

    worst_pnl = worst_case.get('net_pnl', 0)
    best_pnl = best_case.get('net_pnl', 0)
    credit = position.total_credit
    margin = position.estimated_margin

    items = [html.Hr(style={'margin': '16px 0'})]

    # Credit vs worst case
    if worst_pnl < 0:
        risk_reward = credit / abs(worst_pnl) if credit > 0 else 0
        items.append(html.Div([
            html.Span("Risk/Reward: ", style={'fontWeight': 'bold'}),
            html.Span(
                f"{risk_reward:.2f}x" if risk_reward > 0 else "N/A",
                style={'fontFamily': 'monospace'},
            ),
            html.Span(
                f"  (credit ${credit:,.2f} vs max loss ${abs(worst_pnl):,.2f})",
                style={'color': '#6c757d', 'fontSize': '13px', 'marginLeft': '8px'},
            ),
        ]))

    # ROI on margin at worst/best case
    if margin > 0:
        worst_roi = (worst_pnl / margin) * 100
        best_roi = (best_pnl / margin) * 100
        items.append(html.Div([
            html.Span("Margin ROI range: ", style={'fontWeight': 'bold'}),
            html.Span(
                f"{worst_roi:+.2f}% to {best_roi:+.2f}%",
                style={'fontFamily': 'monospace'},
            ),
        ], style={'marginTop': '4px'}))

    return html.Div(items)
