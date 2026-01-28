#!/usr/bin/env python3
"""
Position Monitor
Tracks open positions and manages exits
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.broker.ibkr_client import IBKRClient
from src.strategy.spy_spx_strategy import SPYSPXStrategy
from src.database.models import DatabaseManager, Trade

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitor and manage open positions"""

    def __init__(
        self,
        ibkr_client: IBKRClient,
        strategy: SPYSPXStrategy,
        db_manager: DatabaseManager
    ):
        """
        Initialize position monitor

        Args:
            ibkr_client: IBKR client instance
            strategy: Strategy instance
            db_manager: Database manager instance
        """
        self.client = ibkr_client
        self.strategy = strategy
        self.db = db_manager

    def get_active_positions(self) -> List[Dict[str, Any]]:
        """
        Get all active option positions from IBKR

        Returns:
            List of position dicts
        """
        try:
            positions = self.client.get_positions()

            # Filter for options only
            option_positions = [
                pos for pos in positions
                if pos['sec_type'] == 'OPT' and pos['symbol'] in ['SPY', 'SPX']
            ]

            return option_positions

        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return []

    def monitor_positions(self) -> List[Dict[str, Any]]:
        """
        Monitor all active positions and check for exit signals

        Returns:
            List of positions with exit signals
        """
        results = []

        try:
            # Get active trades from database
            active_trades = self.db.get_active_trades()

            if not active_trades:
                logger.debug("No active trades to monitor")
                return results

            logger.info(f"Monitoring {len(active_trades)} active positions...")

            for trade in active_trades:
                # Get current prices
                spy_price = self.client.get_current_price('SPY')
                spx_price = self.client.get_current_price('SPX')

                if not spy_price or not spx_price:
                    logger.warning(f"Could not get prices for trade {trade.id}")
                    continue

                # Check exit conditions
                should_exit, reason = self.strategy.should_exit_position(
                    spy_price=spy_price,
                    spy_strike=trade.spy_strike,
                    spx_price=spx_price,
                    spx_strike=trade.spx_strike,
                    entry_credit=trade.entry_credit
                )

                # Calculate current P&L estimate
                spy_value = max(0, spy_price - trade.spy_strike) * 100 * 10
                spx_value = max(0, spx_price - trade.spx_strike) * 100
                current_pnl = trade.entry_credit - (spy_value - spx_value)

                result = {
                    'trade_id': trade.id,
                    'spy_price': spy_price,
                    'spx_price': spx_price,
                    'current_pnl': current_pnl,
                    'should_exit': should_exit,
                    'exit_reason': reason,
                    'trade': trade
                }

                results.append(result)

                # Log status
                if should_exit:
                    logger.warning(f"⚠️  Exit signal for trade {trade.id}: {reason}")
                else:
                    logger.info(f"✅ Trade {trade.id} OK - P&L: ${current_pnl:.2f}")

            return results

        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
            return results

    def close_position(self, trade: Trade, spy_price: float, spx_price: float) -> bool:
        """
        Close a position

        Args:
            trade: Trade record
            spy_price: Current SPY price
            spx_price: Current SPX price

        Returns:
            True if successfully closed
        """
        try:
            logger.info(f"Closing position for trade {trade.id}...")

            # Create option contracts
            contracts = self.strategy.create_option_contracts(spy_price, spx_price)

            # We're short SPY calls, so we need to BUY them back
            spy_trade = self.client.place_option_order(
                contract=contracts['spy_call'],
                action='BUY',
                quantity=10,
                order_type='MKT'
            )

            # We're long SPX call, so we need to SELL it
            spx_trade = self.client.place_option_order(
                contract=contracts['spx_call'],
                action='SELL',
                quantity=1,
                order_type='MKT'
            )

            if spy_trade and spx_trade:
                # Calculate exit cost
                spy_fill = spy_trade.orderStatus.avgFillPrice
                spx_fill = spx_trade.orderStatus.avgFillPrice

                exit_calc = self.strategy.calculate_exit_cost(
                    spy_ask=spy_fill,
                    spx_bid=spx_fill
                )

                # Calculate final P&L
                final_pnl = trade.entry_credit - exit_calc['total_cost']

                # Update database
                self.db.update_trade(trade.id, {
                    'spy_exit_price': spy_fill,
                    'spx_exit_price': spx_fill,
                    'exit_cost': exit_calc['total_cost'],
                    'exit_time': datetime.now(),
                    'exit_reason': 'EARLY_CLOSE',
                    'final_pnl': final_pnl,
                    'status': 'CLOSED'
                })

                logger.info(f"✅ Position closed - P&L: ${final_pnl:.2f}")
                return True
            else:
                logger.error("Failed to close one or both legs")
                return False

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False

    def handle_expiration(self, trade: Trade) -> bool:
        """
        Handle position at expiration (settlement)

        Args:
            trade: Trade record

        Returns:
            True if successfully handled
        """
        try:
            logger.info(f"Handling expiration for trade {trade.id}...")

            # Get final settlement prices
            spy_price = self.client.get_current_price('SPY')
            spx_price = self.client.get_current_price('SPX')

            if not spy_price or not spx_price:
                logger.error("Could not get settlement prices")
                return False

            # Calculate final P&L
            pnl_calc = self.strategy.calculate_final_pnl(
                entry_credit=trade.entry_credit,
                spy_settlement=spy_price,
                spx_settlement=spx_price,
                spy_strike=trade.spy_strike,
                spx_strike=trade.spx_strike
            )

            # Update database
            self.db.update_trade(trade.id, {
                'spy_exit_price': spy_price,
                'spx_exit_price': spx_price,
                'exit_time': datetime.now(),
                'exit_reason': 'EXPIRATION',
                'final_pnl': pnl_calc['net_pnl'],
                'status': 'CLOSED'
            })

            logger.info(f"✅ Expiration handled - P&L: ${pnl_calc['net_pnl']:.2f}")
            return True

        except Exception as e:
            logger.error(f"Error handling expiration: {e}")
            return False

    def check_risk_limits(self) -> Dict[str, Any]:
        """
        Check if any risk limits are breached

        Returns:
            Dict with risk status
        """
        try:
            # Get today's trades
            todays_trades = self.db.get_todays_trades()

            # Calculate daily P&L
            daily_pnl = sum(
                t.final_pnl for t in todays_trades
                if t.final_pnl is not None
            )

            # Get active trades for unrealized P&L
            active_trades = self.db.get_active_trades()
            unrealized_pnl = 0

            for trade in active_trades:
                spy_price = self.client.get_current_price('SPY')
                spx_price = self.client.get_current_price('SPX')

                if spy_price and spx_price:
                    spy_value = max(0, spy_price - trade.spy_strike) * 100 * 10
                    spx_value = max(0, spx_price - trade.spx_strike) * 100
                    unrealized_pnl += trade.entry_credit - (spy_value - spx_value)

            total_pnl = daily_pnl + unrealized_pnl

            # Check limits
            max_daily_loss = self.strategy.config.get('max_daily_loss', 1000)
            risk_breached = total_pnl < -max_daily_loss

            return {
                'daily_realized_pnl': daily_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': total_pnl,
                'max_daily_loss': max_daily_loss,
                'risk_breached': risk_breached,
                'trades_count': len(todays_trades),
                'active_positions': len(active_trades)
            }

        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return {'error': str(e)}

    def emergency_close_all(self) -> bool:
        """
        Emergency close all positions (risk limit breached)

        Returns:
            True if all positions closed
        """
        try:
            logger.warning("🚨 EMERGENCY CLOSE ALL POSITIONS 🚨")

            active_trades = self.db.get_active_trades()

            for trade in active_trades:
                spy_price = self.client.get_current_price('SPY')
                spx_price = self.client.get_current_price('SPX')

                if spy_price and spx_price:
                    self.close_position(trade, spy_price, spx_price)

            logger.info("All positions closed")
            return True

        except Exception as e:
            logger.error(f"Error in emergency close: {e}")
            return False
