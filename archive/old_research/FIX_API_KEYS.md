# Fix Alpaca API Keys - "Request Not Authorized" Error

## The Problem

Getting error: `request is not authorized`

This means your API keys were generated from the **LIVE trading** dashboard instead of **PAPER trading**.

## The Solution (5 minutes)

### Step 1: Go to Paper Trading Dashboard

1. Login to Alpaca: https://alpaca.markets
2. **Look for a toggle/dropdown** at the top that says:
   - "Live Trading" / "Paper Trading"
   - OR "Live Money" / "Paper Money"
3. **Click to switch to "Paper Trading"**

### Step 2: Verify You're in Paper Mode

You should see:
- URL changes to: `https://app.alpaca.markets/paper/dashboard/overview`
- Dashboard header says "Paper Trading" or "Paper Money"
- Account balance shows "$100,000" (default paper money amount)

### Step 3: Generate NEW API Keys

1. In Paper Trading dashboard, click "API Keys" (left sidebar)
2. Click "Generate New Key" or "Create New Key"
3. Give it a name: "SPY-SPX-Bot"
4. **Copy BOTH values:**
   - API Key ID (starts with "PK" for paper or "AK")
   - Secret Key (long alphanumeric string)

### Step 4: Replace Keys in .env

Edit: `/Users/johnnyhuang/personal/optionsarbitrage/.env`

Replace with your NEW paper trading keys:
```
ALPACA_API_KEY=your_new_paper_key_here
ALPACA_SECRET_KEY=your_new_paper_secret_here
```

### Step 5: Test Again

```bash
cd /Users/johnnyhuang/personal/optionsarbitrage
python3 test_alpaca_connection.py
```

Should see: ✅ CONNECTION SUCCESSFUL!

---

## Still Not Working?

### Double-Check:

1. **Are you in Paper Trading mode?**
   - URL should have `/paper/` in it
   - Balance should be $100,000 (not your real money)

2. **Did you copy the FULL secret key?**
   - Secret key is usually 40+ characters
   - Make sure no spaces at beginning/end

3. **Are keys activated?**
   - Sometimes takes 1-2 minutes after generation
   - Try waiting 60 seconds and test again

4. **Delete old keys**
   - In Alpaca dashboard, delete any old keys
   - Generate completely fresh pair

---

## Quick Visual Guide

```
Alpaca Dashboard
├── [Toggle Here] → "Paper Trading" ← MUST BE SELECTED!
│
├── Dashboard (should say Paper Trading)
│   └── Balance: $100,000 (paper money)
│
└── API Keys ← Click here
    └── Generate New Key
        ├── API Key: PK... or AK...
        └── Secret: (long string)
```

---

## Next Steps

Once you get new Paper Trading keys:
1. Paste them here
2. I'll test connection
3. We'll proceed with building the Temporal-based automation

**Take your time - this is a common issue and easy to fix!**
