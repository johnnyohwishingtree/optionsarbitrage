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

# Tab 1: Historical Analysis
with tab1:
    st.markdown("Using **real market prices** from historical trades")

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
    # No database available - show error
    st.error("❌ Option price database not found. Cannot display prices.")
    st.info(f"Please ensure {OPTIONS_FILE} exists with option price data.")
    st.stop()

# Option prices from database
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

            # Quantities
            sell_spx_calls = st.number_input("Sell SPX Calls", 1, 100, 10, key=f"sell_spx_c_{entry_time_idx}_{spy_strike}_{spx_strike}")
            buy_spy_calls = st.number_input("Buy SPY Calls", 1, 1000, 100, key=f"buy_spy_c_{entry_time_idx}_{spy_strike}_{spx_strike}")

            # Prices (use estimated prices that update with slider, strikes, and direction)
            # Key includes time, strikes, and direction to force widget recreation when any change
            sell_spx_call_price = st.number_input(
                f"Sell SPX {spx_strike}C Price",
                0.0, 100.0, float(estimated_spx_call), 0.01,
                key=f"sell_spx_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
            )

            buy_spy_call_price = st.number_input(
                f"Buy SPY {spy_strike}C Price",
                0.0, 100.0, float(estimated_spy_call), 0.01,
                key=f"buy_spy_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{call_direction}"
            )

            call_credit = (sell_spx_call_price * sell_spx_calls * 100) - (buy_spy_call_price * buy_spy_calls * 100)
            st.metric("Call Credit", f"${call_credit:,.2f}")

    # Put Spread Section
    if show_puts:
        with col2 if col2 else col1:
            st.subheader("📉 Put Spread")
            st.write(f"**Direction:** {best_combo['put_direction']}")
            st.caption(f"Database prices at {entry_time_label}")

            # Quantities
            sell_spy_puts = st.number_input("Sell SPY Puts", 1, 1000, 100, key=f"sell_spy_p_{entry_time_idx}_{spy_strike}_{spx_strike}")
            buy_spx_puts = st.number_input("Buy SPX Puts", 1, 100, 10, key=f"buy_spx_p_{entry_time_idx}_{spy_strike}_{spx_strike}")

            # Prices (use estimated prices that update with slider, strikes, and direction)
            # Key includes time, strikes, and direction to force widget recreation when any change
            sell_spy_put_price = st.number_input(
                f"Sell SPY {spy_strike}P Price",
                0.0, 100.0, float(estimated_spy_put), 0.01,
                key=f"sell_spy_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"
            )

            buy_spx_put_price = st.number_input(
                f"Buy SPX {spx_strike}P Price",
                0.0, 100.0, float(estimated_spx_put), 0.01,
                key=f"buy_spx_p_px_{entry_time_idx}_{spy_strike}_{spx_strike}_{put_direction}"
            )

            put_credit = (sell_spy_put_price * sell_spy_puts * 100) - (buy_spx_put_price * buy_spx_puts * 100)
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
        call_pnl = calculate_option_pnl(sell_spx_call_price, spx_call_settle, 'SELL', sell_spx_calls)
        call_pnl += calculate_option_pnl(buy_spy_call_price, spy_call_settle, 'BUY', buy_spy_calls)

    if show_puts:
        put_pnl = calculate_option_pnl(sell_spy_put_price, spy_put_settle, 'SELL', sell_spy_puts)
        put_pnl += calculate_option_pnl(buy_spx_put_price, spx_put_settle, 'BUY', buy_spx_puts)

    total_pnl = call_pnl + put_pnl

    # Show P&L metrics based on strategy
    if show_calls and show_puts:
        col1, col2, col3 = st.columns(3)
        col1.metric("Call P&L", f"${call_pnl:,.2f}")
        col2.metric("Put P&L", f"${put_pnl:,.2f}")
        col3.metric("**Total P&L**", f"**${total_pnl:,.2f}**")
    elif show_calls:
        st.metric("**Call P&L (Total)**", f"**${call_pnl:,.2f}**")
    else:  # show_puts
        st.metric("**Put P&L (Total)**", f"**${put_pnl:,.2f}**")

    # Detailed breakdown
    with st.expander("📋 Detailed Breakdown"):
        if show_calls:
            st.write("**Calls:**")
            st.write(f"- Sell {sell_spx_calls} SPX {spx_strike}C @ ${sell_spx_call_price:.2f} → Settle @ ${spx_call_settle:.2f}")
            st.write(f"- Buy {buy_spy_calls} SPY {spy_strike}C @ ${buy_spy_call_price:.2f} → Settle @ ${spy_call_settle:.2f}")
            st.write(f"- Net: ${call_pnl:,.2f}")

        if show_puts:
            if show_calls:
                st.write("")  # Add spacing
            st.write("**Puts:**")
            st.write(f"- Sell {sell_spy_puts} SPY {spy_strike}P @ ${sell_spy_put_price:.2f} → Settle @ ${spy_put_settle:.2f}")
            st.write(f"- Buy {buy_spx_puts} SPX {spx_strike}P @ ${buy_spx_put_price:.2f} → Settle @ ${spx_put_settle:.2f}")
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

        # Call P&L
        c_pnl = calculate_option_pnl(sell_spx_call_price, spx_call_val, 'SELL', sell_spx_calls)
        c_pnl += calculate_option_pnl(buy_spy_call_price, spy_call_val, 'BUY', buy_spy_calls)

        # Put P&L
        p_pnl = calculate_option_pnl(sell_spy_put_price, spy_put_val, 'SELL', sell_spy_puts)
        p_pnl += calculate_option_pnl(buy_spx_put_price, spx_put_val, 'BUY', buy_spx_puts)

        total = c_pnl + p_pnl
        pnl_results.append({
            'spy_price': spy_px,
            'spx_price': spx_px,
            'call_pnl': c_pnl,
            'put_pnl': p_pnl,
            'total_pnl': total
        })

    df_pnl = pd.DataFrame(pnl_results)

    # Create interactive plot
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Total P&L vs SPY Price', 'Call vs Put P&L Breakdown'),
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

    # Add entry price line
    fig.add_vline(
        x=entry_spy['close'],
        line_dash="dash",
        line_color="green",
        annotation_text=f"Entry: ${entry_spy['close']:.2f}",
        row=1, col=1
    )

    # Add EOD price line if different from entry
    if abs(eod_spy - entry_spy['close']) > 0.10:  # Only show if >$0.10 difference
        fig.add_vline(
            x=eod_spy,
            line_dash="dot",
            line_color="blue",
            annotation_text=f"EOD: ${eod_spy:.2f}",
            row=1, col=1
        )

    # Add strike line
    fig.add_vline(
        x=spy_strike,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Strike: {spy_strike}",
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

    # Call and Put breakdown
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

    fig.update_xaxes(title_text="SPY Price ($)", row=2, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=1, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=2, col=1)

    fig.update_layout(
        height=800,
        showlegend=True,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    # Statistics
    max_profit = df_pnl['total_pnl'].max()
    max_loss = df_pnl['total_pnl'].min()
    breakeven_mask = abs(df_pnl['total_pnl']) < 100
    breakeven_prices = df_pnl[breakeven_mask]['spy_price'].values if breakeven_mask.any() else []

    col1, col2, col3 = st.columns(3)
    col1.metric("Max Profit", f"${max_profit:,.2f}")
    col2.metric("Max Loss (in range)", f"${max_loss:,.2f}")
    if len(breakeven_prices) > 0:
        col3.metric("Breakeven Zone", f"${breakeven_prices.min():.2f} - ${breakeven_prices.max():.2f}")

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

                        # Show estimated total
                        st.metric("**Estimated Total P&L (If Closed Now)**", f"**${estimated_pnl:,.2f}**")

                        # Compare to initial credit
                        if os.path.exists(BEST_COMBO_FILE):
                            initial_credit = best_combo.get('total_credit', 0)
                            st.caption(f"Initial Credit Collected: ${initial_credit:,.2f}")
                            st.caption(f"Current P&L: ${estimated_pnl:,.2f}")
                            retention = (estimated_pnl / initial_credit * 100) if initial_credit > 0 else 0
                            st.caption(f"Credit Retention: {retention:.1f}%")

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

                            # Show estimated total
                            st.metric("**Estimated Total P&L (If Closed At Expiration)**", f"**${settlement_pnl:,.2f}**")

                            if os.path.exists(BEST_COMBO_FILE):
                                st.caption(f"Initial Credit Collected: ${initial_credit:,.2f}")
                                st.caption(f"Settlement P&L: ${settlement_pnl:,.2f}")
                                retention_settlement = (settlement_pnl / initial_credit * 100) if initial_credit > 0 else 0
                                st.caption(f"Credit Retention: {retention_settlement:.1f}%")
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
