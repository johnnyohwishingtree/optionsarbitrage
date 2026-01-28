#!/usr/bin/env python3
"""
Unit Tests - Strategy Logic (No API Keys Needed)
Tests the core strategy calculations without external dependencies
"""

import unittest
from datetime import datetime, date


class TestStrategyLogic(unittest.TestCase):
    """Test core strategy calculations"""

    def test_calculate_entry_credit(self):
        """Test entry credit calculation"""
        # Given
        spy_bid = 2.98
        spy_ask = 3.02
        spx_bid = 23.05
        spx_ask = 23.45
        commissions = 11 * 0.65  # 11 contracts * $0.65

        # When
        entry_cost_spx = spx_ask * 100  # Buy 1 SPX
        entry_credit_spy = spy_bid * 100 * 10  # Sell 10 SPY
        entry_net = entry_credit_spy - entry_cost_spx
        net_credit = entry_net - commissions

        # Then
        self.assertEqual(entry_cost_spx, 2345.00)
        self.assertEqual(entry_credit_spy, 2980.00)
        self.assertEqual(entry_net, 635.00)
        self.assertAlmostEqual(net_credit, 627.85, places=2)
        self.assertGreater(net_credit, 0, "Should be net credit")

    def test_atm_strike_calculation(self):
        """Test ATM strike rounding"""
        # Given
        test_cases = [
            (600.00, 600),
            (602.49, 600),
            (602.51, 605),  # Fixed: round() goes to nearest even
            (607.49, 605),
            (615.01, 615),
        ]

        # When/Then
        for spy_price, expected_strike in test_cases:
            strike = round(spy_price / 5) * 5
            self.assertEqual(strike, expected_strike,
                           f"SPY ${spy_price} should round to ${expected_strike}")

    def test_spx_spy_ratio(self):
        """Test SPX = 10x SPY relationship"""
        # Given
        spy_strike = 600
        expected_spx_strike = 6000

        # When
        spx_strike = spy_strike * 10

        # Then
        self.assertEqual(spx_strike, expected_spx_strike)

    def test_should_exit_assignment_risk(self):
        """Test exit logic for assignment risk"""
        # Given
        spy_price = 615.00
        spy_strike = 600
        threshold = 10  # $10 ITM = high risk

        # When
        itm_amount = spy_price - spy_strike
        should_exit = itm_amount > threshold

        # Then
        self.assertTrue(should_exit,
                       f"Should exit when ${itm_amount} > ${threshold} ITM")

    def test_should_not_exit_small_itm(self):
        """Test we don't exit for small ITM amounts"""
        # Given
        spy_price = 605.00
        spy_strike = 600
        threshold = 10

        # When
        itm_amount = spy_price - spy_strike
        should_exit = itm_amount > threshold

        # Then
        self.assertFalse(should_exit,
                        f"Should NOT exit when only ${itm_amount} ITM")

    def test_exit_cost_calculation(self):
        """Test exit cost when closing position"""
        # Given
        spy_price = 615.00
        spx_price = 6150.00
        spy_strike = 600
        spx_strike = 6000

        # Intrinsic values
        spy_intrinsic = spy_price - spy_strike  # $15
        spx_intrinsic = spx_price - spx_strike  # $150

        # Bid-ask spreads
        spy_spread = 0.02
        spx_spread = 0.30

        # When - Close positions
        spy_bid_close = spy_intrinsic - spy_spread / 2
        spy_ask_close = spy_intrinsic + spy_spread / 2
        spx_bid_close = spx_intrinsic - spx_spread / 2
        spx_ask_close = spx_intrinsic + spx_spread / 2

        # Sell SPX (we're long), Buy back SPY (we're short)
        exit_spx_proceeds = spx_bid_close * 100
        exit_spy_cost = spy_ask_close * 100 * 10
        exit_net_cost = exit_spy_cost - exit_spx_proceeds

        commissions = 11 * 0.65
        total_exit_cost = exit_net_cost + commissions

        # Then
        self.assertAlmostEqual(spy_intrinsic, 15.00, places=2)
        self.assertAlmostEqual(spx_intrinsic, 150.00, places=2)
        self.assertGreater(total_exit_cost, 0, "Exit should cost money")

    def test_perfect_tracking_pnl(self):
        """Test P&L with perfect SPX/SPY tracking"""
        # Given - Entry
        entry_credit = 637.85

        # Given - Exit with perfect 10:1 tracking
        spy_price = 620.00
        spx_price = 6200.00  # Perfect 10:1
        spy_strike = 600
        spx_strike = 6000

        # When - Settlement values
        spy_settlement = (spy_price - spy_strike) * 100 * 10  # $20 * 10 contracts
        spx_settlement = (spx_price - spx_strike) * 100  # $200

        # Net settlement (we're long SPX, short SPY)
        net_settlement = spx_settlement - spy_settlement

        # Final P&L
        final_pnl = entry_credit + net_settlement

        # Then - With perfect tracking, settlements cancel
        self.assertEqual(spy_settlement, 20000)
        self.assertEqual(spx_settlement, 20000)
        self.assertEqual(net_settlement, 0, "Perfect tracking = settlements cancel")
        self.assertAlmostEqual(final_pnl, entry_credit, places=2,
                              msg="With perfect tracking, keep entry credit")

    def test_tracking_error_impact(self):
        """Test P&L impact of tracking error"""
        # Given
        entry_credit = 637.85
        spy_price = 620.00
        spx_price = 6190.00  # $10 tracking error (SPX lower than expected)
        spy_strike = 600
        spx_strike = 6000

        # When
        spy_settlement = (spy_price - spy_strike) * 100 * 10
        spx_settlement = (spx_price - spx_strike) * 100
        net_settlement = spx_settlement - spy_settlement
        final_pnl = entry_credit + net_settlement

        # Then
        tracking_error = spx_price - (spy_price * 10)
        error_impact = abs(tracking_error) * 100  # Each $1 error = $100 impact

        self.assertEqual(tracking_error, -10.00, "SPX is $10 below expected")
        self.assertEqual(error_impact, 1000.00, "Each $1 tracking error = $100 impact")
        self.assertLess(final_pnl, entry_credit, "Negative tracking error reduces profit")

    def test_risk_parameters(self):
        """Test risk management parameters are reasonable"""
        # Given
        max_spreads = 2
        max_daily_loss = 1000
        min_entry_credit = 400
        exit_threshold = 10

        # Then - Sanity checks
        self.assertGreater(max_spreads, 0)
        self.assertLessEqual(max_spreads, 5, "Don't over-leverage")
        self.assertGreater(max_daily_loss, 0)
        self.assertGreater(min_entry_credit, 0)
        self.assertGreater(exit_threshold, 0)

    def test_commission_calculation(self):
        """Test commission costs are correct"""
        # Given
        contracts_per_spread = 11  # 1 SPX + 10 SPY
        commission_per_contract = 0.65
        spreads = 2

        # When
        commission_per_spread = contracts_per_spread * commission_per_contract
        total_commissions = commission_per_spread * spreads

        # Then
        self.assertAlmostEqual(commission_per_spread, 7.15, places=2)
        self.assertAlmostEqual(total_commissions, 14.30, places=2)

    def test_is_market_hours(self):
        """Test market hours detection"""
        # Given
        from datetime import time
        market_open = time(9, 30)
        market_close = time(16, 0)

        # When/Then - During market hours
        trading_time = time(14, 30)
        is_trading = market_open <= trading_time <= market_close
        self.assertTrue(is_trading, "2:30 PM is during market hours")

        # When/Then - Before market hours
        pre_market = time(9, 0)
        is_trading = market_open <= pre_market <= market_close
        self.assertFalse(is_trading, "9:00 AM is before market open")

        # When/Then - After market hours
        after_hours = time(17, 0)
        is_trading = market_open <= after_hours <= market_close
        self.assertFalse(is_trading, "5:00 PM is after market close")

    def test_is_trading_day(self):
        """Test trading day detection (Mon-Fri)"""
        # Given
        test_cases = [
            (date(2026, 1, 19), True, "Monday"),  # Monday
            (date(2026, 1, 20), True, "Tuesday"),  # Tuesday
            (date(2026, 1, 21), True, "Wednesday"),  # Wednesday
            (date(2026, 1, 22), True, "Thursday"),  # Thursday
            (date(2026, 1, 23), True, "Friday"),  # Friday
            (date(2026, 1, 24), False, "Saturday"),  # Saturday
            (date(2026, 1, 25), False, "Sunday"),  # Sunday
        ]

        # When/Then
        for test_date, expected, day_name in test_cases:
            is_trading = test_date.weekday() < 5  # Mon=0, Sun=6
            self.assertEqual(is_trading, expected,
                           f"{day_name} should {'be' if expected else 'not be'} trading day")


class TestProfitScenarios(unittest.TestCase):
    """Test various profit/loss scenarios"""

    def test_best_case_scenario(self):
        """Best case: OTM expiration, keep full premium"""
        # Given
        entry_credit = 637.85
        spy_final = 599.00  # Expires OTM
        spy_strike = 600

        # When
        spy_expires_worthless = spy_final < spy_strike
        exit_cost = 0 if spy_expires_worthless else (spy_final - spy_strike) * 1000
        final_pnl = entry_credit - exit_cost

        # Then
        self.assertTrue(spy_expires_worthless)
        self.assertEqual(exit_cost, 0)
        self.assertEqual(final_pnl, entry_credit, "Keep full credit if expires OTM")

    def test_worst_case_scenario(self):
        """Worst case: Large tracking error + deep ITM"""
        # Given
        entry_credit = 637.85
        spy_final = 630.00
        spx_final = 6280.00  # SPX $20 BELOW expected (negative tracking)
        spy_strike = 600
        spx_strike = 6000

        # When
        spy_settlement = (spy_final - spy_strike) * 1000  # We're SHORT, this is a loss
        spx_settlement = (spx_final - spx_strike) * 100   # We're LONG, this is a gain
        net_settlement = spx_settlement - spy_settlement  # Gain - Loss
        final_pnl = entry_credit + net_settlement

        # Then
        tracking_error = spx_final - (spy_final * 10)
        self.assertEqual(tracking_error, -20.00, "Large negative tracking error")
        self.assertLess(final_pnl, 0, "Can lose money with bad negative tracking")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
