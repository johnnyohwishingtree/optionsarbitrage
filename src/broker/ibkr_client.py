#!/usr/bin/env python3
"""
Interactive Brokers Client
Handles connection and order execution via IB Gateway/TWS
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
try:
    from ib_insync import IB, Stock, Option, Contract, Order, Trade
except (ImportError, RuntimeError):
    from ib_async import IB, Stock, Option, Contract, Order, Trade
import asyncio

logger = logging.getLogger(__name__)


class IBKRClient:
    """Interactive Brokers API Client"""

    def __init__(self, host: str = '127.0.0.1', port: int = 4002, client_id: int = 1):
        """
        Initialize IBKR client

        Args:
            host: IB Gateway host (default: localhost)
            port: IB Gateway port (4002 for paper, 7497 for TWS paper)
            client_id: Unique client ID
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.connected = False

    def connect(self) -> bool:
        """Connect to IB Gateway/TWS"""
        try:
            if not self.ib.isConnected():
                logger.info(f"Connecting to IB Gateway at {self.host}:{self.port}...")
                self.ib.connect(self.host, self.port, clientId=self.client_id)
                self.connected = True
                logger.info("✅ Connected to IB Gateway")

                # Request delayed market data (free, no subscription required)
                # Type 3 = Delayed data (15-20 min delay)
                # Type 4 = Delayed frozen data
                self.ib.reqMarketDataType(3)
                logger.info("📊 Requesting delayed market data (no subscription required)")

                # Get account info
                account = self.get_account_summary()
                if account:
                    logger.info(f"Account: {account.get('account_id', 'Unknown')}")
                    logger.info(f"Net Liquidation: ${account.get('net_liquidation', 0):,.2f}")

                return True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IB Gateway: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB Gateway")

    def is_connected(self) -> bool:
        """Check if connected to IB Gateway"""
        return self.ib.isConnected()

    def get_account_summary(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            if not self.is_connected():
                logger.warning("Not connected to IB Gateway")
                return {}

            account_values = self.ib.accountValues()

            summary = {
                'account_id': self.ib.managedAccounts()[0] if self.ib.managedAccounts() else 'Unknown',
                'net_liquidation': 0.0,
                'total_cash': 0.0,
                'available_funds': 0.0,
                'buying_power': 0.0,
            }

            for item in account_values:
                if item.tag == 'NetLiquidation' and item.currency == 'USD':
                    summary['net_liquidation'] = float(item.value)
                elif item.tag == 'TotalCashValue' and item.currency == 'USD':
                    summary['total_cash'] = float(item.value)
                elif item.tag == 'AvailableFunds' and item.currency == 'USD':
                    summary['available_funds'] = float(item.value)
                elif item.tag == 'BuyingPower' and item.currency == 'USD':
                    summary['buying_power'] = float(item.value)

            return summary

        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {}

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        try:
            if symbol in ('SPX', 'XSP'):
                # SPX and XSP are indices on CBOE
                contract = Contract(symbol=symbol, secType='IND', exchange='CBOE', currency='USD')
            else:
                # SPY is a stock
                contract = Stock(symbol, 'SMART', 'USD')

            self.ib.qualifyContracts(contract)
            ticker = self.ib.reqMktData(contract)

            # Wait longer for delayed market data (3 seconds)
            self.ib.sleep(3)

            price = ticker.marketPrice()
            if price and price > 0:
                logger.info(f"Got {symbol} price: ${price:.2f}")
                return price

            # Fallback to last price
            if ticker.last and ticker.last > 0:
                logger.info(f"Got {symbol} last price: ${ticker.last:.2f}")
                return ticker.last

            # Try close price
            if ticker.close and ticker.close > 0:
                logger.info(f"Got {symbol} close price: ${ticker.close:.2f}")
                return ticker.close

            logger.warning(f"No valid price for {symbol} (bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}, close={ticker.close})")
            return None

        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    def get_option_chain(self, symbol: str, expiration: str, strikes: List[float] = None) -> List[Contract]:
        """
        Get options chain for a symbol

        Args:
            symbol: Underlying symbol (SPY or SPX)
            expiration: Expiration date (YYYYMMDD format)
            strikes: List of strikes to filter (optional)

        Returns:
            List of option contracts
        """
        try:
            if symbol == 'SPX':
                contract = Contract(symbol='SPX', secType='IND', exchange='CBOE', currency='USD')
            else:
                contract = Stock(symbol, 'SMART', 'USD')

            self.ib.qualifyContracts(contract)

            # Get chains
            chains = self.ib.reqSecDefOptParams(
                contract.symbol, '', contract.secType, contract.conId
            )

            if not chains:
                logger.warning(f"No option chains found for {symbol}")
                return []

            # Get all calls for the expiration
            options = []
            for chain in chains:
                if expiration in chain.expirations:
                    for strike in chain.strikes:
                        if strikes is None or strike in strikes:
                            opt = Option(
                                symbol=symbol,
                                lastTradeDateOrContractMonth=expiration,
                                strike=strike,
                                right='C',  # Call
                                exchange=chain.exchange if symbol == 'SPX' else 'SMART'
                            )
                            options.append(opt)

            # Qualify contracts
            if options:
                self.ib.qualifyContracts(*options)

            return options

        except Exception as e:
            logger.error(f"Error getting option chain for {symbol}: {e}")
            return []

    def get_option_quote(self, symbol_or_contract, strike: float = None, right: str = None, expiration: str = None) -> Optional[Dict[str, float]]:
        """
        Get bid/ask quote for an option contract

        Can be called two ways:
        1. get_option_quote(contract) - pass a Contract object
        2. get_option_quote(symbol, strike, right, expiration) - pass parameters
        """
        try:
            # Handle both calling conventions
            if isinstance(symbol_or_contract, Contract):
                contract = symbol_or_contract
            else:
                # Create contract from parameters
                symbol = symbol_or_contract
                if symbol == 'SPX':
                    contract = Option('SPX', expiration, strike, right, 'SMART')
                else:
                    contract = Option(symbol, expiration, strike, right, 'SMART')

                # Qualify the contract
                self.ib.qualifyContracts(contract)

            ticker = self.ib.reqMktData(contract)
            self.ib.sleep(2)  # Wait longer for data

            if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
                return {
                    'bid': ticker.bid,
                    'ask': ticker.ask,
                    'last': ticker.last if ticker.last and ticker.last > 0 else (ticker.bid + ticker.ask) / 2,
                    'bid_size': ticker.bidSize,
                    'ask_size': ticker.askSize,
                    'volume': ticker.volume if hasattr(ticker, 'volume') else None,
                    'open_interest': ticker.openInterest if hasattr(ticker, 'openInterest') else None,
                    'implied_vol': ticker.impliedVolatility if hasattr(ticker, 'impliedVolatility') else None,
                    'delta': ticker.modelGreeks.delta if ticker.modelGreeks else None,
                    'gamma': ticker.modelGreeks.gamma if ticker.modelGreeks else None,
                    'theta': ticker.modelGreeks.theta if ticker.modelGreeks else None,
                    'vega': ticker.modelGreeks.vega if ticker.modelGreeks else None,
                }

            return None

        except Exception as e:
            logger.error(f"Error getting option quote: {e}")
            return None

    def place_option_order(
        self,
        contract: Contract,
        action: str,
        quantity: int,
        order_type: str = 'LMT',
        limit_price: float = None
    ) -> Optional[Trade]:
        """
        Place an option order

        Args:
            contract: Option contract
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            order_type: 'LMT' or 'MKT'
            limit_price: Limit price (required for LMT orders)

        Returns:
            Trade object if successful
        """
        try:
            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = order_type

            if order_type == 'LMT':
                if limit_price is None:
                    logger.error("Limit price required for limit orders")
                    return None
                order.lmtPrice = limit_price

            # Place order
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"Order placed: {action} {quantity} {contract.symbol} @ {limit_price}")

            # Wait for fill (with timeout)
            timeout = 30
            self.ib.sleep(1)

            for _ in range(timeout):
                if trade.orderStatus.status in ['Filled', 'Cancelled']:
                    break
                self.ib.sleep(1)

            if trade.orderStatus.status == 'Filled':
                logger.info(f"✅ Order filled: {action} {quantity} @ {trade.orderStatus.avgFillPrice}")
                return trade
            else:
                logger.warning(f"Order status: {trade.orderStatus.status}")
                return trade

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions"""
        try:
            positions = self.ib.positions()

            result = []
            for pos in positions:
                result.append({
                    'symbol': pos.contract.symbol,
                    'sec_type': pos.contract.secType,
                    'position': pos.position,
                    'avg_cost': pos.avgCost,
                    'market_value': pos.position * pos.avgCost,
                    'contract': pos.contract,
                })

            return result

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_open_orders(self) -> List[Trade]:
        """Get open orders"""
        try:
            return self.ib.openTrades()
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    def cancel_order(self, trade: Trade) -> bool:
        """Cancel an open order"""
        try:
            self.ib.cancelOrder(trade.order)
            logger.info(f"Cancelled order: {trade.order.orderId}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def close_position(self, contract: Contract, quantity: int) -> Optional[Trade]:
        """Close a position (reverse the original action)"""
        try:
            # Determine action (opposite of current position)
            action = 'SELL' if quantity > 0 else 'BUY'
            qty = abs(quantity)

            # Get current market price
            ticker = self.ib.reqMktData(contract)
            self.ib.sleep(1)

            # Use market order to ensure execution
            return self.place_option_order(
                contract=contract,
                action=action,
                quantity=qty,
                order_type='MKT'
            )

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None


if __name__ == "__main__":
    # Test connection
    logging.basicConfig(level=logging.INFO)

    client = IBKRClient()

    if client.connect():
        print("\n✅ Connection successful!")

        # Get account info
        account = client.get_account_summary()
        print(f"\nAccount Info:")
        for key, value in account.items():
            print(f"  {key}: {value}")

        # Get current prices
        spy_price = client.get_current_price('SPY')
        spx_price = client.get_current_price('SPX')

        print(f"\nCurrent Prices:")
        print(f"  SPY: ${spy_price:.2f}" if spy_price else "  SPY: N/A")
        print(f"  SPX: ${spx_price:.2f}" if spx_price else "  SPX: N/A")

        client.disconnect()
    else:
        print("\n❌ Connection failed!")
        print("\nMake sure:")
        print("  1. IB Gateway or TWS is running")
        print("  2. API connections are enabled in settings")
        print("  3. Port is correct (4002 for Gateway paper, 7497 for TWS paper)")
