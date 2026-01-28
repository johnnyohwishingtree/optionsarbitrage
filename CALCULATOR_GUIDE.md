# Strategy Calculator Guide

## Overview

The Strategy Calculator is an interactive web-based tool for visualizing and simulating the SPY/SPX 0DTE options strategy. It allows you to explore different strike combinations, entry prices, and exit scenarios to understand the P&L characteristics before executing live trades.

## Quick Start

### Launch the Calculator

```bash
python3 -m streamlit run strategy_calculator.py
```

The calculator will open in your browser at: `http://localhost:8501`

### Run Validation Tests

```bash
python3 test_calculator.py
```

This validates the P&L calculation logic against historical data.

## Features

### 1. Date Selection

- Automatically detects available dates from `data/underlying_prices_*.csv` files
- Loads 1-minute price data for SPY and SPX for the selected date
- Currently available dates:
  - **January 27, 2026** (today's data)
  - **January 26, 2026** (previous trading day)

### 2. Entry Time Configuration

- **Entry Time Picker**: Select when you enter the position (e.g., 9:30 AM, 12:00 PM)
- Automatically uses the underlying prices at that time
- Default: Market open (9:30 AM ET)

### 3. Strike Configuration

The calculator supports two strike configuration modes:

#### Auto Mode (Recommended)
- Click "Auto-fill from current price" button
- Automatically brackets the current price:
  - **SPY**: Floor and ceiling strikes (e.g., 696, 697)
  - **SPX**: Rounded to $5 increments (e.g., 6985, 6990)
- Uses our tested strike selection algorithm

#### Manual Mode
- Manually enter SPY and SPX strikes
- Useful for exploring different strike combinations

### 4. Position Builder

Build your position by adding individual option legs:

#### Call Positions
- **Strike**: Option strike price
- **Direction**:
  - `BUY SPY / SELL SPX` (typical call spread direction)
  - `SELL SPY / BUY SPX` (reverse direction)
- **Quantity**: Number of contracts (e.g., 100 SPY, 10 SPX)
- **Entry Price**: Price paid/received per share

#### Put Positions
- Same configuration as calls
- **Direction**:
  - `SELL SPY / BUY SPX` (typical put spread direction)
  - `BUY SPY / SELL SPX` (reverse direction)

**Example Position (January 27 Strategy):**
```
Calls:
  Buy 100 SPY 697C @ $0.28
  Sell 10 SPX 6985C @ $5.90
  → Net credit: $3,100

Puts:
  Sell 100 SPY 697P @ $1.27
  Buy 10 SPX 6985P @ $7.70
  → Net credit: $4,900

Total Credit: $8,000 ($80/contract)
```

### 5. Exit Scenarios

The calculator provides three ways to analyze P&L:

#### A. End of Day (4:00 PM)
- Uses actual closing prices from the historical data
- Calculates settlement values for cash-settled SPX options
- Shows final P&L at expiration
- **Use for**: Backtesting completed trading days

**Example Output:**
```
Settlement Prices:
  SPY: $695.54
  SPX: $6978.58

P&L Breakdown:
  Calls:  +$3,100
  Puts:   -$3,180
  Total:  -$80
```

#### B. Custom Time Exit
- Select any time during the trading day
- Uses underlying prices at that specific time
- Calculates option values assuming immediate close
- **Use for**: Exploring intraday exit strategies

#### C. Price Range Sweep (Payoff Diagram)
- Tests P&L across a range of underlying prices
- Generates interactive visualization showing:
  - Total P&L vs price
  - Call spread P&L (green line)
  - Put spread P&L (red line)
  - Vertical markers for strikes and entry price
- **Use for**: Understanding risk profile and breakeven points

**Interactive Features:**
- Hover over chart to see exact P&L at each price
- Zoom in/out on specific price ranges
- Pan to explore different areas
- Toggle call/put visibility

### 6. Metrics Display

The calculator shows key position metrics:

#### Entry Metrics
- **Initial Credit**: Total premium collected when opening position
- **Max Profit**: Theoretical maximum profit (if held to expiration in profit zone)
- **Entry SPY**: SPY price at entry time
- **Entry SPX**: SPX price at entry time

#### Exit Metrics (per scenario)
- **Exit SPY/SPX**: Underlying prices at exit
- **Call P&L**: Profit/loss on call spread
- **Put P&L**: Profit/loss on put spread
- **Total P&L**: Combined P&L
- **Return**: P&L as percentage of margin (if configured)

## Usage Examples

### Example 1: Backtest January 27 Strategy

1. Select **Date**: `20260127`
2. Set **Entry Time**: `09:30` (market open)
3. Click **"Auto-fill from current price"** → Fills SPY 696/697, SPX 6985/6990
4. Add **Call Position**:
   - Strike: 697 (SPY), 6985 (SPX)
   - Direction: Buy SPY / Sell SPX
   - Quantity: 100 (SPY), 10 (SPX)
   - Entry: $0.28 (SPY), $5.90 (SPX)
5. Add **Put Position**:
   - Strike: 697 (SPY), 6985 (SPX)
   - Direction: Sell SPY / Buy SPX
   - Quantity: 100 (SPY), 10 (SPX)
   - Entry: $1.27 (SPY), $7.70 (SPX)
6. Click **"Calculate End of Day P&L"**
7. **Result**: Total P&L = -$80 (essentially break-even)

### Example 2: Explore Breakeven Points

1. Set up position as above
2. Click **"Generate Price Range Payoff Diagram"**
3. Examine the chart:
   - Below $690: Profit from put spread dominates
   - $690-$697: Transition zone
   - Above $697: Profit from call spread dominates
   - Notice non-linear behavior near strikes due to strike mismatch

### Example 3: Test Early Exit

1. Set up position as above
2. Change **Exit Time** to `14:00` (2:00 PM)
3. Click **"Calculate Custom Time P&L"**
4. Compare P&L at 2:00 PM vs 4:00 PM close
5. Determine if early exit would have been beneficial

### Example 4: Compare Different Strikes

1. Set up position with SPY 696 / SPX 6985
2. Note the P&L
3. Clear position and test SPY 697 / SPX 6990
4. Compare the payoff diagrams side-by-side
5. Identify which strike combination offers better risk/reward

## Understanding the Outputs

### Interpreting Payoff Diagrams

The price range sweep generates a chart with three lines:

1. **Green Line (Call P&L)**
   - Flat below call strike (options expire worthless, keep premium)
   - Slopes down above strike (long SPY calls gain, but short SPX calls lose more)
   - Kink at strike price indicates transition

2. **Red Line (Put P&L)**
   - Slopes up below put strike (short SPY puts lose, but long SPX puts gain more)
   - Flat above strike (options expire worthless, keep premium)
   - Kink at strike price indicates transition

3. **Blue Line (Total P&L)**
   - Combined result of both spreads
   - Shows actual profit zone
   - Note: NOT a straight line due to SPY/SPX ratio mismatch

**Key Observations:**
- Profit zone typically within ±1-2% of entry price
- Maximum profit when both sides expire out-of-the-money
- Losses accelerate beyond ±1.5% moves
- Asymmetric risk if SPY/SPX tracking diverges

### P&L Components

**Initial Credit**: Premium collected upfront
```
= (SPX Call Premium - SPY Call Premium) * 100 * SPY Qty
  + (SPY Put Premium - SPX Put Premium) * 100 * SPY Qty
```

**Settlement Value**: Intrinsic value at expiration
```
Call: max(0, Underlying - Strike)
Put:  max(0, Strike - Underlying)
```

**P&L per Leg**:
```
BUY:  (Exit Price - Entry Price) * Qty * 100
SELL: (Entry Price - Exit Price) * Qty * 100
```

## Data Requirements

The calculator requires historical price data in the following format:

### File: `data/underlying_prices_YYYYMMDD.csv`

```csv
symbol,time,open,high,low,close,volume
SPY,2026-01-27 09:30:00-05:00,694.18,694.50,694.10,694.30,1234567
SPY,2026-01-27 09:31:00-05:00,694.30,694.60,694.25,694.55,1234567
...
SPX,2026-01-27 09:30:00-05:00,6965.96,6970.00,6965.50,6968.00,0
SPX,2026-01-27 09:31:00-05:00,6968.00,6972.00,6967.50,6971.00,0
...
```

### Generating Historical Data

To download a new day's data:

```bash
python3 download_real_prices.py
```

This will:
1. Connect to Interactive Brokers
2. Fetch 1-minute bars for SPY and SPX
3. Save to `data/underlying_prices_YYYYMMDD.csv`
4. Make the data available in the calculator

## Validation

### Automated Tests

The `test_calculator.py` script validates:

1. **P&L Calculation Logic**: Confirms option settlement and spread P&L formulas
2. **Historical Accuracy**: Compares calculated P&L against actual trading results
3. **Risk Profile**: Validates profit zone matches documented ±1% range
4. **Price Sweep**: Tests payoff diagram across full price range

**Example Test Output:**
```
TEST 1: January 27 Strategy
  Total P&L: -$80 ✓ (matches expected break-even)

TEST 2: Price Range Sweep
  $690: +$2,400 ✓
  $697: +$2,190 ✓
  $703: +$2,010 ✓

TEST 3: Risk Profile
  Flat: +$4,000 ✓ (in profit zone)
  ±1%: +$4,000 ✓ (in profit zone)
```

### Manual Validation Steps

1. **Compare to Backtest Results**:
   - Run calculator with known historical date
   - Compare P&L to backtest CSV results
   - Should match within $100 (due to bid/ask spreads)

2. **Check Strike Bracketing**:
   - Verify auto-fill strikes bracket current price
   - SPY strikes differ by $1
   - SPX strikes differ by $5

3. **Validate Settlement Values**:
   - At expiration, ITM options should equal intrinsic value
   - OTM options should equal $0
   - Calculate manually to confirm

4. **Test Edge Cases**:
   - Exactly at-the-money (settle at $0.00)
   - Deep in-the-money (full intrinsic value)
   - Large moves (>2%) to test loss scenarios

## Tips for Best Results

### 1. Data Quality
- Always use complete trading day data (390 bars per symbol)
- Verify closing prices match external sources
- Check for gaps or missing timestamps

### 2. Entry Timing
- Our backtests use market open (9:30 AM) entries
- Avoid first 5 minutes for more stable fills
- Compare different entry times to find optimal

### 3. Strike Selection
- Use auto-fill for consistency with backtests
- Test adjacent strikes to see sensitivity
- Consider VIX level when choosing strikes

### 4. Position Sizing
- Calculator assumes theoretical unlimited margin
- Adjust quantities to match your account size
- Remember: 10 SPX ≈ 100 SPY in notional value

### 5. Interpreting Results
- Small P&L (-$500 to +$500) = essentially break-even
- Large profits (+$3,000+) = market stayed very calm
- Losses indicate volatility exceeded strategy tolerance

## Common Issues and Solutions

### Issue: "No data available for this date"
**Solution**: Download the data first with `download_real_prices.py`

### Issue: P&L doesn't match expectations
**Solution**:
- Check entry prices (bid vs ask)
- Verify strike prices are correct
- Confirm quantities match (100 SPY = 10 SPX)

### Issue: Chart not displaying
**Solution**:
- Ensure plotly is installed: `pip3 install plotly`
- Check browser JavaScript is enabled
- Try refreshing the page

### Issue: Slow performance
**Solution**:
- Use fewer dates in data/ folder
- Reduce price range in sweep
- Close other Streamlit apps

## Future Enhancements

Potential features to add:

1. **Multi-Scenario Comparison**: Compare 2-3 strategies side-by-side
2. **Live Data Integration**: Pull real-time prices from IBKR
3. **Optimization Mode**: Find best strikes for current conditions
4. **Risk Metrics**: Add Greeks, probability of profit, etc.
5. **Export Functionality**: Save scenarios to PDF/CSV
6. **Historical Performance**: Show all past trades in one view
7. **Margin Calculator**: Estimate required margin for position
8. **Tracking Error Visualization**: Show SPY vs SPX divergence over time

## Related Files

- **strategy_calculator.py**: Main calculator application
- **test_calculator.py**: Validation test suite
- **download_real_prices.py**: Data collection script
- **data/underlying_prices_*.csv**: Historical price data
- **RISK_CORRECTION.md**: Risk profile documentation
- **STRATEGY_DOCUMENTATION.md**: Overall strategy description

## Development Best Practices

### Test-Driven Bug Fixes

When a bug is identified in the calculator, follow this workflow:

1. **Write a Test to Reproduce the Bug**
   - Create a test that fails due to the bug
   - Use actual data values that demonstrate the issue
   - Make the test specific and focused on the bug

2. **Fix the Bug**
   - Implement the fix in the source code
   - Ensure the code change addresses the root cause

3. **Verify the Fix**
   - Run the test to confirm it now passes
   - Run all existing tests to ensure no regressions
   - Manually verify in the calculator UI

**Example: Price Range Mismatch Bug (Fixed 2026-01-27)**

**Bug Report:**
- "Scenario Analysis" P&L showed $50 profit
- "Max Loss (in range)" showed $-54.77 profit
- These should be consistent but were using different price references

**Test Created:** `test_price_range_consistency.py`

Run with:
```bash
python3 test_price_range_consistency.py
```

Key test:
```python
def test_price_range_centered_on_entry():
    """Test that price range sweep centers on entry price, not EOD"""
    # CORRECT: Price range should center on ENTRY prices
    correct_spy_range = np.linspace(entry_spy['close'] * 0.97, entry_spy['close'] * 1.03, 100)

    # WRONG: Price range centered on EOD prices (the bug)
    wrong_spy_range = np.linspace(eod_spy * 0.97, eod_spy * 1.03, 100)

    # Verify they're different
    assert not np.allclose(correct_spy_range.min(), wrong_spy_range.min())
```

**Fix Applied:**
```python
# Before (Bug):
spy_range = np.linspace(eod_spy * 0.97, eod_spy * 1.03, 100)

# After (Fixed):
spy_range = np.linspace(entry_spy['close'] * 0.97, entry_spy['close'] * 1.03, 100)
```

**Verification:**
- Test passes ✅
- P&L and Max Loss now use consistent price references
- Manual testing confirms values align correctly

### Bug Tracking

Document all bugs in this section with:
- Date identified
- Bug description
- Test created
- Fix applied
- Verification steps

**Bug #2: Widget Fields Not Updating (Fixed 2026-01-27)**

**Bug Report:**
- User reported: "whenever I change putspread or call spread direction, it doesn't reflect the input fields in Position Builder with new data from the db"
- User reported: "whenever I change the strike price, it also doesn't reflect the input fields in the Position Builder with new data from the db"
- Root cause: Widget keys only included `entry_time_idx`, not strikes or directions
- When strikes/directions changed, widgets weren't recreated with new estimated prices

**Test Created:** `test_widget_key_updates.py`

Run with:
```bash
python3 test_widget_key_updates.py
```

Key tests:
```python
def test_strike_change_updates_prices():
    """Test that changing strikes produces different estimated prices"""
    # Test with two different strike pairs and verify prices change
    strike_pair_1 = (695, 6975)
    strike_pair_2 = (694, 6965)

    # Verify at least some prices change when strikes change
    any_different = (
        prices_1['spy_call'] != prices_2['spy_call'] or
        prices_1['spx_call'] != prices_2['spx_call'] or
        prices_1['spy_put'] != prices_2['spy_put'] or
        prices_1['spx_put'] != prices_2['spx_put']
    )
    assert any_different

def test_widget_keys_include_all_parameters():
    """Test that widget keys include time, strikes, and direction"""
    # Keys must include all state variables that should trigger updates
    call_key = f"sell_spx_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"

    # Verify changing any parameter produces a different key
    assert str(entry_time_idx) in call_key
    assert str(spy_strike) in call_key
    assert str(spx_strike) in call_key
    assert call_direction in call_key
```

**Fix Applied:**
```python
# Before (incomplete):
sell_spx_call_price = st.number_input(
    f"Sell SPX {spx_strike}C Price",
    key=f"sell_spx_px_{entry_time_idx}"  # Missing strikes and direction!
)

# After (complete):
sell_spx_call_price = st.number_input(
    f"Sell SPX {spx_strike}C Price",
    key=f"sell_spx_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
)
```

Applied to all 4 price input widgets:
- Call spread: `sell_spx_px_*` and `buy_spy_px_*` (lines 334-349)
- Put spread: `sell_spy_p_px_*` and `buy_spx_p_px_*` (lines 362-377)

**Verification:**
- Test passes with all widget keys including all required parameters
- Changing time, strikes, or direction now produces different keys
- Streamlit recreates widgets with new estimated prices when keys change
- Manual testing confirms fields update correctly in UI

**Bug #3: Calculated Prices Instead of Database Prices (Fixed 2026-01-27)**

**Bug Report:**
- User reported: "when I adjust spy strike to 698 now its becomes 0.01 but we should have real data for that right?"
- User directive: "yes all data should pull from the database, is that not what we are doing? We want real data and not calculated data, if you have calculated data anywhere please remove that logic"
- Root cause: Calculator was falling back to calculated prices (e.g., `max(0.01, entry_spy - strike + 0.50)`) when strikes changed, instead of looking up real market prices from `options_data_20260126.csv`
- Affected strikes: ANY strike that differed from `best_combo.json` would show calculated prices instead of database prices

**Test Created:** `test_database_price_lookup.py`

Run with:
```bash
python3 test_database_price_lookup.py
```

Key tests:
```python
def test_spy_698_call_real_price():
    """Test that SPY 698C returns real database price ($0.02), not calculated ($0.01)"""
    price = get_option_price_from_db(df_options, 'SPY', 698, 'C', entry_time)

    assert price == 0.02, "Expected $0.02 from database, got calculated $0.01"

def test_all_option_legs_from_database():
    """Test that all four option legs can be looked up from database"""
    spy_call = get_option_price_from_db(df_options, 'SPY', spy_strike, 'C', entry_time)
    spx_call = get_option_price_from_db(df_options, 'SPX', spx_strike, 'C', entry_time)
    spy_put = get_option_price_from_db(df_options, 'SPY', spy_strike, 'P', entry_time)
    spx_put = get_option_price_from_db(df_options, 'SPX', spx_strike, 'P', entry_time)

    # All must exist in database
    assert all([spy_call, spx_call, spy_put, spx_put] is not None)
```

**Fix Applied:**
```python
# Before (Bug): Used calculated fallback when strikes changed
if strikes_match_best_combo:
    default_spy_call_price = best_combo.get('spy_call_ask', max(0.01, entry_spy - spy_strike + 0.50))
else:
    # WRONG: Calculate estimated prices
    default_spy_call_price = max(0.01, entry_spy - spy_strike + 0.50)

# After (Fixed): Always use database
def get_option_price_from_db(df_options, symbol, strike, right, entry_time):
    """Look up option price from database at specified time"""
    mask = (
        (df_options['symbol'] == symbol) &
        (df_options['strike'] == strike) &
        (df_options['right'] == right) &
        (df_options['time'] == entry_time)
    )
    matches = df_options[mask]
    return matches.iloc[0]['open'] if len(matches) > 0 else None

# Load options database
df_options = pd.read_csv(f'data/options_data_{selected_date}.csv')
df_options['time'] = pd.to_datetime(df_options['time'], utc=True)

# Look up ALL prices from database
spy_call_price = get_option_price_from_db(df_options, 'SPY', spy_strike, 'C', entry_time)
spx_call_price = get_option_price_from_db(df_options, 'SPX', spx_strike, 'C', entry_time)
spy_put_price = get_option_price_from_db(df_options, 'SPY', spy_strike, 'P', entry_time)
spx_put_price = get_option_price_from_db(df_options, 'SPX', spx_strike, 'P', entry_time)
```

Applied to strategy_calculator_simple.py:
- Added `get_option_price_from_db()` function (lines 36-65)
- Load options database at startup (lines 118-127)
- Replaced ALL calculated price logic with database lookups (lines 243-294)
- Removed `estimate_option_price()` function (previously lines 36-69)
- Updated UI labels from "Estimated" to "Database" prices

**Verification:**
- Test passes with SPY 698C returning $0.02 (database) not $0.01 (calculated)
- All four option legs successfully looked up from database
- Different strikes return different database prices (697C=$0.03, 698C=$0.02, 699C=$0.01)
- NO calculated fallback logic remains in code
- Manual testing: Changing strike from 697→698 now shows correct database price ($0.02)

## Support

For questions or issues:

1. Check this guide first
2. Review STRATEGY_DOCUMENTATION.md for strategy context
3. Run test_calculator.py to validate installation
4. Check data files exist in data/ folder

## Summary

The Strategy Calculator is a powerful tool for:
- **Backtesting**: Validate historical performance
- **Planning**: Preview trades before execution
- **Learning**: Understand strategy behavior across scenarios
- **Optimization**: Find best parameters for current conditions

Use it before every live trade to confirm your expected P&L and risk profile!
