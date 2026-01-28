# SPY/SPX Options Arbitrage Strategy

A market-neutral options arbitrage strategy exploiting pricing inefficiencies between SPY (ETF) and SPX (Index) options.

## Strategy Overview

**The Edge**: SPX options are typically more expensive than SPY options when adjusted for the 10:1 ratio. By selling the expensive side and buying the cheap side on both calls and puts, we collect a net credit while maintaining a market-neutral, hedged position.

**Key Characteristics**:
- Market-neutral (direction doesn't matter)
- Fully hedged (SPY and SPX track 98.9% correlation)
- Profit from entry credit, not directional moves
- 0DTE (Zero Days to Expiration) options
- Low risk due to tight SPY/SPX tracking

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.template .env
# Edit .env with your IB Gateway settings

# 3. Analyze current opportunity
python run_strategy.py --mode analyze

# 4. Collect market data
python collect_market_data.py --mode snapshot
```

## Core Scripts

### `run_strategy.py` - Strategy Execution
Analyze and execute the arbitrage strategy.

**Modes**:
- `analyze`: Check current opportunity without trading
- `paper`: Paper trading mode (coming soon)
- `live`: Live trading mode (coming soon)

```bash
python run_strategy.py --mode analyze
```

### `collect_market_data.py` - Data Collection
Collect market data for backtesting and analysis.

**Modes**:
- `snapshot`: Quick snapshot of current prices
- `full`: Full option chain (±3% strikes)
- `live`: Continuous collection at intervals

```bash
# Quick snapshot
python collect_market_data.py --mode snapshot

# Full chain
python collect_market_data.py --mode full

# Live collection every 5 minutes
python collect_market_data.py --mode live --interval 300
```

## Project Structure

```
optionsarbitrage/
├── collect_market_data.py   # Data collection script
├── run_strategy.py           # Main strategy execution
├── src/
│   ├── broker/
│   │   └── ibkr_client.py   # Interactive Brokers API client
│   └── strategy/
│       └── spy_spx_strategy.py  # Core strategy logic
├── data/
│   ├── market_data.db       # SQLite database
│   └── *.csv                # Exported data files
├── archive/                 # Old scripts and analysis
└── README.md
```

## Strategy Details

### Entry Criteria
1. Collect current SPY/SPX option prices (ATM, 0DTE)
2. Calculate potential credit for both calls and puts
3. Enter if net credit > $0 after commissions

### Position Structure
**Standard position**:
- 10 SPY contracts (one side)
- 1 SPX contract (other side)
- Both calls and puts
- Total: 22 contracts

**Example**:
- SELL 1 SPX call @ $30 = Collect $3,000
- BUY 10 SPY calls @ $2.50 = Pay $2,500
- **Calls Credit: $500**

- SELL 10 SPY puts @ $2.50 = Collect $2,500
- BUY 1 SPX put @ $30 = Pay $3,000
- **Puts Debit: -$500**

**Net**: $500 - $500 = $0 (but with real pricing inefficiency, net > $0)

### Real Data Analysis

**SPY/SPX Correlation**: 98.9%
- Average tracking error: 0.0044%
- Maximum tracking error: 0.0208%

**Historical Performance** (Jan 26, 2026):

| Entry Time | Net Credit |
|------------|-----------|
| 9:30 AM    | $180.70   |
| 10:00 AM   | $315.70   |
| 11:00 AM   | $345.70   |
| 12:00 PM   | $305.70   |
| 1:30 PM    | $355.70   |

**Average**: $307.92 profit per trade

## Requirements

- Python 3.8+
- Interactive Brokers account
- IB Gateway or TWS running
- Market data subscription (or use delayed data)

## Risk Management

### Key Risks
1. **Tracking Risk**: SPY/SPX divergence (low probability)
2. **Execution Risk**: Slippage between bid/ask
3. **Liquidity Risk**: Options may not trade at displayed prices
4. **Assignment Risk**: Early assignment (SPX is European style, safer)

### Mitigation
- Use limit orders
- Monitor SPY/SPX correlation
- Start with small positions
- Only trade liquid ATM options
- Use paper trading first

## Archive

Old analysis and test scripts are in `archive/`:
- `analysis_scripts/`: Scenario analysis, P&L calculations
- `test_scripts/`: Unit and integration tests
- Historical backtest data and CSVs

## License & Disclaimer

**This is for educational purposes only. Options trading involves substantial risk of loss. Past performance does not guarantee future results. Always do your own research and consider consulting a financial advisor before trading.**

---

Built for SPY/SPX options arbitrage | Last updated: January 26, 2026
