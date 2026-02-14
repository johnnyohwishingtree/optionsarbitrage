"""
Shared sidebar configuration component.

Provides date selection, symbol pair, entry time, strikes, and direction controls.
Updates the config-store which all tabs read from.
"""

from dash import html, dcc, callback, Input, Output, State
import json

from src.data_loader import (
    list_available_dates,
    load_underlying_prices,
    load_options_data,
    load_bidask_data,
    get_symbol_dataframes,
    get_available_pairs,
)
from src.config import SYMBOL_PAIRS, get_qty_ratio, get_strike_step


def layout():
    """Return the sidebar layout."""
    dates = list_available_dates()
    dates.reverse()  # Most recent first

    if not dates:
        return html.Div([
            html.H3("Configuration"),
            html.P("No historical data found.", style={'color': 'red'}),
        ])

    date_options = [
        {'label': f"{fmt} ({raw})", 'value': raw}
        for raw, fmt in dates
    ]

    section_label = {
        'fontSize': '11px',
        'fontWeight': '600',
        'textTransform': 'uppercase',
        'letterSpacing': '0.5px',
        'color': '#6c757d',
        'marginBottom': '6px',
    }

    return html.Div([
        html.H3("Configuration", style={'marginTop': '0', 'marginBottom': '16px'}),

        # Date Selection
        html.Div("Date", style=section_label),
        dcc.Dropdown(
            id='date-selector',
            options=date_options,
            value=dates[0][0],
            clearable=False,
        ),
        html.Div(id='data-load-status', style={'marginTop': '4px'}),

        html.Hr(style={'margin': '14px 0'}),

        # Symbol Pair
        html.Div("Symbol Pair", style=section_label),
        dcc.Dropdown(
            id='pair-selector',
            options=[],  # populated by callback
            clearable=False,
        ),
        html.Div(id='pair-info'),

        html.Hr(style={'margin': '14px 0'}),

        # Entry Time
        html.Div("Entry Time", style=section_label),
        html.Div(
            dcc.Slider(
                id='entry-time-slider',
                min=0,
                max=0,
                step=1,
                value=0,
                marks={},
                tooltip={'placement': 'bottom', 'always_visible': True},
            ),
            style={'padding': '0 4px'},
        ),
        html.Div(id='entry-time-display', style={'fontWeight': 'bold', 'marginTop': '4px'}),
        html.Div(id='entry-prices-display', style={
            'fontSize': '13px',
            'fontFamily': 'monospace',
            'marginTop': '4px',
        }),

        html.Hr(style={'margin': '14px 0'}),

        # Strike Configuration
        html.Div("Strikes", style=section_label),
        html.Div([
            html.Div([
                html.Label("SYM1", style={'fontSize': '12px', 'fontWeight': 'bold'}),
                dcc.Input(id='sym1-strike-input', type='number', step=1, min=1, style={'width': '100%'}),
            ], style={'flex': '1', 'marginRight': '8px'}),
            html.Div([
                html.Label("SYM2", style={'fontSize': '12px', 'fontWeight': 'bold'}),
                dcc.Input(id='sym2-strike-input', type='number', step=1, min=1, style={'width': '100%'}),
            ], style={'flex': '1'}),
        ], style={'display': 'flex'}),
        html.Div(id='moneyness-check', style={'marginTop': '8px'}),

        html.Hr(style={'margin': '14px 0'}),

        # Strategy Direction
        html.Div("Direction", style=section_label),
        html.Label("Call Spread", style={'fontSize': '12px', 'fontWeight': 'bold'}),
        dcc.Dropdown(id='call-direction-select', clearable=False),
        html.Label("Put Spread", style={'marginTop': '8px', 'fontSize': '12px', 'fontWeight': 'bold'}),
        dcc.Dropdown(id='put-direction-select', clearable=False),
    ])


@callback(
    Output('pair-selector', 'options'),
    Output('pair-selector', 'value'),
    Input('date-selector', 'value'),
)
def update_pairs(selected_date):
    """Update available symbol pairs when date changes."""
    if not selected_date:
        return [], None

    try:
        df_underlying = load_underlying_prices(selected_date)
        pairs = get_available_pairs(df_underlying)
        options = [{'label': k, 'value': k} for k in pairs.keys()]
        default = options[0]['value'] if options else None
        return options, default
    except Exception:
        return [], None


@callback(
    Output('data-load-status', 'children'),
    Output('entry-time-slider', 'max'),
    Output('entry-time-slider', 'marks'),
    Output('entry-time-slider', 'value'),
    Output('sym1-strike-input', 'value'),
    Output('sym1-strike-input', 'step'),
    Output('sym2-strike-input', 'value'),
    Output('sym2-strike-input', 'step'),
    Output('call-direction-select', 'options'),
    Output('call-direction-select', 'value'),
    Output('put-direction-select', 'options'),
    Output('put-direction-select', 'value'),
    Input('date-selector', 'value'),
    Input('pair-selector', 'value'),
)
def update_controls(selected_date, selected_pair):
    """Update all controls when date or pair changes."""
    if not selected_date or not selected_pair:
        return ("", 0, {}, 0, 0, 1, 0, 1, [], None, [], None)

    try:
        df_underlying = load_underlying_prices(selected_date)
        pairs = get_available_pairs(df_underlying)
        if selected_pair not in pairs:
            return ("Pair not available", 0, {}, 0, 0, 1, 0, 1, [], None, [], None)

        sym1, sym2 = pairs[selected_pair]
        sym1_df, sym2_df = get_symbol_dataframes(df_underlying, sym1, sym2)

        if sym1_df.empty or sym2_df.empty:
            return ("No data for symbols", 0, {}, 0, 0, 1, 0, 1, [], None, [], None)

        # Data load status
        df_options = load_options_data(selected_date)
        df_bidask = load_bidask_data(selected_date)
        status_parts = [f"Loaded data for {selected_date}"]
        if df_options is not None:
            status_parts.append(f"{len(df_options)} TRADES records")
        if df_bidask is not None:
            status_parts.append(f"{len(df_bidask)} bid/ask records")
        status = html.Div([html.Small(s) for s in status_parts])

        # Time slider — show only 5 sparse marks to avoid label overlap
        time_labels = sym1_df['time_label'].tolist()
        max_idx = len(time_labels) - 1
        if max_idx > 0:
            # Pick 5 evenly spaced marks: open, mid-morning, noon, mid-afternoon, close
            mark_indices = [
                0,
                max_idx // 4,
                max_idx // 2,
                3 * max_idx // 4,
                max_idx,
            ]
            marks = {
                i: {'label': time_labels[i].replace(' ET', ''), 'style': {'fontSize': '11px'}}
                for i in mark_indices
            }
        else:
            marks = {0: {'label': time_labels[0].replace(' ET', ''), 'style': {'fontSize': '11px'}}}

        # Strikes
        qty_ratio = get_qty_ratio(sym2)
        strike_step = get_strike_step(sym2)
        open_sym1 = sym1_df.iloc[0]['close']
        open_sym2 = sym2_df.iloc[0]['close']
        default_sym1_strike = int(round(open_sym1))
        default_sym2_strike = int(round(open_sym2 / strike_step) * strike_step)

        # Direction options
        call_options = [
            {'label': f"Sell {sym2}, Buy {sym1}", 'value': f"Sell {sym2}, Buy {sym1}"},
            {'label': f"Buy {sym2}, Sell {sym1}", 'value': f"Buy {sym2}, Sell {sym1}"},
        ]
        put_options = [
            {'label': f"Sell {sym1}, Buy {sym2}", 'value': f"Sell {sym1}, Buy {sym2}"},
            {'label': f"Buy {sym1}, Sell {sym2}", 'value': f"Buy {sym1}, Sell {sym2}"},
        ]

        return (
            status, max_idx, marks, 0,
            default_sym1_strike, 1,
            default_sym2_strike, strike_step,
            call_options, call_options[0]['value'],
            put_options, put_options[0]['value'],
        )

    except Exception as e:
        return (f"Error: {e}", 0, {}, 0, 0, 1, 0, 1, [], None, [], None)


@callback(
    Output('entry-time-display', 'children'),
    Output('entry-prices-display', 'children'),
    Output('config-store', 'data'),
    Input('date-selector', 'value'),
    Input('pair-selector', 'value'),
    Input('entry-time-slider', 'value'),
    Input('sym1-strike-input', 'value'),
    Input('sym2-strike-input', 'value'),
    Input('call-direction-select', 'value'),
    Input('put-direction-select', 'value'),
)
def update_config_store(selected_date, selected_pair, entry_time_idx,
                        sym1_strike, sym2_strike, call_direction, put_direction):
    """Update the shared config store whenever any input changes."""
    if not selected_date or not selected_pair:
        return "", "", {}

    try:
        df_underlying = load_underlying_prices(selected_date)
        pairs = get_available_pairs(df_underlying)
        if selected_pair not in pairs:
            return "", "", {}

        sym1, sym2 = pairs[selected_pair]
        sym1_df, sym2_df = get_symbol_dataframes(df_underlying, sym1, sym2)

        if sym1_df.empty or sym2_df.empty or entry_time_idx is None:
            return "", "", {}

        entry_time_idx = min(entry_time_idx, len(sym1_df) - 1)
        entry_sym1 = sym1_df.iloc[entry_time_idx]
        entry_sym2 = sym2_df.iloc[entry_time_idx]
        time_label = entry_sym1['time_label']

        time_display = html.Strong(time_label)
        prices_display = html.Div([
            html.Div(f"{sym1}: ${entry_sym1['close']:.2f}"),
            html.Div(f"{sym2}: ${entry_sym2['close']:.2f}"),
        ])

        qty_ratio = get_qty_ratio(sym2)
        strike_step = get_strike_step(sym2)

        config = {
            'date': selected_date,
            'sym1': sym1,
            'sym2': sym2,
            'qty_ratio': qty_ratio,
            'strike_step': strike_step,
            'entry_time_idx': entry_time_idx,
            'entry_time_label': time_label,
            'sym1_strike': sym1_strike,
            'sym2_strike': sym2_strike,
            'call_direction': call_direction,
            'put_direction': put_direction,
            'entry_sym1_price': entry_sym1['close'],
            'entry_sym2_price': entry_sym2['close'],
        }

        return time_display, prices_display, config

    except Exception:
        return "", "", {}


@callback(
    Output('moneyness-check', 'children'),
    Input('config-store', 'data'),
)
def update_moneyness(config):
    """Display moneyness check for current strikes."""
    if not config or not config.get('sym1_strike') or not config.get('sym2_strike'):
        return ""

    sym1_price = config.get('entry_sym1_price')
    sym2_price = config.get('entry_sym2_price')
    if not sym1_price or not sym2_price:
        return ""

    sym1_strike = config['sym1_strike']
    sym2_strike = config['sym2_strike']

    sym1_moneyness = ((sym1_strike - sym1_price) / sym1_price) * 100
    sym2_moneyness = ((sym2_strike - sym2_price) / sym2_price) * 100
    diff = abs(sym1_moneyness - sym2_moneyness)

    if diff > 0.05:
        return html.Div(
            f"Moneyness mismatch: {diff:.2f}%",
            style={'color': '#856404', 'backgroundColor': '#fff3cd', 'padding': '5px', 'borderRadius': '4px'}
        )
    return html.Div(
        f"Strikes matched (within 0.05%)",
        style={'color': '#155724', 'backgroundColor': '#d4edda', 'padding': '5px', 'borderRadius': '4px'}
    )


@callback(
    Output('sym1-strike-input', 'value', allow_duplicate=True),
    Output('sym2-strike-input', 'value', allow_duplicate=True),
    Output('entry-time-slider', 'value', allow_duplicate=True),
    Output('call-direction-select', 'value', allow_duplicate=True),
    Output('put-direction-select', 'value', allow_duplicate=True),
    Output('main-tabs', 'value'),
    Input('selected-scan-result', 'data'),
    State('date-selector', 'value'),
    State('pair-selector', 'value'),
    prevent_initial_call=True,
)
def apply_scanner_result(scan_result, selected_date, selected_pair):
    """When a scanner result is applied, update sidebar controls and switch to Historical tab."""
    from dash import no_update
    if not scan_result:
        return no_update, no_update, no_update, no_update, no_update, no_update

    sym1_strike = scan_result.get('sym1_strike', no_update)
    sym2_strike = scan_result.get('sym2_strike', no_update)

    # Convert entry time to slider index
    entry_time = scan_result.get('entry_time', '')
    entry_time_idx = no_update
    if entry_time and selected_date:
        try:
            df_underlying = load_underlying_prices(selected_date)
            pairs = get_available_pairs(df_underlying)
            if selected_pair and selected_pair in pairs:
                sym1, sym2 = pairs[selected_pair]
                sym1_df, _ = get_symbol_dataframes(df_underlying, sym1, sym2)
                time_shorts = sym1_df['time_short'].tolist()
                if entry_time in time_shorts:
                    entry_time_idx = time_shorts.index(entry_time)
        except Exception:
            pass

    # Determine direction
    direction = scan_result.get('direction', '')
    right = scan_result.get('right', 'P')
    sym1 = scan_result.get('sym1', 'SPY')
    sym2 = scan_result.get('sym2', 'SPX')

    call_dir = no_update
    put_dir = no_update
    if right == 'P':
        if 'Sell' in direction and sym2 in direction:
            put_dir = f"Buy {sym1}, Sell {sym2}"
        else:
            put_dir = f"Sell {sym1}, Buy {sym2}"
    else:  # Calls
        if 'Sell' in direction and sym2 in direction:
            call_dir = f"Sell {sym2}, Buy {sym1}"
        else:
            call_dir = f"Buy {sym2}, Sell {sym1}"

    return sym1_strike, sym2_strike, entry_time_idx, call_dir, put_dir, 'historical'
