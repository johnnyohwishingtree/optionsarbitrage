#!/usr/bin/env python3
"""
Detailed P&L Breakdown

Shows EXACTLY what happens at entry and exit with all calculations
"""

import pandas as pd
from hold_to_expiration_backtest_both_sides import calculate_expiration_value

def detailed_breakdown():
    """Show step-by-step what happens in the trade"""

    # Load actual backtest results
    results = pd.read_csv('data/hold_to_expiration_results.csv')
    latest = results.iloc[-1]

    print('=' * 100)
    print('DETAILED TRADE BREAKDOWN')
    print('=' * 100)

    print('\n' + '='*100)
    print('PART 1: ENTRY (10:02 AM EST)')
    print('='*100)

    print(f'\n📊 Market Conditions at Entry:')
    print(f'   SPY price: ${latest["spy_entry"]:.2f}')
    print(f'   SPX price: ${latest["spx_entry"]:.2f}')
    print(f'   SPX/SPY ratio: {latest["spx_entry"]/latest["spy_entry"]:.4f} (should be ~10.0)')

    print(f'\n🎯 Strikes Selected:')
    print(f'   SPY strike: ${int(latest["spy_strike"])}')
    print(f'   SPX strike: ${int(latest["spx_strike"])}')
    print(f'   Note: SPY strike is ${latest["spy_entry"] - latest["spy_strike"]:.2f} ABOVE current price (OTM)')
    print(f'         SPX strike is ${latest["spx_entry"] - latest["spx_strike"]:.2f} ABOVE current price (ITM)')

    num_spreads = int(latest['num_spreads'])
    spy_contracts = num_spreads * 10  # 100 SPY contracts
    spx_contracts = num_spreads        # 10 SPX contracts

    print(f'\n📐 Position Size:')
    print(f'   {num_spreads} spreads = {spy_contracts} SPY contracts + {spx_contracts} SPX contracts')

    print(f'\n' + '-'*100)
    print(f'CALL SIDE: {latest["call_direction"]}')
    print('-'*100)

    if latest['call_direction'] == 'Sell SPX, Buy SPY':
        print(f'\n   We SELL {spx_contracts} SPX ${int(latest["spx_strike"])} calls')
        print(f'   We BUY {spy_contracts} SPY ${int(latest["spy_strike"])} calls')
        print(f'\n   Logic: We collect premium on SPX (higher priced), pay less on SPY')
    else:
        print(f'\n   We SELL {spy_contracts} SPY ${int(latest["spy_strike"])} calls')
        print(f'   We BUY {spx_contracts} SPX ${int(latest["spx_strike"])} calls')
        print(f'\n   Logic: We collect premium on SPY, pay on SPX')

    print(f'\n' + '-'*100)
    print(f'PUT SIDE: {latest["put_direction"]}')
    print('-'*100)

    if latest['put_direction'] == 'Sell SPY, Buy SPX':
        print(f'\n   We SELL {spy_contracts} SPY ${int(latest["spy_strike"])} puts')
        print(f'   We BUY {spx_contracts} SPX ${int(latest["spx_strike"])} puts')
        print(f'\n   Logic: We collect premium on SPY, pay on SPX')
    else:
        print(f'\n   We SELL {spx_contracts} SPX ${int(latest["spx_strike"])} puts')
        print(f'   We BUY {spy_contracts} SPY ${int(latest["spy_strike"])} puts')
        print(f'\n   Logic: We collect premium on SPX, pay on SPY')

    print(f'\n💰 ENTRY CASH FLOWS:')
    print(f'   Total premium received (selling): ???')
    print(f'   Total premium paid (buying): ???')
    print(f'   Commission (220 contracts × $0.50): $110.00')
    print(f'   NET CREDIT: ${latest["credit_received"]:,.2f}')
    print(f'\n   → We received ${latest["credit_received"]:,.2f} in our account!')

    # Now calculate expiration
    print('\n\n' + '='*100)
    print('PART 2: EXPIRATION (4:00 PM EST)')
    print('='*100)

    print(f'\n📊 Market Conditions at Expiration:')
    print(f'   SPY close: ${latest["spy_close"]:.2f}')
    print(f'   SPX close: ${latest["spx_close"]:.2f}')
    print(f'   SPX/SPY ratio: {latest["spx_close"]/latest["spy_close"]:.4f}')

    print(f'\n📈 Market Movement:')
    underlying = pd.read_csv('data/underlying_prices_20260126.csv')
    underlying['time'] = pd.to_datetime(underlying['time'], utc=True)
    spy_data = underlying[underlying['symbol'] == 'SPY']
    spx_data = underlying[underlying['symbol'] == 'SPX']
    spy_open = spy_data.iloc[0]['open']
    spx_open = spx_data.iloc[0]['open']

    print(f'   SPY: ${spy_open:.2f} → ${latest["spy_close"]:.2f} '
          f'({((latest["spy_close"]/spy_open - 1)*100):+.2f}%)')
    print(f'   SPX: ${spx_open:.2f} → ${latest["spx_close"]:.2f} '
          f'({((latest["spx_close"]/spx_open - 1)*100):+.2f}%)')

    # Calculate settlement
    settlement = calculate_expiration_value(
        latest['spy_close'], latest['spx_close'],
        int(latest['spy_strike']), int(latest['spx_strike']),
        num_spreads,
        latest['call_direction'],
        latest['put_direction']
    )

    print(f'\n' + '-'*100)
    print(f'CALL SIDE SETTLEMENT')
    print('-'*100)

    print(f'\n   Option Intrinsic Values:')
    print(f'   SPY ${int(latest["spy_strike"])} call: max(0, {latest["spy_close"]:.2f} - {int(latest["spy_strike"])}) = ${settlement["spy_call_intrinsic"]:.2f} per share')
    print(f'   SPX ${int(latest["spx_strike"])} call: max(0, {latest["spx_close"]:.2f} - {int(latest["spx_strike"])}) = ${settlement["spx_call_intrinsic"]:.2f} per point')

    if latest['call_direction'] == 'Sell SPX, Buy SPY':
        print(f'\n   What We Owe (Short SPX):')
        print(f'   {spx_contracts} contracts × ${settlement["spx_call_intrinsic"]:.2f} × 100 = ${settlement["spx_call_intrinsic"] * 100 * spx_contracts:,.2f}')

        print(f'\n   What We Receive (Long SPY):')
        print(f'   {spy_contracts} contracts × ${settlement["spy_call_intrinsic"]:.2f} × 100 = ${settlement["spy_call_intrinsic"] * 100 * spy_contracts:,.2f}')

        print(f'\n   Net Call Settlement: ${settlement["spy_call_intrinsic"] * 100 * spy_contracts:,.2f} - ${settlement["spx_call_intrinsic"] * 100 * spx_contracts:,.2f} = ${settlement["call_net_settlement"]:,.2f}')
    else:
        print(f'\n   What We Owe (Short SPY):')
        print(f'   {spy_contracts} contracts × ${settlement["spy_call_intrinsic"]:.2f} × 100 = ${settlement["spy_call_intrinsic"] * 100 * spy_contracts:,.2f}')

        print(f'\n   What We Receive (Long SPX):')
        print(f'   {spx_contracts} contracts × ${settlement["spx_call_intrinsic"]:.2f} × 100 = ${settlement["spx_call_intrinsic"] * 100 * spx_contracts:,.2f}')

        print(f'\n   Net Call Settlement: ${settlement["spx_call_intrinsic"] * 100 * spx_contracts:,.2f} - ${settlement["spy_call_intrinsic"] * 100 * spy_contracts:,.2f} = ${settlement["call_net_settlement"]:,.2f}')

    if settlement["call_net_settlement"] < 0:
        print(f'   → We PAY ${abs(settlement["call_net_settlement"]):,.2f} (settlement cost)')
    else:
        print(f'   → We RECEIVE ${settlement["call_net_settlement"]:,.2f}')

    print(f'\n' + '-'*100)
    print(f'PUT SIDE SETTLEMENT')
    print('-'*100)

    print(f'\n   Option Intrinsic Values:')
    print(f'   SPY ${int(latest["spy_strike"])} put: max(0, {int(latest["spy_strike"])} - {latest["spy_close"]:.2f}) = ${settlement["spy_put_intrinsic"]:.2f} per share')
    print(f'   SPX ${int(latest["spx_strike"])} put: max(0, {int(latest["spx_strike"])} - {latest["spx_close"]:.2f}) = ${settlement["spx_put_intrinsic"]:.2f} per point')

    if latest['put_direction'] == 'Sell SPY, Buy SPX':
        print(f'\n   What We Owe (Short SPY):')
        print(f'   {spy_contracts} contracts × ${settlement["spy_put_intrinsic"]:.2f} × 100 = ${settlement["spy_put_intrinsic"] * 100 * spy_contracts:,.2f}')

        print(f'\n   What We Receive (Long SPX):')
        print(f'   {spx_contracts} contracts × ${settlement["spx_put_intrinsic"]:.2f} × 100 = ${settlement["spx_put_intrinsic"] * 100 * spx_contracts:,.2f}')

        print(f'\n   Net Put Settlement: ${settlement["spx_put_intrinsic"] * 100 * spx_contracts:,.2f} - ${settlement["spy_put_intrinsic"] * 100 * spy_contracts:,.2f} = ${settlement["put_net_settlement"]:,.2f}')
    else:
        print(f'\n   What We Owe (Short SPX):')
        print(f'   {spx_contracts} contracts × ${settlement["spx_put_intrinsic"]:.2f} × 100 = ${settlement["spx_put_intrinsic"] * 100 * spx_contracts:,.2f}')

        print(f'\n   What We Receive (Long SPY):')
        print(f'   {spy_contracts} contracts × ${settlement["spy_put_intrinsic"]:.2f} × 100 = ${settlement["spy_put_intrinsic"] * 100 * spy_contracts:,.2f}')

        print(f'\n   Net Put Settlement: ${settlement["spy_put_intrinsic"] * 100 * spy_contracts:,.2f} - ${settlement["spx_put_intrinsic"] * 100 * spx_contracts:,.2f} = ${settlement["put_net_settlement"]:,.2f}')

    if settlement["put_net_settlement"] < 0:
        print(f'   → We PAY ${abs(settlement["put_net_settlement"]):,.2f} (settlement cost)')
    elif settlement["put_net_settlement"] > 0:
        print(f'   → We RECEIVE ${settlement["put_net_settlement"]:,.2f}')
    else:
        print(f'   → Puts expired WORTHLESS (we keep the put premium!)')

    print(f'\n💰 EXIT CASH FLOWS:')
    print(f'   Call settlement: ${settlement["call_net_settlement"]:,.2f}')
    print(f'   Put settlement: ${settlement["put_net_settlement"]:,.2f}')
    print(f'   Exit commission: -${settlement["exit_commission"]:.2f}')
    print(f'   TOTAL EXIT COST: ${settlement["total_net_settlement"]:,.2f}')

    # Final P&L
    print('\n\n' + '='*100)
    print('PART 3: FINAL P&L')
    print('='*100)

    total_pnl = latest['credit_received'] + settlement['total_net_settlement']

    print(f'\n📊 Complete Trade Summary:')
    print(f'\n   Entry (10:02 AM):')
    print(f'     Credit received:        +${latest["credit_received"]:>12,.2f}')

    print(f'\n   Exit (4:00 PM):')
    print(f'     Call settlement:         ${settlement["call_net_settlement"]:>12,.2f}')
    print(f'     Put settlement:          ${settlement["put_net_settlement"]:>12,.2f}')
    print(f'     Exit commission:        -${settlement["exit_commission"]:>12.2f}')
    print(f'                              {"─"*18}')
    print(f'     Total exit cost:         ${settlement["total_net_settlement"]:>12,.2f}')

    print(f'\n   {"═"*60}')
    print(f'   NET P&L:                 ${total_pnl:>12,.2f}')
    print(f'   {"═"*60}')

    print(f'\n💡 Why This P&L?')

    if settlement["put_net_settlement"] == 0:
        print(f'\n   ✓ Puts expired worthless → We kept the put premium!')
        print(f'   ✗ Calls were ITM → We had to settle')
    elif settlement["call_net_settlement"] == 0:
        print(f'\n   ✓ Calls expired worthless → We kept the call premium!')
        print(f'   ✗ Puts were ITM → We had to settle')
    else:
        print(f'\n   Both sides were ITM → Had to settle both')

    print(f'\n   The key factors:')
    print(f'   1. Credit collected: ${latest["credit_received"]:,.2f}')
    print(f'   2. Market moved up {((latest["spy_close"]/spy_open - 1)*100):.2f}% (calls ITM, puts OTM)')
    print(f'   3. SPX outperformed SPY by {((latest["spx_close"]/latest["spy_close"]) - (spx_open/spy_open))*100:.4f}%')
    print(f'      (This hurt us because we sold SPX calls)')

    print(f'\n   Starting capital: ${10000:,.2f}')
    print(f'   Ending capital:   ${10000 + total_pnl:,.2f}')
    print(f'   Return:           {(total_pnl/10000)*100:+.2f}%')


if __name__ == '__main__':
    detailed_breakdown()
