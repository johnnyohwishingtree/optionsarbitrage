# Data Collection Guide

## Single Unified Script: `collect_market_data.py`

This is the **only script** you need for collecting market data. It automatically pulls:
- SPY and SPX stock prices (5-minute bars, full day)
- SPY and SPX options within ±3% of current price (5-minute bars, full day)

---

## Usage

### Collect Today's Data (Default)
```bash
python collect_market_data.py
```

This will create:
- `data/underlying_prices_YYYYMMDD.csv` - SPY/SPX stock prices
- `data/options_data_YYYYMMDD.csv` - All options within ±3%

### Collect Specific Date
```bash
python collect_market_data.py --date 20260126
```

### Change Strike Range
```bash
# Use ±5% instead of default ±3%
python collect_market_data.py --range 0.05

# Use ±1%
python collect_market_data.py --range 0.01
```

---

## What It Collects

### Underlying Prices
- Symbol: SPY, SPX
- Data: Open, High, Low, Close, Volume
- Frequency: 5-minute bars
- Coverage: Full trading day (9:30 AM - 4:00 PM ET)

### Options Data
- Symbol: SPY, SPX
- Strikes: ±3% from current price (customizable)
- Rights: Calls and Puts
- Data: Open, High, Low, Close, Volume
- Frequency: 5-minute bars
- Coverage: Full trading day

### Strike Range Calculation
- **SPY**: ±3% rounded to nearest $1
  - Example: If SPY = $693.66, range is 673-714 (42 strikes)
- **SPX**: ±3% rounded to nearest $5
  - Example: If SPX = $6959.74, range is 6750-7170 (85 strikes)

---

## Output Files

### Format
All files are CSV format with headers.

### Underlying Prices Schema
```
symbol,time,open,high,low,close,volume
SPY,2026-01-26 09:30:00-05:00,693.50,693.80,693.40,693.70,1000000
```

### Options Data Schema
```
symbol,strike,right,time,open,high,low,close,volume
SPY,694,C,2026-01-26 09:30:00-05:00,2.50,2.55,2.48,2.52,5000
```

---

## Requirements

### Before Running
1. IB Gateway must be running
2. Connected to paper trading account (port 4002) or live account (port 4001)
3. Market data subscriptions active

### Dependencies
- ib_insync
- pandas
- IBKRClient (from src/broker/ibkr_client.py)

---

## Examples

### Daily After-Market Data Collection
Run this after market close (after 4:00 PM ET) to collect the full day's data:
```bash
python collect_market_data.py
```

### Historical Data Collection
If you need to collect data from a previous day:
```bash
python collect_market_data.py --date 20260123
```

### Wide Strike Range for Analysis
For comprehensive analysis across more strikes:
```bash
python collect_market_data.py --range 0.10  # ±10%
```

---

## Data Storage Convention

Files are named with dates for easy organization:
```
data/
├── underlying_prices_20260126.csv
├── options_data_20260126.csv
├── underlying_prices_20260127.csv
├── options_data_20260127.csv
└── ...
```

This allows you to:
- Easily identify which date the data is from
- Compare data across multiple days
- Keep historical data organized

---

## Troubleshooting

### "Failed to connect to IB Gateway"
- Ensure IB Gateway is running
- Check that port 4002 is correct (or 4001 for live)
- Verify no firewall blocking

### "No options data collected"
- Market may be closed (only works during or after market hours)
- Check if you have options data subscriptions
- Some far OTM strikes may have no trading activity (this is normal)

### Partial Data
Some far out-of-the-money options may have 0 bars if they had no trading activity. This is expected and the script handles it gracefully.

---

## Migration from Old Scripts

**All old data collection scripts have been archived:**
- `download_real_prices.py` → archived
- `fetch_real_data.py` → archived
- `etrade_data_pull.py` → archived
- `fetch_historical_intraday.py` → archived
- `fetch_underlying_prices.py` → archived
- `fetch_full_option_chain.py` → archived

**Use only `collect_market_data.py` going forward.**
