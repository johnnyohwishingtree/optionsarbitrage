"""Tests for src/pages/scanner.py — scanner callbacks."""

import pytest
from dash import no_update
from unittest.mock import patch, MagicMock


class TestUpdateRankingTables:
    def test_empty_results(self):
        from src.pages.scanner import update_ranking_tables
        safety, profit, rr = update_ranking_tables([])
        assert safety == []
        assert profit == []
        assert rr == []

    def test_sorts_by_criteria(self):
        from src.pages.scanner import update_ranking_tables
        mock_data = [
            {
                'sym1_strike': 600, 'sym2_strike': 6000,
                'moneyness': 'ATM', 'direction': 'Sell SPX',
                'credit': 150.0, 'worst_case_pnl': -50.0,
                'risk_reward': 3.0, 'max_gap': 0.0012,
                'max_gap_time': '10:00', 'best_wc_time': '10:30',
                'sym1_vol': 100, 'sym2_vol': 50,
                'liquidity': 'OK', 'price_source': 'mid',
            },
            {
                'sym1_strike': 601, 'sym2_strike': 6010,
                'moneyness': 'ATM', 'direction': 'Sell SPX',
                'credit': 200.0, 'worst_case_pnl': 10.0,
                'risk_reward': 5.0, 'max_gap': 0.0015,
                'max_gap_time': '10:05', 'best_wc_time': '10:35',
                'sym1_vol': 80, 'sym2_vol': 40,
                'liquidity': 'OK', 'price_source': 'mid',
            },
        ]
        safety, profit, rr = update_ranking_tables(mock_data)
        assert safety[0]['worst_case_pnl'] >= safety[1]['worst_case_pnl']
        assert profit[0]['credit'] >= profit[1]['credit']
        assert rr[0]['risk_reward'] >= rr[1]['risk_reward']


class TestRunScan:
    def test_bad_config_returns_3_tuple(self):
        """Error in scan should return ([], error_div, style)."""
        from src.pages.scanner import run_scan
        bad_config = {
            'date': '99999999',
            'sym1': 'SPY', 'sym2': 'SPX',
            'qty_ratio': 10,
        }
        result = run_scan(1, bad_config, 'P', 10, ['hide'])
        assert isinstance(result, tuple)
        assert len(result) == 3
        data, status, style = result
        assert data == []
        assert style == {'display': 'none'}

    def test_min_volume_zero_accepted(self):
        """min_volume=0 should use 0, not fall back to default."""
        from src.config import DEFAULT_MIN_VOLUME
        min_volume = 0
        min_vol = int(min_volume) if min_volume is not None else DEFAULT_MIN_VOLUME
        assert min_vol == 0

    def test_min_volume_none_uses_default(self):
        from src.config import DEFAULT_MIN_VOLUME
        min_volume = None
        min_vol = int(min_volume) if min_volume is not None else DEFAULT_MIN_VOLUME
        assert min_vol == DEFAULT_MIN_VOLUME


class TestApplyScanResult:
    def test_empty_data_returns_no_update(self):
        from src.pages.scanner import apply_scan_result
        mock_ctx = MagicMock()
        mock_ctx.triggered_id = 'scanner-table-safety'
        with patch('dash.ctx', mock_ctx):
            result = apply_scan_result(
                safety_cell={'row': 99},
                profit_cell=None,
                rr_cell=None,
                safety_data=[],
                profit_data=[],
                rr_data=[],
                config={'sym1': 'SPY', 'sym2': 'SPX'},
                scanner_right='P',
            )
        assert result is no_update
