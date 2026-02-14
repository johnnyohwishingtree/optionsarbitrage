---
name: refactor-ui
description: Audit and fix UI/UX issues so the dashboard is usable by a human trader
---

Audit the Dash UI for usability issues, fix them, and ensure the interface is designed for a human trader who needs to make fast, accurate decisions.

Target area (optional): $ARGUMENTS

## Design Philosophy

This is a **trading tool**, not a marketing page. The user is a trader who:
- Glances at the screen to assess a position in seconds
- Needs numbers to be scannable (aligned, monospaced, consistent formatting)
- Needs controls that work on the first try (no overlapping labels, no mystery buttons)
- Needs visual hierarchy: the most important number (P&L, credit) should be the biggest/boldest
- Will use this on a single monitor, often alongside a broker window

**Principles (in priority order):**
1. **Nothing broken** — no overlapping text, truncated labels, or unresponsive controls
2. **Information hierarchy** — most important data is visually dominant
3. **Consistency** — same data type looks the same everywhere (P&L always green/red, monospaced)
4. **Density** — show more information per pixel without clutter (traders want density, not whitespace)
5. **Responsiveness** — sidebar + content should work from 1280px to 1920px wide

## Current Architecture

```
app.py                           # Dash entry point, tab routing
src/pages/
  sidebar.py                     # Shared config: date, pair, time slider, strikes, direction
  historical.py                  # Tab 1: position, credit, settlement P&L, scenario analysis
  live_trading.py                # Tab 2: IB connection, account, positions, P&L chart
  price_overlay.py               # Tab 3: normalized price chart, spread, safe entry
  divergence.py                  # Tab 4: underlying divergence chart
  scanner.py                     # Tab 5: strike scanner with ranking tables
```

All pages use inline `style={}` dicts. There is no shared CSS, no theme system, no component library.

## Audit Checklist

Run through every page and check each item. Fix as you go.

### 1. Sidebar (`src/pages/sidebar.py`)

**Entry Time Slider (critical — currently broken):**
- [ ] Labels overlap and are unreadable when there are 78+ time points in a 320px sidebar
- Fix: Use only 3-5 marks (open, mid-morning, noon, mid-afternoon, close) or use a numeric slider with a single tooltip showing the time label
- Alternative: Replace `dcc.Slider` with a `dcc.Dropdown` of time labels, or a numeric input + display

**Strike Inputs:**
- [ ] +/- buttons should respect the strike step (e.g., $5 for SPX, $1 for SPY)
- [ ] Verify the `step` prop on `dcc.Input` is set from `get_strike_step()`

**General Sidebar:**
- [ ] Width (320px) — is it enough? Is it too much? Check at 1280px and 1920px screen widths
- [ ] Scrolling — does the sidebar scroll independently when content overflows?
- [ ] Font sizes — are labels readable without squinting?
- [ ] Section spacing — enough visual separation between Date, Pair, Time, Strikes, Direction?

### 2. Historical Analysis (`src/pages/historical.py`)

**Position Table:**
- [ ] Columns aligned (numbers right-aligned, text left-aligned)
- [ ] Price source labels ("trade" / "mid") are readable, not cramped
- [ ] SELL rows are visually distinct from BUY rows
- [ ] Liquidity warnings don't break the table layout

**Credit & Margin:**
- [ ] Total Credit is the most visually prominent element (it's the key number)
- [ ] Margin and ROI are secondary, not competing for attention
- [ ] Negative credit (debit) is clearly red and unambiguous

**Settlement P&L:**
- [ ] Table footer total is visually separated and prominent
- [ ] Settlement prices are clearly labeled (not just numbers)

**Scenario Analysis:**
- [ ] Best/worst case blocks are visually distinct (green vs red background is good)
- [ ] P&L numbers are large enough to read at a glance
- [ ] Breakdown details (credit vs settlement cost) are discoverable but not noisy
- [ ] Risk/reward summary is below the scenario blocks, not lost

### 3. Live Paper Trading (`src/pages/live_trading.py`)

- [ ] Connection error state is clear and actionable (tell user what to do)
- [ ] Account summary metrics are scannable (card layout with clear labels)
- [ ] Position table columns are aligned
- [ ] Settlement P&L is visually separated from IB's reported P&L (they differ)
- [ ] P&L chart has a clear title and current price marker is visible
- [ ] Auto-refresh indicator shows when active

### 4. Price Overlay (`src/pages/price_overlay.py`)

- [ ] Chart legend doesn't overlap the data
- [ ] Star markers (max gap, safe entry) are visible against chart background
- [ ] Metric cards are evenly spaced and aligned
- [ ] "SAFE ENTRY" banner is visually prominent for positive worst-case
- [ ] Loading state shows during calculation

### 5. Underlying Divergence (`src/pages/divergence.py`)

- [ ] X-axis time labels don't overlap (currently uses every 20th label — check)
- [ ] Metric cards match the style used in Price Overlay (currently duplicate `_metric()` functions)
- [ ] Strategy suggestions section is clear and actionable

### 6. Strike Scanner (`src/pages/scanner.py`)

- [ ] DataTable is readable with 14 columns — check horizontal scroll works
- [ ] Column widths are appropriate (narrow for flags, wider for prices)
- [ ] Row highlighting (green for safe, red for risky) is not too garish
- [ ] "Click to apply" interaction is obvious (maybe add a dedicated Apply button per row)
- [ ] Controls row (option type, min volume, etc.) doesn't wrap awkwardly

### 7. Cross-Cutting Issues

**Duplicate code:**
- [ ] `_metric()` helper exists in both `price_overlay.py` and `divergence.py` — extract to shared component
- [ ] Style constants (`SECTION_STYLE`, `TABLE_STYLE`, etc.) are defined in `historical.py` and partially in `live_trading.py` — extract to `src/pages/styles.py` or `src/pages/components.py`

**Color consistency:**
- [ ] Positive P&L: always `#28a745` (green)
- [ ] Negative P&L: always `#dc3545` (red)
- [ ] Neutral/info: always `#6c757d` (gray)
- [ ] Warning: always `#856404` on `#fff3cd` (yellow)
- [ ] Verify these are the same across all pages

**Typography:**
- [ ] All monetary values use monospace font
- [ ] Percentages use monospace font
- [ ] Consistent decimal places (2 for dollars, 4 for percentages, 0 for strikes)

**Loading states:**
- [ ] Historical analysis shows loading spinner during computation
- [ ] Scanner shows loading during scan (already has `dcc.Loading`)
- [ ] Price overlay and divergence show loading during chart generation

## Execution Steps

1. **Read all page files** to understand current state
2. **Run the app** (`python app.py`) and visually inspect each tab
3. **Fix critical breaks first** (overlapping slider labels, layout collisions)
4. **Extract shared styles** to `src/pages/components.py`:
   - Style constants (SECTION_STYLE, TABLE_STYLE, etc.)
   - Shared components (`metric_card()`, `pnl_span()`, `section_card()`)
5. **Fix each page** against the checklist above
6. **Verify visually** — take screenshots or have the user confirm
7. **Run tests** — `python -m pytest tests/ -v` to ensure no business logic changed

## Shared Components to Extract

Create `src/pages/components.py` with reusable display helpers:

```python
# src/pages/components.py
"""Shared UI components and style constants for all pages."""

# -- Style constants --
SECTION = {
    'border': '1px solid #dee2e6',
    'borderRadius': '6px',
    'padding': '16px',
    'marginBottom': '20px',
    'backgroundColor': '#ffffff',
}

# -- Colors --
COLOR_POSITIVE = '#28a745'
COLOR_NEGATIVE = '#dc3545'
COLOR_NEUTRAL = '#6c757d'
COLOR_WARNING_TEXT = '#856404'
COLOR_WARNING_BG = '#fff3cd'

# -- Reusable components --
def pnl_span(value: float) -> html.Span:
    """Colored P&L display: green positive, red negative."""
    ...

def metric_card(label: str, value: str, size: str = 'normal') -> html.Div:
    """Metric card with label above, value below."""
    ...

def section(title: str, *children, subtitle: str = None) -> html.Div:
    """Consistent section wrapper with title."""
    ...
```

## Known Issues (from code review + screenshot)

1. **Sidebar Entry Time slider** — all ~78 time marks rendered in 320px, completely unreadable
2. **Duplicate `_metric()` function** in `price_overlay.py:284` and `divergence.py:152`
3. **Duplicate style constants** — `SECTION_STYLE` defined in both `historical.py:29` and `live_trading.py:19`
4. **No shared color constants** — hex codes hardcoded across all files
5. **Sidebar doesn't scroll properly** on smaller screens (position: sticky + 100vh)
6. **Strategy Type dropdown** in `historical.py` is misaligned — flex container with label + dropdown needs vertical centering

## Important Rules

- **Never change business logic** — this is purely visual. Same inputs, same outputs.
- **Don't add new dependencies** — use only Dash built-in components (`dash`, `dash_table`, `plotly`)
- **Don't redesign the layout** — keep sidebar + tabbed content. Fix what's broken, improve what's unclear.
- **Test after every change** — `python -m pytest tests/ -v`
- **If `$ARGUMENTS` specifies a target area**, only fix that area (e.g., "sidebar" = fix slider + strikes only)
- **Ask the user to confirm visual changes** — take a screenshot or describe what changed so they can verify
- **Callback wiring errors are NOT a UI issue** — if you find nonexistent component IDs, missing Inputs/Outputs, or dynamic ID problems, use `/test-suite dash` to diagnose and fix those first
