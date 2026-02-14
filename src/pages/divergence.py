"""
Underlying Divergence page — Tab 4.

Tracks SYM1 vs SYM2 underlying price divergence throughout the trading day.
"""

from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data_loader import load_underlying_prices, get_symbol_dataframes
from src.normalization import calculate_underlying_divergence
from src.config import get_qty_ratio, get_strike_step


def layout():
    return html.Div([
        html.H3("Underlying Divergence"),
        html.P("Track SYM1 vs SYM2 underlying price divergence throughout the trading day"),
        dcc.Loading(html.Div(id='divergence-content')),
    ])


@callback(
    Output('divergence-content', 'children'),
    Input('config-store', 'data'),
)
def update_divergence(config):
    if not config or not config.get('date'):
        return html.P("Select a date and symbol pair to view divergence.")

    try:
        date = config['date']
        sym1, sym2 = config['sym1'], config['sym2']
        qty_ratio = config['qty_ratio']
        strike_step = config['strike_step']

        df_underlying = load_underlying_prices(date)
        sym1_df, sym2_df = get_symbol_dataframes(df_underlying, sym1, sym2)

        if sym1_df.empty or sym2_df.empty:
            return html.P("No underlying data available.", style={'color': 'red'})

        merged = calculate_underlying_divergence(sym1_df, sym2_df, qty_ratio)
        if merged.empty:
            return html.P("No overlapping time data.", style={'color': 'red'})

        # Find max gap
        max_gap_idx = merged['pct_gap'].abs().idxmax()
        max_gap_row = merged.loc[max_gap_idx]
        max_gap_time = max_gap_row['time_label']
        max_gap_val = max_gap_row['pct_gap']
        max_dollar_gap = max_gap_row['dollar_gap']

        latest = merged.iloc[-1]
        current_gap = latest['pct_gap']

        # Metrics
        leading = sym2 if max_gap_val > 0 else sym1
        metrics = html.Div([
            _metric("Max Gap", f"{abs(max_gap_val):.4f}%"),
            _metric("Max Gap Time", f"{max_gap_time} ({leading} leading)"),
            _metric("Current Gap", f"{current_gap:+.4f}%"),
            _metric("Dollar Gap (norm)", f"${max_dollar_gap:+.2f}"),
        ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'})

        # Chart
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            row_heights=[0.6, 0.4],
            subplot_titles=(
                f"{sym1} vs {sym2} — % Change from Open",
                f"Divergence Gap ({sym2} % - {sym1} %)"
            )
        )

        fig.add_trace(go.Scatter(
            x=merged['time_label'], y=merged['pct_change_sym1'],
            name=sym1, line=dict(color='#1f77b4', width=2), mode='lines'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=merged['time_label'], y=merged['pct_change_sym2'],
            name=sym2, line=dict(color='#ff7f0e', width=2), mode='lines'
        ), row=1, col=1)

        # Stars at max gap
        fig.add_trace(go.Scatter(
            x=[max_gap_time], y=[max_gap_row['pct_change_sym1']],
            mode='markers', marker=dict(symbol='star', size=14, color='red'),
            showlegend=False
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[max_gap_time], y=[max_gap_row['pct_change_sym2']],
            mode='markers', marker=dict(symbol='star', size=14, color='red'),
            showlegend=False
        ), row=1, col=1)

        # Gap bars
        bar_colors = ['green' if g >= 0 else 'red' for g in merged['pct_gap']]
        fig.add_trace(go.Bar(
            x=merged['time_label'], y=merged['pct_gap'],
            marker_color=bar_colors, showlegend=False
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=[max_gap_time], y=[max_gap_val],
            mode='markers+text',
            marker=dict(symbol='star', size=14, color='gold'),
            text=[f"  {max_gap_val:+.4f}%"], textposition='top center',
            showlegend=False
        ), row=2, col=1)

        fig.update_layout(
            height=600, margin=dict(t=40, b=30),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            hovermode='x unified'
        )
        fig.update_yaxes(title_text="% Change", row=1, col=1)
        fig.update_yaxes(title_text="Gap %", row=2, col=1)

        tick_step = max(1, len(merged) // 20)
        tick_vals = merged['time_label'].iloc[::tick_step].tolist()
        fig.update_xaxes(tickvals=tick_vals, tickangle=45, row=2, col=1)

        # Strategy suggestions
        overpriced = sym2 if max_gap_val > 0 else sym1
        underpriced = sym1 if max_gap_val > 0 else sym2
        sym1_price_at_gap = max_gap_row['close_sym1']
        sym2_price_at_gap = max_gap_row['close_sym2']
        suggested_sym1 = int(round(sym1_price_at_gap))
        suggested_sym2 = int(round(sym2_price_at_gap / strike_step) * strike_step)

        strategy_section = html.Div([
            html.Hr(),
            html.H4(f"Strategy Suggestions at Max Gap ({max_gap_time})"),
            html.P(f"Underlying prices: {sym1} = ${sym1_price_at_gap:.2f}, {sym2} = ${sym2_price_at_gap:.2f}"),
            html.P(f"Suggested ATM strikes: {sym1} {suggested_sym1} / {sym2} {suggested_sym2}"),
            html.P(f"Direction: {overpriced} is relatively overpriced → Sell {overpriced}, Buy {underpriced}",
                   style={'fontWeight': 'bold'}),
        ])

        return html.Div([metrics, dcc.Graph(figure=fig), strategy_section])

    except Exception as e:
        import traceback
        return html.Div([
            html.P(f"Error: {e}", style={'color': 'red'}),
            html.Pre(traceback.format_exc(), style={'fontSize': '11px'}),
        ])


def _metric(label, value):
    return html.Div([
        html.Div(label, style={'fontSize': '12px', 'color': '#666'}),
        html.Div(value, style={'fontSize': '18px', 'fontWeight': 'bold'}),
    ], style={'minWidth': '120px'})
