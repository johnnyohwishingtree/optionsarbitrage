"""Tests for src/pages/components.py — shared UI components and styles."""

import pytest
from dash import html


class TestColors:
    def test_color_constants_are_hex(self):
        from src.pages.components import (
            COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_NEUTRAL,
            COLOR_INFO, COLOR_WARNING_TEXT, COLOR_WARNING_BG,
            COLOR_SUCCESS_TEXT, COLOR_SUCCESS_BG,
        )
        for color in [COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_NEUTRAL,
                       COLOR_INFO, COLOR_WARNING_TEXT, COLOR_WARNING_BG,
                       COLOR_SUCCESS_TEXT, COLOR_SUCCESS_BG]:
            assert color.startswith('#'), f"Color {color} is not a hex color"


class TestStyles:
    def test_section_style_is_dict(self):
        from src.pages.components import SECTION_STYLE
        assert isinstance(SECTION_STYLE, dict)
        assert 'border' in SECTION_STYLE

    def test_table_style_is_dict(self):
        from src.pages.components import TABLE_STYLE
        assert isinstance(TABLE_STYLE, dict)

    def test_td_right_inherits_td(self):
        from src.pages.components import TD_STYLE, TD_RIGHT
        # TD_RIGHT should have all of TD_STYLE plus textAlign and fontFamily
        for key in TD_STYLE:
            assert key in TD_RIGHT
        assert TD_RIGHT['textAlign'] == 'right'


class TestPnlSpan:
    def test_positive_value(self):
        from src.pages.components import pnl_span, COLOR_POSITIVE
        span = pnl_span(100.0)
        assert isinstance(span, html.Span)
        assert '+$100.00' in span.children
        assert span.style['color'] == COLOR_POSITIVE

    def test_negative_value(self):
        from src.pages.components import pnl_span, COLOR_NEGATIVE
        span = pnl_span(-50.0)
        assert '-$50.00' in span.children
        assert span.style['color'] == COLOR_NEGATIVE

    def test_zero_value(self):
        from src.pages.components import pnl_span, COLOR_NEUTRAL
        span = pnl_span(0.0)
        assert '$0.00' in span.children
        assert span.style['color'] == COLOR_NEUTRAL

    def test_large_value_formatting(self):
        from src.pages.components import pnl_span
        span = pnl_span(1234567.89)
        assert '+$1,234,567.89' in span.children


class TestMetricCard:
    def test_returns_div(self):
        from src.pages.components import metric_card
        card = metric_card("Test", "$100")
        assert isinstance(card, html.Div)

    def test_label_and_value_present(self):
        from src.pages.components import metric_card
        card = metric_card("Net P&L", "+$500.00")
        # First child is label div, second is value div
        assert card.children[0].children == "Net P&L"
        assert card.children[1].children == "+$500.00"

    def test_large_size(self):
        from src.pages.components import metric_card
        card = metric_card("Total", "$1000", size='large')
        assert card.children[1].style['fontSize'] == '24px'

    def test_normal_size(self):
        from src.pages.components import metric_card
        card = metric_card("Total", "$1000", size='normal')
        assert card.children[1].style['fontSize'] == '18px'


class TestSection:
    def test_returns_div_with_title(self):
        from src.pages.components import section
        s = section("My Section")
        assert isinstance(s, html.Div)
        # First child should be the H4 title
        assert isinstance(s.children[0], html.H4)
        assert s.children[0].children == "My Section"

    def test_with_subtitle(self):
        from src.pages.components import section
        s = section("Title", subtitle="Subtitle text")
        # Should have H4 then subtitle Div
        assert len(s.children) >= 2
        assert s.children[1].children == "Subtitle text"

    def test_with_children(self):
        from src.pages.components import section
        child = html.P("Content")
        s = section("Title", child)
        assert child in s.children
