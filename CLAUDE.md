# CLAUDE.md — Options Arbitrage Trading System

## Quick Orientation

Read `docs/architecture/strategy-overview.mmd` first for how the strategy works, then `system-overview.mmd` for the code architecture. Read specific flow diagrams for whatever area you're working in. This gives you instant context without reading thousands of lines of Python.

## The Strategy

This is a **market-neutral 0DTE options arbitrage** between correlated index/ETF pairs (SPY/SPX, SPY/XSP, XSP/SPX). The core idea:

1. **SPY and SPX are ~98.9% correlated** intraday, but their option prices diverge due to liquidity, contract specs, and market microstructure.
2. **Build a 4-leg hedged position**: sell options on one symbol, buy the equivalent on the other, for both calls and puts. This cancels directional risk.
3. **Collect a net credit at entry**. If both symbols move in lockstep, the sold and bought legs cancel at settlement and you keep the credit.
4. **The risk is basis drift**: the SPX/SPY ratio can shift ±0.10% intraday, breaking the perfect hedge. The grid search (50 prices × 3 drift levels = 150 scenarios) quantifies worst-case P&L.
5. **0DTE means same-day expiration**: no overnight risk, positions always settle by market close.

## Business Constants

These values are hardcoded in the codebase and drive the strategy logic:

| Constant | Value | Location |
|----------|-------|----------|
| SPY:SPX quantity ratio | 10:1 | `strategy_calculator_simple.py:150` |
| SPY:XSP / XSP:SPX ratio | 1:1 | `strategy_calculator_simple.py:150` |
| SPX strike step | $5 | `strategy_calculator_simple.py:151` |
| SPY/XSP strike step | $1 | `strategy_calculator_simple.py:151` |
| Moneyness match warning | >0.05% diff | `strategy_calculator_simple.py:386` |
| Scanner pair tolerance | <0.5% | `strategy_calculator_simple.py:2757` |
| Wide spread threshold | >20% | `src/pricing.py:161` |
| Margin estimate | 20% of short notional - credit | `strategy_calculator_simple.py:794` |
| Grid search price range | ±5% (50 points) | `src/pnl.py:58-61` |
| Grid search basis drift | ±0.10% (3 levels) | `src/pnl.py:64` |
| Default min volume (scanner) | 10 | `strategy_calculator_simple.py:2741` |

## Architecture Diagrams

All diagrams live in `docs/architecture/`. See `docs/architecture/README.md` for conventions (node ID prefixes, style classes, edge semantics).

**Strategy & Business Logic:**

| Diagram | What it shows |
|---------|---------------|
| `strategy-overview.mmd` | How the arbitrage works: premise, position, economics, risk |
| `flow-position-construction.mmd` | 4-leg position: direction logic, qty ratios, margin |
| `flow-pnl-settlement.mmd` | P&L formulas: intrinsic value, per-leg P&L, net position |
| `flow-best-worst-case.mmd` | Grid search algorithm: 150 scenarios, basis drift |

**System Architecture:**

| Diagram | What it shows |
|---------|---------------|
| `system-overview.mmd` | Modules, data stores, IB Gateway, Streamlit tabs |
| `module-dependencies.mmd` | Import graph between files and libraries (auto-generated) |
| `data-model.mmd` | CSV schemas (underlying, options trades, bid/ask) |

**Feature Flows:**

| Diagram | What it shows |
|---------|---------------|
| `flow-data-collection.mmd` | CLI -> IB -> CSV pipeline |
| `flow-strategy-analysis.mmd` | Tab 1: load data -> price lookup -> P&L -> best/worst case |
| `flow-live-trading.mmd` | Tab 2: IB connect -> positions -> settlement P&L |
| `flow-strike-scanner.mmd` | Tab 5: match pairs -> filter -> 3 ranking views -> apply |
| `flow-price-discovery.mmd` | Liquidity-aware price lookup: midpoint vs TRADES, stale detection |

## Project Structure

```
collect_market_data.py          # Data collection CLI (IB Gateway -> CSVs)
strategy_calculator_simple.py   # Streamlit dashboard (5 tabs)
src/pnl.py                      # P&L calculations (pure functions)
src/pricing.py                  # Price discovery with liquidity (pure functions)
src/broker/ibkr_client.py       # IB API wrapper (IBKRClient class)
tests/                          # P&L, worst-case consistency, lockstep, architecture sync
data/                           # CSV files per trading date
docs/architecture/              # Mermaid diagrams + viewer
scripts/gen_arch_deps.py        # Auto-generates module-dependencies.mmd
```

## Key Domain Concepts

- **Symbol pairs**: SPY/SPX (10:1 ratio), SPY/XSP (1:1), XSP/SPX
- **0DTE settlement**: Options expire same day, no overnight risk
- **Basis drift**: SPX/SPY ratio can drift ±0.10% intraday, affects P&L
- **Liquidity filtering**: Volume=0 bars are stale (IB carries forward last price); always prefer volume>0
- **Moneyness matching**: Strike pairs must be within 0.05% to hedge well; scanner uses 0.5% tolerance
- **Price source priority**: BID_ASK midpoint preferred over TRADES open price
- **Wide spread**: bid-ask spread >20% of midpoint triggers a liquidity warning
- **Stale detection**: volume=0 AND no valid bid/ask quotes = truly stale (blocks analysis)

## Planning Convention

When referencing code in plans, use architecture node IDs from the diagrams:
- `MOD_collect` = `collect_market_data.py`
- `MOD_pnl` = `src/pnl.py`
- `MOD_pricing` = `src/pricing.py`
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

# Run architecture sync tests only
python -m pytest tests/test_architecture_sync.py -v

# View architecture diagrams in browser
python3 -m http.server 8080 --directory docs/architecture
# Then open http://localhost:8080/viewer.html
```

## After Implementing Changes

Run `/update-architecture` to keep diagrams in sync with the code. The `module-dependencies.mmd` auto-updates on commit via the pre-commit hook, but flow diagrams and business logic diagrams need manual update.
