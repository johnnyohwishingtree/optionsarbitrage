"""
Price Overlay page — Tab 3.

Overlays SYM1 vs SYM2 option prices (normalized) to find arbitrage opportunities.
Shows spread chart, trading signals, and safest entry point.
"""

from dash import html, dcc, callback, Input, Output, no_update
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data_loader import (
    load_underlying_prices, load_options_data, load_bidask_data, get_symbol_dataframes,
)
from src.normalization import normalize_option_prices, calculate_spread, calculate_worst_case_quick
from src.pricing import get_option_price_from_db
from src.pnl import calculate_best_worst_case_with_basis_drift
from src.config import get_qty_ratio
from src.pages.components import (
    metric_card, COLOR_SUCCESS_TEXT, COLOR_SUCCESS_BG,
    COLOR_WARNING_TEXT, COLOR_WARNING_BG,
)


def layout():
    return html.Div([
        html.H3("Price Overlay"),
        html.P("Overlay SYM1 vs SYM2 option prices to find arbitrage opportunities"),
        dcc.Dropdown(
            id='overlay-right',
            options=[
                {'label': 'Puts', 'value': 'P'},
                {'label': 'Calls', 'value': 'C'},
            ],
            value='P',
            clearable=False,
            style={'width': '200px', 'marginBottom': '15px'},
        ),
        dcc.Loading(html.Div(id='overlay-content')),
    ])


@callback(
    Output('overlay-content', 'children'),
    Input('config-store', 'data'),
    Input('overlay-right', 'value'),
    Input('main-tabs', 'value'),
)
def update_overlay(config, overlay_right, active_tab):
    from dash import no_update
    if active_tab != 'price_overlay':
        return no_update

    if not config or not config.get('date'):
        return html.P("Select a date and symbol pair to view overlay.")

    try:
        date = config['date']
        sym1, sym2 = config['sym1'], config['sym2']
        sym1_strike = config.get('sym1_strike')
        sym2_strike = config.get('sym2_strike')
        qty_ratio = config['qty_ratio']

        if not sym1_strike or not sym2_strike:
            return html.P("Configure strikes in the sidebar.")

        df_underlying = load_underlying_prices(date)
        sym1_df, sym2_df = get_symbol_dataframes(df_underlying, sym1, sym2)

        if sym1_df.empty or sym2_df.empty:
            return html.P("No underlying data for selected symbols.", style={'color': '#856404'})

        df_options = load_options_data(date)
        df_bidask = load_bidask_data(date)

        # Determine data source
        if df_options is not None:
            source = df_options
            price_col = 'close'
            has_volume = True
        elif df_bidask is not None:
            source = df_bidask
            price_col = 'midpoint'
            has_volume = False
        else:
            return html.P("No option price data found.", style={'color': 'red'})

        open_sym1 = sym1_df.iloc[0]['close']
        open_sym2 = sym2_df.iloc[0]['close']
        if open_sym1 == 0:
            return html.P("Invalid underlying price data (zero price).", style={'color': '#856404'})
        open_ratio = open_sym2 / open_sym1

        # Get option data for the selected strikes
        sym1_opt = source[
            (source['symbol'] == sym1) &
            (source['strike'] == sym1_strike) &
            (source['right'] == overlay_right)
        ].copy().sort_values('time')

        sym2_opt = source[
            (source['symbol'] == sym2) &
            (source['strike'] == sym2_strike) &
            (source['right'] == overlay_right)
        ].copy().sort_values('time')

        if sym1_opt.empty:
            return html.P(f"No data for {sym1} {sym1_strike}{overlay_right}", style={'color': '#856404'})
        if sym2_opt.empty:
            return html.P(f"No data for {sym2} {sym2_strike}{overlay_right}", style={'color': '#856404'})

        # Filter liquidity
        if has_volume:
            sym1_liquid = sym1_opt[sym1_opt['volume'] > 0].copy()
            sym2_liquid = sym2_opt[sym2_opt['volume'] > 0].copy()
        else:
            sym1_liquid = sym1_opt[(sym1_opt['bid'] > 0) & (sym1_opt['ask'] > 0)].copy()
            sym2_liquid = sym2_opt[(sym2_opt['bid'] > 0) & (sym2_opt['ask'] > 0)].copy()

        if sym1_liquid.empty or sym2_liquid.empty:
            return html.P("Insufficient liquid data for overlay.", style={'color': '#856404'})

        # Normalize and merge
        merged = normalize_option_prices(sym1_liquid, sym2_liquid, open_ratio, price_col)
        if merged.empty:
            return html.P("No overlapping time periods found.", style={'color': '#856404'})

        merged = calculate_spread(merged)

        # Time labels
        merged['time_et'] = merged['time'].dt.tz_convert('America/New_York')
        merged['time_label'] = merged['time_et'].dt.strftime('%H:%M')

        # Moneyness
        sym1_moneyness = ((sym1_strike - open_sym1) / open_sym1) * 100
        sym2_moneyness = ((sym2_strike - open_sym2) / open_sym2) * 100

        # Quick worst case
        merged = calculate_worst_case_quick(
            merged, open_ratio, sym1_strike, qty_ratio,
            sym1_moneyness, sym2_moneyness
        )

        # Find key points
        max_spread_idx = merged['spread'].abs().idxmax()
        max_spread_row = merged.loc[max_spread_idx]
        best_worst_idx = merged['worst_case_pnl'].idxmax()
        best_worst_row = merged.loc[best_worst_idx]

        # Accurate grid search at best worst-case time
        best_worst_time = best_worst_row['time']
        sym1_at = sym1_df.iloc[(sym1_df['time'] - best_worst_time).abs().argsort()[:1]]
        sym2_at = sym2_df.iloc[(sym2_df['time'] - best_worst_time).abs().argsort()[:1]]
        entry_sym1_px = sym1_at['close'].iloc[0]
        entry_sym2_px = sym2_at['close'].iloc[0]

        sym1_opt_price = get_option_price_from_db(sym1_liquid, sym1, sym1_strike, overlay_right, best_worst_time)
        sym2_opt_price = get_option_price_from_db(sym2_liquid, sym2, sym2_strike, overlay_right, best_worst_time)

        spread_sign = best_worst_row['spread']
        direction = f'Sell {sym2}' if spread_sign > 0 else f'Sell {sym1}'

        accurate_worst_pnl = best_worst_row['worst_case_pnl']
        if sym1_opt_price is not None and sym2_opt_price is not None:
            # Build grid search params
            if overlay_right == 'P':
                if direction == f'Sell {sym2}':
                    put_dir = f"Buy {sym1}, Sell {sym2}"
                    sell_put, buy_put = sym2_opt_price, sym1_opt_price
                    sell_pq, buy_pq = 1, qty_ratio
                else:
                    put_dir = f"Sell {sym1}, Buy {sym2}"
                    sell_put, buy_put = sym1_opt_price, sym2_opt_price
                    sell_pq, buy_pq = qty_ratio, 1
                call_dir = f"Sell {sym2}, Buy {sym1}"
                sell_call = buy_call = 0.0
                sell_cq = buy_cq = 0
                show_calls, show_puts = False, True
            else:
                if direction == f'Sell {sym2}':
                    call_dir = f"Sell {sym2}, Buy {sym1}"
                    sell_call, buy_call = sym2_opt_price, sym1_opt_price
                    sell_cq, buy_cq = 1, qty_ratio
                else:
                    call_dir = f"Buy {sym2}, Sell {sym1}"
                    sell_call, buy_call = sym1_opt_price, sym2_opt_price
                    sell_cq, buy_cq = qty_ratio, 1
                put_dir = f"Sell {sym1}, Buy {sym2}"
                sell_put = buy_put = 0.0
                sell_pq = buy_pq = 0
                show_calls, show_puts = True, False

            _, worst = calculate_best_worst_case_with_basis_drift(
                entry_spy_price=entry_sym1_px, entry_spx_price=entry_sym2_px,
                spy_strike=sym1_strike, spx_strike=sym2_strike,
                call_direction=call_dir, put_direction=put_dir,
                sell_call_price=sell_call, buy_call_price=buy_call,
                sell_calls_qty=sell_cq, buy_calls_qty=buy_cq,
                sell_put_price=sell_put, buy_put_price=buy_put,
                sell_puts_qty=sell_pq, buy_puts_qty=buy_pq,
                show_calls=show_calls, show_puts=show_puts,
                sym1=sym1, sym2=sym2,
            )
            accurate_worst_pnl = worst.get('net_pnl', best_worst_row['worst_case_pnl'])

        # Build chart
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
            row_heights=[0.7, 0.3],
            subplot_titles=(
                f"{sym1} {sym1_strike}{overlay_right} vs {sym2} {sym2_strike}{overlay_right} (Normalized)",
                f"Spread ({sym2} - {sym1})"
            )
        )
        fig.add_trace(go.Scatter(
            x=merged['time_label'], y=merged['spy_price'],
            mode='lines', name=f'{sym1} {sym1_strike}{overlay_right}',
            line=dict(color='#00D4AA', width=2)
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=merged['time_label'], y=merged['spx_normalized'],
            mode='lines', name=f'{sym2} {sym2_strike}{overlay_right} (/{open_ratio:.2f})',
            line=dict(color='#FF6B6B', width=2)
        ), row=1, col=1)

        colors = ['#00D4AA' if s < 0 else '#FF6B6B' for s in merged['spread']]
        fig.add_trace(go.Bar(
            x=merged['time_label'], y=merged['spread'],
            marker_color=colors, showlegend=False
        ), row=2, col=1)
        fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1, row=2, col=1)

        # Max gap star
        fig.add_trace(go.Scatter(
            x=[max_spread_row['time_label']],
            y=[max(max_spread_row['spy_price'], max_spread_row['spx_normalized'])],
            mode='markers+text', marker=dict(color='yellow', size=15, symbol='star'),
            text=[f"Max Gap: ${abs(max_spread_row['spread']):.2f}"],
            textposition='top center', textfont=dict(color='yellow', size=12),
            showlegend=False
        ), row=1, col=1)

        # Best worst-case star
        if best_worst_row['time_label'] != max_spread_row['time_label']:
            fig.add_trace(go.Scatter(
                x=[best_worst_row['time_label']],
                y=[min(best_worst_row['spy_price'], best_worst_row['spx_normalized'])],
                mode='markers+text', marker=dict(color='cyan', size=15, symbol='star-diamond'),
                text=[f"Safe: ${accurate_worst_pnl:.0f}"],
                textposition='bottom center', textfont=dict(color='cyan', size=12),
                showlegend=False
            ), row=1, col=1)

        fig.update_layout(height=600, hovermode='x unified',
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        fig.update_xaxes(title_text="Time (ET)", row=2, col=1)
        fig.update_yaxes(title_text="Option Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="Spread ($)", row=2, col=1)

        # Metrics
        metrics = html.Div([
            html.Div([
                metric_card("Max Gap", f"${abs(max_spread_row['spread']):.2f}"),
                metric_card("Best Worst-Case", f"${accurate_worst_pnl:,.2f}"),
                metric_card("Direction", f"{sym2} > {sym1}" if max_spread_row['spread'] > 0 else f"{sym1} > {sym2}"),
                metric_card("Max Gap Time", max_spread_row['time_label']),
            ], style={'display': 'flex', 'gap': '16px', 'marginBottom': '20px'}),
        ])

        safe_section = []
        if accurate_worst_pnl > 0:
            safe_section.append(html.Div(
                [
                    html.Strong("SAFE ENTRY"),
                    html.Span(
                        f" at {best_worst_row['time_label']} — worst-case profit ",
                    ),
                    html.Strong(f"${accurate_worst_pnl:,.2f}", style={'fontFamily': 'monospace'}),
                ],
                style={
                    'color': COLOR_SUCCESS_TEXT,
                    'backgroundColor': COLOR_SUCCESS_BG,
                    'padding': '12px',
                    'borderRadius': '4px',
                    'fontSize': '15px',
                },
            ))
        else:
            safe_section.append(html.Div(
                [
                    html.Span(f"Entry at {best_worst_row['time_label']} has worst-case loss of "),
                    html.Strong(f"${abs(accurate_worst_pnl):,.2f}", style={'fontFamily': 'monospace'}),
                ],
                style={
                    'color': COLOR_WARNING_TEXT,
                    'backgroundColor': COLOR_WARNING_BG,
                    'padding': '12px',
                    'borderRadius': '4px',
                    'fontSize': '15px',
                },
            ))

        return html.Div([
            html.P(f"Open Ratio: {sym2}/{sym1} = {open_ratio:.4f}"),
            metrics,
            dcc.Graph(figure=fig),
            html.Hr(),
            html.H4("Safest Entry (Best Worst-Case)"),
            *safe_section,
        ])

    except Exception as e:
        import traceback
        return html.Div([
            html.P(f"Error: {e}", style={'color': 'red'}),
            html.Pre(traceback.format_exc(), style={'fontSize': '11px'}),
        ])


