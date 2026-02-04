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

# P&L calculation functions
def calculate_option_pnl(entry_price, exit_price, action, quantity):
    """Calculate P&L for an option position"""
    if action == 'BUY':
        return (exit_price - entry_price) * quantity * 100
    else:  # SELL
        return (entry_price - exit_price) * quantity * 100

def calculate_settlement_value(underlying_price, strike, right):
    """Calculate intrinsic value at settlement"""
    if right == 'C':
        return max(0, underlying_price - strike)
    else:  # Put
        return max(0, strike - underlying_price)

def get_option_price_from_db(df_options, symbol, strike, right, entry_time):
    """
    Look up option price from database at specified time.
    If exact time not found, returns price from nearest available time >= entry_time.

    Args:
        df_options: DataFrame with columns [symbol, strike, right, time, open, high, low, close, volume]
        symbol: 'SPY' or 'SPX'
        strike: Strike price (e.g., 698 for SPY, 6985 for SPX)
        right: 'C' for call, 'P' for put
        entry_time: pandas Timestamp for entry time

    Returns:
        float: Option price from database (open price at entry time or nearest after)
        None if contract not found in database
    """
    # Filter to contract (symbol, strike, right)
    contract_mask = (
        (df_options['symbol'] == symbol) &
        (df_options['strike'] == strike) &
        (df_options['right'] == right)
    )

    contract_data = df_options[contract_mask]

    if len(contract_data) == 0:
        # Contract doesn't exist in database at all
        return None

    # Try exact time match first
    exact_match = contract_data[contract_data['time'] == entry_time]
    if len(exact_match) > 0:
        return exact_match.iloc[0]['open']

    # If no exact match, find nearest timestamp >= entry_time
    future_data = contract_data[contract_data['time'] >= entry_time]
    if len(future_data) > 0:
        # Use first available data point after entry time
        nearest = future_data.sort_values('time').iloc[0]
        return nearest['open']

    # If no future data, use the last available data point
    # (This handles case where entry_time is after all data)
    nearest = contract_data.sort_values('time').iloc[-1]
    return nearest['open']

# Page config
st.set_page_config(
    page_title="0DTE Strategy Calculator",
    page_icon="📊",
    layout="wide"
)

st.title("📊 SPY/SPX 0DTE Strategy Calculator")

# Create tabs
tab1, tab2 = st.tabs(["📊 Historical Analysis", "🔴 Live Paper Trading"])

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
    st.sidebar.success(f"✅ Loaded {len(df_options)} option price records")
else:
    st.sidebar.warning(f"⚠️  Option price database not found: {OPTIONS_FILE}")
    st.sidebar.info("Calculator will show error if strike prices are changed")

# Load best combo data (for default values)
BEST_COMBO_FILE = '/tmp/best_combo.json'
best_combo = {}
if os.path.exists(BEST_COMBO_FILE):
    with open(BEST_COMBO_FILE) as f:
        best_combo = json.load(f)

spy_df = df_underlying[df_underlying['symbol'] == 'SPY'].copy()
spx_df = df_underlying[df_underlying['symbol'] == 'SPX'].copy()

if spy_df.empty or spx_df.empty:
    st.error("No SPY or SPX data found in file")
    st.stop()

st.sidebar.success(f"✅ Loaded data for {selected_date}")

# Data collection button
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Collection")

# Initialize session state for tracking background collection
if 'collection_status' not in st.session_state:
    st.session_state.collection_status = {}

collection_key = f"collection_{selected_date}"

if st.sidebar.button("🔄 Update Data for Selected Date", use_container_width=True, help="Fetch missing data incrementally (only new bars since last update)"):
    import subprocess

    try:
        # Start background collection process
        process = subprocess.Popen(
            ['/usr/bin/python3', 'collect_market_data.py', '--date', selected_date],
            cwd='/Users/johnnyhuang/personal/optionsarbitrage',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
time_labels = spy_df['time_label'].tolist()

# Convert to ET for display
st.sidebar.subheader("Entry Time")
entry_time_idx = st.sidebar.slider(
    "Select Entry Time",
    0,
    len(time_labels) - 1,
    0,  # Default to market open
    format=""
)

entry_time_label = time_labels[entry_time_idx]
st.sidebar.write(f"**{entry_time_label}**")

# Get prices at entry time using index
entry_spy = spy_df.iloc[entry_time_idx]
entry_spx = spx_df.iloc[entry_time_idx]

st.sidebar.metric("SPY Price", f"${entry_spy['close']:.2f}")
st.sidebar.metric("SPX Price", f"${entry_spx['close']:.2f}")

# Strike configuration
st.sidebar.subheader("🎯 Strike Configuration")

# Get current prices at market open for default strike selection
entry_spy_open = spy_df.iloc[0]['close']
entry_spx_open = spx_df.iloc[0]['close']

# Default strikes from best_combo or calculated from current price
default_spy_strike = best_combo.get('spy_strike', int(round(entry_spy_open)))
default_spx_strike = best_combo.get('spx_strike', int(round(entry_spx_open / 5) * 5))

# Strike selection with range based on current prices
spy_min_strike = int(entry_spy_open * 0.95)
spy_max_strike = int(entry_spy_open * 1.05)
spx_min_strike = int((entry_spx_open * 0.95) / 5) * 5
spx_max_strike = int((entry_spx_open * 1.05) / 5) * 5

spy_strike = st.sidebar.number_input(
    "SPY Strike",
    min_value=spy_min_strike,
    max_value=spy_max_strike,
    value=default_spy_strike,
    step=1,
    help="Strike price for SPY options"
)

spx_strike = st.sidebar.number_input(
    "SPX Strike",
    min_value=int(spx_min_strike),
    max_value=int(spx_max_strike),
    value=default_spx_strike,
    step=5,
    help="Strike price for SPX options (typically increments of 5)"
)

# STRIKE MONEYNESS CHECKER
# Calculate moneyness (% from underlying at entry time)
spy_moneyness_pct = ((spy_strike - entry_spy['close']) / entry_spy['close']) * 100
spx_moneyness_pct = ((spx_strike - entry_spx['close']) / entry_spx['close']) * 100
moneyness_diff = abs(spy_moneyness_pct - spx_moneyness_pct)

# Display moneyness analysis
with st.sidebar.expander("⚠️ Strike Moneyness Check", expanded=(moneyness_diff > 0.05)):
    st.caption(f"**SPY Strike {spy_strike}:**")
    st.caption(f"  {spy_moneyness_pct:+.4f}% from entry price ${entry_spy['close']:.2f}")

    st.caption(f"**SPX Strike {spx_strike}:**")
    st.caption(f"  {spx_moneyness_pct:+.4f}% from entry price ${entry_spx['close']:.2f}")

    st.caption(f"**Moneyness Difference: {moneyness_diff:.4f}%**")

    if moneyness_diff > 0.05:
        st.warning(f"⚠️ **Strikes are mismatched by {moneyness_diff:.2f}%**\n\nThis creates basis risk! Even if SPY/SPX move perfectly in sync, the different moneyness levels will cause asymmetric P&L.")

        # Suggest better matched strikes
        # Find SPX strike that matches SPY moneyness
        target_spx_strike = entry_spx['close'] * (1 + spy_moneyness_pct / 100)
        suggested_spx = round(target_spx_strike / 5) * 5

        # Find SPY strike that matches SPX moneyness
        target_spy_strike = entry_spy['close'] * (1 + spx_moneyness_pct / 100)
        suggested_spy = round(target_spy_strike)

        st.info(f"**Suggested matched strikes:**\n- Keep SPY {spy_strike}, use SPX {int(suggested_spx)} ({spy_moneyness_pct:+.2f}%)\n- OR: Keep SPX {spx_strike}, use SPY {int(suggested_spy)} ({spx_moneyness_pct:+.2f}%)")
    else:
        st.success(f"✅ Strikes are well-matched (within 0.05%)")

# Strategy direction configuration
st.sidebar.subheader("📊 Strategy Direction")

call_direction_options = [
    "Sell SPX, Buy SPY",
    "Buy SPX, Sell SPY"
]
put_direction_options = [
    "Sell SPY, Buy SPX",
    "Buy SPY, Sell SPX"
]

default_call_direction = best_combo.get('call_direction', call_direction_options[0])
default_put_direction = best_combo.get('put_direction', put_direction_options[0])

call_direction = st.sidebar.selectbox(
    "Call Spread Direction",
    call_direction_options,
    index=call_direction_options.index(default_call_direction) if default_call_direction in call_direction_options else 0,
    help="Direction for call spread"
)

put_direction = st.sidebar.selectbox(
    "Put Spread Direction",
    put_direction_options,
    index=put_direction_options.index(default_put_direction) if default_put_direction in put_direction_options else 0,
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

if df_options is not None:
    # Look up all four option legs from database
    spy_call_price = get_option_price_from_db(df_options, 'SPY', spy_strike, 'C', entry_time)
    spx_call_price = get_option_price_from_db(df_options, 'SPX', spx_strike, 'C', entry_time)
    spy_put_price = get_option_price_from_db(df_options, 'SPY', spy_strike, 'P', entry_time)
    spx_put_price = get_option_price_from_db(df_options, 'SPX', spx_strike, 'P', entry_time)

    # Check if all prices were found
    missing_prices = []
    if spy_call_price is None:
        missing_prices.append(f"SPY {spy_strike}C")
    if spx_call_price is None:
        missing_prices.append(f"SPX {spx_strike}C")
    if spy_put_price is None:
        missing_prices.append(f"SPY {spy_strike}P")
    if spx_put_price is None:
        missing_prices.append(f"SPX {spx_strike}P")

    if missing_prices:
        st.error(f"❌ Option prices not found in database for: {', '.join(missing_prices)}")
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
else:
    # No database available - will show error in Tab 1 only
    # Don't call st.stop() here - let Tab 2 remain accessible
    pass

# Option prices from database (only show in sidebar if data exists)
if df_options is not None:
    st.sidebar.subheader("📊 Database Option Prices")
    st.sidebar.info(f"Real market prices at {entry_time_label}")
    with st.sidebar.expander("Call Prices", expanded=True):
        st.write(f"**SPY {spy_strike}C:** ${estimated_spy_call:.2f}")
        st.write(f"**SPX {spx_strike}C:** ${estimated_spx_call:.2f}")

    with st.sidebar.expander("Put Prices", expanded=True):
        st.write(f"**SPY {spy_strike}P:** ${estimated_spy_put:.2f}")
        st.write(f"**SPX {spx_strike}P:** ${estimated_spx_put:.2f}")

# Tab 1: Historical Analysis
with tab1:
    st.markdown("Using **real market prices** from historical trades")

    # Check if options data is available for this tab
    if df_options is None:
        st.error("❌ Option price database not found. Cannot display historical analysis.")
        st.info(f"**Required file:** {OPTIONS_FILE}")
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

        selected_strategy = st.selectbox(
            "Select Strategy",
            strategy_options,
            index=0,
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
                if call_direction == "Buy SPX, Sell SPY":
                    # Sell SPY calls, Buy SPX calls
                    sell_label_calls = "Sell SPY Calls"
                    buy_label_calls = "Buy SPX Calls"
                    sell_strike_calls = spy_strike
                    buy_strike_calls = spx_strike
                    sell_price_calls = estimated_spy_call
                    buy_price_calls = estimated_spx_call
                    default_sell_qty = 100
                    default_buy_qty = 10
                else:  # "Sell SPX, Buy SPY"
                    # Sell SPX calls, Buy SPY calls
                    sell_label_calls = "Sell SPX Calls"
                    buy_label_calls = "Buy SPY Calls"
                    sell_strike_calls = spx_strike
                    buy_strike_calls = spy_strike
                    sell_price_calls = estimated_spx_call
                    buy_price_calls = estimated_spy_call
                    default_sell_qty = 10
                    default_buy_qty = 100

                # Quantities
                sell_calls_qty = st.number_input(sell_label_calls, 1, 1000, default_sell_qty, key=f"sell_c_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}")
                buy_calls_qty = st.number_input(buy_label_calls, 1, 1000, default_buy_qty, key=f"buy_c_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}")

                # Prices (use estimated prices that update with slider, strikes, and direction)
                sell_call_price = st.number_input(
                    f"{sell_label_calls.replace('Calls', '')}@ ${sell_price_calls:.2f}",
                    0.0, 100.0, float(sell_price_calls), 0.01,
                    key=f"sell_c_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
                )

                buy_call_price = st.number_input(
                    f"{buy_label_calls.replace('Calls', '')}@ ${buy_price_calls:.2f}",
                    0.0, 100.0, float(buy_price_calls), 0.01,
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
                if put_direction == "Buy SPY, Sell SPX":
                    # Buy SPY puts, Sell SPX puts
                    sell_label_puts = "Sell SPX Puts"
                    buy_label_puts = "Buy SPY Puts"
                    sell_strike_puts = spx_strike
                    buy_strike_puts = spy_strike
                    sell_price_puts = estimated_spx_put
                    buy_price_puts = estimated_spy_put
                    default_sell_qty_puts = 10
                    default_buy_qty_puts = 100
                else:  # "Sell SPY, Buy SPX"
                    # Sell SPY puts, Buy SPX puts
                    sell_label_puts = "Sell SPY Puts"
                    buy_label_puts = "Buy SPX Puts"
                    sell_strike_puts = spy_strike
                    buy_strike_puts = spx_strike
                    sell_price_puts = estimated_spy_put
                    buy_price_puts = estimated_spx_put
                    default_sell_qty_puts = 100
                    default_buy_qty_puts = 10

                # Quantities
                sell_puts_qty = st.number_input(sell_label_puts, 1, 1000, default_sell_qty_puts, key=f"sell_p_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}")
                buy_puts_qty = st.number_input(buy_label_puts, 1, 1000, default_buy_qty_puts, key=f"buy_p_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}")

                # Prices (use estimated prices that update with slider, strikes, and direction)
                sell_put_price = st.number_input(
                    f"{sell_label_puts.replace('Puts', '')}@ ${sell_price_puts:.2f}",
                    0.0, 100.0, float(sell_price_puts), 0.01,
                    key=f"sell_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"
                )

                buy_put_price = st.number_input(
                    f"{buy_label_puts.replace('Puts', '')}@ ${buy_price_puts:.2f}",
                    0.0, 100.0, float(buy_price_puts), 0.01,
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

        # Scenario Analysis
        st.header("Scenario Analysis")

        # Get EOD prices
        eod_spy = spy_df.iloc[-1]['close']
        eod_spx = spx_df.iloc[-1]['close']

        st.info(f"**Market Close:** SPY ${eod_spy:.2f}, SPX ${eod_spx:.2f}")

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
            if call_direction == "Buy SPX, Sell SPY":
                # Sell SPY calls, Buy SPX calls
                call_pnl = calculate_option_pnl(sell_call_price, spy_call_settle, 'SELL', sell_calls_qty)
                call_pnl += calculate_option_pnl(buy_call_price, spx_call_settle, 'BUY', buy_calls_qty)
            else:  # "Sell SPX, Buy SPY"
                # Sell SPX calls, Buy SPY calls
                call_pnl = calculate_option_pnl(sell_call_price, spx_call_settle, 'SELL', sell_calls_qty)
                call_pnl += calculate_option_pnl(buy_call_price, spy_call_settle, 'BUY', buy_calls_qty)

        if show_puts:
            # Determine which settlement values to use based on direction
            if put_direction == "Buy SPY, Sell SPX":
                # Sell SPX puts, Buy SPY puts
                put_pnl = calculate_option_pnl(sell_put_price, spx_put_settle, 'SELL', sell_puts_qty)
                put_pnl += calculate_option_pnl(buy_put_price, spy_put_settle, 'BUY', buy_puts_qty)
            else:  # "Sell SPY, Buy SPX"
                # Sell SPY puts, Buy SPX puts
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
            if call_direction == "Buy SPX, Sell SPY":
                # Sold SPY calls, Bought SPX calls
                call_settlement_cost = (spy_call_settle * sell_calls_qty * 100) - (spx_call_settle * buy_calls_qty * 100)
            else:
                # Sold SPX calls, Bought SPY calls
                call_settlement_cost = (spx_call_settle * sell_calls_qty * 100) - (spy_call_settle * buy_calls_qty * 100)

        if show_puts:
            if put_direction == "Buy SPY, Sell SPX":
                # Sold SPX puts, Bought SPY puts
                put_settlement_cost = (spx_put_settle * sell_puts_qty * 100) - (spy_put_settle * buy_puts_qty * 100)
            else:
                # Sold SPY puts, Bought SPX puts
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
        elif show_calls:
            total_call_pnl = call_credit + call_pnl
            st.metric("**Call P&L (Total)**", f"**${total_call_pnl:,.2f}**")
            st.caption(f"Initial Credit: +${call_credit:,.2f} | Settlement P&L: ${call_pnl:+,.2f}")
        else:  # show_puts
            total_put_pnl = put_credit + put_pnl
            st.metric("**Put P&L (Total)**", f"**${total_put_pnl:,.2f}**")
            st.caption(f"Initial Credit: +${put_credit:,.2f} | Settlement P&L: ${put_pnl:+,.2f}")

        # Detailed breakdown
        with st.expander("📋 Detailed Breakdown"):
            if show_calls:
                st.write("**Calls:**")
                if call_direction == "Buy SPX, Sell SPY":
                    st.write(f"- Sell {sell_calls_qty} SPY {spy_strike}C @ ${sell_call_price:.2f} → Settle @ ${spy_call_settle:.2f}")
                    st.write(f"- Buy {buy_calls_qty} SPX {spx_strike}C @ ${buy_call_price:.2f} → Settle @ ${spx_call_settle:.2f}")
                else:
                    st.write(f"- Sell {sell_calls_qty} SPX {spx_strike}C @ ${sell_call_price:.2f} → Settle @ ${spx_call_settle:.2f}")
                    st.write(f"- Buy {buy_calls_qty} SPY {spy_strike}C @ ${buy_call_price:.2f} → Settle @ ${spy_call_settle:.2f}")
                st.write(f"- Net: ${call_pnl:,.2f}")

            if show_puts:
                if show_calls:
                    st.write("")  # Add spacing
                st.write("**Puts:**")
            if put_direction == "Buy SPY, Sell SPX":
                st.write(f"- Sell {sell_puts_qty} SPX {spx_strike}P @ ${sell_put_price:.2f} → Settle @ ${spx_put_settle:.2f}")
                st.write(f"- Buy {buy_puts_qty} SPY {spy_strike}P @ ${buy_put_price:.2f} → Settle @ ${spy_put_settle:.2f}")
            else:
                st.write(f"- Sell {sell_puts_qty} SPY {spy_strike}P @ ${sell_put_price:.2f} → Settle @ ${spy_put_settle:.2f}")
                st.write(f"- Buy {buy_puts_qty} SPX {spx_strike}P @ ${buy_put_price:.2f} → Settle @ ${spx_put_settle:.2f}")
            st.write(f"- Net: ${put_pnl:,.2f}")

        # Price range sweep
        st.subheader("📈 P&L Across Price Range")
    
        # PREDICTIVE ANALYSIS: Use entry prices as center for range sweep
        # This shows what P&L WOULD BE if prices moved ±3% from entry, maintaining entry-time ratio
        # This is a PREDICTION based on entry-time information only, NOT using actual EOD values
        spy_range = np.linspace(entry_spy['close'] * 0.97, entry_spy['close'] * 1.03, 100)
        spx_range = spy_range * (entry_spx['close'] / entry_spy['close'])  # Maintain entry ratio
    
        pnl_results = []
    
        for spy_px, spx_px in zip(spy_range, spx_range):
            # Calculate settlement values
            spy_call_val = calculate_settlement_value(spy_px, spy_strike, 'C')
            spx_call_val = calculate_settlement_value(spx_px, spx_strike, 'C')
            spy_put_val = calculate_settlement_value(spy_px, spy_strike, 'P')
            spx_put_val = calculate_settlement_value(spx_px, spx_strike, 'P')
    
            # Call P&L (use same logic as in the P&L calculation section)
            c_pnl = 0.0
            if show_calls:
                if call_direction == "Buy SPX, Sell SPY":
                    c_pnl = calculate_option_pnl(sell_call_price, spy_call_val, 'SELL', sell_calls_qty)
                    c_pnl += calculate_option_pnl(buy_call_price, spx_call_val, 'BUY', buy_calls_qty)
                else:
                    c_pnl = calculate_option_pnl(sell_call_price, spx_call_val, 'SELL', sell_calls_qty)
                    c_pnl += calculate_option_pnl(buy_call_price, spy_call_val, 'BUY', buy_calls_qty)
    
            # Put P&L (use same logic as in the P&L calculation section)
            p_pnl = 0.0
            if show_puts:
                if put_direction == "Buy SPY, Sell SPX":
                    p_pnl = calculate_option_pnl(sell_put_price, spx_put_val, 'SELL', sell_puts_qty)
                    p_pnl += calculate_option_pnl(buy_put_price, spy_put_val, 'BUY', buy_puts_qty)
                else:
                    p_pnl = calculate_option_pnl(sell_put_price, spy_put_val, 'SELL', sell_puts_qty)
                    p_pnl += calculate_option_pnl(buy_put_price, spx_put_val, 'BUY', buy_puts_qty)
    
            # INCLUDE initial credit in total P&L (only for selected strategy)
            # Only include credit for the legs we're trading
            credit_to_include = 0.0
            if show_calls:
                credit_to_include += call_credit
            if show_puts:
                credit_to_include += put_credit
    
            total = credit_to_include + c_pnl + p_pnl
            pnl_results.append({
                'spy_price': spy_px,
                'spx_price': spx_px,
                'call_pnl': c_pnl,
                'put_pnl': p_pnl,
                'total_pnl': total
            })
    
        df_pnl = pd.DataFrame(pnl_results)
    
        # Create interactive plot
        # Adjust subtitle based on selected strategy
        if show_calls and show_puts:
            breakdown_title = 'Call vs Put P&L Breakdown'
        elif show_calls:
            breakdown_title = 'Call P&L Breakdown'
        else:  # show_puts
            breakdown_title = 'Put P&L Breakdown'
    
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Total P&L vs SPY Price', breakdown_title),
            vertical_spacing=0.15,
            row_heights=[0.6, 0.4]
        )
    
        # Total P&L
        fig.add_trace(
            go.Scatter(
                x=df_pnl['spy_price'],
                y=df_pnl['total_pnl'],
                mode='lines',
                name='Total P&L',
                line=dict(color='blue', width=3),
                fill='tozeroy',
                fillcolor='rgba(0, 100, 255, 0.1)'
            ),
            row=1, col=1
        )
    
        # Add entry price line (top position)
        fig.add_vline(
            x=entry_spy['close'],
            line_dash="dash",
            line_color="green",
            annotation=dict(
                text=f"Entry: ${entry_spy['close']:.2f}",
                yanchor="top",
                y=0.95
            ),
            row=1, col=1
        )
    
        # Add EOD price line if different from entry (middle position)
        if abs(eod_spy - entry_spy['close']) > 0.10:  # Only show if >$0.10 difference
            fig.add_vline(
                x=eod_spy,
                line_dash="dot",
                line_color="blue",
                annotation=dict(
                    text=f"EOD: ${eod_spy:.2f}",
                    yanchor="top",
                    y=0.85
                ),
                row=1, col=1
            )
    
        # Add strike lines - show BOTH SPY and SPX strikes
        # SPY strike line
        fig.add_vline(
            x=spy_strike,
            line_dash="dot",
            line_color="red",
            annotation=dict(
                text=f"SPY Strike: {spy_strike}",
                yanchor="top",
                y=0.75,
                xanchor="right"
            ),
            row=1, col=1
        )
    
        # SPX strike converted to SPY scale (using lockstep ratio)
        # At what SPY price would SPX hit its strike (if moving in lockstep)?
        ratio = entry_spx['close'] / entry_spy['close']
        spy_price_at_spx_strike = spx_strike / ratio
    
        # Only show separate line if strikes are mismatched
        if abs(spy_price_at_spx_strike - spy_strike) > 0.5:  # More than $0.50 apart
            fig.add_vline(
                x=spy_price_at_spx_strike,
                line_dash="dot",
                line_color="orange",
                annotation=dict(
                    text=f"SPX Strike: {spx_strike} (@ SPY {spy_price_at_spx_strike:.1f})",
                    yanchor="top",
                    y=0.65,
                    xanchor="left"
                ),
                row=1, col=1
            )
    
        # Add zero line
        fig.add_hline(
            y=0,
            line_dash="solid",
            line_color="gray",
            line_width=1,
            row=1, col=1
        )
    
        # Call and Put breakdown - only show selected strategies
        if show_calls:
            fig.add_trace(
                go.Scatter(
                    x=df_pnl['spy_price'],
                    y=df_pnl['call_pnl'],
                    mode='lines',
                    name='Call P&L',
                    line=dict(color='green', width=2)
                ),
                row=2, col=1
            )
    
        if show_puts:
            fig.add_trace(
                go.Scatter(
                    x=df_pnl['spy_price'],
                    y=df_pnl['put_pnl'],
                    mode='lines',
                    name='Put P&L',
                    line=dict(color='orange', width=2)
                ),
                row=2, col=1
            )
    
        # Add strike lines to breakdown chart too
        fig.add_vline(x=spy_strike, line_dash="dot", line_color="red", row=2, col=1)
        if abs(spy_price_at_spx_strike - spy_strike) > 0.5:
            fig.add_vline(x=spy_price_at_spx_strike, line_dash="dot", line_color="orange", row=2, col=1)
    
        # Add secondary x-axis for SPX prices (at top)
        # Calculate corresponding SPX values for the SPY range
        ratio = entry_spx['close'] / entry_spy['close']
    
        fig.update_xaxes(title_text="SPY Price ($)", row=2, col=1)
        fig.update_yaxes(title_text="P&L ($)", row=1, col=1)
        fig.update_yaxes(title_text="P&L ($)", row=2, col=1)
    
        # Add SPX price scale on top axis
        fig.update_layout(
            height=800,
            showlegend=True,
            hovermode='x unified',
            xaxis=dict(
                title="SPY Price ($)",
                side="bottom"
            ),
            xaxis2=dict(
                title="<b>SPY Price ($)</b> | SPX Price ($) [shown in hover]",
                side="bottom",
                overlaying="x",
                showgrid=False
            )
        )
    
        # Update hover template to show both SPY and SPX prices
        for trace in fig.data:
            if hasattr(trace, 'x'):
                trace.customdata = [[spy_px, spy_px * ratio] for spy_px in trace.x]
                trace.hovertemplate = (
                    '<b>SPY:</b> $%{customdata[0]:.2f}<br>'
                    '<b>SPX:</b> $%{customdata[1]:.2f}<br>'
                    '<b>P&L:</b> $%{y:,.0f}<br>'
                    '<extra></extra>'
                )
    
        # Statistics - Lockstep Movement (SPY and SPX move together with same %)
        # Since SPY and SPX track the same index, they CANNOT diverge significantly
        # Worst case is simply the minimum P&L when they move together in lockstep
        best_case_lockstep = df_pnl['total_pnl'].max()
        worst_case_lockstep = df_pnl['total_pnl'].min()
    
        # Find price levels where worst/best case occurs
        worst_case_idx = df_pnl['total_pnl'].idxmin()
        best_case_idx = df_pnl['total_pnl'].idxmax()
        worst_case_spy_price = df_pnl.iloc[worst_case_idx]['spy_price']
        best_case_spy_price = df_pnl.iloc[best_case_idx]['spy_price']
        worst_case_spx_price = df_pnl.iloc[worst_case_idx]['spx_price']
        best_case_spx_price = df_pnl.iloc[best_case_idx]['spx_price']
    
        # Add worst/best case shaded regions to the chart
        # Create a narrow band around worst/best case prices for visual highlighting
        worst_range_width = (entry_spy['close'] * 0.03) * 0.05  # 5% of the total ±3% range
        best_range_width = (entry_spy['close'] * 0.03) * 0.05
    
        # Add worst case shaded region (red/pink)
        fig.add_vrect(
            x0=worst_case_spy_price - worst_range_width,
            x1=worst_case_spy_price + worst_range_width,
            fillcolor="rgba(255, 0, 0, 0.2)",
            layer="below",
            line_width=0,
            row=1, col=1,
            annotation=dict(
                text=f"Worst Case<br>${worst_case_spy_price:.2f}",
                textangle=0,
                yanchor="top",
                y=0.95,
                xanchor="center",
                font=dict(size=10, color="red")
            )
        )
    
        # Add best case shaded region (green/lime)
        fig.add_vrect(
            x0=best_case_spy_price - best_range_width,
            x1=best_case_spy_price + best_range_width,
            fillcolor="rgba(0, 255, 0, 0.2)",
            layer="below",
            line_width=0,
            row=1, col=1,
            annotation=dict(
                text=f"Best Case<br>${best_case_spy_price:.2f}",
                textangle=0,
                yanchor="top",
                y=0.85,
                xanchor="center",
                font=dict(size=10, color="green")
            )
        )
    
        st.plotly_chart(fig, use_container_width=True)
    
        # Note about P&L calculation - show only relevant credit
        if show_calls and show_puts:
            credit_msg = f"${call_credit + put_credit:,.2f}"
        elif show_calls:
            credit_msg = f"${call_credit:,.2f} (calls only)"
        else:  # show_puts
            credit_msg = f"${put_credit:,.2f} (puts only)"
    
        st.caption(f"💡 **Note:** Total P&L includes initial credit collected ({credit_msg}) plus settlement value changes")
    
        # LOCKSTEP SETTLEMENT ANALYSIS
        # Calculate theoretical constant settlement cost in perfect lockstep
        if show_calls and show_puts:
            st.markdown("---")
            st.markdown("### 🔒 Lockstep Settlement Analysis")
            st.caption("**What happens if SPY and SPX maintain perfect 10:1 ratio at settlement**")
    
            # Using ratio from entry time for lockstep calculation
            ratio_from_entry = entry_spx['close'] / entry_spy['close']
    
            # Theoretical constant settlement cost formula:
            # For perfect lockstep (SPX = ratio × SPY), settlement cost is constant regardless of price level
            # Settlement Cost = (SPX_strike - ratio × SPY_strike) × sell_qty × 100
    
            theoretical_settlement = (spx_strike - ratio_from_entry * spy_strike) * sell_puts_qty * 100
            theoretical_net_pnl = total_credit - theoretical_settlement
    
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Lockstep Settlement Cost",
                    f"${theoretical_settlement:,.2f}",
                    help="Constant cost if SPY/SPX maintain perfect lockstep"
                )
            with col2:
                st.metric(
                    "Lockstep Net P&L",
                    f"${theoretical_net_pnl:,.2f}",
                    help="Credit - Lockstep Settlement Cost"
                )
    
            # Detailed breakdown
            with st.expander("📋 Lockstep Settlement Breakdown"):
                st.markdown(f"""
    **Perfect Lockstep Formula:**
    
    In perfect lockstep (SPX = {ratio_from_entry:.4f} × SPY), the settlement cost is **constant** regardless of where SPY/SPX close.
    
    **Calculation:**
    - Strike Gap = SPX Strike - (Ratio × SPY Strike)
    - Strike Gap = {spx_strike} - ({ratio_from_entry:.4f} × {spy_strike})
    - Strike Gap = {spx_strike} - {ratio_from_entry * spy_strike:.2f}
    - Strike Gap = {spx_strike - ratio_from_entry * spy_strike:.2f} points
    
    **Constant Settlement Cost:**
    - Settlement = Gap × Quantity × Multiplier
    - Settlement = {spx_strike - ratio_from_entry * spy_strike:.2f} × {sell_puts_qty} × 100
    - Settlement = **${theoretical_settlement:,.2f}**
    
    **Net P&L (in perfect lockstep):**
    - Net P&L = Credit - Settlement
    - Net P&L = ${total_credit:,.2f} - ${theoretical_settlement:,.2f}
    - Net P&L = **${theoretical_net_pnl:,.2f}**
    
    **Key Insight:** This value is the SAME at any price level as long as SPY/SPX maintain their {ratio_from_entry:.4f} ratio.
    
    **Why actual P&L differs from lockstep:**
    - Entry option prices include **time premium** (not just intrinsic value)
    - At settlement, all time premium decays to zero
    - Real-world P&L varies due to time decay + small SPY/SPX divergence ({abs(eod_spx / eod_spy - ratio_from_entry):.6f} ratio diff at EOD)
                """)
    
            # Show strike moneyness analysis
            if moneyness_diff > 0.05:
                st.warning(f"""
    ⚠️ **Strike Mismatch Alert:**
    
    Your strikes have {moneyness_diff:.2f}% moneyness difference, which creates **${abs(theoretical_settlement):,.2f}** lockstep settlement cost.
    
    - To minimize lockstep risk, match strike moneyness to <0.01%
    - Current gap: SPX {spx_strike} - ({ratio_from_entry:.4f} × SPY {spy_strike}) = {spx_strike - ratio_from_entry * spy_strike:.2f} points
                """)
            else:
                st.success(f"""
    ✅ **Well-Matched Strikes:**
    
    Your strikes are well-matched ({moneyness_diff:.4f}% difference), resulting in minimal lockstep settlement cost of ${abs(theoretical_settlement):,.2f}.
                """)
    
    
            st.caption(f"**Current Configuration:**")
            st.caption(f"- SPY Strike: {spy_strike} ({spy_moneyness_pct:+.4f}% moneyness)")
            st.caption(f"- SPX Strike: {spx_strike} ({spx_moneyness_pct:+.4f}% moneyness)")
            st.caption(f"- Moneyness difference: {moneyness_diff:.4f}%")
    
            if moneyness_diff < 0.01:
                st.success("✅ Strikes are very well matched - P&L range will be tight")
            elif moneyness_diff < 0.05:
                st.info("✓ Strikes are reasonably matched")
            else:
                st.warning(f"⚠️ Strikes have {moneyness_diff:.2f}% mismatch - this creates the ${best_case_lockstep - worst_case_lockstep:,.2f} P&L range")
    
        # Show basis risk warning if strikes are mismatched
        if moneyness_diff > 0.05:
            gap = abs(spy_price_at_spx_strike - spy_strike)
            st.warning(f"""
    ⚠️ **Strike Mismatch Detected** ({moneyness_diff:.2f}% moneyness difference)
    
    Your SPY and SPX strikes don't align (gap: ${gap:.2f} on chart). While SPY/SPX typically move together,
    mismatched strikes mean your hedge won't offset perfectly if they diverge even slightly.
    
    **Visual guide:** Two strike lines on chart (red SPY, orange SPX) - closer together = better hedge.
            """)
    
        # Detailed breakdown
        st.markdown("---")
        st.markdown("**📊 P&L Range Breakdown:**")
    
        if worst_case_lockstep >= 0:
            st.success(f"✅ **Profitable in all scenarios** within ±3% range (${worst_case_lockstep:,.2f} to ${best_case_lockstep:,.2f})")
        else:
            st.warning(f"⚠️ **Risk Range:** Loss of ${abs(worst_case_lockstep):,.2f} to profit of ${best_case_lockstep:,.2f}")
    
        col1, col2, col3 = st.columns(3)
        with col1:
            # Show only relevant credit based on strategy
            if show_calls and show_puts:
                credit_display = f"${call_credit + put_credit:,.2f}"
            elif show_calls:
                credit_display = f"${call_credit:,.2f}"
            else:  # show_puts
                credit_display = f"${put_credit:,.2f}"
    
            st.caption(f"**Initial Credit:** {credit_display}")
            st.caption("Premium collected upfront")
        with col2:
            profit_range = best_case_lockstep - worst_case_lockstep
            st.caption(f"**P&L Range:** ${profit_range:,.2f}")
            st.caption("Difference between best and worst case")
        with col3:
            avg_pnl = df_pnl['total_pnl'].mean()
            st.caption(f"**Average P&L:** ${avg_pnl:,.2f}")
            st.caption("Expected outcome across all prices")
    
            # Footer
            st.markdown("---")
            st.caption("**Data Sources:** Real market prices from Jan 27, 2026 | Underlying: 1-min bars | Options: Live bid/ask quotes")
    
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
            spy_price = client.get_current_price('SPY')
            spx_price = client.get_current_price('SPX')

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
                            st.caption(f"SPY: ${spy_price:.2f} | SPX: ${spx_price:.2f}")

                            settlement_pnl = 0.0
                            settlement_breakdown = []

                            for pos in option_positions:
                                contract = pos['contract']
                                position_size = pos.get('position', 0)
                                avg_cost_per_share = pos.get('avg_cost', 0) / 100

                                # Calculate intrinsic value at current prices
                                if contract.symbol == 'SPY':
                                    underlying = spy_price
                                else:  # SPX
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
                            st.warning(f"⚠️ Underlying prices not available (SPY: {spy_price}, SPX: {spx_price})")
                            st.info("Settlement P&L requires valid SPY/SPX prices with delayed market data")

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
                col1.metric("SPY", f"${spy_price:.2f}" if spy_price else "N/A")
                col2.metric("SPX", f"${spx_price:.2f}" if spx_price else "N/A")

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
                    spy_strikes_in_position = [p['contract'].strike for p in option_positions if p['contract'].symbol == 'SPY']
                    spx_strikes_in_position = [p['contract'].strike for p in option_positions if p['contract'].symbol == 'SPX']

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
                            if contract.symbol == 'SPY':
                                underlying = spy_px
                            else:  # SPX
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
                            if pos['contract'].symbol == 'SPY':
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

                    fig.update_xaxes(title_text="SPY Price ($)")
                    fig.update_yaxes(title_text="P&L ($)")
                    fig.update_layout(
                        height=500,
                        showlegend=False,
                        hovermode='x unified',
                        title="Total P&L vs SPY Price"
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
