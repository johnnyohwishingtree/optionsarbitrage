#!/usr/bin/env python3
"""
Simple Strategy Calculator - Uses best_combo.json for real prices

Until the database is populated with option prices, this uses:
- Underlying prices from CSV files (real 1-min data)
- Option prices from best_combo.json (real market prices from today)

Run with: streamlit run strategy_calculator_simple.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import json
import os
import sys
import asyncio

# Setup event loop for ib_insync
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Import IBKR client after setting up event loop
sys.path.insert(0, '/Users/johnnyhuang/personal/optionsarbitrage')
from src.broker.ibkr_client import IBKRClient
from src.pnl import calculate_option_pnl, calculate_settlement_value, calculate_best_worst_case_with_basis_drift
from src.pricing import get_option_price_from_db, get_option_price_with_liquidity


# Page config
st.set_page_config(
    page_title="0DTE Strategy Calculator",
    page_icon="📊",
    layout="wide"
)

st.title("📊 0DTE Strategy Calculator")  # Title set before symbol pair selected

# Initialize session state early (needed for banner check)
if 'strikes_just_applied' not in st.session_state:
    st.session_state.strikes_just_applied = False

# Show banner if strikes were just applied from Scanner
if st.session_state.strikes_just_applied:
    applied_spy = st.session_state.get('applied_spy_strike')
    applied_spx = st.session_state.get('applied_spx_strike')
    applied_dir = st.session_state.get('applied_direction', '')
    applied_time = st.session_state.get('applied_entry_time', '')

    _sym1_label = st.session_state.get('applied_sym1', 'SYM1')
    _sym2_label = st.session_state.get('applied_sym2', 'SYM2')
    st.success(f"✅ **Applied: {_sym1_label} {applied_spy} / {_sym2_label} {applied_spx}** | {applied_dir} | Entry Time: {applied_time}")
    st.info("👆 **Click the 📊 Historical Analysis tab above to analyze this trade!**")

    # Clear the flag after showing
    st.session_state.strikes_just_applied = False

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Historical Analysis", "🔴 Live Paper Trading", "📈 Price Overlay", "📉 Underlying Divergence", "🔍 Strike Scanner"])

# Sidebar configuration
st.sidebar.header("Configuration")

# Note: Tab content will be defined below after data loading

# Date selection
st.sidebar.subheader("📅 Date Selection")
data_dir = 'data'
available_dates = []
if os.path.exists(data_dir):
    for file in sorted(os.listdir(data_dir)):
        if file.startswith('underlying_prices_') and file.endswith('.csv'):
            date_str = file.replace('underlying_prices_', '').replace('.csv', '')
            # Format date for display: YYYYMMDD -> YYYY-MM-DD
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            available_dates.append((date_str, formatted_date))

if not available_dates:
    st.error("No historical data found. Please download data first.")
    st.stop()

# Show dates in reverse chronological order (most recent first)
available_dates.reverse()
date_options = [f"{formatted} ({raw})" for raw, formatted in available_dates]
selected_date_display = st.sidebar.selectbox(
    "Select Trading Date",
    date_options,
    index=0
)

# Extract the raw date string (YYYYMMDD)
selected_date = available_dates[date_options.index(selected_date_display)][0]

# Load underlying price data for selected date
UNDERLYING_FILE = f'data/underlying_prices_{selected_date}.csv'
if not os.path.exists(UNDERLYING_FILE):
    st.error(f"Underlying price data not found: {UNDERLYING_FILE}")
    st.stop()

df_underlying = pd.read_csv(UNDERLYING_FILE)
# Parse time column - handle timezone-aware strings
df_underlying['time'] = pd.to_datetime(df_underlying['time'], utc=True)

# Load options price data for selected date
OPTIONS_FILE = f'data/options_data_{selected_date}.csv'
df_options = None
if os.path.exists(OPTIONS_FILE):
    df_options = pd.read_csv(OPTIONS_FILE)
    df_options['time'] = pd.to_datetime(df_options['time'], utc=True)
    st.sidebar.success(f"✅ Loaded {len(df_options)} option TRADES records")

# Load BID_ASK data for selected date (optional)
BIDASK_FILE = f'data/options_bidask_{selected_date}.csv'
df_bidask = None
if os.path.exists(BIDASK_FILE):
    df_bidask = pd.read_csv(BIDASK_FILE)
    df_bidask['time'] = pd.to_datetime(df_bidask['time'], utc=True)
    st.sidebar.success(f"✅ Loaded {len(df_bidask)} bid/ask records")

if df_options is None and df_bidask is None:
    st.sidebar.warning(f"⚠️  No option data found for {selected_date}")
    st.sidebar.info("Need options_data or options_bidask CSV")

# Symbol pair selection
st.sidebar.subheader("🔄 Symbol Pair")
SYMBOL_PAIRS = {
    "XSP / SPX": ("XSP", "SPX"),
    "SPY / SPX": ("SPY", "SPX"),
    "SPY / XSP": ("SPY", "XSP"),
}
# Only show pairs where both symbols have underlying data
_available_symbols = set(df_underlying['symbol'].unique())
_available_pairs = {label: syms for label, syms in SYMBOL_PAIRS.items()
                    if syms[0] in _available_symbols and syms[1] in _available_symbols}
if not _available_pairs:
    st.error("No valid symbol pairs found in data")
    st.stop()

selected_pair = st.sidebar.selectbox("Symbol Pair", list(_available_pairs.keys()))
SYM1, SYM2 = _available_pairs[selected_pair]

# Quantity ratio: 10:1 when SYM2 is SPX ($5 strikes), 1:1 when both are $1-strike symbols
QTY_RATIO = 10 if SYM2 == 'SPX' else 1
SYM2_STRIKE_STEP = 5 if SYM2 == 'SPX' else 1

# Load best combo data (for default values)
BEST_COMBO_FILE = '/tmp/best_combo.json'
best_combo = {}
if os.path.exists(BEST_COMBO_FILE):
    with open(BEST_COMBO_FILE) as f:
        best_combo = json.load(f)

spy_df = df_underlying[df_underlying['symbol'] == SYM1].copy()
spx_df = df_underlying[df_underlying['symbol'] == SYM2].copy()

if spy_df.empty or spx_df.empty:
    st.error(f"No {SYM1} or {SYM2} data found in file")
    st.stop()

st.sidebar.success(f"✅ Loaded data for {selected_date}")

# Data collection button
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Collection")

# Initialize session state for tracking background collection
if 'collection_status' not in st.session_state:
    st.session_state.collection_status = {}

# Initialize session state for selected strikes (from Strike Scanner)
if 'selected_spy_strike' not in st.session_state:
    st.session_state.selected_spy_strike = None
if 'selected_spx_strike' not in st.session_state:
    st.session_state.selected_spx_strike = None
if 'selected_entry_time' not in st.session_state:
    st.session_state.selected_entry_time = None
if 'strikes_just_applied' not in st.session_state:
    st.session_state.strikes_just_applied = False
if 'applied_direction' not in st.session_state:
    st.session_state.applied_direction = None
if 'applied_spy_strike' not in st.session_state:
    st.session_state.applied_spy_strike = None
if 'applied_spx_strike' not in st.session_state:
    st.session_state.applied_spx_strike = None
if 'applied_entry_time' not in st.session_state:
    st.session_state.applied_entry_time = None
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'applied_scanner_right' not in st.session_state:
    st.session_state.applied_scanner_right = None

def _apply_scanner_result(spy_s, spx_s, direction, entry_time, scanner_right):
    """Callback for scanner Apply buttons. Runs BEFORE the script reruns,
    so session state is available from line 1 of the next run."""
    st.session_state.selected_spy_strike = spy_s
    st.session_state.selected_spx_strike = spx_s
    st.session_state.selected_entry_time = entry_time
    st.session_state.strikes_just_applied = True
    st.session_state.applied_spy_strike = spy_s
    st.session_state.applied_spx_strike = spx_s
    st.session_state.applied_direction = direction
    st.session_state.applied_entry_time = entry_time
    st.session_state.applied_scanner_right = scanner_right
    st.session_state.applied_sym1 = SYM1
    st.session_state.applied_sym2 = SYM2

collection_key = f"collection_{selected_date}"

if st.sidebar.button("🔄 Update Data for Selected Date", use_container_width=True, help="Fetch missing data incrementally (only new bars since last update)"):
    import subprocess

    try:
        # Start background collection process using the project venv Python
        venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv', 'bin', 'python')
        process = subprocess.Popen(
            [venv_python, 'collect_market_data.py', '--date', selected_date, '--data-type', 'both'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )

        # Store process info in session state
        st.session_state.collection_status[collection_key] = {
            'pid': process.pid,
            'date': selected_date,
            'started': True
        }

        st.sidebar.success(f"✅ Started data collection for {selected_date}")
        st.sidebar.info("Collection is running in the background. You can continue using the calculator.")
        st.sidebar.caption(f"Process ID: {process.pid}")

    except Exception as e:
        st.sidebar.error(f"❌ Error starting collection: {e}")

# Show status of background collections
if st.session_state.collection_status:
    active_collections = [k for k, v in st.session_state.collection_status.items() if v.get('started')]
    if active_collections:
        st.sidebar.info(f"🔄 {len(active_collections)} collection(s) running in background")
        st.sidebar.caption("Data will appear on refresh once complete")

# Entry time selection - convert to ET for display
spy_df['time_et'] = spy_df['time'].dt.tz_convert('America/New_York')
spx_df['time_et'] = spx_df['time'].dt.tz_convert('America/New_York')

# Create time labels for display
spy_df['time_label'] = spy_df['time_et'].dt.strftime('%I:%M %p ET')
spy_df['time_short'] = spy_df['time_et'].dt.strftime('%H:%M')  # For matching with scanner results
time_labels = spy_df['time_label'].tolist()
time_short_labels = spy_df['time_short'].tolist()

# Initialize widget keys in session state if not present
if 'entry_time_slider' not in st.session_state:
    st.session_state.entry_time_slider = 0

# Update entry time from scanner selection BEFORE widget renders
if st.session_state.selected_entry_time is not None:
    selected_time = st.session_state.selected_entry_time
    if selected_time in time_short_labels:
        st.session_state.entry_time_slider = time_short_labels.index(selected_time)
    st.session_state.selected_entry_time = None  # Clear after using

# Convert to ET for display
st.sidebar.subheader("Entry Time")
entry_time_idx = st.sidebar.slider(
    "Select Entry Time",
    0,
    len(time_labels) - 1,
    key="entry_time_slider",
    format=""
)

entry_time_label = time_labels[entry_time_idx]
st.sidebar.write(f"**{entry_time_label}**")

# Get prices at entry time using index
entry_spy = spy_df.iloc[entry_time_idx]
entry_spx = spx_df.iloc[entry_time_idx]

st.sidebar.metric(f"{SYM1} Price", f"${entry_spy['close']:.2f}")
st.sidebar.metric(f"{SYM2} Price", f"${entry_spx['close']:.2f}")

# Strike configuration
st.sidebar.subheader("🎯 Strike Configuration")

# Get current prices at market open for default strike selection
entry_spy_open = spy_df.iloc[0]['close']
entry_spx_open = spx_df.iloc[0]['close']

# Strike selection with expanded range to accommodate scanner results
spy_min_strike = int(entry_spy_open * 0.90)
spy_max_strike = int(entry_spy_open * 1.10)
spx_min_strike = int((entry_spx_open * 0.90) / SYM2_STRIKE_STEP) * SYM2_STRIKE_STEP
spx_max_strike = int((entry_spx_open * 1.10) / SYM2_STRIKE_STEP) * SYM2_STRIKE_STEP

# Detect symbol pair change and reset strikes
_prev_pair = st.session_state.get('_last_symbol_pair')
_pair_changed = (_prev_pair is not None and _prev_pair != selected_pair)
st.session_state._last_symbol_pair = selected_pair
if _pair_changed:
    # Clear direction widget keys so they reinitialize with new symbol names
    for k in ['call_direction_select', 'put_direction_select']:
        st.session_state.pop(k, None)
    # Clear stale scan results (column names contain old symbol names)
    st.session_state.pop('scan_results', None)
    st.session_state.pop('stored_scan_results', None)

# Initialize widget keys in session state (or reset on pair change)
if 'spy_strike_input' not in st.session_state or _pair_changed:
    default_spy = best_combo.get('spy_strike', int(round(entry_spy_open))) if not _pair_changed else int(round(entry_spy_open))
    st.session_state.spy_strike_input = max(spy_min_strike, min(spy_max_strike, default_spy))

if 'spx_strike_input' not in st.session_state or _pair_changed:
    default_spx = best_combo.get('spx_strike', int(round(entry_spx_open / SYM2_STRIKE_STEP) * SYM2_STRIKE_STEP)) if not _pair_changed else int(round(entry_spx_open / SYM2_STRIKE_STEP) * SYM2_STRIKE_STEP)
    st.session_state.spx_strike_input = max(spx_min_strike, min(spx_max_strike, default_spx))

# Update strikes from scanner selection BEFORE widgets render
if st.session_state.selected_spy_strike is not None:
    new_spy = st.session_state.selected_spy_strike
    st.session_state.spy_strike_input = max(spy_min_strike, min(spy_max_strike, new_spy))
    st.session_state.selected_spy_strike = None  # Clear after using

if st.session_state.selected_spx_strike is not None:
    new_spx = st.session_state.selected_spx_strike
    st.session_state.spx_strike_input = max(spx_min_strike, min(spx_max_strike, new_spx))
    st.session_state.selected_spx_strike = None  # Clear after using

spy_strike = st.sidebar.number_input(
    f"{SYM1} Strike",
    min_value=spy_min_strike,
    max_value=spy_max_strike,
    key="spy_strike_input",
    step=1,
    help=f"Strike price for {SYM1} options"
)

spx_strike = st.sidebar.number_input(
    f"{SYM2} Strike",
    min_value=int(spx_min_strike),
    max_value=int(spx_max_strike),
    key="spx_strike_input",
    step=SYM2_STRIKE_STEP,
    help=f"Strike price for {SYM2} options (increments of {SYM2_STRIKE_STEP})"
)

# STRIKE MONEYNESS CHECKER
# Calculate moneyness (% from underlying at entry time)
spy_moneyness_pct = ((spy_strike - entry_spy['close']) / entry_spy['close']) * 100
spx_moneyness_pct = ((spx_strike - entry_spx['close']) / entry_spx['close']) * 100
moneyness_diff = abs(spy_moneyness_pct - spx_moneyness_pct)

# Display moneyness analysis
with st.sidebar.expander("⚠️ Strike Moneyness Check", expanded=(moneyness_diff > 0.05)):
    st.caption(f"**{SYM1} Strike {spy_strike}:**")
    st.caption(f"  {spy_moneyness_pct:+.4f}% from entry price ${entry_spy['close']:.2f}")

    st.caption(f"**{SYM2} Strike {spx_strike}:**")
    st.caption(f"  {spx_moneyness_pct:+.4f}% from entry price ${entry_spx['close']:.2f}")

    st.caption(f"**Moneyness Difference: {moneyness_diff:.4f}%**")

    if moneyness_diff > 0.05:
        st.warning(f"⚠️ **Strikes are mismatched by {moneyness_diff:.2f}%**\n\nThis creates basis risk! Even if {SYM1}/{SYM2} move perfectly in sync, the different moneyness levels will cause asymmetric P&L.")

        # Suggest better matched strikes
        # Find SYM2 strike that matches SYM1 moneyness
        target_spx_strike = entry_spx['close'] * (1 + spy_moneyness_pct / 100)
        suggested_spx = round(target_spx_strike / SYM2_STRIKE_STEP) * SYM2_STRIKE_STEP

        # Find SYM1 strike that matches SYM2 moneyness
        target_spy_strike = entry_spy['close'] * (1 + spx_moneyness_pct / 100)
        suggested_spy = round(target_spy_strike)

        st.info(f"**Suggested matched strikes:**\n- Keep {SYM1} {spy_strike}, use {SYM2} {int(suggested_spx)} ({spy_moneyness_pct:+.2f}%)\n- OR: Keep {SYM2} {spx_strike}, use {SYM1} {int(suggested_spy)} ({spx_moneyness_pct:+.2f}%)")
    else:
        st.success(f"✅ Strikes are well-matched (within 0.05%)")

# Strategy direction configuration
st.sidebar.subheader("📊 Strategy Direction")

call_direction_options = [
    f"Sell {SYM2}, Buy {SYM1}",
    f"Buy {SYM2}, Sell {SYM1}"
]
put_direction_options = [
    f"Sell {SYM1}, Buy {SYM2}",
    f"Buy {SYM1}, Sell {SYM2}"
]

default_call_direction = best_combo.get('call_direction', call_direction_options[0])
default_put_direction = best_combo.get('put_direction', put_direction_options[0])

# Override direction AND strategy from scanner Apply — set ALL widget keys BEFORE widgets render
_scanner_applied = False
if st.session_state.get('applied_scanner_right') and st.session_state.get('applied_direction'):
    _scanner_dir = st.session_state.applied_direction  # "Sell SYM2" or "Sell SYM1"
    _scanner_right = st.session_state.applied_scanner_right  # "P" or "C"

    # Set direction widget key
    if _scanner_right == 'P':
        if _scanner_dir == f'Sell {SYM2}':
            st.session_state.put_direction_select = f"Buy {SYM1}, Sell {SYM2}"
        else:
            st.session_state.put_direction_select = f"Sell {SYM1}, Buy {SYM2}"
    else:  # Calls
        if _scanner_dir == f'Sell {SYM2}':
            st.session_state.call_direction_select = f"Sell {SYM2}, Buy {SYM1}"
        else:
            st.session_state.call_direction_select = f"Buy {SYM2}, Sell {SYM1}"

    # Set strategy widget key
    if _scanner_right == 'P':
        st.session_state.strategy_select = "Puts Only"
    else:
        st.session_state.strategy_select = "Calls Only"

    # Clear flags after consuming — do this once, here
    st.session_state.applied_scanner_right = None
    st.session_state.applied_direction = None
    _scanner_applied = True

# Force tab reset to Historical Analysis after scanner Apply.
# on_click callback sets flags → natural rerun → consuming code above processes & clears flags
# → st.rerun() forces fresh render with tab reset → flags already cleared so no loop.
if _scanner_applied:
    st.rerun()

# Initialize direction widget keys if not set
if 'call_direction_select' not in st.session_state:
    st.session_state.call_direction_select = default_call_direction
if 'put_direction_select' not in st.session_state:
    st.session_state.put_direction_select = default_put_direction

call_direction = st.sidebar.selectbox(
    "Call Spread Direction",
    call_direction_options,
    key="call_direction_select",
    help="Direction for call spread"
)

put_direction = st.sidebar.selectbox(
    "Put Spread Direction",
    put_direction_options,
    key="put_direction_select",
    help="Direction for put spread"
)

# Calculate time fraction remaining (1.0 at open, 0.0 at close)
# Trading day: 9:30 AM to 4:00 PM ET = 390 minutes
total_minutes = 390
minutes_elapsed = entry_time_idx  # Each index = 1 minute
time_fraction = max(0, (total_minutes - minutes_elapsed) / total_minutes)

# Get option prices from database - NO CALCULATED PRICES!
# User directive: "We want real data and not calculated data"

# Update best_combo with selected values for display
best_combo['spy_strike'] = spy_strike
best_combo['spx_strike'] = spx_strike
best_combo['call_direction'] = call_direction
best_combo['put_direction'] = put_direction

# Look up option prices from database at entry time
entry_time = entry_spy['time']

if df_options is not None or df_bidask is not None:
    # Look up all four option legs with liquidity info
    spy_call_liq = get_option_price_with_liquidity(df_options, df_bidask, SYM1, spy_strike, 'C', entry_time)
    spx_call_liq = get_option_price_with_liquidity(df_options, df_bidask, SYM2, spx_strike, 'C', entry_time)
    spy_put_liq = get_option_price_with_liquidity(df_options, df_bidask, SYM1, spy_strike, 'P', entry_time)
    spx_put_liq = get_option_price_with_liquidity(df_options, df_bidask, SYM2, spx_strike, 'P', entry_time)

    # Store liquidity info for all legs
    leg_liquidity = {
        f'{SYM1} {spy_strike}C': spy_call_liq,
        f'{SYM2} {spx_strike}C': spx_call_liq,
        f'{SYM1} {spy_strike}P': spy_put_liq,
        f'{SYM2} {spx_strike}P': spx_put_liq,
    }

    # Extract prices (backward compatible)
    spy_call_price = spy_call_liq['price'] if spy_call_liq else None
    spx_call_price = spx_call_liq['price'] if spx_call_liq else None
    spy_put_price = spy_put_liq['price'] if spy_put_liq else None
    spx_put_price = spx_put_liq['price'] if spx_put_liq else None

    # Check if all prices were found
    missing_prices = []
    if spy_call_price is None:
        missing_prices.append(f"{SYM1} {spy_strike}C")
    if spx_call_price is None:
        missing_prices.append(f"{SYM2} {spx_strike}C")
    if spy_put_price is None:
        missing_prices.append(f"{SYM1} {spy_strike}P")
    if spx_put_price is None:
        missing_prices.append(f"{SYM2} {spx_strike}P")

    if missing_prices:
        st.error(f"Option prices not found in database for: {', '.join(missing_prices)}")
        st.info(f"Database lookup: symbol={spy_strike}, time={entry_time}")
        st.info("Try selecting different strikes or ensure options data was downloaded for this date")
        st.stop()

    # Use the database prices directly (no estimation/calculation)
    default_spy_call_price = spy_call_price
    default_spx_call_price = spx_call_price
    default_spy_put_price = spy_put_price
    default_spx_put_price = spx_put_price

    # For display: these are the actual prices from database at entry time
    estimated_spy_call = spy_call_price
    estimated_spx_call = spx_call_price
    estimated_spy_put = spy_put_price
    estimated_spx_put = spx_put_price

    # Check for stale/illiquid legs
    stale_legs_call = [name for name, liq in leg_liquidity.items()
                       if liq and liq['is_stale'] and name.endswith('C')]
    stale_legs_put = [name for name, liq in leg_liquidity.items()
                      if liq and liq['is_stale'] and name.endswith('P')]
    stale_legs = stale_legs_call + stale_legs_put
else:
    leg_liquidity = {}
    # No database available - will show error in Tab 1 only
    # Don't call st.stop() here - let Tab 2 remain accessible
    pass

# Option prices from database (only show in sidebar if data exists)
if df_options is not None:
    st.sidebar.subheader("📊 Database Option Prices")
    price_source_label = "midpoint" if df_bidask is not None else "trade"
    st.sidebar.info(f"Real market prices at {entry_time_label} (source: {price_source_label})")

    def _format_leg_price(name, price, liq_info):
        """Format a leg price with liquidity indicator."""
        if liq_info is None:
            return f"**{name}:** ${price:.2f}"
        warning = ""
        if liq_info['is_stale']:
            warning = " :red[STALE (vol=0)]"
        elif liq_info['liquidity_warning']:
            warning = f" :orange[{liq_info['liquidity_warning']}]"
        source = f" ({liq_info['price_source']})" if liq_info['price_source'] == 'midpoint' else ""
        return f"**{name}:** ${price:.2f}{source}{warning}"

    with st.sidebar.expander("Call Prices", expanded=True):
        st.markdown(_format_leg_price(f"{SYM1} {spy_strike}C", estimated_spy_call, leg_liquidity.get(f'{SYM1} {spy_strike}C')))
        st.markdown(_format_leg_price(f"{SYM2} {spx_strike}C", estimated_spx_call, leg_liquidity.get(f'{SYM2} {spx_strike}C')))

    with st.sidebar.expander("Put Prices", expanded=True):
        st.markdown(_format_leg_price(f"{SYM1} {spy_strike}P", estimated_spy_put, leg_liquidity.get(f'{SYM1} {spy_strike}P')))
        st.markdown(_format_leg_price(f"{SYM2} {spx_strike}P", estimated_spx_put, leg_liquidity.get(f'{SYM2} {spx_strike}P')))

    # Sidebar liquidity status section
    if any(liq is not None for liq in leg_liquidity.values()):
        _has_stale = any(liq is not None and liq['is_stale'] for liq in leg_liquidity.values())
        with st.sidebar.expander("Liquidity Status", expanded=_has_stale):
            for name, liq in leg_liquidity.items():
                if liq is None:
                    st.write(f"**{name}:** No data")
                    continue
                vol = liq['volume']
                spread_str = ""
                if liq['spread'] is not None:
                    spread_str = f", spread=${liq['spread']:.2f} ({liq['spread_pct']:.1f}%)"
                status = "OK" if not liq['is_stale'] and (liq['spread_pct'] is None or liq['spread_pct'] <= 20) else "WARNING"
                if liq['is_stale']:
                    st.write(f"**{name}:** :red[STALE] vol={vol}{spread_str}")
                elif status == "WARNING":
                    st.write(f"**{name}:** :orange[WIDE] vol={vol}{spread_str}")
                else:
                    st.write(f"**{name}:** :green[OK] vol={vol}{spread_str}")

# Tab 1: Historical Analysis
with tab1:
    st.markdown("Using **real market prices** from historical trades")

    # Check if options data is available for this tab
    if df_options is None and df_bidask is None:
        st.error("❌ No option price data found. Cannot display historical analysis.")
        st.info(f"**Required:** {OPTIONS_FILE} or {BIDASK_FILE}")
        st.info("**To use Historical Analysis tab:**")
        st.write("1. Click '🔄 Update Data for Selected Date' in the sidebar, OR")
        st.write("2. Wait for the background data collection to complete")
        st.info("**💡 You can still use the 'Live Paper Trading' tab** which doesn't require historical options data!")
    else:
        # Main area: Position Builder
        st.header("Position Builder")

        # Strategy selection
        strategy_options = [
            "Full Strategy (Calls + Puts)",
            "Calls Only",
            "Puts Only"
        ]

        # Strategy type is set from scanner Apply at line ~690 (before any widgets render)

        selected_strategy = st.selectbox(
            "Select Strategy",
            strategy_options,
            key="strategy_select",
            help="Choose which legs of the strategy to trade"
        )

        # Show strategy description
        if selected_strategy == "Full Strategy (Calls + Puts)":
            st.info(f"**Strategy:** {best_combo['call_direction']} (calls) | {best_combo['put_direction']} (puts)")
            show_calls = True
            show_puts = True
        elif selected_strategy == "Calls Only":
            st.info(f"**Strategy:** {best_combo['call_direction']} (calls only)")
            show_calls = True
            show_puts = False
        else:  # Puts Only
            st.info(f"**Strategy:** {best_combo['put_direction']} (puts only)")
            show_calls = False
            show_puts = True

        # Check if active legs have stale prices
        active_stale = []
        if show_calls:
            active_stale.extend(stale_legs_call)
        if show_puts:
            active_stale.extend(stale_legs_put)

        if active_stale:
            st.error(
                f"**Cannot calculate P&L:** {', '.join(active_stale)} "
                f"{'has' if len(active_stale) == 1 else 'have'} zero trade volume at this entry time. "
                f"The price is stale (carried forward by IB) and not executable."
            )
            st.info("Try a different entry time, different strikes, or collect BID_ASK data for more accurate pricing.")
            st.stop()

        # Initialize variables for P&L calculation
        sell_spx_calls = 0
        buy_spy_calls = 0
        sell_spx_call_price = 0.0
        buy_spy_call_price = 0.0
        call_credit = 0.0

        sell_spy_puts = 0
        buy_spx_puts = 0
        sell_spy_put_price = 0.0
        buy_spx_put_price = 0.0
        put_credit = 0.0

        # Show columns based on selected strategy
        if show_calls and show_puts:
            col1, col2 = st.columns(2)
        elif show_calls or show_puts:
            col1 = st.container()
            col2 = None
        else:
            col1, col2 = st.columns(2)

        # Call Spread Section
        if show_calls:
            with col1 if col2 else col1:
                st.subheader("📞 Call Spread")
                st.write(f"**Direction:** {best_combo['call_direction']}")
                st.caption(f"Database prices at {entry_time_label}")

                # Determine position labels based on direction
                if call_direction == f"Buy {SYM2}, Sell {SYM1}":
                    # Sell SYM1 calls, Buy SYM2 calls
                    sell_label_calls = f"Sell {SYM1} Calls"
                    buy_label_calls = f"Buy {SYM2} Calls"
                    sell_strike_calls = spy_strike
                    buy_strike_calls = spx_strike
                    sell_price_calls = estimated_spy_call
                    buy_price_calls = estimated_spx_call
                    default_sell_qty = QTY_RATIO
                    default_buy_qty = 1
                else:  # f"Sell {SYM2}, Buy {SYM1}"
                    # Sell SYM2 calls, Buy SYM1 calls
                    sell_label_calls = f"Sell {SYM2} Calls"
                    buy_label_calls = f"Buy {SYM1} Calls"
                    sell_strike_calls = spx_strike
                    buy_strike_calls = spy_strike
                    sell_price_calls = estimated_spx_call
                    buy_price_calls = estimated_spy_call
                    default_sell_qty = 1
                    default_buy_qty = QTY_RATIO

                # Quantities
                sell_calls_qty = st.number_input(sell_label_calls, 1, 1000, default_sell_qty, key=f"sell_c_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}")
                buy_calls_qty = st.number_input(buy_label_calls, 1, 1000, default_buy_qty, key=f"buy_c_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}")

                # Prices (use estimated prices that update with slider, strikes, and direction)
                sell_call_price = st.number_input(
                    f"{sell_label_calls.replace('Calls', '')}@ ${sell_price_calls:.2f}",
                    0.0, 500.0, float(sell_price_calls), 0.01,
                    key=f"sell_c_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
                )

                buy_call_price = st.number_input(
                    f"{buy_label_calls.replace('Calls', '')}@ ${buy_price_calls:.2f}",
                    0.0, 500.0, float(buy_price_calls), 0.01,
                    key=f"buy_c_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
                )

                call_credit = (sell_call_price * sell_calls_qty * 100) - (buy_call_price * buy_calls_qty * 100)
                st.metric("Call Credit", f"${call_credit:,.2f}")

        # Put Spread Section
        if show_puts:
            with col2 if col2 else col1:
                st.subheader("📉 Put Spread")
                st.write(f"**Direction:** {best_combo['put_direction']}")
                st.caption(f"Database prices at {entry_time_label}")

                # Determine position labels based on direction
                if put_direction == f"Buy {SYM1}, Sell {SYM2}":
                    # Buy SYM1 puts, Sell SYM2 puts
                    sell_label_puts = f"Sell {SYM2} Puts"
                    buy_label_puts = f"Buy {SYM1} Puts"
                    sell_strike_puts = spx_strike
                    buy_strike_puts = spy_strike
                    sell_price_puts = estimated_spx_put
                    buy_price_puts = estimated_spy_put
                    default_sell_qty_puts = 1
                    default_buy_qty_puts = QTY_RATIO
                else:  # f"Sell {SYM1}, Buy {SYM2}"
                    # Sell SYM1 puts, Buy SYM2 puts
                    sell_label_puts = f"Sell {SYM1} Puts"
                    buy_label_puts = f"Buy {SYM2} Puts"
                    sell_strike_puts = spy_strike
                    buy_strike_puts = spx_strike
                    sell_price_puts = estimated_spy_put
                    buy_price_puts = estimated_spx_put
                    default_sell_qty_puts = QTY_RATIO
                    default_buy_qty_puts = 1

                # Quantities
                sell_puts_qty = st.number_input(sell_label_puts, 1, 1000, default_sell_qty_puts, key=f"sell_p_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}")
                buy_puts_qty = st.number_input(buy_label_puts, 1, 1000, default_buy_qty_puts, key=f"buy_p_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}")

                # Prices (use estimated prices that update with slider, strikes, and direction)
                sell_put_price = st.number_input(
                    f"{sell_label_puts.replace('Puts', '')}@ ${sell_price_puts:.2f}",
                    0.0, 500.0, float(sell_price_puts), 0.01,
                    key=f"sell_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"
                )

                buy_put_price = st.number_input(
                    f"{buy_label_puts.replace('Puts', '')}@ ${buy_price_puts:.2f}",
                    0.0, 500.0, float(buy_price_puts), 0.01,
                    key=f"buy_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"
                )

                put_credit = (sell_put_price * sell_puts_qty * 100) - (buy_put_price * buy_puts_qty * 100)
                st.metric("Put Credit", f"${put_credit:,.2f}")

        # Total credit
        total_credit = call_credit + put_credit
        if show_calls and show_puts:
            st.metric("**Total Net Credit**", f"**${total_credit:,.2f}**")
        elif show_calls:
            st.metric("**Call Credit (Total)**", f"**${call_credit:,.2f}**")
        else:  # show_puts
            st.metric("**Put Credit (Total)**", f"**${put_credit:,.2f}**")

        # Margin Requirements
        st.markdown("---")
        st.subheader("💳 Margin Requirements")
        st.caption("Estimated capital required to execute this strategy")

        # Calculate margin for each leg
        # For spreads, margin = max potential loss (width of spread × 100 × quantity)
        # For short options without defined risk, we use a more complex calculation

        call_margin = 0.0
        put_margin = 0.0

        if show_calls:
            # Call spread margin calculation
            # For SYM1/SYM2 spreads with different strikes and ratios, calculate max loss
            if call_direction == f"Buy {SYM2}, Sell {SYM1}":
                # Sold SYM1 calls, Bought SYM2 calls
                # Max loss: (sold qty × strike) - (bought qty × strike) when both ITM
                # Simplified: Short side notional value is the margin base
                call_margin = sell_calls_qty * spy_strike * 100 * 0.20  # 20% of notional for naked short
                # Reduce by credit received
                call_margin = max(0, call_margin - call_credit)
            else:  # f"Sell {SYM2}, Buy {SYM1}"
                # Sold SYM2 calls, Bought SYM1 calls
                call_margin = sell_calls_qty * spx_strike * 100 * 0.20
                call_margin = max(0, call_margin - call_credit)

        if show_puts:
            # Put spread margin calculation
            if put_direction == f"Buy {SYM1}, Sell {SYM2}":
                # Sold SYM2 puts, Bought SYM1 puts
                put_margin = sell_puts_qty * spx_strike * 100 * 0.20
                put_margin = max(0, put_margin - put_credit)
            else:  # f"Sell {SYM1}, Buy {SYM2}"
                # Sold SYM1 puts, Bought SYM2 puts
                put_margin = sell_puts_qty * spy_strike * 100 * 0.20
                put_margin = max(0, put_margin - put_credit)

        total_margin = call_margin + put_margin

        # Display margin requirements
        col1, col2, col3 = st.columns(3)

        with col1:
            if show_calls:
                st.metric("Call Margin", f"${call_margin:,.2f}",
                         help="Estimated margin for call spread (after credit)")

        with col2:
            if show_puts:
                st.metric("Put Margin", f"${put_margin:,.2f}",
                         help="Estimated margin for put spread (after credit)")

        with col3:
            st.metric("**Total Margin**", f"**${total_margin:,.2f}**",
                     help="Total estimated margin required")

        st.info(f"⚠️ **Note:** These are rough estimates. Actual margin requirements depend on your broker's policies, account type, and real-time portfolio margin calculations. {SYM2} options may have different margin treatment than {SYM1} options. Always verify margin requirements with your broker before trading.")

        with st.expander("📖 Margin Calculation Details"):
            st.write("**How margin is estimated:**")
            st.write("1. **Short Option Notional**: Strike price × Quantity × 100 × 20%")
            st.write("2. **Credit Offset**: Subtract premium received")
            st.write("3. **Long Option**: No additional margin (protective)")
            st.write("")
            st.write("**Broker-specific factors:**")
            st.write(f"- **{SYM2}**: May qualify for portfolio margin with lower requirements (especially if cash-settled index)")
            st.write(f"- **{SYM1}**: Standard option margin rules apply")
            st.write("- **Spreads**: Actual margin may be lower due to defined risk")
            st.write("- **Account type**: Portfolio margin accounts typically have 50-70% lower requirements")
            st.write("")
            st.write("**Best practice:** Check your broker's margin calculator or contact them directly for accurate requirements before entering the position.")

        # Scenario Analysis
        st.header("Scenario Analysis")

        # Get EOD prices
        eod_spy = spy_df.iloc[-1]['close']
        eod_spx = spx_df.iloc[-1]['close']

        st.info(f"**Market Close:** {SYM1} ${eod_spy:.2f}, {SYM2} ${eod_spx:.2f}")

        # Calculate settlement values
        spy_call_settle = calculate_settlement_value(eod_spy, spy_strike, 'C')
        spx_call_settle = calculate_settlement_value(eod_spx, spx_strike, 'C')
        spy_put_settle = calculate_settlement_value(eod_spy, spy_strike, 'P')
        spx_put_settle = calculate_settlement_value(eod_spx, spx_strike, 'P')

        # Calculate P&L based on selected strategy
        call_pnl = 0.0
        put_pnl = 0.0

        if show_calls:
            # Determine which settlement values to use based on direction
            if call_direction == f"Buy {SYM2}, Sell {SYM1}":
                # Sell SYM1 calls, Buy SYM2 calls
                call_pnl = calculate_option_pnl(sell_call_price, spy_call_settle, 'SELL', sell_calls_qty)
                call_pnl += calculate_option_pnl(buy_call_price, spx_call_settle, 'BUY', buy_calls_qty)
            else:  # f"Sell {SYM2}, Buy {SYM1}"
                # Sell SYM2 calls, Buy SYM1 calls
                call_pnl = calculate_option_pnl(sell_call_price, spx_call_settle, 'SELL', sell_calls_qty)
                call_pnl += calculate_option_pnl(buy_call_price, spy_call_settle, 'BUY', buy_calls_qty)

        if show_puts:
            # Determine which settlement values to use based on direction
            if put_direction == f"Buy {SYM1}, Sell {SYM2}":
                # Sell SYM2 puts, Buy SYM1 puts
                put_pnl = calculate_option_pnl(sell_put_price, spx_put_settle, 'SELL', sell_puts_qty)
                put_pnl += calculate_option_pnl(buy_put_price, spy_put_settle, 'BUY', buy_puts_qty)
            else:  # f"Sell {SYM1}, Buy {SYM2}"
                # Sell SYM1 puts, Buy SYM2 puts
                put_pnl = calculate_option_pnl(sell_put_price, spy_put_settle, 'SELL', sell_puts_qty)
                put_pnl += calculate_option_pnl(buy_put_price, spx_put_settle, 'BUY', buy_puts_qty)

        # Calculate total P&L INCLUDING initial credit collected
        total_pnl = call_credit + put_credit + call_pnl + put_pnl

        # Calculate settlement costs for display
        # Settlement cost represents what we OWE (always positive for cost)
        # Formula: (sold options payout) - (bought options receive)
        # If negative (we receive more than we pay), that's still a "cost" of zero for display
        call_settlement_cost = 0.0
        put_settlement_cost = 0.0

        if show_calls:
            if call_direction == f"Buy {SYM2}, Sell {SYM1}":
                # Sold SYM1 calls, Bought SYM2 calls
                call_settlement_cost = (spy_call_settle * sell_calls_qty * 100) - (spx_call_settle * buy_calls_qty * 100)
            else:
                # Sold SYM2 calls, Bought SYM1 calls
                call_settlement_cost = (spx_call_settle * sell_calls_qty * 100) - (spy_call_settle * buy_calls_qty * 100)

        if show_puts:
            if put_direction == f"Buy {SYM1}, Sell {SYM2}":
                # Sold SYM2 puts, Bought SYM1 puts
                put_settlement_cost = (spx_put_settle * sell_puts_qty * 100) - (spy_put_settle * buy_puts_qty * 100)
            else:
                # Sold SYM1 puts, Bought SYM2 puts
                put_settlement_cost = (spy_put_settle * sell_puts_qty * 100) - (spx_put_settle * buy_puts_qty * 100)

        # Total settlement cost (can be negative if we receive more than we pay)
        total_settlement_cost = call_settlement_cost + put_settlement_cost

        # Show P&L table with explicit cash flows
        if show_calls and show_puts:
            st.markdown("### Settlement Cash Flow")

            # Calculate net profit: Credit - Settlement Cost
            net_profit = total_credit - total_settlement_cost

            # Create settlement table
            # Display settlement cost with sign (positive = we owe, negative = we receive)
            settlement_data = {
                "": ["Credit Received", "Settlement Cost", "**Net Profit**"],
                "Amount": [
                    f"${total_credit:,.2f}",
                    f"${-total_settlement_cost:,.2f}",  # Negate for display (cost is negative of received)
                    f"**${net_profit:,.2f}**"
                ]
            }

            st.table(settlement_data)

            # Show breakdown by leg
            col1, col2 = st.columns(2)
            with col1:
                st.caption(f"**Call Leg:**")
                st.caption(f"  Credit: +${call_credit:,.2f}")
                st.caption(f"  Settlement: -${call_settlement_cost:,.2f}")
                st.caption(f"  Net: ${call_credit - call_settlement_cost:,.2f}")
            with col2:
                st.caption(f"**Put Leg:**")
                st.caption(f"  Credit: +${put_credit:,.2f}")
                st.caption(f"  Settlement: -${put_settlement_cost:,.2f}")
                st.caption(f"  Net: ${put_credit - put_settlement_cost:,.2f}")

            # Calculate best/worst case for JSON export (with basis drift)
            best_case_export, worst_case_export = calculate_best_worst_case_with_basis_drift(
                entry_spy_price=entry_spy['close'],
                entry_spx_price=entry_spx['close'],
                spy_strike=spy_strike,
                spx_strike=spx_strike,
                call_direction=call_direction,
                put_direction=put_direction,
                sell_call_price=sell_call_price,
                buy_call_price=buy_call_price,
                sell_calls_qty=sell_calls_qty,
                buy_calls_qty=buy_calls_qty,
                sell_put_price=sell_put_price,
                buy_put_price=buy_put_price,
                sell_puts_qty=sell_puts_qty,
                buy_puts_qty=buy_puts_qty,
                show_calls=show_calls,
                show_puts=show_puts,
                sym1=SYM1, sym2=SYM2,
            )

            # Export snapshot button
            st.markdown("---")
            snapshot_data = {
                "date": selected_date,
                "entry_time": entry_time_label,
                "strategy": {
                    "call_direction": call_direction,
                    "put_direction": put_direction,
                    "spy_strike": spy_strike,
                    "spx_strike": spx_strike
                },
                "entry_prices": {
                    "spy": float(entry_spy['close']),
                    "spx": float(entry_spx['close']),
                    "spy_call": float(sell_call_price) if call_direction == f"Buy {SYM2}, Sell {SYM1}" else float(buy_call_price),
                    "spx_call": float(buy_call_price) if call_direction == f"Buy {SYM2}, Sell {SYM1}" else float(sell_call_price),
                    "spy_put": float(buy_put_price) if put_direction == f"Buy {SYM1}, Sell {SYM2}" else float(sell_put_price),
                    "spx_put": float(sell_put_price) if put_direction == f"Buy {SYM1}, Sell {SYM2}" else float(buy_put_price)
                },
                "eod_prices": {
                    "spy": float(eod_spy),
                    "spx": float(eod_spx)
                },
                "positions": {
                    "calls": {
                        "sell_qty": int(sell_calls_qty),
                        "buy_qty": int(buy_calls_qty),
                        "sell_price": float(sell_call_price),
                        "buy_price": float(buy_call_price),
                        "sell_symbol": SYM1 if call_direction == f"Buy {SYM2}, Sell {SYM1}" else SYM2,
                        "buy_symbol": SYM2 if call_direction == f"Buy {SYM2}, Sell {SYM1}" else SYM1
                    },
                    "puts": {
                        "sell_qty": int(sell_puts_qty),
                        "buy_qty": int(buy_puts_qty),
                        "sell_price": float(sell_put_price),
                        "buy_price": float(buy_put_price),
                        "sell_symbol": SYM2 if put_direction == f"Buy {SYM1}, Sell {SYM2}" else SYM1,
                        "buy_symbol": SYM1 if put_direction == f"Buy {SYM1}, Sell {SYM2}" else SYM2
                    }
                },
                "settlement": {
                    "spy_call_settle": float(spy_call_settle),
                    "spx_call_settle": float(spx_call_settle),
                    "spy_put_settle": float(spy_put_settle),
                    "spx_put_settle": float(spx_put_settle)
                },
                "pnl": {
                    "call_credit": float(call_credit),
                    "put_credit": float(put_credit),
                    "total_credit": float(total_credit),
                    "call_settlement_cost": float(call_settlement_cost),
                    "put_settlement_cost": float(put_settlement_cost),
                    "total_settlement_cost": float(total_settlement_cost),
                    "net_profit": float(net_profit),
                    "call_pnl": float(call_pnl),
                    "put_pnl": float(put_pnl)
                },
                "best_worst_case_analysis": {
                    "includes_basis_drift": True,
                    "basis_drift_range_pct": 0.05,
                    "best_case": {
                        "net_pnl": float(best_case_export['net_pnl']),
                        "spy_price": float(best_case_export['spy_price']),
                        "spx_price": float(best_case_export['spx_price']),
                        "basis_drift_pct": float(best_case_export.get('basis_drift', 0)),
                        "pct_move_from_entry": float(((best_case_export['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100)
                    },
                    "worst_case": {
                        "net_pnl": float(worst_case_export['net_pnl']),
                        "spy_price": float(worst_case_export['spy_price']),
                        "spx_price": float(worst_case_export['spx_price']),
                        "basis_drift_pct": float(worst_case_export.get('basis_drift', 0)),
                        "pct_move_from_entry": float(((worst_case_export['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100)
                    },
                    "pnl_range": float(best_case_export['net_pnl'] - worst_case_export['net_pnl']),
                    "risk_reward_ratio": float(abs(best_case_export['net_pnl']) / abs(worst_case_export['net_pnl'])) if worst_case_export['net_pnl'] != 0 else None,
                    "actual_outcome": {
                        "pct_of_best_case": float((net_profit / best_case_export['net_pnl'] * 100)) if best_case_export['net_pnl'] != 0 else 0,
                        "pct_of_worst_case": float((net_profit / worst_case_export['net_pnl'] * 100)) if worst_case_export['net_pnl'] != 0 else 0
                    }
                }
            }

            snapshot_json = json.dumps(snapshot_data, indent=2)
            st.download_button(
                label="📋 Export Snapshot (JSON)",
                data=snapshot_json,
                file_name=f"strategy_snapshot_{selected_date}_{entry_time_label.replace(' ', '_').replace(':', '')}.json",
                mime="application/json",
                help="Download all position details, prices, and calculations as JSON for analysis"
            )
        elif show_calls:
            # net_profit = credit - settlement_cost (correct P&L calculation)
            net_profit = call_credit - call_settlement_cost
            st.metric("**Call P&L (Total)**", f"**${net_profit:,.2f}**")
            st.caption(f"Initial Credit: +${call_credit:,.2f} | Settlement Cost: ${-call_settlement_cost:+,.2f}")

            # Calculate best/worst case for JSON export (Calls Only, with basis drift)
            best_case_export, worst_case_export = calculate_best_worst_case_with_basis_drift(
                entry_spy_price=entry_spy['close'],
                entry_spx_price=entry_spx['close'],
                spy_strike=spy_strike,
                spx_strike=spx_strike,
                call_direction=call_direction,
                put_direction=put_direction,
                sell_call_price=sell_call_price,
                buy_call_price=buy_call_price,
                sell_calls_qty=sell_calls_qty,
                buy_calls_qty=buy_calls_qty,
                sell_put_price=0,
                buy_put_price=0,
                sell_puts_qty=0,
                buy_puts_qty=0,
                show_calls=True,
                show_puts=False,
                sym1=SYM1, sym2=SYM2,
            )

            # Export snapshot button for Calls Only
            st.markdown("---")
            snapshot_data = {
                "date": selected_date,
                "entry_time": entry_time_label,
                "strategy_type": "Calls Only",
                "strategy": {
                    "call_direction": call_direction,
                    "spy_strike": spy_strike,
                    "spx_strike": spx_strike
                },
                "entry_prices": {
                    "spy": float(entry_spy['close']),
                    "spx": float(entry_spx['close']),
                    "spy_call": float(sell_call_price) if call_direction == f"Buy {SYM2}, Sell {SYM1}" else float(buy_call_price),
                    "spx_call": float(buy_call_price) if call_direction == f"Buy {SYM2}, Sell {SYM1}" else float(sell_call_price)
                },
                "eod_prices": {
                    "spy": float(eod_spy),
                    "spx": float(eod_spx)
                },
                "positions": {
                    "calls": {
                        "sell_qty": int(sell_calls_qty),
                        "buy_qty": int(buy_calls_qty),
                        "sell_price": float(sell_call_price),
                        "buy_price": float(buy_call_price),
                        "sell_symbol": SYM1 if call_direction == f"Buy {SYM2}, Sell {SYM1}" else SYM2,
                        "buy_symbol": SYM2 if call_direction == f"Buy {SYM2}, Sell {SYM1}" else SYM1
                    }
                },
                "settlement": {
                    "spy_call_settle": float(spy_call_settle),
                    "spx_call_settle": float(spx_call_settle)
                },
                "pnl": {
                    "call_credit": float(call_credit),
                    "total_credit": float(call_credit),
                    "call_settlement_cost": float(call_settlement_cost),
                    "total_settlement_cost": float(call_settlement_cost),
                    "net_profit": float(net_profit),
                    "call_pnl": float(call_pnl)
                },
                "best_worst_case_analysis": {
                    "includes_basis_drift": True,
                    "basis_drift_range_pct": 0.05,
                    "best_case": {
                        "net_pnl": float(best_case_export['net_pnl']),
                        "spy_price": float(best_case_export['spy_price']),
                        "spx_price": float(best_case_export['spx_price']),
                        "basis_drift_pct": float(best_case_export.get('basis_drift', 0)),
                        "pct_move_from_entry": float(((best_case_export['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100)
                    },
                    "worst_case": {
                        "net_pnl": float(worst_case_export['net_pnl']),
                        "spy_price": float(worst_case_export['spy_price']),
                        "spx_price": float(worst_case_export['spx_price']),
                        "basis_drift_pct": float(worst_case_export.get('basis_drift', 0)),
                        "pct_move_from_entry": float(((worst_case_export['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100)
                    },
                    "pnl_range": float(best_case_export['net_pnl'] - worst_case_export['net_pnl']),
                    "risk_reward_ratio": float(abs(best_case_export['net_pnl']) / abs(worst_case_export['net_pnl'])) if worst_case_export['net_pnl'] != 0 else None,
                    "actual_outcome": {
                        "pct_of_best_case": float((net_profit / best_case_export['net_pnl'] * 100)) if best_case_export['net_pnl'] != 0 else 0,
                        "pct_of_worst_case": float((net_profit / worst_case_export['net_pnl'] * 100)) if worst_case_export['net_pnl'] != 0 else 0
                    }
                }
            }

            snapshot_json = json.dumps(snapshot_data, indent=2)
            st.download_button(
                label="📋 Export Snapshot (JSON)",
                data=snapshot_json,
                file_name=f"strategy_snapshot_calls_{selected_date}_{entry_time_label.replace(' ', '_').replace(':', '')}.json",
                mime="application/json",
                help="Download all position details, prices, and calculations as JSON for analysis"
            )
        else:  # show_puts
            # net_profit = credit - settlement_cost (correct P&L calculation)
            net_profit = put_credit - put_settlement_cost
            st.metric("**Put P&L (Total)**", f"**${net_profit:,.2f}**")
            st.caption(f"Initial Credit: +${put_credit:,.2f} | Settlement Cost: ${-put_settlement_cost:+,.2f}")

            # Calculate best/worst case for JSON export (Puts Only, with basis drift)
            best_case_export, worst_case_export = calculate_best_worst_case_with_basis_drift(
                entry_spy_price=entry_spy['close'],
                entry_spx_price=entry_spx['close'],
                spy_strike=spy_strike,
                spx_strike=spx_strike,
                call_direction=call_direction,
                put_direction=put_direction,
                sell_call_price=0,
                buy_call_price=0,
                sell_calls_qty=0,
                buy_calls_qty=0,
                sell_put_price=sell_put_price,
                buy_put_price=buy_put_price,
                sell_puts_qty=sell_puts_qty,
                buy_puts_qty=buy_puts_qty,
                show_calls=False,
                show_puts=True,
                sym1=SYM1, sym2=SYM2,
            )

            # Export snapshot button for Puts Only
            st.markdown("---")
            snapshot_data = {
                "date": selected_date,
                "entry_time": entry_time_label,
                "strategy_type": "Puts Only",
                "strategy": {
                    "put_direction": put_direction,
                    "spy_strike": spy_strike,
                    "spx_strike": spx_strike
                },
                "entry_prices": {
                    "spy": float(entry_spy['close']),
                    "spx": float(entry_spx['close']),
                    "spy_put": float(buy_put_price) if put_direction == f"Buy {SYM1}, Sell {SYM2}" else float(sell_put_price),
                    "spx_put": float(sell_put_price) if put_direction == f"Buy {SYM1}, Sell {SYM2}" else float(buy_put_price)
                },
                "eod_prices": {
                    "spy": float(eod_spy),
                    "spx": float(eod_spx)
                },
                "positions": {
                    "puts": {
                        "sell_qty": int(sell_puts_qty),
                        "buy_qty": int(buy_puts_qty),
                        "sell_price": float(sell_put_price),
                        "buy_price": float(buy_put_price),
                        "sell_symbol": SYM2 if put_direction == f"Buy {SYM1}, Sell {SYM2}" else SYM1,
                        "buy_symbol": SYM1 if put_direction == f"Buy {SYM1}, Sell {SYM2}" else SYM2
                    }
                },
                "settlement": {
                    "spy_put_settle": float(spy_put_settle),
                    "spx_put_settle": float(spx_put_settle)
                },
                "pnl": {
                    "put_credit": float(put_credit),
                    "total_credit": float(put_credit),
                    "put_settlement_cost": float(put_settlement_cost),
                    "total_settlement_cost": float(put_settlement_cost),
                    "net_profit": float(net_profit),
                    "put_pnl": float(put_pnl)
                },
                "best_worst_case_analysis": {
                    "includes_basis_drift": True,
                    "basis_drift_range_pct": 0.05,
                    "best_case": {
                        "net_pnl": float(best_case_export['net_pnl']),
                        "spy_price": float(best_case_export['spy_price']),
                        "spx_price": float(best_case_export['spx_price']),
                        "basis_drift_pct": float(best_case_export.get('basis_drift', 0)),
                        "pct_move_from_entry": float(((best_case_export['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100)
                    },
                    "worst_case": {
                        "net_pnl": float(worst_case_export['net_pnl']),
                        "spy_price": float(worst_case_export['spy_price']),
                        "spx_price": float(worst_case_export['spx_price']),
                        "basis_drift_pct": float(worst_case_export.get('basis_drift', 0)),
                        "pct_move_from_entry": float(((worst_case_export['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100)
                    },
                    "pnl_range": float(best_case_export['net_pnl'] - worst_case_export['net_pnl']),
                    "risk_reward_ratio": float(abs(best_case_export['net_pnl']) / abs(worst_case_export['net_pnl'])) if worst_case_export['net_pnl'] != 0 else None,
                    "actual_outcome": {
                        "pct_of_best_case": float((net_profit / best_case_export['net_pnl'] * 100)) if best_case_export['net_pnl'] != 0 else 0,
                        "pct_of_worst_case": float((net_profit / worst_case_export['net_pnl'] * 100)) if worst_case_export['net_pnl'] != 0 else 0
                    }
                }
            }

            snapshot_json = json.dumps(snapshot_data, indent=2)
            st.download_button(
                label="📋 Export Snapshot (JSON)",
                data=snapshot_json,
                file_name=f"strategy_snapshot_puts_{selected_date}_{entry_time_label.replace(' ', '_').replace(':', '')}.json",
                mime="application/json",
                help="Download all position details, prices, and calculations as JSON for analysis"
            )

        # Detailed breakdown
        with st.expander("📋 Detailed Breakdown"):
            if show_calls:
                st.write("**Calls:**")
                if call_direction == f"Buy {SYM2}, Sell {SYM1}":
                    st.write(f"- Sell {sell_calls_qty} {SYM1} {spy_strike}C @ ${sell_call_price:.2f} → Settle @ ${spy_call_settle:.2f}")
                    st.write(f"- Buy {buy_calls_qty} {SYM2} {spx_strike}C @ ${buy_call_price:.2f} → Settle @ ${spx_call_settle:.2f}")
                else:
                    st.write(f"- Sell {sell_calls_qty} {SYM2} {spx_strike}C @ ${sell_call_price:.2f} → Settle @ ${spx_call_settle:.2f}")
                    st.write(f"- Buy {buy_calls_qty} {SYM1} {spy_strike}C @ ${buy_call_price:.2f} → Settle @ ${spy_call_settle:.2f}")
                st.write(f"- Net: ${call_pnl:,.2f}")

            if show_puts:
                if show_calls:
                    st.write("")  # Add spacing
                st.write("**Puts:**")
                if put_direction == f"Buy {SYM1}, Sell {SYM2}":
                    st.write(f"- Sell {sell_puts_qty} {SYM2} {spx_strike}P @ ${sell_put_price:.2f} → Settle @ ${spx_put_settle:.2f}")
                    st.write(f"- Buy {buy_puts_qty} {SYM1} {spy_strike}P @ ${buy_put_price:.2f} → Settle @ ${spy_put_settle:.2f}")
                else:
                    st.write(f"- Sell {sell_puts_qty} {SYM1} {spy_strike}P @ ${sell_put_price:.2f} → Settle @ ${spy_put_settle:.2f}")
                    st.write(f"- Buy {buy_puts_qty} {SYM2} {spx_strike}P @ ${buy_put_price:.2f} → Settle @ ${spx_put_settle:.2f}")
                st.write(f"- Net: ${put_pnl:,.2f}")

        # Best/Worst Case Analysis
        st.markdown("---")
        st.header("📊 Best & Worst Case Analysis")

        # Calculate best and worst case scenarios at settlement
        # Includes ±0.05% basis drift to account for SYM1/SYM2 ratio changes
        best_case, worst_case = calculate_best_worst_case_with_basis_drift(
            entry_spy_price=entry_spy['close'],
            entry_spx_price=entry_spx['close'],
            spy_strike=spy_strike,
            spx_strike=spx_strike,
            call_direction=call_direction,
            put_direction=put_direction,
            sell_call_price=sell_call_price if show_calls else 0,
            buy_call_price=buy_call_price if show_calls else 0,
            sell_calls_qty=sell_calls_qty if show_calls else 0,
            buy_calls_qty=buy_calls_qty if show_calls else 0,
            sell_put_price=sell_put_price if show_puts else 0,
            buy_put_price=buy_put_price if show_puts else 0,
            sell_puts_qty=sell_puts_qty if show_puts else 0,
            buy_puts_qty=buy_puts_qty if show_puts else 0,
            show_calls=show_calls,
            show_puts=show_puts,
            sym1=SYM1, sym2=SYM2,
        )

        # Display results
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### ✅ Best Case Scenario")
            st.metric("Maximum Profit", f"${best_case['net_pnl']:,.2f}",
                     help="Best possible outcome at settlement")
            st.caption(f"**Occurs at:**")
            st.caption(f"  {SYM1}: ${best_case['spy_price']:.2f}")
            st.caption(f"  {SYM2}: ${best_case['spx_price']:.2f}")

            pct_move = ((best_case['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100
            direction = "rises" if pct_move > 0 else "falls"
            st.caption(f"  Market {direction} {abs(pct_move):.1f}% from entry")

            # Detailed breakdown
            if 'breakdown' in best_case:
                bd = best_case['breakdown']
                with st.expander("Show P&L breakdown"):
                    st.markdown("**Credit Received (at entry)**")
                    if show_calls:
                        sell_c_total = bd['sell_call_price'] * bd['sell_calls_qty'] * 100
                        buy_c_total = bd['buy_call_price'] * bd['buy_calls_qty'] * 100
                        st.caption(f"  Sell {bd['sell_call_symbol']} {bd['spy_strike'] if bd['sell_call_symbol']==SYM1 else bd['spx_strike']}C × {bd['sell_calls_qty']}: (${bd['sell_call_price']:.2f} × {bd['sell_calls_qty']} × 100) = +${sell_c_total:,.2f}")
                        st.caption(f"  Buy {bd['buy_call_symbol']} {bd['spx_strike'] if bd['buy_call_symbol']==SYM2 else bd['spy_strike']}C × {bd['buy_calls_qty']}: (${bd['buy_call_price']:.2f} × {bd['buy_calls_qty']} × 100) = -${buy_c_total:,.2f}")
                    if show_puts:
                        sell_p_total = bd['sell_put_price'] * bd['sell_puts_qty'] * 100
                        buy_p_total = bd['buy_put_price'] * bd['buy_puts_qty'] * 100
                        st.caption(f"  Sell {bd['sell_put_symbol']} {bd['spy_strike'] if bd['sell_put_symbol']==SYM1 else bd['spx_strike']}P × {bd['sell_puts_qty']}: (${bd['sell_put_price']:.2f} × {bd['sell_puts_qty']} × 100) = +${sell_p_total:,.2f}")
                        st.caption(f"  Buy {bd['buy_put_symbol']} {bd['spx_strike'] if bd['buy_put_symbol']==SYM2 else bd['spy_strike']}P × {bd['buy_puts_qty']}: (${bd['buy_put_price']:.2f} × {bd['buy_puts_qty']} × 100) = -${buy_p_total:,.2f}")
                    st.caption(f"  **Total credit: +${bd['total_credit']:,.2f}**")

                    st.markdown("**Settlement (at expiry)**")
                    if show_calls:
                        sell_c_settle_total = bd['sell_call_settle'] * bd['sell_calls_qty'] * 100
                        buy_c_settle_total = bd['buy_call_settle'] * bd['buy_calls_qty'] * 100
                        sell_c_label = "we owe" if bd['sell_call_settle'] > 0 else "expires OTM"
                        buy_c_label = "we receive" if bd['buy_call_settle'] > 0 else "expires OTM"
                        st.caption(f"  {bd['sell_call_symbol']} {bd['spy_strike'] if bd['sell_call_symbol']==SYM1 else bd['spx_strike']}C settle: ${bd['sell_call_settle']:.2f} ({sell_c_label}) → -${sell_c_settle_total:,.2f}")
                        st.caption(f"  {bd['buy_call_symbol']} {bd['spx_strike'] if bd['buy_call_symbol']==SYM2 else bd['spy_strike']}C settle: ${bd['buy_call_settle']:.2f} ({buy_c_label}) → +${buy_c_settle_total:,.2f}")
                    if show_puts:
                        sell_p_settle_total = bd['sell_put_settle'] * bd['sell_puts_qty'] * 100
                        buy_p_settle_total = bd['buy_put_settle'] * bd['buy_puts_qty'] * 100
                        sell_p_label = "we owe" if bd['sell_put_settle'] > 0 else "expires OTM"
                        buy_p_label = "we receive" if bd['buy_put_settle'] > 0 else "expires OTM"
                        st.caption(f"  {bd['sell_put_symbol']} {bd['spy_strike'] if bd['sell_put_symbol']==SYM1 else bd['spx_strike']}P settle: ${bd['sell_put_settle']:.2f} ({sell_p_label}) → -${sell_p_settle_total:,.2f}")
                        st.caption(f"  {bd['buy_put_symbol']} {bd['spx_strike'] if bd['buy_put_symbol']==SYM2 else bd['spy_strike']}P settle: ${bd['buy_put_settle']:.2f} ({buy_p_label}) → +${buy_p_settle_total:,.2f}")
                    net_settle = -bd['total_settlement_cost']
                    settle_sign = "+" if net_settle >= 0 else "-"
                    st.caption(f"  **Net settlement: {settle_sign}${abs(net_settle):,.2f}**")

                    st.markdown("---")
                    if net_settle >= 0:
                        st.markdown(f"**Net P&L = ${bd['total_credit']:,.2f} credit + ${net_settle:,.2f} settlement = ${best_case['net_pnl']:,.2f}**")
                    else:
                        st.markdown(f"**Net P&L = ${bd['total_credit']:,.2f} credit - ${abs(net_settle):,.2f} settlement = ${best_case['net_pnl']:,.2f}**")

        with col2:
            if worst_case['net_pnl'] >= 0:
                st.markdown("### ✅ Worst Case Scenario")
                st.metric("Worst Case P&L", f"+${worst_case['net_pnl']:,.2f}",
                         help="Worst possible outcome at settlement (still a profit!)")
            else:
                st.markdown("### ❌ Worst Case Scenario")
                st.metric("Worst Case P&L", f"-${abs(worst_case['net_pnl']):,.2f}",
                         help="Worst possible outcome at settlement (a loss)")
            st.caption(f"**Occurs at:**")
            st.caption(f"  {SYM1}: ${worst_case['spy_price']:.2f}")
            st.caption(f"  {SYM2}: ${worst_case['spx_price']:.2f}")

            pct_move = ((worst_case['spy_price'] - entry_spy['close']) / entry_spy['close']) * 100
            direction = "rises" if pct_move > 0 else "falls"
            st.caption(f"  Market {direction} {abs(pct_move):.1f}% from entry")

            # Detailed breakdown
            if 'breakdown' in worst_case:
                bd = worst_case['breakdown']
                with st.expander("Show P&L breakdown"):
                    st.markdown("**Credit Received (at entry)**")
                    if show_calls:
                        sell_c_total = bd['sell_call_price'] * bd['sell_calls_qty'] * 100
                        buy_c_total = bd['buy_call_price'] * bd['buy_calls_qty'] * 100
                        st.caption(f"  Sell {bd['sell_call_symbol']} {bd['spy_strike'] if bd['sell_call_symbol']==SYM1 else bd['spx_strike']}C × {bd['sell_calls_qty']}: (${bd['sell_call_price']:.2f} × {bd['sell_calls_qty']} × 100) = +${sell_c_total:,.2f}")
                        st.caption(f"  Buy {bd['buy_call_symbol']} {bd['spx_strike'] if bd['buy_call_symbol']==SYM2 else bd['spy_strike']}C × {bd['buy_calls_qty']}: (${bd['buy_call_price']:.2f} × {bd['buy_calls_qty']} × 100) = -${buy_c_total:,.2f}")
                    if show_puts:
                        sell_p_total = bd['sell_put_price'] * bd['sell_puts_qty'] * 100
                        buy_p_total = bd['buy_put_price'] * bd['buy_puts_qty'] * 100
                        st.caption(f"  Sell {bd['sell_put_symbol']} {bd['spy_strike'] if bd['sell_put_symbol']==SYM1 else bd['spx_strike']}P × {bd['sell_puts_qty']}: (${bd['sell_put_price']:.2f} × {bd['sell_puts_qty']} × 100) = +${sell_p_total:,.2f}")
                        st.caption(f"  Buy {bd['buy_put_symbol']} {bd['spx_strike'] if bd['buy_put_symbol']==SYM2 else bd['spy_strike']}P × {bd['buy_puts_qty']}: (${bd['buy_put_price']:.2f} × {bd['buy_puts_qty']} × 100) = -${buy_p_total:,.2f}")
                    st.caption(f"  **Total credit: +${bd['total_credit']:,.2f}**")

                    st.markdown("**Settlement (at expiry)**")
                    if show_calls:
                        sell_c_settle_total = bd['sell_call_settle'] * bd['sell_calls_qty'] * 100
                        buy_c_settle_total = bd['buy_call_settle'] * bd['buy_calls_qty'] * 100
                        sell_c_label = "we owe" if bd['sell_call_settle'] > 0 else "expires OTM"
                        buy_c_label = "we receive" if bd['buy_call_settle'] > 0 else "expires OTM"
                        st.caption(f"  {bd['sell_call_symbol']} {bd['spy_strike'] if bd['sell_call_symbol']==SYM1 else bd['spx_strike']}C settle: ${bd['sell_call_settle']:.2f} ({sell_c_label}) → -${sell_c_settle_total:,.2f}")
                        st.caption(f"  {bd['buy_call_symbol']} {bd['spx_strike'] if bd['buy_call_symbol']==SYM2 else bd['spy_strike']}C settle: ${bd['buy_call_settle']:.2f} ({buy_c_label}) → +${buy_c_settle_total:,.2f}")
                    if show_puts:
                        sell_p_settle_total = bd['sell_put_settle'] * bd['sell_puts_qty'] * 100
                        buy_p_settle_total = bd['buy_put_settle'] * bd['buy_puts_qty'] * 100
                        sell_p_label = "we owe" if bd['sell_put_settle'] > 0 else "expires OTM"
                        buy_p_label = "we receive" if bd['buy_put_settle'] > 0 else "expires OTM"
                        st.caption(f"  {bd['sell_put_symbol']} {bd['spy_strike'] if bd['sell_put_symbol']==SYM1 else bd['spx_strike']}P settle: ${bd['sell_put_settle']:.2f} ({sell_p_label}) → -${sell_p_settle_total:,.2f}")
                        st.caption(f"  {bd['buy_put_symbol']} {bd['spx_strike'] if bd['buy_put_symbol']==SYM2 else bd['spy_strike']}P settle: ${bd['buy_put_settle']:.2f} ({buy_p_label}) → +${buy_p_settle_total:,.2f}")
                    net_settle = -bd['total_settlement_cost']
                    settle_sign = "+" if net_settle >= 0 else "-"
                    st.caption(f"  **Net settlement: {settle_sign}${abs(net_settle):,.2f}**")

                    st.markdown("---")
                    if net_settle >= 0:
                        st.markdown(f"**Net P&L = ${bd['total_credit']:,.2f} credit + ${net_settle:,.2f} settlement = ${worst_case['net_pnl']:,.2f}**")
                    else:
                        st.markdown(f"**Net P&L = ${bd['total_credit']:,.2f} credit - ${abs(net_settle):,.2f} settlement = ${worst_case['net_pnl']:,.2f}**")

        # Risk/Reward Summary
        st.markdown("---")
        risk_reward_ratio = abs(best_case['net_pnl']) / abs(worst_case['net_pnl']) if worst_case['net_pnl'] != 0 else float('inf')

        col1, col2, col3 = st.columns(3)
        with col1:
            total_credit_collected = (call_credit if show_calls else 0) + (put_credit if show_puts else 0)
            st.metric("Total Credit", f"${total_credit_collected:,.2f}",
                     help="Premium collected upfront")
        with col2:
            pnl_range = best_case['net_pnl'] - worst_case['net_pnl']
            st.metric("P&L Range", f"${pnl_range:,.2f}",
                     help="Difference between best and worst case")
        with col3:
            if risk_reward_ratio != float('inf'):
                st.metric("Risk/Reward", f"{risk_reward_ratio:.2f}",
                         help="Ratio of potential profit to potential loss")
            else:
                st.metric("Risk/Reward", "∞ (No loss scenario)",
                         help="Best case exists with no worst case loss")

        # Overall assessment
        if worst_case['net_pnl'] >= 0:
            st.success(f"✅ **Strategy is profitable in all scenarios** within ±5% price range")
        elif best_case['net_pnl'] > 0:
            st.warning(f"⚠️ **Mixed outcomes:** Potential profit of ${best_case['net_pnl']:,.2f} or loss of ${abs(worst_case['net_pnl']):,.2f}")
        else:
            st.error(f"❌ **Strategy has losses in all scenarios** within ±5% range")

        # Actual outcome comparison
        st.markdown("---")
        st.markdown("### 📍 Actual Outcome at Market Close")
        st.info(f"**{SYM1} closed at ${eod_spy:.2f}, {SYM2} at ${eod_spx:.2f}**")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Actual Net P&L", f"${net_profit:,.2f}")
        with col2:
            pct_of_best = (net_profit / best_case['net_pnl'] * 100) if best_case['net_pnl'] != 0 else 0
            st.metric("% of Best Case", f"{pct_of_best:.1f}%")
        with col3:
            pct_of_worst = (net_profit / worst_case['net_pnl'] * 100) if worst_case['net_pnl'] != 0 else 0
            st.metric("% of Worst Case", f"{pct_of_worst:.1f}%")

        # Footer
        st.markdown("---")
        st.caption(f"**Analysis:** Best/worst case calculated across ±5% price range with ±0.05% basis drift ({SYM1}/{SYM2} ratio change)")
    
    # Tab 2: Live Paper Trading
with tab2:
    st.markdown("**Real-time positions** from IB Gateway paper trading account")

    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    with col2:
        from datetime import datetime as dt
        st.caption(f"Last updated: {dt.now().strftime('%I:%M:%S %p ET')}")

    try:
        # Connect to IB Gateway
        client = IBKRClient(port=4002, client_id=998)

        if not client.connect():
            st.error("❌ Failed to connect to IB Gateway")
            st.info("Make sure IB Gateway is running on port 4002 (Paper Trading)")
        else:
            # Get account summary
            account = client.get_account_summary()

            st.subheader("💰 Account Summary")
            col1, col2, col3 = st.columns(3)
            col1.metric("Net Liquidation", f"${account.get('net_liquidation', 0):,.2f}")
            col2.metric("Available Funds", f"${account.get('available_funds', 0):,.2f}")
            col3.metric("Buying Power", f"${account.get('buying_power', 0):,.2f}")

            # Get current underlying prices FIRST (before anything else)
            # These will be reused by all P&L calculations
            spy_price = client.get_current_price(SYM1)
            spx_price = client.get_current_price(SYM2)

            # Get current positions
            positions = client.get_positions()

            if not positions:
                st.info("No open positions")
            else:
                st.subheader("📊 Current Positions")

                # Separate option and stock positions
                option_positions = [p for p in positions if p['sec_type'] == 'OPT']
                stock_positions = [p for p in positions if p['sec_type'] == 'STK']

                # Display option positions
                if option_positions:
                    st.write("**Options:**")

                    # Create position table
                    position_data = []
                    for pos in option_positions:
                        contract = pos['contract']
                        position_data.append({
                            'Symbol': contract.symbol,
                            'Strike': contract.strike,
                            'Right': contract.right,
                            'Expiry': contract.lastTradeDateOrContractMonth,
                            'Position': int(pos.get('position', 0)),
                            'Avg Cost': f"${pos.get('avg_cost', 0):.2f}",
                            'Market Price': f"${pos.get('market_price', 0):.2f}" if pos.get('market_price') else 'N/A',
                            'Market Value': f"${pos.get('market_value', 0):,.2f}" if pos.get('market_value') else 'N/A',
                            'Unrealized P&L': f"${pos.get('unrealized_pnl', 0):,.2f}" if pos.get('unrealized_pnl') is not None else 'N/A'
                        })

                    df_positions = pd.DataFrame(position_data)
                    st.dataframe(df_positions, use_container_width=True, hide_index=True)

                    # Position Management - Close Positions
                    st.markdown("---")
                    st.subheader("⚙️ Position Management")
                    st.caption("Close individual positions manually")

                    # Create a form for closing positions
                    with st.expander("🔴 Close Positions"):
                        for i, pos in enumerate(option_positions):
                            contract = pos['contract']
                            position_size = pos.get('position', 0)

                            col1, col2, col3 = st.columns([3, 1, 1])

                            with col1:
                                st.write(f"**{contract.symbol} {contract.strike}{contract.right}**")
                                st.caption(f"Current position: {int(position_size):+d} contracts")

                            with col2:
                                # Input for quantity to close
                                max_close = int(abs(position_size))
                                qty_to_close = st.number_input(
                                    "Qty",
                                    min_value=1,
                                    max_value=max_close,
                                    value=max_close,
                                    step=1,
                                    key=f"close_qty_{i}_{contract.symbol}_{contract.strike}_{contract.right}",
                                    label_visibility="collapsed"
                                )

                            with col3:
                                # Close button
                                if st.button("Close", key=f"close_btn_{i}_{contract.symbol}_{contract.strike}_{contract.right}", type="primary"):
                                    try:
                                        # Determine action (opposite of current position)
                                        action = 'BUY' if position_size < 0 else 'SELL'

                                        st.info(f"Closing {qty_to_close} {contract.symbol} {contract.strike}{contract.right}...")

                                        # Place closing order
                                        trade = client.place_option_order(
                                            contract=contract,
                                            action=action,
                                            quantity=qty_to_close,
                                            order_type='MKT'
                                        )

                                        if trade and trade.orderStatus.status in ['Filled', 'PreSubmitted', 'Submitted']:
                                            st.success(f"✅ Order placed: {trade.orderStatus.status}")
                                            st.info("Refresh the page to see updated positions")
                                        else:
                                            st.error(f"❌ Order failed: {trade.orderStatus.status if trade else 'No trade'}")

                                    except Exception as e:
                                        st.error(f"❌ Error closing position: {e}")

                            st.markdown("---")

                    # Calculate estimated current P&L based on live quotes
                    st.subheader("💵 Estimated Current P&L")
                    st.caption("Based on current market bid/ask prices")

                    estimated_pnl = 0.0
                    pnl_breakdown = []

                    try:
                        from ib_insync import Option

                        # Fetch ALL quotes at once (parallel) - much faster!
                        tickers = {}
                        for pos in option_positions:
                            contract = pos['contract']
                            client.ib.qualifyContracts(contract)
                            ticker = client.ib.reqMktData(contract)
                            tickers[contract] = ticker

                        # Single wait for all quotes
                        client.ib.sleep(1)  # Reduced from 2 to 1 second

                        # Process all positions
                        # (spy_price and spx_price already fetched at start of tab2)
                        for pos in option_positions:
                            contract = pos['contract']
                            position_size = pos.get('position', 0)
                            avg_cost = pos.get('avg_cost', 0)  # This is already total cost per contract (price * 100)

                            ticker = tickers[contract]

                            if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
                                # Convert avg_cost from "per contract" to "per share" for comparison
                                avg_cost_per_share = avg_cost / 100

                                # Calculate P&L
                                # ticker.bid and ticker.ask are already per-share prices
                                if position_size < 0:  # SHORT position
                                    # To close: BUY at ask price
                                    # P&L = (Entry - Exit) * Quantity * 100
                                    pnl = (avg_cost_per_share - ticker.ask) * abs(position_size) * 100
                                else:  # LONG position
                                    # To close: SELL at bid price
                                    # P&L = (Exit - Entry) * Quantity * 100
                                    pnl = (ticker.bid - avg_cost_per_share) * position_size * 100

                                estimated_pnl += pnl

                                pnl_breakdown.append({
                                    'Contract': f"{contract.symbol} {contract.strike}{contract.right}",
                                    'Position': position_size,
                                    'Entry': f"${avg_cost_per_share:.2f}",  # Show per-share price
                                    'Current Bid': f"${ticker.bid:.2f}",
                                    'Current Ask': f"${ticker.ask:.2f}",
                                    'Est. P&L': f"${pnl:,.2f}"
                                })

                                # Cancel market data
                                client.ib.cancelMktData(contract)
                            else:
                                # Convert avg_cost from "per contract" to "per share" for display
                                avg_cost_per_share = avg_cost / 100

                                pnl_breakdown.append({
                                    'Contract': f"{contract.symbol} {contract.strike}{contract.right}",
                                    'Position': position_size,
                                    'Entry': f"${avg_cost_per_share:.2f}",
                                    'Current Bid': 'N/A',
                                    'Current Ask': 'N/A',
                                    'Est. P&L': 'N/A'
                                })

                        # Display breakdown
                        if pnl_breakdown:
                            df_pnl = pd.DataFrame(pnl_breakdown)
                            st.dataframe(df_pnl, use_container_width=True, hide_index=True)

                        # Show estimated total with breakdown
                        # NOTE: estimated_pnl already includes the full P&L from entry to now
                        # Do NOT add initial_credit - that would be double-counting!
                        net_profit = estimated_pnl

                        st.markdown("**P&L Breakdown:**")
                        st.caption(f"Unrealized P&L:             {estimated_pnl:+,.2f}")
                        st.caption(f"━" * 50)
                        st.metric("**NET PROFIT (If Closed Now)**", f"**${net_profit:,.2f}**")

                        # Calculate settlement P&L if market closed at current prices
                        st.markdown("---")
                        st.subheader("💰 Estimated P&L If Market Closes Now")
                        st.caption("Based on intrinsic value at current underlying prices")

                        # Reuse underlying prices from above (already fetched at lines 810-811)
                        if spy_price and spx_price:
                            st.caption(f"{SYM1}: ${spy_price:.2f} | {SYM2}: ${spx_price:.2f}")

                            settlement_pnl = 0.0
                            settlement_breakdown = []

                            for pos in option_positions:
                                contract = pos['contract']
                                position_size = pos.get('position', 0)
                                avg_cost_per_share = pos.get('avg_cost', 0) / 100

                                # Calculate intrinsic value at current prices
                                if contract.symbol == SYM1:
                                    underlying = spy_price
                                else:  # SYM2
                                    underlying = spx_price

                                if contract.right == 'C':
                                    intrinsic = max(0, underlying - contract.strike)
                                else:  # Put
                                    intrinsic = max(0, contract.strike - underlying)

                                # Calculate P&L
                                if position_size < 0:  # SHORT position
                                    pnl = (avg_cost_per_share - intrinsic) * abs(position_size) * 100
                                else:  # LONG position
                                    pnl = (intrinsic - avg_cost_per_share) * position_size * 100

                                settlement_pnl += pnl

                                settlement_breakdown.append({
                                    'Contract': f"{contract.symbol} {contract.strike}{contract.right}",
                                    'Position': position_size,
                                    'Entry': f"${avg_cost_per_share:.2f}",
                                    'Intrinsic Value': f"${intrinsic:.2f}",
                                    'Est. P&L': f"${pnl:,.2f}"
                                })

                            # Display breakdown
                            if settlement_breakdown:
                                df_settlement = pd.DataFrame(settlement_breakdown)
                                st.dataframe(df_settlement, use_container_width=True, hide_index=True)

                            # Show estimated total with breakdown
                            # NOTE: settlement_pnl already includes the full P&L at expiration
                            # Do NOT add initial_credit - that would be double-counting!
                            net_settlement_profit = settlement_pnl

                            st.markdown("**Settlement P&L Breakdown:**")
                            st.caption(f"Settlement P&L:             {settlement_pnl:+,.2f}")
                            st.caption(f"━" * 50)
                            st.metric("**NET PROFIT (At Expiration)**", f"**${net_settlement_profit:,.2f}**")
                        else:
                            st.warning(f"⚠️ Underlying prices not available ({SYM1}: {spy_price}, {SYM2}: {spx_price})")
                            st.info(f"Settlement P&L requires valid {SYM1}/{SYM2} prices with delayed market data")

                    except Exception as e:
                        st.warning(f"⚠️ Could not fetch current quotes: {e}")
                        st.info("Estimated P&L unavailable with delayed data")

                    # Show IB's reported P&L (will be $0 with delayed data)
                    st.markdown("---")
                    st.caption("**IB Gateway Reported P&L** (from delayed data):")
                    total_option_pnl = sum(
                        p.get('unrealized_pnl', 0) for p in option_positions
                        if p.get('unrealized_pnl') is not None
                    )
                    st.metric("Total Option P&L", f"${total_option_pnl:,.2f}")

                # Display stock positions
                if stock_positions:
                    st.write("**Stocks:**")
                    st.warning("⚠️ Stock positions detected - may indicate option assignment")

                    stock_data = []
                    for pos in stock_positions:
                        contract = pos['contract']
                        stock_data.append({
                            'Symbol': contract.symbol,
                            'Position': int(pos.get('position', 0)),
                            'Avg Cost': f"${pos.get('avg_cost', 0):.2f}",
                            'Market Price': f"${pos.get('market_price', 0):.2f}" if pos.get('market_price') else 'N/A',
                            'Market Value': f"${pos.get('market_value', 0):,.2f}" if pos.get('market_value') else 'N/A',
                            'Unrealized P&L': f"${pos.get('unrealized_pnl', 0):,.2f}" if pos.get('unrealized_pnl') is not None else 'N/A'
                        })

                    df_stocks = pd.DataFrame(stock_data)
                    st.dataframe(df_stocks, use_container_width=True, hide_index=True)

                # Get current market prices
                st.subheader("📈 Current Market Prices")

                # Prices already fetched at start of tab2 (lines 697-698)
                col1, col2 = st.columns(2)
                col1.metric(SYM1, f"${spy_price:.2f}" if spy_price else "N/A")
                col2.metric(SYM2, f"${spx_price:.2f}" if spx_price else "N/A")

                # Time to expiration (for 0DTE)
                import pytz
                et_tz = pytz.timezone('America/New_York')
                now_et = dt.now(et_tz)
                market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
                time_to_close = market_close - now_et

                if time_to_close.total_seconds() > 0:
                    hours = int(time_to_close.total_seconds() // 3600)
                    minutes = int((time_to_close.total_seconds() % 3600) // 60)
                    st.info(f"⏰ Time to market close: {hours}h {minutes}m")
                else:
                    st.info("🔔 Market closed")

                # P&L Visualization Chart
                if option_positions and spy_price and spx_price:
                    st.markdown("---")
                    st.subheader("📈 P&L Across Price Range")
                    st.caption("Risk profile visualization for current positions")

                    # Get strike prices from positions to use as fixed reference points
                    # (not current prices, so analysis stays consistent)
                    spy_strikes_in_position = [p['contract'].strike for p in option_positions if p['contract'].symbol == SYM1]
                    spx_strikes_in_position = [p['contract'].strike for p in option_positions if p['contract'].symbol == SYM2]

                    reference_spy_price = spy_strikes_in_position[0] if spy_strikes_in_position else spy_price
                    reference_spx_price = spx_strikes_in_position[0] if spx_strikes_in_position else spx_price

                    # Create price range ±3% from FIXED reference (strike price)
                    spy_range = np.linspace(reference_spy_price * 0.97, reference_spy_price * 1.03, 100)
                    spx_range = spy_range * (reference_spx_price / reference_spy_price)  # Maintain ratio

                    pnl_results = []

                    # Extract position details for P&L calculation
                    for spy_px, spx_px in zip(spy_range, spx_range):
                        total_pnl = 0

                        for pos in option_positions:
                            contract = pos['contract']
                            position_size = pos.get('position', 0)
                            avg_cost_per_share = pos.get('avg_cost', 0) / 100

                            # Determine which underlying price to use
                            if contract.symbol == SYM1:
                                underlying = spy_px
                            else:  # SYM2
                                underlying = spx_px

                            # Calculate intrinsic value
                            if contract.right == 'C':
                                intrinsic = max(0, underlying - contract.strike)
                            else:  # Put
                                intrinsic = max(0, contract.strike - underlying)

                            # Calculate P&L for this position
                            if position_size < 0:  # SHORT
                                pnl = (avg_cost_per_share - intrinsic) * abs(position_size) * 100
                            else:  # LONG
                                pnl = (intrinsic - avg_cost_per_share) * position_size * 100

                            total_pnl += pnl

                        pnl_results.append({
                            'spy_price': spy_px,
                            'spx_price': spx_px,
                            'total_pnl': total_pnl
                        })

                    df_pnl_chart = pd.DataFrame(pnl_results)

                    # Create plotly chart
                    fig = go.Figure()

                    # Total P&L line
                    fig.add_trace(
                        go.Scatter(
                            x=df_pnl_chart['spy_price'],
                            y=df_pnl_chart['total_pnl'],
                            mode='lines',
                            name='Total P&L',
                            line=dict(color='blue', width=3),
                            fill='tozeroy',
                            fillcolor='rgba(0, 100, 255, 0.1)'
                        )
                    )

                    # Add current price line
                    fig.add_vline(
                        x=spy_price,
                        line_dash="dash",
                        line_color="green",
                        annotation_text=f"Current: ${spy_price:.2f}"
                    )

                    # Add strike lines if position has common strike
                    if option_positions:
                        # Get unique strikes from positions
                        spy_strikes = set()
                        for pos in option_positions:
                            if pos['contract'].symbol == SYM1:
                                spy_strikes.add(pos['contract'].strike)

                        # Add strike line (just one for simplicity)
                        if spy_strikes:
                            strike = sorted(spy_strikes)[0]  # Use first strike
                            fig.add_vline(
                                x=strike,
                                line_dash="dot",
                                line_color="red",
                                annotation_text=f"Strike: {strike}"
                            )

                    # Add zero line
                    fig.add_hline(
                        y=0,
                        line_dash="solid",
                        line_color="gray",
                        line_width=1
                    )

                    fig.update_xaxes(title_text=f"{SYM1} Price ($)")
                    fig.update_yaxes(title_text="P&L ($)")
                    fig.update_layout(
                        height=500,
                        showlegend=False,
                        hovermode='x unified',
                        title=f"Total P&L vs {SYM1} Price"
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Statistics
                    max_profit = df_pnl_chart['total_pnl'].max()
                    max_loss = df_pnl_chart['total_pnl'].min()
                    breakeven_mask = abs(df_pnl_chart['total_pnl']) < 50
                    breakeven_prices = df_pnl_chart[breakeven_mask]['spy_price'].values if breakeven_mask.any() else []

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Max Profit (in range)", f"${max_profit:,.2f}")
                    col2.metric("Max Loss (in range)", f"${max_loss:,.2f}")
                    if len(breakeven_prices) > 0:
                        col3.metric("Breakeven Zone", f"${breakeven_prices.min():.2f} - ${breakeven_prices.max():.2f}")
                    else:
                        col3.metric("Breakeven Zone", "N/A")

            # Disconnect
            client.disconnect()

    except Exception as e:
        st.error(f"❌ Error fetching live data: {e}")
        import traceback
        with st.expander("Show error details"):
            st.code(traceback.format_exc())

# Tab 3: Price Overlay
with tab3:
    st.markdown(f"**Overlay {SYM1} vs {SYM2} option prices** to find arbitrage opportunities")

    # Determine data source: prefer TRADES (df_options), fall back to BID_ASK (df_bidask)
    _ov_source = None
    _ov_price_col = None
    _ov_has_volume = False
    if df_options is not None:
        _ov_source = df_options
        _ov_price_col = 'close'
        _ov_has_volume = True
    elif df_bidask is not None:
        _ov_source = df_bidask
        _ov_price_col = 'midpoint'
        _ov_has_volume = False

    if _ov_source is None:
        st.error("❌ No option price data found. Cannot display overlay chart.")
        st.info(f"**Required:** {OPTIONS_FILE} or {BIDASK_FILE}")
    else:
        # Calculate open ratio from underlying prices at market open
        open_spy = spy_df.iloc[0]['close']
        open_spx = spx_df.iloc[0]['close']
        open_ratio = open_spx / open_spy

        st.info(f"**Open Ratio:** {SYM2}/{SYM1} = {open_ratio:.4f} ({SYM1}: ${open_spy:.2f}, {SYM2}: ${open_spx:.2f})")
        if not _ov_has_volume:
            st.caption("Using BID_ASK midpoint prices (no TRADES data available)")

        # Option type selection
        col1, col2 = st.columns(2)
        with col1:
            overlay_right = st.selectbox("Option Type", ["P", "C"], format_func=lambda x: "Puts" if x == "P" else "Calls", key="overlay_right")
        with col2:
            st.caption(f"Using strikes: {SYM1} {spy_strike} / {SYM2} {spx_strike}")

        # Get time series data for both options
        spy_opt_data = _ov_source[
            (_ov_source['symbol'] == SYM1) &
            (_ov_source['strike'] == spy_strike) &
            (_ov_source['right'] == overlay_right)
        ].copy()

        spx_opt_data = _ov_source[
            (_ov_source['symbol'] == SYM2) &
            (_ov_source['strike'] == spx_strike) &
            (_ov_source['right'] == overlay_right)
        ].copy()

        if spy_opt_data.empty:
            st.warning(f"⚠️ No data found for {SYM1} {spy_strike}{overlay_right}")
        elif spx_opt_data.empty:
            st.warning(f"⚠️ No data found for {SYM2} {spx_strike}{overlay_right}")
        else:
            # Sort by time
            spy_opt_data = spy_opt_data.sort_values('time')
            spx_opt_data = spx_opt_data.sort_values('time')

            if _ov_has_volume:
                # Filter out zero-volume bars (stale carried-forward prices from IB)
                spy_opt_liquid = spy_opt_data[spy_opt_data['volume'] > 0].copy()
                spx_opt_liquid = spx_opt_data[spx_opt_data['volume'] > 0].copy()

                # Show how many bars were filtered
                spy_filtered = len(spy_opt_data) - len(spy_opt_liquid)
                spx_filtered = len(spx_opt_data) - len(spx_opt_liquid)
                if spy_filtered > 0 or spx_filtered > 0:
                    st.caption(f"Filtered out {spy_filtered} {SYM1} + {spx_filtered} {SYM2} zero-volume (stale) bars")

                if spy_opt_liquid.empty:
                    st.warning(f"{SYM1} {spy_strike}{overlay_right} has no bars with volume > 0 — all prices are stale")
                elif spx_opt_liquid.empty:
                    st.warning(f"{SYM2} {spx_strike}{overlay_right} has no bars with volume > 0 — all prices are stale")
            else:
                # BID_ASK data: filter by valid quotes (bid > 0 and ask > 0)
                spy_opt_liquid = spy_opt_data[(spy_opt_data['bid'] > 0) & (spy_opt_data['ask'] > 0)].copy()
                spx_opt_liquid = spx_opt_data[(spx_opt_data['bid'] > 0) & (spx_opt_data['ask'] > 0)].copy()
                spy_filtered = len(spy_opt_data) - len(spy_opt_liquid)
                spx_filtered = len(spx_opt_data) - len(spx_opt_liquid)

            # Normalize SYM2 price by dividing by the open ratio
            spx_opt_liquid[f'normalized_{_ov_price_col}'] = spx_opt_liquid[_ov_price_col] / open_ratio

            # Merge on time to align data points (only liquid bars)
            merged = pd.merge(
                spy_opt_liquid[['time', _ov_price_col]].rename(columns={_ov_price_col: 'spy_price'}),
                spx_opt_liquid[['time', f'normalized_{_ov_price_col}']].rename(columns={f'normalized_{_ov_price_col}': 'spx_normalized'}),
                on='time',
                how='inner'
            )

            if merged.empty:
                st.warning(f"No overlapping time periods found between {SYM1} and {SYM2} data")
            else:
                # Calculate the spread (gap) - SYM2 normalized minus SYM1
                # Positive = SYM2 more expensive (sell SYM2, buy SYM1)
                # Negative = SYM1 more expensive (sell SYM1, buy SYM2)
                merged['spread'] = merged['spx_normalized'] - merged['spy_price']
                merged['spread_pct'] = (merged['spread'] / merged['spy_price']) * 100

                # Convert time to ET for display
                merged['time_et'] = merged['time'].dt.tz_convert('America/New_York')
                merged['time_label'] = merged['time_et'].dt.strftime('%H:%M')

                # Find max spread (best arbitrage opportunity)
                max_spread_idx = merged['spread'].abs().idxmax()
                max_spread_row = merged.loc[max_spread_idx]

                # Calculate worst-case P&L for each time point
                # Worst case accounts for basis drift (±0.05%) at settlement
                basis_drift_pct = 0.001  # 0.10%

                def calc_worst_case_pnl(row):
                    """
                    Calculate worst-case P&L if entering at this time.
                    Credit = spread * 10 contracts * 100 multiplier
                    Worst case = credit - max potential settlement cost from basis drift
                    """
                    spread = row['spread']
                    spy_px = row['spy_price']
                    spx_norm = row['spx_normalized']

                    # Entry credit (QTY_RATIO SYM1 vs 1 SYM2, normalized)
                    # Positive spread means SYM2 > SYM1, so sell SYM2 buy SYM1
                    credit = abs(spread) * QTY_RATIO * 100

                    # Worst case basis drift cost
                    # If basis drifts against us by 0.05%, the settlement spread changes
                    # Max adverse drift = open_ratio * basis_drift_pct * strike
                    max_basis_cost = open_ratio * basis_drift_pct * spy_strike * QTY_RATIO * 100

                    # Also account for potential moneyness mismatch at settlement
                    # Using the moneyness difference calculated earlier
                    moneyness_cost = abs(spy_moneyness_pct - spx_moneyness_pct) / 100 * spy_strike * QTY_RATIO * 100

                    worst_case = credit - max_basis_cost - moneyness_cost
                    return worst_case

                merged['worst_case_pnl'] = merged.apply(calc_worst_case_pnl, axis=1)

                # Find best worst-case (highest floor on P&L) using simplified formula for ranking
                best_worst_idx = merged['worst_case_pnl'].idxmax()
                best_worst_row = merged.loc[best_worst_idx]

                # Recompute accurate worst-case at the best time using grid search
                best_worst_time_overlay = best_worst_row['time']

                # Look up underlying prices at best worst-case time
                _ov_spy_at = spy_df.iloc[(spy_df['time'] - best_worst_time_overlay).abs().argsort()[:1]]
                _ov_spx_at = spx_df.iloc[(spx_df['time'] - best_worst_time_overlay).abs().argsort()[:1]]
                _ov_entry_spy = _ov_spy_at['close'].iloc[0]
                _ov_entry_spx = _ov_spx_at['close'].iloc[0]

                # Look up actual option prices at best worst-case time (open price, volume>0)
                _ov_spy_opt_price = get_option_price_from_db(
                    spy_opt_liquid, SYM1, spy_strike, overlay_right, best_worst_time_overlay)
                _ov_spx_opt_price = get_option_price_from_db(
                    spx_opt_liquid, SYM2, spx_strike, overlay_right, best_worst_time_overlay)

                # Determine direction from spread
                _ov_spread_sign = best_worst_row['spread']
                _ov_direction = f'Sell {SYM2}' if _ov_spread_sign > 0 else f'Sell {SYM1}'

                # Build params for grid search based on option type and direction
                if overlay_right == 'P':
                    if _ov_direction == f'Sell {SYM2}':
                        _ov_put_dir = f"Buy {SYM1}, Sell {SYM2}"
                        _ov_sell_put_px, _ov_buy_put_px = _ov_spx_opt_price, _ov_spy_opt_price
                        _ov_sell_puts_q, _ov_buy_puts_q = 1, QTY_RATIO
                    else:
                        _ov_put_dir = f"Sell {SYM1}, Buy {SYM2}"
                        _ov_sell_put_px, _ov_buy_put_px = _ov_spy_opt_price, _ov_spx_opt_price
                        _ov_sell_puts_q, _ov_buy_puts_q = QTY_RATIO, 1
                    _ov_call_dir = f"Sell {SYM2}, Buy {SYM1}"
                    _ov_sell_call_px = _ov_buy_call_px = 0.0
                    _ov_sell_calls_q = _ov_buy_calls_q = 0
                    _ov_show_calls, _ov_show_puts = False, True
                else:
                    if _ov_direction == f'Sell {SYM2}':
                        _ov_call_dir = f"Sell {SYM2}, Buy {SYM1}"
                        _ov_sell_call_px, _ov_buy_call_px = _ov_spx_opt_price, _ov_spy_opt_price
                        _ov_sell_calls_q, _ov_buy_calls_q = 1, QTY_RATIO
                    else:
                        _ov_call_dir = f"Buy {SYM2}, Sell {SYM1}"
                        _ov_sell_call_px, _ov_buy_call_px = _ov_spy_opt_price, _ov_spx_opt_price
                        _ov_sell_calls_q, _ov_buy_calls_q = QTY_RATIO, 1
                    _ov_put_dir = f"Sell {SYM1}, Buy {SYM2}"
                    _ov_sell_put_px = _ov_buy_put_px = 0.0
                    _ov_sell_puts_q = _ov_buy_puts_q = 0
                    _ov_show_calls, _ov_show_puts = True, False

                if _ov_spy_opt_price is not None and _ov_spx_opt_price is not None:
                    _ov_best, _ov_worst = calculate_best_worst_case_with_basis_drift(
                        entry_spy_price=_ov_entry_spy,
                        entry_spx_price=_ov_entry_spx,
                        spy_strike=spy_strike,
                        spx_strike=spx_strike,
                        call_direction=_ov_call_dir,
                        put_direction=_ov_put_dir,
                        sell_call_price=_ov_sell_call_px,
                        buy_call_price=_ov_buy_call_px,
                        sell_calls_qty=_ov_sell_calls_q,
                        buy_calls_qty=_ov_buy_calls_q,
                        sell_put_price=_ov_sell_put_px,
                        buy_put_price=_ov_buy_put_px,
                        sell_puts_qty=_ov_sell_puts_q,
                        buy_puts_qty=_ov_buy_puts_q,
                        show_calls=_ov_show_calls,
                        show_puts=_ov_show_puts,
                        sym1=SYM1, sym2=SYM2,
                    )
                    accurate_worst_pnl = _ov_worst.get('net_pnl', best_worst_row['worst_case_pnl'])
                else:
                    accurate_worst_pnl = best_worst_row['worst_case_pnl']

                # Display key metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Max Gap", f"${abs(max_spread_row['spread']):.2f}",
                             help="Largest price difference - highest potential credit")
                with col2:
                    st.metric("Best Worst-Case", f"${accurate_worst_pnl:,.2f}",
                             delta=f"@ {best_worst_row['time_label']}",
                             help="Entry time where even worst-case scenario is most profitable (accurate grid search)")
                with col3:
                    direction = f"{SYM2} > {SYM1}" if max_spread_row['spread'] > 0 else f"{SYM1} > {SYM2}"
                    st.metric("Direction", direction)
                with col4:
                    st.metric("Max Gap Time", max_spread_row['time_label'])

                # Create overlay chart with Plotly
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.1,
                    row_heights=[0.7, 0.3],
                    subplot_titles=(
                        f"{SYM1} {spy_strike}{overlay_right} vs {SYM2} {spx_strike}{overlay_right} (Normalized)",
                        f"Spread ({SYM2} - {SYM1})"
                    )
                )

                # SYM1 price line
                fig.add_trace(
                    go.Scatter(
                        x=merged['time_label'],
                        y=merged['spy_price'],
                        mode='lines',
                        name=f'{SYM1} {spy_strike}{overlay_right}',
                        line=dict(color='#00D4AA', width=2)
                    ),
                    row=1, col=1
                )

                # SYM2 normalized price line
                fig.add_trace(
                    go.Scatter(
                        x=merged['time_label'],
                        y=merged['spx_normalized'],
                        mode='lines',
                        name=f'{SYM2} {spx_strike}{overlay_right} (÷{open_ratio:.2f})',
                        line=dict(color='#FF6B6B', width=2)
                    ),
                    row=1, col=1
                )

                # Spread chart (bottom)
                colors = ['#00D4AA' if s < 0 else '#FF6B6B' for s in merged['spread']]
                fig.add_trace(
                    go.Bar(
                        x=merged['time_label'],
                        y=merged['spread'],
                        name='Spread',
                        marker_color=colors,
                        showlegend=False
                    ),
                    row=2, col=1
                )

                # Add zero line to spread chart
                fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1, row=2, col=1)

                # Mark the max spread point with a scatter marker (works with categorical x-axis)
                fig.add_trace(
                    go.Scatter(
                        x=[max_spread_row['time_label']],
                        y=[max(max_spread_row['spy_price'], max_spread_row['spx_normalized'])],
                        mode='markers+text',
                        name='Max Gap',
                        marker=dict(color='yellow', size=15, symbol='star'),
                        text=[f"Max Gap: ${abs(max_spread_row['spread']):.2f}"],
                        textposition='top center',
                        textfont=dict(color='yellow', size=12),
                        showlegend=False
                    ),
                    row=1, col=1
                )

                # Mark the best worst-case point with a different star (cyan)
                # Only add if it's a different point than max spread
                if best_worst_row['time_label'] != max_spread_row['time_label']:
                    fig.add_trace(
                        go.Scatter(
                            x=[best_worst_row['time_label']],
                            y=[min(best_worst_row['spy_price'], best_worst_row['spx_normalized'])],
                            mode='markers+text',
                            name='Best Worst-Case',
                            marker=dict(color='cyan', size=15, symbol='star-diamond'),
                            text=[f"Safe: ${accurate_worst_pnl:.0f}"],
                            textposition='bottom center',
                            textfont=dict(color='cyan', size=12),
                            showlegend=False
                        ),
                        row=1, col=1
                    )

                # Add worst-case P&L line to spread chart (secondary y-axis effect via color)
                fig.add_trace(
                    go.Scatter(
                        x=merged['time_label'],
                        y=merged['worst_case_pnl'] / 100,  # Scale down to fit on spread chart
                        mode='lines',
                        name='Worst-Case P&L (÷100)',
                        line=dict(color='cyan', width=2, dash='dot'),
                        opacity=0.7
                    ),
                    row=2, col=1
                )

                fig.update_layout(
                    height=600,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    ),
                    hovermode='x unified'
                )

                fig.update_xaxes(title_text="Time (ET)", row=2, col=1)
                fig.update_yaxes(title_text="Option Price ($)", row=1, col=1)
                fig.update_yaxes(title_text="Spread ($)", row=2, col=1)

                st.plotly_chart(fig, use_container_width=True)

                # Trading signal interpretation
                st.markdown("---")
                st.subheader("📊 Trading Signal")

                if max_spread_row['spread'] > 0:
                    signal = f"SELL {SYM2}, BUY {SYM1}"
                    st.success(f"**{signal}** - {SYM2} is overpriced relative to {SYM1} by ${abs(max_spread_row['spread']):.2f}")
                else:
                    signal = f"SELL {SYM1}, BUY {SYM2}"
                    st.success(f"**{signal}** - {SYM1} is overpriced relative to {SYM2} by ${abs(max_spread_row['spread']):.2f}")

                # Credit calculation at max spread time
                spx_price_at_max = spx_opt_data[spx_opt_data['time'] == max_spread_row['time']][_ov_price_col].iloc[0]
                spy_price_at_max = max_spread_row['spy_price']

                # Calculate potential credit ({QTY_RATIO} SYM1 vs 1 SYM2)
                if max_spread_row['spread'] > 0:
                    # Sell 1 SYM2, Buy QTY_RATIO SYM1
                    credit = (spx_price_at_max * 1 * 100) - (spy_price_at_max * QTY_RATIO * 100)
                else:
                    # Sell QTY_RATIO SYM1, Buy 1 SYM2
                    credit = (spy_price_at_max * QTY_RATIO * 100) - (spx_price_at_max * 1 * 100)

                st.info(f"**Estimated Credit at {max_spread_row['time_label']}:** ${credit:,.2f} (1 {SYM2} @ ${spx_price_at_max:.2f} vs {QTY_RATIO} {SYM1} @ ${spy_price_at_max:.2f})")

                # Best worst-case analysis
                st.markdown("---")
                st.subheader("🛡️ Safest Entry (Best Worst-Case)")

                spx_price_at_safe = spx_opt_data[spx_opt_data['time'] == best_worst_row['time']][_ov_price_col].iloc[0]
                spy_price_at_safe = best_worst_row['spy_price']

                if best_worst_row['spread'] > 0:
                    safe_credit = (spx_price_at_safe * 1 * 100) - (spy_price_at_safe * QTY_RATIO * 100)
                else:
                    safe_credit = (spy_price_at_safe * QTY_RATIO * 100) - (spx_price_at_safe * 1 * 100)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Entry Time", best_worst_row['time_label'])
                    st.metric("Entry Credit", f"${safe_credit:,.2f}")
                with col2:
                    st.metric("Worst-Case P&L", f"${accurate_worst_pnl:,.2f}",
                             delta="guaranteed" if accurate_worst_pnl > 0 else "at risk")

                if accurate_worst_pnl > 0:
                    st.success(f"✅ **SAFE ENTRY** at {best_worst_row['time_label']} - Even in worst-case (0.10% basis drift), you profit ${accurate_worst_pnl:,.2f}")
                else:
                    st.warning(f"⚠️ Entry at {best_worst_row['time_label']} has worst-case loss of ${abs(accurate_worst_pnl):,.2f}")

                # Legend
                st.markdown("---")
                st.caption("**Chart Legend:**")
                st.caption("⭐ **Yellow Star** = Max Gap (highest credit potential)")
                st.caption("💎 **Cyan Diamond** = Best Worst-Case (safest entry - profit even if things go wrong)")
                st.caption("📈 **Cyan Dotted Line** = Worst-case P&L over time (÷100 for scale)")

                # Show data table
                with st.expander("📋 Raw Data"):
                    display_df = merged[['time_label', 'spy_price', 'spx_normalized', 'spread', 'spread_pct', 'worst_case_pnl']].copy()
                    display_df.columns = ['Time', f'{SYM1} {spy_strike}{overlay_right}', f'{SYM2} {spx_strike}{overlay_right} (Norm)', 'Spread ($)', 'Spread (%)', 'Worst-Case P&L']
                    st.dataframe(display_df, use_container_width=True, hide_index=True)

                # Export overlay data as JSON
                overlay_export = {
                    "view": "price_overlay",
                    "date": selected_date,
                    "option_type": overlay_right,
                    "strikes": {
                        "spy": spy_strike,
                        "spx": spx_strike,
                        "spy_moneyness_pct": float(spy_moneyness_pct),
                        "spx_moneyness_pct": float(spx_moneyness_pct),
                        "moneyness_diff": float(moneyness_diff)
                    },
                    "open_ratio": float(open_ratio),
                    "open_prices": {
                        "spy": float(open_spy),
                        "spx": float(open_spx)
                    },
                    "max_gap": {
                        "spread": float(max_spread_row['spread']),
                        "spread_abs": float(abs(max_spread_row['spread'])),
                        "time": max_spread_row['time_label'],
                        "spy_price": float(max_spread_row['spy_price']),
                        "spx_normalized": float(max_spread_row['spx_normalized']),
                        "direction": f"{SYM2} > {SYM1}" if max_spread_row['spread'] > 0 else f"{SYM1} > {SYM2}",
                        "credit": float(credit)
                    },
                    "best_worst_case": {
                        "time": best_worst_row['time_label'],
                        "spread": float(best_worst_row['spread']),
                        "spy_price": float(best_worst_row['spy_price']),
                        "spx_normalized": float(best_worst_row['spx_normalized']),
                        "simplified_worst_pnl": float(best_worst_row['worst_case_pnl']),
                        "accurate_worst_pnl": float(accurate_worst_pnl),
                        "safe_credit": float(safe_credit),
                        "direction": f"Sell {SYM2}" if best_worst_row['spread'] > 0 else f"Sell {SYM1}"
                    },
                    "grid_search_params": {
                        "entry_spy_price": float(_ov_entry_spy) if _ov_spy_opt_price is not None else None,
                        "entry_spx_price": float(_ov_entry_spx) if _ov_spx_opt_price is not None else None,
                        "spy_opt_price": float(_ov_spy_opt_price) if _ov_spy_opt_price is not None else None,
                        "spx_opt_price": float(_ov_spx_opt_price) if _ov_spx_opt_price is not None else None,
                        "basis_drift_pct": basis_drift_pct
                    },
                    "time_series": [
                        {
                            "time": r['time_label'],
                            "spy_price": float(r['spy_price']),
                            "spx_normalized": float(r['spx_normalized']),
                            "spread": float(r['spread']),
                            "spread_pct": float(r['spread_pct']),
                            "worst_case_pnl": float(r['worst_case_pnl'])
                        }
                        for _, r in merged.iterrows()
                    ],
                    "filtered_bars": {
                        "spy_zero_volume": spy_filtered,
                        "spx_zero_volume": spx_filtered,
                        "overlapping_liquid_bars": len(merged)
                    }
                }
                overlay_json = json.dumps(overlay_export, indent=2)
                st.download_button(
                    label="Export Overlay Data (JSON)",
                    data=overlay_json,
                    file_name=f"overlay_{selected_date}_{SYM1}{spy_strike}_{SYM2}{spx_strike}_{overlay_right}.json",
                    mime="application/json",
                    help="Download price overlay data, spread time series, and worst-case analysis as JSON"
                )

# Tab 4: Underlying Divergence
with tab4:
    st.markdown(f"**Track {SYM1} vs {SYM2} underlying price divergence** throughout the trading day")

    # Normalize underlying prices to % change from open
    sym1_open = spy_df.iloc[0]['close']
    sym2_open = spx_df.iloc[0]['close']

    spy_div = spy_df[['time', 'time_label', 'close']].copy()
    spx_div = spx_df[['time', 'close']].copy()

    spy_div['pct_change'] = (spy_div['close'] - sym1_open) / sym1_open * 100
    spx_div['pct_change'] = (spx_div['close'] - sym2_open) / sym2_open * 100

    # Merge on time (inner join) — time_label comes from spy_div only
    merged_div = pd.merge(
        spy_div[['time', 'time_label', 'close', 'pct_change']],
        spx_div[['time', 'close', 'pct_change']],
        on='time', suffixes=('_sym1', '_sym2')
    )

    if merged_div.empty:
        st.error("No overlapping time data between the two underlyings.")
    else:
        # Compute gap: SYM2 % change - SYM1 % change
        merged_div['pct_gap'] = merged_div['pct_change_sym2'] - merged_div['pct_change_sym1']
        # Dollar gap: SYM2/ratio - SYM1
        merged_div['dollar_gap'] = merged_div['close_sym2'] / QTY_RATIO - merged_div['close_sym1']

        # Find max absolute gap
        max_gap_idx = merged_div['pct_gap'].abs().idxmax()
        max_gap_row = merged_div.loc[max_gap_idx]
        max_gap_time = max_gap_row['time_label']
        max_gap_val = max_gap_row['pct_gap']
        max_dollar_gap = max_gap_row['dollar_gap']

        # Current (latest) gap
        latest = merged_div.iloc[-1]
        current_gap = latest['pct_gap']
        current_dollar_gap = latest['dollar_gap']

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Max Gap", f"{abs(max_gap_val):.4f}%",
                       help="Largest absolute % divergence between the two underlyings")
        with m2:
            leading = SYM2 if max_gap_val > 0 else SYM1
            st.metric("Max Gap Time", max_gap_time,
                       help=f"{leading} was leading at this point")
        with m3:
            st.metric("Current Gap", f"{current_gap:+.4f}%",
                       help="Latest divergence (positive = SYM2 leading)")
        with m4:
            st.metric("Dollar Gap (norm)", f"${max_dollar_gap:+.2f}",
                       help=f"{SYM2}/{QTY_RATIO} minus {SYM1}")

        # 2-panel Plotly chart
        div_fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.6, 0.4],
            subplot_titles=(
                f"{SYM1} vs {SYM2} — % Change from Open",
                f"Divergence Gap ({SYM2} % − {SYM1} %)"
            )
        )

        # Top panel: % change lines
        div_fig.add_trace(
            go.Scatter(
                x=merged_div['time_label'], y=merged_div['pct_change_sym1'],
                name=SYM1, line=dict(color='#1f77b4', width=2), mode='lines'
            ), row=1, col=1
        )
        div_fig.add_trace(
            go.Scatter(
                x=merged_div['time_label'], y=merged_div['pct_change_sym2'],
                name=SYM2, line=dict(color='#ff7f0e', width=2), mode='lines'
            ), row=1, col=1
        )

        # Star at max gap on both lines
        div_fig.add_trace(
            go.Scatter(
                x=[max_gap_time], y=[max_gap_row['pct_change_sym1']],
                mode='markers', marker=dict(symbol='star', size=14, color='red', line=dict(width=1, color='black')),
                name='Max Gap', showlegend=False,
                hovertemplate=f"Max Gap: {max_gap_val:+.4f}%<br>{SYM1}: {max_gap_row['pct_change_sym1']:.4f}%<extra></extra>"
            ), row=1, col=1
        )
        div_fig.add_trace(
            go.Scatter(
                x=[max_gap_time], y=[max_gap_row['pct_change_sym2']],
                mode='markers', marker=dict(symbol='star', size=14, color='red', line=dict(width=1, color='black')),
                name='Max Gap', showlegend=False,
                hovertemplate=f"Max Gap: {max_gap_val:+.4f}%<br>{SYM2}: {max_gap_row['pct_change_sym2']:.4f}%<extra></extra>"
            ), row=1, col=1
        )

        # Bottom panel: gap bar chart
        bar_colors = ['green' if g >= 0 else 'red' for g in merged_div['pct_gap']]
        div_fig.add_trace(
            go.Bar(
                x=merged_div['time_label'], y=merged_div['pct_gap'],
                marker_color=bar_colors, name='Gap',
                showlegend=False,
                hovertemplate="Gap: %{y:.4f}%<extra></extra>"
            ), row=2, col=1
        )

        # Star on max gap bar
        div_fig.add_trace(
            go.Scatter(
                x=[max_gap_time], y=[max_gap_val],
                mode='markers+text',
                marker=dict(symbol='star', size=14, color='gold', line=dict(width=1, color='black')),
                text=[f"  {max_gap_val:+.4f}%"], textposition='top center',
                name='Max Gap Point', showlegend=False
            ), row=2, col=1
        )

        div_fig.update_layout(
            height=600,
            margin=dict(t=40, b=30),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            hovermode='x unified'
        )
        div_fig.update_yaxes(title_text="% Change", row=1, col=1)
        div_fig.update_yaxes(title_text="Gap %", row=2, col=1)

        # Reduce x-axis tick density
        tick_step = max(1, len(merged_div) // 20)
        tick_vals = merged_div['time_label'].iloc[::tick_step].tolist()
        div_fig.update_xaxes(tickvals=tick_vals, tickangle=45, row=2, col=1)

        st.plotly_chart(div_fig, use_container_width=True)

        # Strategy suggestions at max gap time
        st.markdown("---")
        st.subheader(f"Strategy Suggestions at Max Gap ({max_gap_time})")

        sym1_price_at_gap = max_gap_row['close_sym1']
        sym2_price_at_gap = max_gap_row['close_sym2']

        # Suggested ATM strikes
        suggested_sym1_strike = int(round(sym1_price_at_gap))
        suggested_sym2_strike = int(round(sym2_price_at_gap / SYM2_STRIKE_STEP) * SYM2_STRIKE_STEP)

        st.info(f"**Underlying prices at max gap:** {SYM1} = ${sym1_price_at_gap:.2f}, {SYM2} = ${sym2_price_at_gap:.2f}")
        st.info(f"**Suggested ATM strikes:** {SYM1} {suggested_sym1_strike} / {SYM2} {suggested_sym2_strike}")

        # Determine direction: if SYM2 is leading (positive gap), SYM2 is overpriced -> sell SYM2
        if max_gap_val > 0:
            overpriced = SYM2
            underpriced = SYM1
        else:
            overpriced = SYM1
            underpriced = SYM2

        st.markdown(f"**Direction:** {overpriced} is relatively overpriced → **Sell {overpriced}, Buy {underpriced}**")

        # Look up option prices if data exists
        if df_options is not None:
            max_gap_utc_time = max_gap_row['time']

            strategy_rows = []
            for right in ['P', 'C']:
                right_label = 'Put' if right == 'P' else 'Call'

                sym1_opt = df_options[
                    (df_options['symbol'] == SYM1) &
                    (df_options['strike'] == suggested_sym1_strike) &
                    (df_options['right'] == right)
                ]
                sym2_opt = df_options[
                    (df_options['symbol'] == SYM2) &
                    (df_options['strike'] == suggested_sym2_strike) &
                    (df_options['right'] == right)
                ]

                if not sym1_opt.empty and not sym2_opt.empty:
                    # Find closest time to max gap
                    sym1_at_gap = sym1_opt.iloc[(sym1_opt['time'] - max_gap_utc_time).abs().argsort()[:1]]
                    sym2_at_gap = sym2_opt.iloc[(sym2_opt['time'] - max_gap_utc_time).abs().argsort()[:1]]

                    sym1_price = sym1_at_gap.iloc[0]['close']
                    sym2_price = sym2_at_gap.iloc[0]['close']
                    sym2_normalized = sym2_price / QTY_RATIO

                    if overpriced == SYM2:
                        sell_price = sym2_normalized
                        buy_price = sym1_price
                        sell_label = SYM2
                        buy_label = SYM1
                    else:
                        sell_price = sym1_price
                        buy_price = sym2_normalized
                        sell_label = SYM1
                        buy_label = SYM2

                    credit = sell_price - buy_price
                    strategy_rows.append({
                        'Type': right_label,
                        f'{SYM1} {suggested_sym1_strike}': f'${sym1_price:.2f}',
                        f'{SYM2} {suggested_sym2_strike}': f'${sym2_price:.2f}',
                        f'{SYM2} (norm)': f'${sym2_normalized:.2f}',
                        'Sell': sell_label,
                        'Buy': buy_label,
                        'Est. Credit': f'${credit:.2f}',
                    })

            if strategy_rows:
                st.dataframe(pd.DataFrame(strategy_rows), use_container_width=True, hide_index=True)
            else:
                st.warning("No option data found for the suggested strikes at the max gap time.")
        else:
            st.warning("Option price data not loaded — cannot look up option prices.")

        # Apply button
        st.markdown("---")

        # Determine entry time in short format for the slider
        max_gap_time_et = max_gap_row['time'].tz_convert('America/New_York')
        max_gap_time_short = max_gap_time_et.strftime('%H:%M')

        # Direction string for _apply_scanner_result: "Sell SYM1" or "Sell SYM2"
        apply_direction = f"Sell {overpriced}"

        # Offer apply for both puts and calls
        apply_col1, apply_col2 = st.columns(2)
        with apply_col1:
            st.button(
                f"📊 Apply as Puts ({SYM1} {suggested_sym1_strike} / {SYM2} {suggested_sym2_strike})",
                on_click=_apply_scanner_result,
                args=(suggested_sym1_strike, suggested_sym2_strike, apply_direction, max_gap_time_short, 'P'),
                key="div_apply_puts",
                use_container_width=True
            )
        with apply_col2:
            st.button(
                f"📊 Apply as Calls ({SYM1} {suggested_sym1_strike} / {SYM2} {suggested_sym2_strike})",
                on_click=_apply_scanner_result,
                args=(suggested_sym1_strike, suggested_sym2_strike, apply_direction, max_gap_time_short, 'C'),
                key="div_apply_calls",
                use_container_width=True
            )

        st.info("💡 Click **Apply** to load these strikes and entry time into the sidebar, then switch to **📊 Historical Analysis** to analyze.")

# Tab 5: Strike Scanner
with tab5:
    st.markdown("**Scan all strikes** to find the best arbitrage opportunity")

    # Determine data source for scanner
    _sc_source = None
    _sc_price_col = None
    _sc_has_volume = False
    if df_options is not None:
        _sc_source = df_options
        _sc_price_col = 'close'
        _sc_has_volume = True
    elif df_bidask is not None:
        _sc_source = df_bidask
        _sc_price_col = 'midpoint'
        _sc_has_volume = False

    if _sc_source is None:
        st.error("❌ No option price data found. Cannot scan strikes.")
        st.info(f"**Required:** {OPTIONS_FILE} or {BIDASK_FILE}")
    else:
        # Get open ratio
        open_spy = spy_df.iloc[0]['close']
        open_spx = spx_df.iloc[0]['close']
        open_ratio = open_spx / open_spy

        st.info(f"**Open Ratio:** {SYM2}/{SYM1} = {open_ratio:.4f}")
        if not _sc_has_volume:
            st.caption("Using BID_ASK midpoint prices (no TRADES data available)")

        # Option type selection
        scanner_right = st.selectbox("Option Type to Scan", ["P", "C"],
                                     format_func=lambda x: "Puts" if x == "P" else "Calls",
                                     key="scanner_right")

        # Get all unique strikes from the data
        spy_strikes_list = sorted(_sc_source[_sc_source['symbol'] == SYM1]['strike'].unique())
        spx_strikes_list = sorted(_sc_source[_sc_source['symbol'] == SYM2]['strike'].unique())

        st.caption(f"Found {len(spy_strikes_list)} {SYM1} strikes and {len(spx_strikes_list)} {SYM2} strikes")

        # Liquidity filtering controls (only shown when volume data is available)
        hide_illiquid = False
        min_volume = 0
        if _sc_has_volume:
            scanner_col1, scanner_col2 = st.columns(2)
            with scanner_col1:
                hide_illiquid = st.checkbox("Hide illiquid strikes", value=True,
                                            help="Filter out strikes with total daily volume below threshold")
            with scanner_col2:
                min_volume = st.number_input("Min Total Volume", value=10, min_value=0, step=5,
                                              help="Minimum total daily volume across all bars for a contract")

        if st.button("🔍 Scan All Strike Pairs", type="primary", use_container_width=True):
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Find matching strike pairs (SYM1 strike * ratio ≈ SYM2 strike)
            pairs_to_scan = []

            for spy_s in spy_strikes_list:
                # Find SYM2 strikes that are close to SYM1 * open_ratio
                target_spx = spy_s * open_ratio
                for spx_s in spx_strikes_list:
                    # Allow some tolerance for matching (within 0.5%)
                    if abs(spx_s - target_spx) / target_spx < 0.005:
                        pairs_to_scan.append((spy_s, spx_s))

            total_pairs = len(pairs_to_scan)
            st.caption(f"Found {total_pairs} matching strike pairs to analyze")

            for idx, (spy_s, spx_s) in enumerate(pairs_to_scan):
                progress_bar.progress((idx + 1) / total_pairs)
                status_text.text(f"Scanning {SYM1} {spy_s} / {SYM2} {spx_s}...")

                # Get data for this strike pair from the active data source
                spy_opt = _sc_source[
                    (_sc_source['symbol'] == SYM1) &
                    (_sc_source['strike'] == spy_s) &
                    (_sc_source['right'] == scanner_right)
                ].copy()

                spx_opt = _sc_source[
                    (_sc_source['symbol'] == SYM2) &
                    (_sc_source['strike'] == spx_s) &
                    (_sc_source['right'] == scanner_right)
                ].copy()

                if spy_opt.empty or spx_opt.empty:
                    continue

                if _sc_has_volume:
                    # TRADES data: filter by volume
                    spy_total_vol = int(spy_opt['volume'].sum())
                    spx_total_vol = int(spx_opt['volume'].sum())

                    if hide_illiquid and (spy_total_vol < min_volume or spx_total_vol < min_volume):
                        continue

                    spy_opt = spy_opt[spy_opt['volume'] > 0].copy()
                    spx_opt = spx_opt[spx_opt['volume'] > 0].copy()

                    if spy_opt.empty or spx_opt.empty:
                        continue
                else:
                    # BID_ASK data: filter by valid quotes
                    spy_opt = spy_opt[(spy_opt['bid'] > 0) & (spy_opt['ask'] > 0)].copy()
                    spx_opt = spx_opt[(spx_opt['bid'] > 0) & (spx_opt['ask'] > 0)].copy()
                    spy_total_vol = len(spy_opt)
                    spx_total_vol = len(spx_opt)

                    if spy_opt.empty or spx_opt.empty:
                        continue

                # Sort
                spy_opt = spy_opt.sort_values('time')
                spx_opt = spx_opt.sort_values('time')

                # Use midpoint from BID_ASK when we have both TRADES + BID_ASK
                _using_midpoint = False
                if _sc_has_volume and df_bidask is not None:
                    spy_ba = df_bidask[
                        (df_bidask['symbol'] == SYM1) &
                        (df_bidask['strike'] == spy_s) &
                        (df_bidask['right'] == scanner_right)
                    ].copy()
                    spx_ba = df_bidask[
                        (df_bidask['symbol'] == SYM2) &
                        (df_bidask['strike'] == spx_s) &
                        (df_bidask['right'] == scanner_right)
                    ].copy()

                    if not spy_ba.empty and not spx_ba.empty:
                        spy_ba = spy_ba.sort_values('time')
                        spx_ba = spx_ba.sort_values('time')

                        # Only keep BID_ASK bars at times with actual trade volume
                        spy_liquid_times = set(spy_opt['time'])
                        spx_liquid_times = set(spx_opt['time'])
                        spy_ba = spy_ba[spy_ba['time'].isin(spy_liquid_times)].copy()
                        spx_ba = spx_ba[spx_ba['time'].isin(spx_liquid_times)].copy()

                        spx_ba['normalized_mid'] = spx_ba['midpoint'] / open_ratio

                        merged_scan = pd.merge(
                            spy_ba[['time', 'midpoint']].rename(columns={'midpoint': 'spy_price'}),
                            spx_ba[['time', 'normalized_mid']].rename(columns={'normalized_mid': 'spx_normalized'}),
                            on='time',
                            how='inner'
                        )
                        _using_midpoint = True

                if not _using_midpoint:
                    # Use the primary data source directly
                    spx_opt[f'normalized_{_sc_price_col}'] = spx_opt[_sc_price_col] / open_ratio
                    merged_scan = pd.merge(
                        spy_opt[['time', _sc_price_col]].rename(columns={_sc_price_col: 'spy_price'}),
                        spx_opt[['time', f'normalized_{_sc_price_col}']].rename(columns={f'normalized_{_sc_price_col}': 'spx_normalized'}),
                        on='time',
                        how='inner'
                    )

                if merged_scan.empty or len(merged_scan) < 5:
                    continue

                # Calculate spread
                merged_scan['spread'] = merged_scan['spx_normalized'] - merged_scan['spy_price']

                # Calculate moneyness for this strike pair
                spy_moneyness_scan = ((spy_s - open_spy) / open_spy) * 100
                spx_moneyness_scan = ((spx_s - open_spx) / open_spx) * 100
                moneyness_diff_scan = abs(spy_moneyness_scan - spx_moneyness_scan)

                # Calculate worst-case P&L for each time point
                basis_drift_pct = 0.001

                def calc_worst_case_scan(row):
                    spread_val = row['spread']
                    credit_val = abs(spread_val) * QTY_RATIO * 100
                    max_basis_cost = open_ratio * basis_drift_pct * spy_s * QTY_RATIO * 100
                    moneyness_cost = moneyness_diff_scan / 100 * spy_s * QTY_RATIO * 100
                    return credit_val - max_basis_cost - moneyness_cost

                merged_scan['worst_case_pnl'] = merged_scan.apply(calc_worst_case_scan, axis=1)

                # Find max spread and best worst-case
                max_spread_idx_scan = merged_scan['spread'].abs().idxmax()
                max_spread_row_scan = merged_scan.loc[max_spread_idx_scan]

                best_worst_idx_scan = merged_scan['worst_case_pnl'].idxmax()
                best_worst_row_scan = merged_scan.loc[best_worst_idx_scan]

                # Get actual SYM2 price for credit calculation (use midpoint when available)
                if _using_midpoint:
                    _spx_at_max = spx_ba[spx_ba['time'] == max_spread_row_scan['time']]
                    if not _spx_at_max.empty:
                        spx_price_at_max_scan = _spx_at_max['midpoint'].iloc[0]
                    else:
                        spx_price_at_max_scan = spx_opt[spx_opt['time'] == max_spread_row_scan['time']][_sc_price_col].iloc[0]
                else:
                    spx_price_at_max_scan = spx_opt[spx_opt['time'] == max_spread_row_scan['time']][_sc_price_col].iloc[0]
                if max_spread_row_scan['spread'] > 0:
                    credit_scan = (spx_price_at_max_scan * 1 * 100) - (max_spread_row_scan['spy_price'] * QTY_RATIO * 100)
                else:
                    credit_scan = (max_spread_row_scan['spy_price'] * QTY_RATIO * 100) - (spx_price_at_max_scan * 1 * 100)

                # Convert time to ET for display
                max_time_et_scan = max_spread_row_scan['time'].tz_convert('America/New_York').strftime('%H:%M')
                best_worst_time_et_scan = best_worst_row_scan['time'].tz_convert('America/New_York').strftime('%H:%M')

                # Recompute worst case using accurate grid search at the selected time
                best_worst_time = best_worst_row_scan['time']

                # Look up underlying SYM1/SYM2 prices at the best worst-case time
                spy_at_time = spy_df.iloc[(spy_df['time'] - best_worst_time).abs().argsort()[:1]]
                spx_at_time = spx_df.iloc[(spx_df['time'] - best_worst_time).abs().argsort()[:1]]
                entry_spy_price_scan = spy_at_time['close'].iloc[0]
                entry_spx_price_scan = spx_at_time['close'].iloc[0]

                # Look up option prices at the best worst-case time
                # Use midpoint from BID_ASK data when available
                if _using_midpoint:
                    spy_ba_at_time = spy_ba.iloc[(spy_ba['time'] - best_worst_time).abs().argsort()[:1]]
                    spx_ba_at_time = spx_ba.iloc[(spx_ba['time'] - best_worst_time).abs().argsort()[:1]]
                    spy_opt_price_scan = spy_ba_at_time['midpoint'].iloc[0]
                    spx_opt_price_scan = spx_ba_at_time['midpoint'].iloc[0]
                else:
                    spy_opt_at_time = spy_opt.iloc[(spy_opt['time'] - best_worst_time).abs().argsort()[:1]]
                    spx_opt_at_time = spx_opt.iloc[(spx_opt['time'] - best_worst_time).abs().argsort()[:1]]
                    spy_opt_price_scan = spy_opt_at_time[_sc_price_col].iloc[0]
                    spx_opt_price_scan = spx_opt_at_time[_sc_price_col].iloc[0]

                # Determine sell/buy setup based on spread direction and scanner_right
                scan_direction = f'Sell {SYM2}' if max_spread_row_scan['spread'] > 0 else f'Sell {SYM1}'

                # Set up parameters for grid search (only the scanned option type)
                scan_show_calls = (scanner_right == 'C')
                scan_show_puts = (scanner_right == 'P')

                if scanner_right == 'P':
                    if scan_direction == f'Sell {SYM2}':
                        # Sell SYM2 put, Buy SYM1 put
                        scan_put_direction = f"Buy {SYM1}, Sell {SYM2}"
                        scan_sell_put_price = spx_opt_price_scan
                        scan_buy_put_price = spy_opt_price_scan
                        scan_sell_puts_qty = 1
                        scan_buy_puts_qty = QTY_RATIO
                    else:
                        # Sell SYM1 put, Buy SYM2 put
                        scan_put_direction = f"Sell {SYM1}, Buy {SYM2}"
                        scan_sell_put_price = spy_opt_price_scan
                        scan_buy_put_price = spx_opt_price_scan
                        scan_sell_puts_qty = QTY_RATIO
                        scan_buy_puts_qty = 1
                    scan_call_direction = f"Sell {SYM2}, Buy {SYM1}"  # unused
                    scan_sell_call_price = 0.0
                    scan_buy_call_price = 0.0
                    scan_sell_calls_qty = 0
                    scan_buy_calls_qty = 0
                else:  # Calls
                    if scan_direction == f'Sell {SYM2}':
                        # Sell SYM2 call, Buy SYM1 call
                        scan_call_direction = f"Sell {SYM2}, Buy {SYM1}"
                        scan_sell_call_price = spx_opt_price_scan
                        scan_buy_call_price = spy_opt_price_scan
                        scan_sell_calls_qty = 1
                        scan_buy_calls_qty = QTY_RATIO
                    else:
                        # Sell SYM1 call, Buy SYM2 call
                        scan_call_direction = f"Buy {SYM2}, Sell {SYM1}"
                        scan_sell_call_price = spy_opt_price_scan
                        scan_buy_call_price = spx_opt_price_scan
                        scan_sell_calls_qty = QTY_RATIO
                        scan_buy_calls_qty = 1
                    scan_put_direction = f"Sell {SYM1}, Buy {SYM2}"  # unused
                    scan_sell_put_price = 0.0
                    scan_buy_put_price = 0.0
                    scan_sell_puts_qty = 0
                    scan_buy_puts_qty = 0

                _, accurate_worst = calculate_best_worst_case_with_basis_drift(
                    entry_spy_price=entry_spy_price_scan,
                    entry_spx_price=entry_spx_price_scan,
                    spy_strike=spy_s,
                    spx_strike=spx_s,
                    call_direction=scan_call_direction,
                    put_direction=scan_put_direction,
                    sell_call_price=scan_sell_call_price,
                    buy_call_price=scan_buy_call_price,
                    sell_calls_qty=scan_sell_calls_qty,
                    buy_calls_qty=scan_buy_calls_qty,
                    sell_put_price=scan_sell_put_price,
                    buy_put_price=scan_buy_put_price,
                    sell_puts_qty=scan_sell_puts_qty,
                    buy_puts_qty=scan_buy_puts_qty,
                    show_calls=scan_show_calls,
                    show_puts=scan_show_puts,
                    sym1=SYM1, sym2=SYM2,
                )
                accurate_worst_pnl = accurate_worst.get('net_pnl', best_worst_row_scan['worst_case_pnl'])

                # Liquidity status
                _liq_ok = spy_total_vol >= min_volume and spx_total_vol >= min_volume
                _liq_label = "OK" if _liq_ok else "LOW"

                results.append({
                    f'{SYM1} Strike': int(spy_s),
                    f'{SYM2} Strike': int(spx_s),
                    'Moneyness': f"{spy_moneyness_scan:+.2f}%",
                    'Max Gap': abs(max_spread_row_scan['spread']),
                    'Max Gap $': f"${abs(max_spread_row_scan['spread']):.2f}",
                    'Max Gap Time': max_time_et_scan,
                    'Credit': credit_scan,
                    'Credit $': f"${credit_scan:,.0f}",
                    'Best Worst-Case': accurate_worst_pnl,
                    'Best WC $': f"${accurate_worst_pnl:,.0f}",
                    'Best WC Time': best_worst_time_et_scan,
                    'Direction': scan_direction,
                    f'{SYM1} Vol': spy_total_vol,
                    f'{SYM2} Vol': spx_total_vol,
                    'Liquidity': _liq_label,
                    'Price Source': 'midpoint' if _using_midpoint else 'trade',
                    'Risk/Reward': (credit_scan / abs(accurate_worst_pnl)) if accurate_worst_pnl < 0 else float('inf'),
                    'Risk/Reward $': f"{'∞' if accurate_worst_pnl >= 0 else f'{credit_scan / abs(accurate_worst_pnl):.1f}x'}",
                    'Max Risk': min(accurate_worst_pnl, 0),
                    'Max Risk $': f"${accurate_worst_pnl:,.0f}" if accurate_worst_pnl < 0 else "None",
                })

            progress_bar.empty()
            status_text.empty()

            if results:
                df_results = pd.DataFrame(results)

                # Sort by best worst-case (descending)
                df_results = df_results.sort_values('Best Worst-Case', ascending=False)

                # Store in session state for persistence after Apply
                st.session_state.scan_results = df_results.to_dict('records')

                # Highlight the best opportunity
                best_row = df_results.iloc[0]

                st.success(f"🏆 **BEST OPPORTUNITY: {SYM1} {best_row[f'{SYM1} Strike']} / {SYM2} {best_row[f'{SYM2} Strike']}**")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Max Credit", best_row['Credit $'])
                with col2:
                    st.metric("Best Worst-Case", best_row['Best WC $'],
                             delta="SAFE" if best_row['Best Worst-Case'] > 0 else "RISK")
                with col3:
                    st.metric("Best Entry Time", best_row['Best WC Time'])
                with col4:
                    st.metric("Direction", best_row['Direction'])

                st.markdown("---")

                # Show which strikes have guaranteed profit
                safe_strikes = df_results[df_results['Best Worst-Case'] > 0]
                if not safe_strikes.empty:
                    st.success(f"✅ **{len(safe_strikes)} strike pairs have GUARANTEED profit** (worst-case > $0)")
                else:
                    st.warning("⚠️ No strike pairs have guaranteed profit with current data")

                # Helper to render a ranked table with Apply buttons
                def _render_ranked_table(df_sorted, key_prefix, highlight_col, highlight_label):
                    st.caption("Click **Apply** to load strikes into sidebar and view in Price Overlay tab")

                    header_cols = st.columns([1, 1, 1, 1.2, 1, 1, 1, 0.8, 0.8, 1])
                    headers = [SYM1, SYM2, 'Moneyness', 'Credit', highlight_label, 'R/R', 'Dir', f'{SYM1} Vol', f'{SYM2} Vol', 'Action']
                    for col, header in zip(header_cols, headers):
                        col.markdown(f"**{header}**")

                    for idx, row in df_sorted.head(15).iterrows():
                        cols = st.columns([1, 1, 1, 1.2, 1, 1, 1, 0.8, 0.8, 1])
                        is_safe = row['Best Worst-Case'] > 0

                        cols[0].write(f"{row[f'{SYM1} Strike']}")
                        cols[1].write(f"{row[f'{SYM2} Strike']}")
                        cols[2].write(row['Moneyness'])
                        cols[3].write(row['Credit $'])

                        if is_safe:
                            cols[4].write(f"✅ {row['Best WC $']}")
                        else:
                            cols[4].write(f"⚠️ {row['Best WC $']}")

                        cols[5].write(row['Risk/Reward $'])
                        cols[6].write(row['Direction'])

                        spy_vol = row.get(f'{SYM1} Vol', 'N/A')
                        spx_vol = row.get(f'{SYM2} Vol', 'N/A')
                        cols[7].write(f"{spy_vol}" if isinstance(spy_vol, int) and spy_vol >= min_volume else f":red[{spy_vol}]")
                        cols[8].write(f"{spx_vol}" if isinstance(spx_vol, int) and spx_vol >= min_volume else f":red[{spx_vol}]")

                        cols[9].button(
                            "Apply",
                            key=f"{key_prefix}_{row[f'{SYM1} Strike']}_{row[f'{SYM2} Strike']}",
                            type="primary" if is_safe else "secondary",
                            on_click=_apply_scanner_result,
                            args=(int(row[f'{SYM1} Strike']), int(row[f'{SYM2} Strike']),
                                  row['Direction'], row['Best WC Time'], scanner_right),
                        )

                # Create three sorted views
                df_by_safety = df_results.sort_values('Best Worst-Case', ascending=False)
                df_by_profit = df_results.sort_values('Credit', ascending=False)
                df_by_rr = df_results.sort_values('Risk/Reward', ascending=False)

                tab_safety, tab_profit, tab_rr = st.tabs([
                    "🛡️ Ranked by Safety",
                    "💰 Ranked by Profit",
                    "⚖️ Ranked by Risk/Reward",
                ])

                with tab_safety:
                    st.subheader("📊 All Strike Pairs Ranked by Safety")
                    st.caption("Sorted by best worst-case P&L (highest first)")
                    _render_ranked_table(df_by_safety, "apply_safety", 'Worst Case', 'Worst Case')

                with tab_profit:
                    st.subheader("📊 All Strike Pairs Ranked by Profit")
                    st.caption("Sorted by maximum credit received (highest first)")
                    _render_ranked_table(df_by_profit, "apply_profit", 'Credit', 'Worst Case')

                with tab_rr:
                    st.subheader("📊 All Strike Pairs Ranked by Risk/Reward")
                    st.caption("Sorted by credit ÷ max risk (highest ratio first). ∞ = no risk (worst-case is profitable)")
                    _render_ranked_table(df_by_rr, "apply_rr", 'Risk/Reward', 'Worst Case')

                # Show full table in expander
                with st.expander("📋 View Full Table (all strikes)"):
                    display_cols = [f'{SYM1} Strike', f'{SYM2} Strike', 'Moneyness', 'Credit $', 'Max Gap Time',
                                   'Best WC $', 'Best WC Time', 'Direction', 'Risk/Reward $', 'Max Risk $',
                                   f'{SYM1} Vol', f'{SYM2} Vol', 'Liquidity', 'Price Source']
                    available_cols = [c for c in display_cols if c in df_results.columns]
                    st.dataframe(df_by_safety[available_cols], use_container_width=True, hide_index=True)

                # Export scanner results as JSON
                scanner_export = {
                    "view": "strike_scanner",
                    "date": selected_date,
                    "option_type": scanner_right,
                    "open_prices": {
                        "spy": float(open_spy),
                        "spx": float(open_spx),
                        "ratio": float(open_ratio)
                    },
                    "filters": {
                        "hide_illiquid": hide_illiquid,
                        "min_volume": int(min_volume)
                    },
                    "total_pairs_scanned": total_pairs,
                    "results_count": len(df_results),
                    "best_opportunity": {
                        "spy_strike": int(best_row[f'{SYM1} Strike']),
                        "spx_strike": int(best_row[f'{SYM2} Strike']),
                        "moneyness": best_row['Moneyness'],
                        "credit": float(best_row['Credit']),
                        "best_worst_case": float(best_row['Best Worst-Case']),
                        "best_wc_time": best_row['Best WC Time'],
                        "direction": best_row['Direction'],
                        "spy_volume": int(best_row.get(f'{SYM1} Vol', 0)),
                        "spx_volume": int(best_row.get(f'{SYM2} Vol', 0)),
                        "price_source": best_row.get('Price Source', 'trade')
                    },
                    "all_results": [
                        {
                            "spy_strike": int(r[f'{SYM1} Strike']),
                            "spx_strike": int(r[f'{SYM2} Strike']),
                            "moneyness": r['Moneyness'],
                            "max_gap": float(r['Max Gap']),
                            "max_gap_time": r['Max Gap Time'],
                            "credit": float(r['Credit']),
                            "best_worst_case": float(r['Best Worst-Case']),
                            "best_wc_time": r['Best WC Time'],
                            "direction": r['Direction'],
                            "spy_volume": int(r.get(f'{SYM1} Vol', 0)),
                            "spx_volume": int(r.get(f'{SYM2} Vol', 0)),
                            "liquidity": r.get('Liquidity', 'N/A'),
                            "price_source": r.get('Price Source', 'trade')
                        }
                        for _, r in df_results.iterrows()
                    ]
                }
                scanner_json = json.dumps(scanner_export, indent=2)
                st.download_button(
                    label="Export Scanner Results (JSON)",
                    data=scanner_json,
                    file_name=f"scanner_{selected_date}_{scanner_right}.json",
                    mime="application/json",
                    help="Download all scanner results with strike pairs, credits, and worst-case analysis as JSON"
                )

                st.markdown("---")
                st.info("💡 After clicking **Apply**, go to the **📊 Historical Analysis** tab to deep dive!")

            else:
                st.warning("No valid strike pairs found with sufficient data")

        # Display stored results if they exist (after Apply button was clicked)
        elif st.session_state.get('scan_results') is not None:
            df_results = pd.DataFrame(st.session_state.scan_results)

            # Show the best opportunity
            best_row = df_results.iloc[0]

            st.success(f"🏆 **BEST OPPORTUNITY: {SYM1} {best_row[f'{SYM1} Strike']} / {SYM2} {best_row[f'{SYM2} Strike']}**")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Max Credit", best_row['Credit $'])
            with col2:
                st.metric("Best Worst-Case", best_row['Best WC $'],
                         delta="SAFE" if best_row['Best Worst-Case'] > 0 else "RISK")
            with col3:
                st.metric("Best Entry Time", best_row['Best WC Time'])
            with col4:
                st.metric("Direction", best_row['Direction'])

            st.markdown("---")

            # Show which strikes have guaranteed profit
            safe_strikes = df_results[df_results['Best Worst-Case'] > 0]
            if not safe_strikes.empty:
                st.success(f"✅ **{len(safe_strikes)} strike pairs have GUARANTEED profit** (worst-case > $0)")
            else:
                st.warning("⚠️ No strike pairs have guaranteed profit with current data")

            # Helper to render stored results table
            _has_vol_cols = f'{SYM1} Vol' in df_results.columns
            _has_rr_cols = 'Risk/Reward' in df_results.columns

            def _render_stored_table(df_sorted, key_prefix):
                st.caption("Click **Apply** to load strikes into sidebar and view in Historical Analysis tab")

                if _has_vol_cols:
                    header_cols = st.columns([1, 1, 1, 1.2, 1, 1, 1, 0.8, 0.8, 1])
                    headers = [SYM1, SYM2, 'Moneyness', 'Credit', 'Worst Case', 'R/R', 'Dir', f'{SYM1} Vol', f'{SYM2} Vol', 'Action']
                else:
                    header_cols = st.columns([1, 1, 1, 1.2, 1, 1, 1, 1])
                    headers = [SYM1, SYM2, 'Moneyness', 'Credit', 'Worst Case', 'R/R', 'Direction', 'Action']
                for col, header in zip(header_cols, headers):
                    col.markdown(f"**{header}**")

                for idx, row in df_sorted.head(15).iterrows():
                    is_safe = row['Best Worst-Case'] > 0

                    if _has_vol_cols:
                        cols = st.columns([1, 1, 1, 1.2, 1, 1, 1, 0.8, 0.8, 1])
                        cols[0].write(f"{row[f'{SYM1} Strike']}")
                        cols[1].write(f"{row[f'{SYM2} Strike']}")
                        cols[2].write(row['Moneyness'])
                        cols[3].write(row['Credit $'])
                        cols[4].write(f"{'✅' if is_safe else '⚠️'} {row['Best WC $']}")
                        cols[5].write(row.get('Risk/Reward $', 'N/A'))
                        cols[6].write(row['Direction'])
                        cols[7].write(f"{row[f'{SYM1} Vol']}")
                        cols[8].write(f"{row[f'{SYM2} Vol']}")
                        btn_col = cols[9]
                    else:
                        cols = st.columns([1, 1, 1, 1.2, 1, 1, 1, 1])
                        cols[0].write(f"{row[f'{SYM1} Strike']}")
                        cols[1].write(f"{row[f'{SYM2} Strike']}")
                        cols[2].write(row['Moneyness'])
                        cols[3].write(row['Credit $'])
                        cols[4].write(f"{'✅' if is_safe else '⚠️'} {row['Best WC $']}")
                        cols[5].write(row.get('Risk/Reward $', 'N/A'))
                        cols[6].write(row['Direction'])
                        btn_col = cols[7]

                    btn_col.button(
                        "Apply",
                        key=f"{key_prefix}_{row[f'{SYM1} Strike']}_{row[f'{SYM2} Strike']}",
                        type="primary" if is_safe else "secondary",
                        on_click=_apply_scanner_result,
                        args=(int(row[f'{SYM1} Strike']), int(row[f'{SYM2} Strike']),
                              row['Direction'], row['Best WC Time'], scanner_right),
                    )

            # Create sorted views
            df_by_safety = df_results.sort_values('Best Worst-Case', ascending=False)
            df_by_profit = df_results.sort_values('Credit', ascending=False)
            if _has_rr_cols:
                df_by_rr = df_results.sort_values('Risk/Reward', ascending=False)
            else:
                df_by_rr = df_by_safety  # fallback for old data without R/R

            tab_safety, tab_profit, tab_rr = st.tabs([
                "🛡️ Ranked by Safety",
                "💰 Ranked by Profit",
                "⚖️ Ranked by Risk/Reward",
            ])

            with tab_safety:
                st.subheader("📊 All Strike Pairs Ranked by Safety")
                st.caption("Sorted by best worst-case P&L (highest first)")
                _render_stored_table(df_by_safety, "stored_safety")

            with tab_profit:
                st.subheader("📊 All Strike Pairs Ranked by Profit")
                st.caption("Sorted by maximum credit received (highest first)")
                _render_stored_table(df_by_profit, "stored_profit")

            with tab_rr:
                st.subheader("📊 All Strike Pairs Ranked by Risk/Reward")
                st.caption("Sorted by credit ÷ max risk (highest ratio first). ∞ = no risk")
                _render_stored_table(df_by_rr, "stored_rr")

            # Export stored scanner results as JSON
            stored_best_row = df_results.iloc[0]
            stored_scanner_export = {
                "view": "strike_scanner",
                "date": selected_date,
                "option_type": scanner_right,
                "open_prices": {
                    "spy": float(open_spy),
                    "spx": float(open_spx),
                    "ratio": float(open_ratio)
                },
                "results_count": len(df_results),
                "best_opportunity": {
                    "spy_strike": int(stored_best_row[f'{SYM1} Strike']),
                    "spx_strike": int(stored_best_row[f'{SYM2} Strike']),
                    "moneyness": stored_best_row['Moneyness'],
                    "credit": float(stored_best_row['Credit']),
                    "best_worst_case": float(stored_best_row['Best Worst-Case']),
                    "best_wc_time": stored_best_row['Best WC Time'],
                    "direction": stored_best_row['Direction'],
                    "spy_volume": int(stored_best_row.get(f'{SYM1} Vol', 0)),
                    "spx_volume": int(stored_best_row.get(f'{SYM2} Vol', 0)),
                    "price_source": stored_best_row.get('Price Source', 'trade')
                },
                "all_results": [
                    {
                        "spy_strike": int(r[f'{SYM1} Strike']),
                        "spx_strike": int(r[f'{SYM2} Strike']),
                        "moneyness": r['Moneyness'],
                        "max_gap": float(r['Max Gap']),
                        "max_gap_time": r['Max Gap Time'],
                        "credit": float(r['Credit']),
                        "best_worst_case": float(r['Best Worst-Case']),
                        "best_wc_time": r['Best WC Time'],
                        "direction": r['Direction'],
                        "spy_volume": int(r.get(f'{SYM1} Vol', 0)),
                        "spx_volume": int(r.get(f'{SYM2} Vol', 0)),
                        "liquidity": r.get('Liquidity', 'N/A'),
                        "price_source": r.get('Price Source', 'trade')
                    }
                    for _, r in df_results.iterrows()
                ]
            }
            stored_scanner_json = json.dumps(stored_scanner_export, indent=2)
            st.download_button(
                label="Export Scanner Results (JSON)",
                data=stored_scanner_json,
                file_name=f"scanner_{selected_date}_{scanner_right}.json",
                mime="application/json",
                help="Download all scanner results with strike pairs, credits, and worst-case analysis as JSON"
            )

            st.markdown("---")
            st.info("💡 After clicking **Apply**, go to the **📊 Historical Analysis** tab to deep dive!")
