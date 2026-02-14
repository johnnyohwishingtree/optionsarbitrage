"""Tests for src/models.py — domain model dataclasses."""

import pytest
from dataclasses import asdict
from src.models import StrategyConfig, PriceQuote, Leg, Position, ScanResult


class TestLeg:
    def test_create_sell_leg(self):
        leg = Leg('SPY', 600.0, 'C', 'SELL', 10, 2.50)
        assert leg.symbol == 'SPY'
        assert leg.strike == 600.0
        assert leg.right == 'C'
        assert leg.action == 'SELL'
        assert leg.quantity == 10
        assert leg.entry_price == 2.50

    def test_serializable(self):
        leg = Leg('SPX', 6000.0, 'P', 'BUY', 1, 25.00)
        d = asdict(leg)
        assert d['symbol'] == 'SPX'
        assert d['strike'] == 6000.0


class TestPosition:
    def test_default_values(self):
        pos = Position()
        assert pos.legs == []
        assert pos.call_credit == 0.0
        assert pos.put_credit == 0.0
        assert pos.total_credit == 0.0
        assert pos.estimated_margin == 0.0

    def test_with_legs(self):
        legs = [
            Leg('SPY', 600, 'C', 'SELL', 10, 2.50),
            Leg('SPX', 6000, 'C', 'BUY', 1, 25.00),
        ]
        pos = Position(legs=legs, call_credit=0.0, total_credit=0.0)
        assert len(pos.legs) == 2

    def test_serializable(self):
        pos = Position(
            legs=[Leg('SPY', 600, 'C', 'SELL', 10, 2.50)],
            call_credit=100.0,
            total_credit=100.0,
        )
        d = asdict(pos)
        assert len(d['legs']) == 1
        assert d['call_credit'] == 100.0


class TestPriceQuote:
    def test_minimal_creation(self):
        pq = PriceQuote(price=2.50, source='trade', volume=100)
        assert pq.price == 2.50
        assert pq.source == 'trade'
        assert pq.is_stale is False
        assert pq.liquidity_warning is None

    def test_stale_quote(self):
        pq = PriceQuote(price=2.50, source='midpoint', volume=0, is_stale=True)
        assert pq.is_stale is True
        assert pq.volume == 0

    def test_with_spread(self):
        pq = PriceQuote(
            price=2.50, source='midpoint', volume=50,
            bid=2.40, ask=2.60, spread=0.20, spread_pct=8.0,
        )
        assert pq.bid == 2.40
        assert pq.ask == 2.60
        assert pq.spread_pct == 8.0


class TestStrategyConfig:
    def test_creation(self):
        config = StrategyConfig(
            sym1='SPY', sym2='SPX',
            qty_ratio=10, strike_step=5,
            strategy_type='full',
            call_direction='Sell SPX, Buy SPY',
            put_direction='Sell SPY, Buy SPX',
        )
        assert config.sym1 == 'SPY'
        assert config.qty_ratio == 10


class TestScanResult:
    def test_creation(self):
        sr = ScanResult(
            sym1_strike=600, sym2_strike=6000,
            moneyness='+0.10%', max_gap=0.15,
            max_gap_time='10:30', credit=500.0,
            worst_case_pnl=-200.0, best_wc_time='11:00',
            direction='Sell SPX',
        )
        assert sr.credit == 500.0
        assert sr.risk_reward == 0.0  # default

    def test_defaults(self):
        sr = ScanResult(
            sym1_strike=600, sym2_strike=6000,
            moneyness='ATM', max_gap=0.0,
            max_gap_time='', credit=0.0,
            worst_case_pnl=0.0, best_wc_time='',
            direction='Sell SPX',
        )
        assert sr.sym1_vol == 0
        assert sr.sym2_vol == 0
        assert sr.liquidity == 'OK'
        assert sr.price_source == 'trade'
        assert sr.max_risk == 0.0

    def test_serializable(self):
        sr = ScanResult(
            sym1_strike=600, sym2_strike=6000,
            moneyness='ATM', max_gap=0.15,
            max_gap_time='10:30', credit=500.0,
            worst_case_pnl=-200.0, best_wc_time='11:00',
            direction='Sell SPX', risk_reward=2.5, max_risk=-200.0,
        )
        d = asdict(sr)
        assert d['credit'] == 500.0
        assert d['risk_reward'] == 2.5
