---
name: plan-feature
description: Plan a feature using architecture diagram vocabulary
argument-hint: "[feature description]"
---

Plan a new feature using architecture diagram vocabulary.

Feature to plan: $ARGUMENTS

## Context

This is a market-neutral 0DTE options arbitrage system trading SPY/SPX/XSP pairs. Key business rules:
- 4-leg hedged positions (sell calls on one symbol, buy on another, same for puts)
- SPY:SPX ratio is 10:1, SPY:XSP is 1:1
- P&L = net credit at entry - settlement cost at expiration
- Risk measured via grid search: 50 price points × 3 basis drift levels (±0.10%)
- Price lookup prefers BID_ASK midpoint over TRADES; rejects stale data (volume=0)
- Moneyness matching within 0.05%; scanner tolerance 0.5%

## Steps

1. Read the current architecture diagrams:
   - `docs/architecture/strategy-overview.mmd` for how the strategy works
   - `docs/architecture/system-overview.mmd` for code structure
   - `docs/architecture/module-dependencies.mmd` for import relationships
   - Any flow diagrams relevant to the feature area
   - `docs/architecture/README.md` for node ID conventions
2. Analyze where the feature fits in the existing architecture.
3. Consider whether the feature affects business logic (P&L, position construction, risk assessment) vs just code structure.
4. Produce a structured plan with these sections:

## Affected Diagrams
List which `.mmd` files will need updates after implementation. Include both code structure and business logic diagrams.

## New Nodes
For each new piece of code, specify:
- Node ID (e.g., `FN_alertEngine`, `CLS_PriceMonitor`)
- Code location (file and function/class name)
- Style class (module/function/data/tab/external)

## Modified Nodes
Existing nodes that change behavior or signature.

## New Edges
New relationships between nodes:
- Source -> Target
- Edge type (solid/dashed/thick)
- Label describing the relationship

## Business Logic Impact
- Does this change any business constants? (thresholds, ratios, grid params)
- Does this affect P&L calculation, position construction, or risk assessment?
- Does the CLAUDE.md Business Constants table need updating?

## Implementation Steps
Ordered list of code changes, referencing node IDs:
1. Create/modify file X to add `FN_newFunction`
2. Update `MOD_strategy` to import and call `FN_newFunction`
3. etc.

## Test Plan
What tests to add or modify, referencing existing test files. Include:
- `tests/test_architecture_sync.py` updates if new nodes/functions added
- Business logic tests if strategy behavior changes
