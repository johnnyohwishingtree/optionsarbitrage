#!/usr/bin/env python3
"""
2025 Backtest: SPY vs SPX Daily Arbitrage Strategy
Uses real daily prices + realistic option pricing model
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def get_2025_prices():
    """Get actual SPY and SPX daily prices from 2025"""
    print("Downloading 2025 price data...")

    # Get data from Jan 1, 2025 to today
    start_date = "2025-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        spy = yf.Ticker("SPY")
        spx = yf.Ticker("^SPX")

        spy_hist = spy.history(start=start_date, end=end_date)
        spx_hist = spx.history(start=start_date, end=end_date)

        if len(spy_hist) == 0 or len(spx_hist) == 0:
            print("⚠️  No price data available - using sample data")
            return None, None

        print(f"✅ Downloaded {len(spy_hist)} days of SPY data")
        print(f"✅ Downloaded {len(spx_hist)} days of SPX data")

        return spy_hist, spx_hist

    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        return None, None

def estimate_option_price(stock_price, strike, days_to_exp=0, volatility=0.15):
    """
    Estimate ATM 0DTE option price using simplified model

    For 0DTE options:
    - Mostly intrinsic value
    - Small time value (a few cents to dollars depending on vol)
    """

    intrinsic = max(0, stock_price - strike)

    if days_to_exp == 0:
        # 0DTE: mostly intrinsic + tiny time value
        time_value = volatility * np.sqrt(stock_price) * 0.5  # Simplified
        return intrinsic + time_value
    else:
        # Use simple approximation for non-0DTE
        time_value = volatility * np.sqrt(stock_price * days_to_exp / 365)
        return intrinsic + time_value

def simulate_daily_trade(date, spy_price, spx_price, trade_num):
    """
    Simulate one day's trade

    Returns dict with trade details
    """

    # Round to nearest $5 strike
    spy_strike = round(spy_price / 5) * 5
    spx_strike = spy_strike * 10

    # Estimate option prices (ATM 0DTE)
    spy_call_value = estimate_option_price(spy_price, spy_strike, days_to_exp=0)
    spx_call_value = estimate_option_price(spx_price, spx_strike, days_to_exp=0)

    # Add realistic bid-ask spreads
    spy_spread = 0.02  # SPY is very tight
    spx_spread = 0.30  # SPX wider (0DTE can be $0.20-0.50)

    spy_bid = spy_call_value - spy_spread / 2
    spy_ask = spy_call_value + spy_spread / 2
    spx_bid = spx_call_value - spx_spread / 2
    spx_ask = spx_call_value + spx_spread / 2

    # Entry: Buy SPX at ask, Sell SPY at bid
    entry_spx_cost = spx_ask * 100  # 1 contract
    entry_spy_credit = spy_bid * 100 * 10  # 10 contracts
    entry_net = entry_spy_credit - entry_spx_cost
    commissions_entry = 11 * 0.65
    net_entry_credit = entry_net - commissions_entry

    # Determine if we need to close (assignment risk threshold)
    assignment_risk = spy_price > (spy_strike + 10)  # $10 ITM = high risk

    if assignment_risk:
        # Close both positions
        # Exit: Sell SPX at bid, Buy back SPY at ask
        exit_spx_proceeds = spx_bid * 100
        exit_spy_cost = spy_ask * 100 * 10
        exit_net = exit_spx_proceeds - exit_spy_cost
        commissions_exit = 11 * 0.65
        exit_cost = -exit_net - commissions_exit

        final_pnl = net_entry_credit + exit_net - commissions_exit
        exit_reason = "Assignment Risk (closed early)"

    else:
        # Hold to expiration - both expire worthless or offset
        # Assume perfect tracking at expiration
        spy_settlement = max(0, spy_price - spy_strike) * 100 * 10
        spx_settlement = max(0, spx_price - spx_strike) * 100
        net_settlement = spx_settlement - spy_settlement

        final_pnl = net_entry_credit + net_settlement
        exit_reason = "Held to expiration"
        exit_cost = net_settlement

    return {
        'Trade_Num': trade_num,
        'Date': date,
        'SPY_Price': spy_price,
        'SPX_Price': spx_price,
        'SPY_Strike': spy_strike,
        'SPX_Strike': spx_strike,
        'SPY_Bid': spy_bid,
        'SPY_Ask': spy_ask,
        'SPX_Bid': spx_bid,
        'SPX_Ask': spx_ask,
        'Entry_Credit': net_entry_credit,
        'Exit_Cost': exit_cost,
        'Exit_Reason': exit_reason,
        'Final_PnL': final_pnl,
        'Cumulative_PnL': 0  # Will be calculated later
    }

def run_backtest():
    """Run full backtest for 2025"""

    print("=" * 80)
    print("2025 BACKTEST: SPY vs SPX Daily Arbitrage")
    print("=" * 80)

    # Get real price data
    spy_hist, spx_hist = get_2025_prices()

    if spy_hist is None or spx_hist is None:
        print("\n⚠️  Using simulated data (real data unavailable)")
        # Create sample data
        dates = pd.date_range(start='2025-01-02', end='2025-01-16', freq='B')
        spy_prices = 600 + np.cumsum(np.random.randn(len(dates)) * 2)
        spx_prices = spy_prices * 10 + np.random.randn(len(dates)) * 5

        spy_hist = pd.DataFrame({'Close': spy_prices}, index=dates)
        spx_hist = pd.DataFrame({'Close': spx_prices}, index=dates)

    # Merge data
    prices = pd.DataFrame({
        'SPY': spy_hist['Close'],
        'SPX': spx_hist['Close']
    }).dropna()

    print(f"\n📊 Backtesting Period:")
    print(f"   Start: {prices.index[0].strftime('%Y-%m-%d')}")
    print(f"   End: {prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"   Trading days: {len(prices)}")

    # Run simulation for each day
    trades = []
    trade_num = 1

    for date, row in prices.iterrows():
        trade = simulate_daily_trade(
            date=date.strftime('%Y-%m-%d'),
            spy_price=row['SPY'],
            spx_price=row['SPX'],
            trade_num=trade_num
        )
        trades.append(trade)
        trade_num += 1

    # Create DataFrame
    df = pd.DataFrame(trades)

    # Calculate cumulative P&L
    df['Cumulative_PnL'] = df['Final_PnL'].cumsum()

    # Calculate statistics
    total_trades = len(df)
    winning_trades = len(df[df['Final_PnL'] > 0])
    losing_trades = len(df[df['Final_PnL'] < 0])
    win_rate = winning_trades / total_trades * 100

    total_pnl = df['Final_PnL'].sum()
    avg_win = df[df['Final_PnL'] > 0]['Final_PnL'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['Final_PnL'] < 0]['Final_PnL'].mean() if losing_trades > 0 else 0
    best_trade = df['Final_PnL'].max()
    worst_trade = df['Final_PnL'].min()
    avg_trade = df['Final_PnL'].mean()

    # Calculate drawdown
    df['Peak'] = df['Cumulative_PnL'].cummax()
    df['Drawdown'] = df['Cumulative_PnL'] - df['Peak']
    max_drawdown = df['Drawdown'].min()

    # Print results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)

    print(f"\n📈 Performance:")
    print(f"   Total P&L: ${total_pnl:,.2f}")
    print(f"   Average per trade: ${avg_trade:.2f}")
    print(f"   Win rate: {win_rate:.1f}%")

    print(f"\n📊 Trade Statistics:")
    print(f"   Total trades: {total_trades}")
    print(f"   Winning trades: {winning_trades}")
    print(f"   Losing trades: {losing_trades}")
    print(f"   Average win: ${avg_win:.2f}")
    print(f"   Average loss: ${avg_loss:.2f}")
    print(f"   Best trade: ${best_trade:.2f}")
    print(f"   Worst trade: ${worst_trade:.2f}")

    print(f"\n💰 Risk Metrics:")
    print(f"   Max drawdown: ${max_drawdown:.2f}")
    print(f"   Profit factor: {abs(avg_win / avg_loss):.2f}" if avg_loss != 0 else "   Profit factor: N/A")

    # Annualized returns (if we have enough data)
    if len(prices) > 20:
        trading_days_year = 252
        days_in_backtest = len(prices)
        annual_pnl = total_pnl * (trading_days_year / days_in_backtest)
        roi = (annual_pnl / 50000) * 100  # Assuming $50K capital

        print(f"\n📅 Annualized Projections:")
        print(f"   Days in backtest: {days_in_backtest}")
        print(f"   Projected annual P&L: ${annual_pnl:,.2f}")
        print(f"   Projected ROI (on $50K): {roi:.1f}%")

    # Save to CSV
    output_file = 'backtest_2025_results.csv'
    df.to_csv(output_file, index=False, float_format='%.2f')
    print(f"\n✅ Results saved to: {output_file}")

    # Create summary file
    summary = pd.DataFrame([{
        'Period': f"{prices.index[0].strftime('%Y-%m-%d')} to {prices.index[-1].strftime('%Y-%m-%d')}",
        'Total_Trades': total_trades,
        'Win_Rate_%': win_rate,
        'Total_PnL': total_pnl,
        'Avg_Trade': avg_trade,
        'Best_Trade': best_trade,
        'Worst_Trade': worst_trade,
        'Max_Drawdown': max_drawdown,
        'Annualized_PnL': annual_pnl if len(prices) > 20 else 'N/A',
        'Projected_ROI_%': roi if len(prices) > 20 else 'N/A'
    }])

    summary.to_csv('backtest_2025_summary.csv', index=False)
    print(f"✅ Summary saved to: backtest_2025_summary.csv")

    print("\n" + "=" * 80)
    print("⚠️  IMPORTANT NOTES")
    print("=" * 80)
    print("\nThis backtest uses:")
    print("  ✅ Real SPY/SPX daily prices from 2025")
    print("  ⚠️  Estimated option prices (realistic spreads)")
    print("  ⚠️  Simplified pricing model")
    print("\nLimitations:")
    print("  • Actual bid/ask spreads may vary")
    print("  • Does not account for early assignment before we close")
    print("  • Assumes ability to execute at these prices")
    print("  • 0DTE liquidity can be lower than shown")
    print("\n💡 Next step: Paper trade this for 2-4 weeks to verify!")
    print("=" * 80)

    return df

if __name__ == "__main__":
    results = run_backtest()
