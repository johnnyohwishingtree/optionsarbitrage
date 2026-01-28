#!/usr/bin/env python3
"""
Interactive Strategy Calculator and Visualizer

Loads real option prices from SQLite database.
No default values - all prices come from actual market data.

Run with: streamlit run strategy_calculator.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, time
import glob
import os
import sqlite3

# Page config
st.set_page_config(
    page_title="0DTE Strategy Calculator",
    page_icon="📊",
    layout="wide"
)

st.title("📊 SPY/SPX 0DTE Strategy Calculator")
st.markdown("Interactive simulator using **real option prices from database**")

# Database connection
DB_PATH = 'data/market_data.db'

@st.cache_data
def load_available_dates_from_db():
    """Find all available dates with option price data"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT DISTINCT DATE(timestamp) as date
        FROM option_prices
        ORDER BY date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df['date'].tolist()

@st.cache_data
def load_underlying_data(date):
    """Load underlying prices for a specific date"""
    file_path = f'data/underlying_prices_{date.replace("-", "")}.csv'
    if not os.path.exists(file_path):
        return None

    df = pd.read_csv(file_path)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    return df

@st.cache_data
def get_option_price_from_db(date, symbol, strike, right, time_str=None):
    """
    Get option price from database for a specific date/time
    Returns: (bid, ask, mid) or (None, None, None) if not found
    """
    conn = sqlite3.connect(DB_PATH)

    # Format expiration date (YYYYMMDD)
    exp_date = date.replace("-", "")

    if time_str:
        # Get price at specific time
        query = """
            SELECT bid, ask, last
            FROM option_prices
            WHERE DATE(timestamp) = ?
              AND TIME(timestamp) = ?
              AND symbol = ?
              AND expiration = ?
              AND strike = ?
              AND right = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        params = (date, time_str, symbol, exp_date, strike, right)
    else:
        # Get latest price for the day
        query = """
            SELECT bid, ask, last
            FROM option_prices
            WHERE DATE(timestamp) = ?
              AND symbol = ?
              AND expiration = ?
              AND strike = ?
              AND right = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        params = (date, symbol, exp_date, strike, right)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return None, None, None

    bid = df['bid'].iloc[0]
    ask = df['ask'].iloc[0]
    last = df['last'].iloc[0]

    # Calculate mid price
    if bid and ask:
        mid = (bid + ask) / 2
    elif last:
        mid = last
    else:
        mid = None

    return bid, ask, mid

@st.cache_data
def get_strikes_near_price(date, symbol, underlying_price, count=5):
    """Get strikes near the underlying price from database"""
    conn = sqlite3.connect(DB_PATH)
    exp_date = date.replace("-", "")

    query = """
        SELECT DISTINCT strike
        FROM option_prices
        WHERE DATE(timestamp) = ?
          AND symbol = ?
          AND expiration = ?
        ORDER BY ABS(strike - ?) ASC
        LIMIT ?
    """

    df = pd.read_sql_query(query, conn, params=(date, symbol, exp_date, underlying_price, count))
    conn.close()

    if df.empty:
        return []

    return sorted(df['strike'].tolist())

def calculate_option_pnl(entry_price, exit_price, action, quantity):
    """
    Calculate P&L for an option position
    action: 'BUY' or 'SELL'
    """
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

# Sidebar: Configuration
st.sidebar.header("Configuration")

available_dates = load_available_dates_from_db()
if not available_dates:
    st.error("No data found in database. Please collect market data first.")
    st.stop()

selected_date = st.sidebar.selectbox(
    "Select Date",
    available_dates,
    format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%B %d, %Y')
)

# Load underlying data for selected date
underlying_df = load_underlying_data(selected_date)
if underlying_df is None:
    st.error(f"Could not load underlying data for {selected_date}")
    st.stop()

spy_df = underlying_df[underlying_df['symbol'] == 'SPY'].copy()
spx_df = underlying_df[underlying_df['symbol'] == 'SPX'].copy()

# Get available times
available_times = spy_df['time'].dt.time.unique()
time_options = sorted(available_times)

st.sidebar.subheader("Entry Parameters")

entry_time = st.sidebar.selectbox(
    "Entry Time",
    time_options,
    index=0,  # Market open
    format_func=lambda t: t.strftime('%I:%M %p')
)

# Get prices at entry time
entry_spy_row = spy_df[spy_df['time'].dt.time == entry_time].iloc[0]
entry_spx_row = spx_df[spx_df['time'].dt.time == entry_time].iloc[0]

entry_spy_price = entry_spy_row['close']
entry_spx_price = entry_spx_row['close']

st.sidebar.metric("SPY Price at Entry", f"${entry_spy_price:.2f}")
st.sidebar.metric("SPX Price at Entry", f"${entry_spx_price:.2f}")

# Strike selection from database
st.sidebar.subheader("Strike Selection")

# Get available strikes from database
spy_strikes = get_strikes_near_price(selected_date, 'SPY', entry_spy_price, count=10)
spx_strikes = get_strikes_near_price(selected_date, 'SPX', entry_spx_price, count=10)

if not spy_strikes or not spx_strikes:
    st.error("No option data found in database for this date")
    st.stop()

spy_strike = st.sidebar.selectbox(
    "SPY Strike",
    spy_strikes,
    index=len(spy_strikes)//2  # Middle strike
)

spx_strike = st.sidebar.selectbox(
    "SPX Strike",
    spx_strikes,
    index=len(spx_strikes)//2  # Middle strike
)

# Fetch option prices from database
time_str = entry_time.strftime('%H:%M:%S')

spy_call_bid, spy_call_ask, spy_call_mid = get_option_price_from_db(selected_date, 'SPY', spy_strike, 'C', time_str)
spx_call_bid, spx_call_ask, spx_call_mid = get_option_price_from_db(selected_date, 'SPX', spx_strike, 'C', time_str)
spy_put_bid, spy_put_ask, spy_put_mid = get_option_price_from_db(selected_date, 'SPY', spy_strike, 'P', time_str)
spx_put_bid, spx_put_ask, spx_put_mid = get_option_price_from_db(selected_date, 'SPX', spx_strike, 'P', time_str)

# Show database prices in sidebar
st.sidebar.subheader("📊 Option Prices from Database")
with st.sidebar.expander("SPY Options", expanded=False):
    if spy_call_bid and spy_call_ask:
        st.text(f"Call {spy_strike}: ${spy_call_bid:.2f} / ${spy_call_ask:.2f}")
    else:
        st.warning(f"No SPY {spy_strike}C data")

    if spy_put_bid and spy_put_ask:
        st.text(f"Put {spy_strike}: ${spy_put_bid:.2f} / ${spy_put_ask:.2f}")
    else:
        st.warning(f"No SPY {spy_strike}P data")

with st.sidebar.expander("SPX Options", expanded=False):
    if spx_call_bid and spx_call_ask:
        st.text(f"Call {spx_strike}: ${spx_call_bid:.2f} / ${spx_call_ask:.2f}")
    else:
        st.warning(f"No SPX {spx_strike}C data")

    if spx_put_bid and spx_put_ask:
        st.text(f"Put {spx_strike}: ${spx_put_bid:.2f} / ${spx_put_ask:.2f}")
    else:
        st.warning(f"No SPX {spx_strike}P data")

# Main area: Position Builder
st.header("Position Builder")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📞 Call Spread")

    call_direction = st.radio(
        "Call Direction",
        ["Sell SPX, Buy SPY", "Sell SPY, Buy SPX"],
        key="call_dir"
    )

    if "SPX" in call_direction.split(',')[0]:
        # Sell SPX, Buy SPY
        sell_symbol_call = "SPX"
        buy_symbol_call = "SPY"
        sell_strike_call = spx_strike
        buy_strike_call = spy_strike
        sell_qty_call = st.number_input("Sell SPX Calls", 1, 100, 10, key="sell_spx_c")
        buy_qty_call = st.number_input("Buy SPY Calls", 1, 1000, 100, key="buy_spy_c")

        # Use database prices
        sell_price_default = spx_call_bid if spx_call_bid else 0.0
        buy_price_default = spy_call_ask if spy_call_ask else 0.0
    else:
        # Sell SPY, Buy SPX
        sell_symbol_call = "SPY"
        buy_symbol_call = "SPX"
        sell_strike_call = spy_strike
        buy_strike_call = spx_strike
        sell_qty_call = st.number_input("Sell SPY Calls", 1, 1000, 100, key="sell_spy_c")
        buy_qty_call = st.number_input("Buy SPX Calls", 1, 100, 10, key="buy_spx_c")

        # Use database prices
        sell_price_default = spy_call_bid if spy_call_bid else 0.0
        buy_price_default = spx_call_ask if spx_call_ask else 0.0

    sell_price_call = st.number_input(
        f"Sell {sell_symbol_call} {sell_strike_call}C Price",
        0.0, 100.0, float(sell_price_default), 0.01, key="sell_call_px",
        help="From database" if sell_price_default > 0 else "⚠️ No database price found"
    )

    buy_price_call = st.number_input(
        f"Buy {buy_symbol_call} {buy_strike_call}C Price",
        0.0, 100.0, float(buy_price_default), 0.01, key="buy_call_px",
        help="From database" if buy_price_default > 0 else "⚠️ No database price found"
    )

    call_credit = (sell_price_call * sell_qty_call * 100) - (buy_price_call * buy_qty_call * 100)
    st.metric("Call Credit", f"${call_credit:,.2f}")

with col2:
    st.subheader("📉 Put Spread")

    put_direction = st.radio(
        "Put Direction",
        ["Sell SPY, Buy SPX", "Sell SPX, Buy SPY"],
        key="put_dir"
    )

    if "SPY" in put_direction.split(',')[0]:
        # Sell SPY, Buy SPX
        sell_symbol_put = "SPY"
        buy_symbol_put = "SPX"
        sell_strike_put = spy_strike
        buy_strike_put = spx_strike
        sell_qty_put = st.number_input("Sell SPY Puts", 1, 1000, 100, key="sell_spy_p")
        buy_qty_put = st.number_input("Buy SPX Puts", 1, 100, 10, key="buy_spx_p")

        # Use database prices
        sell_price_default = spy_put_bid if spy_put_bid else 0.0
        buy_price_default = spx_put_ask if spx_put_ask else 0.0
    else:
        # Sell SPX, Buy SPY
        sell_symbol_put = "SPX"
        buy_symbol_put = "SPY"
        sell_strike_put = spx_strike
        buy_strike_put = spy_strike
        sell_qty_put = st.number_input("Sell SPX Puts", 1, 100, 10, key="sell_spx_p")
        buy_qty_put = st.number_input("Buy SPY Puts", 1, 1000, 100, key="buy_spy_p")

        # Use database prices
        sell_price_default = spx_put_bid if spx_put_bid else 0.0
        buy_price_default = spy_put_ask if spy_put_ask else 0.0

    sell_price_put = st.number_input(
        f"Sell {sell_symbol_put} {sell_strike_put}P Price",
        0.0, 100.0, float(sell_price_default), 0.01, key="sell_put_px",
        help="From database" if sell_price_default > 0 else "⚠️ No database price found"
    )

    buy_price_put = st.number_input(
        f"Buy {buy_symbol_put} {buy_strike_put}P Price",
        0.0, 100.0, float(buy_price_default), 0.01, key="buy_put_px",
        help="From database" if buy_price_default > 0 else "⚠️ No database price found"
    )

    put_credit = (sell_price_put * sell_qty_put * 100) - (buy_price_put * buy_qty_put * 100)
    st.metric("Put Credit", f"${put_credit:,.2f}")

total_credit = call_credit + put_credit
st.metric("**Total Net Credit**", f"**${total_credit:,.2f}**", delta=None)

# Scenario Analysis
st.header("Scenario Analysis")

scenario_type = st.radio(
    "Exit Scenario",
    ["End of Day (4:00 PM)", "Price Range Sweep"],
    horizontal=True
)

if scenario_type == "End of Day (4:00 PM)":
    exit_spy_price = spy_df.iloc[-1]['close']
    exit_spx_price = spx_df.iloc[-1]['close']

    st.info(f"Market Close: SPY ${exit_spy_price:.2f}, SPX ${exit_spx_price:.2f}")

    # Calculate settlement
    spy_call_settle = calculate_settlement_value(exit_spy_price, spy_strike, 'C')
    spx_call_settle = calculate_settlement_value(exit_spx_price, spx_strike, 'C')
    spy_put_settle = calculate_settlement_value(exit_spy_price, spy_strike, 'P')
    spx_put_settle = calculate_settlement_value(exit_spx_price, spx_strike, 'P')

    # Call P&L
    if sell_symbol_call == "SPX":
        call_pnl = calculate_option_pnl(sell_price_call, spx_call_settle, 'SELL', sell_qty_call)
        call_pnl += calculate_option_pnl(buy_price_call, spy_call_settle, 'BUY', buy_qty_call)
    else:
        call_pnl = calculate_option_pnl(sell_price_call, spy_call_settle, 'SELL', sell_qty_call)
        call_pnl += calculate_option_pnl(buy_price_call, spx_call_settle, 'BUY', buy_qty_call)

    # Put P&L
    if sell_symbol_put == "SPY":
        put_pnl = calculate_option_pnl(sell_price_put, spy_put_settle, 'SELL', sell_qty_put)
        put_pnl += calculate_option_pnl(buy_price_put, spx_put_settle, 'BUY', buy_qty_put)
    else:
        put_pnl = calculate_option_pnl(sell_price_put, spx_put_settle, 'SELL', sell_qty_put)
        put_pnl += calculate_option_pnl(buy_price_put, spy_put_settle, 'BUY', buy_qty_put)

    total_pnl = call_pnl + put_pnl

    col1, col2, col3 = st.columns(3)
    col1.metric("Call P&L", f"${call_pnl:,.2f}")
    col2.metric("Put P&L", f"${put_pnl:,.2f}")
    col3.metric("**Total P&L**", f"**${total_pnl:,.2f}**")

    # Show breakdown
    with st.expander("Detailed Breakdown"):
        st.write("**Calls:**")
        st.write(f"- Sell {sell_qty_call} {sell_symbol_call} {sell_strike_call}C @ ${sell_price_call:.2f}")
        st.write(f"- Buy {buy_qty_call} {buy_symbol_call} {buy_strike_call}C @ ${buy_price_call:.2f}")
        st.write(f"- Credit: ${call_credit:,.2f}")
        st.write(f"- Settlement: SPY={spy_call_settle:.2f}, SPX={spx_call_settle:.2f}")
        st.write(f"- Net P&L: ${call_pnl:,.2f}")

        st.write("**Puts:**")
        st.write(f"- Sell {sell_qty_put} {sell_symbol_put} {sell_strike_put}P @ ${sell_price_put:.2f}")
        st.write(f"- Buy {buy_qty_put} {buy_symbol_put} {buy_strike_put}P @ ${buy_price_put:.2f}")
        st.write(f"- Credit: ${put_credit:,.2f}")
        st.write(f"- Settlement: SPY={spy_put_settle:.2f}, SPX={spx_put_settle:.2f}")
        st.write(f"- Net P&L: ${put_pnl:,.2f}")

elif scenario_type == "Price Range Sweep":
    st.subheader("P&L Across Price Range")

    # Generate price range
    spy_range = np.linspace(entry_spy_price * 0.97, entry_spy_price * 1.03, 100)
    spx_range = spy_range * (entry_spx_price / entry_spy_price)  # Maintain ratio

    pnl_results = []

    for spy_px, spx_px in zip(spy_range, spx_range):
        # Calculate settlement values
        spy_call_val = calculate_settlement_value(spy_px, spy_strike, 'C')
        spx_call_val = calculate_settlement_value(spx_px, spx_strike, 'C')
        spy_put_val = calculate_settlement_value(spy_px, spy_strike, 'P')
        spx_put_val = calculate_settlement_value(spx_px, spx_strike, 'P')

        # Call P&L
        if sell_symbol_call == "SPX":
            c_pnl = calculate_option_pnl(sell_price_call, spx_call_val, 'SELL', sell_qty_call)
            c_pnl += calculate_option_pnl(buy_price_call, spy_call_val, 'BUY', buy_qty_call)
        else:
            c_pnl = calculate_option_pnl(sell_price_call, spy_call_val, 'SELL', sell_qty_call)
            c_pnl += calculate_option_pnl(buy_price_call, spx_call_val, 'BUY', buy_qty_call)

        # Put P&L
        if sell_symbol_put == "SPY":
            p_pnl = calculate_option_pnl(sell_price_put, spy_put_val, 'SELL', sell_qty_put)
            p_pnl += calculate_option_pnl(buy_price_put, spx_put_val, 'BUY', buy_qty_put)
        else:
            p_pnl = calculate_option_pnl(sell_price_put, spx_put_val, 'SELL', sell_qty_put)
            p_pnl += calculate_option_pnl(buy_price_put, spy_put_val, 'BUY', buy_qty_put)

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
        subplot_titles=('Total P&L vs SPY Price', 'Call vs Put P&L'),
        vertical_spacing=0.12,
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
        x=entry_spy_price,
        line_dash="dash",
        line_color="gray",
        annotation_text="Entry",
        row=1, col=1
    )

    # Add strike line
    fig.add_vline(
        x=spy_strike,
        line_dash="dot",
        line_color="red",
        annotation_text=f"SPY Strike ({spy_strike})",
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

    fig.update_xaxes(title_text="SPY Price", row=2, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=1, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=2, col=1)

    fig.update_layout(height=800, showlegend=True)

    st.plotly_chart(fig, use_container_width=True)

    # Show key statistics
    max_profit = df_pnl['total_pnl'].max()
    max_loss = df_pnl['total_pnl'].min()
    breakeven_prices = df_pnl[abs(df_pnl['total_pnl']) < 100]['spy_price'].values

    col1, col2, col3 = st.columns(3)
    col1.metric("Max Profit", f"${max_profit:,.2f}")
    col2.metric("Max Loss", f"${max_loss:,.2f}")
    if len(breakeven_prices) > 0:
        col3.metric("Breakeven Range", f"${breakeven_prices.min():.2f} - ${breakeven_prices.max():.2f}")

# Footer
st.markdown("---")
st.caption("SPY/SPX 0DTE Strategy Calculator | **All prices from SQLite database**")
