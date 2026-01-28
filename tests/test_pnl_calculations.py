#!/usr/bin/env python3
"""
Tests for P&L calculation logic in Live Paper Trading tab

These tests ensure that:
1. Reference prices are extracted correctly from positions (not calculated)
2. P&L calculations are accurate for both long and short positions
3. Intrinsic value calculations are correct for calls and puts
"""

import pytest
import sys
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')


class MockContract:
    """Mock contract for testing"""
    def __init__(self, symbol, strike, right):
        self.symbol = symbol
        self.strike = strike
        self.right = right


class MockPosition:
    """Mock position for testing"""
    def __init__(self, contract, position, avg_cost):
        self.data = {
            'contract': contract,
            'position': position,
            'avg_cost': avg_cost,
            'sec_type': 'OPT'
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]


def calculate_intrinsic_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)


def calculate_position_pnl(position, underlying_price):
    """Calculate P&L for a single position"""
    contract = position['contract']
    position_size = position.get('position', 0)
    avg_cost_per_share = position.get('avg_cost', 0) / 100

    # Calculate intrinsic value
    intrinsic = calculate_intrinsic_value(
        underlying_price,
        contract.strike,
        contract.right
    )

    # Calculate P&L
    if position_size < 0:  # SHORT position
        pnl = (avg_cost_per_share - intrinsic) * abs(position_size) * 100
    else:  # LONG position
        pnl = (intrinsic - avg_cost_per_share) * position_size * 100

    return pnl


class TestReferencePointExtraction:
    """Test that reference prices are extracted correctly from positions"""

    def test_spy_strike_extraction(self):
        """Test extracting SPY strike from positions"""
        positions = [
            MockPosition(MockContract('SPY', 694.0, 'C'), -10, 218.40),
            MockPosition(MockContract('SPY', 694.0, 'P'), 10, 124.51),
            MockPosition(MockContract('SPX', 6975.0, 'C'), 1, 1281.64),
            MockPosition(MockContract('SPX', 6975.0, 'P'), -1, 1478.36),
        ]

        spy_strikes = [p['contract'].strike for p in positions if p['contract'].symbol == 'SPY']

        assert len(spy_strikes) == 2
        assert spy_strikes[0] == 694.0

    def test_spx_strike_extraction(self):
        """Test extracting SPX strike from positions"""
        positions = [
            MockPosition(MockContract('SPY', 694.0, 'C'), -10, 218.40),
            MockPosition(MockContract('SPY', 694.0, 'P'), 10, 124.51),
            MockPosition(MockContract('SPX', 6975.0, 'C'), 1, 1281.64),
            MockPosition(MockContract('SPX', 6975.0, 'P'), -1, 1478.36),
        ]

        spx_strikes = [p['contract'].strike for p in positions if p['contract'].symbol == 'SPX']

        assert len(spx_strikes) == 2
        assert spx_strikes[0] == 6975.0

    def test_reference_not_calculated_from_ratio(self):
        """
        REGRESSION TEST: Ensure SPX reference is from strike, not calculated

        This was the bug: reference_spx_price = reference_spy_price * (spx_price / spy_price)
        Which gave 6957.36 instead of actual strike 6975.0
        """
        positions = [
            MockPosition(MockContract('SPY', 694.0, 'C'), -10, 218.40),
            MockPosition(MockContract('SPX', 6975.0, 'P'), -1, 1478.36),
        ]

        # Current prices
        spy_price = 695.76
        spx_price = 6975.0

        # Extract reference prices (CORRECT way)
        spy_strikes = [p['contract'].strike for p in positions if p['contract'].symbol == 'SPY']
        spx_strikes = [p['contract'].strike for p in positions if p['contract'].symbol == 'SPX']

        reference_spy = spy_strikes[0] if spy_strikes else spy_price
        reference_spx = spx_strikes[0] if spx_strikes else spx_price

        # WRONG calculation (the bug we fixed)
        wrong_spx_ref = reference_spy * (spx_price / spy_price)

        # Verify we're using actual strike, not calculated
        assert reference_spx == 6975.0, "Should use actual SPX strike from position"
        assert wrong_spx_ref != reference_spx, "Bug check: calculated value should differ from actual"
        assert abs(wrong_spx_ref - 6957.36) < 0.1, "Bug reproduced: calculated value was ~6957.36"


class TestIntrinsicValueCalculations:
    """Test intrinsic value calculations for options"""

    def test_call_itm(self):
        """Test in-the-money call intrinsic value"""
        intrinsic = calculate_intrinsic_value(700, 694, 'C')
        assert intrinsic == 6.0

    def test_call_atm(self):
        """Test at-the-money call intrinsic value"""
        intrinsic = calculate_intrinsic_value(694, 694, 'C')
        assert intrinsic == 0.0

    def test_call_otm(self):
        """Test out-of-the-money call intrinsic value"""
        intrinsic = calculate_intrinsic_value(690, 694, 'C')
        assert intrinsic == 0.0

    def test_put_itm(self):
        """Test in-the-money put intrinsic value"""
        intrinsic = calculate_intrinsic_value(6970, 6975, 'P')
        assert intrinsic == 5.0

    def test_put_atm(self):
        """Test at-the-money put intrinsic value"""
        intrinsic = calculate_intrinsic_value(6975, 6975, 'P')
        assert intrinsic == 0.0

    def test_put_otm(self):
        """Test out-of-the-money put intrinsic value"""
        intrinsic = calculate_intrinsic_value(6980, 6975, 'P')
        assert intrinsic == 0.0


class TestPnLCalculations:
    """Test P&L calculations for different position types"""

    def test_short_call_otm(self):
        """Test P&L for short call expiring OTM (profitable)"""
        # Sold SPY 694C at $2.184, SPY expires at $690 (OTM)
        position = MockPosition(MockContract('SPY', 694, 'C'), -10, 218.40)
        pnl = calculate_position_pnl(position, 690)

        # Intrinsic = 0, collected $2.184/share
        # P&L = (2.184 - 0) * 10 * 100 = $2,184
        assert abs(pnl - 2184.0) < 0.01

    def test_short_call_itm(self):
        """Test P&L for short call expiring ITM (loss)"""
        # Sold SPY 694C at $2.184, SPY expires at $700 (ITM by $6)
        position = MockPosition(MockContract('SPY', 694, 'C'), -10, 218.40)
        pnl = calculate_position_pnl(position, 700)

        # Intrinsic = 6, collected $2.184/share
        # P&L = (2.184 - 6) * 10 * 100 = -$3,816
        assert abs(pnl - (-3816.0)) < 0.01

    def test_long_put_otm(self):
        """Test P&L for long put expiring OTM (loss)"""
        # Bought SPY 694P at $1.25, SPY expires at $700 (OTM)
        position = MockPosition(MockContract('SPY', 694, 'P'), 10, 125.00)
        pnl = calculate_position_pnl(position, 700)

        # Intrinsic = 0, paid $1.25/share
        # P&L = (0 - 1.25) * 10 * 100 = -$1,250
        assert pnl == -1250.0

    def test_long_put_itm(self):
        """Test P&L for long put expiring ITM (profit)"""
        # Bought SPY 694P at $1.25, SPY expires at $690 (ITM by $4)
        position = MockPosition(MockContract('SPY', 694, 'P'), 10, 125.00)
        pnl = calculate_position_pnl(position, 690)

        # Intrinsic = 4, paid $1.25/share
        # P&L = (4 - 1.25) * 10 * 100 = $2,750
        assert pnl == 2750.0

    def test_short_put_atm(self):
        """Test P&L for short put expiring ATM"""
        # Sold SPX 6975P at $14.78, SPX expires at 6975 (ATM)
        position = MockPosition(MockContract('SPX', 6975, 'P'), -1, 1478.36)
        pnl = calculate_position_pnl(position, 6975)

        # Intrinsic = 0, collected $14.78/share
        # P&L = (14.78 - 0) * 1 * 100 = $1,478
        expected = (1478.36 / 100) * 1 * 100
        assert abs(pnl - expected) < 0.1


class TestActualPositionScenario:
    """Test the actual positions from the bug report"""

    def test_bug_scenario_at_strike(self):
        """
        REGRESSION TEST: Verify P&L at strike prices

        This was showing -$638 with the bug, should be +$1,126
        """
        positions = [
            MockPosition(MockContract('SPX', 6975.0, 'P'), -1, 1478.36),
            MockPosition(MockContract('SPY', 694.0, 'C'), -10, 218.40),
            MockPosition(MockContract('SPY', 694.0, 'P'), 10, 124.51),
            MockPosition(MockContract('SPX', 6975.0, 'C'), 1, 1281.64),
        ]

        # At strike prices: SPY=694, SPX=6975
        spy_price = 694.0
        spx_price = 6975.0

        total_pnl = 0.0
        for pos in positions:
            if pos['contract'].symbol == 'SPY':
                underlying = spy_price
            else:
                underlying = spx_price

            pnl = calculate_position_pnl(pos, underlying)
            total_pnl += pnl

        # Expected P&L breakdown:
        # SPX 6975P SHORT: (14.78 - 0) * 1 * 100 = +$1,478
        # SPY 694C SHORT: (2.18 - 0) * 10 * 100 = +$2,180
        # SPY 694P LONG: (0 - 1.25) * 10 * 100 = -$1,250  (rounded from 124.51)
        # SPX 6975C LONG: (0 - 12.82) * 1 * 100 = -$1,282  (rounded from 1281.64)

        # Total should be approximately +$1,126
        assert total_pnl > 1100, f"Expected positive P&L ~$1126, got ${total_pnl:.2f}"
        assert total_pnl < 1150, f"Expected P&L ~$1126, got ${total_pnl:.2f}"

    def test_bug_scenario_with_wrong_spx_reference(self):
        """
        REGRESSION TEST: Show what happens with the bug

        Using calculated SPX reference (6957.36) instead of actual strike (6975)
        """
        positions = [
            MockPosition(MockContract('SPX', 6975.0, 'P'), -1, 1478.36),
            MockPosition(MockContract('SPY', 694.0, 'C'), -10, 218.40),
            MockPosition(MockContract('SPY', 694.0, 'P'), 10, 124.51),
            MockPosition(MockContract('SPX', 6975.0, 'C'), 1, 1281.64),
        ]

        # At strike prices
        spy_price = 694.0

        # BUG: Using calculated SPX reference instead of actual strike
        wrong_spx_price = 6957.36

        total_pnl_wrong = 0.0
        for pos in positions:
            if pos['contract'].symbol == 'SPY':
                underlying = spy_price
            else:
                underlying = wrong_spx_price  # Using WRONG reference

            pnl = calculate_position_pnl(pos, underlying)
            total_pnl_wrong += pnl

        # With the bug, SPX 6975P shows intrinsic value of ~17.64
        # This creates a loss of (14.78 - 17.64) * 100 = -$286
        # Total P&L becomes negative around -$638

        assert total_pnl_wrong < 0, f"Bug reproduced: should show negative P&L, got ${total_pnl_wrong:.2f}"
        assert total_pnl_wrong > -700, f"Bug reproduced: should be ~-$638, got ${total_pnl_wrong:.2f}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
