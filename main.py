#!/usr/bin/env python3
"""
SPY/SPX Automated Trading System
Main orchestrator that runs continuously
"""

import os
import sys
import logging
import threading
import time
import schedule
import yaml
from datetime import datetime, time as dtime
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.broker.ibkr_client import IBKRClient
from src.strategy.spy_spx_strategy import SPYSPXStrategy
from src.strategy.position_monitor import PositionMonitor
from src.database.models import DatabaseManager
from src.ui.dashboard import run_dashboard, set_trading_system

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class TradingSystem:
    """Main trading system orchestrator"""

    def __init__(self):
        """Initialize trading system"""
        logger.info("=" * 80)
        logger.info("SPY/SPX AUTOMATED TRADING SYSTEM")
        logger.info("=" * 80)

        # Load configuration
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize components
        logger.info("Initializing components...")

        self.ib_client = IBKRClient(
            host=os.getenv('IB_HOST', '127.0.0.1'),
            port=int(os.getenv('IB_PORT', 4002)),
            client_id=int(os.getenv('IB_CLIENT_ID', 1))
        )

        self.strategy = SPYSPXStrategy(self.config['trading'])
        self.db = DatabaseManager('data/trading.db')
        self.monitor = PositionMonitor(self.ib_client, self.strategy, self.db)

        self.is_trading = False
        self.is_running = True

        logger.info("✅ System initialized")

    def connect(self) -> bool:
        """Connect to IB Gateway"""
        logger.info("Connecting to IB Gateway...")
        return self.ib_client.connect()

    def start_trading(self):
        """Enable automated trading"""
        self.is_trading = True
        self.db.update_system_state({'is_trading': True})
        logger.info("🟢 Trading enabled")

    def stop_trading(self):
        """Disable automated trading"""
        self.is_trading = False
        self.db.update_system_state({'is_trading': False})
        logger.info("🔴 Trading disabled")

    def morning_routine(self):
        """Morning entry routine (9:35 AM)"""
        try:
            if not self.is_trading:
                logger.info("Trading disabled, skipping entry")
                return

            logger.info("=" * 80)
            logger.info("MORNING ENTRY ROUTINE")
            logger.info("=" * 80)

            # Check if we've already done max trades today
            trades_today = len(self.db.get_todays_trades())
            max_trades = self.config['trading']['max_spreads_per_day']

            if trades_today >= max_trades:
                logger.info(f"Already executed {trades_today} trades today (max: {max_trades})")
                return

            # Get current prices
            spy_price = self.ib_client.get_current_price('SPY')
            spx_price = self.ib_client.get_current_price('SPX')

            if not spy_price or not spx_price:
                logger.error("Could not get current prices")
                return

            logger.info(f"Current prices: SPY=${spy_price:.2f}, SPX=${spx_price:.2f}")

            # Create option contracts
            contracts = self.strategy.create_option_contracts(spy_price, spx_price)

            # Get option quotes
            spy_quote = self.ib_client.get_option_quote(contracts['spy_call'])
            spx_quote = self.ib_client.get_option_quote(contracts['spx_call'])

            if not spy_quote or not spx_quote:
                logger.error("Could not get option quotes")
                return

            logger.info(f"SPY {contracts['spy_strike']} Call: Bid=${spy_quote['bid']:.2f}, Ask=${spy_quote['ask']:.2f}")
            logger.info(f"SPX {contracts['spx_strike']} Call: Bid=${spx_quote['bid']:.2f}, Ask=${spx_quote['ask']:.2f}")

            # Check if we should enter trade
            should_enter, reason = self.strategy.should_enter_trade(
                spy_price=spy_price,
                spx_price=spx_price,
                spy_bid=spy_quote['bid'],
                spx_ask=spx_quote['ask'],
                trades_today=trades_today
            )

            logger.info(f"Entry decision: {should_enter} - {reason}")

            if not should_enter:
                return

            # Calculate entry credit
            credit_calc = self.strategy.calculate_entry_credit(
                spy_bid=spy_quote['bid'],
                spx_ask=spx_quote['ask']
            )

            logger.info(f"Entry credit: ${credit_calc['net_credit']:.2f}")

            # Execute trade
            logger.info("Executing trade...")

            # Buy SPX call
            spx_trade = self.ib_client.place_option_order(
                contract=contracts['spx_call'],
                action='BUY',
                quantity=1,
                order_type='LMT',
                limit_price=spx_quote['ask']
            )

            # Sell SPY calls
            spy_trade = self.ib_client.place_option_order(
                contract=contracts['spy_call'],
                action='SELL',
                quantity=10,
                order_type='LMT',
                limit_price=spy_quote['bid']
            )

            if spx_trade and spy_trade:
                # Log trade to database
                trade_data = {
                    'trade_date': datetime.now(),
                    'spy_price': spy_price,
                    'spx_price': spx_price,
                    'spy_strike': contracts['spy_strike'],
                    'spx_strike': contracts['spx_strike'],
                    'spy_entry_bid': spy_quote['bid'],
                    'spy_entry_ask': spy_quote['ask'],
                    'spx_entry_bid': spx_quote['bid'],
                    'spx_entry_ask': spx_quote['ask'],
                    'entry_credit': credit_calc['net_credit'],
                    'entry_time': datetime.now(),
                    'entry_filled': True,
                    'commissions': credit_calc['commissions'],
                    'status': 'ACTIVE'
                }

                trade = self.db.add_trade(trade_data)
                logger.info(f"✅ Trade #{trade.id} entered successfully!")

                # Update system state
                self.db.update_system_state({
                    'trades_today': trades_today + 1,
                    'open_positions': len(self.db.get_active_trades())
                })

            else:
                logger.error("❌ Failed to execute trade")

        except Exception as e:
            logger.error(f"Error in morning routine: {e}", exc_info=True)

    def monitor_positions_routine(self):
        """Monitor positions throughout the day"""
        try:
            if not self.is_trading:
                return

            results = self.monitor.monitor_positions()

            for result in results:
                if result['should_exit']:
                    logger.warning(f"Exit signal detected: {result['exit_reason']}")

                    # Close position
                    success = self.monitor.close_position(
                        trade=result['trade'],
                        spy_price=result['spy_price'],
                        spx_price=result['spx_price']
                    )

                    if success:
                        # Update system state
                        self.db.update_system_state({
                            'open_positions': len(self.db.get_active_trades())
                        })

        except Exception as e:
            logger.error(f"Error monitoring positions: {e}", exc_info=True)

    def end_of_day_routine(self):
        """End of day settlement"""
        try:
            logger.info("=" * 80)
            logger.info("END OF DAY ROUTINE")
            logger.info("=" * 80)

            # Handle any remaining positions at expiration
            active_trades = self.db.get_active_trades()

            for trade in active_trades:
                logger.info(f"Settling trade #{trade.id} at expiration")
                self.monitor.handle_expiration(trade)

            # Update daily summary
            todays_trades = self.db.get_todays_trades()
            winning_trades = len([t for t in todays_trades if t.final_pnl and t.final_pnl > 0])
            losing_trades = len([t for t in todays_trades if t.final_pnl and t.final_pnl < 0])
            total_pnl = sum(t.final_pnl for t in todays_trades if t.final_pnl)

            summary_data = {
                'date': datetime.now(),
                'trades_count': len(todays_trades),
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'total_pnl': total_pnl,
                'net_pnl': total_pnl
            }

            self.db.update_daily_summary(summary_data)

            logger.info(f"Day complete: {len(todays_trades)} trades, P&L: ${total_pnl:.2f}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in end of day routine: {e}", exc_info=True)

    def schedule_tasks(self):
        """Schedule all automated tasks"""
        logger.info("Scheduling automated tasks...")

        # Morning entry (9:35 AM ET)
        schedule.every().day.at("09:35").do(self.morning_routine)

        # Monitor positions every 5 minutes during market hours
        schedule.every(5).minutes.do(self.monitor_positions_routine)

        # End of day routine (4:05 PM ET)
        schedule.every().day.at("16:05").do(self.end_of_day_routine)

        logger.info("✅ Tasks scheduled")

    def run(self):
        """Main run loop"""
        try:
            # Connect to IB Gateway
            if not self.connect():
                logger.error("Failed to connect to IB Gateway. Exiting.")
                return

            # Schedule tasks
            self.schedule_tasks()

            # Start dashboard in separate thread
            logger.info("Starting dashboard server...")
            set_trading_system(self)
            dashboard_thread = threading.Thread(
                target=run_dashboard,
                args=('127.0.0.1', 5000),
                daemon=True
            )
            dashboard_thread.start()

            logger.info("=" * 80)
            logger.info("🚀 System running")
            logger.info("Dashboard: http://localhost:5000")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 80)

            # Main loop
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("\n\nShutdown requested...")
            self.shutdown()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down system...")
        self.is_running = False

        # Disconnect from IB
        self.ib_client.disconnect()

        # Close database
        self.db.close()

        logger.info("✅ Shutdown complete")

    # API methods for dashboard
    def get_system_status(self):
        """Get system status for dashboard"""
        state = self.db.get_system_state()
        return {
            'is_trading': self.is_trading,
            'is_connected': self.ib_client.is_connected(),
            'open_positions': len(self.db.get_active_trades()),
            'trades_today': len(self.db.get_todays_trades()),
        }

    def get_positions_summary(self):
        """Get positions summary for dashboard"""
        active_trades = self.db.get_active_trades()
        positions = []

        for trade in active_trades:
            spy_price = self.ib_client.get_current_price('SPY')
            spx_price = self.ib_client.get_current_price('SPX')

            if spy_price and spx_price:
                spy_value = max(0, spy_price - trade.spy_strike) * 100 * 10
                spx_value = max(0, spx_price - trade.spx_strike) * 100
                current_pnl = trade.entry_credit - (spy_value - spx_value)
            else:
                current_pnl = 0

            positions.append({
                'trade_id': trade.id,
                'entry_time': trade.entry_time.strftime('%Y-%m-%d %H:%M'),
                'spy_strike': trade.spy_strike,
                'spx_strike': trade.spx_strike,
                'entry_credit': trade.entry_credit,
                'current_pnl': current_pnl,
                'status': trade.status
            })

        return positions

    def get_trade_history(self, limit=50):
        """Get trade history for dashboard"""
        trades = self.db.get_all_trades()[-limit:]
        return [{
            'id': t.id,
            'trade_date': t.trade_date.strftime('%Y-%m-%d %H:%M'),
            'entry_credit': t.entry_credit,
            'final_pnl': t.final_pnl,
            'exit_reason': t.exit_reason,
            'status': t.status
        } for t in trades]

    def get_account_info(self):
        """Get account info for dashboard"""
        return self.ib_client.get_account_summary()

    def get_market_prices(self):
        """Get market prices for dashboard"""
        return {
            'spy_price': self.ib_client.get_current_price('SPY'),
            'spx_price': self.ib_client.get_current_price('SPX'),
        }

    def get_performance_metrics(self):
        """Get performance metrics for dashboard"""
        return self.monitor.check_risk_limits()

    def emergency_close_all(self):
        """Emergency close all positions"""
        return self.monitor.emergency_close_all()


if __name__ == "__main__":
    # Create logs and data directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)

    # Create and run trading system
    system = TradingSystem()
    system.run()
