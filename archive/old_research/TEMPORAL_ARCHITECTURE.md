# Temporal Workflow Architecture
## Serverless Automation for SPY/SPX Trading

## Why Temporal is Perfect for This

You're right to prefer Temporal over cron! Here's why:

### ✅ Temporal Advantages:
- **No server to manage** - Deploy once, runs forever
- **Built-in scheduling** - Like cron but better (retries, monitoring)
- **Durable execution** - If something fails, it automatically retries
- **Activity isolation** - Each API call is a separate activity
- **Easy monitoring** - Web UI to see all workflow executions
- **No infrastructure** - Use Temporal Cloud (managed service)

### ❌ vs Cron:
- Cron requires a running machine
- No built-in retries
- No monitoring/visibility
- Have to manage failures manually

---

## System Architecture with Temporal

```
┌──────────────────────────────────────────────────────────────┐
│                   TEMPORAL CLOUD                              │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           SCHEDULED WORKFLOW (Daily 9:35 AM)          │  │
│  │                                                        │  │
│  │  1. Fetch Market Data Activity                        │  │
│  │     └─> Get SPY/SPX prices from Alpaca               │  │
│  │                                                        │  │
│  │  2. Calculate Strategy Activity                       │  │
│  │     └─> Determine if we should trade                 │  │
│  │                                                        │  │
│  │  3. Execute Trade Activity                            │  │
│  │     └─> Place orders via Alpaca API                  │  │
│  │                                                        │  │
│  │  4. Monitor Position Workflow (runs until 4pm)       │  │
│  │     └─> Check every 5 min for exit signals           │  │
│  │                                                        │  │
│  │  5. Log Results Activity                              │  │
│  │     └─> Save to database, export CSV                 │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              WORKER (Your Code)                        │  │
│  │  Runs activities when triggered by workflows          │  │
│  │  Can run anywhere: AWS Lambda, Cloud Run, local       │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
optionsarbitrage/
├── temporal/
│   ├── workflows/
│   │   ├── daily_trading_workflow.py     ← Main trading workflow
│   │   └── position_monitor_workflow.py  ← Monitoring workflow
│   │
│   ├── activities/
│   │   ├── market_data.py          ← Fetch SPY/SPX data
│   │   ├── strategy.py             ← Calculate trade decisions
│   │   ├── trading.py              ← Execute trades via Alpaca
│   │   └── logging.py              ← Log results
│   │
│   └── worker.py                   ← Temporal worker (runs activities)
│
├── src/
│   ├── brokers/
│   │   └── alpaca_client.py        ← Alpaca API wrapper
│   │
│   ├── strategy_engine.py          ← Trading logic
│   └── results_logger.py           ← Database/CSV logging
│
├── config/
│   └── temporal_config.py          ← Temporal connection settings
│
└── main.py                         ← Deploy worker + register schedules
```

---

## Temporal Workflow Code (High-Level)

### 1. Daily Trading Workflow

```python
# temporal/workflows/daily_trading_workflow.py

from temporalio import workflow
from datetime import timedelta

@workflow.defn
class DailyTradingWorkflow:
    """Main workflow - runs every trading day at 9:35 AM"""

    @workflow.run
    async def run(self) -> dict:
        # Step 1: Fetch market data
        market_data = await workflow.execute_activity(
            fetch_market_data,
            start_to_close_timeout=timedelta(seconds=30)
        )

        # Step 2: Calculate trade
        decision = await workflow.execute_activity(
            calculate_trade,
            market_data,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Step 3: Execute if valid
        if decision['should_trade']:
            order = await workflow.execute_activity(
                execute_trade,
                decision,
                start_to_close_timeout=timedelta(seconds=60)
            )

            # Step 4: Start monitoring workflow
            await workflow.execute_child_workflow(
                PositionMonitorWorkflow.run,
                order,
                id=f"monitor-{order['id']}"
            )

            # Step 5: Log results
            await workflow.execute_activity(
                log_trade,
                order,
                start_to_close_timeout=timedelta(seconds=30)
            )

        return {"status": "complete", "decision": decision}
```

### 2. Position Monitor Workflow

```python
# temporal/workflows/position_monitor_workflow.py

from temporalio import workflow
from datetime import timedelta

@workflow.defn
class PositionMonitorWorkflow:
    """Monitors position during the day, closes if needed"""

    @workflow.run
    async def run(self, order: dict) -> dict:
        while True:
            # Check if market closed (4pm)
            if await workflow.execute_activity(
                is_market_closed,
                start_to_close_timeout=timedelta(seconds=10)
            ):
                break

            # Check exit conditions
            should_exit = await workflow.execute_activity(
                check_exit_conditions,
                order,
                start_to_close_timeout=timedelta(seconds=30)
            )

            if should_exit:
                # Close position
                exit_order = await workflow.execute_activity(
                    close_position,
                    order,
                    start_to_close_timeout=timedelta(seconds=60)
                )
                return {"action": "closed_early", "order": exit_order}

            # Wait 5 minutes before checking again
            await asyncio.sleep(300)

        return {"action": "held_to_expiration"}
```

### 3. Activities (Actual API Calls)

```python
# temporal/activities/trading.py

from temporalio import activity
from src.brokers.alpaca_client import AlpacaClient

@activity.defn
async def execute_trade(decision: dict) -> dict:
    """Execute trade via Alpaca API"""

    client = AlpacaClient()

    # Buy SPX call
    spx_order = client.buy_option(
        symbol="SPX",
        strike=decision['spx_strike'],
        expiry=decision['expiry'],
        quantity=1
    )

    # Sell SPY calls
    spy_order = client.sell_option(
        symbol="SPY",
        strike=decision['spy_strike'],
        expiry=decision['expiry'],
        quantity=10
    )

    return {
        "id": f"trade-{datetime.now().isoformat()}",
        "spx_order": spx_order,
        "spy_order": spy_order,
        "entry_credit": decision['entry_credit']
    }
```

---

## Deployment Options

### Option 1: Temporal Cloud (Recommended - Zero Infrastructure)

```bash
# 1. Sign up for Temporal Cloud
# https://temporal.io/cloud

# 2. Deploy worker to AWS Lambda or Cloud Run
# Worker just needs to connect to Temporal Cloud

# 3. Register schedules
temporal schedule create \
  --schedule-id daily-trading \
  --workflow-type DailyTradingWorkflow \
  --cron "35 9 * * 1-5" \
  --timezone "America/New_York"
```

**Cost:** ~$10-25/month (Temporal Cloud starter)

### Option 2: Self-Hosted Temporal (Free but More Setup)

```bash
# Run Temporal locally via Docker
docker-compose up -d

# Worker runs on your Mac (or cloud)
python worker.py

# Temporal server manages scheduling/execution
```

**Cost:** FREE (but need to run Temporal server somewhere)

---

## Comparison: Temporal Cloud vs Self-Hosted

| Feature | Temporal Cloud | Self-Hosted |
|---------|---------------|-------------|
| **Setup time** | 15 minutes | 2-3 hours |
| **Cost** | $10-25/month | FREE |
| **Maintenance** | None (managed) | Manage Docker/server |
| **Reliability** | 99.9% uptime | Depends on your setup |
| **Scaling** | Automatic | Manual |
| **Monitoring** | Built-in UI | Setup yourself |

**My Recommendation:** Start with **Temporal Cloud** (easiest, $10/month worth it)

---

## Complete Setup Steps

### Phase 1: Temporal Cloud Setup (15 min)

1. **Sign up:** https://temporal.io/cloud
2. **Create namespace:** `spy-spx-trading`
3. **Get connection credentials:**
   - Namespace URL
   - mTLS certificates
   - API token

### Phase 2: Build Worker (2 hours)

```bash
# Install Temporal SDK
pip install temporalio

# Build activities (Alpaca API calls)
# Build workflows (trading logic)
# Build worker (connects to Temporal Cloud)
```

### Phase 3: Deploy Worker (30 min)

**Option A: AWS Lambda** (Serverless)
```bash
# Package worker as Lambda function
# Triggers on Temporal task queue
# Scales automatically
```

**Option B: Cloud Run** (Google Cloud)
```bash
# Deploy as container
# Always-on, minimal cost
```

**Option C: Local (for testing)**
```bash
# Just run worker.py
# Connects to Temporal Cloud
# Good for development
```

### Phase 4: Create Schedule (5 min)

```bash
# Register daily trading schedule
temporal schedule create \
  --schedule-id daily-spy-spx \
  --workflow-id daily-trading-$(date +%Y%m%d) \
  --type DailyTradingWorkflow \
  --cron "35 9 * * 1-5" \
  --timezone "America/New_York"

# Done! Runs every trading day at 9:35 AM ET
```

---

## Monitoring & Alerts

### Temporal Web UI (Built-in)

```
https://cloud.temporal.io/<your-namespace>

View:
- ✅ All workflow executions
- ✅ Activity results
- ✅ Failures/retries
- ✅ Execution history
- ✅ Schedule status
```

### Custom Notifications

```python
# Add to workflow:

if trade_executed:
    await workflow.execute_activity(
        send_notification,
        f"✅ Trade executed: ${entry_credit}",
        start_to_close_timeout=timedelta(seconds=10)
    )
```

---

## Error Handling (Why Temporal is Great)

```python
# Temporal automatically retries failed activities

@activity.defn(
    retry_policy=RetryPolicy(
        maximum_attempts=3,
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0
    )
)
async def fetch_market_data():
    # If this fails, Temporal retries:
    # - Attempt 1: immediate
    # - Attempt 2: after 1 second
    # - Attempt 3: after 2 seconds
    # - If all fail: workflow can handle error
    pass
```

---

## Cost Breakdown

### Temporal Cloud:
- **Worker execution:** FREE (pay only for compute)
- **Workflow executions:** $0.00025 per action (very cheap)
- **Storage:** $0.15/GB per month

**Expected monthly cost:** ~$10-15 for our use case

### Worker Hosting:
- **AWS Lambda:** ~$2/month (minimal usage)
- **Cloud Run:** ~$5/month (always-on)
- **Local:** FREE (but Mac must be on)

**Total: ~$12-20/month for fully automated, serverless system**

---

## Next Steps

Once you provide corrected Paper Trading API keys:

1. ✅ Test Alpaca connection
2. ✅ Build Temporal workflows
3. ✅ Build activities
4. ✅ Deploy worker (Cloud Run or local for testing)
5. ✅ Set up schedule
6. ✅ First automated trade Monday!

---

## Why This is Better Than Cron

| Feature | Cron | Temporal |
|---------|------|----------|
| **Requires running machine** | Yes | No |
| **Automatic retries** | No | Yes |
| **Monitoring UI** | No | Yes |
| **Durable execution** | No | Yes |
| **Activity isolation** | No | Yes |
| **Easy testing** | Hard | Easy |
| **Handles failures** | Manually | Automatically |

**Bottom line:** Temporal is like "cron on steroids" with built-in reliability, monitoring, and error handling.

---

**Ready to build this once you get the correct Paper Trading keys!** 🚀
