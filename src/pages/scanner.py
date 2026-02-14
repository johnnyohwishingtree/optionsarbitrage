"""
Strike Scanner page for finding arbitrage opportunities.

Scans all matching strike pairs for the selected symbol pair and date,
ranks them by safety, profit, or risk/reward, and lets the user apply
a result back to the sidebar for full analysis.
"""

from dataclasses import asdict

from dash import html, dcc, callback, Input, Output, State, no_update, dash_table

from src.scanner_engine import scan_all_pairs, rank_results
from src.data_loader import (
    load_underlying_prices,
    load_options_data,
    load_bidask_data,
    get_symbol_dataframes,
)
from src.config import DEFAULT_MIN_VOLUME


# Column definitions for the results DataTable
SCAN_COLUMNS = [
    {'name': 'SYM1 Strike', 'id': 'sym1_strike', 'type': 'numeric'},
    {'name': 'SYM2 Strike', 'id': 'sym2_strike', 'type': 'numeric'},
    {'name': 'Moneyness', 'id': 'moneyness', 'type': 'text'},
    {'name': 'Direction', 'id': 'direction', 'type': 'text'},
    {'name': 'Credit ($)', 'id': 'credit', 'type': 'numeric', 'format': {'specifier': ',.2f'}},
    {'name': 'Worst Case ($)', 'id': 'worst_case_pnl', 'type': 'numeric', 'format': {'specifier': ',.2f'}},
    {'name': 'Risk/Reward', 'id': 'risk_reward', 'type': 'numeric', 'format': {'specifier': '.2f'}},
    {'name': 'Max Gap', 'id': 'max_gap', 'type': 'numeric', 'format': {'specifier': '.4f'}},
    {'name': 'Gap Time', 'id': 'max_gap_time', 'type': 'text'},
    {'name': 'Best Entry', 'id': 'best_wc_time', 'type': 'text'},
    {'name': 'SYM1 Vol', 'id': 'sym1_vol', 'type': 'numeric'},
    {'name': 'SYM2 Vol', 'id': 'sym2_vol', 'type': 'numeric'},
    {'name': 'Liquidity', 'id': 'liquidity', 'type': 'text'},
    {'name': 'Price Src', 'id': 'price_source', 'type': 'text'},
]


def _make_table(table_id: str) -> dash_table.DataTable:
    """Create a DataTable with shared styling for a ranking tab."""
    return dash_table.DataTable(
        id=table_id,
        columns=SCAN_COLUMNS,
        data=[],
        page_size=25,
        sort_action='native',
        filter_action='native',
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'center',
            'padding': '8px',
            'fontSize': '13px',
            'minWidth': '70px',
        },
        style_header={
            'backgroundColor': '#f8f9fa',
            'fontWeight': 'bold',
            'borderBottom': '2px solid #dee2e6',
        },
        style_data_conditional=[
            {
                'if': {'filter_query': '{worst_case_pnl} >= 0'},
                'backgroundColor': '#d4edda',
            },
            {
                'if': {'filter_query': '{worst_case_pnl} < -500'},
                'backgroundColor': '#f8d7da',
            },
            {
                'if': {'filter_query': '{liquidity} = "LOW"'},
                'color': '#856404',
            },
            {
                'if': {'state': 'active'},
                'backgroundColor': '#cce5ff',
                'border': '1px solid #b8daff',
            },
        ],
        row_selectable=False,
        cell_selectable=True,
    )


def layout():
    """Return the scanner tab layout."""
    return html.Div([
        html.H3("Strike Scanner"),
        html.P(
            "Scan all matching strike pairs for arbitrage opportunities. "
            "Click any row to apply it to the sidebar for full analysis.",
            style={'color': '#6c757d'},
        ),

        # Controls row
        html.Div([
            # Option type
            html.Div([
                html.Label("Option Type"),
                dcc.Dropdown(
                    id='scanner-right-select',
                    options=[
                        {'label': 'Puts', 'value': 'P'},
                        {'label': 'Calls', 'value': 'C'},
                    ],
                    value='P',
                    clearable=False,
                    style={'width': '120px'},
                ),
            ], style={'display': 'inline-block', 'marginRight': '20px', 'verticalAlign': 'top'}),

            # Min volume
            html.Div([
                html.Label("Min Volume"),
                dcc.Input(
                    id='scanner-min-volume',
                    type='number',
                    value=DEFAULT_MIN_VOLUME,
                    min=0,
                    step=1,
                    style={'width': '80px'},
                ),
            ], style={'display': 'inline-block', 'marginRight': '20px', 'verticalAlign': 'top'}),

            # Hide illiquid
            html.Div([
                dcc.Checklist(
                    id='scanner-hide-illiquid',
                    options=[{'label': ' Hide illiquid contracts', 'value': 'hide'}],
                    value=['hide'],
                    style={'marginTop': '24px'},
                ),
            ], style={'display': 'inline-block', 'marginRight': '20px', 'verticalAlign': 'top'}),

            # Scan button
            html.Div([
                html.Button(
                    'Scan',
                    id='scan-button',
                    n_clicks=0,
                    style={
                        'marginTop': '20px',
                        'padding': '8px 24px',
                        'backgroundColor': '#007bff',
                        'color': 'white',
                        'border': 'none',
                        'borderRadius': '4px',
                        'cursor': 'pointer',
                        'fontSize': '14px',
                    },
                ),
            ], style={'display': 'inline-block', 'verticalAlign': 'top'}),
        ], style={'marginBottom': '20px'}),

        # Status line
        html.Div(id='scanner-status', style={'marginBottom': '10px'}),

        # Results with loading spinner
        dcc.Loading(
            id='scanner-loading',
            type='default',
            children=[
                # Hidden store for raw scan results (all rows as dicts)
                dcc.Store(id='scanner-results-store', data=[]),

                # Tabs for different ranking views
                html.Div(
                    id='scanner-results-section',
                    style={'display': 'none'},
                    children=[
                        dcc.Tabs(
                            id='scanner-rank-tabs',
                            value='safety',
                            children=[
                                dcc.Tab(label='Ranked by Safety', value='safety'),
                                dcc.Tab(label='Ranked by Profit', value='profit'),
                                dcc.Tab(label='Ranked by Risk/Reward', value='risk_reward'),
                            ],
                        ),
                        html.Div(id='scanner-table-container', style={'marginTop': '10px'}),
                    ],
                ),
            ],
        ),
    ])


@callback(
    Output('scanner-results-store', 'data'),
    Output('scanner-status', 'children'),
    Output('scanner-results-section', 'style'),
    Input('scan-button', 'n_clicks'),
    State('config-store', 'data'),
    State('scanner-right-select', 'value'),
    State('scanner-min-volume', 'value'),
    State('scanner-hide-illiquid', 'value'),
    prevent_initial_call=True,
)
def run_scan(n_clicks, config, scanner_right, min_volume, hide_illiquid_val):
    """Execute the strike scanner when the Scan button is clicked."""
    if not n_clicks or not config or not config.get('date'):
        return no_update, no_update, no_update

    date_str = config['date']
    sym1 = config['sym1']
    sym2 = config['sym2']
    qty_ratio = config['qty_ratio']

    hide_illiquid = 'hide' in (hide_illiquid_val or [])
    min_vol = int(min_volume) if min_volume else DEFAULT_MIN_VOLUME

    # Load data
    try:
        df_underlying = load_underlying_prices(date_str)
        df_options = load_options_data(date_str)
        df_bidask = load_bidask_data(date_str)
    except FileNotFoundError as e:
        return [], html.Div(str(e), style={'color': 'red'}), {'display': 'none'}

    if df_options is None and df_bidask is None:
        return [], html.Div(
            "No options data available for this date.",
            style={'color': 'red'},
        ), {'display': 'none'}

    sym1_df, sym2_df = get_symbol_dataframes(df_underlying, sym1, sym2)

    if sym1_df.empty or sym2_df.empty:
        return [], html.Div(
            f"No underlying data for {sym1} or {sym2}.",
            style={'color': 'red'},
        ), {'display': 'none'}

    # Determine data source: prefer TRADES, fall back to BID_ASK
    if df_options is not None:
        has_volume = True
        price_col = 'open'
    else:
        has_volume = False
        price_col = 'midpoint'

    # Open prices and ratio
    open_sym1 = sym1_df.iloc[0]['close']
    open_sym2 = sym2_df.iloc[0]['close']
    open_ratio = open_sym2 / open_sym1

    # Run scan
    results = scan_all_pairs(
        df_options=df_options,
        df_bidask=df_bidask,
        sym1_df=sym1_df,
        sym2_df=sym2_df,
        sym1=sym1,
        sym2=sym2,
        scanner_right=scanner_right,
        open_ratio=open_ratio,
        open_sym1=open_sym1,
        open_sym2=open_sym2,
        qty_ratio=qty_ratio,
        has_volume=has_volume,
        price_col=price_col,
        min_volume=min_vol,
        hide_illiquid=hide_illiquid,
    )

    if not results:
        return [], html.Div(
            "No results found. Try lowering min volume or unchecking 'Hide illiquid'.",
            style={'color': '#856404'},
        ), {'display': 'none'}

    # Convert to dicts for storage
    right_label = 'Puts' if scanner_right == 'P' else 'Calls'
    result_dicts = []
    for r in results:
        d = asdict(r)
        # Cap risk_reward for display (inf -> 999.99)
        if d['risk_reward'] == float('inf') or d['risk_reward'] > 999.99:
            d['risk_reward'] = 999.99
        result_dicts.append(d)

    status = html.Div([
        html.Strong(f"Found {len(result_dicts)} {right_label.lower()} pair(s)"),
        html.Span(
            f" | {sym1}/{sym2} | {date_str} | "
            f"Source: {'TRADES + BID_ASK' if has_volume and df_bidask is not None else 'TRADES' if has_volume else 'BID_ASK'}",
            style={'color': '#6c757d'},
        ),
    ])

    return result_dicts, status, {'display': 'block'}


@callback(
    Output('scanner-table-container', 'children'),
    Input('scanner-rank-tabs', 'value'),
    Input('scanner-results-store', 'data'),
)
def update_ranking_table(rank_by, result_dicts):
    """Re-rank and display results when the ranking tab changes."""
    if not result_dicts:
        return html.Div("No results to display.")

    # Re-sort the dicts based on selected ranking
    if rank_by == 'profit':
        sorted_dicts = sorted(result_dicts, key=lambda r: r['credit'], reverse=True)
    elif rank_by == 'risk_reward':
        sorted_dicts = sorted(result_dicts, key=lambda r: r['risk_reward'], reverse=True)
    else:  # safety
        sorted_dicts = sorted(result_dicts, key=lambda r: r['worst_case_pnl'], reverse=True)

    table_id = f'scanner-table-{rank_by}'
    table = _make_table(table_id)
    table.data = sorted_dicts

    return html.Div([
        table,
        html.Div(
            "Click any row to apply it to the sidebar for analysis.",
            style={'marginTop': '8px', 'color': '#6c757d', 'fontSize': '12px'},
        ),
    ])


@callback(
    Output('selected-scan-result', 'data'),
    Input('scanner-table-safety', 'active_cell'),
    Input('scanner-table-profit', 'active_cell'),
    Input('scanner-table-risk_reward', 'active_cell'),
    State('scanner-table-safety', 'data'),
    State('scanner-table-profit', 'data'),
    State('scanner-table-risk_reward', 'data'),
    State('config-store', 'data'),
    State('scanner-right-select', 'value'),
    prevent_initial_call=True,
)
def apply_scan_result(
    safety_cell, profit_cell, rr_cell,
    safety_data, profit_data, rr_data,
    config, scanner_right,
):
    """When user clicks a row in any ranking table, store the result for sidebar apply."""
    from dash import ctx

    if not config:
        return no_update

    # Determine which table was clicked
    triggered_id = ctx.triggered_id
    if triggered_id == 'scanner-table-safety' and safety_cell:
        row = safety_data[safety_cell['row']]
    elif triggered_id == 'scanner-table-profit' and profit_cell:
        row = profit_data[profit_cell['row']]
    elif triggered_id == 'scanner-table-risk_reward' and rr_cell:
        row = rr_data[rr_cell['row']]
    else:
        return no_update

    return {
        'sym1_strike': row['sym1_strike'],
        'sym2_strike': row['sym2_strike'],
        'direction': row['direction'],
        'entry_time': row['best_wc_time'],
        'right': scanner_right,
        'sym1': config['sym1'],
        'sym2': config['sym2'],
    }
