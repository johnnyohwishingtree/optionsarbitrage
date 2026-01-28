#!/usr/bin/env python3
"""
Execute 0DTE SPY/SPX Hold-to-Expiration Strategy

This script:
1. Reads today's prices and strike brackets
2. Tests all 4 strike combinations (SPY floor/ceiling × SPX floor/ceiling)
3. For each combination, tests BOTH sides (calls and puts)
4. For each side, tests BOTH directions (Sell SPY/Buy SPX and Sell SPX/Buy SPY)
5. Selects best combination with credit on BOTH sides
6. Places orders

Based on our "opening-based" strategy from backtest.
