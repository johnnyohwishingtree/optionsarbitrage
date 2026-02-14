"""
Shared UI components and style constants for all dashboard pages.

Centralizes colors, typography, section styles, and reusable display helpers
so every page has a consistent look without duplicating style dicts.
"""

from dash import html


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

COLOR_POSITIVE = '#28a745'
COLOR_NEGATIVE = '#dc3545'
COLOR_NEUTRAL = '#6c757d'
COLOR_INFO = '#17a2b8'
COLOR_WARNING_TEXT = '#856404'
COLOR_WARNING_BG = '#fff3cd'
COLOR_SUCCESS_TEXT = '#155724'
COLOR_SUCCESS_BG = '#d4edda'


# ---------------------------------------------------------------------------
# Section & Table Styles
# ---------------------------------------------------------------------------

SECTION_STYLE = {
    'border': '1px solid #dee2e6',
    'borderRadius': '6px',
    'padding': '16px',
    'marginBottom': '20px',
    'backgroundColor': '#ffffff',
}

TABLE_STYLE = {
    'width': '100%',
    'borderCollapse': 'collapse',
    'fontSize': '14px',
}

TH_STYLE = {
    'textAlign': 'left',
    'borderBottom': '2px solid #dee2e6',
    'padding': '8px',
    'backgroundColor': '#f8f9fa',
}

TD_STYLE = {
    'padding': '8px',
    'borderBottom': '1px solid #eee',
}

TD_RIGHT = {
    **TD_STYLE,
    'textAlign': 'right',
    'fontFamily': 'monospace',
}


# ---------------------------------------------------------------------------
# Semantic styles
# ---------------------------------------------------------------------------

POSITIVE_STYLE = {'color': COLOR_POSITIVE, 'fontWeight': 'bold'}
NEGATIVE_STYLE = {'color': COLOR_NEGATIVE, 'fontWeight': 'bold'}
NEUTRAL_STYLE = {'color': COLOR_NEUTRAL}

WARNING_STYLE = {
    'color': COLOR_WARNING_TEXT,
    'backgroundColor': COLOR_WARNING_BG,
    'padding': '8px',
    'borderRadius': '4px',
    'marginTop': '6px',
    'fontSize': '13px',
}


# ---------------------------------------------------------------------------
# Reusable components
# ---------------------------------------------------------------------------

def pnl_span(value: float) -> html.Span:
    """Colored P&L display: green for positive, red for negative, gray for zero."""
    if value > 0:
        style = {**POSITIVE_STYLE, 'fontFamily': 'monospace'}
        text = f"+${value:,.2f}"
    elif value < 0:
        style = {**NEGATIVE_STYLE, 'fontFamily': 'monospace'}
        text = f"-${abs(value):,.2f}"
    else:
        style = {**NEUTRAL_STYLE, 'fontFamily': 'monospace'}
        text = "$0.00"
    return html.Span(text, style=style)


def metric_card(label: str, value: str, size: str = 'normal') -> html.Div:
    """Metric card with label above, value below.

    Args:
        label: Short description (e.g. "Max Gap", "Net Liquidation").
        value: Formatted string to display.
        size: 'normal' (18px) or 'large' (24px) value font.
    """
    value_size = '24px' if size == 'large' else '18px'
    return html.Div([
        html.Div(label, style={
            'fontSize': '12px',
            'color': COLOR_NEUTRAL,
            'marginBottom': '2px',
        }),
        html.Div(value, style={
            'fontSize': value_size,
            'fontWeight': 'bold',
            'fontFamily': 'monospace',
        }),
    ], style={
        'minWidth': '130px',
        'padding': '10px',
    })


def section(title: str, *children, subtitle: str = None) -> html.Div:
    """Consistent section wrapper with title and optional subtitle."""
    header = [html.H4(title)]
    if subtitle:
        header.append(html.Div(
            subtitle,
            style={'fontSize': '13px', 'color': COLOR_NEUTRAL, 'marginBottom': '12px'},
        ))
    return html.Div(header + list(children), style=SECTION_STYLE)
