---
name: qa
description: Walk through the UI like a real user and document every bug found
---

Act as a QA tester. Trace through every user interaction path in the Dash app, find bugs, and produce a prioritized bug report. This is NOT automated testing — it's systematic code-path review simulating what a human user would experience.

Target area (optional): $ARGUMENTS

## How This Works

Since Claude can't run a browser, this skill works by **tracing callback chains through the code**. For every user action (click, select, slide), follow the data through:

1. Which callback fires?
2. What are the inputs at that moment? (What could be None, empty, missing?)
3. What exceptions can occur? Are they all caught gracefully?
4. What does the user see if something fails? (Error message? Blank screen? Dash error overlay?)
5. Does the callback fire when it shouldn't? (Missing `prevent_initial_call`, tab not active)

## Step 1: Map All User Actions

Read `app.py` and every file in `src/pages/`. For each page, list every user action:

### App-level
- [ ] App loads for the first time (cold start)
- [ ] User switches between tabs (main-tabs value changes)
- [ ] Scanner result applied → sidebar updates → tab switches

### Sidebar (`src/pages/sidebar.py`)
- [ ] Page load with no data files in `data/`
- [ ] Page load with data files present
- [ ] Select a different date
- [ ] Select a different symbol pair
- [ ] Move entry time slider
- [ ] Change SYM1 strike (type a number, use +/- buttons)
- [ ] Change SYM2 strike
- [ ] Change call direction
- [ ] Change put direction
- [ ] Select a pair that has no options data

### Historical Analysis (`src/pages/historical.py`)
- [ ] Tab loads with no config set yet
- [ ] Tab loads with valid config
- [ ] Change strategy type (Full → Calls Only → Puts Only)
- [ ] Select strikes with no options data for that strike
- [ ] Select a time where options are stale (volume=0)
- [ ] All 4 option prices are zero → what happens to credit/margin/P&L?

### Live Paper Trading (`src/pages/live_trading.py`)
- [ ] Tab loads — IB Gateway NOT running
- [ ] Tab loads — `ib_insync`/`ib_async` NOT installed
- [ ] Tab loads — IB Gateway IS running (happy path)
- [ ] Click Refresh button
- [ ] Toggle auto-refresh on/off
- [ ] No open positions → display empty state
- [ ] Open positions with missing market data
- [ ] Stock positions present (assignment scenario)

### Price Overlay (`src/pages/price_overlay.py`)
- [ ] Tab loads with valid config
- [ ] Switch between Puts/Calls
- [ ] Strike has no option data → error handling
- [ ] Only TRADES data (no BID_ASK) → fallback
- [ ] Only BID_ASK data (no TRADES) → fallback
- [ ] No overlapping time periods between symbols

### Underlying Divergence (`src/pages/divergence.py`)
- [ ] Tab loads with valid config
- [ ] Date with very short trading session (< 5 bars)
- [ ] Date where symbols have different number of bars

### Strike Scanner (`src/pages/scanner.py`)
- [ ] Click Scan with no config
- [ ] Click Scan with valid config (happy path)
- [ ] Scan returns zero results
- [ ] Switch ranking tabs (Safety → Profit → Risk/Reward)
- [ ] Click a row to apply to sidebar
- [ ] Scan with min volume = 0
- [ ] Scan with "Hide illiquid" unchecked

## Step 2: Trace Each Path

For each action, read the callback code and trace:

### Common Failure Patterns to Check

**1. Unguarded initial callback fire**
```python
# BAD — fires on page load with n_clicks=0
@callback(Output(...), Input('button', 'n_clicks'))
def handler(n_clicks):
    do_expensive_thing()  # runs immediately!

# GOOD — skips initial fire
@callback(Output(...), Input('button', 'n_clicks'), prevent_initial_call=True)
```
Check every callback: does it need `prevent_initial_call=True`?

**2. None/empty config**
```python
# BAD — config is {} on first load
config.get('sym1')  # returns None
sym1_df, sym2_df = get_symbol_dataframes(df, None, None)  # crashes

# GOOD — guard early
if not config or not config.get('date'):
    return "Select a date..."
```
Check every callback that reads `config-store`: does it guard against empty config?

**3. Missing data graceful handling**
```python
# BAD — crashes if no options data
df_options = load_options_data(date)
df_options[df_options['strike'] == strike]  # AttributeError if None

# GOOD — check before use
if df_options is None:
    return "No options data available."
```

**4. Dynamic component IDs**
```python
# BAD — callback references ID that doesn't exist yet
@callback(Input('dynamic-table', 'active_cell'))  # created by another callback

# GOOD — component exists in static layout
```
Check `suppress_callback_exceptions=True` in `app.py` — this hides these errors at runtime.

**5. Callback fires when tab not active**
Dash registers ALL callbacks globally. A callback for Tab 3 fires even when the user is on Tab 1 if its Input changes. Check for callbacks that do heavy work (IB connection, scanning) — they should guard against being triggered on inactive tabs.

**6. Exception handling gaps**
```python
# BAD — catches specific exception, misses others
except ImportError:
    ...
# What if ib_insync IS installed but connect() raises ConnectionRefusedError?
# What if asyncio event loop conflicts with Dash's threading model?

# GOOD — catch broad, show user-friendly message
except Exception as e:
    return html.Div(f"Error: {e}"), timestamp
```
Check every try/except: does the broad `except Exception` always return the right number of outputs?

**7. Callback output count mismatch**
```python
# Callback declares 2 Outputs but exception path returns 1
@callback(Output('a', 'children'), Output('b', 'children'), ...)
def handler():
    try:
        return result_a, result_b  # 2 outputs ✓
    except Exception:
        return error_div  # 1 output ✗ — Dash crashes
```
Count the Outputs in every callback. Verify EVERY return path (including exceptions) returns the same count.

## Step 3: Document Findings

For each bug found, record:

```
### BUG-001: [Short title]
**Severity:** Critical / High / Medium / Low
**Page:** [which page/callback]
**Trigger:** [exact user action that causes it]
**What happens:** [what the user sees]
**Root cause:** [code location + why]
**Fix:** [proposed fix, 1-2 sentences]
```

Severity guide:
- **Critical**: App crashes, data loss, blank screen, Dash error overlay
- **High**: Feature doesn't work, wrong numbers displayed, misleading info
- **Medium**: Poor error message, cosmetic issue, works but confusing
- **Low**: Minor polish, edge case nobody will hit

## Step 4: Produce the Bug Report

After tracing all paths, output a single report with:

1. **Summary**: X bugs found (Y critical, Z high, ...)
2. **Bugs listed by severity** (critical first)
3. **Quick wins**: bugs that are 1-3 line fixes
4. **Recommendations**: patterns to adopt to prevent future bugs

## Known Bug Categories (from past issues)

These bugs have been found before. Check if they're fixed:

1. **Scanner dynamic table IDs** — `scanner-table-profit` and `scanner-table-risk_reward` referenced as callback Inputs but created dynamically. Causes Dash error overlay.

2. **Live trading initial fire** — callback fires on page load, tries to connect to IB Gateway immediately. No `prevent_initial_call=True`. Connection attempt may hang or crash in Dash's thread context.

3. **Sidebar slider labels** — Entry Time slider renders ~78 marks in 320px, all overlapping. User can't read times.

4. **Live trading `COLOR_*` variables** — verify `COLOR_NEGATIVE`, `COLOR_WARNING_TEXT`, `COLOR_NEUTRAL` are defined. If these are from `components.py` but not imported, callback crashes on the error-handling path itself.

## Important Rules

- **Don't fix bugs during the QA pass** — just document. Fix after the full report is done.
- **Check EVERY return path in EVERY callback** — especially exception handlers
- **Count outputs** — every return must match the number of `Output()` declarations
- **Read the actual code** — don't guess what it does, read it line by line
- **If `$ARGUMENTS` specifies a page**, only QA that page (e.g., "scanner", "live_trading", "sidebar")
- After the report is done, the user can run fixes manually or invoke `/test-suite` to write automated tests for the bugs found
