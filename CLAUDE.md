# CLAUDE.md — Options Arbitrage Trading System

## Quick Orientation

Read `docs/architecture/system-overview.mmd` first, then the specific flow diagram for whatever area you're working in. This gives you instant context without reading thousands of lines of Python.

## Architecture Diagrams

All diagrams live in `docs/architecture/`. See `docs/architecture/README.md` for conventions (node ID prefixes, style classes, edge semantics).

| Diagram | What it shows |
|---------|---------------|
| `system-overview.mmd` | Modules, data stores, IB Gateway, Streamlit tabs |
| `module-dependencies.mmd` | Import graph between files and libraries |
| `data-model.mmd` | CSV schemas (underlying, options trades, bid/ask) |
| `flow-data-collection.mmd` | CLI -> IB -> CSV pipeline |
| `flow-strategy-analysis.mmd` | Tab 1: load data -> price lookup -> P&L -> best/worst case |
| `flow-live-trading.mmd` | Tab 2: IB connect -> positions -> settlement P&L |
| `flow-strike-scanner.mmd` | Tab 5: match pairs -> filter -> rank -> apply |
| `flow-price-discovery.mmd` | Liquidity-aware price lookup logic |

## Project Structure

```
collect_market_data.py          # Data collection CLI (IB Gateway -> CSVs)
strategy_calculator_simple.py   # Streamlit dashboard (5 tabs)
src/broker/ibkr_client.py       # IB API wrapper (IBKRClient class)
tests/                          # P&L, worst-case consistency, lockstep tests
data/                           # CSV files per trading date
docs/architecture/              # Mermaid diagrams (this system)
```

## Key Domain Concepts

- **Symbol pairs**: SPY/SPX (10:1 ratio), SPY/XSP (1:1), XSP/SPX
- **0DTE settlement**: Options expire same day, no overnight risk
- **Basis drift**: SPX/SPY ratio can drift ±0.10% intraday, affects P&L
- **Liquidity filtering**: Volume=0 bars are stale (IB carries forward last price); always prefer volume>0
- **Moneyness matching**: Strike pairs must be within 0.5% moneyness to hedge properly

## Planning Convention

When referencing code in plans, use architecture node IDs from the diagrams:
- `MOD_collect` = `collect_market_data.py`
- `FN_calcBestWorst` = `calculate_best_worst_case_with_basis_drift()`
- `TAB_scanner` = Tab 5 in `strategy_calculator_simple.py`
- See full prefix table in `docs/architecture/README.md`

## Run Commands

```bash
# Collect market data for a date
python collect_market_data.py --date 20260207 --data-type both --symbols SPY SPX XSP

# Run the Streamlit dashboard
streamlit run strategy_calculator_simple.py

# Run tests
python -m pytest tests/ -v

# View architecture diagrams in browser
python3 -m http.server 8080 --directory docs/architecture
# Then open http://localhost:8080/viewer.html
```

## After Implementing Changes

Run `/update-architecture` to keep diagrams in sync with the code.
