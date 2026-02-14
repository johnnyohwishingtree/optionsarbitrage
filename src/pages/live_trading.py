"""
Live Paper Trading page — Tab 2.

Connects to IB Gateway to show account summary, current positions,
estimated P&L (mark-to-market and settlement), and a risk profile chart.
Uses dcc.Interval for auto-refresh.
"""

from dash import html, dcc, callback, Input, Output, State, no_update
import plotly.graph_objects as go

from src.config import IB_HOST, IB_PORT


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

SECTION_STYLE = {
    'border': '1px solid #dee2e6',
    'borderRadius': '6px',
    'padding': '16px',
    'marginBottom': '20px',
    'backgroundColor': '#ffffff',
}

METRIC_STYLE = {
    'display': 'inline-block',
    'minWidth': '150px',
    'padding': '10px',
    'textAlign': 'center',
}


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout():
    return html.Div([
        html.H3("Live Paper Trading"),
        html.P("Real-time positions from IB Gateway paper trading account"),

        # Controls
        html.Div([
            html.Button(
                'Refresh',
                id='live-refresh-btn',
                n_clicks=0,
                style={
                    'padding': '8px 20px',
                    'backgroundColor': '#007bff',
                    'color': 'white',
                    'border': 'none',
                    'borderRadius': '4px',
                    'cursor': 'pointer',
                    'marginRight': '15px',
                },
            ),
            html.Span(id='live-last-updated', style={'color': '#6c757d', 'fontSize': '13px'}),
        ], style={'marginBottom': '15px'}),

        # Auto-refresh toggle
        dcc.Checklist(
            id='live-auto-refresh-toggle',
            options=[{'label': ' Auto-refresh every 30s', 'value': 'on'}],
            value=[],
            style={'marginBottom': '15px', 'fontSize': '13px'},
        ),
        dcc.Interval(id='live-refresh-interval', interval=30_000, disabled=True),

        # Main content
        dcc.Loading(html.Div(id='live-trading-content')),
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output('live-refresh-interval', 'disabled'),
    Input('live-auto-refresh-toggle', 'value'),
)
def toggle_auto_refresh(toggle_val):
    return 'on' not in (toggle_val or [])


@callback(
    Output('live-trading-content', 'children'),
    Output('live-last-updated', 'children'),
    Input('live-refresh-btn', 'n_clicks'),
    Input('live-refresh-interval', 'n_intervals'),
    State('config-store', 'data'),
)
def update_live_trading(n_clicks, n_intervals, config):
    from datetime import datetime
    import pytz

    et_tz = pytz.timezone('America/New_York')
    now_et = datetime.now(et_tz)
    timestamp = f"Last updated: {now_et.strftime('%I:%M:%S %p ET')}"

    # Determine symbol pair from config (or defaults)
    sym1 = config.get('sym1', 'SPY') if config else 'SPY'
    sym2 = config.get('sym2', 'SPX') if config else 'SPX'

    try:
        from src.broker.ibkr_client import IBKRClient

        client = IBKRClient(host=IB_HOST, port=IB_PORT, client_id=998)

        if not client.connect():
            return html.Div([
                html.Div("Failed to connect to IB Gateway", style={'color': '#dc3545', 'fontWeight': 'bold'}),
                html.P(
                    f"Make sure IB Gateway is running on {IB_HOST}:{IB_PORT} (Paper Trading)",
                    style={'color': '#6c757d'},
                ),
            ], style=SECTION_STYLE), timestamp

        sections = []

        # --- Account Summary ---
        account = client.get_account_summary()
        sections.append(html.Div([
            html.H4("Account Summary"),
            html.Div([
                _metric_card("Net Liquidation", f"${account.get('net_liquidation', 0):,.2f}"),
                _metric_card("Available Funds", f"${account.get('available_funds', 0):,.2f}"),
                _metric_card("Buying Power", f"${account.get('buying_power', 0):,.2f}"),
            ], style={'display': 'flex', 'gap': '10px'}),
        ], style=SECTION_STYLE))

        # --- Current Prices ---
        sym1_price = client.get_current_price(sym1)
        sym2_price = client.get_current_price(sym2)
        sections.append(html.Div([
            html.H4("Current Market Prices"),
            html.Div([
                _metric_card(sym1, f"${sym1_price:.2f}" if sym1_price else "N/A"),
                _metric_card(sym2, f"${sym2_price:.2f}" if sym2_price else "N/A"),
            ], style={'display': 'flex', 'gap': '10px'}),
            _time_to_close_display(now_et),
        ], style=SECTION_STYLE))

        # --- Positions ---
        positions = client.get_positions()

        if not positions:
            sections.append(html.Div([
                html.H4("Positions"),
                html.P("No open positions", style={'color': '#6c757d'}),
            ], style=SECTION_STYLE))
        else:
            option_positions = [p for p in positions if p['sec_type'] == 'OPT']
            stock_positions = [p for p in positions if p['sec_type'] == 'STK']

            if option_positions:
                sections.append(_build_options_section(option_positions))

                # Settlement P&L
                if sym1_price and sym2_price:
                    sections.append(
                        _build_settlement_pnl(option_positions, sym1, sym2, sym1_price, sym2_price)
                    )

                    # P&L chart
                    sections.append(
                        _build_pnl_chart(option_positions, sym1, sym2, sym1_price, sym2_price)
                    )

            if stock_positions:
                sections.append(_build_stocks_section(stock_positions))

        client.disconnect()
        return html.Div(sections), timestamp

    except ImportError:
        return html.Div([
            html.Div("IB Gateway client not available", style={'color': '#856404', 'fontWeight': 'bold'}),
            html.P(
                "Install ib_insync or ib_async to use live trading features.",
                style={'color': '#6c757d'},
            ),
        ], style=SECTION_STYLE), timestamp

    except Exception as e:
        import traceback
        return html.Div([
            html.P(f"Error: {e}", style={'color': '#dc3545'}),
            html.Pre(traceback.format_exc(), style={'fontSize': '11px'}),
        ], style=SECTION_STYLE), timestamp


# ---------------------------------------------------------------------------
# Helper components
# ---------------------------------------------------------------------------

def _metric_card(label, value):
    return html.Div([
        html.Div(label, style={'fontSize': '12px', 'color': '#6c757d'}),
        html.Div(value, style={'fontSize': '20px', 'fontWeight': 'bold', 'fontFamily': 'monospace'}),
    ], style=METRIC_STYLE)


def _time_to_close_display(now_et):
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    delta = market_close - now_et

    if delta.total_seconds() > 0:
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return html.Div(
            f"Time to market close: {hours}h {minutes}m",
            style={'marginTop': '10px', 'color': '#17a2b8', 'fontWeight': 'bold'},
        )
    return html.Div("Market closed", style={'marginTop': '10px', 'color': '#6c757d'})


def _build_options_section(option_positions):
    header = html.Tr([
        html.Th("Symbol"), html.Th("Strike"), html.Th("Right"),
        html.Th("Expiry"), html.Th("Position"), html.Th("Avg Cost"),
        html.Th("Market Value"), html.Th("Unrealized P&L"),
    ])

    rows = [header]
    for pos in option_positions:
        contract = pos['contract']
        position_size = int(pos.get('position', 0))
        avg_cost = pos.get('avg_cost', 0)
        market_value = pos.get('market_value', 0)
        unrealized = pos.get('unrealized_pnl')

        rows.append(html.Tr([
            html.Td(contract.symbol),
            html.Td(f"${contract.strike:.0f}"),
            html.Td("Call" if contract.right == 'C' else "Put"),
            html.Td(getattr(contract, 'lastTradeDateOrContractMonth', 'N/A')),
            html.Td(
                f"{position_size:+d}",
                style={'color': '#dc3545' if position_size < 0 else '#28a745', 'fontWeight': 'bold'},
            ),
            html.Td(f"${avg_cost / 100:.2f}"),
            html.Td(f"${market_value:,.2f}" if market_value else "N/A"),
            html.Td(
                f"${unrealized:,.2f}" if unrealized is not None else "N/A",
                style={
                    'color': '#28a745' if unrealized and unrealized > 0
                    else '#dc3545' if unrealized and unrealized < 0
                    else '#6c757d',
                },
            ),
        ]))

    total_unrealized = sum(
        p.get('unrealized_pnl', 0) for p in option_positions
        if p.get('unrealized_pnl') is not None
    )

    return html.Div([
        html.H4("Option Positions"),
        html.Table(rows, style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'}),
        html.Div([
            html.Span("IB Reported Total P&L: ", style={'fontWeight': 'bold'}),
            html.Span(f"${total_unrealized:,.2f}", style={
                'fontWeight': 'bold',
                'color': '#28a745' if total_unrealized >= 0 else '#dc3545',
            }),
        ], style={'marginTop': '12px'}),
    ], style=SECTION_STYLE)


def _build_stocks_section(stock_positions):
    header = html.Tr([
        html.Th("Symbol"), html.Th("Position"), html.Th("Avg Cost"),
        html.Th("Market Value"), html.Th("Unrealized P&L"),
    ])

    rows = [header]
    for pos in stock_positions:
        contract = pos['contract']
        rows.append(html.Tr([
            html.Td(contract.symbol),
            html.Td(str(int(pos.get('position', 0)))),
            html.Td(f"${pos.get('avg_cost', 0):.2f}"),
            html.Td(f"${pos.get('market_value', 0):,.2f}" if pos.get('market_value') else "N/A"),
            html.Td(
                f"${pos.get('unrealized_pnl', 0):,.2f}" if pos.get('unrealized_pnl') is not None else "N/A",
            ),
        ]))

    return html.Div([
        html.H4("Stock Positions"),
        html.Div(
            "Stock positions detected - may indicate option assignment",
            style={'color': '#856404', 'backgroundColor': '#fff3cd', 'padding': '8px', 'borderRadius': '4px', 'marginBottom': '10px'},
        ),
        html.Table(rows, style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'}),
    ], style=SECTION_STYLE)


def _build_settlement_pnl(option_positions, sym1, sym2, sym1_price, sym2_price):
    header = html.Tr([
        html.Th("Contract"), html.Th("Position"), html.Th("Entry"),
        html.Th("Intrinsic"), html.Th("Est. P&L"),
    ])

    rows = [header]
    total_pnl = 0.0

    for pos in option_positions:
        contract = pos['contract']
        position_size = pos.get('position', 0)
        avg_cost_per_share = pos.get('avg_cost', 0) / 100

        underlying = sym1_price if contract.symbol == sym1 else sym2_price

        if contract.right == 'C':
            intrinsic = max(0, underlying - contract.strike)
        else:
            intrinsic = max(0, contract.strike - underlying)

        if position_size < 0:
            pnl = (avg_cost_per_share - intrinsic) * abs(position_size) * 100
        else:
            pnl = (intrinsic - avg_cost_per_share) * position_size * 100

        total_pnl += pnl

        label = f"{contract.symbol} {contract.strike:.0f}{'C' if contract.right == 'C' else 'P'}"
        rows.append(html.Tr([
            html.Td(label),
            html.Td(str(int(position_size))),
            html.Td(f"${avg_cost_per_share:.2f}"),
            html.Td(f"${intrinsic:.2f}"),
            html.Td(
                f"${pnl:,.2f}",
                style={'color': '#28a745' if pnl >= 0 else '#dc3545', 'fontWeight': 'bold'},
            ),
        ]))

    return html.Div([
        html.H4("Estimated P&L If Market Closes Now"),
        html.P(
            f"Based on intrinsic value at current prices: {sym1} ${sym1_price:.2f}, {sym2} ${sym2_price:.2f}",
            style={'fontSize': '13px', 'color': '#6c757d'},
        ),
        html.Table(rows, style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'}),
        html.Div([
            html.Span("Net Settlement P&L: ", style={'fontWeight': 'bold', 'fontSize': '16px'}),
            html.Span(
                f"${total_pnl:,.2f}",
                style={
                    'fontSize': '16px', 'fontWeight': 'bold',
                    'color': '#28a745' if total_pnl >= 0 else '#dc3545',
                },
            ),
        ], style={'marginTop': '12px'}),
    ], style=SECTION_STYLE)


def _build_pnl_chart(option_positions, sym1, sym2, sym1_price, sym2_price):
    import numpy as np

    # Use strike prices as reference for stable chart
    sym1_strikes = [p['contract'].strike for p in option_positions if p['contract'].symbol == sym1]
    sym2_strikes = [p['contract'].strike for p in option_positions if p['contract'].symbol == sym2]
    ref_sym1 = sym1_strikes[0] if sym1_strikes else sym1_price
    ref_sym2 = sym2_strikes[0] if sym2_strikes else sym2_price

    sym1_range = np.linspace(ref_sym1 * 0.97, ref_sym1 * 1.03, 100)
    sym2_range = sym1_range * (ref_sym2 / ref_sym1)

    pnl_values = []
    for s1_px, s2_px in zip(sym1_range, sym2_range):
        total = 0.0
        for pos in option_positions:
            contract = pos['contract']
            position_size = pos.get('position', 0)
            avg_cost_per_share = pos.get('avg_cost', 0) / 100

            underlying = s1_px if contract.symbol == sym1 else s2_px

            if contract.right == 'C':
                intrinsic = max(0, underlying - contract.strike)
            else:
                intrinsic = max(0, contract.strike - underlying)

            if position_size < 0:
                pnl = (avg_cost_per_share - intrinsic) * abs(position_size) * 100
            else:
                pnl = (intrinsic - avg_cost_per_share) * position_size * 100

            total += pnl
        pnl_values.append(total)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sym1_range.tolist(), y=pnl_values,
        mode='lines', name='Total P&L',
        line=dict(color='#007bff', width=2),
        fill='tozeroy',
        fillcolor='rgba(0,123,255,0.1)',
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)

    # Mark current price
    if sym1_price:
        fig.add_vline(x=sym1_price, line_dash="dot", line_color="orange", line_width=1,
                       annotation_text=f"Current {sym1}")

    fig.update_layout(
        title=f"P&L Across {sym1} Price Range",
        xaxis_title=f"{sym1} Price ($)",
        yaxis_title="P&L ($)",
        height=400,
        hovermode='x unified',
    )

    return html.Div([
        html.H4("P&L Across Price Range"),
        html.P("Risk profile visualization for current positions",
               style={'fontSize': '13px', 'color': '#6c757d'}),
        dcc.Graph(figure=fig),
    ], style=SECTION_STYLE)
