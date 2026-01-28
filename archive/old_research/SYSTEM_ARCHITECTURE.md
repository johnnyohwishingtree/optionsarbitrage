# Automated SPY/SPX Arbitrage Trading System
## Complete Technical Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    AUTOMATED TRADING SYSTEM                       │
│                                                                   │
│  ┌────────────┐   ┌─────────────┐   ┌──────────────┐            │
│  │   Market   │──▶│  Strategy   │──▶│    Order     │            │
│  │   Data     │   │   Engine    │   │  Execution   │            │
│  └────────────┘   └─────────────┘   └──────────────┘            │
│         │                                     │                   │
│         ▼                                     ▼                   │
│  ┌────────────┐                      ┌──────────────┐            │
│  │ Position   │                      │   Broker     │            │
│  │ Monitor    │◀─────────────────────│   API        │            │
│  └────────────┘                      │ (Alpaca/IBKR)│            │
│         │                            └──────────────┘            │
│         ▼                                                         │
│  ┌────────────┐   ┌─────────────┐   ┌──────────────┐            │
│  │   Risk     │──▶│  Results    │──▶│  Dashboard   │            │
│  │ Management │   │   Logger    │   │  & Alerts    │            │
│  └────────────┘   └─────────────┘   └──────────────┘            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Core Technologies
```yaml
Language: Python 3.9+
APIs:
  - alpaca-trade-api (Option 1)
  - ib_insync (Option 2)
  - yfinance (backup data)

Data Storage:
  - SQLite (local database)
  - CSV (exports)
  - JSON (configuration)

Scheduling:
  - schedule (simple cron)
  - APScheduler (advanced)

Monitoring:
  - logging (built-in)
  - Streamlit (dashboard - optional)
  - Email/SMS alerts
```

### Deployment Options
```yaml
Option 1 - Local Mac:
  - Runs on your computer
  - Cron job for daily execution
  - Simple, reliable

Option 2 - Cloud (AWS):
  - Lambda functions (serverless)
  - CloudWatch events (scheduling)
  - More robust, always-on

Option 3 - VPS/Raspberry Pi:
  - Always-on server
  - Lowest cost
  - Full control
```

## Module Breakdown

### 1. Market Data Module (`market_data.py`)

**Responsibilities:**
- Fetch current SPY and SPX prices
- Get 0DTE options chains
- Calculate ATM strikes
- Extract bid/ask spreads

**APIs Used:**
- Alpaca Market Data API (real-time)
- IBKR TWS API (alternative)
- yfinance (backup)

**Example Output:**
```python
{
  "timestamp": "2026-01-20 09:35:00",
  "spy_price": 600.25,
  "spx_price": 6002.50,
  "spy_strike": 600,
  "spx_strike": 6000,
  "spy_call": {"bid": 2.98, "ask": 3.02},
  "spx_call": {"bid": 23.00, "ask": 23.40}
}
```

**Code Structure:**
```python
class MarketDataCollector:
    def __init__(self, api_client):
        self.client = api_client

    def get_current_prices(self):
        """Fetch SPY and SPX current prices"""
        pass

    def get_atm_strikes(self, price):
        """Calculate ATM strikes"""
        pass

    def get_options_quotes(self, symbol, strike, expiry):
        """Get option bid/ask"""
        pass

    def get_trade_setup(self):
        """Complete trade setup with all data"""
        pass
```

---

### 2. Strategy Engine (`strategy_engine.py`)

**Responsibilities:**
- Analyze market data
- Decide if trade setup is valid
- Calculate expected profit
- Determine position sizing

**Logic:**
```python
def should_enter_trade(market_data):
    """
    Entry criteria:
    1. Market is open
    2. Time is 9:35-10:00 AM ET
    3. 0DTE options available
    4. SPX/SPY tracking is normal (ratio 9.95-10.05)
    5. Bid/ask spreads are reasonable
    6. Expected profit > $400
    """

def calculate_entry_credit(spy_bid, spx_ask):
    """
    Calculate net credit:
    - Receive: 10 × SPY bid × $100
    - Pay: 1 × SPX ask × $100
    - Subtract: commissions
    """

def calculate_position_size(account_value):
    """
    Risk management:
    - Max 2-3 spreads at once
    - Require $25K margin per spread
    """
```

**Example Output:**
```python
{
  "should_trade": True,
  "entry_credit": 637.85,
  "risk": "LOW",
  "position_size": 1,  # num spreads
  "spy_quantity": 10,
  "spx_quantity": 1
}
```

---

### 3. Order Execution (`order_executor.py`)

**Responsibilities:**
- Place orders via broker API
- Handle order validation
- Confirm fills
- Error handling

**Alpaca Implementation:**
```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import OptionOrderRequest

class OrderExecutor:
    def __init__(self, api_key, secret_key, paper=True):
        self.client = TradingClient(api_key, secret_key, paper=paper)

    def place_spread_order(self, setup):
        """
        Place multi-leg order:
        1. Buy SPX call
        2. Sell SPY calls
        """
        # Buy SPX
        spx_order = self.buy_option(
            symbol="SPX",
            strike=setup['spx_strike'],
            expiry=setup['expiry'],
            quantity=1,
            order_type='LIMIT',
            limit_price=setup['spx_ask']
        )

        # Sell SPY
        spy_order = self.sell_option(
            symbol="SPY",
            strike=setup['spy_strike'],
            expiry=setup['expiry'],
            quantity=10,
            order_type='LIMIT',
            limit_price=setup['spy_bid']
        )

        return {
            'spx_order': spx_order,
            'spy_order': spy_order,
            'status': 'FILLED' or 'PENDING'
        }
```

**IBKR Implementation:**
```python
from ib_insync import IB, Option, Order

class OrderExecutor:
    def __init__(self, host='127.0.0.1', port=7497):
        self.ib = IB()
        self.ib.connect(host, port, clientId=1)

    def place_spread_order(self, setup):
        # Create option contracts
        spx_contract = Option(
            'SPX', '20260120', setup['spx_strike'], 'C', 'CBOE'
        )
        spy_contract = Option(
            'SPY', '20260120', setup['spy_strike'], 'C', 'SMART'
        )

        # Place orders
        spx_order = Order('BUY', 1, 'LMT', setup['spx_ask'])
        spy_order = Order('SELL', 10, 'LMT', setup['spy_bid'])

        # Execute
        spx_trade = self.ib.placeOrder(spx_contract, spx_order)
        spy_trade = self.ib.placeOrder(spy_contract, spy_order)

        return {
            'spx_trade': spx_trade,
            'spy_trade': spy_trade
        }
```

---

### 4. Position Monitor (`position_monitor.py`)

**Responsibilities:**
- Track open positions
- Monitor for exit signals
- Check assignment risk
- Calculate real-time P&L

**Exit Logic:**
```python
class PositionMonitor:
    def check_exit_conditions(self, position, current_price):
        """
        Exit if:
        1. SPY > strike + $10 (assignment risk)
        2. Time is 3:45 PM (close before expiration)
        3. Loss exceeds max ($500)
        4. Manual override
        """

        spy_itm_amount = current_price - position['spy_strike']

        if spy_itm_amount > 10:
            return {
                'should_exit': True,
                'reason': 'ASSIGNMENT_RISK',
                'urgency': 'HIGH'
            }

        if time.now() > '15:45' and spy_itm_amount > 0:
            return {
                'should_exit': True,
                'reason': 'PRE_EXPIRATION',
                'urgency': 'MEDIUM'
            }

        return {'should_exit': False}

    def close_position(self, position):
        """
        Close both legs:
        1. Sell SPX call (we're long)
        2. Buy back SPY calls (we're short)
        """
        pass
```

**Monitoring Schedule:**
```python
# Check every 5 minutes during market hours
schedule.every(5).minutes.do(monitor_positions)

# Force check at 3:45 PM
schedule.every().day.at("15:45").do(check_final_exit)
```

---

### 5. Results Logger (`results_logger.py`)

**Responsibilities:**
- Log all trades to database
- Export to CSV
- Calculate statistics
- Generate reports

**Database Schema (SQLite):**
```sql
CREATE TABLE trades (
    trade_id INTEGER PRIMARY KEY,
    date DATE,
    spy_price REAL,
    spx_price REAL,
    spy_strike REAL,
    spx_strike REAL,
    spy_bid REAL,
    spy_ask REAL,
    spx_bid REAL,
    spx_ask REAL,
    entry_credit REAL,
    exit_cost REAL,
    exit_reason TEXT,
    final_pnl REAL,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP
);

CREATE TABLE daily_summary (
    date DATE PRIMARY KEY,
    trades_count INTEGER,
    total_pnl REAL,
    win_rate REAL,
    notes TEXT
);
```

**CSV Export:**
```python
def export_to_csv(start_date, end_date):
    """
    Generate CSV with:
    - All trades
    - Daily summaries
    - Cumulative P&L
    - Win rate over time
    """
    df = pd.read_sql(f"""
        SELECT * FROM trades
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
    """, db)

    df.to_csv(f'trades_{start_date}_to_{end_date}.csv')
```

---

### 6. Risk Management (`risk_manager.py`)

**Responsibilities:**
- Position sizing
- Max loss limits
- Circuit breakers
- Account protection

**Rules:**
```python
class RiskManager:
    MAX_SPREADS = 3
    MAX_DAILY_LOSS = 1000
    MAX_POSITION_SIZE = 0.1  # 10% of account

    def can_open_position(self, account_value, current_positions):
        """
        Checks:
        1. Not too many open positions
        2. Haven't hit daily loss limit
        3. Have enough margin
        4. Account value sufficient
        """

    def emergency_close_all(self):
        """
        If daily loss > $1,000:
        - Close all positions
        - Stop trading for day
        - Send alert
        """
```

---

## Daily Workflow

### Morning (9:30-10:00 AM ET)

```python
# Main execution loop

def morning_routine():
    # 1. Wait for market open
    wait_until_market_open()

    # 2. Wait 5 minutes for stability
    time.sleep(300)

    # 3. Collect market data
    market_data = collector.get_trade_setup()

    # 4. Run strategy engine
    decision = strategy.should_enter_trade(market_data)

    # 5. Execute if valid
    if decision['should_trade']:
        order = executor.place_spread_order(market_data)
        logger.log_trade(order)

        send_notification(
            f"✅ Trade entered: {decision['entry_credit']}"
        )
    else:
        logger.log_skip(decision['reason'])
```

### During Market Hours (10:00 AM - 3:45 PM)

```python
def monitor_loop():
    while market_is_open():
        # Check every 5 minutes
        positions = get_open_positions()

        for position in positions:
            current_price = get_current_spy_price()
            exit_signal = monitor.check_exit_conditions(
                position, current_price
            )

            if exit_signal['should_exit']:
                executor.close_position(position)
                logger.log_exit(position, exit_signal)

                send_notification(
                    f"⚠️ Position closed: {exit_signal['reason']}"
                )

        time.sleep(300)  # 5 minutes
```

### End of Day (4:00 PM ET)

```python
def end_of_day_routine():
    # 1. Check final positions
    positions = get_open_positions()

    # 2. Calculate P&L
    for position in positions:
        final_pnl = calculate_expiration_value(position)
        logger.update_final_pnl(position, final_pnl)

    # 3. Generate daily report
    report = logger.generate_daily_report()

    # 4. Send summary
    send_email_report(report)

    # 5. Export CSV
    logger.export_daily_csv()
```

---

## Configuration File (`config.yaml`)

```yaml
broker:
  name: "alpaca"  # or "ibkr"
  paper_trading: true
  api_key: "YOUR_API_KEY"
  api_secret: "YOUR_API_SECRET"

strategy:
  max_spreads: 2
  min_entry_credit: 400
  max_daily_loss: 1000
  exit_threshold: 10  # SPY dollars ITM

trading_hours:
  entry_start: "09:35"
  entry_end: "10:00"
  exit_check: "15:45"

notifications:
  email: "your@email.com"
  sms: "+1234567890"
  slack_webhook: "https://..."

logging:
  level: "INFO"
  file: "trading.log"
  database: "trades.db"
```

---

## File Structure

```
optionsarbitrage/
├── config/
│   ├── config.yaml
│   └── secrets.yaml (gitignored)
│
├── src/
│   ├── __init__.py
│   ├── market_data.py
│   ├── strategy_engine.py
│   ├── order_executor.py
│   ├── position_monitor.py
│   ├── results_logger.py
│   └── risk_manager.py
│
├── brokers/
│   ├── alpaca_client.py
│   └── ibkr_client.py
│
├── utils/
│   ├── notifications.py
│   ├── scheduler.py
│   └── helpers.py
│
├── data/
│   ├── trades.db
│   └── exports/
│
├── logs/
│   └── trading.log
│
├── tests/
│   ├── test_strategy.py
│   ├── test_execution.py
│   └── test_monitoring.py
│
├── scripts/
│   ├── main.py (daily execution)
│   ├── backfill.py (historical data)
│   └── dashboard.py (optional UI)
│
├── requirements.txt
├── README.md
└── .env (API keys)
```

---

## Deployment Strategy

### Option 1: Local Mac (Simplest)

**Setup:**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up cron job
crontab -e

# Add this line (runs at 9:30 AM ET daily):
30 9 * * 1-5 cd /Users/johnnyhuang/personal/optionsarbitrage && python3 scripts/main.py
```

**Pros:**
- ✅ Simple setup
- ✅ No cloud costs
- ✅ Full control

**Cons:**
- ⚠️ Mac must be on and connected
- ⚠️ No redundancy

---

### Option 2: AWS Lambda (Cloud)

**Setup:**
```bash
# 1. Package code
zip -r function.zip src/ brokers/ utils/

# 2. Deploy to Lambda
aws lambda create-function \
    --function-name spy-spx-trader \
    --runtime python3.9 \
    --handler main.lambda_handler \
    --zip-file fileb://function.zip

# 3. Set up CloudWatch Events (cron)
# Runs at 9:30 AM ET Mon-Fri
```

**Pros:**
- ✅ Always available
- ✅ Redundant
- ✅ No local requirements

**Cons:**
- ⚠️ Slightly more complex setup
- ⚠️ Small cloud costs (~$5/month)

---

## Testing Strategy

### 1. Unit Tests
```python
# test_strategy.py
def test_entry_credit_calculation():
    assert calculate_entry_credit(2.98, 23.40) == 637.85

def test_exit_conditions():
    assert should_exit(spy_price=615, strike=600) == True
```

### 2. Paper Trading Validation
```python
# Run system in paper mode for 2-4 weeks
# Collect real data, zero risk
```

### 3. Backtesting (Optional)
```python
# If we get historical data, backtest on past
# But paper trading is more important
```

---

## Monitoring & Alerts

### Email Notifications
```python
import smtplib

def send_email(subject, body):
    """Send email for important events"""
    # Trade entered
    # Trade exited
    # Daily summary
    # Errors
```

### SMS Alerts (Optional)
```python
from twilio.rest import Client

def send_sms(message):
    """Send SMS for urgent alerts"""
    # Assignment risk
    # Max loss hit
    # System errors
```

### Dashboard (Optional - Streamlit)
```python
import streamlit as st

# Real-time dashboard showing:
# - Current positions
# - Today's P&L
# - Cumulative results
# - Charts and graphs
```

---

## Timeline to Build

### Week 1: Core System
- ✅ Market data collection
- ✅ Strategy engine
- ✅ Order execution (basic)
- ✅ Results logging

### Week 2: Monitoring & Safety
- ✅ Position monitoring
- ✅ Exit management
- ✅ Risk management
- ✅ Notifications

### Week 3: Polish & Deploy
- ✅ Error handling
- ✅ Logging
- ✅ Testing
- ✅ Deployment

### Week 4: Live Paper Trading
- ✅ Run daily automatically
- ✅ Collect real results
- ✅ Validate strategy

**Total: 4 weeks from start to validated system**

---

## What I Need from You

1. **Choose broker:** Alpaca (easy) or IBKR (production)
2. **Sign up for account:** I'll guide you
3. **Provide API keys:** Secure .env file
4. **Confirm deployment:** Local Mac vs Cloud

Then I'll build the entire system!

**Ready to proceed?**
