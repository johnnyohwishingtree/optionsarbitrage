# Architecture Diagram Conventions

> Single source of truth for all `.mmd` diagram files in this directory.

## Node ID Prefixes

Every node in a diagram maps to a specific code location.

| Prefix | Meaning         | Example                                | Code Location                                                      |
|--------|-----------------|----------------------------------------|--------------------------------------------------------------------|
| `MOD_` | Python module   | `MOD_collect`                          | `collect_market_data.py`                                           |
| `MOD_` | Python module   | `MOD_strategy`                         | `strategy_calculator_simple.py`                                    |
| `MOD_` | Python module   | `MOD_ibkrClient`                       | `src/broker/ibkr_client.py`                                        |
| `MOD_` | Python module   | `MOD_pnl`                              | `src/pnl.py`                                                       |
| `MOD_` | Python module   | `MOD_pricing`                          | `src/pricing.py`                                                   |
| `CLS_` | Class           | `CLS_IBKRClient`                       | `src/broker/ibkr_client.py::IBKRClient`                            |
| `FN_`  | Function        | `FN_collectDailyData`                  | `collect_market_data.py::collect_daily_data()`                     |
| `FN_`  | Function        | `FN_getLastTimestamp`                  | `collect_market_data.py::get_last_timestamp()`                     |
| `FN_`  | Function        | `FN_calcOptionPnl`                     | `src/pnl.py::calculate_option_pnl()`                              |
| `FN_`  | Function        | `FN_calcSettlement`                    | `src/pnl.py::calculate_settlement_value()`                        |
| `FN_`  | Function        | `FN_calcBestWorst`                     | `src/pnl.py::calculate_best_worst_case_with_basis_drift()`        |
| `FN_`  | Function        | `FN_getPriceWithLiquidity`             | `src/pricing.py::get_option_price_with_liquidity()`               |
| `FN_`  | Function        | `FN_getPriceFromDb`                    | `src/pricing.py::get_option_price_from_db()`                      |
| `FN_`  | Function        | `FN_findNearestRow`                    | `src/pricing.py::_find_nearest_row()`                             |
| `TAB_` | Streamlit tab   | `TAB_historical`                       | Tab 1 in `strategy_calculator_simple.py`                           |
| `TAB_` | Streamlit tab   | `TAB_liveTrade`                        | Tab 2 in `strategy_calculator_simple.py`                           |
| `TAB_` | Streamlit tab   | `TAB_priceOverlay`                     | Tab 3 in `strategy_calculator_simple.py`                           |
| `TAB_` | Streamlit tab   | `TAB_divergence`                       | Tab 4 in `strategy_calculator_simple.py`                           |
| `TAB_` | Streamlit tab   | `TAB_scanner`                          | Tab 5 in `strategy_calculator_simple.py`                           |
| `DATA_`| Data file       | `DATA_underlying`                      | `data/underlying_prices_{date}.csv`                                |
| `DATA_`| Data file       | `DATA_optTrades`                       | `data/options_data_{date}.csv`                                     |
| `DATA_`| Data file       | `DATA_optBidask`                       | `data/options_bidask_{date}.csv`                                   |
| `EXT_` | External system | `EXT_ibGateway`                        | IB Gateway at `127.0.0.1:4002`                                     |
| `EXT_` | External system | `EXT_browser`                          | User's web browser (Streamlit UI)                                  |

## Style Classes

```mermaid
classDef external  fill:#f9d0d0,stroke:#c0392b,color:#333
classDef module    fill:#d0e0f9,stroke:#2471a3,color:#333
classDef function  fill:#d0f9d0,stroke:#27ae60,color:#333
classDef data      fill:#f9e4d0,stroke:#e67e22,color:#333
classDef tab       fill:#e0d0f9,stroke:#8e44ad,color:#333
```

| Class      | Color  | Usage                          |
|------------|--------|--------------------------------|
| `external` | Pink   | IB Gateway, browser, APIs      |
| `module`   | Blue   | Python modules                 |
| `function` | Green  | Key functions                  |
| `data`     | Orange | CSV files, data stores         |
| `tab`      | Purple | Streamlit UI tabs              |

## Edge Semantics

| Style           | Meaning              | Mermaid Syntax |
|-----------------|----------------------|----------------|
| Solid arrow     | Runtime call / flow  | `-->`          |
| Dashed arrow    | Test dependency      | `-.->` |
| Thick arrow     | Data flow (I/O)      | `==>`          |
| Dotted arrow    | Optional / fallback  | `-.->`         |

## Diagram Index

| File                            | Description                                     |
|---------------------------------|-------------------------------------------------|
| `system-overview.mmd`           | Top-level architecture: modules, data, external |
| `module-dependencies.mmd`       | Import/dependency graph between files           |
| `data-model.mmd`                | ER diagram of CSV schemas                       |
| `flow-data-collection.mmd`      | Data collection pipeline                        |
| `flow-strategy-analysis.mmd`    | Historical analysis & P&L workflow              |
| `flow-live-trading.mmd`         | Live paper trading flow                         |
| `flow-strike-scanner.mmd`       | Strike pair scanning & ranking                  |
| `flow-price-discovery.mmd`      | Liquidity-aware price lookup                    |
| `strategy-overview.mmd`         | How the arbitrage strategy works                |
| `flow-position-construction.mmd`| 4-leg position: direction, qty ratios, margin   |
| `flow-pnl-settlement.mmd`      | P&L formulas and settlement calculation         |
| `flow-best-worst-case.mmd`     | Best/worst case grid search with basis drift    |
