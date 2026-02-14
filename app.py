#!/usr/bin/env python3
"""
0DTE Options Arbitrage Dashboard — Dash Application

Run with: python app.py
Then open http://127.0.0.1:8050 in your browser.
"""

from dash import Dash, html, dcc, callback, Input, Output

from src.pages import sidebar, historical, live_trading, price_overlay, divergence, scanner

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="0DTE Strategy Calculator",
)

app.layout = html.Div([
    # Shared data stores
    dcc.Store(id='config-store', data={}),
    dcc.Store(id='selected-scan-result', data=None),

    # Banner for scanner apply
    html.Div(id='apply-banner'),

    # Main layout: sidebar + content
    html.Div([
        # Sidebar
        html.Div(
            sidebar.layout(),
            style={
                'width': '300px',
                'minWidth': '300px',
                'padding': '16px',
                'backgroundColor': '#f8f9fa',
                'borderRight': '1px solid #dee2e6',
                'overflowY': 'auto',
                'height': '100vh',
                'position': 'sticky',
                'top': '0',
                'flexShrink': '0',
            }
        ),
        # Content area
        html.Div([
            html.H1("0DTE Strategy Calculator", style={'fontSize': '22px', 'marginBottom': '12px'}),
            dcc.Tabs(
                id='main-tabs',
                value='historical',
                children=[
                    dcc.Tab(label='Historical Analysis', value='historical'),
                    dcc.Tab(label='Live Paper Trading', value='live_trading'),
                    dcc.Tab(label='Price Overlay', value='price_overlay'),
                    dcc.Tab(label='Underlying Divergence', value='divergence'),
                    dcc.Tab(label='Strike Scanner', value='scanner'),
                ],
            ),
            html.Div(id='tab-content', style={'padding': '20px'}),
        ], style={'flex': '1', 'padding': '20px', 'overflowY': 'auto'}),
    ], style={'display': 'flex', 'height': '100vh'}),
])


@callback(
    Output('tab-content', 'children'),
    Input('main-tabs', 'value'),
)
def render_tab(tab_value):
    """Render the selected tab's layout."""
    if tab_value == 'historical':
        return historical.layout()
    elif tab_value == 'live_trading':
        return live_trading.layout()
    elif tab_value == 'price_overlay':
        return price_overlay.layout()
    elif tab_value == 'divergence':
        return divergence.layout()
    elif tab_value == 'scanner':
        return scanner.layout()
    return html.Div("Select a tab")


@callback(
    Output('apply-banner', 'children'),
    Input('selected-scan-result', 'data'),
)
def show_apply_banner(scan_result):
    """Show a banner when scanner result is applied."""
    if not scan_result:
        return None
    return html.Div(
        [
            html.Strong(
                f"Applied: {scan_result.get('sym1', 'SYM1')} {scan_result.get('sym1_strike', '')} / "
                f"{scan_result.get('sym2', 'SYM2')} {scan_result.get('sym2_strike', '')} | "
                f"{scan_result.get('direction', '')} | Entry Time: {scan_result.get('entry_time', '')}"
            ),
            html.Br(),
            html.Em("Click the Historical Analysis tab to analyze this trade."),
        ],
        style={
            'padding': '10px 20px',
            'backgroundColor': '#d4edda',
            'borderBottom': '1px solid #c3e6cb',
            'color': '#155724',
        }
    )


if __name__ == '__main__':
    app.run(debug=True, port=8050)
